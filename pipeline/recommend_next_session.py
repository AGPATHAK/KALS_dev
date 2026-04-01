#!/usr/bin/env python3

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import duckdb


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "kals.duckdb"
ANALYTICS_SQL_PATH = REPO_ROOT / "data" / "analytics_views.sql"
SCHEMA_SQL_PATH = REPO_ROOT / "data" / "schema.sql"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Produce a deterministic next-session recommendation from Stage 2.5 analytics.")
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="DuckDB file path. Default: data/kals.duckdb",
    )
    parser.add_argument(
        "--refresh-views",
        action="store_true",
        help="Refresh persistent analytics views before recommending.",
    )
    parser.add_argument(
        "--top-items",
        type=int,
        default=5,
        help="How many review items to include for the recommended app.",
    )
    parser.add_argument(
        "--top-apps",
        type=int,
        default=3,
        help="How many app summaries to show in the app ranking.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format for the recommendation payload.",
    )
    parser.add_argument(
        "--save-run",
        action="store_true",
        help="Persist the recommendation payload into the recommendation_runs table.",
    )
    return parser


def refresh_views(db_path: Path) -> None:
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(ANALYTICS_SQL_PATH.read_text(encoding="utf-8"))
    finally:
        conn.close()


def format_row(prefix: str, parts: List[str]) -> None:
    print(f"{prefix} " + " | ".join(parts))


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_recommendation_id(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def recommend_session_size(app: str, urgent_count: int, review_count: int, accuracy_pct: float) -> tuple:
    if app == "words":
        if urgent_count >= 2 or accuracy_pct < 85.0:
            return 10, "keep the words session short because current review pressure is meaningful"
        return 20, "use a standard words session because current review pressure is light"

    if urgent_count >= 3 or accuracy_pct < 75.0:
        return 5, "keep the session tightly focused because there are several urgent review items"

    if review_count >= 2 or accuracy_pct < 85.0:
        return 10, "use a moderate session size to cover the main review items without overloading the session"

    return 10, "use the default session size because review pressure is currently light"


def build_payload(
    *,
    db_path: Path,
    recommended_app_row: tuple,
    top_items: List[tuple],
    app_ranking: List[tuple],
) -> Dict:
    (
        app,
        review_count,
        urgent_count,
        nonperfect_items,
        accuracy_pct,
        top_item_id,
        top_item_value,
        score,
    ) = recommended_app_row
    session_size, session_size_reason = recommend_session_size(app, urgent_count, review_count, accuracy_pct)
    rationale_summary = (
        f"{urgent_count} urgent review candidate(s), "
        f"{review_count} total review candidate(s), "
        f"accuracy {accuracy_pct}%"
    )

    payload = {
        "generated_at_utc": now_utc_iso(),
        "source_db_path": str(db_path),
        "recommended_app": {
            "app": app,
            "app_priority_score": score,
            "recommended_session_size": session_size,
            "session_size_reason": session_size_reason,
            "rationale_summary": rationale_summary,
            "review_candidate_count": review_count,
            "urgent_review_count": urgent_count,
            "nonperfect_items_seen": nonperfect_items,
            "top_driver": {
                "item_id": top_item_id,
                "shown_value": top_item_value,
            },
        },
        "top_review_items": [
            {
                "item_id": item_id,
                "shown_value": shown_value,
                "fails": fails,
                "latest_result": latest_result,
                "first_fails": first_fails,
                "lifetime_accuracy_pct": lifetime_accuracy_pct,
                "review_priority_score": priority_score,
            }
            for (
                item_id,
                shown_value,
                fails,
                latest_result,
                first_fails,
                lifetime_accuracy_pct,
                priority_score,
            ) in top_items
        ],
        "app_ranking": [
            {
                "app": rank_app,
                "review_candidate_count": rank_review_count,
                "urgent_review_count": rank_urgent_count,
                "accuracy_pct": rank_accuracy_pct,
                "next_app_priority_score": rank_score,
            }
            for (
                rank_app,
                rank_review_count,
                rank_urgent_count,
                rank_accuracy_pct,
                rank_score,
            ) in app_ranking
        ],
    }
    return payload


def save_recommendation_run(db_path: Path, payload: Dict) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    recommendation_id = make_recommendation_id(payload_json)
    recommended = payload["recommended_app"]

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(SCHEMA_SQL_PATH.read_text(encoding="utf-8"))
        conn.execute(
            """
            INSERT OR REPLACE INTO recommendation_runs (
              recommendation_id,
              created_at_utc,
              source_db_path,
              recommended_app,
              app_priority_score,
              recommended_session_size,
              rationale_summary,
              top_driver_item_id,
              top_driver_shown_value,
              payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                recommendation_id,
                payload["generated_at_utc"],
                payload["source_db_path"],
                recommended["app"],
                recommended["app_priority_score"],
                recommended["recommended_session_size"],
                recommended["rationale_summary"],
                recommended["top_driver"]["item_id"],
                recommended["top_driver"]["shown_value"],
                payload_json,
            ],
        )
    finally:
        conn.close()
    return recommendation_id


def print_text_recommendation(payload: Dict) -> None:
    recommended = payload["recommended_app"]
    top_items = payload["top_review_items"]
    app_ranking = payload["app_ranking"]

    print("Next Session Recommendation")
    print(f"- recommended_app: {recommended['app']}")
    print(f"- app_priority_score: {recommended['app_priority_score']}")
    print(f"- why: {recommended['rationale_summary']}")
    print(f"- recommended_session_size: {recommended['recommended_session_size']}")
    print(f"- session_size_reason: {recommended['session_size_reason']}")
    if recommended["top_driver"]["item_id"]:
        print(f"- top_driver: {recommended['top_driver']['item_id']} ({recommended['top_driver']['shown_value']})")
    if recommended["nonperfect_items_seen"]:
        print(f"- nonperfect_items_seen: {recommended['nonperfect_items_seen']}")

    print("\nTop Review Items For Recommended App")
    if not top_items:
        print("- no item-level candidates yet")
    else:
        for idx, item in enumerate(top_items, start=1):
            format_row(
                f"{idx}.",
                [
                    item["item_id"],
                    f"shown={item['shown_value']}",
                    f"fails={item['fails']}",
                    f"latest={item['latest_result']}",
                    f"first_fails={item['first_fails']}",
                    f"accuracy={item['lifetime_accuracy_pct']}%",
                    f"score={item['review_priority_score']}",
                ],
            )

    print("\nApp Ranking")
    for idx, row in enumerate(app_ranking, start=1):
        format_row(
            f"{idx}.",
            [
                row["app"],
                f"review_candidates={row['review_candidate_count']}",
                f"urgent={row['urgent_review_count']}",
                f"accuracy={row['accuracy_pct']}%",
                f"score={row['next_app_priority_score']}",
            ],
        )


def main() -> int:
    args = build_parser().parse_args()
    db_path = Path(args.db_path)

    if args.refresh_views:
        refresh_views(db_path)

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        recommended_app = conn.execute(
            """
            SELECT
              app,
              review_candidate_count,
              urgent_review_count,
              nonperfect_items,
              accuracy_pct,
              top_candidate_item_id,
              top_candidate_shown_value,
              next_app_priority_score
            FROM next_session_app_summary
            ORDER BY next_app_priority_score DESC, app ASC
            LIMIT 1
            """
        ).fetchone()

        app_ranking = conn.execute(
            """
            SELECT
              app,
              review_candidate_count,
              urgent_review_count,
              accuracy_pct,
              next_app_priority_score
            FROM next_session_app_summary
            ORDER BY next_app_priority_score DESC, app ASC
            LIMIT ?
            """,
            [args.top_apps],
        ).fetchall()

        if not recommended_app:
            print("No recommendation available yet. Ingest more events first.")
            return 0

        top_items = conn.execute(
            """
            SELECT
              item_id,
              shown_value,
              fails,
              latest_result,
              first_fails,
              lifetime_accuracy_pct,
              review_priority_score
            FROM prioritized_review_candidates
            WHERE app = ?
            ORDER BY review_priority_score DESC, item_id ASC
            LIMIT ?
            """,
            [recommended_app[0], args.top_items],
        ).fetchall()
    finally:
        conn.close()

    payload = build_payload(
        db_path=db_path,
        recommended_app_row=recommended_app,
        top_items=top_items,
        app_ranking=app_ranking,
    )

    recommendation_id = None
    if args.save_run:
        recommendation_id = save_recommendation_run(db_path, payload)

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_text_recommendation(payload)
        if recommendation_id:
            print(f"\nSaved Recommendation Run\n- recommendation_id: {recommendation_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
