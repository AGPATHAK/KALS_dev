#!/usr/bin/env python3

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import duckdb
from playwright.sync_api import sync_playwright


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "kals.duckdb"
DEFAULT_PROFILE_DIR = REPO_ROOT / ".playwright-profile"
SCHEMA_PATH = REPO_ROOT / "data" / "schema.sql"
APP_PAGES = {
    "alphabet": REPO_ROOT / "alphabet" / "index.html",
    "matras": REPO_ROOT / "matras" / "index.html",
    "conjuncts": REPO_ROOT / "conjuncts" / "index.html",
    "words": REPO_ROOT / "words" / "index.html",
}
REQUIRED_FIELDS = [
    "session_id",
    "app",
    "app_version",
    "item_id",
    "item_type",
    "shown_value",
    "correct_answer",
    "user_answer",
    "choices_presented",
    "result",
    "response_time_ms",
    "timestamp",
    "mode",
    "distractor_mode",
    "difficulty",
    "intervention_id",
]
VALID_APPS = set(APP_PAGES.keys())
VALID_RESULTS = {"pass", "fail"}
VALID_MODES = {"recognition"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest KALS kjt_events into DuckDB.")
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="DuckDB file path. Default: data/kals.duckdb",
    )
    parser.add_argument(
        "--app",
        action="append",
        choices=sorted(APP_PAGES.keys()),
        help="App page(s) to use as Playwright sources. Defaults to all apps.",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Run Chromium visibly instead of headless.",
    )
    parser.add_argument(
        "--profile-dir",
        default=str(DEFAULT_PROFILE_DIR),
        help="Persistent Playwright browser profile directory.",
    )
    return parser


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def make_event_uid(event: Dict) -> str:
    payload = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_issue_uid(event_uid: Optional[str], source_page: str, issue_code: str, issue_message: str) -> str:
    payload = f"{event_uid or 'no-event'}|{source_page}|{issue_code}|{issue_message}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_schema_sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def validate_event(event: Dict) -> List[Tuple[str, str]]:
    issues: List[Tuple[str, str]] = []

    for field in REQUIRED_FIELDS:
        if field not in event:
            issues.append(("missing_field", f"Missing required field: {field}"))

    if issues:
        return issues

    if event["app"] not in VALID_APPS:
        issues.append(("invalid_app", f"Unexpected app value: {event['app']}"))

    if event["result"] not in VALID_RESULTS:
        issues.append(("invalid_result", f"Unexpected result value: {event['result']}"))

    if event["mode"] not in VALID_MODES:
        issues.append(("invalid_mode", f"Unexpected mode value: {event['mode']}"))

    if not isinstance(event["response_time_ms"], int):
        issues.append(("invalid_response_time", "response_time_ms must be an integer"))
    elif event["response_time_ms"] < 0:
        issues.append(("invalid_response_time", "response_time_ms must be non-negative"))

    choices = event["choices_presented"]
    if choices is not None and not isinstance(choices, list):
        issues.append(("invalid_choices", "choices_presented must be a list or null"))

    if event["app"] == "words":
        if event["user_answer"] is not None:
            issues.append(("words_user_answer", "words app must use user_answer = null"))
        if event["choices_presented"] is not None:
            issues.append(("words_choices", "words app must use choices_presented = null"))
        if event["distractor_mode"] is not None:
            issues.append(("words_distractor_mode", "words app must use distractor_mode = null"))

    item_id = str(event["item_id"])
    expected_prefix = {
        "alphabet": "alpha.",
        "matras": "matra.",
        "conjuncts": "conjunct.",
        "words": "word.",
    }[event["app"]]
    if not item_id.startswith(expected_prefix):
        issues.append(("item_id_prefix", f"{event['app']} item_id must start with {expected_prefix}"))

    try:
        normalize_timestamp(str(event["timestamp"]))
    except ValueError as exc:
        issues.append(("invalid_timestamp", f"timestamp is not ISO 8601: {exc}"))

    return issues


def fetch_events_from_page(page_path: Path, headless: bool, profile_dir: Path) -> List[Dict]:
    url = page_path.resolve().as_uri()
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(150)
            data = page.evaluate("() => JSON.parse(localStorage.getItem('kjt_events') || '[]')")
            if not isinstance(data, list):
                raise RuntimeError("kjt_events did not resolve to a JSON array")
            return data
        finally:
            context.close()


