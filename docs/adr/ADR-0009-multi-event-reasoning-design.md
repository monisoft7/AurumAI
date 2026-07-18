# ADR-0009: Multi-Event Reasoning — Architecture Design

**Date:** 2026-07-17  
**Capability:** 13.3 — Multi-Event Reasoning  
**Status:** Implemented — 477 tests pass (27 new + 450 existing), zero regressions

---

## The 5 Questions

### 1. What already exists inside AurumAI that solves part of this?

**Almost all of the plumbing already exists.** The following components already support multi-event operation:

| Component | Already Supports | Gap |
|-----------|-----------------|-----|
| `Evidence` | `event_type` field — can hold evidence from CPI, NFP, DXY, etc. | None |
| `EvidenceCollection` | Can hold evidence from multiple event types | None |
| `EvidenceQuery` | `by_event_type()`, `all()` — queries across types | None |
| `EvidenceAggregator` | Merges collections from different layers, deduplicates by `evidence_id`, detects bias conflicts | None |
| `EvidenceRanker` | Composite scoring (confidence, sample count, return magnitude) | None |
| `KnowledgeGraph` | Stores nodes for all event types, edges link by type/condition/horizon | None |
| `GraphBuilder` | Creates edges across same event_type, condition, horizon | None |
| `ReasoningEngine` | Accepts `EvidenceCollection` with diverse `event_type` values; comparison step groups by `event_type` | Comparison is **within-event-type** only — no cross-event comparison |
| `OrchestrationEngine` | Runs economic, temporal, causal, core layers; merges via `EvidenceAggregator` | Takes single `event_type` in `OrchestrationContext` |
| `PolicyEngine` | `LayerPolicy` with `run_if` predicates, priority ordering | None |
| `EventRegistry` | Lists all registered event types | None |
| `FOMCCalendar` | FOMC meeting dates | Not yet integrated into reasoning |
| `DecisionEngine` | Produces decision from reasoning chain | None |

**Key finding:** The existing `ReasoningEngine.reason(evidence, context)` already accepts `EvidenceCollection` containing evidence from **any** event type. The comparison step (`_add_comparison_steps`) groups by `event_type` and compares conditions **within** each type. The gap is: there is no cross-event-type comparison (e.g., "CPI says gold positive but NFP says gold negative → conflict").

### 2. What can be reused from open source?

| Project | License | Activity | Verdict |
|---------|---------|----------|---------|
| **ERTool** (Peking Univ) | Open | 6 stars, limited | **Adapt algorithm idea only.** Evidential Reasoning (ER) algorithm for weighted belief fusion across multiple evidence sources. The concept of weighting evidence by reliability and combining belief masses is directly applicable to cross-event consensus detection. Too academic/general to use directly — we adapt the **weighted consensus idea** (not the code). |
| **FinHEAR** (EMNLP 2025) | Research | No public code | **Inspire pattern only.** Six-agent architecture (Historical Trend, Current Event, Human Expertise, Risk, Trading Decision, Refinement). The multi-agent orchestration pattern validates our architectural direction, but the implementation is GPT-4o-dependent and too heavy. |
| **TradingAgents** (AAAI 2025) | Apache 2.0 | 91k+ stars, very active | **Overengineered for this use case.** LangGraph-based multi-agent trading framework with LLM-dependent agents. We want deterministic, explainable, zero-LLM reasoning. Not a fit. |
| **K-Quant** | Apache 2.0 | 83 stars, moderate | **Different domain.** Stock-focused quantitative investment with knowledge-enhanced KBs, not macro/gold. Fusion module concept is high-level inspiration only. |
| **Graphiti (Zep)** | Apache 2.0 | Very active, 5.4k+ stars | **Too heavy.** Requires Neo4j/FalkorDB backend. Temporal knowledge graphs for AI agent memory. Our KnowledgeGraph already solves the graph layer. |
| **Microsoft GraphRAG** | MIT | Very active | **Different problem.** LLM-based RAG over private documents. Our domain is deterministic macro reasoning, not document retrieval. |
| **FinReflectKG** | Research | No public code | **KG-guided retrieval** concept is relevant but for S&P 100 filings QA, not macro event reasoning. |

**Summary:** No OSS project is directly copyable. The key reusable **idea** is Evidential Reasoning's weighted belief fusion — a mathematical approach to combining evidence from multiple sources with different reliability levels. We adapt the **consensus detection concept**, not code.

### 3. What should NOT be written from scratch?

**Nothing that already exists.** The following should be reused as-is (zero modifications):

