CREATE OR REPLACE VIEW event_counts_by_app AS
SELECT
  app,
  COUNT(*) AS attempts,
  COUNT(DISTINCT session_id) AS sessions,
  SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) AS passes,
  SUM(CASE WHEN result = 'fail' THEN 1 ELSE 0 END) AS fails,
  ROUND(100.0 * SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) / COUNT(*), 1) AS accuracy_pct,
  ROUND(AVG(response_time_ms), 1) AS avg_response_ms,
  MAX(timestamp_utc) AS last_attempt_utc
FROM raw_attempt_events
GROUP BY app;

CREATE OR REPLACE VIEW weak_items AS
SELECT
  app,
  item_id,
  item_type,
  MAX(shown_value) AS shown_value,
  COUNT(*) AS attempts,
  SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) AS passes,
  SUM(CASE WHEN result = 'fail' THEN 1 ELSE 0 END) AS fails,
  ROUND(100.0 * SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) / COUNT(*), 1) AS accuracy_pct,
  ROUND(AVG(response_time_ms), 1) AS avg_response_ms,
  MAX(timestamp_utc) AS last_seen_utc
FROM raw_attempt_events
GROUP BY app, item_id, item_type;

CREATE OR REPLACE VIEW confusion_pairs AS
SELECT
  app,
  item_id,
  MAX(shown_value) AS shown_value,
  correct_answer,
  user_answer AS chosen_wrong_answer,
  COUNT(*) AS misses,
  ROUND(AVG(response_time_ms), 1) AS avg_response_ms,
  MAX(timestamp_utc) AS last_seen_utc
FROM raw_attempt_events
WHERE result = 'fail'
  AND user_answer IS NOT NULL
GROUP BY app, item_id, correct_answer, user_answer;

CREATE OR REPLACE VIEW session_first_attempts AS
WITH ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY session_id, app, item_id
      ORDER BY timestamp_utc ASC
    ) AS item_attempt_rank_in_session
  FROM raw_attempt_events
)
SELECT
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
  raw_event_json,
  item_attempt_rank_in_session
FROM ranked
WHERE item_attempt_rank_in_session = 1;

CREATE OR REPLACE VIEW first_pass_accuracy AS
SELECT
  app,
  item_id,
  item_type,
  MAX(shown_value) AS shown_value,
  COUNT(*) AS first_attempt_sessions,
  SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) AS first_passes,
  SUM(CASE WHEN result = 'fail' THEN 1 ELSE 0 END) AS first_fails,
  ROUND(100.0 * SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) / COUNT(*), 1) AS first_pass_accuracy_pct,
  ROUND(AVG(response_time_ms), 1) AS avg_first_attempt_ms,
  MAX(timestamp_utc) AS last_first_attempt_utc
FROM session_first_attempts
GROUP BY app, item_id, item_type;

CREATE OR REPLACE VIEW item_recency AS
SELECT
  app,
  item_id,
  item_type,
  MAX(shown_value) AS shown_value,
  COUNT(*) AS attempts,
  COUNT(DISTINCT session_id) AS sessions_seen,
  MIN(timestamp_utc) AS first_seen_utc,
  MAX(timestamp_utc) AS last_seen_utc,
  DATE_DIFF('minute', MAX(timestamp_utc), CURRENT_TIMESTAMP) AS minutes_since_last_seen,
  ARG_MAX(result, timestamp_utc) AS latest_result,
  ARG_MAX(response_time_ms, timestamp_utc) AS latest_response_ms,
  ROUND(100.0 * SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) / COUNT(*), 1) AS lifetime_accuracy_pct
FROM raw_attempt_events
GROUP BY app, item_id, item_type;

CREATE OR REPLACE VIEW session_rollup AS
SELECT
  session_id,
  app,
  MIN(timestamp_utc) AS session_start_utc,
  MAX(timestamp_utc) AS session_end_utc,
  COUNT(*) AS attempt_count,
  SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) AS pass_count,
  SUM(CASE WHEN result = 'fail' THEN 1 ELSE 0 END) AS fail_count
FROM raw_attempt_events
GROUP BY session_id, app;

