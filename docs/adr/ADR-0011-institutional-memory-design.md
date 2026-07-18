# ADR-0011: Institutional Memory & Analogical Reasoning

**Date:** 2026-07-17  
**Capability:** Sprint — Institutional Memory & Analogical Reasoning Research & Implementation  
**Status:** Design — pre-implementation

---

## Pre-Implementation Questions

### Q1: What memory/retrieval/reasoning capabilities does the codebase already have?

| Component | Capability | Limitation |
|-----------|-----------|------------|
| `Memory` | Simple JSON key-value store (`save`/`load`/`add`/`set_namespace`) | No search, no similarity, no retrieval beyond exact key lookup |
| `KnowledgeGraph` | NetworkX MultiDiGraph with `search_nodes()` by key/value, `get_neighbors()` by relation type, `get_relations()` by source/target/type | No similarity scoring, no ranking, no query-by-example |
| `EvidenceQuery` | Exact-match by `event_type`, `condition` (subset match), `horizon_days`; `related()` traverses graph edges | No partial matching, no broadened retrieval, no similarity ranking |
| `TemporalIndexer` | `nearest_date()`, `events_in_range()`, `rolling_window()` | Indexes `TemporalState` objects, not `KnowledgeRecord` or `Evidence` |
| `EvidenceRanker` | Score-based ranking (confidence×0.4 + samples×0.3 + magnitude×0.3) | Ranks within a single EvidenceCollection; no cross-situation comparison |
| `CrossEventAnalyzer` | Agreement scoring across event types | Operates on merged evidence; answers "do different event types agree?" not "is this situation historically familiar?" |
| `EvidenceWeighter` | Quality-weighted aggregation | Operates on current evidence; no historical lookup |
| `ReasoningContext` | Event type, condition, horizon_days metadata | Provides the query dimensions but no retrieval is performed on it |

**Finding**: AurumAI has all the necessary data structures (`Evidence`, `KnowledgeRecord`, `ReasoningContext`) and graph infrastructure, but lacks any component that *retrieves historically analogous situations* and scores them by structural similarity.

### Q2: What can be directly reused or minimally adapted?

| Component | Reuse as-is | Minor adaptation |
|-----------|-------------|-----------------|
| `EvidenceQuery.matching()` | Exact retrieval by event_type + condition + horizon | — |
| `EvidenceQuery.by_event_type()` | Broadened retrieval fallback | — |
| `EvidenceQuery.by_condition()` | Condition-based candidate expansion | — |
| `EvidenceQuery.related()` | Traverse `same_event_type`/`same_condition`/`same_horizon` edges | Could be used for "related situations" expansion |
| `KnowledgeGraph.get_relations()` | Discover event type relationships | — |
| `TemporalIndexer.nearest_date()` | Temporal proximity scoring | Used for temporal similarity (not indexing) |
| `ReasoningContext` | Query source (event_type, condition, horizon_days) | — |
| `Evidence.dataclass` | Uniform representation for similarity comparison | — |
| Weighted geometric mean pattern | From `EvidenceWeighter` — same composite pattern | — |

**Zero adaptation needed**: All reused components are called via their existing public APIs.

### Q3: What in the codebase must never be rewritten or replaced?

**Frozen (no modifications allowed)**:
- Core v1.0 (all modules under `src/knowledge/`)
- `Pipeline` (orchestration flow)
- `ReasoningEngine`
- `DecisionEngine`
- `EventRegistry`

**Recently completed (no modifications, additive-only)**:
- `EvidenceWeighter` + `WeightConfig` + `WeightFactors` + `WeightedAggregate`
- `CrossEventAnalyzer` + `CrossEventResult` + `AgreementPair`

**The retriever must be additive** — it reads from the Knowledge Graph via `EvidenceQuery` (frozen) and writes its results into the `OrchestrationReport` alongside existing fields. It never modifies graph state.

### Q4: What is the minimum new code required?

**One new file: `src/knowledge/reasoning/retrieval.py`** (~130 lines)