- `Evidence` — universal data unit
- `EvidenceCollection` — container
- `EvidenceQuery` — `by_event_type()`, `all()`, `matching()`
- `EvidenceAggregator` — `merge(collections)`
- `EvidenceRanker` — `combined()`
- `ReasoningEngine` — `reason(evidence, context)` — **frozen, no modifications**
- `DecisionEngine` — `decide(chain, context)`
- `ReasoningChain` — chain data structure
- `ReasoningContext` — context for reasoning
- `Decision` — decision data structure
- `EventRegistry` — `list_events()`, `is_registered()`
- `KnowledgeGraph` — graph storage
- `OrchestrationEngine` — multi-layer fusion

### 4. What is the absolute minimum code required?

**3 new components, ~175 lines of production code:**

```
src/knowledge/reasoning/
  ├── cross_event.py              ← NEW: CrossEventAnalyzer (~80 lines)
  ├── multi_event.py              ← NEW: MultiEventReasoningOrchestrator (~80 lines)
  └── cross_event_result.py       ← NEW: CrossEventResult dataclass (~15 lines)
```

**New dataclass: `CrossEventResult`**
- `event_type_groups: dict[str, EvidenceCollection]` — evidence per event type
- `pairwise_agreements: list[AgreementPair]` — per-pair (CPI vs NFP, CPI vs DXY, etc.)
- `overall_consensus: str` — `"strong_agreement"`, `"agreement"`, `"mixed"`, `"conflict"`, `"insufficient"`
- `consensus_confidence: float` — [0, 1] confidence in the consensus
- `conflicts: list[str]` — descriptions of detected conflicts

**New class: `CrossEventAnalyzer`**
- `analyze(collections: dict[str, EvidenceCollection])` → `CrossEventResult`
- For each pair of event types, compares bias directions:
  - Both positive → agreement
  - Both negative → agreement
  - One positive, one negative → conflict
  - Mixed/neutral → mixed
- Weighs agreement by confidence and sample count
- Produces overall consensus assessment

**New class: `MultiEventReasoningOrchestrator`**
- Orchestrates: query → cross-analyze → reason → decide
- `reason(event_types, condition, horizon, query, evidence_query, reasoning_engine, decision_engine)` → `MultiEventResult`
- Steps:
  1. Query evidence for each event type via `EvidenceQuery.matching()`
  2. Run `CrossEventAnalyzer.analyze()` to detect cross-event patterns
  3. Merge all evidence into single `EvidenceCollection`
  4. Run existing `ReasoningEngine.reason(merged_evidence, context)` — produces chain with within-event comparisons
  5. Run existing `DecisionEngine.decide(chain, context)` — produces decision
  6. Return `MultiEventResult` containing cross-event analysis + chain + decision

### 5. Does this make AurumAI objectively smarter?

**YES.** Here is the before/after:

| Scenario | Before (Single Event) | After (Multi-Event) |
|----------|----------------------|---------------------|
| CPI: inflation up → gold positive | Decision: STRONG_POSITIVE | CPI agrees with NFP (jobs softening → gold positive), DXY stable → consensus: AGREE |
| CPI: inflation up → gold positive, DXY: dollar surging → gold negative | Decision: POSITIVE | Conflict detected: CPI says positive, DXY says negative → consensus: MIXED → more cautious decision |
| CPI: flat, NFP: weak, DXY: falling | Single-factor: INSUFFICIENT_EVIDENCE or NEUTRAL | Multiple weak signals converge → "gold positive on balance" |
| FOMC: hawkish, DXY: rising, US10Y: yields rising | Decision depends on which single factor is chosen | Cross-event confirms: ALL pointing gold-negative → STRONG_NEGATIVE with high confidence |

**Institutional research gold standard:** Real macro desks do exactly this — cross-reference CPI, NFP, DXY, yields, and FOMC calendar before making a call. This capability bridges the gap between single-factor academic backtesting and real-world institutional decision-making.

---

## Architectural Constraint (per review)

Cross-event reasoning was implemented as a **pure analysis component** plugging into the existing `OrchestrationEngine`. No new orchestrator, no parallel execution path, no duplication of orchestration responsibilities.

### Modified files

| File | Change | Lines Changed |
|------|--------|---------------|
| `src/knowledge/orchestration/context.py` | Added `event_types: tuple[str, ...] \| None` field | +1 |
| `src/knowledge/orchestration/engine.py` | Added `CrossEventAnalyzer` import, `cross_event_result` to report, multi-event `_run_core`, analyzer call after merge | +11 |

### Backward compatibility

When `event_types=None` (default), every component behaves exactly as before. The `event_type` field still controls the `ReasoningContext` and `DecisionContext`. The new field is purely additive.

## Final Architecture

```
                         MultiEventReasoningOrchestrator
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
           CPIEventQuery     NFPEventQuery     DXY+US10Y+FOMC
                    │               │               │
                    └───────────────┼───────────────┘
                                    ▼
                         EvidenceCollection
                         (all event types)
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
           CrossEventAnalyzer  ReasoningEngine  DecisionEngine
           (agreement/conflict) (within-event     (final decision)
                                 comparisons)
                    │               │               │
                    └───────────────┼───────────────┘
                                    ▼
                          MultiEventResult
              (cross_event_result + chain + decision)
```

