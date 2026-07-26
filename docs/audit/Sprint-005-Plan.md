# Sprint-005: Context-Aware Evidence Retrieval — Plan

**Date:** 2026-07-25
**Status:** Planning — No Implementation

---

## Objective

Activate Institutional Context during historical evidence selection. The retriever must consider `KnowledgeRecord.institutional_context` when computing similarity between a query and candidate evidence — but **ONLY** for evidence selection, not for weighting, reasoning, confidence, decisions, or explanations.

---

## Constraints

| Constraint | Status |
|------------|--------|
| FC-001 (semantic condition matching) is complete | ✅ |
| Sprint-004 (Institutional Context visibility) is complete | ✅ |
| Institutional Context visible in KnowledgeRecord, Evidence.metadata, ReasoningContext, DecisionContext | ✅ |
| Must NOT influence evidence weighting, reasoning, confidence, decision, explanation | Strict |
| Must NOT reference `macro_regime` directly — operate only on `KnowledgeRecord.institutional_context` | Strict |
| Must preserve deterministic retrieval | Strict |
| Must preserve backward compatibility | Strict |
| Retrieval ownership unchanged (`src/knowledge/reasoning/retrieval.py`) | Strict |
| Must NOT modify ReasoningEngine | Strict |
| Must NOT modify EvidenceWeighter | Strict |

---

## Architectural Owner

| Component | Responsibility | Change? |
|-----------|---------------|---------|
| `HistoricalSituationRetriever` | Similarity computation & evidence selection | Add 6th dimension: institutional context |
| `OrchestrationContext` | Carries query-level context for orchestration | Add `institutional_context` field |
| `OrchestrationEngine` | Constructs `SituationQuery` and calls retriever | Pass institutional_context to query |
| `ReasoningEngine` | Reasoning over already-retrieved evidence | **No change** |
| `EvidenceWeighter` | Weighing already-retrieved evidence | **No change** |

---

## Execution Plan

### Step 1: Extend `SituationQuery` (retrieval.py)

Add `institutional_context: dict[str, str] = field(default_factory=dict)` — the query carries the current event's institutional context as a generic dict. No reference to `macro_regime`.

### Step 2: Extend `SituationMatch` (retrieval.py)

Add `institutional_context_similarity: float = 0.5` — records the similarity score for transparency. Default 0.5 matches neutral convention when no context is available.

### Step 3: Adjust `RetrievalConfig` weights (retrieval.py)

Current weights: `et=0.35, cond=0.30, horiz=0.15, mat=0.10, temp=0.10` (sum=1.0).

New weights: `et=0.35, cond=0.25, horiz=0.10, mat=0.10, temp=0.10, ctx=0.10` (sum=1.0).

Rationale:
- `event_type` remains the dominant factor (0.35)
- `condition` reduced slightly (0.30→0.25) — FC-001 already made condition more precise, slight reduction is safe
- `horizon` reduced (0.15→0.10) — horizon discrimination is coarse (typically 1/5/20 days)
- `institutional_context` enters at 0.10, equal to `maturity` and `temporal`
- No weight below 0.10, no single dimension dominates

### Step 4: Add `_institutional_context_similarity()` (retrieval.py)

```python
@staticmethod
def _institutional_context_similarity(
    a: dict[str, str], b: dict[str, str]
) -> float:
    if not a or not b:
        return 0.5
    keys_a = set(a.items())
    keys_b = set(b.items())
    intersection = keys_a & keys_b
    union = keys_a | keys_b
    return len(intersection) / len(union)
```

Same Jaccard formula as `_jaccard_similarity()` — generic, operates on key-value pairs. No reference to `macro_regime`.

### Step 5: Update `_compute_similarities()` (retrieval.py)

Return 6-tuple: `(et_sim, cond_sim, horizon_sim, maturity_sim, temporal_sim, context_sim)`.

The context similarity reads from `evidence.metadata`:
```python
evidence_ctx = evidence.metadata.get("institutional_context", {})
if isinstance(evidence_ctx, dict):
    ctx_sim = self._institutional_context_similarity(
        query.institutional_context, evidence_ctx
    )
else:
    ctx_sim = 0.5
```

### Step 6: Update `_geometric_mean()` signature (retrieval.py)

Accept 6 scores, 6 weights.

### Step 7: Update `retrieve()` (retrieval.py)

- Pass 6th score to SituationMatch
- Include `ctx_sim` in geometric mean
- Update `min_similarity` check (unchanged in value, just recomputed with new dimension)

### Step 8: Add `institutional_context` to `OrchestrationContext` (orchestration/context.py)

```python
institutional_context: dict[str, str] = field(default_factory=dict)
```

