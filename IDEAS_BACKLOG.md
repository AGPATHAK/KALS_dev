# KALS Ideas Backlog

Deferred design ideas that are important, but intentionally not on the current critical path.

## How To Use This File

- Keep entries short and concrete.
- Capture why the idea matters.
- Capture why it is deferred.
- Promote an item into `ROADMAP.md` only when it becomes an active milestone.

## 2026-04-01

### Coach UI Clarifications And Progressive Disclosure

- Idea:
  Simplify the coach UI so recommendation mechanics are clearer and low-signal controls or labels are either explained better or hidden until needed.

- Why it matters:
  The current coach loop works, but some controls still read like system internals rather than learner-facing affordances. Examples already observed in live use:
  - the `Selection Policy` field does not yet communicate much practical value
  - the `Clear Pending` action is not self-explanatory
  - once session-complete auto-refresh is stable, the role of the manual `Refresh Recommendation` button may need to change
  - coach status text and the last-session summary can feel partly redundant

- What this could enable later:
  - clearer learner-facing coach UI
  - progressive disclosure of system details only when useful
  - a cleaner distinction between “what just happened” and “what to do next”
  - fewer moments where the user has to infer product behavior from technical wording

- Why deferred for now:
  The current priority is to validate the Stage 4 loop and then refine the recommender. This is a real UX pass, but it is not blocking the core control loop anymore.

### Coach As Ranked Practice Hub

- Idea:
  Reshape the coach from a single-app recommendation card plus a separate launcher into a ranked four-app practice hub.

- Why it matters:
  A ranked app grid would give the learner more agency while still expressing the system’s priorities. It could also make the “fatigue” question less about hard stop logic and more about guided choice. The suggested shape is something like:
  - strongly recommended
  - recommended
  - practice
  - test or maintenance
  along with last accuracy and time since last practice

- What this could enable later:
  - learner choice without losing recommendation structure
  - easier cross-app comparison in one place
  - a more natural place to show app freshness, recent performance, and review pressure together
  - softer fatigue handling through ranked options instead of a single forced next step

- Why deferred for now:
  This is a meaningful coach redesign and should happen after the Stage 4 loop and recommender behavior settle a bit more. It is better treated as a product pass than as a blocking systems step.

### Teacher-Like Reflective Language

- Idea:
  Shape Stage 3B reflections and later coach-facing explanations to sound more like a good teacher or tutor than an analytics console.

- Why it matters:
  The current Stage 3B reflection path is structurally useful, but eventually the system should explain learner patterns in a more pedagogically supportive way, for example:
  - “you are mixing up `da` and `tha`”
  - “the `au` matra still needs reinforcement”
  - “let’s review this in a shorter focused session”

- What this could enable later:
  - more motivating learner-facing explanations
  - reflections that are easier to act on during real practice
  - a bridge from raw analytics into tutor-style coaching language
  - better eventual teacher-mode prompts for OpenAI or local LLM backends

- Why deferred for now:
  The reflection contract itself was the first milestone. Tone shaping should come after we are satisfied that the underlying evidence selection is sound and the coach UX is stable enough to present richer language.

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

### Reuse App-Side Leitner Signals In The Coach

- Idea:
  Bring the coach recommender closer to the standalone apps' intuitive mastery logic by reusing or reconstructing Leitner-lite signals at the analytics layer.

- Why it matters:
  The standalone apps already feel more pedagogically intuitive because they respond to item mastery, weakness, and recovery in a lightweight spaced-repetition style.
  The current coach still leans too heavily on cumulative telemetry totals, which can keep recommending `alphabet` longer than feels reasonable.

- What this could enable later:
  - coach rankings that decay old mistakes more naturally
  - stronger use of recent recovery and box-like mastery state
  - fewer cases where high historical exposure dominates current pedagogical need
  - closer alignment between standalone app behavior and coach-guided behavior

- Why deferred for now:
  The roadmap priority is still to complete the first major architecture milestones before deep recommender retuning.
  This is a meaningful recommendation-policy refinement, not a blocker for the Stage 3B reflective-layer milestone.

### Local LLM Reflection Option

- Idea:
  Support a local LLM runtime, such as Llama or a similar local model, for Stage 3B reflection work.

- Why it matters:
  Local inference would let reflective analysis be tested without an external API key, recurring API cost, or cloud dependency.
  It would also fit the project's local-first development style and make experimentation easier once the reflection contract stabilizes.

- What this could enable later:
  - offline Stage 3B experimentation
  - local comparison between OpenAI reflections and local-model reflections
  - easier privacy-preserving testing on real learner history
  - a future pluggable reflection backend instead of a single-provider path

- Why deferred for now:
  The current goal is to validate the Stage 3B contract itself before multiplying model backends.
  Local-model support is best added once the reflection input/output shape is stable enough to compare providers fairly.
