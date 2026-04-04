import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import duckdb

from recommendation_logic import (
    DEFAULT_DB_PATH,
    RECOMMENDATION_CONTRACT_VERSION,
    generate_recommendation,
    make_hash,
    now_utc_iso,
    refresh_views,
)


REFLECTION_PROMPT_VERSION = "stage3b_v3"
DEFAULT_OPENAI_MODEL = "gpt-5-mini"


def rows_to_dicts(columns: List[str], rows: List[tuple]) -> List[Dict]:
    return [dict(zip(columns, row)) for row in rows]


def build_reflection_context(
    conn: duckdb.DuckDBPyConnection,
    *,
    db_path: Path,
    top_items_limit: int,
    top_apps_limit: int,
) -> Optional[Dict]:
    recommendation = generate_recommendation(
        conn,
        db_path=db_path,
        top_items_limit=top_items_limit,
        top_apps_limit=top_apps_limit,
    )
    if not recommendation:
        return None

    weak_items = rows_to_dicts(
        ["app", "item_id", "shown_value", "attempts", "fails", "accuracy_pct", "avg_response_ms"],
        conn.execute(
            """
            SELECT app, item_id, shown_value, attempts, fails, accuracy_pct, avg_response_ms
            FROM weak_items
            ORDER BY accuracy_pct ASC, attempts DESC, item_id ASC
            LIMIT 8
            """
        ).fetchall(),
    )

    confusion_pairs = rows_to_dicts(
        ["app", "item_id", "shown_value", "correct_answer", "chosen_wrong_answer", "misses"],
        conn.execute(
            """
            SELECT app, item_id, shown_value, correct_answer, chosen_wrong_answer, misses
            FROM confusion_pairs
            ORDER BY misses DESC, item_id ASC, chosen_wrong_answer ASC
            LIMIT 8
            """
        ).fetchall(),
    )

    guided_comparison = rows_to_dicts(
        [
            "app",
            "normal_sessions",
            "normal_accuracy_pct",
            "guided_sessions",
            "guided_accuracy_pct",
            "accuracy_delta_pct",
            "avg_normal_response_ms",
            "avg_guided_response_ms",
            "response_time_delta_ms",
        ],
        conn.execute(
            """
            SELECT
              app,
              normal_sessions,
              normal_accuracy_pct,
              guided_sessions,
              guided_accuracy_pct,
              accuracy_delta_pct,
              avg_normal_response_ms,
              avg_guided_response_ms,
              response_time_delta_ms
            FROM guided_vs_normal_app_comparison
            ORDER BY app
            LIMIT 8
            """
        ).fetchall(),
    )

    follow_up = rows_to_dicts(
        [
            "app",
            "guided_outcome",
            "follow_up_action",
            "session_count",
            "avg_accuracy_pct",
            "avg_focus_surface_rate_pct",
            "avg_focus_clear_rate_pct",
        ],
        conn.execute(
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
            ORDER BY session_count DESC, app ASC
            LIMIT 8
            """
        ).fetchall(),
    )

    recent_app_usage = rows_to_dicts(
        [
            "app",
            "sessions_seen",
            "last_session_rank",
            "last_session_attempt_count",
            "last_session_fail_count",
            "sessions_in_last_3",
        ],
        conn.execute(
            """
            SELECT
              app,
              sessions_seen,
              last_session_rank,
              last_session_attempt_count,
              last_session_fail_count,
              sessions_in_last_3
            FROM recent_app_usage
            ORDER BY last_session_rank ASC, app ASC
            LIMIT 8
            """
        ).fetchall(),
    )

    latest_event_row = conn.execute(
        """
        SELECT max(timestamp_utc) AS latest_event_utc
        FROM raw_attempt_events
        """
    ).fetchone()
    latest_event_utc = latest_event_row[0].isoformat() if latest_event_row and latest_event_row[0] else None

    return {
        "generated_at_utc": now_utc_iso(),
        "latest_event_utc": latest_event_utc,
        "source_db_path": str(db_path),
        "recommendation_contract_version": RECOMMENDATION_CONTRACT_VERSION,
        "deterministic_recommendation": recommendation,
        "weak_items": weak_items,
        "confusion_pairs": confusion_pairs,
        "guided_vs_normal_app_comparison": guided_comparison,
        "guided_follow_up_summary": follow_up,
        "recent_app_usage": recent_app_usage,
    }


def build_reflection_prompts(context: Dict) -> Tuple[str, str]:
    system_prompt = (
        "You are a warm, concise teacher-coach for KALS. "
        "You are not allowed to replace the deterministic recommendation. "
        "Your job is to turn the current learner state into short, supportive coaching language. "
        "Use only the curated summary you are given. "
        "Do not mention scores, ranking formulas, cross-app priority, deterministic policy names, "
        "or system internals unless absolutely necessary. "
        "Return compact JSON with exactly these keys: "
        "focus_today, watch_out_for, encouragement, optional_variety, stable_area, confidence_note."
    )

    user_prompt = (
        "Turn this deterministic KALS recommendation context into short learner-facing coaching.\n\n"
        "Tasks:\n"
        "1. Write one short `focus_today` line saying what to practice now.\n"
        "2. Write one short `watch_out_for` line naming a likely confusion or weak area.\n"
        "3. Write one short `encouragement` line in a teacher-like tone.\n"
        "4. Optionally write one short `optional_variety` line offering a nearby alternative if the learner wants variety.\n"
        "5. Optionally write one short `stable_area` line naming an app or area that looks steady enough to skip for now.\n"
        "6. Write one short `confidence_note` line about how firm or tentative this coaching is.\n\n"
        "Guardrails:\n"
        "- Do not invent learner history.\n"
        "- Do not output a new command or handoff.\n"
        "- The deterministic recommendation remains the official decision.\n\n"
        "Style:\n"
        "- Keep each field to 1 sentence.\n"
        "- Use plain learner-friendly language.\n"
        "- Do not justify the recommendation like an analyst.\n"
        "- Do not say things like 'the deterministic recommendation is coherent' or refer to scores unless essential.\n\n"
        f"Context JSON:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    return system_prompt, user_prompt


def build_prompt_text(system_prompt: str, user_prompt: str) -> str:
    return f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_prompt}"


def extract_response_text(payload: Dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]

    chunks: List[str] = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "output_text" and isinstance(node.get("text"), str):
                chunks.append(node["text"])
            elif node.get("type") == "text" and isinstance(node.get("text"), str):
                chunks.append(node["text"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def call_openai_reflection(
    *,
    api_key: str,
    org_id: Optional[str],
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> Dict:
    request_body = {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Connection": "close",
    }
    if org_id:
        headers["OpenAI-Organization"] = org_id

    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(request_body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_reflection_json(output_text: str) -> Optional[Dict]:
    try:
        return json.loads(output_text)
    except Exception:
        return None


def save_reflection_run(
    *,
    db_path: Path,
    reflection_mode: str,
    provider: str,
    model: Optional[str],
    context: Dict,
    prompt_text: str,
    output_text: Optional[str],
    reflection_json: Optional[Dict],
    status: str,
    error_message: Optional[str] = None,
) -> str:
    reflection_payload = {
        "created_at_utc": now_utc_iso(),
        "source_db_path": str(db_path),
        "reflection_mode": reflection_mode,
        "provider": provider,
        "model": model,
        "context": context,
        "prompt_text": prompt_text,
        "output_text": output_text,
        "reflection_json": reflection_json,
        "status": status,
        "error_message": error_message,
    }
    reflection_id = make_hash(json.dumps(reflection_payload, ensure_ascii=False, sort_keys=True))

    conn = duckdb.connect(str(db_path))
    try:
        schema_path = Path(__file__).resolve().parent.parent / "data" / "schema.sql"
        conn.execute(schema_path.read_text(encoding="utf-8"))
        conn.execute(
            """
            INSERT OR REPLACE INTO llm_reflection_runs (
              reflection_id,
              created_at_utc,
              source_db_path,
              reflection_mode,
              provider,
              model,
              prompt_version,
              recommended_app,
              recommendation_contract_version,
              context_json,
              prompt_text,
              output_text,
              reflection_json,
              status,
              error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                reflection_id,
                reflection_payload["created_at_utc"],
                str(db_path),
                reflection_mode,
                provider,
                model,
                REFLECTION_PROMPT_VERSION,
                context["deterministic_recommendation"]["recommended_app"]["app"],
                context["recommendation_contract_version"],
                json.dumps(context, ensure_ascii=False, sort_keys=True),
                prompt_text,
                output_text,
                None if reflection_json is None else json.dumps(reflection_json, ensure_ascii=False, sort_keys=True),
                status,
                error_message,
            ],
        )
    finally:
        conn.close()
    return reflection_id


def run_reflection(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    top_items_limit: int = 5,
    top_apps_limit: int = 3,
    mode: str = "prompt",
    model: str = DEFAULT_OPENAI_MODEL,
) -> Dict:
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        context = build_reflection_context(
            conn,
            db_path=db_path,
            top_items_limit=top_items_limit,
            top_apps_limit=top_apps_limit,
        )
    finally:
        conn.close()

    if not context:
        return {
            "status": "empty",
            "context": None,
            "prompt_text": "",
            "output_text": None,
            "reflection_json": None,
            "provider": "none",
            "model": None,
            "error_message": "No recommendation context available yet.",
        }

    system_prompt, user_prompt = build_reflection_prompts(context)
    prompt_text = build_prompt_text(system_prompt, user_prompt)

    if mode == "prompt":
        return {
            "status": "prompt_only",
            "context": context,
            "prompt_text": prompt_text,
            "output_text": None,
            "reflection_json": None,
            "provider": "none",
            "model": None,
            "error_message": None,
        }

    api_key = os.environ.get("OPENAI_API_KEY")
    org_id = os.environ.get("OPENAI_ORG_ID")
    if not api_key:
        return {
            "status": "error",
            "context": context,
            "prompt_text": prompt_text,
            "output_text": None,
            "reflection_json": None,
            "provider": "openai",
            "model": model,
            "error_message": "OPENAI_API_KEY is not set.",
        }

    try:
        response_payload = call_openai_reflection(
            api_key=api_key,
            org_id=org_id,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        output_text = extract_response_text(response_payload)
        reflection_json = parse_reflection_json(output_text)
        return {
            "status": "completed",
            "context": context,
            "prompt_text": prompt_text,
            "output_text": output_text,
            "reflection_json": reflection_json,
            "provider": "openai",
            "model": model,
            "error_message": None,
        }
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {
            "status": "error",
            "context": context,
            "prompt_text": prompt_text,
            "output_text": None,
            "reflection_json": None,
            "provider": "openai",
            "model": model,
            "error_message": f"HTTP {exc.code}: {detail}",
        }
    except Exception as exc:
        return {
            "status": "error",
            "context": context,
            "prompt_text": prompt_text,
            "output_text": None,
            "reflection_json": None,
            "provider": "openai",
            "model": model,
            "error_message": str(exc),
        }