### Step 9: Wire `institutional_context` into `SituationQuery` (orchestration/engine.py)

```python
query = SituationQuery(
    event_type=ctx.event_type,
    condition=ctx.condition,
    horizon_days=ctx.horizon_days,
    date=ctx.date,
    institutional_context=ctx.institutional_context,
)
```

---

## Files Modified

| File | Change |
|------|--------|
| `src/knowledge/reasoning/retrieval.py` | 5 changes: SituationQuery field, SituationMatch field, RetrievalConfig weight, `_institutional_context_similarity()`, `_compute_similarities()` 6-tuple, `_geometric_mean()` 6-tuple, `retrieve()` unpacking |
| `src/knowledge/orchestration/context.py` | 1 change: `institutional_context` field |
| `src/knowledge/orchestration/engine.py` | 1 change: pass to SituationQuery |

---

## Files NOT Modified

| File | Reason |
|------|--------|
| `ReasoningEngine` | Not responsible for retrieval |
| `EvidenceWeighter` | Out of scope |
| `KnowledgeRecord` | Already has institutional_context (Sprint-004) |
| `PipelineContext` | Inference pipeline doesn't use retriever |
| `InferencePipeline` | Inference pipeline doesn't use retriever |
| `EvidenceQuery` | Not involved in similarity computation |

---

## Backward Compatibility

| Scenario | Before | After | Change? |
|----------|--------|-------|---------|
| No institutional_context in query or evidence | Sim = geometric mean of 5 dims | Sim = geometric mean of 6 dims (context=0.5 contributes neutrally) | Minimal — 0.5 in geometric mean shifts result slightly, but existing thresholds compensate |
| Empty dicts in both | N/A | context_sim = 0.5 | New |
| Query has context, evidence doesn't | N/A | context_sim = 0.5 | New |
| Same institutional_context | N/A | context_sim = 1.0 | New |
| Different institutional_context | N/A | context_sim = 0.0 | New |

For the weight shift (0.30→0.25 condition, 0.15→0.10 horizon), existing test scenarios without institutional context will see slight changes in overall similarity due to the rebalancing. The `min_similarity=0.3` and `top_k=5` thresholds absorb small fluctuations. Existing test assertions use deterministic inputs and should remain stable.

---

## Tests

### New tests (in `tests/test_retrieval.py`):

| Test | Purpose |
|------|---------|
| `test_institutional_context_similarity` | Direct test of `_institutional_context_similarity` — identical contexts → 1.0, different → 0.0, partial → <1.0, both empty → 0.5 |
| `test_retrieval_with_institutional_context` | End-to-end: query with context retrieves matching evidence over non-matching |
| `test_retrieval_with_empty_context` | Backward compatibility: empty context behaves same as baseline |
| `test_institutional_context_in_evidence_metadata` | Verify context is accessible from `evidence.metadata["institutional_context"]` |
| `test_institutional_context_generic_no_regime_reference` | Verify no string "macro_regime" appears in retrieval.py test setup |

### Existing tests:
All 60 existing retrieval tests must continue to pass without modification.

---

## Institutional Intelligence Delta

| Dimension | Before | After |
|-----------|--------|-------|
| Similarity dimensions | 5 (event, condition, horizon, maturity, temporal) | 6 (+ institutional context) |
| Context-awareness for retrieval | None | Jaccard on `institutional_context` dicts |
| Query carries context | No | Yes, via `SituationQuery.institutional_context` |
| Evidence metadata carries context | Yes (Sprint-004) | Yes — unchanged |
| Macro-regime referenced in code | Yes (LessonBuilder, LessonSummaryConfig defaults) | No — retriever is generic, operates on dicts only |

---

## IRL Progression

| IRL Level | Description | Status |
|-----------|-------------|--------|
| IRL 2 | Technology concept formulated | ✅ Macro Regime feature extraction (Sprint-002) |
| IRL 3 | Experimental proof of concept | ✅ LessonBuilder propagation (Sprint-003), visibility (Sprint-004) |
| **IRL 3→4** | **Component validation in lab** | **⬅ Sprint-005: retriever uses institutional context for evidence selection** |
| IRL 4 | Component validation in lab environment | Next: context-aware weighting (Sprint-006) |
| IRL 5 | System integration in relevant environment | Context-aware reasoning (Sprint-007) |
| IRL 6 | System demonstrated in relevant environment | Full pipeline with context-driven decisions |
| IRL 7 | System prototype demonstration in operational environment | Live or simulated market data |

Sprint-005 advances IRL from 3 to 3→4 by making Institutional Context operational — it now influences evidence selection, the first decision point in the retrieval pipeline.
