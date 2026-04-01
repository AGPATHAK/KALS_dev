# KALS Progress Log

Append-only session log for resuming work across gaps.

## How To Use This Log

- Add a new dated entry at the top for each meaningful work session or milestone.
- Reference commit hashes when available.
- Keep entries focused on:
  - what changed
  - what now works
  - known limitations
  - immediate next step

## 2026-04-01

### Current State

- Stage 3A is now split into two working parts:
  - deterministic recommendation generation
  - offline replay evaluation against historical sessions
- Recommendation payloads are structured, versioned, and can be stored in DuckDB.
- Replay evaluation rows can also be stored in DuckDB for later inspection.
- The rule baseline now includes recent-app continuation logic, not just cross-app priority ranking.
- The recommendation output now includes a dedicated handoff contract for future app-facing use.
- A delivery bridge can now place that handoff contract into the app environment via the persistent Playwright profile.
- `words` now has the first optional app-side consumption path for that advisory handoff.
- `alphabet` now also has an optional app-side consumption path for the same advisory handoff pattern.
- `matras` now also has an optional app-side consumption path for the same advisory handoff pattern.
- `conjuncts` now also has an optional app-side consumption path for the same advisory handoff pattern.
- Guided-session analytics now exist on top of `intervention_id`, so agent-guided sessions can be measured separately from normal sessions.
- Guided-session analytics can now compare agent-guided sessions against normal sessions by app.

### What Works Now

- `pipeline/recommend_next_session.py` reuses shared recommendation logic and can output:
  - terminal text
  - JSON payloads
  - handoff-only JSON
  - persisted recommendation runs
  - selection policy metadata such as `highest_priority` vs `continue_recent_app`
  - a structured `handoff` block with action, target app, session size, and focus item IDs
- `pipeline/deliver_recommendation_handoff.py` can:
  - deliver the handoff into browser `localStorage`
  - verify that the app environment received it
  - log handoff deliveries in `handoff_delivery_runs`
- `words/index.html` can:
  - surface a pending handoff as an `Agent-Guided Session` panel on the home screen
  - start a guided session that prioritizes the delivered `recommended_item_ids`
  - consume the pending handoff on guided start
  - attach the delivered `handoff_id` to telemetry as `intervention_id`
- `alphabet/index.html` can:
  - surface a pending handoff as an `Agent-Guided Session` panel on the home screen
  - start a guided session that prioritizes delivered letter IDs before filling the rest of the deck
  - consume the pending handoff on guided start
  - attach the delivered `handoff_id` to telemetry as `intervention_id`
- `matras/index.html` can:
  - surface a pending handoff as an `Agent-Guided Session` panel on the home screen
  - start a guided session that prioritizes delivered matra IDs before filling the rest of the deck
  - consume the pending handoff on guided start
  - attach the delivered `handoff_id` to telemetry as `intervention_id`
- `conjuncts/index.html` can:
  - surface a pending handoff as an `Agent-Guided Session` panel on the home screen
  - start a guided session that prioritizes delivered conjunct IDs before filling the rest of the deck
  - consume the pending handoff on guided start
  - attach the delivered `handoff_id` to telemetry as `intervention_id`
- `pipeline/replay_evaluate.py` can:
  - rebuild "what the agent knew before session X"
  - run the same deterministic recommender on that snapshot
  - compare predicted app against the learner's actual next app
  - compare predicted review items against any items actually seen in the target session
  - compare predicted review items against the target session's failed items
  - persist replay evaluation rows in `replay_evaluation_runs`
- `data/analytics_views.sql` and `pipeline/query_insights.py` can now report:
  - guided session summaries
  - guided focus-item outcomes
  - guided app performance
  - guided-vs-normal app comparison

### Current Replay Signal

- On the current toy dataset, replay evaluates 7 historical sessions.
- The present rule baseline now matches the learner's actual next app in 4 of 7 replayed sessions.
- Item-seen rate is now measurable, which is more useful for repeated review than strict fail overlap alone.
- Item-hit rate is currently 0.0% on later failed items.
- This is useful, not discouraging: it shows the replay harness can now measure whether rule changes are helping or not.

### Key Commands To Resume