New dataclasses:
- `SituationQuery` — query parameters wrapped from `ReasoningContext`
- `SituationMatch` — scored result with per-component explainability
- `RetrievalConfig` — tunable weights and thresholds

New class:
- `HistoricalSituationRetriever` — stateless; `retrieve(query, graph) -> list[SituationMatch]`

Algorithm:
1. **Try exact retrieval**: `EvidenceQuery.matching(event_type, condition, horizon_days)` — returns same-context historical records
2. **If too few results**: broaden to `EvidenceQuery.by_event_type()` for same event type, wider net
3. **Score each candidate** across 5 dimensions (all [0,1]):
   - `event_type_similarity`: 1.0 for exact match, 0.0 otherwise
   - `condition_similarity`: Jaccard index on condition dict keys
   - `horizon_similarity`: `1 / (1 + |h_q - h_c| / max(|h_q|, |h_c|, 1))`
   - `maturity_similarity`: `sqrt(min(n_q, n_c) / max(n_q, n_c))`
   - `temporal_similarity`: `1 / (1 + years_diff)` (via TemporalIndexer)
4. **Aggregate**: Weighted geometric mean → overall similarity
5. **Return top-K** with full component breakdown

**Modifications to existing files**:
- `src/knowledge/orchestration/engine.py`: +4 lines (import + report field + call after cross_event)
- `src/knowledge/orchestration/context.py`: +1 field (`OrchestrationContext.retriever`)

**Tests**: `tests/test_retrieval.py` with ~30 tests.

### Q5: Does this move AurumAI toward institutional financial reasoning?

**Yes.** Institutional financial reasoning requires systematically answering "when has this happened before?" — the ability to identify historically analogous regimes is a hallmark of sophisticated macro analysis. This capability enables:

1. **Historical precedent detection**: "This FOMC hike with inflation at 3.5% looks structurally similar to June 2004"
2. **Regime-aware confidence calibration**: When strong analogues exist → higher confidence; when no analogues exist → reduced confidence (uncertainty flag)
3. **Explainable analogies**: Every top-K match shows *why* it was retrieved (component-level similarity scores)
4. **Zero infrastructure cost**: Uses existing Knowledge Graph and EvidenceQuery — no LLM, no vector DB, no external dependencies

---

## Design

### New File: `src/knowledge/reasoning/retrieval.py`

```
SituationQuery              — query dataclass (event_type, condition, horizon_days, date)
SituationMatch              — result dataclass (evidence, overall_similarity, per-component scores)
RetrievalConfig             — tunable parameters (top_k, min_similarity, broaden_on_empty, weights)
HistoricalSituationRetriever — main class; .retrieve(query, query, temporal_indexer) → list[SituationMatch]
```

### Similarity Scoring Details

| Dimension | Formula | [0,1]? | Purpose |
|-----------|---------|--------|---------|
| Event type | `1.0 if q.event_type == c.event_type else 0.0` | Yes | Same event = strong signal |
| Condition | Jaccard: `|keys(q) ∩ keys(c)| / |keys(q) ∪ keys(c)|` | Yes | Similar macro conditions |
| Horizon | `1 / (1 + |h_q - h_c| / max(|h_q|, |h_c|, 1))` | Yes | Similar lookahead windows |
| Maturity | `sqrt(min(n_q, n_c) / max(n_q, n_c))` | Yes | Comparable statistical power |
| Temporal | `1 / (1 + years_diff)` | Yes | Recency preference |

**Composite**: `overall = exp(sum(w_i * ln(s_i + eps)) / sum(w_i))` — weighted geometric mean. Any dimension at zero zeros the composite only if the relevant weight is non-zero.

### Retrieval Strategy

```
retrieve(query):
    1. candidates = query.matching(event_type, condition, horizon)  // exact
    2. if len(candidates) < min_results and broaden_on_empty:
         candidates += query.by_event_type(event_type)              // broadened
    3. for each candidate:
         scores = compute_all_similarities(query, candidate, temporal_indexer)
         overall = geometric_mean(scores, weights)
    4. filter: overall >= min_similarity
    5. sort desc by overall, return top_k
```