CREATE OR REPLACE VIEW recent_app_usage AS
WITH ranked_sessions AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      ORDER BY session_start_utc DESC, app ASC, session_id ASC
    ) AS global_recent_session_rank
  FROM session_rollup
)
SELECT
  app,
  COUNT(*) AS sessions_seen,
  MAX(session_start_utc) AS last_session_start_utc,
  MAX(session_end_utc) AS last_session_end_utc,
  MIN(global_recent_session_rank) AS last_session_rank,
  ARG_MAX(attempt_count, session_start_utc) AS last_session_attempt_count,
  ARG_MAX(fail_count, session_start_utc) AS last_session_fail_count,
  SUM(CASE WHEN global_recent_session_rank <= 3 THEN 1 ELSE 0 END) AS sessions_in_last_3
FROM ranked_sessions
GROUP BY app;

CREATE OR REPLACE VIEW prioritized_review_candidates AS
SELECT
  r.app,
  r.item_id,
  r.item_type,
  r.shown_value,
  r.attempts,
  w.fails,
  r.latest_result,
  r.minutes_since_last_seen,
  r.lifetime_accuracy_pct,
  COALESCE(f.first_attempt_sessions, 0) AS first_attempt_sessions,
  COALESCE(f.first_fails, 0) AS first_fails,
  COALESCE(f.first_pass_accuracy_pct, 100.0) AS first_pass_accuracy_pct,
  ROUND(
      (COALESCE(w.fails, 0) * 4.0)
    + (CASE WHEN r.latest_result = 'fail' THEN 3.0 ELSE 0.0 END)
    + (COALESCE(f.first_fails, 0) * 2.0)
    + ((100.0 - r.lifetime_accuracy_pct) / 25.0)
    + ((100.0 - COALESCE(f.first_pass_accuracy_pct, 100.0)) / 40.0)
    + (CASE
        WHEN r.minutes_since_last_seen >= 1440 THEN 2.0
        WHEN r.minutes_since_last_seen >= 60 THEN 1.0
        WHEN r.minutes_since_last_seen >= 10 THEN 0.5
        ELSE 0.0
      END)
    + (CASE WHEN r.attempts >= 2 THEN 0.5 ELSE 0.0 END)
  , 2) AS review_priority_score
FROM item_recency r
LEFT JOIN weak_items w
  ON r.app = w.app
 AND r.item_id = w.item_id
LEFT JOIN first_pass_accuracy f
  ON r.app = f.app
 AND r.item_id = f.item_id
WHERE COALESCE(w.fails, 0) > 0
   OR COALESCE(f.first_fails, 0) > 0
   OR r.latest_result = 'fail';

