# Sprint-004: Institutional Context Consumption — Readiness

**Date:** 2026-07-25  
**Status:** Readiness Analysis — No Implementation  

---

## Context

Sprint-002 activated `MacroRegimeFeatureExtractor` as a global extractor.  
Sprint-003 propagated `macro_regime` (and future institutional context columns) into lesson dicts via `LessonBuilder._add_institutional_context()`.

However, **institutional context is present in lesson dicts but not yet consumed by any downstream component**. The consumption chain — retrieval, weighting, reasoning, and assessment — operates without awareness of institutional context.

This document analyzes each downstream component to determine what is needed for **generic** institutional context consumption.

---

## Consumption Chain Overview

```
LessonBuilder._add_institutional_context()
    → lesson dict includes "macro_regime": "EXPANSION"
        ↓
LessonSummaryAggregator.build()
    → groups by condition_columns; macro_regime NOT in default condition_columns
    → macro_regime is dropped / only in CSV, not in KnowledgeRecord
        ↓
KnowledgeRecord (frozen dataclass, no institutional_context field)
    → condition: dict[str,str] — does NOT include macro_regime
        ↓
GraphBuilder.build() → GraphNode (properties = full record dict)
        ↓
EvidenceQuery.matching() → Evidence
    → condition: same as KnowledgeRecord
    → metadata: dict(props) — contains full record dict (includes condition only)
        ↓
EvidenceWeighter.weigh() → WeightedAggregate
    → reads confidence, sample_count, bias, event_type, provenance.created_at
    → does NOT read condition, metadata, or any context field
        ↓
ReasoningEngine.reason() → ReasoningChain
    → steps reference evidence.condition, event_type, horizon_days
    → /no institutional context/
        ↓
DecisionEngine.decide() → Decision
    → /no institutional context/
```

**Key finding**: After Sprint-003, `macro_regime` exists in the lesson CSV but does **not** reach `KnowledgeRecord`, `Evidence`, `ReasoningChain`, or `Decision`. The `condition` dict used throughout these components only contains `condition_columns` (default: `("cpi_pressure",)`).

---

## Component Analysis

### 1. Evidence Retrieval

**Does it already read Institutional Context?**  
No. `EvidenceQuery.matching()` filters by exact match on `event_type`, `condition` (dict key-value pairs), and `horizon_days`. `HistoricalSituationRetriever` computes Jaccard similarity on condition keys and value match ratio. Neither is aware of `macro_regime` or any institutional context.

**If not, who should own the responsibility?**  
The retrieval layer is the **first consumer** in the chain. It should filter and rank evidence based on institutional context similarity. Two ownership models are possible:

- **Option A: EvidenceQuery** — Add institutional context as an additional filter dimension (exact match on context values). Minimal change, but does not support similarity.
- **Option B: HistoricalSituationRetrieval** — Add institutional context as a new similarity dimension in the multi-factor comparison. This is a natural fit since `RetrievalConfig` already models 5 similarity weights and `_compute_similarities()` is extendable.
- **Recommended: Option B** — HistoricalSituationRetriever is the correct owner because institutional context is a *similarity* concern, not an exact-match filter. EvidenceQuery should remain an exact-match pass-through.

**Is the missing capability wiring, extension, or new capability?**  
**Extension** — `HistoricalSituationRetriever` already has a multi-factor similarity architecture. Adding a 6th similarity dimension for institutional context requires:
- Add `institutional_context` field to `SituationQuery`
- Add `context_similarity` to `RetrievalConfig` (with default weight, e.g., 0.15)
- Add `_context_similarity()` to `HistoricalSituationRetriever`
- Normalize weights to sum to 1.0

**Smallest architectural increment:**  

