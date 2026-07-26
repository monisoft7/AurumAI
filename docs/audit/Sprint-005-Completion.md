# Sprint-005: Context-Aware Evidence Retrieval — Completion

## Objective

Activate Institutional Context during historical evidence selection. `HistoricalSituationRetriever` now considers `institutional_context` as a 6th similarity dimension alongside event_type, condition, horizon, maturity, and temporal.

## Scope

Institutional Context influences: **historical evidence selection ONLY**.

Does NOT influence: evidence weighting, reasoning, confidence, decision, explanation.

## Architectural Owner

| Component | Change |
|-----------|--------|
| `HistoricalSituationRetriever` (retrieval.py) | 6th similarity dimension, new method, updated data structures |
| `OrchestrationContext` (context.py) | New `institutional_context` field |
| `OrchestrationEngine` (engine.py) | Passes `institutional_context` to `SituationQuery` |

## Files Changed

**Source (3 files):**

| File | Lines Changed | What Changed |
|------|--------------|--------------|
| `src/knowledge/reasoning/retrieval.py` | ~20 | `SituationQuery.institutional_context`, `SituationMatch.institutional_context_similarity`, `RetrievalConfig.institutional_context_weight` (+ weight rebalance), `_institutional_context_similarity()` method, `_compute_similarities()` 6-tuple return, `_geometric_mean()` 6-tuple signature, `retrieve()` unpacking |
| `src/knowledge/orchestration/context.py` | +1 | `institutional_context: dict[str, str] = field(default_factory=dict)` |
| `src/knowledge/orchestration/engine.py` | +1 | `institutional_context=ctx.institutional_context` in `SituationQuery()` construction |

**Tests (1 file):**

| File | Tests Added |
|------|-------------|
| `tests/test_retrieval.py` | 5 new tests in `TestInstitutionalContextRetrieval` class |

**Existing test adjustments:**
- `RetrievalConfig` defaults test: updated `condition_weight` (0.30→0.25), `horizon_weight` (0.15→0.10), added `institutional_context_weight` assertion
- Custom/test configs: `institutional_context_weight=0.0` added where 5 weights summed to 1.0
- `SituationQuery` tests: added `institutional_context` assertions

## Files NOT Modified

| File | Reason |
|------|--------|
| `ReasoningEngine` | Not responsible for retrieval |
| `EvidenceWeighter` | Out of scope |
| `KnowledgeRecord` | Already has institutional_context (Sprint-004) |
| `PipelineContext` | Inference pipeline doesn't use retriever |
| `InferencePipeline` | Uses EvidenceQuery directly, not the retriever |
| `EvidenceQuery` | Not involved in similarity computation |

## Implementation Details

### Weight rebalancing

```
Before:  et=0.35  cond=0.30  horiz=0.15  mat=0.10  temp=0.10
After:   et=0.35  cond=0.25  horiz=0.10  mat=0.10  temp=0.10  ctx=0.10
```

### Similarity computation

`_institutional_context_similarity(a, b)` uses the same Jaccard formula as `_jaccard_similarity()` — generic, operates on `set(a.items())` and `set(b.items())`. No reference to `macro_regime` or any specific context key.

Default: 0.5 when either dict is empty (matching the neutral convention from `_jaccard_similarity`).

### Evidence metadata access

Institutional context reaches the retriever via the orchestration path:

```
OrchestrationContext.institutional_context
  → SituationQuery.institutional_context
  → _compute_similarities()
  → _institutional_context_similarity(query.context, evidence.metadata["institutional_context"])
```

The `evidence.metadata` already contains `institutional_context` from Sprint-004 (KnowledgeRecord → GraphNode.properties → Evidence.metadata pipeline).

## Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| retrieval (including 5 new) | 65 | ✅ All pass |
| reasoning + forecast | 94 | ✅ All pass |
| decision | 119 | ✅ All pass |
| inference + news pipeline | 205 | ✅ All pass |
| lesson summary + builder | 40 | ✅ All pass |
| evidence + weighting | 40 | ✅ All pass |
| knowledge graph + integrity | 17 | ✅ All pass |
| orchestration | 13 | ✅ All pass |
| economic/causal/temporal intelligence | 75 | ✅ All pass |
| **Total** | **518** | **✅ All passing** |

## New Tests (5)

| Test | What It Verifies |
|------|------------------|
| `test_institutional_context_similarity` | Direct method: identical→1.0, different→0.0, partial→0.5, both empty→0.5, one empty→0.5 |
| `test_retrieval_with_institutional_context` | End-to-end: matching context evidence selected, non-matching context has 0.0 similarity and is deprioritized |
| `test_retrieval_with_empty_context` | Backward compat: empty query context → context_sim defaults to 0.5 |
| `test_institutional_context_in_evidence_metadata` | Verify context accessible from `evidence.metadata["institutional_context"]` as dict |
| `test_institutional_context_generic_no_regime_reference` | Verify `retrieval.py` source contains no `macro_regime`, `EXPANSION`, or `RECESSION` strings |

## Institutional Intelligence Delta

| Dimension | Before | After |
|-----------|--------|-------|
| Similarity dimensions | 5 (et, cond, horiz, mat, temp) | 6 (+ institutional context) |
| Context-aware retrieval | None | Jaccard on `institutional_context` dicts |
| Context influence | None | Can raise or lower overall similarity vs non-contextual evidence |
| Zero-context evidence | N/A | Neutral score (0.5) — does not penalize missing context |
| Generic implementation | N/A | No `macro_regime` references in retriever |

## IRL Progression

| IRL Level | Description | Status |
|-----------|-------------|--------|
| IRL 2 | Technology concept formulated | ✅ Macro Regime feature extraction |
| IRL 3 | Experimental proof of concept | ✅ Propagation (Sprint-003), visibility (Sprint-004) |
| IRL 3→4 | Component validation — retrieval | ✅ Sprint-005: retriever uses institutional context |
| IRL 4 | Component validation in lab | ⬜ Next: context-aware weighting (Sprint-006) |
| IRL 5 | System integration | ⬜ Context-aware reasoning (Sprint-007) |
