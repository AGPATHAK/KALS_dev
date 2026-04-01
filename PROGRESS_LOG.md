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
- Guided-session evaluation now has its own follow-up report for deciding whether the agent should repeat the same app, continue it, or switch.
- Handoff delivery can now be manually targeted to a specific app for chain validation, without changing the recommender.
- Manual targeted handoffs now save delivery rows automatically, so guided-session evaluation can reconstruct their focus items without needing `--save-run`.
- Whole-chain validation now has its own report for checking which apps are fully validated and which still need one more clean guided run.
- The first full end-to-end chain is now validated across all four apps.
- A browser-side coach hub now exists as the first non-terminal control surface for launching recommended practice.
- The practice flow is now smoother: the coach opens apps in new tabs, shows the post-practice pipeline commands, and every app exposes a direct `Coach Hub` return shortcut in its header.
- A lightweight local coach control server now exists as the next UX layer above the validated pipeline, so the browser can request ingest + recommendation refresh without dropping back into the old stop-and-run-bash loop each time.
- The smoother practice entrypoint now also has a one-command launcher that starts the local coach control server and opens the coach together.
- Guided review now uses a smaller focus subset in short handoffs so app-side Leitner-lite spacing can actually resurface weak items instead of filling the whole session with distinct targets.

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
- `pipeline/evaluate_guided_sessions.py` can now:
  - evaluate whether guided focus items were actually surfaced
  - report whether they were cleared or still failing
  - suggest a simple follow-up action per guided session
- `pipeline/check_chain_validation.py` can now:
  - report guided-session validation coverage by app
  - distinguish fully validated apps from apps with only partial guided evidence
  - confirm when all four apps have completed the same first-pass guided-session loop
- `coach/index.html` can now:
  - read the pending/latest recommendation handoff from browser storage
  - show the recommended app and focus items
  - launch the recommended app from the browser without using bash for each app start
  - open any app directly for normal practice
  - call a local coach control server to ingest browser events and refresh the next recommendation in place
  - reuse named coach/app tabs instead of multiplying browser pages during practice
- `pipeline/deliver_recommendation_handoff.py` can now:
  - deliver the normal recommender-selected handoff
  - or deliver a manual app-targeted handoff for validation runs
  - automatically persist manual validation handoffs into `handoff_delivery_runs`
- `pipeline/coach_control_server.py` can now:
  - accept browser-side `kjt_events` over a local HTTP endpoint
  - ingest them into DuckDB without reopening the Playwright profile
  - recompute the deterministic recommendation
  - persist recommendation and delivery rows for the refreshed handoff
- `pipeline/start_coach_practice.py` can now:
  - start the local coach control server
  - open the coach hub in the persistent Playwright profile
  - shut both down together from one terminal session

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
- The new follow-up actions are still heuristic and should be treated as evaluation scaffolding, not final policy.
- Cross-app chain validation is now complete for the first-pass advisory loop.
- Future work should treat this validated chain as the baseline and avoid changing too many moving pieces at once.
- Recommendation refresh is smoother now, but it depends on keeping the local coach control server running in a separate terminal during practice.

### Immediate Next Step

Use the smoother coach-led refresh loop to generate more natural real-practice data before major recommender refinements. The most likely next changes are:

- keep testing the local coach control path during real practice
- use guided-session performance, focus-item outcomes, and guided-vs-normal comparisons to refine the recommender once the real-practice sample is less toy-like
- keep major refinements deferred unless they are needed to interpret the validated chain
- decide how much of the current handoff contract should become the real app command interface

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
