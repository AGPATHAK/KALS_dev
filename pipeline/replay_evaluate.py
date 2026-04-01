#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

import duckdb

from recommendation_logic import (
    DEFAULT_DB_PATH,
    RECOMMENDER_VERSION,
    SCHEMA_SQL_PATH,
    generate_recommendation,
    make_hash,
    refresh_views,
    refresh_views_connection,
)


RAW_EVENT_COLUMNS = [
    "event_uid",
    "session_id",
    "app",
    "app_version",
    "item_id",
    "item_type",
    "shown_value",
    "correct_answer",
    "user_answer",
    "choices_presented_json",
    "result",
    "response_time_ms",
    "timestamp_utc",
    "mode",
    "distractor_mode",
    "difficulty",
    "intervention_id",
    "source_page",
    "ingested_at_utc",
    "raw_event_json",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay-evaluate the deterministic recommender against historical sessions.")
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="DuckDB file path. Default: data/kals.duckdb",
    )
    parser.add_argument(
        "--refresh-views",
        action="store_true",
        help="Refresh persistent analytics views in the source database before replaying.",
    )
    parser.add_argument(
        "--top-items",
        type=int,
        default=5,
        help="How many review items to include in replayed recommendations.",
    )
    parser.add_argument(
        "--top-apps",
        type=int,
        default=3,
        help="How many ranked apps to include in replayed recommendations.",
    )
    parser.add_argument(
        "--session-limit",
        type=int,
        default=0,
        help="Optional cap on how many historical sessions to replay. Default: 0 means all.",
    )
    parser.add_argument(
        "--show-limit",
        type=int,
        default=10,
        help="How many per-session replay rows to print.",
    )
    parser.add_argument(
        "--save-run",
        action="store_true",
        help="Persist replay evaluation rows into the replay_evaluation_runs table.",
    )
    return parser


def format_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def print_table(title: str, columns: List[str], rows: Iterable[tuple]) -> None:
    rows = list(rows)
    print(f"\n{title}")
    if not rows:
        print("- no rows")
        return

    widths = [len(col) for col in columns]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(str(value)))

    header = " | ".join(col.ljust(widths[idx]) for idx, col in enumerate(columns))
    divider = "-+-".join("-" * widths[idx] for idx in range(len(columns)))
    print(header)
    print(divider)
    for row in rows:
        print(" | ".join(str(value).ljust(widths[idx]) for idx, value in enumerate(row)))


def fetch_sessions(conn: duckdb.DuckDBPyConnection, session_limit: int) -> List[tuple]:
    sql = """
        SELECT
          session_id,
          app,
          MIN(timestamp_utc) AS session_start_utc,
          MAX(timestamp_utc) AS session_end_utc,
          COUNT(*) AS attempt_count,
          SUM(CASE WHEN result = 'fail' THEN 1 ELSE 0 END) AS fail_count
        FROM raw_attempt_events
        GROUP BY session_id, app
        ORDER BY session_start_utc ASC, app ASC
    """
    if session_limit > 0:
        sql += " LIMIT ?"
        return conn.execute(sql, [session_limit]).fetchall()
    return conn.execute(sql).fetchall()


def fetch_prior_rows(conn: duckdb.DuckDBPyConnection, session_start_utc: datetime) -> List[tuple]:
    sql = f"""
        SELECT {", ".join(RAW_EVENT_COLUMNS)}
        FROM raw_attempt_events
        WHERE timestamp_utc < ?
        ORDER BY timestamp_utc ASC, event_uid ASC
    """
    return conn.execute(sql, [session_start_utc]).fetchall()


def load_prior_rows(rows: List[tuple]) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute(SCHEMA_SQL_PATH.read_text(encoding="utf-8"))
    if rows:
        placeholders = ", ".join(["?"] * len(RAW_EVENT_COLUMNS))
        conn.executemany(
            f"INSERT INTO raw_attempt_events ({', '.join(RAW_EVENT_COLUMNS)}) VALUES ({placeholders})",
            rows,
        )
    refresh_views_connection(conn)
    return conn


