# Sprint-006: Institutional Context Aware Evidence Weighting — Readiness

**Date:** 2026-07-25
**Status:** Readiness Analysis — No Implementation

---

## Objective

Determine whether Institutional Context should influence Evidence Weighting, given that it already influences Evidence Retrieval (Sprint-005).

---

## Prerequisites

| Prerequisite | Status |
|-------------|--------|
| FC-001 (Semantic Condition Matching) | ✅ Complete |
| Sprint-004 (Institutional Context Visibility) | ✅ Complete |
| Sprint-005 (Context-Aware Evidence Retrieval) | ✅ Validated |
| Baseline V2 (retrieval with context) | ✅ Approved |

---

## EvidenceWeighter Architecture

### Current factor model (5 factors, geometric mean)

The `EvidenceWeighter` computes five independent sub-factors per `Evidence` item, combined into a composite weight using geometric mean:

| Factor | Method | Measures | Source |
|--------|--------|----------|--------|
| Confidence | `_confidence_factor()` | Statistical reliability of the evidence's return estimate | `ev.confidence` |
| Sample size | `_sample_factor()` | Number of observations supporting the evidence | `ev.sample_count` |
| Provenance | `_provenance_factor()` | Whether the evidence has a verifiable creation record | `ev.provenance is not None` |
| Consistency | `_consistency_factor()` | Agreement with majority bias of same event type | `ev.bias`, `ev.event_type` |
| Recency | `_recency_factor()` | Age of the evidence (decay over time) | `ev.provenance.created_at` |

All factors are pure functions of their inputs, deterministic, and clamped to [0.0, 1.0]. The weighter has:

- **Zero access** to retriever similarity scores (`SituationMatch` is not available to the weighter)
- **Zero access** to query context (`OrchestrationContext` is not available to the weighter)
- **Zero reads** of `Evidence.metadata` (the metadata dict is never consulted by any weighting factor)

### Weight combining formula

```python
# default (geometric):
composite = (cf * sf * pf * cosf * rf) ** (1.0 / 5.0)
```

The geometric mean acts as a **soft AND**: any factor near zero drives the composite toward zero. A zero-confidence, zero-sample, zero-provenance evidence gets near-zero weight even if recency is perfect.

### Data flow

```
OrchestrationEngine.analyze():
  ┌─ Layer evidence (economic, temporal, causal, core) ─┐
  └─ EvidenceAggregator.merge() ── EvidenceCollection ──┘
       │
       ├── EvidenceWeighter.weigh(collection)
       │     → WeightedAggregate (weighted avg return, confidence, ESS)
       │     → WeightFactors per evidence (5 intrinsic factors only)
       │
       └── HistoricalSituationRetriever.retrieve(query, eq)
             → list[SituationMatch] (6 similarity dimensions)
             → stored in report.historical_matches (NOT used by weighter)
```

**Key insight: The retriever and weighter operate on completely separate data flows.** The weighter has no visibility into retrieval results or similarity scores. The retriever has no influence on weighting.

---

## Analysis

### 1. Where Institutional Context Belongs Inside Weighting

**Answer: It does NOT belong inside weighting.**

The weighter is designed as a **intrinsic quality scoring system** — every factor measures something about the evidence itself: how reliable is its confidence estimate? How many samples? Does it have provenance? Is it consistent with its peers? How recent is it?

Institutional context measures **query-evidence alignment** — how relevant is this evidence to the current question? This is fundamentally different from intrinsic quality. The retriever already handles this in a dedicated subsystem with its own similarity dimensions and weights.