### Data Flow

```
1. Orchestrator receives: event_types=["CPI", "NFP", "DXY", "FOMC"], condition={...}
2. For each event type, calls EvidenceQuery.matching(event_type, condition, horizon)
3. Merges results into dict[str, EvidenceCollection]
4. CrossEventAnalyzer.analyze(dict):
   - For each pair (CPI vs NFP, CPI vs DXY, ...):
     - Compare bias distributions
     - Compute agreement score
     - Detect conflicts
   - Aggregate pairwise into overall_consensus
5. Merge all collections into one EvidenceCollection (via EvidenceAggregator)
6. Feed to ReasoningEngine.reason(merged, context) → ReasoningChain
7. Feed chain to DecisionEngine.decide(chain) → Decision
8. Return MultiEventResult with all outputs
```

### Consensus Scoring

```
agreement_score(event_type_a, event_type_b):
  - Collect biases from all evidence in each group
  - Compute positive_ratio_a, positive_ratio_b
  - If both > 0.6 → agree (positive)
  - If both < 0.4 → agree (negative)
  - If one > 0.6 and one < 0.4 → conflict
  - Otherwise → mixed
  - Weight by average confidence of each group

overall_consensus:
  - Count pairwise agreements vs conflicts
  - If all pairs agree → strong_agreement
  - If majority agree → agreement
  - If equal agree/conflict → mixed
  - If majority conflict → conflict
  - If insufficient evidence (< 2 event types with data) → insufficient
```

---

## Files Created / Modified

| File | Lines | Purpose |
|------|-------|---------|
| `src/knowledge/reasoning/cross_event.py` | ~176 | `CrossEventResult`, `AgreementPair` dataclasses + `CrossEventAnalyzer` class |
| `tests/test_cross_event.py` | ~195 | 27 tests across 10 test classes |
| `src/knowledge/orchestration/context.py` | +1 | Added `event_types` field |
| `src/knowledge/orchestration/engine.py` | +11 | Multi-event `_run_core`, `CrossEventAnalyzer` call, report field |
| `docs/adr/ADR-0009-multi-event-reasoning-design.md` | This file | Design + implementation report |

**Total new production code:** ~176 lines (1 file)  
**Total new test code:** ~195 lines (1 file)  
**Modified existing files:** 2 (context.py +1 line, engine.py +11 lines)  
**Zero modifications** to Core Brain, InferencePipeline, ReasoningEngine, DecisionEngine, MacroEvent, or EventRegistry.

---

## Test Plan

| Test Class | Tests | Scope |
|-----------|-------|-------|
| `TestCrossEventResult` | 2 | Dataclass construction, frozen |
| `TestAgreementPair` | 2 | Pair agreement scoring |
| `TestCrossEventAnalyzer` | 6 | Agreement detection, conflict detection, mixed signals, single event type, empty, weighted confidence |
| `TestMultiEventOrchestrator` | 5 | Full multi-event reasoning, agreement consensus, conflict consensus, edge cases (single type, empty) |
| `TestIntegrationWithRealData` | 3 | Real evidence from multiple event types, CPI+NFP agreement, CPI+DXY conflict |

---

## OSS Candidates Summary

| Project | Stars | License | Status | Reuse Potential | Verdict |
|---------|-------|---------|--------|----------------|---------|
| ERTool (Peking Univ) | 6 | Open | Limited activity | **Medium** — weighted belief fusion algorithm concept | **Adapt idea** of weighted consensus, not code |
| FinHEAR (EMNLP 2025) | Research | Paper only | No public code | **Low** — multi-agent pattern inspiration | **Inspire architecture** |
| TradingAgents | 91k+ | Apache 2.0 | Very active | **None** — LLM/LangGraph heavy, different paradigm | **Skip** |
| K-Quant | 83 | Apache 2.0 | Moderate | **Low** — stock focus, fusion concept only | **Inspire** at high level |
| Graphiti (Zep) | 5.4k+ | Apache 2.0 | Very active | **Low** — requires graph DB backend | **Skip** |
| Microsoft GraphRAG | 18k+ | MIT | Very active | **None** — LLM-based document RAG | **Skip** |
| FinReflectKG | Research | Paper only | No public code | **None** — SEC filing QA, not macro | **Skip** |

---

## Future-Proofing

This design is purely additive and sits **above** Core v1.0. When future capabilities add:
- **FOMCEvent** — automatically included via `EventRegistry.list_events()`
- **GDPEvent, PPIEvent** — same pattern, zero code changes
- **New intelligence layers** — integrated through OrchestrationEngine
- The `CrossEventAnalyzer` is generic — it works with any future event type
