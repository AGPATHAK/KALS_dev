# KALS Ideas Backlog

Deferred design ideas that are important, but intentionally not on the current critical path.

## How To Use This File

- Keep entries short and concrete.
- Capture why the idea matters.
- Capture why it is deferred.
- Promote an item into `ROADMAP.md` only when it becomes an active milestone.

## 2026-04-01

### Cross-App Concept Model

- Idea:
  Move from app-centered recommendation logic toward concept-centered learner modeling.

- Why it matters:
  A weak base akshara can show up again inside matras, conjuncts, and words.
  In real script learning, the best intervention may be to reinforce the same underlying concept in a richer context rather than only drilling the original app.

- What this could enable later:
  - concept-level weak-item tracking across apps
  - transfer-aware recommendations
  - recommendations like:
    - review in `alphabet`
    - reinforce in `matras`
    - confirm transfer in `words`
  - evaluation that measures concept repair, not only same-app prediction quality

- Why deferred for now:
  The current goal is still to complete one full end-to-end pass through the planned roadmap:
  telemetry -> ingest -> analytics -> deterministic recommender -> replay evaluation -> eventual app-agent handoff.
  Cross-app concept modeling is better treated as a second-pass intelligence upgrade after the first loop is complete.

### App-Type-Aware Evaluation

- Idea:
  Evaluate recommendation quality differently for multiple-choice apps and the self-scored `words` app.

- Why it matters:
  `words` produces a noisier signal than the other apps because it is self-scored and does not capture chosen distractors.
  Treating it exactly like the multiple-choice apps may distort both analytics and replay conclusions.

- What this could enable later:
  - separate confidence levels by app type
  - app-specific success metrics
  - replay metrics that do not over-penalize self-scored sessions for lacking confusion-pair detail
  - cleaner comparison of recommendation quality across app families

- Why deferred for now:
  The current priority is to prove the end-to-end loop works at all.
  App-type-aware calibration is best added after the baseline recommender and replay workflow are stable enough to tune.

### Concept-Repair Evaluation

- Idea:
  Move beyond strict same-item and same-app replay scoring toward "did the underlying concept improve?" evaluation.

- Why it matters:
  In language learning, a recommendation can be pedagogically good even if it does not predict the exact next failed card.
  A learner may repair a weak concept in a different app or a richer context before the original item reappears.

- What this could enable later:
  - evaluation that credits transfer across apps
  - better scoring for reinforcement in matras, conjuncts, or words after an alphabet weakness
  - a more realistic benchmark for adaptive learning quality

- Why deferred for now:
  This depends on a concept model and a more mature recommendation contract.
  For the first pass, strict replay metrics are still useful because they are simple, inspectable, and easy to compute.

### MCP As Packaging, Not Intelligence

- Idea:
  Treat MCP wrapping as an interface/packaging step, not as the main intelligence milestone.

- Why it matters:
  It is easy to make the stack feel more advanced by standardizing tools while still not improving recommendation quality.
  The stronger learning value is in telemetry, evaluation, decision quality, and app-agent coordination.

- What this could enable later:
  - cleaner local tool interfaces
  - easier agent interoperability
  - less ad hoc app-control plumbing once the bidirectional protocol exists

- Why deferred for now:
  The system should first earn a stable decision loop before its tools are standardized.
  MCP will matter more after the recommendation and command contracts are clearer.

### Learner Data Export, Import, and Reset

- Idea:
  Add explicit controls to export learner data, re-import it later, and wipe it when needed.

- Why it matters:
  This project is now generating meaningful telemetry, app progress state, and guided-session history across multiple browser storage keys and DuckDB.
  We should be able to preserve a dataset before experiments, restore it later, or reset everything cleanly when testing from a fresh state.

- What this could enable later:
  - one-click backup of browser-side training data
  - reload of a previously exported learner state
  - safe reset for clean validation runs
  - easier comparison of "before" and "after" experimental conditions
  - portability of learner data across machines or browser profiles

- Why deferred for now:
  The current priority is still validating the first full agent-app chain.
  Data management is important, but it is a product/ops feature rather than a blocker for the current control-loop milestone.
