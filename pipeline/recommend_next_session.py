#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
from typing import Dict, List

import duckdb

from recommendation_logic import DEFAULT_DB_PATH, generate_recommendation, refresh_views, save_recommendation_run


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
        choices=["text", "json", "handoff"],
        default="text",
        help="Output format for the recommendation payload.",
    )
    parser.add_argument(
        "--save-run",
        action="store_true",
        help="Persist the recommendation payload into the recommendation_runs table.",
    )
    return parser


def format_row(prefix: str, parts: List[str]) -> None:
    print(f"{prefix} " + " | ".join(parts))


def print_text_recommendation(payload: Dict) -> None:
    recommended = payload["recommended_app"]
    top_items = payload["top_review_items"]
    app_ranking = payload["app_ranking"]
    handoff = payload["handoff"]

    print("Next Session Recommendation")
    print(f"- recommended_app: {recommended['app']}")
    print(f"- app_priority_score: {recommended['app_priority_score']}")
    print(f"- contract_version: {payload['recommendation_contract_version']}")
    print(f"- selection_policy: {recommended['selection_policy']}")
    print(f"- selection_reason: {recommended['selection_reason']}")
    print(f"- why: {recommended['rationale_summary']}")
    print(f"- recommended_session_size: {recommended['recommended_session_size']}")
    print(f"- session_size_reason: {recommended['session_size_reason']}")
    if recommended["top_driver"]["item_id"]:
        print(f"- top_driver: {recommended['top_driver']['item_id']} ({recommended['top_driver']['shown_value']})")
    if recommended["nonperfect_items_seen"]:
        print(f"- nonperfect_items_seen: {recommended['nonperfect_items_seen']}")

    print("\nHandoff Contract")
    print(f"- action: {handoff['action']}")
    print(f"- delivery_mode: {handoff['delivery_mode']}")
    print(f"- target_app: {handoff['target_app']}")
    print(f"- target_mode: {handoff['target_mode']}")
    print(f"- session_size: {handoff['session_size']}")
    print(f"- focus_strategy: {handoff['focus_strategy']}")
    print(f"- ui_message: {handoff['ui_message']}")
    if handoff["focus_item_ids"]:
        print(f"- focus_item_ids: {', '.join(handoff['focus_item_ids'])}")

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
                f"last_session_rank={row['last_session_rank']}",
                f"last_session_fails={row['last_session_fail_count']}",
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
        payload = generate_recommendation(
            conn,
            db_path=db_path,
            top_items_limit=args.top_items,
            top_apps_limit=args.top_apps,
        )
    finally:
        conn.close()

    if not payload:
        print("No recommendation available yet. Ingest more events first.")
        return 0

    recommendation_id = None
    if args.save_run:
        recommendation_id = save_recommendation_run(db_path, payload)

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.format == "handoff":
        print(json.dumps(payload["handoff"], ensure_ascii=False, indent=2))
    else:
        print_text_recommendation(payload)
        if recommendation_id:
            print(f"\nSaved Recommendation Run\n- recommendation_id: {recommendation_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
