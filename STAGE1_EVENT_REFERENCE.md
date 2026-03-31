# Stage 1 Event Reference

Frozen reference for KALS Stage 1 raw telemetry before Stage 2 ETL work begins.

## Status

- Stage 1 instrumentation: complete
- Stage 1.5 telemetry QA: complete for event shape
- Shared raw event buffer: `localStorage.kjt_events`
- Post-normalization smoke check still recommended for updated `alphabet` and `conjuncts` `item_id` values

## Raw Event Fields

Each raw event record must contain:

- `session_id`
- `app`
- `app_version`
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
- `distractor_mode`
- `difficulty`
- `intervention_id`

## Frozen Conventions

### Shared conventions

- `mode = "recognition"` for Stage 1
- `intervention_id = null` unless an agent intervention exists
- `difficulty = null` unless the app exposes a meaningful difficulty control
- `timestamp` is ISO 8601 UTC
- `result` is `pass` or `fail`

### Session conventions

- A session starts when the learner starts a run in the app
- `session_id` is stored in `sessionStorage`
- Timeout after 20 minutes of inactivity resets the active telemetry session
- All attempts in one run should share the same `session_id`

## Canonical `item_id` Formats

These are the frozen Stage 1 item ID conventions currently emitted by the apps:

- `alphabet`: `alpha.L001` through `alpha.L049`
- `matras`: `matra.<deck row id>`
  - Examples: `matra.L014`, `matra.CV235`, `matra.M002`
- `conjuncts`: `conjunct.C001` through `conjunct.C035`
- `words`: `word.W001` through `word.W100`

## App-Specific Notes

### `alphabet`

- `item_type = "akshara"`
- `choices_presented` is populated
- Timeout uses `user_answer = null`

### `matras`

- `item_type` may be `akshara` or `matra` depending on deck row
- `choices_presented` is populated
- `distractor_mode` is populated when relevant
- Timeout uses `user_answer = null`

### `conjuncts`

- `item_type = "conjunct"`
- `choices_presented` is populated
- `distractor_mode = null`
- Timeout uses `user_answer = null`

### `words`

- `item_type = "word"`
- Self-scored app exception:
  - `user_answer = null`
  - `choices_presented = null`
  - `distractor_mode = null`
- `response_time_ms` measures reveal-to-self-score latency

## QA Outcome

Manual browser validation has confirmed:

- `alphabet` appends valid events to `kjt_events`
- `matras` appends valid events to `kjt_events`
- `conjuncts` appends valid events to `kjt_events`
- `words` appends valid events to `kjt_events`

This reference should be treated as the Stage 1 contract for Stage 2 ETL and analytics work.
