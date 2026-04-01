import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import duckdb


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "kals.duckdb"
ANALYTICS_SQL_PATH = REPO_ROOT / "data" / "analytics_views.sql"
SCHEMA_SQL_PATH = REPO_ROOT / "data" / "schema.sql"
RECOMMENDER_VERSION = "stage3a_v1"
RECOMMENDATION_CONTRACT_VERSION = "kals.recommendation.v1"


def refresh_views_connection(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(ANALYTICS_SQL_PATH.read_text(encoding="utf-8"))


def refresh_views(db_path: Path) -> None:
    conn = duckdb.connect(str(db_path))
    try:
        refresh_views_connection(conn)
    finally:
        conn.close()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def recommend_session_size(
    app: str,
    urgent_count: int,
    review_count: int,
    accuracy_pct: float,
    *,
    selection_policy: str = "highest_priority",
    last_session_fail_count: int = 0,
) -> tuple:
    if selection_policy == "continue_recent_app" and last_session_fail_count > 0:
        if app == "words":
            return 10, "keep the continuation session short so the fresh miss can be revisited while it is still recent"
        return 5, "keep the continuation session short so the fresh misses can be reviewed while they are still recent"

    if app == "words":
        if urgent_count >= 2 or accuracy_pct < 85.0:
            return 10, "keep the words session short because current review pressure is meaningful"
        return 20, "use a standard words session because current review pressure is light"

    if urgent_count >= 3 or accuracy_pct < 75.0:
        return 5, "keep the session tightly focused because there are several urgent review items"

    if review_count >= 2 or accuracy_pct < 85.0:
        return 10, "use a moderate session size to cover the main review items without overloading the session"

    return 10, "use the default session size because review pressure is currently light"


def fetch_recommendation_inputs(
    conn: duckdb.DuckDBPyConnection,
    *,
    top_items_limit: int,
    top_apps_limit: int,
) -> tuple:
    app_rows = conn.execute(
        """
        SELECT
          app,
          review_candidate_count,
          urgent_review_count,
          nonperfect_items,
          accuracy_pct,
          top_candidate_item_id,
          top_candidate_shown_value,
          next_app_priority_score,
          sessions,
          last_session_rank,
          last_session_fail_count
        FROM next_session_app_summary
        ORDER BY next_app_priority_score DESC, app ASC
        """
    ).fetchall()

    recommended_app, selection_policy, selection_reason = choose_recommended_app(app_rows)

    app_ranking = [
        (
            row[0],
            row[1],
            row[2],
            row[4],
            row[7],
            row[9],
            row[10],
        )
        for row in app_rows[:top_apps_limit]
    ]

    top_items = []
    if recommended_app:
        top_items = conn.execute(
            """
            SELECT
              item_id,
              shown_value,
              fails,
              latest_result,
              first_fails,
              lifetime_accuracy_pct,
              review_priority_score
            FROM prioritized_review_candidates
            WHERE app = ?
            ORDER BY review_priority_score DESC, item_id ASC
            LIMIT ?
            """,
            [recommended_app[0], top_items_limit],
        ).fetchall()

    return recommended_app, app_ranking, top_items, selection_policy, selection_reason


def choose_recommended_app(app_rows: List[tuple]) -> Tuple[Optional[tuple], str, str]:
    if not app_rows:
        return None, "none", "no app recommendation is available yet"

    for row in app_rows:
        (
            app,
            review_count,
            urgent_count,
            nonperfect_items,
            accuracy_pct,
            top_item_id,
            top_item_value,
            score,
            sessions,
            last_session_rank,
            last_session_fail_count,
        ) = row
        if last_session_rank == 1 and sessions <= 2 and (last_session_fail_count > 0 or sessions == 1):
            if last_session_fail_count > 0:
                reason = "continue the most recent app because the last session ended with unresolved failures"
            else:
                reason = "continue the most recent app because it is newly introduced and still under-sampled"
            return row, "continue_recent_app", reason

    return app_rows[0], "highest_priority", "choose the app with the highest current cross-app priority score"


def build_payload(
    *,
    db_path: Path,
    recommended_app_row: tuple,
    top_items: List[tuple],
    app_ranking: List[tuple],
    selection_policy: str,
    selection_reason: str,
    generated_at_utc: Optional[str] = None,
) -> Dict:
    (
        app,
        review_count,
        urgent_count,
        nonperfect_items,
        accuracy_pct,
        top_item_id,
        top_item_value,
        score,
        sessions,
        last_session_rank,
        last_session_fail_count,
    ) = recommended_app_row
    session_size, session_size_reason = recommend_session_size(
        app,
        urgent_count,
        review_count,
        accuracy_pct,
        selection_policy=selection_policy,
        last_session_fail_count=last_session_fail_count,
    )
    rationale_summary = (
        f"{urgent_count} urgent review candidate(s), "
        f"{review_count} total review candidate(s), "
        f"accuracy {accuracy_pct}%"
    )
    focus_item_ids = [item_id for (item_id, *_rest) in top_items]
    focus_items = [
        {
            "item_id": item_id,
            "shown_value": shown_value,
            "review_priority_score": priority_score,
        }
        for (
            item_id,
            shown_value,
            _fails,
            _latest_result,
            _first_fails,
            _lifetime_accuracy_pct,
            priority_score,
        ) in top_items
    ]
    handoff = {
        "contract_version": RECOMMENDATION_CONTRACT_VERSION,
        "action": "start_practice_session",
        "delivery_mode": "advisory",
        "target_app": app,
        "target_mode": "recognition",
        "session_size": session_size,
        "selection_policy": selection_policy,
        "selection_reason": selection_reason,
        "focus_strategy": "review_candidates_first" if focus_item_ids else "normal_practice",
        "focus_item_ids": focus_item_ids,
        "focus_items": focus_items,
        "top_driver_item_id": top_item_id,
        "top_driver_shown_value": top_item_value,
        "ui_message": (
            f"Open {app} for a {session_size}-item session and prioritize "
            f"{len(focus_item_ids)} review item(s)."
            if focus_item_ids
            else f"Open {app} for a {session_size}-item session."
        ),
        "app_request": {
            "app": app,
            "mode": "recognition",
            "session_size": session_size,
            "recommended_item_ids": focus_item_ids,
        },
    }

    payload = {
        "generated_at_utc": generated_at_utc or now_utc_iso(),
        "source_db_path": str(db_path),
        "recommender_version": RECOMMENDER_VERSION,
        "recommendation_contract_version": RECOMMENDATION_CONTRACT_VERSION,
        "recommended_app": {
            "app": app,
            "app_priority_score": score,
            "selection_policy": selection_policy,
            "selection_reason": selection_reason,
            "recommended_session_size": session_size,
            "session_size_reason": session_size_reason,
            "rationale_summary": rationale_summary,
            "review_candidate_count": review_count,
            "urgent_review_count": urgent_count,
            "nonperfect_items_seen": nonperfect_items,
            "sessions_seen": sessions,
            "last_session_rank": last_session_rank,
            "last_session_fail_count": last_session_fail_count,
            "top_driver": {
                "item_id": top_item_id,
                "shown_value": top_item_value,
            },
        },
        "top_review_items": [
            {
                "item_id": item_id,
                "shown_value": shown_value,
                "fails": fails,
                "latest_result": latest_result,
                "first_fails": first_fails,
                "lifetime_accuracy_pct": lifetime_accuracy_pct,
                "review_priority_score": priority_score,
            }
            for (
                item_id,
                shown_value,
                fails,
                latest_result,
                first_fails,
                lifetime_accuracy_pct,
                priority_score,
            ) in top_items
        ],
        "app_ranking": [
            {
                "app": rank_app,
                "review_candidate_count": rank_review_count,
                "urgent_review_count": rank_urgent_count,
                "accuracy_pct": rank_accuracy_pct,
                "next_app_priority_score": rank_score,
                "last_session_rank": rank_last_session_rank,
                "last_session_fail_count": rank_last_session_fail_count,
            }
            for (
                rank_app,
                rank_review_count,
                rank_urgent_count,
                rank_accuracy_pct,
                rank_score,
                rank_last_session_rank,
                rank_last_session_fail_count,
            ) in app_ranking
        ],
        "handoff": handoff,
    }
    return payload


def generate_recommendation(
    conn: duckdb.DuckDBPyConnection,
    *,
    db_path: Path,
    top_items_limit: int,
    top_apps_limit: int,
    generated_at_utc: Optional[str] = None,
) -> Optional[Dict]:
    recommended_app, app_ranking, top_items, selection_policy, selection_reason = fetch_recommendation_inputs(
        conn,
        top_items_limit=top_items_limit,
        top_apps_limit=top_apps_limit,
    )
    if not recommended_app:
        return None

    return build_payload(
        db_path=db_path,
        recommended_app_row=recommended_app,
        top_items=top_items,
        app_ranking=app_ranking,
        selection_policy=selection_policy,
        selection_reason=selection_reason,
        generated_at_utc=generated_at_utc,
    )


def save_recommendation_run(db_path: Path, payload: Dict) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    recommendation_id = make_hash(payload_json)
    recommended = payload["recommended_app"]

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(SCHEMA_SQL_PATH.read_text(encoding="utf-8"))
        conn.execute(
            """
            INSERT OR REPLACE INTO recommendation_runs (
              recommendation_id,
              created_at_utc,
              source_db_path,
              recommended_app,
              app_priority_score,
              recommended_session_size,
              rationale_summary,
              top_driver_item_id,
              top_driver_shown_value,
              payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                recommendation_id,
                payload["generated_at_utc"],
                payload["source_db_path"],
                recommended["app"],
                recommended["app_priority_score"],
                recommended["recommended_session_size"],
                recommended["rationale_summary"],
                recommended["top_driver"]["item_id"],
                recommended["top_driver"]["shown_value"],
                payload_json,
            ],
        )
    finally:
        conn.close()
    return recommendation_id
