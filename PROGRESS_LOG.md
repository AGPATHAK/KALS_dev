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

### What Works Now

- `pipeline/recommend_next_session.py` reuses shared recommendation logic and can output:
  - terminal text
  - JSON payloads
  - persisted recommendation runs
  - selection policy metadata such as `highest_priority` vs `continue_recent_app`
- `pipeline/replay_evaluate.py` can:
  - rebuild "what the agent knew before session X"
  - run the same deterministic recommender on that snapshot
  - compare predicted app against the learner's actual next app
  - compare predicted review items against the target session's failed items
  - persist replay evaluation rows in `replay_evaluation_runs`

### Current Replay Signal

- On the current toy dataset, replay evaluates 7 historical sessions.
- The present rule baseline now matches the learner's actual next app in 4 of 7 replayed sessions.
- Item-hit rate is currently 0.0% on later failed items.
- This is useful, not discouraging: it shows the replay harness can now measure whether rule changes are helping or not.

### Key Commands To Resume

Run the recommender with structured output:

```bash
.venv/bin/python pipeline/recommend_next_session.py --refresh-views --format json
```

Replay-evaluate the recommender:

```bash
.venv/bin/python pipeline/replay_evaluate.py --refresh-views
```

Persist replay evaluation rows:

```bash
.venv/bin/python pipeline/replay_evaluate.py --save-run
```

### Known Limitations

- The current data is still small and ordered by a few manual sessions, so replay metrics are illustrative rather than decisive.
- The current rule engine over-favors `alphabet` on this dataset.
- Replay currently scores against actual failed items only; it does not yet score softer notions like "good app choice despite no failure overlap."

### Immediate Next Step

Use the replay output to refine the deterministic rule engine before adding more autonomy. The most likely next changes are:

- improve evaluation metrics beyond strict item-failure overlap
- make item-level recommendation hits more meaningful for repeated review sessions
- decide how much of the current continuation logic should eventually be exposed to the apps as a command contract

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