def existing_event_uids(conn: duckdb.DuckDBPyConnection) -> set:
    rows = conn.execute("SELECT event_uid FROM raw_attempt_events").fetchall()
    return {row[0] for row in rows}


def insert_validation_issue(
    conn: duckdb.DuckDBPyConnection,
    *,
    event_uid: Optional[str],
    source_page: str,
    issue_code: str,
    issue_message: str,
    raw_event_json: str,
) -> None:
    issue_uid = make_issue_uid(event_uid, source_page, issue_code, issue_message)
    conn.execute(
        """
        INSERT OR REPLACE INTO validation_issues (
          issue_uid, event_uid, source_page, issue_code, issue_message, raw_event_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [issue_uid, event_uid, source_page, issue_code, issue_message, raw_event_json],
    )


def insert_raw_event(
    conn: duckdb.DuckDBPyConnection,
    *,
    event_uid: str,
    event: Dict,
    source_page: str,
    raw_event_json: str,
) -> None:
    timestamp_utc = normalize_timestamp(str(event["timestamp"]))
    choices_json = None if event["choices_presented"] is None else json.dumps(event["choices_presented"], ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO raw_attempt_events (
          event_uid,
          session_id,
          app,
          app_version,
          item_id,
          item_type,
          shown_value,
          correct_answer,
          user_answer,
          choices_presented_json,
          result,
          response_time_ms,
          timestamp_utc,
          mode,
          distractor_mode,
          difficulty,
          intervention_id,
          source_page,
          ingested_at_utc,
          raw_event_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            event_uid,
            event["session_id"],
            event["app"],
            event["app_version"],
            event["item_id"],
            event["item_type"],
            event["shown_value"],
            event["correct_answer"],
            event["user_answer"],
            choices_json,
            event["result"],
            event["response_time_ms"],
            timestamp_utc,
            event["mode"],
            event["distractor_mode"],
            event["difficulty"],
            event["intervention_id"],
            source_page,
            datetime.now(timezone.utc),
            raw_event_json,
        ],
    )


def selected_pages(app_names: Optional[Iterable[str]]) -> List[Tuple[str, Path]]:
    names = list(app_names) if app_names else list(APP_PAGES.keys())
    return [(name, APP_PAGES[name]) for name in names]


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    db_path = Path(args.db_path)
    profile_dir = Path(args.profile_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path))
    conn.execute(load_schema_sql())

    seen = existing_event_uids(conn)
    inserted = 0
    duplicates = 0
    issues = 0

    pages = selected_pages(args.app)
    print(f"[{now_iso()}] Stage 2 ingest starting")
    print(f"Database: {db_path}")
    print(f"Sources: {', '.join(name for name, _ in pages)}")

    for app_name, page_path in pages:
        print(f"\nReading localStorage via Playwright from {app_name}: {page_path}")
        events = fetch_events_from_page(page_path, headless=not args.headful, profile_dir=profile_dir)
        print(f"Fetched {len(events)} raw event(s)")

        for event in events:
            raw_event_json = json.dumps(event, ensure_ascii=False, sort_keys=True)
            event_uid = make_event_uid(event)

            if event_uid in seen:
                duplicates += 1
                continue

            event_issues = validate_event(event)
            if event_issues:
                issues += 1
                for issue_code, issue_message in event_issues:
                    insert_validation_issue(
                        conn,
                        event_uid=event_uid,
                        source_page=app_name,
                        issue_code=issue_code,
                        issue_message=issue_message,
                        raw_event_json=raw_event_json,
                    )
                continue

            insert_raw_event(
                conn,
                event_uid=event_uid,
                event=event,
                source_page=app_name,
                raw_event_json=raw_event_json,
            )
            seen.add(event_uid)
            inserted += 1

    total_raw = conn.execute("SELECT COUNT(*) FROM raw_attempt_events").fetchone()[0]
    total_issues = conn.execute("SELECT COUNT(*) FROM validation_issues").fetchone()[0]

    print("\nIngest summary")
    print(f"- inserted: {inserted}")
    print(f"- duplicates skipped: {duplicates}")
    print(f"- new invalid events: {issues}")
    print(f"- total raw events stored: {total_raw}")
    print(f"- total validation issues stored: {total_issues}")
    print(f"- database path: {db_path}")

    conn.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        raise SystemExit(130)
