#!/usr/bin/env python3

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

import duckdb

from deliver_recommendation_handoff import save_delivery_run
from ingest_events import DEFAULT_DB_PATH, ingest_events_batch
from reflection_logic import run_reflection, save_reflection_run
from recommendation_logic import generate_recommendation, refresh_views, save_recommendation_run


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
CONTROL_SOURCE_PAGE = "coach_local_api"
CONTROL_PROFILE_DIR = Path("coach-local")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local control plane for the KALS coach hub.")
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="DuckDB file path. Default: data/kals.duckdb",
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


def make_handler(*, db_path: Path, top_items: int, top_apps: int):
    class CoachControlHandler(BaseHTTPRequestHandler):
        server_version = "KALSCoachControl/0.1"

        def _send_json(self, payload: Dict[str, Any], status: int = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length > 0 else b"{}"
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self) -> None:
            if self.path != "/health":
                self._send_json({"ok": False, "error": "not_found"}, status=HTTPStatus.NOT_FOUND)
                return

            self._send_json(
                {
                    "ok": True,
                    "service": "coach-control",
                    "db_path": str(db_path),
                }
            )

        def do_POST(self) -> None:
            if self.path not in {"/refresh", "/reflect"}:
                self._send_json({"ok": False, "error": "not_found"}, status=HTTPStatus.NOT_FOUND)
                return

            try:
                body = self._read_json_body()

                if self.path == "/reflect":
                    refresh_requested = bool(body.get("refresh_views", False))
                    if refresh_requested:
                        refresh_views(db_path)

                    result = run_reflection(
                        db_path=db_path,
                        top_items_limit=top_items,
                        top_apps_limit=top_apps,
                        mode="openai",
                    )
                    reflection_id = None
                    if result.get("context") and result.get("status") == "completed":
                        reflection_id = save_reflection_run(
                            db_path=db_path,
                            reflection_mode="openai_auto",
                            provider=result["provider"],
                            model=result.get("model"),
                            context=result["context"],
                            prompt_text=result["prompt_text"],
                            output_text=result.get("output_text"),
                            reflection_json=result.get("reflection_json"),
                            status=result["status"],
                            error_message=result.get("error_message"),
                        )
                    self._send_json(
                        {
                            "ok": result.get("status") == "completed",
                            "reflection_result": result,
                            "reflection_id": reflection_id,
                        },
                        status=HTTPStatus.OK if result.get("status") == "completed" else HTTPStatus.BAD_GATEWAY,
                    )
                    return

                events = body.get("events") or []
                if not isinstance(events, list):
                    raise ValueError("events must be a JSON array")

                ingest_summary = ingest_events_batch(
                    db_path=db_path,
                    events=events,
                    source_page=CONTROL_SOURCE_PAGE,
                )
                refresh_views(db_path)

                conn = duckdb.connect(str(db_path), read_only=True)
                try:
                    payload = generate_recommendation(
                        conn,
                        db_path=db_path,
                        top_items_limit=top_items,
                        top_apps_limit=top_apps,
                    )
                finally:
                    conn.close()

                if not payload:
                    self._send_json(
                        {
                            "ok": True,
                            "ingest_summary": ingest_summary,
                            "recommendation": None,
                            "message": "No recommendation available yet.",
                        }
                    )
                    return

                recommendation_id = save_recommendation_run(db_path, payload)
                delivery_id = save_delivery_run(
                    db_path=db_path,
                    handoff=payload["handoff"],
                    profile_dir=CONTROL_PROFILE_DIR,
                    source_page=CONTROL_SOURCE_PAGE,
                    verified=True,
                )

                self._send_json(
                    {
                        "ok": True,
                        "ingest_summary": ingest_summary,
                        "recommendation": payload,
                        "recommendation_id": recommendation_id,
                        "delivery_id": delivery_id,
                    }
                )
            except Exception as exc:  # pragma: no cover - operational path
                self._send_json(
                    {"ok": False, "error": str(exc)},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )

        def log_message(self, format: str, *args: Any) -> None:
            return

    return CoachControlHandler


def main() -> int:
    args = build_parser().parse_args()
    db_path = Path(args.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    handler = make_handler(
        db_path=db_path,
        top_items=args.top_items,
        top_apps=args.top_apps,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"KALS coach control server listening on http://{args.host}:{args.port}")
    print("Use the coach hub Refresh Recommendation button while this server is running.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping coach control server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