CREATE OR REPLACE VIEW next_session_app_summary AS
WITH review_rollup AS (
  SELECT
    app,
    COUNT(*) AS review_candidate_count,
    SUM(CASE WHEN review_priority_score >= 12 THEN 1 ELSE 0 END) AS urgent_review_count,
    ROUND(AVG(review_priority_score), 2) AS avg_review_priority_score,
    MAX(review_priority_score) AS top_review_priority_score,
    ARG_MAX(item_id, review_priority_score) AS top_candidate_item_id,
    ARG_MAX(shown_value, review_priority_score) AS top_candidate_shown_value
  FROM prioritized_review_candidates
  GROUP BY app
),
item_rollup AS (
  SELECT
    app,
    COUNT(*) AS items_seen,
    SUM(CASE WHEN lifetime_accuracy_pct < 100 THEN 1 ELSE 0 END) AS nonperfect_items
  FROM item_recency
  GROUP BY app
),
recent_usage AS (
  SELECT
    app,
    sessions_seen,
    last_session_start_utc,
    last_session_end_utc,
    last_session_rank,
    last_session_attempt_count,
    last_session_fail_count,
    sessions_in_last_3
  FROM recent_app_usage
)
SELECT
  e.app,
  e.attempts,
  e.sessions,
  e.passes,
  e.fails,
  e.accuracy_pct,
  e.avg_response_ms,
  e.last_attempt_utc,
  COALESCE(i.items_seen, 0) AS items_seen,
  COALESCE(i.nonperfect_items, 0) AS nonperfect_items,
  COALESCE(r.review_candidate_count, 0) AS review_candidate_count,
  COALESCE(r.urgent_review_count, 0) AS urgent_review_count,
  COALESCE(r.avg_review_priority_score, 0.0) AS avg_review_priority_score,
  COALESCE(r.top_review_priority_score, 0.0) AS top_review_priority_score,
  r.top_candidate_item_id,
  r.top_candidate_shown_value,
  COALESCE(u.last_session_rank, 999) AS last_session_rank,
  COALESCE(u.last_session_attempt_count, 0) AS last_session_attempt_count,
  COALESCE(u.last_session_fail_count, 0) AS last_session_fail_count,
  COALESCE(u.sessions_in_last_3, 0) AS sessions_in_last_3,
  ROUND(
    (CASE
      WHEN COALESCE(u.last_session_rank, 999) = 1
       AND e.sessions = 1
       AND COALESCE(u.last_session_fail_count, 0) > 0 THEN 7.0
      WHEN COALESCE(u.last_session_rank, 999) = 1
       AND e.sessions = 1 THEN 4.0
      WHEN COALESCE(u.last_session_rank, 999) = 1
       AND COALESCE(u.last_session_fail_count, 0) > 0 THEN 4.0
      WHEN COALESCE(u.last_session_rank, 999) = 1 THEN -2.0
      ELSE 0.0
    END)
    - (CASE WHEN COALESCE(u.sessions_in_last_3, 0) >= 3 THEN 3.0 ELSE 0.0 END)
  , 2) AS recent_session_adjustment,
  ROUND(
      (COALESCE(r.urgent_review_count, 0) * 4.0)
    + (COALESCE(r.review_candidate_count, 0) * 1.5)
    + (COALESCE(i.nonperfect_items, 0) * 0.75)
    + ((100.0 - e.accuracy_pct) / 10.0)
    + (CASE WHEN e.fails > 0 THEN 1.0 ELSE 0.0 END)
    + (CASE
        WHEN COALESCE(u.last_session_rank, 999) = 1
         AND e.sessions = 1
         AND COALESCE(u.last_session_fail_count, 0) > 0 THEN 7.0
        WHEN COALESCE(u.last_session_rank, 999) = 1
         AND e.sessions = 1 THEN 4.0
        WHEN COALESCE(u.last_session_rank, 999) = 1
         AND COALESCE(u.last_session_fail_count, 0) > 0 THEN 4.0
        WHEN COALESCE(u.last_session_rank, 999) = 1 THEN -2.0
        ELSE 0.0
      END)
    - (CASE WHEN COALESCE(u.sessions_in_last_3, 0) >= 3 THEN 3.0 ELSE 0.0 END)
  , 2) AS next_app_priority_score
FROM event_counts_by_app e
LEFT JOIN review_rollup r
  ON e.app = r.app
LEFT JOIN item_rollup i
  ON e.app = i.app
LEFT JOIN recent_usage u
  ON e.app = u.app;

CREATE OR REPLACE VIEW delivered_handoffs AS
SELECT
  delivery_id,
  created_at_utc,
  recommended_app,
  delivery_mode,
  verified,
  focus_item_count,
  json_extract_string(handoff_json, '$.handoff_id') AS handoff_id,
  json_extract_string(handoff_json, '$.contract_version') AS contract_version,
  json_extract_string(handoff_json, '$.selection_policy') AS selection_policy,
  json_extract_string(handoff_json, '$.selection_reason') AS selection_reason,
  json_extract_string(handoff_json, '$.top_driver_item_id') AS top_driver_item_id,
  json_extract_string(handoff_json, '$.top_driver_shown_value') AS top_driver_shown_value,
  json_extract_string(handoff_json, '$.ui_message') AS ui_message,
  handoff_json
FROM handoff_delivery_runs;