Adding institutional context to weighting would create an **architectural mismatch**:
- The weighter would need access to query context (which it doesn't have)
- The weighter would duplicate logic already in the retriever
- The clean separation between "select evidence" (retriever) and "weigh evidence" (weighter) would be blurred

### 2. What Should Institutional Context Do?

| Option | Assessment |
|--------|-----------|
| **Increase weight** | Would amplify evidence that contextually matches. But the retriever already selected it — it's already in the collection. Increasing weight further creates double-counting. |
| **Decrease weight** | Would suppress evidence that contextually mismatches. But the retriever already suppressed or excluded it via `min_similarity`. Suppressing it again is redundant. |
| **Reject evidence** | This is what the retriever does (via geometric mean zeroing when ctx_sim=0.0). Rejection at weighting stage would be redundant — rejected evidence never reaches the weighter. |
| **Remain an independent similarity factor** | **This is the correct answer.** Institutional context operates effectively at the retrieval level as a 6th similarity dimension alongside condition, horizon, maturity, and temporal. It should remain there. |

**Verdict: Institutional Context should remain an independent similarity factor at the retrieval level** and NOT be promoted to a weighting factor.

### 3. Ownership Verification

| Component | File | Responsibility | Should change? |
|-----------|------|---------------|----------------|
| `HistoricalSituationRetriever` | `retrieval.py` | Institutional context as similarity dimension | ✅ Already owns it (Sprint-005) |
| `EvidenceWeighter` | `weighting.py` | Intrinsic evidence quality scoring | ❌ Should NOT change |
| `WeightConfig` | `weighting.py` | Weighting parameters | ❌ Should NOT change |
| `WeightFactors` | `weighting.py` | Per-evidence factor breakdown | ❌ Should NOT change |
| `WeightedAggregate` | `weighting.py` | Aggregated result | ❌ Should NOT change |

Ownership is correct. No transfer needed.

### 4. Deterministic Behavior

Institutional context as a weighting factor would be deterministic (Jaccard similarity on key-value pairs is a pure function). However, adding it is unnecessary — determinism is already preserved at the retrieval level.

### 5. Backward Compatibility

`WeightFactors` is a frozen dataclass with exactly 6 fields. Adding a 7th field would break all existing code that constructs or destructures `WeightFactors` tuples. `WeightConfig` is similarly frozen. Changes would cascade through 40+ test assertions and multiple production uses.

This is technically feasible but architecturally destructive — it would couple the weighter to query context for the first time.

### 6. Interaction with Retrieval (Double Counting)

This is the decisive analysis. The retriever and weighter currently interact as follows:

```
Retrieval path:
  SituationQuery.institutional_context
    → retriever._institutional_context_similarity(query.ctx, evidence.metadata.ctx)
    → scores[5] included in geometric mean
    → overall_similarity filtered by min_similarity
    → matches sorted by overall_similarity
    → top_k returned

Weighting path:
  (no institutional context involvement)
    → _confidence_factor(ev.confidence)
    → _sample_factor(ev.sample_count)
    → _provenance_factor(ev.provenance)
    → _consistency_factor(ev.bias, majority)
    → _recency_factor(ev.provenance.created_at)
    → geometric mean of 5 factors
    → composite_weight used for weighted averages
```

If institutional context were added to weighting, the pipeline would evaluate it twice:

```
Pass 1 (Retrieval):  context_sim = 1.0  →  helps evidence PASS min_similarity
Pass 2 (Weighting):  context_sim = 1.0  →  boosts composite_weight  →  more influence on decision
```

This is double-counting by design. The evidence benefits from context match TWICE: once to be selected, once to be amplified. While technically defensible (retrieval selects candidates, weighting ranks them), the practical concern is:

- **No evidence in the current pipeline has context_sim=0.0 at the weighting stage** — those are all excluded by the retriever's `min_similarity` threshold. The only evidence that reaches the weighter with context_sim < 1.0 is:
  - Legacy records with empty `institutional_context` → context_sim = 0.5 (neutral)
  - Records from the exact-match path where context isn't the differentiator
- This means adding context to weighting provides marginal value — it mostly affects records that already received neutral context scores.

**The double-counting concern is real but not critical.** The marginal value of a second evaluation is low, but the architectural cost (coupling weighter to query context, breaking field count invariants) is high.

---

## Recommendation

**REJECT** — Institutional Context should NOT be added to Evidence Weighting.

### Architectural justification

The EvidenceWeighter's five-factor model (confidence, sample, provenance, consistency, recency) measures **intrinsic evidence quality** — properties of the evidence itself that indicate how reliable it is regardless of the query. Institutional context is a **query-evidence alignment signal** — it measures how relevant the evidence is to the specific question being asked.

These two concerns are architecturally separated:

| Concern | System | Method |
|---------|--------|--------|
| Query-evidence alignment | `HistoricalSituationRetriever` | 6-dimension weighted geometric mean similarity |
| Evidence quality | `EvidenceWeighter` | 5-factor weighted geometric mean composite |

Adding query-evidence alignment to the weighter would:
1. **Break architectural separation** between retrieval (selection) and weighting (quality scoring)
2. **Introduce double-counting** — context influences selection AND weight, creating an implicit bonus for context-matching evidence that exceeds what either system independently intends
3. **Couple the weighter to query context** — it currently has no access to `SituationQuery` or `OrchestrationContext`
4. **Provide marginal value** — the retriever already excludes evidence with context_sim=0.0; the only records reaching the weighter with context_sim < 1.0 would be legacy records with empty context (neutral 0.5)
5. **Break backward compatibility** — `WeightFactors` is a frozen dataclass with fixed fields; adding a 7th field cascades through all construction sites and test assertions

Institutional Context is correctly positioned at the retrieval level as an independent similarity factor (Sprint-005). Evidence weighting should remain focused on intrinsic quality. The next step for institutional context deployment should be context-aware reasoning (Sprint-007), not context-aware weighting.
