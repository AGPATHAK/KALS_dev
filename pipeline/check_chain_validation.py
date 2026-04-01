#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import Iterable, List

import duckdb

from recommendation_logic import DEFAULT_DB_PATH, refresh_views


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check whether the guided-session chain has been validated across all apps."
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="DuckDB file path. Default: data/kals.duckdb",
    )
    parser.add_argument(
        "--refresh-views",
        action="store_true",
        help="Refresh persistent analytics views before checking.",
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
        rows = conn.execute(
            """
            SELECT
              app,
              guided_sessions,
              sessions_with_focus_items,
              sessions_with_focus_seen,
              validation_status,
              next_validation_action
            FROM guided_chain_validation_status
            ORDER BY app ASC
            """
        ).fetchall()
    finally:
        conn.close()

    print_table(
        "Guided Chain Validation Status",
        [
            "app",
            "guided_sessions",
            "sessions_with_focus_items",
            "sessions_with_focus_seen",
            "validation_status",
            "next_validation_action",
        ],
        rows,
    )

    fully_validated = [row[0] for row in rows if row[4] == "validated"]
    pending = [row[0] for row in rows if row[4] != "validated"]

    print("\nSummary")
    print(f"- validated_apps: {', '.join(fully_validated) if fully_validated else 'none'}")
    print(f"- pending_apps: {', '.join(pending) if pending else 'none'}")
    print(f"- all_apps_validated: {'yes' if not pending else 'no'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