CREATE OR REPLACE VIEW guided_session_summary AS
WITH intervention_events AS (
  SELECT *
  FROM raw_attempt_events
  WHERE intervention_id IS NOT NULL
),
session_rollup AS (
  SELECT
    intervention_id,
    session_id,
    app,
    MIN(timestamp_utc) AS session_start_utc,
    MAX(timestamp_utc) AS session_end_utc,
    COUNT(*) AS attempts,
    SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) AS passes,
    SUM(CASE WHEN result = 'fail' THEN 1 ELSE 0 END) AS fails,
    ROUND(100.0 * SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) / COUNT(*), 1) AS accuracy_pct,
    ROUND(AVG(response_time_ms), 1) AS avg_response_ms
  FROM intervention_events
  GROUP BY intervention_id, session_id, app
)
SELECT
  s.intervention_id,
  s.session_id,
  s.app,
  s.session_start_utc,
  s.session_end_utc,
  s.attempts,
  s.passes,
  s.fails,
  s.accuracy_pct,
  s.avg_response_ms,
  d.delivery_id,
  d.created_at_utc AS delivered_at_utc,
  d.recommended_app,
  d.delivery_mode,
  d.verified,
  d.focus_item_count,
  d.selection_policy,
  d.selection_reason,
  d.top_driver_item_id,
  d.top_driver_shown_value
FROM session_rollup s
LEFT JOIN delivered_handoffs d
  ON s.intervention_id = d.handoff_id;

CREATE OR REPLACE VIEW guided_focus_item_outcomes AS
WITH guided_events AS (
  SELECT
    intervention_id,
    session_id,
    app,
    item_id,
    shown_value,
    result,
    timestamp_utc
  FROM raw_attempt_events
  WHERE intervention_id IS NOT NULL
),
expanded_focus_items AS (
  SELECT
    h.handoff_id,
    h.recommended_app,
    json_extract_string(item.value, '$.item_id') AS focus_item_id,
    json_extract_string(item.value, '$.shown_value') AS focus_shown_value
  FROM delivered_handoffs h,
  json_each(json_extract(h.handoff_json, '$.focus_items')) AS item
  WHERE h.handoff_id IS NOT NULL
),
focus_attempts AS (
  SELECT
    f.handoff_id AS intervention_id,
    g.session_id,
    COALESCE(g.app, f.recommended_app) AS app,
    f.focus_item_id,
    COALESCE(MAX(g.shown_value), MAX(f.focus_shown_value)) AS shown_value,
    COUNT(g.item_id) AS attempts_on_focus_item,
    SUM(CASE WHEN g.result = 'pass' THEN 1 ELSE 0 END) AS passes_on_focus_item,
    SUM(CASE WHEN g.result = 'fail' THEN 1 ELSE 0 END) AS fails_on_focus_item,
    ROUND(
      100.0 * SUM(CASE WHEN g.result = 'pass' THEN 1 ELSE 0 END) / NULLIF(COUNT(g.item_id), 0),
      1
    ) AS focus_item_accuracy_pct,
    MAX(g.timestamp_utc) AS last_seen_utc
  FROM expanded_focus_items f
  LEFT JOIN guided_events g
    ON g.intervention_id = f.handoff_id
   AND g.item_id = f.focus_item_id
  GROUP BY f.handoff_id, g.session_id, COALESCE(g.app, f.recommended_app), f.focus_item_id
)
SELECT *
FROM focus_attempts
WHERE session_id IS NOT NULL;

CREATE OR REPLACE VIEW guided_app_performance AS
SELECT
  app,
  COUNT(*) AS guided_sessions,
  SUM(attempts) AS guided_attempts,
  SUM(passes) AS guided_passes,
  SUM(fails) AS guided_fails,
  ROUND(100.0 * SUM(passes) / NULLIF(SUM(attempts), 0), 1) AS guided_accuracy_pct,
  ROUND(AVG(avg_response_ms), 1) AS avg_guided_response_ms,
  MAX(session_end_utc) AS last_guided_session_utc
FROM guided_session_summary
GROUP BY app;

CREATE OR REPLACE VIEW normal_session_summary AS
SELECT
  session_id,
  app,
  MIN(timestamp_utc) AS session_start_utc,
  MAX(timestamp_utc) AS session_end_utc,
  COUNT(*) AS attempts,
  SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) AS passes,
  SUM(CASE WHEN result = 'fail' THEN 1 ELSE 0 END) AS fails,
  ROUND(100.0 * SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) / COUNT(*), 1) AS accuracy_pct,
  ROUND(AVG(response_time_ms), 1) AS avg_response_ms
