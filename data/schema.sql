CREATE TABLE IF NOT EXISTS raw_attempt_events (
  event_uid VARCHAR PRIMARY KEY,
  session_id VARCHAR NOT NULL,
  app VARCHAR NOT NULL,
  app_version VARCHAR NOT NULL,
  item_id VARCHAR NOT NULL,
  item_type VARCHAR NOT NULL,
  shown_value VARCHAR NOT NULL,
  correct_answer VARCHAR NOT NULL,
  user_answer VARCHAR,
  choices_presented_json VARCHAR,
  result VARCHAR NOT NULL,
  response_time_ms BIGINT NOT NULL,
  timestamp_utc TIMESTAMP NOT NULL,
  mode VARCHAR NOT NULL,
  distractor_mode VARCHAR,
  difficulty VARCHAR,
  intervention_id VARCHAR,
  source_page VARCHAR NOT NULL,
  ingested_at_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  raw_event_json VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_issues (
  issue_uid VARCHAR PRIMARY KEY,
  event_uid VARCHAR,
  source_page VARCHAR NOT NULL,
  issue_code VARCHAR NOT NULL,
  issue_message VARCHAR NOT NULL,
  raw_event_json VARCHAR NOT NULL,
  created_at_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recommendation_runs (
  recommendation_id VARCHAR PRIMARY KEY,
  created_at_utc TIMESTAMP NOT NULL,
  source_db_path VARCHAR NOT NULL,
  recommended_app VARCHAR NOT NULL,
  app_priority_score DOUBLE NOT NULL,
  recommended_session_size INTEGER NOT NULL,
  rationale_summary VARCHAR NOT NULL,
  top_driver_item_id VARCHAR,
  top_driver_shown_value VARCHAR,
  payload_json VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS handoff_delivery_runs (
  delivery_id VARCHAR PRIMARY KEY,
  created_at_utc TIMESTAMP NOT NULL,
  source_db_path VARCHAR NOT NULL,
  contract_version VARCHAR NOT NULL,
  recommended_app VARCHAR NOT NULL,
  delivery_mode VARCHAR NOT NULL,
  profile_dir VARCHAR NOT NULL,
  source_page VARCHAR NOT NULL,
  latest_storage_key VARCHAR NOT NULL,
  pending_storage_key VARCHAR NOT NULL,
  focus_item_count INTEGER NOT NULL,
  verified BOOLEAN NOT NULL,
  handoff_json VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS replay_evaluation_runs (
  evaluation_id VARCHAR PRIMARY KEY,
  created_at_utc TIMESTAMP NOT NULL,
  source_db_path VARCHAR NOT NULL,
  evaluation_mode VARCHAR NOT NULL,
  recommender_version VARCHAR NOT NULL,
  target_session_id VARCHAR NOT NULL,
  target_app VARCHAR NOT NULL,
  target_session_start_utc TIMESTAMP NOT NULL,
  target_session_end_utc TIMESTAMP NOT NULL,
  prior_event_count BIGINT NOT NULL,
  target_attempt_count BIGINT NOT NULL,
  target_fail_count BIGINT NOT NULL,
  predicted_app VARCHAR,
  predicted_session_size INTEGER,
  app_match BOOLEAN,
  predicted_top_items_json VARCHAR NOT NULL,
  actual_seen_items_json VARCHAR,
  actual_failed_items_json VARCHAR NOT NULL,
  item_seen_count INTEGER,
  item_seen_rate DOUBLE,
  item_hit_count INTEGER NOT NULL,
  item_hit_rate DOUBLE,
  payload_json VARCHAR
);

ALTER TABLE replay_evaluation_runs ADD COLUMN IF NOT EXISTS actual_seen_items_json VARCHAR;
ALTER TABLE replay_evaluation_runs ADD COLUMN IF NOT EXISTS item_seen_count INTEGER;
ALTER TABLE replay_evaluation_runs ADD COLUMN IF NOT EXISTS item_seen_rate DOUBLE;

CREATE TABLE IF NOT EXISTS llm_reflection_runs (
  reflection_id VARCHAR PRIMARY KEY,
  created_at_utc TIMESTAMP NOT NULL,
  source_db_path VARCHAR NOT NULL,
  reflection_mode VARCHAR NOT NULL,
  provider VARCHAR NOT NULL,
  model VARCHAR,
  prompt_version VARCHAR NOT NULL,
  recommended_app VARCHAR,
  recommendation_contract_version VARCHAR,
  context_json VARCHAR NOT NULL,
  prompt_text VARCHAR NOT NULL,
  output_text VARCHAR,
  reflection_json VARCHAR,
  status VARCHAR NOT NULL,
  error_message VARCHAR
);
