import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import duckdb


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "kals.duckdb"
ANALYTICS_SQL_PATH = REPO_ROOT / "data" / "analytics_views.sql"
SCHEMA_SQL_PATH = REPO_ROOT / "data" / "schema.sql"
RECOMMENDER_VERSION = "stage3a_v1"


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


def recommend_session_size(app: str, urgent_count: int, review_count: int, accuracy_pct: float) -> tuple:
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
    recommended_app = conn.execute(
        """
        SELECT
          app,
          review_candidate_count,
          urgent_review_count,
          nonperfect_items,
          accuracy_pct,
          top_candidate_item_id,
          top_candidate_shown_value,
          next_app_priority_score
        FROM next_session_app_summary
        ORDER BY next_app_priority_score DESC, app ASC
        LIMIT 1
        """
    ).fetchone()

    app_ranking = conn.execute(
        """
        SELECT
          app,
          review_candidate_count,
          urgent_review_count,
          accuracy_pct,
          next_app_priority_score
        FROM next_session_app_summary
        ORDER BY next_app_priority_score DESC, app ASC
        LIMIT ?
        """,
        [top_apps_limit],
    ).fetchall()

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

    return recommended_app, app_ranking, top_items


def build_payload(
    *,
    db_path: Path,
    recommended_app_row: tuple,
    top_items: List[tuple],
    app_ranking: List[tuple],
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
    ) = recommended_app_row
    session_size, session_size_reason = recommend_session_size(app, urgent_count, review_count, accuracy_pct)
    rationale_summary = (
        f"{urgent_count} urgent review candidate(s), "
        f"{review_count} total review candidate(s), "
        f"accuracy {accuracy_pct}%"
    )

    payload = {
        "generated_at_utc": generated_at_utc or now_utc_iso(),
        "source_db_path": str(db_path),
        "recommender_version": RECOMMENDER_VERSION,
        "recommended_app": {
            "app": app,
            "app_priority_score": score,
            "recommended_session_size": session_size,
            "session_size_reason": session_size_reason,
            "rationale_summary": rationale_summary,
            "review_candidate_count": review_count,
            "urgent_review_count": urgent_count,
            "nonperfect_items_seen": nonperfect_items,
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
            }
            for (
                rank_app,
                rank_review_count,
                rank_urgent_count,
                rank_accuracy_pct,
                rank_score,
            ) in app_ranking
        ],
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
    recommended_app, app_ranking, top_items = fetch_recommendation_inputs(
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