def fetch_actual_failed_items(conn: duckdb.DuckDBPyConnection, session_id: str) -> List[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT item_id
        FROM raw_attempt_events
        WHERE session_id = ?
          AND result = 'fail'
        ORDER BY item_id ASC
        """,
        [session_id],
    ).fetchall()
    return [row[0] for row in rows]


def fetch_actual_seen_items(conn: duckdb.DuckDBPyConnection, session_id: str) -> List[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT item_id
        FROM raw_attempt_events
        WHERE session_id = ?
        ORDER BY item_id ASC
        """,
        [session_id],
    ).fetchall()
    return [row[0] for row in rows]


def make_evaluation_row(
    *,
    db_path: Path,
    target_session: tuple,
    prior_event_count: int,
    payload: dict,
    actual_seen_items: List[str],
    actual_failed_items: List[str],
) -> tuple:
    session_id, target_app, session_start_utc, session_end_utc, attempt_count, fail_count = target_session
    predicted_app = payload["recommended_app"]["app"]
    predicted_session_size = payload["recommended_app"]["recommended_session_size"]
    predicted_top_item_ids = [item["item_id"] for item in payload["top_review_items"]]
    item_seen_count = len(set(predicted_top_item_ids) & set(actual_seen_items))
    item_seen_rate = None
    if actual_seen_items:
        item_seen_rate = round(100.0 * item_seen_count / len(actual_seen_items), 1)
    item_hit_count = len(set(predicted_top_item_ids) & set(actual_failed_items))
    item_hit_rate = None
    if actual_failed_items:
        item_hit_rate = round(100.0 * item_hit_count / len(actual_failed_items), 1)
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    evaluation_id = make_hash(
        json.dumps(
            {
                "evaluation_mode": "pre_session_replay",
                "recommender_version": RECOMMENDER_VERSION,
                "target_session_id": session_id,
                "payload_json": payload_json,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    return (
        evaluation_id,
        datetime.now(timezone.utc).isoformat(),
        str(db_path),
        "pre_session_replay",
        RECOMMENDER_VERSION,
        session_id,
        target_app,
        format_utc(session_start_utc),
        format_utc(session_end_utc),
        prior_event_count,
        attempt_count,
        fail_count,
        predicted_app,
        predicted_session_size,
        predicted_app == target_app,
        json.dumps(predicted_top_item_ids, ensure_ascii=False),
        json.dumps(actual_seen_items, ensure_ascii=False),
        json.dumps(actual_failed_items, ensure_ascii=False),
        item_seen_count,
        item_seen_rate,
        item_hit_count,
        item_hit_rate,
        payload_json,
    )


def save_evaluations(db_path: Path, rows: List[tuple]) -> None:
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(SCHEMA_SQL_PATH.read_text(encoding="utf-8"))
        conn.executemany(
            """
            INSERT OR REPLACE INTO replay_evaluation_runs (
              evaluation_id,
              created_at_utc,
              source_db_path,
              evaluation_mode,
              recommender_version,
              target_session_id,
              target_app,
              target_session_start_utc,
              target_session_end_utc,
              prior_event_count,
              target_attempt_count,
              target_fail_count,
              predicted_app,
              predicted_session_size,
              app_match,
              predicted_top_items_json,
              actual_seen_items_json,
              actual_failed_items_json,
              item_seen_count,
              item_seen_rate,
              item_hit_count,
              item_hit_rate,
              payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    finally:
        conn.close()


def main() -> int:
    args = build_parser().parse_args()
    db_path = Path(args.db_path)

    if args.refresh_views:
        refresh_views(db_path)

    source_conn = duckdb.connect(str(db_path), read_only=True)
    try:
        sessions = fetch_sessions(source_conn, args.session_limit)
        evaluation_rows = []
        skipped_no_history = 0

        for target_session in sessions:
            session_id, _, session_start_utc, _, _, _ = target_session
            prior_rows = fetch_prior_rows(source_conn, session_start_utc)
            if not prior_rows:
                skipped_no_history += 1
                continue

            replay_conn = load_prior_rows(prior_rows)
            try:
                payload = generate_recommendation(
                    replay_conn,
                    db_path=db_path,
                    top_items_limit=args.top_items,
                    top_apps_limit=args.top_apps,
                    generated_at_utc=format_utc(session_start_utc),
                )
            finally:
                replay_conn.close()

            if not payload:
                continue

            actual_seen_items = fetch_actual_seen_items(source_conn, session_id)
            actual_failed_items = fetch_actual_failed_items(source_conn, session_id)
            evaluation_rows.append(
                make_evaluation_row(
                    db_path=db_path,
                    target_session=target_session,
                    prior_event_count=len(prior_rows),
                    payload=payload,
                    actual_seen_items=actual_seen_items,
                    actual_failed_items=actual_failed_items,
                )
            )
    finally:
        source_conn.close()

    if args.save_run and evaluation_rows:
        save_evaluations(db_path, evaluation_rows)

    replayed_sessions = len(evaluation_rows)
    app_match_count = sum(1 for row in evaluation_rows if row[14] is True)
    total_seen_items = sum(len(json.loads(row[16])) for row in evaluation_rows)
    total_failed_items = sum(len(json.loads(row[17])) for row in evaluation_rows)
    total_item_seen_hits = sum((row[18] or 0) for row in evaluation_rows)
    total_item_hits = sum(row[20] for row in evaluation_rows)
    sessions_with_failures = sum(1 for row in evaluation_rows if row[11] > 0)
    sessions_with_item_seen_hits = sum(1 for row in evaluation_rows if (row[18] or 0) > 0)
    sessions_with_item_hits = sum(1 for row in evaluation_rows if row[20] > 0)

    print("Replay Evaluation Summary")
    print(f"- sessions_seen: {len(sessions)}")
    print(f"- skipped_no_history: {skipped_no_history}")
    print(f"- replayed_sessions: {replayed_sessions}")
    print(f"- app_match_count: {app_match_count}")
    if replayed_sessions:
        print(f"- app_match_rate_pct: {round(100.0 * app_match_count / replayed_sessions, 1)}")
    print(f"- sessions_with_failures: {sessions_with_failures}")
    print(f"- sessions_with_item_seen_hits: {sessions_with_item_seen_hits}")
    print(f"- sessions_with_item_hits: {sessions_with_item_hits}")
    print(f"- total_seen_items: {total_seen_items}")
    print(f"- total_failed_items: {total_failed_items}")
    print(f"- total_item_seen_hits: {total_item_seen_hits}")
    print(f"- total_item_hits: {total_item_hits}")
    if total_seen_items:
        print(f"- item_seen_rate_pct: {round(100.0 * total_item_seen_hits / total_seen_items, 1)}")
    if total_failed_items:
        print(f"- item_hit_rate_pct: {round(100.0 * total_item_hits / total_failed_items, 1)}")
    if args.save_run and evaluation_rows:
        print(f"- replay_rows_saved: {len(evaluation_rows)}")

    print_table(
        "Per-Session Replay",
        [
            "target_app",
            "predicted_app",
            "app_match",
            "target_fail_count",
            "item_seen_count",
            "item_seen_rate",
            "item_hit_count",
            "item_hit_rate",
            "prior_event_count",
            "target_session_id",
        ],
        [
            (
                row[6],
                row[12],
                row[14],
                row[11],
                row[18],
                row[19],
                row[20],
                row[21],
                row[9],
                row[5],
            )
            for row in evaluation_rows[: args.show_limit]
        ],
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
