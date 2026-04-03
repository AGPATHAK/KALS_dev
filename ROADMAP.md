# KALS Development Roadmap

Learning-first rewrite aligned to the KALS project charter.

## Purpose

KALS has two linked goals:

- Build practical skill in agentic AI development through a real project.
- Improve Kannada script learning through adaptive, data-informed practice.

This roadmap is written to serve both goals at once. The Kannada apps are the product surface. The agent is the control system built around them. Each stage should teach a distinct agentic AI concept while also leaving behind working infrastructure that will be reused in later stages.

## Core Principles

- Agents are clients. Interfaces are the architecture.
- Pedagogy is the product. Agency is only the control system.
- Instrument before you optimize.
- Establish a deterministic baseline before introducing LLM judgment.
- Evaluate interventions before trusting them.
- Prefer replayable, inspectable systems over clever but opaque behavior.

## Current Status

Current stage: Stage 3A / 3A.5 complete for the validated baseline, with Stage 3B now working in a bounded manual-first form.

Repository status at time of writing:

- All four apps emit Stage 1 raw telemetry into `kjt_events`.
- Stage 1.5 manual telemetry QA has been completed across all four apps.
- Stage 1 event conventions are frozen in `STAGE1_EVENT_REFERENCE.md`.
- Stage 2 ingest is working with a persistent Playwright browser profile and DuckDB.
- Stage 2.5 analytical views are producing recommendation-ready learner state.
- A first deterministic next-session recommender baseline exists in `pipeline/recommend_next_session.py`.
- Recommendation handoffs can be delivered into the app environment through the persistent Playwright profile.
- All four apps can now consume an advisory handoff through an optional learner-started guided-session path.
- Guided-session outcomes flow back through the normal telemetry path via `intervention_id`.
- Whole-chain validation has been completed across `alphabet`, `matras`, `conjuncts`, and `words`.
- A lightweight local coach control layer now exists so real practice can refresh recommendations without dropping back into a terminal-only loop.
- Stage 3B now has a working reflective-layer scaffold that reads curated summaries, builds bounded prompts, supports offline manual ChatGPT reflection import, and can later call an API-backed model without replacing the deterministic baseline.

## Roadmap Overview

| Stage | Focus | Main Agentic AI Lesson | Primary Output |
| --- | --- | --- | --- |
| 0 | Task analysis and metrics | Define decisions before building the agent | Locked decision model and raw schema |
| 1 | App instrumentation | Telemetry design and event discipline | Valid raw event stream from all four apps |
| 1.5 | Telemetry QA | Reliability and schema validation | Verified event correctness and edge-case coverage |
| 2 | ETL to DuckDB | Browser/Python boundary design | Repeatable ingest pipeline with validation |
| 2.5 | Analytics baseline | Converting events into decision-ready signals | Queries and reports that explain learner state |
| 3A | Deterministic recommender | Rules before models | Rule-based baseline recommender |
| 3A.5 | Replay evaluation | Evaluate before intervening live | Offline scoring of recommendations on historical data |
| 3B | Reflective LLM layer | LLM as explainer, not oracle | Bounded LLM-assisted analysis and recommendation notes |
| 4 | In-session agent loop | Timing, action, and system coordination | Near-real-time perceive → reason → act loop |
| 5A | Bidirectional protocol | Apps as command-receptive environments | Explicit app-agent command interface |
| 5B | MCP wrapping | Tool interface standardization | MCP-exposed tools for the local agent stack |
| 5C | Enrichment and intervention evaluation | Closing the adaptive loop | Selective web/LLM enrichment with measured outcomes |

## Stage 0

Status: Complete

### Objective

Define what the agent is actually trying to decide, how success will be measured, and what telemetry is needed before implementation begins.

### Why This Stage Matters

Most weak agent systems fail because they start with tools or models instead of decisions. Stage 0 avoids that mistake by locking the task model first.

### Key Outputs

- Learner task taxonomy
- Agent decision targets
- Success metrics
- Failure mode taxonomy
- Session boundary rules
- Fatigue heuristic
- Stage 1 raw event schema

### Exit Criteria

- All target agent decisions are explicitly listed
- Raw schema fields are justified by downstream use
- Session boundary and fatigue logic are fixed for Stage 1

## Stage 1

Status: Complete

### Objective

Instrument all four apps so they emit raw attempt events into a shared event buffer with a consistent schema.

### Why This Stage Matters

This is the foundation for everything that follows. If the event stream is incomplete, inconsistent, or app-specific, every later stage becomes harder to trust.

### Deliverables

- Shared raw event schema implemented across `alphabet`, `matras`, `conjuncts`, and `words`
- Session IDs created at page load or session start, persisted in `sessionStorage`
- Append-only event log in `localStorage` using the common key
- Event emission on every scored learner attempt
- Handling of app-specific exceptions, especially the self-scored `words` flow