| Step | Change | Risk |
|------|--------|------|
| 1 | Add `institutional_context: dict[str, str]` to `SituationQuery` | None — new field with default |
| 2 | Add `context_similarity_weight: float` to `RetrievalConfig` | None — new field with default 0 |
| 3 | Implement `_context_similarity(query, evidence)` → Jaccard on context dict values | Low — parallels existing `_condition_similarity` |
| 4 | Normalize weights and add to geometric mean | Low — existing pattern |

**Backward compatibility:**  
- `RetrievalConfig` defaults preserve existing behavior (context_weight=0.0)
- `SituationQuery` field defaults to empty dict
- Existing callers not passing `institutional_context` see no change
- Existing tests continue to pass unchanged

---

### 2. Evidence Weighting

**Does it already read Institutional Context?**  
No. `EvidenceWeighter._compute_factors()` reads five factors (confidence, sample, provenance, consistency, recency). None reference condition, metadata, or any context field.

**If not, who should own the responsibility?**  
`EvidenceWeighter` should own this because weight modulation by context is a *weighting concern*. The weight of an evidence item should increase when its historical institutional context matches the current query's context.

**Is the missing capability wiring, extension, or new capability?**  
**Extension** — Add a 6th factor `institutional_context_factor` to `EvidenceWeighter`:

- Add `context_weight: float` config field to `WeightConfig` (default 0.0 to preserve backward compat)
- Add `context_match_exponent: float` (controls sharpness of match penalty)
- Implement `_context_factor(query_context: dict, evidence_context: dict) -> float`:
  - 1.0 if all context keys match
  - `(matching_keys / total_keys) ** exponent` for partial match
  - 0.5 if no context available on either side

**Smallest architectural increment:**  

| Step | Change | Risk |
|------|--------|------|
| 1 | Add `context_weight` to `WeightConfig` (default 0.0) | None |
| 2 | Add `_context_factor()` to `EvidenceWeighter` | Low |
| 3 | Wire into `_compute_factors()` and `weigh()` as opt-in | Low |
| 4 | Pass query context through pipeline to weighter | Wiring |

**Backward compatibility:**  
- `context_weight=0.0` by default → existing behavior unchanged
- Factor only activates when caller provides query context
- Existing 143 tests continue to pass

**Important note on EvidenceWeighter interface:**  
Currently `weigh(collection, as_of=None)` does not accept query context. The interface must be extended to accept optional `query_context: dict[str, str] | None = None`. This is a backward-compatible extension (new optional parameter).

---

### 3. ReasoningChain

**Does it already read Institutional Context?**  
No. `ReasoningContext` has fields:
- `event_type: str`
- `condition: dict[str, str] | None`
- `horizon_days: int | None`
- `metadata: dict[str, Any]`

Neither `ReasoningContext` nor `ReasoningEngine.reason()` reads institutional context. The conclusion step (`_build_conclusion`) describes `context_desc` using only `event_type`, `condition`, and `horizon_days`.

**If not, who should own the responsibility?**  
`ReasoningContext` should carry the context, and `ReasoningEngine` should include it in the chain output. The reasoning chain is the *explanation layer* — institutional context should appear in step conclusions and chain metadata.

**Is the missing capability wiring, extension, or new capability?**  
**Extension + Wiring** — Two parts:

1. **ReasoningContext extension**: Add `institutional_context: dict[str, str] = field(default_factory=dict)` field
2. **ReasoningEngine extension**: Update `_build_conclusion()` to include institutional context in `context_desc` and `details`
3. **Pipeline wiring**: Pass `institutional_context` from `PipelineContext` → `ReasoningContext`

**Smallest architectural increment:**  

| Step | Change | Risk |
|------|--------|------|
| 1 | Add `institutional_context` to `ReasoningContext` | None — frozen dataclass, new field with default |
| 2 | Include in `_build_conclusion` context description | Low |
| 3 | Wire from pipeline context → ReasoningContext | Wiring |

**Backward compatibility:**  
- `ReasoningContext` frozen dataclass — adding a field with a default value is backward-compatible (existing construction sites continue to work)
- `_build_conclusion` only adds context to description when non-empty dict provided
- Existing tests continue to pass

