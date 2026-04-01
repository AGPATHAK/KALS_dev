#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
from playwright.sync_api import sync_playwright

from recommendation_logic import (
    DEFAULT_DB_PATH,
    SCHEMA_SQL_PATH,
    generate_recommendation,
    make_hash,
    refresh_views,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE_DIR = REPO_ROOT / ".playwright-profile"
APP_PAGES = {
    "alphabet": REPO_ROOT / "alphabet" / "index.html",
    "matras": REPO_ROOT / "matras" / "index.html",
    "conjuncts": REPO_ROOT / "conjuncts" / "index.html",
    "words": REPO_ROOT / "words" / "index.html",
}
LATEST_HANDOFF_KEY = "kals_latest_recommendation_handoff"
PENDING_HANDOFF_KEY = "kals_pending_recommendation_handoff"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deliver the current recommendation handoff into the Playwright app environment.")
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="DuckDB file path. Default: data/kals.duckdb",
    )
    parser.add_argument(
        "--refresh-views",
        action="store_true",
        help="Refresh persistent analytics views before generating the handoff.",
    )
    parser.add_argument(
        "--top-items",
        type=int,
        default=5,
        help="How many review items to include in the generated handoff.",
    )
    parser.add_argument(
        "--top-apps",
        type=int,
        default=3,
        help="How many ranked apps to include in the generated payload.",
    )
    parser.add_argument(
        "--profile-dir",
        default=str(DEFAULT_PROFILE_DIR),
        help="Persistent Playwright browser profile directory.",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Run Chromium visibly instead of headless.",
    )
    parser.add_argument(
        "--save-run",
        action="store_true",
        help="Persist the handoff delivery row into the handoff_delivery_runs table.",
    )
    return parser


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_delivery_run(
    *,
    db_path: Path,
    handoff: dict,
    profile_dir: Path,
    source_page: str,
    verified: bool,
) -> str:
    handoff_json = json.dumps(handoff, ensure_ascii=False, sort_keys=True)
    delivery_id = make_hash(
        json.dumps(
            {
                "created_at_utc": now_utc_iso(),
                "profile_dir": str(profile_dir),
                "source_page": source_page,
                "handoff_json": handoff_json,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(SCHEMA_SQL_PATH.read_text(encoding="utf-8"))
        conn.execute(
            """
            INSERT OR REPLACE INTO handoff_delivery_runs (
              delivery_id,
              created_at_utc,
              source_db_path,
              contract_version,
              recommended_app,
              delivery_mode,
              profile_dir,
              source_page,
              latest_storage_key,
              pending_storage_key,
              focus_item_count,
              verified,
              handoff_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                delivery_id,
                now_utc_iso(),
                str(db_path),
                handoff["contract_version"],
                handoff["target_app"],
                handoff["delivery_mode"],
                str(profile_dir),
                source_page,
                LATEST_HANDOFF_KEY,
                PENDING_HANDOFF_KEY,
                len(handoff["focus_item_ids"]),
                verified,
                handoff_json,
            ],
        )
    finally:
        conn.close()
    return delivery_id


def main() -> int:
    args = build_parser().parse_args()
    db_path = Path(args.db_path)
    profile_dir = Path(args.profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)

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
        print("No handoff available yet. Generate more data first.")
        return 0

    handoff = payload["handoff"]
    target_app = handoff["target_app"]
    page_path = APP_PAGES[target_app]
    verified = False

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=not args.headful,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(page_path.resolve().as_uri(), wait_until="domcontentloaded")
            page.wait_for_timeout(150)
            result = page.evaluate(
                """
                ([latestKey, pendingKey, handoff]) => {
                  const payload = JSON.stringify(handoff);
                  localStorage.setItem(latestKey, payload);
                  localStorage.setItem(pendingKey, payload);
                  return {
                    latest: localStorage.getItem(latestKey),
                    pending: localStorage.getItem(pendingKey),
                    href: window.location.href
                  };
                }
                """,
                [LATEST_HANDOFF_KEY, PENDING_HANDOFF_KEY, handoff],
            )
            latest_payload = json.loads(result["latest"]) if result["latest"] else None
            pending_payload = json.loads(result["pending"]) if result["pending"] else None
            verified = latest_payload == handoff and pending_payload == handoff
        finally:
            context.close()

    delivery_id = None
    if args.save_run:
        delivery_id = save_delivery_run(
            db_path=db_path,
            handoff=handoff,
            profile_dir=profile_dir,
            source_page=page_path.resolve().as_uri(),
            verified=verified,
        )

    print("Recommendation Handoff Delivery")
    print(f"- target_app: {handoff['target_app']}")
    print(f"- contract_version: {handoff['contract_version']}")
    print(f"- delivery_mode: {handoff['delivery_mode']}")
    print(f"- session_size: {handoff['session_size']}")
    print(f"- focus_item_count: {len(handoff['focus_item_ids'])}")
    print(f"- latest_storage_key: {LATEST_HANDOFF_KEY}")
    print(f"- pending_storage_key: {PENDING_HANDOFF_KEY}")
    print(f"- verified: {verified}")
    if delivery_id:
        print(f"- delivery_id: {delivery_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
