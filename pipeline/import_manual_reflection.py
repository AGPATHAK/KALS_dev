#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Tuple

from reflection_logic import (
    DEFAULT_DB_PATH,
    DEFAULT_OPENAI_MODEL,
    refresh_views,
    run_reflection,
    save_reflection_run,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import a manually obtained Stage 3B reflection into DuckDB."
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="DuckDB file path. Default: data/kals.duckdb",
    )
    parser.add_argument(
        "--refresh-views",
        action="store_true",
        help="Refresh persistent analytics views before rebuilding the reflection context.",
    )
    parser.add_argument(
        "--top-items",
        type=int,
        default=5,
        help="How many top review items to include in the deterministic context.",
    )
    parser.add_argument(
        "--top-apps",
        type=int,
        default=3,
        help="How many app ranking rows to include in the deterministic context.",
    )
    parser.add_argument(
        "--input-file",
        help="Optional path to a text or JSON file containing the manual reflection output.",
    )
    parser.add_argument(
        "--provider",
        default="manual_chatgpt",
        help="Provider label to store with the reflection. Default: manual_chatgpt",
    )
    parser.add_argument(
        "--model",
        default="chatgpt_manual",
        help="Model label to store with the reflection. Default: chatgpt_manual",
    )
    parser.add_argument(
        "--format",
        choices=["auto", "json", "text"],
        default="auto",
        help="Interpret the imported content as JSON, plain text, or auto-detect. Default: auto",
    )
    return parser


def read_input_text(input_file: Optional[str]) -> str:
    if input_file:
        return Path(input_file).read_text(encoding="utf-8").strip()
    return sys.stdin.read().strip()


def normalize_manual_text(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()

    replacements = {
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def parse_manual_content(raw_text: str, mode: str) -> Tuple[str, Optional[dict]]:
    normalized_text = normalize_manual_text(raw_text)

    if mode == "text":
        return normalized_text, None

    if mode == "json":
        return normalized_text, json.loads(normalized_text)

    try:
        return normalized_text, json.loads(normalized_text)
    except Exception:
        return normalized_text, None


def print_summary(reflection_id: str, result: dict, reflection_json: Optional[dict]) -> None:
    deterministic = result["context"]["deterministic_recommendation"]["recommended_app"]
    print("Manual Reflection Imported")
    print(f"- reflection_id: {reflection_id}")
    print(f"- recommended_app: {deterministic['app']}")
    print(f"- selection_policy: {deterministic['selection_policy']}")
    print(f"- provider: {result['provider']}")
    print(f"- model: {result['model']}")
    if reflection_json:
        print(f"- summary: {reflection_json.get('summary')}")
        print(f"- alignment: {reflection_json.get('alignment')}")
        if reflection_json.get("alternative_app"):
            print(f"- alternative_app: {reflection_json['alternative_app']}")


def main() -> int:
    args = build_parser().parse_args()
    db_path = Path(args.db_path)

    if args.refresh_views:
        refresh_views(db_path)

    result = run_reflection(
        db_path=db_path,
        top_items_limit=args.top_items,
        top_apps_limit=args.top_apps,
        mode="prompt",
        model=DEFAULT_OPENAI_MODEL,
    )
    if not result.get("context"):
        print("No recommendation context available yet.", file=sys.stderr)
        return 1

    raw_text = read_input_text(args.input_file)
    if not raw_text:
        print("No manual reflection content was provided.", file=sys.stderr)
        return 1

    output_text, reflection_json = parse_manual_content(raw_text, args.format)
    reflection_id = save_reflection_run(
        db_path=db_path,
        reflection_mode="manual_import",
        provider=args.provider,
        model=args.model,
        context=result["context"],
        prompt_text=result["prompt_text"],
        output_text=output_text,
        reflection_json=reflection_json,
        status="completed",
        error_message=None,
    )
    print_summary(reflection_id, {"context": result["context"], "provider": args.provider, "model": args.model}, reflection_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
