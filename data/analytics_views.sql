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
