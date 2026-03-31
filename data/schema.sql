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
