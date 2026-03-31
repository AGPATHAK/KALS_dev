# Stage 1 Checklist

Execution checklist for completing KALS Stage 1: app instrumentation.

## Stage Goal

All four apps should emit raw attempt events into the shared `kjt_events` buffer using the Stage 1 schema defined in the project charter.

## Stage 1 Definition of Done

- Every learner attempt produces one raw event.
- All four apps write to the same append-only `localStorage` key: `kjt_events`.
- Each event includes the required Stage 1 fields.
- Session IDs are generated consistently and reused within a session.
- Timeout behavior is captured explicitly as a failed attempt.
- App-specific local progress stores remain separate from raw telemetry.
- `words` follows the charter exception:
  - `user_answer = null`
  - `choices_presented = null`
  - `distractor_mode = null`

## Shared Schema Checklist

Each emitted event should contain:

- `session_id`
- `app`
- `item_id`
- `item_type`
- `shown_value`
- `correct_answer`
- `user_answer`
- `choices_presented`
- `result`
- `response_time_ms`
- `timestamp`
- `mode`
- `app_version`
- `intervention_id`
- `distractor_mode`
- `difficulty`

## App-by-App Checklist

### `alphabet`

- Shared telemetry module present
- Emits events on answer selection
- Emits events on timeout
- Needs verification against final canonical `item_id` expectations

Status: Implemented, verify during telemetry QA

### `matras`

- Shared telemetry module present
- Emits events on answer selection
- Emits events on timeout
- Includes distractor mode
- Needs verification against final canonical `item_id` expectations

Status: Implemented, verify during telemetry QA

### `conjuncts`

- Add shared telemetry module
- Emit event on answer selection
- Emit event on timeout
- Use app-specific mappings:
  - `app = conjuncts`
  - `item_type = conjunct`
  - `distractor_mode = null`
  - `difficulty = null`

Status: Implemented, verify during telemetry QA

### `words`

- Add shared telemetry module
- Emit event on self-score
- Measure response time from reveal to self-score
- Use charter exceptions:
  - `user_answer = null`
  - `choices_presented = null`
  - `distractor_mode = null`
- Preserve existing progress tracking separately from raw events

Status: Implemented, verify during telemetry QA

## Telemetry QA Checklist

Run after instrumentation is complete:

- Inspect at least one session from each app in browser `localStorage`
- Confirm schema keys match exactly
- Confirm `session_id` stays stable within a session
- Confirm new session behavior after restart or inactivity
- Confirm timeout events are captured correctly
- Confirm `words` events use nulls for the exception fields
- Confirm event values are analyzable without app-specific parsing

## Immediate Execution Order

1. Inspect emitted events manually in all four apps
2. Fix any schema drift before Stage 2
3. Confirm canonical `item_id` conventions across apps
4. Freeze the Stage 1 event reference for ETL work
