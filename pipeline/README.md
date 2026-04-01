# Stage 2 Pipeline

This folder contains the first Stage 2 implementation for KALS:

- Playwright reads the browser-side `kjt_events` buffer
- Python validates raw events against the frozen Stage 1 contract
- DuckDB stores validated raw events in a local analytical database

Current milestone status:

- the first end-to-end advisory guided-session chain is now validated across all four apps
- recommendation -> handoff delivery -> app consumption -> telemetry return -> evaluation is working end to end
- a browser-side coach hub now lets you launch the recommended app without using bash for each practice start

## Install

Create a virtual environment if you want:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install Python dependencies:

```bash
python3 -m pip install -r pipeline/requirements.txt
python3 -m playwright install chromium
```

## Run

Default run:

```bash
python3 pipeline/ingest_events.py
```

This will:

- open the local app pages with Playwright
- read `localStorage.kjt_events`
- validate and deduplicate events
- write valid events into `data/kals.duckdb`
- write invalid records into `validation_issues`

Refresh and query the first analytical views:

```bash
.venv/bin/python pipeline/query_insights.py --refresh-views
```

This prints:

- event counts by app
- recent raw events
- weak items
- confusion pairs
- first-pass accuracy by item
- item recency summaries
- prioritized review candidates
- recent app usage
- next-session app summary
- guided session summary
- guided focus-item outcomes
- guided app performance
- guided-vs-normal app comparison

Generate a deterministic next-session recommendation:

```bash
.venv/bin/python pipeline/recommend_next_session.py --refresh-views
```

This prints:

- recommended next app
- selection policy and selection reason
- recommended session size
- handoff contract details for a future app-facing integration
- top review items for that app
- app ranking with simple rule-based scores

Open the browser-side coach hub in the persistent Playwright profile:

```bash
.venv/bin/python pipeline/open_app.py coach
```

The coach hub can:

- show the current pending or latest recommendation
- launch the recommended app from the browser
- open any practice app directly for normal use
- reduce the need to trigger app launches from bash during real practice

Structured JSON output:

```bash
.venv/bin/python pipeline/recommend_next_session.py --refresh-views --format json
```

Handoff-only JSON output:

```bash
.venv/bin/python pipeline/recommend_next_session.py --refresh-views --format handoff
```

This emits a machine-friendly contract with:

- contract version
- action and delivery mode
- target app and mode
- session size
- focus strategy
- recommended item IDs
- a future app-request block

Deliver the current handoff contract into the persistent Playwright app environment:

```bash
.venv/bin/python pipeline/deliver_recommendation_handoff.py --save-run
```

This will:

- generate the current recommendation handoff
- open the target app page through the persistent Playwright profile
- write the handoff into browser `localStorage`
- verify the write
- optionally log the delivery in DuckDB

For chain validation, you can also force a manual handoff for a specific app:

```bash
.venv/bin/python pipeline/deliver_recommendation_handoff.py --target-app alphabet --focus-item-id alpha.L008 --session-size 5
```

This is useful when you want to validate the full guided-session loop for a specific app even if the recommender is currently choosing a different one. Manual targeted handoffs are now saved automatically into `handoff_delivery_runs`, so guided-session evaluation can reconstruct their intended focus items.

Current app-side consumer:

- `alphabet` can now detect a pending advisory handoff on its home screen
- `alphabet` shows an `Agent-Guided Session` panel when a valid pending handoff exists
- starting that guided session prioritizes the recommended letter IDs and then fills the rest of the deck normally
- the pending handoff is consumed on guided start, while the latest delivered handoff remains available for inspection
- `matras` can now detect a pending advisory handoff on its home screen
- `matras` shows an `Agent-Guided Session` panel when a valid pending handoff exists
- starting that guided session prioritizes the recommended matra IDs and then fills the rest of the deck normally
- the pending handoff is consumed on guided start, while the latest delivered handoff remains available for inspection
- `conjuncts` can now detect a pending advisory handoff on its home screen
- `conjuncts` shows an `Agent-Guided Session` panel when a valid pending handoff exists
- starting that guided session prioritizes the recommended conjunct IDs and then fills the rest of the deck normally
- the pending handoff is consumed on guided start, while the latest delivered handoff remains available for inspection
- `words` can now detect a pending advisory handoff on its home screen
- `words` shows an `Agent-Guided Session` panel when a valid pending handoff exists
- starting that guided session prioritizes the recommended word IDs and then fills the rest of the deck normally
- the pending handoff is consumed on guided start, while the latest delivered handoff remains available for inspection

