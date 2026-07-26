# CER-008: Context-Aware Retrieval — Ownership Decision
**Status:** Ownership Decision  
**Authority:** Architecture Review  
**Date:** 2026-07-25  
**Question:** Should Institutional Context influence Evidence Retrieval?

---

## 1. Is Institutional Context Conceptually Part of Retrieval Semantics?

**Yes. It already is — partially and incorrectly.**

Institutional context (yield regime, macro regime, DXY) flows into `KnowledgeRecord.condition` and then `Evidence.condition` when `condition_columns` includes those fields. The production pipeline currently runs with `condition_columns = ("cpi_pressure", "us10y_level")` for enriched runs, embedding yield context directly into the condition dict.

Evidence retrieval operates on `condition` at two levels:

1. **EvidenceQuery.matching()** — performs exact key-value matching on the condition dict. This is fully context-aware. When a query specifies `{cpi_pressure: "high", us10y_level: "high_yield_regime"}`, only evidence with those exact values is returned. Institutional context already gates which evidence enters reasoning.

2. **HistoricalSituationRetriever._jaccard_similarity()** — compares condition dicts by **key names only**, ignoring values entirely (`retrieval.py:153–163`). A query for `{cpi_pressure: "high", us10y_level: "high_yield_regime"}` scores identically against evidence with `{cpi_pressure: "low", us10y_level: "low_yield_regime"}`. The retriever recognizes that both records describe the same *dimensions* but cannot distinguish between opposite *regimes*.

This is a semantic defect. The retriever's similarity model treats "high CPI during rising yields" as identical to "low CPI during falling yields." Institutional context is present in the data but invisible to similarity scoring.

**Conclusion:** Institutional context is already part of retrieval semantics at the exact-match level (EvidenceQuery). It is conceptually required at the similarity level (HistoricalSituationRetriever) but currently absent there. The concept belongs; the gap is in one method.

---

## 2. Would Context-Aware Retrieval Violate Current Ownership?

**No.**

Frozen Core per `PROJECT_NORTH_STAR.md §4`:
- Inference Pipeline
- Reasoning Engine
- Decision Engine
- Evidence Engine
- Knowledge Graph Contracts
- Core Entity Contracts
- Institutional Assessment
- Constitutional Rules

`HistoricalSituationRetriever` is **not frozen core.** It resides in `src/knowledge/reasoning/retrieval.py` under the reasoning package, but it is not the Reasoning Engine. The frozen boundary is `ReasoningEngine` (`engine.py`), not the entire `reasoning/` package.

Verified ownership chain (from CER-006 runtime trace, §3 Ownership Graph):
- **Created by:** OrchestrationContext (dead code; never instantiated in production)
- **Owned by:** Nobody (unreachable in production)
- **Invoked by:** OrchestrationEngine.analyze() (dead code)
- **Output consumed by:** OrchestrationReport.historical_matches (dead code)

The retriever has no production owner. No frozen component depends on it. Its public contract (`SituationQuery`, `SituationMatch`, `RetrievalConfig`) is consumed only by dead code paths.

Additionally:
- `SituationQuery` is owned by the retriever module, not by any frozen component.
- `RetrievalConfig` weights are owned by the retriever module.
- `EvidenceQuery` (which the retriever calls) is part of the Evidence Engine, but the retriever is a *consumer* of EvidenceQuery, not a *modifier*. Making the retriever context-aware changes how it *scores* results, not how EvidenceQuery *produces* them.

**Conclusion:** Modifying HistoricalSituationRetriever violates no frozen core boundary. The component is unfrozen, unowned, and unreachable in production.

---

## 3. If Retrieval Should Become Context-Aware, What Is the Smallest Architectural Increment?

The defect is isolated to one static method: `_jaccard_similarity()` (`retrieval.py:153–163`).

Current behavior:
```
keys_a = set(a.keys())
keys_b = set(b.keys())
intersection = keys_a & keys_b
```
This computes structural overlap (which dimensions exist) but discards semantic content (what values those dimensions hold).

