# MEMORY

## Project Identity

AurumAI — Intelligence Core for macroeconomic event-driven trading knowledge.

## Architecture Overview

```
Source Data → Lessons → Knowledge Summary → Knowledge Graph
                                                     ↓
                                              Evidence Query
                                                     ↓
                                              Reasoning Chain
                                                     ↓
                                              Decision Engine
                                                     ↓
                                              Learning Engine
```

Plus three parallel Intelligence Layers:
- Economic (regime/state/cycle classification)
- Temporal (time indexing/querying)
- Causal (relation/hypothesis analysis)

Plus Knowledge Integrity:
- Provenance on every entity
- LineageRegistry for full traceability
- VersionedStore for append-only immutable history

## Current Sprint

Institutional Readiness — Production Hardening complete, Lineage activated in production.
Focus: OOS Validation (ADR-0004 Gate 6).

## Documentation Authority

This file is governed by the hierarchy defined in PROJECT_NORTH_STAR.md.
Priority: NORTH_STAR > CONSTITUTION > CURRENT_STATE > ROADMAP > PROJECT_STATUS > Historical docs.

## Key Decisions

- All core entities are frozen dataclasses (immutable by default)
- Provenance is an optional field (defaults to None) — no breaking changes
- LineageRegistry is in-memory, simple, and testable; optionally wired into InferencePipeline and OrchestrationEngine
- VersionedStore writes to disk as JSON files (v0001.json, v0002.json, ...); accepts optional `loader` factory for typed deserialization
- KnowledgeRecord is now a proper typed entity with `from_dict()` / `to_dict()` for explicit conversion
- GraphBuilder.build() accepts both `dict` and `KnowledgeRecord` objects
- The lesson repository uses CSV for bulk reads and JSON VersionedStore for individual versioned writes
- **OrchestrationEngine is an adapter pattern around InferencePipeline** — it runs intelligence layer adapters, aggregates evidence, then delegates reasoning and decision to the canonical InferencePipeline components (ReasoningEngine, DecisionEngine)
- **EvidenceQuery.matching(event_type, condition, horizon_days)** is the canonical evidence lookup, used by both InferencePipeline and OrchestrationEngine
- **INSUFFICIENT_EVIDENCE** is produced by the normal orchestration flow when evidence is absent
- **Lineage canonical path:** Decision → ReasoningChain → Evidence → KnowledgeRecord → Lesson → SourceData (traceable backward from any decision)
- **LineageRegistry now wired in production pipeline** (`stages.py` creates and passes it to `InferencePipeline.run()`)
- **Full reproducibility verified** — all IDs content-derived, no uuid4, RNG fixed seed 42

## Architecture Overview (Updated)

```
Event + Context
    ↓
┌─ OrchestrationEngine (adapter) ──────────────────┐
│  (optional) evaluate_policies() → filter+sort     │
│  Economic Layer ──→ EvidenceAdapter ──→ Evidence   │
│  Temporal Layer ──→ EvidenceAdapter ──→ Evidence   │
│  Causal Layer   ──→ relation→Evidence ─→ Evidence  │
│  Core KG        ──→ EvidenceQuery.matching() → Ev  │
└────────────────→ EvidenceAggregator ←─────────────┘
                         ↓
              EvidenceCollection (merged)
                         ↓
              ReasoningEngine (canonical)
                         ↓
              DecisionEngine (canonical)
```

## Key Design Decisions (Policy Engine)

- **LayerPolicy**: frozen dataclass with three fields — `layer_fn` (callable), `run_if` (predicate), `priority` (int). No base class, no registry, no DSL.
- **`evaluate_policies()`**: pure function — filter by `run_if(ctx)`, sort by `priority`. Deterministic, no side effects, only reads context.
- **Zero new dependencies**: uses existing `networkx` only transitively.

## Validation Summary

| Category | Status | Key Finding |
|---|---|---|
| 1. Evidence Quality | PASS | Uses all matching evidence, ignores non-matching |
| 2. Knowledge Consistency | PASS | Consistent records produce consistent decisions |
| 3. Temporal Consistency | WARNING | Comparison step groups by condition, not horizon_days |
| 4. Causal Consistency | PASS | Causal evidence internally consistent |
| 5. Cross-Layer Consistency | WARNING | Aggregator doesn't detect cross-layer conflicts (different IDs) |
| 6. Explainability Integrity | PASS | Full decision->chain->evidence->source trace verified |
| 7. Deterministic Behavior | PASS | Identical inputs produce identical outputs |
| 8. Traceability | PASS | Lineage records full path: decision to layer |
| 9. Insufficient Evidence | PASS | INSUFFICIENT_EVIDENCE reachable via normal orchestration flow (resolved) |
| 10. End-to-End | PASS | All layers + all step types + decision + lineage |

2 Findings documented (unfixed pending approval):
1. Temporal: comparison step ignores horizon differences within same condition group
2. Cross-Layer: aggregator misses conflicts across layers (ID-based dedup only)

## Test Status

1593 tests collected — 1591 functional (2 legacy scaffolded test files fail collection:
`test_dummy_event.py` and `test_test_event_event.py` reference removed scaffolding modules).
Exclude with `py -3 -m pytest -q --ignore=tests/test_dummy_event.py --ignore=tests/test_test_event_event.py`.
Full pass: 1537+ (verified).

## Lineage Chain (Complete + Production Active)

The canonical lineage path is traversable in both directions and now active in production:

```
Forward:  SourceData → Lesson → KnowledgeRecord → Evidence → ReasoningChain → Decision
Backward: Decision  → ReasoningChain → Evidence → KnowledgeRecord → Lesson → SourceData
```

Each hop uses `GENERATES` (builds-from) or `REFERENCES` (cited-by) relations. Both `LineageRegistry.trace()` (backward DFS) and `LineageRegistry.query()` (forward filter) work through the full chain.

## Next Steps

- **OOS Validation (Gate 6)**: Real CPI/US10Y expanding-window evaluation
- **Immutable Persistence (Gate 5)**: Atomic writes, content-addressed versions
- **CI Pipeline (Gate 7)**: Clean CI from fresh clone
