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

Project Stabilization — test suite green, dead code removed, unused imports cleaned, documents synchronized, formatting verified.

## Key Decisions

- All core entities are frozen dataclasses (immutable by default)
- Provenance is an optional field (defaults to None) — no breaking changes
- Provenance serialize/deserialize centralized in `provenance.py` (not duplicated in repos)
- LineageRegistry is in-memory, simple, and testable; optionally wired into InferencePipeline and OrchestrationEngine
- VersionedStore writes to disk as JSON files (v0001.json, v0002.json, ...); accepts optional `loader` factory for typed deserialization
- KnowledgeRecord is now a proper typed entity with `from_dict()` / `to_dict()` for explicit conversion
- GraphBuilder.build() accepts both `dict` and `KnowledgeRecord` objects
- SourceData entity exists but is not yet wired into the pipeline
- The lesson repository uses CSV for bulk reads and JSON VersionedStore for individual versioned writes
- **OrchestrationEngine is an adapter pattern around InferencePipeline** — it runs intelligence layer adapters, aggregates evidence, then delegates reasoning and decision to the canonical InferencePipeline components (ReasoningEngine, DecisionEngine)
- **Zero external dependencies added** — reuses existing Evidence bridge and Pipeline pattern
- **EvidenceQuery.matching(event_type, condition, horizon_days)** is the canonical evidence lookup, used by both InferencePipeline and OrchestrationEngine
- **INSUFFICIENT_EVIDENCE** is produced by the normal orchestration flow when evidence is absent
- **Lineage canonical path:** Decision → ReasoningChain → Evidence → KnowledgeRecord → Lesson → SourceData (traceable backward from any decision)

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
- **Engine integration**: `analyze()` accepts optional `policies`. When `None` (default) → original 4-layer hardcoded path (zero breakage). When provided → policy-driven execution, aggregation, reasoning, decision all identical.
- **Testability**: policies take callables so tests can inject mock layers. Conditions are pure predicates — fully testable in isolation.
- **Zero new dependencies**: uses existing `networkx` only transitively (not directly needed by policy.py).
- **Standing principle**: every sprint passes the question "does this make AurumAI smarter or just more complex?" — the policy engine is ~25 lines of new code providing adaptive layer selection.

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

786 tests total — all passing (100%)

## Lineage Chain (Complete)

The canonical lineage path is now traversable in both directions:

```
Forward:  SourceData → Lesson → KnowledgeRecord → Evidence → ReasoningChain → Decision
Backward: Decision  → ReasoningChain → Evidence → KnowledgeRecord → Lesson → SourceData
```

Each hop uses `GENERATES` (builds-from) or `REFERENCES` (cited-by) relations. Both `LineageRegistry.trace()` (backward DFS) and `LineageRegistry.query()` (forward filter) work through the full chain.

## Next Steps

Remaining ADR-0004 gates (4–7) deferred:
- Gate 4: Every knowledge record identifies source lessons + source artifact
- Gate 5: Atomic, immutable content-addressed persistence
- Gate 6: Real CPI/US10Y out-of-sample evaluation
- Gate 7: Clean CI test pass
