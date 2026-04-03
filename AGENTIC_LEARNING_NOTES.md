# KALS As An Agentic AI Learning Project

This note explains what KALS is teaching about agentic AI, using the code and documents in this repo rather than abstract theory alone.

## Why KALS Is Agentic AI Practice

KALS is not just "an app with an LLM." It is a control system around a real learning environment.

The learning apps are the environment:

- [alphabet/index.html](/Users/ardhendupathak/Documents/GitHub/KALS_dev/alphabet/index.html)
- [matras/index.html](/Users/ardhendupathak/Documents/GitHub/KALS_dev/matras/index.html)
- [conjuncts/index.html](/Users/ardhendupathak/Documents/GitHub/KALS_dev/conjuncts/index.html)
- [words/index.html](/Users/ardhendupathak/Documents/GitHub/KALS_dev/words/index.html)

The agentic system sits around them:

- telemetry
- analytics
- recommendation
- delivery
- guided-session evaluation
- reflection

That makes KALS a good project for learning agentic AI because it teaches how to build a loop, not just how to call a model.

## A Useful Framework

KALS maps cleanly to:

1. Perceive
2. Reason
3. Act
4. Observe
5. Evaluate

This is a better fit than thinking only in terms of "prompting."

## Perceive

The system first needs to sense what the learner is doing.

Where this exists in KALS:

- raw telemetry emitted from all four apps into `kjt_events`
- frozen event contract in [STAGE1_EVENT_REFERENCE.md](/Users/ardhendupathak/Documents/GitHub/KALS_dev/STAGE1_EVENT_REFERENCE.md)
- Stage 1 checklist in [STAGE1_CHECKLIST.md](/Users/ardhendupathak/Documents/GitHub/KALS_dev/STAGE1_CHECKLIST.md)

What this teaches:

- state must be observable
- schema discipline matters
- the agent cannot reason well if the environment is not instrumented well

In KALS terms, "perception" includes:

- item shown
- right or wrong result
- response time
- distractor context
- session boundaries
- guided intervention identifiers
- session-complete signals

## Reason

Once the system perceives events, it has to turn them into decision-ready state.

Where this exists in KALS:

- ingest pipeline in [pipeline/ingest_events.py](/Users/ardhendupathak/Documents/GitHub/KALS_dev/pipeline/ingest_events.py)
- DuckDB schema in [data/schema.sql](/Users/ardhendupathak/Documents/GitHub/KALS_dev/data/schema.sql)
- analytical views in [data/analytics_views.sql](/Users/ardhendupathak/Documents/GitHub/KALS_dev/data/analytics_views.sql)
- insight script in [pipeline/query_insights.py](/Users/ardhendupathak/Documents/GitHub/KALS_dev/pipeline/query_insights.py)

What this teaches:

- memory is not just storage, it is structured state
- raw logs are not enough; agents need derived features
- decision quality depends heavily on the shape of the analytical layer

In KALS, reasoning currently happens in two layers:

- deterministic analytical views and scoring
- bounded reflective interpretation in Stage 3B

## Act

A real agent must be able to do something bounded in the environment.

Where this exists in KALS:

- recommender core in [pipeline/recommendation_logic.py](/Users/ardhendupathak/Documents/GitHub/KALS_dev/pipeline/recommendation_logic.py)
- recommender runner in [pipeline/recommend_next_session.py](/Users/ardhendupathak/Documents/GitHub/KALS_dev/pipeline/recommend_next_session.py)
- handoff delivery in [pipeline/deliver_recommendation_handoff.py](/Users/ardhendupathak/Documents/GitHub/KALS_dev/pipeline/deliver_recommendation_handoff.py)
- coach hub in [coach/index.html](/Users/ardhendupathak/Documents/GitHub/KALS_dev/coach/index.html)

What this teaches:

- actions should be explicit and inspectable
- the first useful agent actions are often advisory, not fully autonomous
- command contracts matter

In KALS, the system acts by:

- recommending the next app
- choosing a session size
- identifying focus items
- delivering an advisory handoff
- surfacing that handoff through the coach and app UI

## Observe

After an action, the system must observe what happened next.

Where this exists in KALS:

- guided sessions tagged with `intervention_id`
- guided-session views in [data/analytics_views.sql](/Users/ardhendupathak/Documents/GitHub/KALS_dev/data/analytics_views.sql)
- guided-session evaluation in [pipeline/evaluate_guided_sessions.py](/Users/ardhendupathak/Documents/GitHub/KALS_dev/pipeline/evaluate_guided_sessions.py)
- chain validation in [pipeline/check_chain_validation.py](/Users/ardhendupathak/Documents/GitHub/KALS_dev/pipeline/check_chain_validation.py)

What this teaches:

- actions are only meaningful if their aftermath is measurable
- intervention logging is essential
- agent systems need attribution, not just output

This is one of the strongest agentic lessons in KALS:

the system does not merely recommend; it can later ask whether that recommendation was surfaced, followed, and useful.

## Evaluate

An agent is not trustworthy just because it produces plausible outputs.

Where this exists in KALS:

- replay evaluation in [pipeline/replay_evaluate.py](/Users/ardhendupathak/Documents/GitHub/KALS_dev/pipeline/replay_evaluate.py)
- guided-vs-normal comparison views in [data/analytics_views.sql](/Users/ardhendupathak/Documents/GitHub/KALS_dev/data/analytics_views.sql)
- progress snapshots in [PROGRESS_LOG.md](/Users/ardhendupathak/Documents/GitHub/KALS_dev/PROGRESS_LOG.md)

What this teaches:

- evaluate before trusting live intervention logic
- compare baseline decisions to actual outcomes
- distinguish "sounds smart" from "helps the learner"

This is core agentic engineering:

- you need a loop
- you need attribution
- you need evaluation

## How The Roadmap Teaches Agentic AI

The roadmap itself is a curriculum:

- [ROADMAP.md](/Users/ardhendupathak/Documents/GitHub/KALS_dev/ROADMAP.md)

Stage by stage:

### Stage 0

Defines decisions before implementation.

Agent lesson:

- do not start with tools or models
- start with the decision surface

### Stage 1 / 1.5

Builds and validates perception.

Agent lesson:

- sensing and observability come first

### Stage 2 / 2.5

Builds memory and learner state.

Agent lesson:

- agents need structured internal state, not just event logs

### Stage 3A / 3A.5

Builds and evaluates a deterministic policy.

Agent lesson:

- rules are a baseline
- replay matters
- intervention must be measurable

### Stage 3B

Adds bounded reflection.

Where this exists:

- [pipeline/reflect_recommendation.py](/Users/ardhendupathak/Documents/GitHub/KALS_dev/pipeline/reflect_recommendation.py)
- [pipeline/reflection_logic.py](/Users/ardhendupathak/Documents/GitHub/KALS_dev/pipeline/reflection_logic.py)
- [pipeline/import_manual_reflection.py](/Users/ardhendupathak/Documents/GitHub/KALS_dev/pipeline/import_manual_reflection.py)

Agent lesson:

- LLMs are best used first as explainers, critics, or reflective aids
- not as the only controller

### Stage 4

Starts the live loop.

Where this exists now:

- session-complete event emission from apps
- coach auto-refresh behavior
- local control plane in [pipeline/coach_control_server.py](/Users/ardhendupathak/Documents/GitHub/KALS_dev/pipeline/coach_control_server.py)
- combined startup in [pipeline/start_coach_practice.py](/Users/ardhendupathak/Documents/GitHub/KALS_dev/pipeline/start_coach_practice.py)

Agent lesson:

- timing and coordination become the real challenge
- the system now behaves like an operating loop, not just a batch analytics tool

## Why This Is Better Than A Toy Agent Demo

Many agent demos skip the hard parts.

KALS does not. It includes:

- real environment boundaries
- persistent learner state
- command delivery
- feedback from actions
- offline evaluation
- bounded reflection
- human-in-the-loop control

That makes it a better way to learn agentic AI development than building a chatbot that only talks.

## Current Best Interpretation

At this point, KALS is teaching:

- how to build an agent around a product surface
- how to separate telemetry, analytics, policy, and reflection
- how to validate a full control loop before chasing sophistication
- how to keep the learner experience advisory and reversible while the system matures

## What To Watch For Later

Some of the deeper agentic lessons are still ahead:

- cross-app concept modeling
- richer teacher-like explanations
- local or API-backed reflective models
- more direct bidirectional app-agent protocols
- selective enrichment and more nuanced interventions

Those are future layers on top of a solid base, not substitutes for it.

## One-Sentence Summary

KALS teaches agentic AI as systems design:

perceive the learner, reason over structured state, act through bounded handoffs, observe the outcome, and evaluate whether the loop genuinely helps.