### Integration Point

In `OrchestrationEngine.analyze()`, after `CrossEventAnalyzer`:

```
EvidenceAggregator.merge(collections)
    ↓ merged EvidenceCollection [unchanged]
EvidenceWeighter.weigh(merged)
    ↓ WeightedAggregate [unchanged]
CrossEventAnalyzer.analyze(merged)     [if event_types set]
    ↓ CrossEventResult [unchanged]
HistoricalSituationRetriever.retrieve(query, evidence_query, temporal_indexer)  ← NEW
    ↓ list[SituationMatch] stored in report.historical_matches [NEW field]
ReasoningEngine.reason(merged, rctx)    [unchanged]
    ↓
DecisionEngine.decide(chain, dctx)      [unchanged]
```

The retriever is called after cross-event analysis but before reasoning. The historical matches are available to downstream consumers (reports, UI) but the existing reasoning/decision pipeline is unaffected — zero risk of regression.

### Modified Files

| File | Change | Impact |
|------|--------|--------|
| `src/knowledge/orchestration/context.py` | Add `retriever: HistoricalSituationRetriever \| None = None` | Optional field; default None |
| `src/knowledge/orchestration/engine.py` | Import retriever; add `report.historical_matches` field; call retriever after cross_event | +4 lines |

---

## Testing Strategy

### Scenarios

**A — Exact match retrieval**: Query for FOMC, condition={rate:"hike", inflation:"3.5"}, horizon=30 — returns existing knowledge record with same signature.

**B — Broadened retrieval**: Query for FOMC with rare condition that has no exact match — falls back to by_event_type, returns FOMC records with partial condition overlap.

**C — Similarity ranking**: Multiple candidates — the one matching on more dimensions ranks higher.

**D — Explainability**: Each match includes per-component scores; a match retrieved primarily for horizon similarity has a high horizon_similarity.

**E — Empty knowledge graph**: Returns empty list, no errors.

**F — No temporal_indexer**: Temporal similarity defaults to 0.5 (neutral), retrieval still works.

**G — Condition Jaccard**: Two matching condition keys out of four → condition_similarity = 0.5.

**H — Maturity bonus**: All else equal, a record with sample_count closer to the query's sample_count scores higher.

**I — Geometric mean damping**: A candidate with one zero dimension and four perfect dimensions scores lower than one with five medium dimensions.

**J — Integration**: retriever called from OrchestrationEngine after cross_event; matches stored in report.

### Tests

~30 tests covering:
- SituationQuery dataclass construction from ReasoningContext
- SituationMatch dataclass correctness
- RetrievalConfig defaults and custom parameters
- Individual similarity dimensions (event_type, condition, horizon, maturity, temporal)
- Geoemtric mean weight combination
- Weighted vs unweighted aggregation
- Exact retrieval branch
- Broadened retrieval fallback
- Empty graph
- No TemporalIndexer
- Edge cases: all identical, all different, single candidate
- Integration with OrchestrationEngine (historical_matches stored in report)

---

## Performance Impact

- Time: O(n * m) where n = graph nodes examined, m = similarity dimensions (fixed at 5)
- Memory: 1 `SituationMatch` per result (top_k, typically 5)
- Dependencies: zero new external dependencies (stdlib only)
- The retriever is a no-op when retriever is not configured on context

---

## Reuse Percentage

| Component | Lines | Source |
|-----------|-------|--------|
| `SituationQuery` | ~10 | Maps from `ReasoningContext` |
| `SituationMatch` | ~15 | Original design |
| `RetrievalConfig` | ~15 | Inspired by `WeightConfig` pattern |
| `HistoricalSituationRetriever` | ~90 | Original — Jaccard, geometric mean, retrieval algorithm |
| Tests | ~300 | Original scenarios |

**Reuse estimate: ~15%** (geometric mean pattern from EvidenceWeighter, Jaccard from stdlib, EvidenceQuery/EvidenceCollection APIs frozen). The module is overwhelmingly original code.