FROM raw_attempt_events
WHERE intervention_id IS NULL
GROUP BY session_id, app;

CREATE OR REPLACE VIEW normal_app_performance AS
SELECT
  app,
  COUNT(*) AS normal_sessions,
  SUM(attempts) AS normal_attempts,
  SUM(passes) AS normal_passes,
  SUM(fails) AS normal_fails,
  ROUND(100.0 * SUM(passes) / NULLIF(SUM(attempts), 0), 1) AS normal_accuracy_pct,
  ROUND(AVG(avg_response_ms), 1) AS avg_normal_response_ms,
  MAX(session_end_utc) AS last_normal_session_utc
FROM normal_session_summary
GROUP BY app;

CREATE OR REPLACE VIEW guided_vs_normal_app_comparison AS
SELECT
  COALESCE(n.app, g.app) AS app,
  COALESCE(n.normal_sessions, 0) AS normal_sessions,
  COALESCE(n.normal_attempts, 0) AS normal_attempts,
  COALESCE(n.normal_fails, 0) AS normal_fails,
  n.normal_accuracy_pct,
  n.avg_normal_response_ms,
  COALESCE(g.guided_sessions, 0) AS guided_sessions,
  COALESCE(g.guided_attempts, 0) AS guided_attempts,
  COALESCE(g.guided_fails, 0) AS guided_fails,
  g.guided_accuracy_pct,
  g.avg_guided_response_ms,
  CASE
    WHEN n.normal_sessions IS NOT NULL AND g.guided_sessions IS NOT NULL
    THEN ROUND(g.guided_accuracy_pct - n.normal_accuracy_pct, 1)
    ELSE NULL
  END AS accuracy_delta_pct,
  CASE
    WHEN n.normal_sessions IS NOT NULL AND g.guided_sessions IS NOT NULL
    THEN ROUND(g.avg_guided_response_ms - n.avg_normal_response_ms, 1)
    ELSE NULL
  END AS response_time_delta_ms
FROM normal_app_performance n
FULL OUTER JOIN guided_app_performance g
  ON n.app = g.app;

CREATE OR REPLACE VIEW guided_session_evaluation AS
WITH focus_rollup AS (
  SELECT
    intervention_id,
    session_id,
    app,
    COUNT(*) AS focus_items_declared,
    SUM(CASE WHEN attempts_on_focus_item > 0 THEN 1 ELSE 0 END) AS focus_items_seen_count,
    SUM(CASE WHEN COALESCE(fails_on_focus_item, 0) > 0 THEN 1 ELSE 0 END) AS focus_items_failed_count,
    SUM(CASE WHEN attempts_on_focus_item > 0 AND COALESCE(fails_on_focus_item, 0) = 0 THEN 1 ELSE 0 END) AS focus_items_cleared_count
  FROM guided_focus_item_outcomes
  GROUP BY intervention_id, session_id, app
)
SELECT
  g.app,
  g.intervention_id,
  g.session_id,
  g.session_start_utc,
  g.session_end_utc,
  g.attempts,
  g.passes,
  g.fails,
  g.accuracy_pct,
  g.avg_response_ms,
  g.selection_policy,
  g.selection_reason,
  g.top_driver_item_id,
  g.top_driver_shown_value,
  COALESCE(g.focus_item_count, f.focus_items_declared, 0) AS focus_item_count,
  COALESCE(f.focus_items_seen_count, 0) AS focus_items_seen_count,
  COALESCE(f.focus_items_failed_count, 0) AS focus_items_failed_count,
  COALESCE(f.focus_items_cleared_count, 0) AS focus_items_cleared_count,
  ROUND(
    100.0 * COALESCE(f.focus_items_seen_count, 0) / NULLIF(COALESCE(g.focus_item_count, f.focus_items_declared, 0), 0),
    1
  ) AS focus_item_surface_rate_pct,
  ROUND(
    100.0 * COALESCE(f.focus_items_cleared_count, 0) / NULLIF(COALESCE(g.focus_item_count, f.focus_items_declared, 0), 0),
    1
  ) AS focus_item_clear_rate_pct,
  CASE
    WHEN COALESCE(g.focus_item_count, f.focus_items_declared, 0) = 0 THEN 'no_focus_items'
    WHEN COALESCE(f.focus_items_seen_count, 0) < COALESCE(g.focus_item_count, f.focus_items_declared, 0) THEN 'focus_items_not_fully_seen'
    WHEN COALESCE(f.focus_items_failed_count, 0) > 0 THEN 'focus_items_still_failing'
    WHEN g.fails > 0 THEN 'nonfocus_errors_remain'
    ELSE 'focus_items_cleared'
  END AS guided_outcome,
  CASE
    WHEN COALESCE(g.focus_item_count, f.focus_items_declared, 0) = 0 THEN 'inspect_handoff'
    WHEN COALESCE(f.focus_items_seen_count, 0) < COALESCE(g.focus_item_count, f.focus_items_declared, 0) THEN 'repeat_same_app'
    WHEN COALESCE(f.focus_items_failed_count, 0) > 0 THEN 'repeat_same_app'
    WHEN g.fails > 0 THEN 'continue_same_app'
    ELSE 'switch_or_expand'
  END AS follow_up_action
