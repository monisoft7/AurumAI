# ADR-0004: Canonical Intelligence Inference Path

Status: Accepted

Date: 2026-07-16

## Context

AurumAI currently exposes two overlapping intelligence paths:

1. `EconomicBrain`, backed by flat `Memory` records and legacy `RULES` fallbacks.
2. `InferencePipeline`, backed by lessons, knowledge records, a knowledge graph,
   evidence, an explicit reasoning chain, and an advisory decision.

Allowing both paths to evolve as peers would violate the project constitution's
requirements for one responsibility per module, evidence-backed decisions, and
explicit migration of duplicate implementations.

## Decision

### Canonical path

`knowledge.pipeline.InferencePipeline` is the canonical entry point for all new
Intelligence Core behavior and for all future external consumers.

The canonical flow is:

`Event data -> Features -> Lessons -> Knowledge -> Graph -> Evidence -> Reasoning -> Decision`

A decision is valid only when it is produced by this path and references its
reasoning chain and evidence set.

### EconomicBrain migration status

`knowledge.brain.EconomicBrain`, `knowledge.memory.Memory`, and
`knowledge.rules.RULES` are classified as legacy compatibility components.

- They are not deleted in this sprint.
- They receive no new intelligence behavior.
- They are not injected into the canonical reasoning path.
- Their rule-based fallback is not accepted as evidence.
- Existing callers and tests remain supported until a dedicated migration ADR
  inventories callers and defines a removal or adapter plan.

### Temporary package boundaries

The existing `knowledge.reasoning`, `knowledge.decision`, and
`knowledge.learning` packages remain in place during stabilization. Moving them
into top-level packages now would create import churn without improving semantic
correctness.

No new implementation is added to the empty top-level `decision`, `agents`, or
`execution` directories during this sprint.

### Stabilization gates

The canonical path cannot be declared stable until all of the following pass:

1. ✅ **CLOSED** — Evidence is filtered by event type, condition, and requested horizon.
   `EvidenceQuery.matching(event_type, condition, horizon_days)` is now the canonical
   lookup in both `InferencePipeline._stage_query_evidence` and
   `OrchestrationEngine._run_core`. The old `by_condition`/`all` pattern is replaced.
2. ✅ **CLOSED** — Missing or sub-threshold evidence produces `INSUFFICIENT_EVIDENCE`
   in the normal orchestration flow. The `if len(merged) > 0` guard was removed from
   `OrchestrationEngine.analyze()`; empty evidence now reaches `DecisionEngine`,
   which returns `INSUFFICIENT_EVIDENCE` when `evidence_count < min_evidence_count`.
3. ✅ **CLOSED** — Optional pipeline stages (`compare_context`) are validated without
   corrupting stage order by `PipelineValidator`.
4. ❌ **OPEN** — Every knowledge record identifies its source lessons and source artifact.
5. ❌ **OPEN** — Persisted artifacts are written atomically and preserved as immutable,
   content-addressed versions while current compatibility paths remain usable.
6. ❌ **OPEN** — CPI/US10Y context is evaluated out of sample on real local history
   before DXY is added.
7. ❌ **OPEN** — The documented test command succeeds in a clean environment and CI.

## Related Canonical Documents

- [Project Constitution](../PROJECT_CONSTITUTION.md) — highest authority in the
  repository. Sections 5 (Non-Negotiable Rules), 9 (Architecture Principles),
  and 10 (Decision Principles) govern the canonical path.
- [PROJECT_IDENTITY.md](../../PROJECT_IDENTITY.md) — original CTO decision
  record; defers to Constitution on any conflict.
- [ROADMAP.md](../../ROADMAP.md) — live roadmap. This ADR's stabilization gates
  are tracked as Phase 12 items.
- [PROJECT_STATUS.md](../../PROJECT_STATUS.md) — current project status and
  version history.
- [Architecture: Knowledge Engine](../architecture/knowledge_engine.md) — living
  architecture description of the canonical inference flow.

## Consequences

### Positive

- One auditable path owns intelligence semantics.
- Future event types and agents integrate against one stable contract.
- Legacy behavior remains available without silently influencing evidence.
- Package relocation is deferred until it has a measurable benefit.

### Negative

- Existing direct `EconomicBrain` consumers remain on a deprecated behavior
  until their migration is planned.
- `PipelineContext` remains the required explicit configuration boundary.
- Stabilization work takes precedence over DXY, agents, and backtesting.

## Deferred

- DXY context.
- Multi-agent orchestration.
- Neo4j or another graph backend.
- Backtesting, paper trading, and execution.
- Physical relocation of reasoning/decision/learning packages.
