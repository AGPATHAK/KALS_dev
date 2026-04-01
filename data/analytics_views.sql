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
