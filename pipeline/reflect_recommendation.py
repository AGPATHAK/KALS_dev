#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

from reflection_logic import (
    DEFAULT_DB_PATH,
    DEFAULT_OPENAI_MODEL,
    REFLECTION_PROMPT_VERSION,
    refresh_views,
    run_reflection,
    save_reflection_run,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage 3B reflective layer over the deterministic KALS recommender.")
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="DuckDB file path. Default: data/kals.duckdb",
    )
    parser.add_argument(
        "--refresh-views",
        action="store_true",
        help="Refresh persistent analytics views before building the reflection context.",
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
        "--mode",
        choices=["prompt", "openai"],
        default="prompt",
        help="Use prompt-only scaffolding or call OpenAI for a real reflection.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_OPENAI_MODEL,
        help=f"LLM model for --mode openai. Default: {DEFAULT_OPENAI_MODEL}",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "prompt"],
        default="text",
        help="Output format for the reflection result.",
    )
    parser.add_argument(
        "--save-run",
        action="store_true",
        help="Persist the reflection packet into llm_reflection_runs.",
    )
    return parser


def print_text(result: dict) -> None:
    context = result.get("context")
    if not context:
        print("Stage 3B Reflection")
        print(f"- status: {result['status']}")
        print(f"- error: {result.get('error_message')}")
        return

    deterministic = context["deterministic_recommendation"]["recommended_app"]
    print("Stage 3B Reflection")
    print(f"- prompt_version: {REFLECTION_PROMPT_VERSION}")
    print(f"- reflection_mode: {result['status']}")
    print(f"- deterministic_app: {deterministic['app']}")
    print(f"- deterministic_policy: {deterministic['selection_policy']}")
    print(f"- deterministic_why: {deterministic['rationale_summary']}")

    if result.get("error_message"):
        print(f"- error: {result['error_message']}")

    if result.get("reflection_json"):
        reflection = result["reflection_json"]
        print("\nLLM Reflection")
        print(f"- summary: {reflection.get('summary')}")
        print(f"- alignment: {reflection.get('alignment')}")
        bullets = reflection.get("evidence_bullets") or []
        if bullets:
            print("- evidence:")
            for bullet in bullets:
                print(f"  - {bullet}")
        if reflection.get("alternative_app"):
            print(f"- alternative_app: {reflection['alternative_app']}")
        if reflection.get("caution_note"):
            print(f"- caution_note: {reflection['caution_note']}")
        if reflection.get("confidence_note"):
            print(f"- confidence_note: {reflection['confidence_note']}")
    elif result.get("output_text"):
        print("\nLLM Output")
        print(result["output_text"])
    else:
        print("\nPrompt Ready")
        print("- no LLM call made yet")


def main() -> int:
    args = build_parser().parse_args()
    db_path = Path(args.db_path)

    if args.refresh_views:
        refresh_views(db_path)

    result = run_reflection(
        db_path=db_path,
        top_items_limit=args.top_items,
        top_apps_limit=args.top_apps,
        mode=args.mode,
        model=args.model,
    )

    reflection_id = None
    if args.save_run and result.get("context"):
        reflection_id = save_reflection_run(
            db_path=db_path,
            reflection_mode=args.mode,
            provider=result["provider"],
            model=result.get("model"),
            context=result["context"],
            prompt_text=result["prompt_text"],
            output_text=result.get("output_text"),
            reflection_json=result.get("reflection_json"),
            status=result["status"],
            error_message=result.get("error_message"),
        )

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.format == "prompt":
        print(result.get("prompt_text", ""))
    else:
        print_text(result)
        if reflection_id:
            print(f"\nSaved Reflection Run\n- reflection_id: {reflection_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