---

### 4. Institutional Assessment (Decision)

**Does it already read Institutional Context?**  
No. `DecisionEngine.decide()` classifies purely on `avg_return`, `confidence`, and `evidence_count`. `DecisionContext` has `event_type` and `query` only. `Decision` has `context: DecisionContext` but not institutional context.

**If not, who should own the responsibility?**  
Two ownership models:

- **Option A: DecisionEngine** — Add institutional context as a factor in decision classification (e.g., adjust confidence threshold based on context — higher weight for matching regime, lower for mismatching).
- **Option B: DecisionContext + Decision** — Carry institutional context through so that decision consumers can use it, but do not modify classification logic.
- **Recommended: Option B first, Option A later.** The decision classification should remain simple. Institutional context should first be *present* in the decision record. Modifying classification thresholds by context is a separate optimization.

**Is the missing capability wiring, extension, or new capability?**  
**Extension** — Add institutional context to `DecisionContext` and propagate to `Decision`:

- Add `institutional_context: dict[str, str]` to `DecisionContext`
- Include in `Decision.metadata` when present

**Smallest architectural increment:**  

| Step | Change | Risk |
|------|--------|------|
| 1 | Add `institutional_context` to `DecisionContext` | None |
| 2 | Wire from pipeline context → DecisionContext | Wiring |
| 3 | Include in Decision.metadata | None |

**Backward compatibility:**  
- `DecisionContext` frozen dataclass — new field with default empty dict
- `Decision.metadata` already a dict; adding a key is backward-compatible
- Existing tests continue to pass

---

## Summary: Ownership and Increments

| Component | Owner | Missing Capability | Smallest Increment | Type |
|-----------|-------|--------------------|--------------------|------|
| Evidence Retrieval | `HistoricalSituationRetriever` | Context similarity dimension | Add `context_similarity` to 6-factor geometric mean (weight default 0.0) | Extension |
| Evidence Weighting | `EvidenceWeighter` | Context-match weight factor | Add `_context_factor()` and `context_weight` to WeightConfig (default 0.0) | Extension |
| ReasoningChain | `ReasoningContext` + `ReasoningEngine` | Context not present in chain | Add `institutional_context` to ReasoningContext; include in conclusion | Extension + Wiring |
| Institutional Assessment | `DecisionContext` | Context not present in decision | Add `institutional_context` to DecisionContext; propagate to Decision.metadata | Wiring |

---

## Required Precondition: KnowledgeRecord Must Carry Institutional Context

Before any downstream component can consume institutional context, **KnowledgeRecord must include it**. Currently, `LessonSummaryAggregator` groups by `condition_columns` (default: `("cpi_pressure",)`), and `macro_regime` is NOT in that tuple. The column exists in the lesson CSV but is dropped during aggregation.

### Gap

`LessonSummaryAggregator._load_lessons()` validates required columns and groups by `condition_columns`. `_summarize_group()` uses the `condition` dict only for grouping key and explanation. The `institutional_context` column is an independent dimension, not a grouping key — lessons under different regimes should NOT be grouped together.

### Solution

Institutional context must be **carried through** the aggregation without being a grouping key. Smallest increment:

1. Add `institutional_context: tuple[str, ...]` to `LessonSummaryConfig` (parallel to `LessonBuilderConfig.institutional_context`)
2. In `_load_lessons()`, validate that institutional context columns exist in the CSV (if configured)
3. In `_summarize_group()`, include `institutional_context: dict[str, str]` in the returned record dict, merging the institutional context values from the first lesson in the group (all rows in the group share the same condition, but they may span multiple regimes — the group represents the AVERAGE behavior, not a single regime)

**Important design decision**: The group may contain lessons from multiple institutional contexts (e.g., both EXPANSION and CONTRACTION regimes under `cpi_pressure=inflation_pressure_up`). The group's `institutional_context` should represent the **majority context** or **context distribution** within the group. Two approaches:

