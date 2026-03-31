#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import List

import duckdb


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "kals.duckdb"
ANALYTICS_SQL_PATH = REPO_ROOT / "data" / "analytics_views.sql"


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
    return parser


def refresh_views(db_path: Path) -> None:
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(ANALYTICS_SQL_PATH.read_text(encoding="utf-8"))
    finally:
        conn.close()


def format_row(prefix: str, parts: List[str]) -> None:
    print(f"{prefix} " + " | ".join(parts))


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

    app, review_count, urgent_count, nonperfect_items, accuracy_pct, top_item_id, top_item_value, score = recommended_app
    session_size, session_size_reason = recommend_session_size(app, urgent_count, review_count, accuracy_pct)

    print("Next Session Recommendation")
    print(f"- recommended_app: {app}")
    print(f"- app_priority_score: {score}")
    print(f"- why: {urgent_count} urgent review candidate(s), {review_count} total review candidate(s), accuracy {accuracy_pct}%")
    print(f"- recommended_session_size: {session_size}")
    print(f"- session_size_reason: {session_size_reason}")
    if top_item_id:
        print(f"- top_driver: {top_item_id} ({top_item_value})")
    if nonperfect_items:
        print(f"- nonperfect_items_seen: {nonperfect_items}")

    print("\nTop Review Items For Recommended App")
    if not top_items:
        print("- no item-level candidates yet")
    else:
        for idx, row in enumerate(top_items, start=1):
            item_id, shown_value, fails, latest_result, first_fails, lifetime_accuracy_pct, priority_score = row
            format_row(
                f"{idx}.",
                [
                    f"{item_id}",
                    f"shown={shown_value}",
                    f"fails={fails}",
                    f"latest={latest_result}",
                    f"first_fails={first_fails}",
                    f"accuracy={lifetime_accuracy_pct}%",
                    f"score={priority_score}",
                ],
            )

    print("\nApp Ranking")
    for idx, row in enumerate(app_ranking, start=1):
        rank_app, rank_review_count, rank_urgent_count, rank_accuracy_pct, rank_score = row
        format_row(
            f"{idx}.",
            [
                rank_app,
                f"review_candidates={rank_review_count}",
                f"urgent={rank_urgent_count}",
                f"accuracy={rank_accuracy_pct}%",
                f"score={rank_score}",
            ],
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
