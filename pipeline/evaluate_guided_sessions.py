#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import Iterable, List

import duckdb

from recommendation_logic import DEFAULT_DB_PATH, refresh_views


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate guided sessions and suggest the next follow-up action."
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="DuckDB file path. Default: data/kals.duckdb",
    )
    parser.add_argument(
        "--refresh-views",
        action="store_true",
        help="Refresh persistent analytics views before evaluating.",
    )
    parser.add_argument(
        "--session-limit",
        type=int,
        default=10,
        help="How many recent guided sessions to print.",
    )
    parser.add_argument(
        "--summary-limit",
        type=int,
        default=10,
        help="How many grouped follow-up summary rows to print.",
    )
    parser.add_argument(
        "--comparison-limit",
        type=int,
        default=10,
        help="How many guided-vs-normal comparison rows to print.",
    )
    return parser


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
        guided_sessions = conn.execute(
            """
            SELECT
              app,
              intervention_id,
              top_driver_item_id,
              attempts,
              fails,
              accuracy_pct,
              focus_item_count,
              focus_items_seen_count,
              focus_items_failed_count,
              focus_item_surface_rate_pct,
              focus_item_clear_rate_pct,
              guided_outcome,
              follow_up_action
            FROM guided_session_evaluation
            ORDER BY session_end_utc DESC, app ASC
            LIMIT ?
            """,
            [args.session_limit],
        ).fetchall()

        follow_up_summary = conn.execute(
            """
            SELECT
              app,
              guided_outcome,
              follow_up_action,
              session_count,
              avg_accuracy_pct,
              avg_focus_surface_rate_pct,
              avg_focus_clear_rate_pct
            FROM guided_follow_up_summary
            ORDER BY last_session_end_utc DESC, app ASC, guided_outcome ASC
            LIMIT ?
            """,
            [args.summary_limit],
        ).fetchall()

        comparison_rows = conn.execute(
            """
            SELECT
              app,
              normal_sessions,
              normal_accuracy_pct,
              guided_sessions,
              guided_accuracy_pct,
              accuracy_delta_pct,
              response_time_delta_ms
            FROM guided_vs_normal_app_comparison
            WHERE guided_sessions > 0
            ORDER BY app ASC
            LIMIT ?
            """,
            [args.comparison_limit],
        ).fetchall()
    finally:
        conn.close()

    print_table(
        "Guided Session Evaluation",
        [
            "app",
            "intervention_id",
            "top_driver_item_id",
            "attempts",
            "fails",
            "accuracy_pct",
            "focus_item_count",
            "focus_items_seen_count",
            "focus_items_failed_count",
            "focus_item_surface_rate_pct",
            "focus_item_clear_rate_pct",
            "guided_outcome",
            "follow_up_action",
        ],
        guided_sessions,
    )
    print_table(
        "Guided Follow-Up Summary",
        [
            "app",
            "guided_outcome",
            "follow_up_action",
            "session_count",
            "avg_accuracy_pct",
            "avg_focus_surface_rate_pct",
            "avg_focus_clear_rate_pct",
        ],
        follow_up_summary,
    )
    print_table(
        "Guided vs Normal Comparison (Apps With Guided Data)",
        [
            "app",
            "normal_sessions",
            "normal_accuracy_pct",
            "guided_sessions",
            "guided_accuracy_pct",
            "accuracy_delta_pct",
            "response_time_delta_ms",
        ],
        comparison_rows,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
