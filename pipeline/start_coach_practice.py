#!/usr/bin/env python3

import argparse
import threading
from pathlib import Path

from http.server import ThreadingHTTPServer

from coach_control_server import DEFAULT_HOST, DEFAULT_PORT, make_handler
from ingest_events import DEFAULT_DB_PATH
from open_app import DEFAULT_PROFILE_DIR, run_app_until_interrupt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the local coach control server and open the coach hub together.")
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="DuckDB file path. Default: data/kals.duckdb",
    )
    parser.add_argument(
        "--profile-dir",
        default=str(DEFAULT_PROFILE_DIR),
        help="Persistent Playwright browser profile directory.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Bind host. Default: {DEFAULT_HOST}",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Bind port. Default: {DEFAULT_PORT}",
    )
    parser.add_argument(
        "--top-items",
        type=int,
        default=5,
        help="How many review items to include in refresh responses.",
    )
    parser.add_argument(
        "--top-apps",
        type=int,
        default=3,
        help="How many ranked apps to include in refresh responses.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    db_path = Path(args.db_path)
    profile_dir = Path(args.profile_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    handler = make_handler(
        db_path=db_path,
        top_items=args.top_items,
        top_apps=args.top_apps,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print(f"Coach control server listening on http://{args.host}:{args.port}")
    print("Opening coach hub in the persistent Playwright profile.")
    try:
        return run_app_until_interrupt("coach", profile_dir)
    finally:
        print("Stopping coach control server.")
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
