#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import Iterable, List

import duckdb


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "kals.duckdb"
ANALYTICS_SQL_PATH = REPO_ROOT / "data" / "analytics_views.sql"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect KALS Stage 2 DuckDB data.")
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="DuckDB file path. Default: data/kals.duckdb",
    )
    parser.add_argument(
        "--refresh-views",
        action="store_true",
        help="Refresh persistent analytics views before querying.",
    )
    parser.add_argument(
        "--recent-limit",
        type=int,
        default=10,
        help="How many recent events to print.",
    )
    parser.add_argument(
        "--weak-limit",
        type=int,
        default=10,
        help="How many weak items to print.",
    )
    parser.add_argument(
        "--confusion-limit",
        type=int,
        default=10,
        help="How many confusion pairs to print.",
    )
    parser.add_argument(
        "--first-pass-limit",
        type=int,
        default=10,
        help="How many first-pass rows to print.",
    )
    parser.add_argument(
        "--recency-limit",
        type=int,
        default=10,
        help="How many recent item recency rows to print.",
    )
    parser.add_argument(
        "--review-limit",
        type=int,
        default=10,
        help="How many prioritized review candidates to print.",
    )
    parser.add_argument(
        "--app-summary-limit",
        type=int,
        default=10,
        help="How many next-session app summary rows to print.",
    )
    parser.add_argument(
        "--app-usage-limit",
        type=int,
        default=10,
        help="How many recent app usage rows to print.",
    )
    return parser


def refresh_views(db_path: Path) -> None:
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(ANALYTICS_SQL_PATH.read_text(encoding="utf-8"))
    finally:
        conn.close()


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


def main() -> int:
    args = build_parser().parse_args()
    db_path = Path(args.db_path)

    if args.refresh_views:
        refresh_views(db_path)

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        app_counts = conn.execute(
            """
            SELECT app, attempts, sessions, passes, fails, accuracy_pct, avg_response_ms
            FROM event_counts_by_app
            ORDER BY app
            """
        ).fetchall()

        recent_events = conn.execute(
            """
            SELECT app, item_id, result, response_time_ms, timestamp_utc
            FROM raw_attempt_events
            ORDER BY timestamp_utc DESC
            LIMIT ?
            """,
            [args.recent_limit],
        ).fetchall()

        weak_items = conn.execute(
            """
            SELECT app, item_id, shown_value, attempts, fails, accuracy_pct, avg_response_ms
            FROM weak_items
            WHERE attempts >= 1
            ORDER BY accuracy_pct ASC, attempts DESC, item_id ASC
            LIMIT ?
            """,
            [args.weak_limit],
        ).fetchall()

        confusion_pairs = conn.execute(
            """
            SELECT app, item_id, shown_value, correct_answer, chosen_wrong_answer, misses
            FROM confusion_pairs
            ORDER BY misses DESC, item_id ASC, chosen_wrong_answer ASC
            LIMIT ?
            """,
            [args.confusion_limit],
        ).fetchall()

        first_pass_rows = conn.execute(
            """
            SELECT app, item_id, shown_value, first_attempt_sessions, first_fails, first_pass_accuracy_pct, avg_first_attempt_ms
            FROM first_pass_accuracy
            ORDER BY first_pass_accuracy_pct ASC, first_attempt_sessions DESC, item_id ASC
            LIMIT ?
            """,
            [args.first_pass_limit],
        ).fetchall()

        recency_rows = conn.execute(
            """
            SELECT app, item_id, shown_value, attempts, latest_result, minutes_since_last_seen, lifetime_accuracy_pct
            FROM item_recency
            ORDER BY last_seen_utc DESC, item_id ASC
            LIMIT ?
            """,
            [args.recency_limit],
        ).fetchall()

        review_candidates = conn.execute(
            """
            SELECT
              app,
              item_id,
              shown_value,
              fails,
              latest_result,
              first_fails,
              lifetime_accuracy_pct,
              review_priority_score
            FROM prioritized_review_candidates
            ORDER BY review_priority_score DESC, app ASC, item_id ASC
            LIMIT ?
            """,
            [args.review_limit],
        ).fetchall()

        app_usage_rows = conn.execute(
            """
            SELECT
              app,
              sessions_seen,
              last_session_rank,
              last_session_attempt_count,
              last_session_fail_count,
              sessions_in_last_3
            FROM recent_app_usage
            ORDER BY last_session_rank ASC, app ASC
            LIMIT ?
            """,
            [args.app_usage_limit],
        ).fetchall()

        app_summaries = conn.execute(
            """
            SELECT
              app,
              review_candidate_count,
              urgent_review_count,
              nonperfect_items,
              accuracy_pct,
              last_session_rank,
              last_session_fail_count,
              recent_session_adjustment,
              top_candidate_item_id,
              top_candidate_shown_value,
              next_app_priority_score
            FROM next_session_app_summary
            ORDER BY next_app_priority_score DESC, app ASC
            LIMIT ?
            """,
            [args.app_summary_limit],
        ).fetchall()
    finally:
        conn.close()

    print_table(
        "Counts By App",
        ["app", "attempts", "sessions", "passes", "fails", "accuracy_pct", "avg_response_ms"],
        app_counts,
    )
    print_table(
        "Recent Events",
        ["app", "item_id", "result", "response_time_ms", "timestamp_utc"],
        recent_events,
    )
    print_table(
        "Weak Items",
        ["app", "item_id", "shown_value", "attempts", "fails", "accuracy_pct", "avg_response_ms"],
        weak_items,
    )
    print_table(
        "Confusion Pairs",
        ["app", "item_id", "shown_value", "correct_answer", "chosen_wrong_answer", "misses"],
        confusion_pairs,
    )
    print_table(
        "First-Pass Accuracy",
        ["app", "item_id", "shown_value", "first_attempt_sessions", "first_fails", "first_pass_accuracy_pct", "avg_first_attempt_ms"],
        first_pass_rows,
    )
    print_table(
        "Item Recency",
        ["app", "item_id", "shown_value", "attempts", "latest_result", "minutes_since_last_seen", "lifetime_accuracy_pct"],
        recency_rows,
    )
    print_table(
        "Prioritized Review Candidates",
        ["app", "item_id", "shown_value", "fails", "latest_result", "first_fails", "lifetime_accuracy_pct", "review_priority_score"],
        review_candidates,
    )
    print_table(
        "Recent App Usage",
        ["app", "sessions_seen", "last_session_rank", "last_session_attempt_count", "last_session_fail_count", "sessions_in_last_3"],
        app_usage_rows,
    )
    print_table(
        "Next-Session App Summary",
        ["app", "review_candidate_count", "urgent_review_count", "nonperfect_items", "accuracy_pct", "last_session_rank", "last_session_fail_count", "recent_session_adjustment", "top_candidate_item_id", "top_candidate_shown_value", "next_app_priority_score"],
        app_summaries,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