- **Approach A (recommended for Sprint-004)**: Store `institutional_context` as the **majority** value per key (mode of each context column across the group). Simple, deterministic.
- **Approach B (future)**: Store a context histogram for each key (e.g., `macro_regime: {"EXPANSION": 0.6, "CONTRACTION": 0.4}`). Richer but more complex.

**Approach A** is recommended for Sprint-004 because it:
- Adds no new data structures to KnowledgeRecord
- Requires only a single `majority_context` computation per group  
- Is purely additive (existing fields unchanged)
- Enables all 4 downstream consumption paths

---

## Implementation Order (for Sprint-004)

```
Phase 1: KnowledgeRecord carries institutional context
  1. LessonSummaryConfig.institutional_context
  2. _summarize_group() → majority context → record dict
  3. Ensure KnowledgeRecord.from_dict() accepts the field

Phase 2: EvidenceRetrieval uses context
  4. HistoricalSituationRetriever._context_similarity()
  5. RetrievalConfig.context_similarity_weight

Phase 3: EvidenceWeighting modulates by context
  6. EvidenceWeighter._context_factor()
  7. WeightConfig.context_weight
  8. Optional query_context parameter on weigh()

Phase 4: ReasoningChain carries context
  9. ReasoningContext.institutional_context
  10. ReasoningEngine._build_conclusion() includes context

Phase 5: Decision carries context
  11. DecisionContext.institutional_context
  12. Decision.metadata includes context
```

---

## Key Constraints

1. **Must remain generic** — No references to `macro_regime` in any retrieval/weighting/reasoning/decision code. Use `institutional_context` as the abstraction. The specific column names are configured in `LessonSummaryConfig.institutional_context` and `LessonBuilderConfig.institutional_context`.

2. **No modification to individual event classes** — CPIEvent, NFPEvent, GDPEvent, PPIEvent, PMIEvent, FOMCEvent, InterestRateEvent must not be modified.

3. **Backward compatibility** — All increments must be opt-in with default-disabled behavior. Zero existing tests should need modification.

4. **KnowledgeRecord is the single source of truth** — All downstream components consume institutional context through KnowledgeRecord → GraphNode → Evidence → ReasoningChain → Decision. Never read directly from lesson CSV.

---

## Files Requiring Change (Sprint-004)

| File | Phase | Change |
|------|-------|--------|
| `src/knowledge/lesson_summary.py` | 1 | Add `institutional_context` to config; carry through to record dict |
| `src/knowledge/integrity/knowledge_record.py` | 1 | Accept (optional) `institutional_context` field (or store in metadata) |
| `src/knowledge/reasoning/retrieval.py` | 2 | Add context similarity dimension |
| `src/knowledge/evidence/weighting.py` | 3 | Add context weight factor |
| `src/knowledge/reasoning/context.py` | 4 | Add `institutional_context` field |
| `src/knowledge/reasoning/engine.py` | 4 | Include context in conclusion |
| `src/knowledge/decision/context.py` | 5 | Add `institutional_context` field |
| `src/knowledge/decision/engine.py` | 5 | Propagate to Decision.metadata |
| `src/knowledge/pipeline/context.py` | 2–5 | Add `institutional_context` field for wiring |
| `src/knowledge/orchestration/context.py` | 2–5 | Add `institutional_context` field for wiring |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|----------|--------|------------|
| KnowledgeRecord needs schema change | High | Medium | Use `metadata` field as temporary carrier; schema update in separate increment |
| Grouping by condition_columns loses context granularity | High | Medium | Store majority context per group; docs note limitation |
| Weighting performance with 6 factors | Low | Low | Factor is O(n); single dict comparison per item |
| Feature extraction engine produces context after pipeline start | Low | Low | Macro_regime is per-row in event_data; computed before lesson building |