Run the recommender with structured output:

```bash
.venv/bin/python pipeline/recommend_next_session.py --refresh-views --format json
```

Emit only the handoff contract:

```bash
.venv/bin/python pipeline/recommend_next_session.py --refresh-views --format handoff
```

Replay-evaluate the recommender:

```bash
.venv/bin/python pipeline/replay_evaluate.py --refresh-views
```

Persist replay evaluation rows:

```bash
.venv/bin/python pipeline/replay_evaluate.py --save-run
```

Deliver the current handoff into the app environment:

```bash
.venv/bin/python pipeline/deliver_recommendation_handoff.py --save-run
```

### Known Limitations

- The current data is still small and ordered by a few manual sessions, so replay metrics are illustrative rather than decisive.
- The current rule engine over-favors `alphabet` on this dataset.
- Replay is now slightly softer than before, but it still does not capture concept-level transfer across apps.
- The apps still do not consume the delivered handoff automatically; the bridge currently writes advisory data only.
- All four apps now support optional advisory handoff consumption, but the handoff is still learner-started rather than automatically enforced.
- Guided-session evaluation is still early and depends on creating more real guided-session data.
- Guided-session comparisons are now possible, but the sample is still too small for strong conclusions.

### Immediate Next Step

Use the replay output to refine the deterministic rule engine before adding more autonomy. The most likely next changes are:

- generate more real guided-session data in the Playwright profile
- inspect guided-session performance, focus-item outcomes, and guided-vs-normal comparisons in DuckDB
- decide how much of the current handoff contract should become the real app command interface
- evaluate whether replay and guided-session metrics are enough before touching the rule engine again

### Relevant Commits

- `d8a7d10` Shape recommender output as JSON and log recommendation runs
- `a054c62` Add progress log and update roadmap status

## 2026-03-31

### Current State

- Stage 1 is complete and frozen.
- Stage 2 ingest is working with Python, Playwright, and DuckDB.
- Stage 2.5 learner-state analytics are working.
- A first deterministic Stage 3A baseline recommender is working.
- Apps are still one-way telemetry emitters only; no app-agent command protocol exists yet.

### What Works Now

- All four apps emit shared raw telemetry into `kjt_events`.
- Stage 2 ingest reads the persistent Playwright browser profile and stores validated events in DuckDB.
- Raw-event validation and deduplication are working.
- Analytical views exist for:
  - app counts
  - weak items
  - confusion pairs
  - first-pass accuracy
  - item recency
  - prioritized review candidates
  - next-session app summary
- The deterministic recommender outputs:
  - recommended next app
  - recommended session size
  - top review items
  - simple rule-based reasons

### Key Commands To Resume

Open an app in the persistent Playwright browser profile:

```bash
.venv/bin/python pipeline/open_app.py alphabet
```

Ingest the latest browser-side events:

```bash
.venv/bin/python pipeline/ingest_events.py
```

Inspect the analytical views:

```bash
.venv/bin/python pipeline/query_insights.py --refresh-views
```

Run the deterministic recommender:

```bash
.venv/bin/python pipeline/recommend_next_session.py --refresh-views
```

### Known Limitations

- Current data is still small and mainly useful for pipeline validation, not strong pedagogical conclusions.
- The recommender is deterministic and intentionally simple.
- The recommender is still advisory only; it does not trigger apps or push recommended cards into app state.
- The Playwright browser profile is separate from the normal browser profile by design.
- `ROADMAP.md` should be kept aligned with actual progress when milestones are crossed.

### Immediate Next Step

Move from the current deterministic baseline toward a fuller Stage 3A rule engine by adding one or both of:

- a more explicit recommendation output format that can later be logged and evaluated
- a recommendation-to-app handoff shape that Stage 5A can eventually consume

### Relevant Commits

- `e732ee2` Add session-size rule to the deterministic recommender
- `9b418a3` Add next-session app summary to Stage 2 analytics
- `2f60093` Build Stage 2 ingest pipeline and initial analytics views
- `6c02cee` Freeze Stage 1 telemetry schema and normalize item IDs
- `53455ae` Complete Stage 1 telemetry instrumentation for conjuncts and words