Persist a recommendation run for later evaluation:

```bash
.venv/bin/python pipeline/recommend_next_session.py --refresh-views --save-run
```

Replay-evaluate the deterministic recommender against historical sessions:

```bash
.venv/bin/python pipeline/replay_evaluate.py --refresh-views
```

This prints:

- how many historical sessions could be replayed
- how often the predicted app matched the learner's actual next app
- how often the predicted review items appeared anywhere in the target session
- how often the predicted review items overlapped with later failed items
- per-session replay rows for inspection

The current baseline now uses two selection modes:

- `highest_priority`: choose the app with the strongest cross-app review pressure
- `continue_recent_app`: continue the most recent app when it is still newly introduced or ended with fresh failures

Persist replay evaluation rows for later inspection:

```bash
.venv/bin/python pipeline/replay_evaluate.py --save-run
```

Evaluate guided sessions and suggest follow-up actions:

```bash
.venv/bin/python pipeline/evaluate_guided_sessions.py --refresh-views
```

This prints:

- recent guided sessions
- whether the intended focus items were surfaced
- whether those focus items were cleared or still failing
- a simple follow-up action such as `repeat_same_app`, `continue_same_app`, or `switch_or_expand`
- guided-vs-normal comparison for apps that already have guided-session data

Check whole-chain validation coverage across apps:

```bash
.venv/bin/python pipeline/check_chain_validation.py --refresh-views
```

This prints:

- which apps have real guided sessions
- which guided sessions also have reconstructable focus-item evidence
- which apps are fully validated versus still needing one more clean run

At the current milestone, this report should show all four apps as validated.

## Notes

- This script is intentionally local-first and small.
- It uses the frozen Stage 1 event contract from `STAGE1_EVENT_REFERENCE.md`.
- Existing local app progress stores are not touched.
- Playwright uses its own persistent browser profile in `.playwright-profile`.
- Data created in your normal browser profile is separate from the Playwright profile.
- Recommendation payloads and replay-evaluation rows can both be stored in DuckDB for later analysis.
- The recommender output now includes a dedicated `handoff` block intended to evolve into the later bidirectional app-agent contract.
- The delivery bridge currently writes advisory handoffs into:
  - `kals_latest_recommendation_handoff`
  - `kals_pending_recommendation_handoff`
- Guided sessions can now be evaluated analytically because app-side guided runs write the delivered `handoff_id` back into raw telemetry as `intervention_id`.
- The analytics layer can now compare guided-session performance against normal-session performance by app.
- Guided-session evaluation is now separated into its own script so the follow-up decision remains readable and inspectable.
- Whole-chain validation now has its own report so we can tell when all apps have truly completed the same guided-session path.
- The current stack should now be treated as a validated baseline before major recommender refinements are introduced.

## Use The Playwright Browser For Stage 2

To create data that the Stage 2 pipeline can read reliably, open an app through the persistent Playwright profile:

```bash
.venv/bin/python pipeline/open_app.py alphabet
```

Or open the coach hub first and launch apps from there:

```bash
.venv/bin/python pipeline/open_app.py coach
```

Then practice in that browser window. When you are done:

1. close the browser or stop the script with `Ctrl+C`
2. run the ingest:

```bash
.venv/bin/python pipeline/ingest_events.py
```

This keeps the browser context reproducible and makes the browser-to-Python bridge explicit.