FROM guided_session_summary g
LEFT JOIN focus_rollup f
  ON g.intervention_id = f.intervention_id
 AND g.session_id = f.session_id
 AND g.app = f.app;

CREATE OR REPLACE VIEW guided_follow_up_summary AS
SELECT
  app,
  guided_outcome,
  follow_up_action,
  COUNT(*) AS session_count,
  ROUND(AVG(accuracy_pct), 1) AS avg_accuracy_pct,
  ROUND(AVG(focus_item_surface_rate_pct), 1) AS avg_focus_surface_rate_pct,
  ROUND(AVG(focus_item_clear_rate_pct), 1) AS avg_focus_clear_rate_pct,
  MAX(session_end_utc) AS last_session_end_utc
FROM guided_session_evaluation
GROUP BY app, guided_outcome, follow_up_action;

CREATE OR REPLACE VIEW guided_chain_validation_status AS
WITH apps AS (
  SELECT * FROM (
    VALUES ('alphabet'), ('matras'), ('conjuncts'), ('words')
  ) AS t(app)
),
guided_rollup AS (
  SELECT
    app,
    COUNT(*) AS guided_sessions,
    SUM(CASE WHEN focus_item_count > 0 THEN 1 ELSE 0 END) AS sessions_with_focus_items,
    SUM(CASE WHEN focus_items_seen_count > 0 THEN 1 ELSE 0 END) AS sessions_with_focus_seen,
    MAX(session_end_utc) AS last_guided_session_utc
  FROM guided_session_evaluation
  GROUP BY app
)
SELECT
  a.app,
  COALESCE(g.guided_sessions, 0) AS guided_sessions,
  COALESCE(g.sessions_with_focus_items, 0) AS sessions_with_focus_items,
  COALESCE(g.sessions_with_focus_seen, 0) AS sessions_with_focus_seen,
  g.last_guided_session_utc,
  CASE
    WHEN COALESCE(g.guided_sessions, 0) = 0 THEN 'not_started'
    WHEN COALESCE(g.sessions_with_focus_items, 0) = 0 THEN 'guided_without_logged_focus'
    WHEN COALESCE(g.sessions_with_focus_seen, 0) = 0 THEN 'guided_focus_not_seen'
    ELSE 'validated'
  END AS validation_status,
  CASE
    WHEN COALESCE(g.guided_sessions, 0) = 0 THEN 'run one guided session'
    WHEN COALESCE(g.sessions_with_focus_items, 0) = 0 THEN 'deliver manual handoff again and let it auto-save'
    WHEN COALESCE(g.sessions_with_focus_seen, 0) = 0 THEN 'rerun guided session and confirm the target item appears'
    ELSE 'chain validated'
  END AS next_validation_action
FROM apps a
LEFT JOIN guided_rollup g
  ON a.app = g.app;