**Smallest correct increment:** Replace key-only Jaccard with key-value Jaccard within the same method signature. The similarity between two condition dicts should reflect how many key-value pairs match, not merely how many key names overlap.

This change:
- Stays within `retrieval.py` (unfrozen)
- Does not modify `SituationQuery`, `SituationMatch`, or `RetrievalConfig` contracts
- Does not add a new similarity dimension or change the weight vector
- Does not modify `EvidenceQuery` (frozen)
- Does not modify `ReasoningEngine` (frozen)
- Does not require a new pipeline stage

The method signature, the scoring architecture, and the downstream contract all remain unchanged. Only the definition of "condition similarity" becomes semantically correct.

**What this does NOT include:** Activating the retriever in the production path. The retriever is currently dead code. Wiring it into InferencePipeline would require modifying frozen core and is a separate ownership question (addressed in CER-007/CER-007A). This decision covers only the internal correctness of the retriever's similarity model.

---

## 4. Does This Remain Deterministic?

**Yes.**

The current Jaccard computation is deterministic: `set(a.keys()) & set(b.keys())` produces the same result for the same inputs. Key-value Jaccard (`set(a.items()) & set(b.items())`) is equally deterministic. No randomness, no timestamp dependency, no hidden state.

The geometric mean aggregation (`_geometric_mean`), threshold filtering (`min_similarity`), and sort order (`overall_similarity` descending) are all unaffected. The only change is that the `condition_similarity` score for a given pair of dicts will now reflect value agreement, not just structural overlap. Same inputs will always produce the same score.

**Verified against North Star §3.2:** "The same inputs must always produce the same outputs. No hidden randomness. No hidden state. No time-dependent behavior." Key-value Jaccard satisfies all three constraints.

---

## 5. Does This Improve Institutional Reasoning Quality?

**Yes — at the retrieval level, when retrieval is activated.**

Current behavior (key-only Jaccard, verified at `retrieval.py:159–163`):

| Query Condition | Candidate A | Candidate B | Current Score |
|----------------|-------------|-------------|---------------|
| `{cpi_pressure: "high", us10y_level: "high_yield_regime"}` | `{cpi_pressure: "high", us10y_level: "high_yield_regime"}` | `{cpi_pressure: "low", us10y_level: "low_yield_regime"}` | **1.0 = 1.0** |

The retriever cannot distinguish an exact institutional match from a complete institutional mismatch. Any two records sharing the same dimension names score identically regardless of regime.

With key-value Jaccard:

| Query Condition | Candidate A | Candidate B | Corrected Score |
|----------------|-------------|-------------|-----------------|
| `{cpi_pressure: "high", us10y_level: "high_yield_regime"}` | `{cpi_pressure: "high", us10y_level: "high_yield_regime"}` | `{cpi_pressure: "low", us10y_level: "low_yield_regime"}` | **1.0 vs 0.0** |

The retriever would correctly rank exact regime matches above opposite-regime records. This is the definition of context-aware retrieval: historical situations are ranked by institutional similarity, not just structural similarity.

**Impact qualification:** This improvement is latent until the retriever is activated in the production path. The retriever is currently dead code. The improvement is real but deferred.

---

## Ownership Decision

**Context-aware retrieval is architecturally correct, ownership-safe, and should proceed as a single-method correction within the unfrozen retriever module.**

| Question | Answer |
|----------|--------|
| Conceptually part of retrieval? | Yes — already partially present; similarity scoring is the gap |
| Violates ownership? | No — retriever is unfrozen, unowned, unreachable |
| Smallest increment? | Key-value Jaccard replacing key-only Jaccard in `_jaccard_similarity()` |
| Deterministic? | Yes — set intersection on items is as deterministic as on keys |
| Improves reasoning quality? | Yes — eliminates false-positive similarity between opposite regimes |

**Scope boundary:** This decision authorizes correction of the similarity model within `retrieval.py`. It does not authorize activating the retriever in the production path, which would require a separate frozen-core governance decision per CER-007A Finding 1.