### Learning Outcomes

- Telemetry schema design
- Forward-compatible event modeling
- Separation of raw events from derived metrics
- Handling product differences without breaking a shared schema

### Risks

- Treating app-specific progress state as equivalent to a raw event log
- Inconsistent `item_id` patterns across apps
- Missing timing data or missing choices for multiple-choice apps
- Underspecified exceptions for self-scored sessions

### Exit Criteria

- Every app emits valid events that match the Stage 1 schema
- Events are inspectable in the browser and consistent across apps
- Required edge cases are covered: timeout, manual answer, self-score, new session, inactivity reset
- A short schema reference exists for future ETL work

## Stage 1.5

Status: Complete

### Objective

Add explicit telemetry QA before any ETL work begins.

### Why This Stage Matters

A broken ingest pipeline is frustrating. A broken ingest pipeline fed by unreliable events is much worse. This checkpoint makes Stage 2 tractable.

### Deliverables

- Event validation checklist per app
- Sample captured sessions from each app
- Schema conformance review
- Known limitations log

### Learning Outcomes

- Validation discipline
- Thinking in terms of observability and debuggability
- Detecting product edge cases before infrastructure hardens around them

### Exit Criteria

- Each app has at least one manually inspected sample session
- Event payloads are checked against the schema field-by-field
- Known gaps are documented and intentionally accepted or fixed

## Stage 2

Status: Complete

### Objective

Build the ETL path from browser events to DuckDB through Playwright, with validation and idempotent ingest behavior.

### Why This Stage Matters

This stage teaches one of the core agentic AI lessons: the system boundary between the acting environment and the reasoning environment matters more than the model.

### Deliverables

- Playwright script to read `kjt_events`
- Transform layer that normalizes and validates records
- DuckDB schema for raw events
- Ingest command or script that can be rerun safely
- Basic data quality checks

### Learning Outcomes

- Browser automation as infrastructure
- Data movement across boundaries
- Local analytical storage design
- Validation at ingest time

### Risks

- Coupling ingest logic too tightly to current browser UI details
- Letting raw and derived tables blur together
- Inability to rerun ingest safely

### Exit Criteria

- Events from all four apps can be ingested into DuckDB
- Duplicate ingest behavior is defined and controlled
- Invalid records are surfaced clearly
- Raw event table is queryable and stable

## Stage 2.5

Status: Complete

### Objective

Create the first decision-ready analytics layer before building any recommender.

### Why This Stage Matters

The agent should not make recommendations directly from intuition about raw logs. It should act on a small set of clearly defined learner-state signals.

### Deliverables

- Queries or views for weak items
- Confusion pair analysis
- Retention and recency indicators
- Fatigue-trigger session analysis
- Early cross-app transfer views where feasible

### Learning Outcomes

- Translating raw telemetry into operational features
- Understanding what information is genuinely decision-useful
- Designing analytical views that are human- and agent-readable

### Exit Criteria

- At least five stable analytical queries or views exist
- Outputs are interpretable without reading raw JSON events
- A human can explain how each query could support an agent decision

## Stage 3A

Status: Complete for first-pass baseline

### Objective

Build a deterministic recommender that selects next app, review items, and stop/continue suggestions using explicit rules.

### Why This Stage Matters

This stage establishes the baseline that every future LLM-assisted version must beat or at least justify.

### Deliverables

- Rule engine for next-session recommendations
- Rule engine for top-priority review items
- Recommendation output format that can be logged and evaluated
- App-facing handoff contract for future guided-session delivery

### Learning Outcomes

- Rule systems as agent cores
- Making decisions traceable and debuggable
- Turning analytics into actions

### Risks

- Hidden heuristics that are too hard to inspect later
- Rules that overfit early data volume
- Producing recommendations without logging why

### Exit Criteria

- Rules are explicit and versioned
- Recommendations include reasons or feature summaries
- Outputs can be compared against learner outcomes later
- A structured handoff contract exists and can be emitted consistently

## Stage 3A.5

Status: Complete for first-pass baseline

### Objective

Evaluate the deterministic recommender offline using replay before allowing it to affect live sessions.

### Why This Stage Matters

This stage is where the project shifts from "interesting automation" toward genuine agent evaluation.

### Deliverables

- Replay harness over historical session data
- Offline recommendation scoring framework
- Initial comparison metrics for intervention quality
- First guided-session evaluation views tied to `intervention_id`

### Learning Outcomes

- Counterfactual thinking
- Evaluation design in an agent setting
- Distinguishing plausible decisions from effective decisions

### Exit Criteria

- Historical sessions can be replayed through the rule engine
- Recommendation outputs are archived for comparison
- Guided sessions can be distinguished from normal sessions analytically
- At least one evaluation report exists with clear findings and limitations

## Stage 3B

Status: Working manual-first baseline

### Objective

Add a tightly bounded LLM layer for explanation, pattern recognition, and reflective support, not for unconstrained control.

### Why This Stage Matters

This stage teaches the right role for LLMs in agentic systems: they are best used where ambiguity is high and explanation matters, not as a replacement for clear logic.

### Deliverables

- Prompted analysis over derived learner summaries
- LLM-generated explanations for confusion patterns or suggested focus areas
- Optional proposal layer that can augment, but not silently replace, rule-based outputs
- Logged reflection history so deterministic and reflective outputs can be inspected together

### Learning Outcomes

- Prompt design around constrained context
- Using models for reflection rather than raw control
- Comparing symbolic and generative decision components

### Guardrails

- LLM never becomes the only decision path
- Inputs come from curated summaries, not uncontrolled raw logs
- Outputs are logged and attributable

### Exit Criteria

- LLM use is limited to named tasks
- A rule-only baseline still exists and remains runnable
- Comparative evaluation exists for at least one LLM-assisted workflow
- A manual or API-backed reflection can be logged against the same deterministic context for later inspection

## Stage 4

### Objective

Introduce a near-real-time, in-session agent loop that can perceive active learner behavior and make timing-sensitive decisions.

### Why This Stage Matters

This is the most operationally complex stage. It is where the project moves from batch intelligence to an acting agent.

### Deliverables

- Live or near-live session state feed
- Agent loop capable of perceiving, deciding, and issuing bounded actions
- Intervention timing rules
- Logging of every intervention and its observed aftermath

### Learning Outcomes

- Perceive → reason → act loop design
- Race conditions and timing control
- Choosing when an agent should not act

### Risks

- Prematurely making the product feel unstable or intrusive
- Interventions that are hard to evaluate because timing is not logged well
- Overcomplicating the loop before Stage 3 logic is mature

### Exit Criteria

- Live interventions are bounded and reversible
- Every intervention is logged with timing and rationale
- The system can run a full session without losing state or corrupting telemetry

## Stage 5A

### Objective

Define an explicit bidirectional protocol so apps can receive commands as well as emit telemetry.

### Why This Stage Matters

At this point the apps stop being passive data sources and become agent-operable environments.

### Deliverables

- Command schema for app actions
- App-side handlers for accepted commands
- Protocol documentation

### Learning Outcomes

- Tool design
- Interface contracts
- Safe action boundaries between agent and app

### Exit Criteria

- Commands are explicit, validated, and limited
- Apps reject unsupported or malformed commands safely
- Protocol is documented independently of implementation details

## Stage 5B

### Objective

Wrap the existing local tools and interfaces in MCP.

### Why This Stage Matters

MCP is valuable here as a standard way to expose capabilities, not as the source of intelligence itself.

### Deliverables

- MCP tools for data access, recommendations, and app control
- Tool descriptions with clear inputs and outputs
- Example end-to-end agent use of MCP interfaces

### Learning Outcomes

- Interface standardization
- Thinking of local capabilities as reusable tools
- Designing tools for agent consumption

### Exit Criteria

- Core local capabilities are accessible through MCP
- Tool boundaries are stable and documented
- Existing workflows still work without MCP if needed

## Stage 5C

### Objective

Introduce selective enrichment and explicit intervention evaluation to close the adaptive loop.

### Why This Stage Matters

This is where the system begins to combine local learner evidence with broader pedagogical context, but only in ways that can be evaluated.

### Deliverables

- Selective LLM or web-enriched explanations
- Logged intervention outcomes tied to `intervention_id`
- Evaluation reports comparing pre/post intervention behavior

### Learning Outcomes

- Contextual augmentation
- Causal caution in agent evaluation
- Judging whether richer context actually improves decisions

### Risks

- Adding enrichment that sounds smart but does not improve outcomes
- Pulling in noisy external context too early or too often
- Confusing explanatory quality with learning impact

### Exit Criteria

- Enriched interventions are sparse, intentional, and logged
- Outcome tracking exists for intervention effectiveness
- At least one measured comparison shows whether enrichment helped

## Recommended Working Order Right Now

The next practical sequence should be:

1. Use the validated first-pass chain as the baseline for recommender refinement.
2. Compare delivered focus items against what the guided session actually surfaced and how those attempts performed.
3. Refine the deterministic recommender only after the guided-session evaluation is readable.
4. Decide whether the current advisory handoff contract is close enough to become the real Stage 5A command interface.

This keeps the project aligned with the learning goal: measure the loop you already built before adding more autonomy.

## Definition of Success

The roadmap is successful if it produces:

- A fully instrumented suite of Kannada learning apps
- A reproducible local data pipeline
- A rule-based agent baseline with measurable behavior
- A carefully bounded LLM layer that adds value without replacing discipline
- A clear record of what helped the learner and what did not

The roadmap is also successful if it teaches the builder how to reason about agentic systems as architectures, not just prompts.
