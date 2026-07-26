# Validation-001: Context-Aware Evidence Retrieval

**Date:** 2026-07-25
**Status:** Validation Design — No Implementation

---

## Objective

Validate that Sprint-005's 6th similarity dimension (`institutional_context`) improves retrieval quality. Determine whether Institutional Context correctly favors matching-context evidence over mismatching-context evidence, eliminates false historical analogies, preserves determinism, and is ready to become the new retrieval baseline.

---

## Method

Use the **in-process retrieval pattern** (same approach as EXP-002's direct retriever/query usage — see `scripts/run_experiment_002.py`). No experiment framework, no OOS engine, no pipeline — only:

1. `GraphBuilder.build()` to create a KnowledgeGraph from controlled KnowledgeRecords
2. `EvidenceQuery(graph)` to query evidence from the graph
3. `HistoricalSituationRetriever.retrieve()` to compute similarity and rank matches
4. Direct inspection of `SituationMatch` fields

This is deterministic (pure functions on known inputs), uses zero new infrastructure, and isolates the retriever behavior from other pipeline stages.

---

## Knowledge Graph Fixture

Create 6 KnowledgeRecords with varied conditions and institutional contexts, all stored in a single graph:

| ID | Event Type | Condition | Inst. Context | Horizon | Sample | Date | Avg Return |
|----|-----------|-----------|--------------|---------|--------|------|-----------|
| kr_1 | CPI | cpi_pressure=high | regime=EXPANSION, vol=LOW | 5 | 100 | 2025-06-01 | 0.8 |
| kr_2 | CPI | cpi_pressure=high | regime=RECESSION, vol=HIGH | 5 | 100 | 2025-06-01 | 0.5 |
| kr_3 | CPI | cpi_pressure=high | regime=EXPANSION, vol=LOW | 5 | 100 | 2025-06-01 | -0.2 |
| kr_4 | CPI | cpi_pressure=low | regime=EXPANSION, vol=LOW | 5 | 100 | 2025-06-01 | 0.3 |
| kr_5 | CPI | cpi_pressure=low | regime=RECESSION, vol=HIGH | 5 | 100 | 2025-06-01 | 0.1 |
| kr_6 | CPI | cpi_pressure=high | (empty dict) | 5 | 100 | 2025-06-01 | 0.6 |

Rationale:
- kr_1 and kr_3 share condition AND context — tests identical condition + identical context
- kr_2 has same condition but opposite context — tests identical condition + different context
- kr_4 has different condition but same context — tests different condition + identical context
- kr_5 has different condition AND different context — tests both different
- kr_6 has no institutional context — tests backward compatibility with legacy records

All records share `event_type=CPI`, `horizon_days=5`, `sample_count=100`, same date — so event_type, horizon, maturity, and temporal dimensions are neutral between matches. This isolates condition and institutional_context as the differentiating dimensions.

---

## Scenario 1: Identical Condition + Identical Institutional Context

**Query:** `event_type=CPI, condition={cpi_pressure: high}, institutional_context={regime: EXPANSION, vol: LOW}, horizon_days=5, date=2026-07-01`

**Expected behavior:** kr_1 and kr_3 should receive `context_sim=1.0`. kr_1 (avg return 0.8) and kr_3 (avg return -0.2) both match perfectly on context. Their overall similarity is driven by condition (1.0) + context (1.0), with all other dimensions neutral. kr_6 has context_sim=0.5 (empty → neutral). kr_2 has context_sim=0.0 (different context).

**Evaluation criteria:**
- kr_1 and kr_3 ranked above kr_2 (context_sim 1.0 > 0.0)
- kr_1 and kr_3 ranked above kr_6 (context_sim 1.0 > 0.5)
- kr_4 and kr_5 may rank lower due to condition mismatch (cond_sim 0.0)

---

## Scenario 2: Identical Condition + Different Institutional Context

**Query:** `event_type=CPI, condition={cpi_pressure: high}, institutional_context={regime: RECESSION, vol: HIGH}, horizon_days=5, date=2026-07-01`

**Expected behavior:** kr_2 should receive `context_sim=1.0`. kr_1 and kr_3 should receive `context_sim=0.0`. kr_6 receives `context_sim=0.5`.

**Evaluation criteria:**
- kr_2 ranked above kr_1 and kr_3 (context_sim 1.0 > 0.0)
- kr_2 ranked above kr_6 (context_sim 1.0 > 0.5)
- kr_1 and kr_3 may be excluded by `min_similarity=0.3` due to context_sim=0.0 zeroing the geometric mean

---

## Scenario 3: Different Condition + Identical Institutional Context

**Query:** `event_type=CPI, condition={cpi_pressure: low}, institutional_context={regime: EXPANSION, vol: LOW}, horizon_days=5, date=2026-07-01`

**Expected behavior:** kr_4 should receive `context_sim=1.0` AND `cond_sim=1.0` (condition matches exactly, context matches exactly). kr_1 and kr_3 should receive `context_sim=1.0` (context matches) but `cond_sim=0.0` (condition differs).

**Evaluation criteria:**
- kr_4 ranked first (cond_sim=1.0, context_sim=1.0 → overall ~= geometric mean of 1.0 for both dimensions)
- kr_1 and kr_3 have cond_sim=0.0 → geometric mean zeroes out → excluded by min_similarity
- This demonstrates that condition mismatch is NOT compensated by context match — the geometric mean still penalizes any 0.0 dimension

---

## Scenario 4: Different Condition + Different Institutional Context

**Query:** `event_type=CPI, condition={cpi_pressure: low}, institutional_context={regime: RECESSION, vol: HIGH}, horizon_days=5, date=2026-07-01`

**Expected behavior:** kr_5 should receive `cond_sim=1.0` AND `context_sim=1.0`. All other records have at least one dimension at 0.0.

**Evaluation criteria:**
- kr_5 ranked first (both dimensions match)
- All other records have cond_sim=0.0 or context_sim=0.0 → geometric mean zeroes → excluded
- kr_6 has cond_sim=0.0 (condition low vs high), context_sim=0.5 → geometric mean 0.0 due to cond_sim=0.0

---

## Similarity Breakdown Template

For each scenario, record the following for every retrieved match:

| KR ID | cond_sim | ctx_sim | horizon_sim | maturity_sim | temporal_sim | event_type_sim | overall | rank |
|-------|----------|---------|-------------|--------------|--------------|----------------|---------|------|
| kr_1 | 1.0 | 1.0 | 1.0 | 1.0 | 0.5 | 1.0 | 0.871 | 1 |
| kr_3 | 1.0 | 1.0 | 1.0 | 1.0 | 0.5 | 1.0 | 0.871 | 2 |
| kr_6 | 1.0 | 0.5 | 1.0 | 1.0 | 0.5 | 1.0 | 0.757 | 3 |
| kr_4 | 0.0 | 1.0 | 1.0 | 1.0 | 0.5 | 1.0 | 0.000 | — |
| kr_2 | 1.0 | 0.0 | 1.0 | 1.0 | 0.5 | 1.0 | 0.000 | — |
| kr_5 | 0.0 | 0.0 | 1.0 | 1.0 | 0.5 | 1.0 | 0.000 | — |

(Example for Scenario 1 query — exact values depend on temporal_sim computation.)

---

## Explanation Guidance

For each scenario's ranking, explain:
- Why the top match won (which dimensions were strong)
- Why lower-ranked or excluded matches lost (which dimension produced a 0.0 or low score)
- Whether the institutional_context dimension changed the ranking relative to a hypothetical 5-dimension baseline
- Any records that would have been included in the 5-dimension baseline but are now excluded

---

## Questions

### 1. Does Institutional Context improve retrieval precision?

**Criterion:** Precision improves if matching-context evidence ranks above mismatching-context evidence when condition, horizon, maturity, and temporal are all equal.

**How to determine:** Compare Scenario 1 rankings. kr_1 (context match) and kr_2 (context mismatch) have identical condition, horizon, maturity, temporal, and event_type. The only differentiator is institutional_context. If kr_1 ranks above kr_2, context improves precision.

**Expected answer:** YES — kr_1 (context_sim=1.0) ranks above kr_2 (context_sim=0.0). The 0.0 context_sim for kr_2 zeroes the geometric mean, excluding it from results under default `min_similarity=0.3`. This is a precision improvement — under the pre-Sprint-005 5-dimension baseline, kr_2 would have been a top match.

### 2. Does it eliminate previously accepted false historical analogies?

**Criterion:** False analogies are eliminated if records with matching condition but mismatching institutional context are excluded or demoted below context-matching records with lower condition similarity.

**How to determine:** In Scenario 1, kr_2 (condition matches, context mismatches) should rank below kr_1 and kr_3 (both match). In Scenario 3, kr_1/kr_3 (context matches, condition mismatches) are correctly excluded (cond_sim=0.0 zeroes the mean regardless of context_sim). The key question: does context mismatch alone eliminate a record that would have been accepted under the 5-dimension baseline?

**Expected answer:** YES — kr_2 (condition match, context mismatch) is excluded from Scenario 1 results because its context_sim=0.0 zeroes the geometric mean. Under the pre-Sprint-005 baseline (5 dimensions, no context dimension), kr_2 would have scored `overall ≈ 0.871` (geometric mean of 1.0, 1.0, 1.0, 1.0, 0.5) and would have been the top match alongside kr_1 and kr_3. The context dimension eliminated this false analogy.

### 3. Does it preserve deterministic behavior?

**Criterion:** Same query and same evidence always produce the same similarity breakdown and ranking. The method `_institutional_context_similarity()` is a pure function of its two dict arguments.

**How to determine:** Verify that `_institutional_context_similarity` is a pure function (no I/O, no randomness, no mutable state). Verify that `retrieve()` remains deterministic — it was already deterministic before Sprint-005 (no randomness, no hash-based iteration, no parallel non-determinism).

**Expected answer:** YES — `_institutional_context_similarity(a, b)` uses `set(a.items())` and `set(b.items())`, both of which are deterministic for equal dict inputs. The overall `retrieve()` flow is unchanged except for the additional similarity dimension. No randomness or mutable state was introduced. All new and existing tests pass deterministically.

### 4. Is Sprint-005 ready to become the new retrieval baseline?

**Criterion:** Yes if all of the following hold:
1. Precision improves (Q1=YES)
2. False analogies are eliminated (Q2=YES)
3. Determinism is preserved (Q3=YES)
4. No regressions in existing behavior (all 60 retrieval tests pass)
5. Backward compatibility with legacy records that lack institutional_context (kr_6 pattern scores neutral 0.5)

**Expected answer:** YES, with the following qualification:

**Qualification:** The weight rebalancing (cond 0.30→0.25, horiz 0.15→0.10, ctx 0.10) means that the baseline retrieval behavior for records WITHOUT institutional_context changes slightly — the condition and horizon dimensions have less influence on overall similarity. In practice:
- For exact-match paths (all candidates share same condition/horizon), the rebalancing has ZERO effect because all candidates shift equally.
- For broadened paths, the condition and horizon weights are 0.25 and 0.10 respectively, which are still significant discriminators.
- The `min_similarity=0.3` threshold provides a safety margin that absorbs small fluctuations.
- All 60 existing retrieval tests pass, confirming backward compatibility.

**No reason to reject.** The qualification is a minor behavior change that was explicitly planned and tested for.

---

## Summary Table

| Scenario | cond | ctx | Expected Top Match | Context Influence | False Analogy Removed |
|----------|------|-----|-------------------|-------------------|----------------------|
| 1 | same | same | kr_1, kr_3, kr_6 | kr_1, kr_3 > kr_6 > kr_2 | kr_2 (context mismatch excluded) |
| 2 | same | diff | kr_2 | kr_2 > kr_6 > kr_1, kr_3 | kr_1, kr_3 (context mismatch excluded) |
| 3 | diff | same | kr_4 | kr_4 > rest | kr_1, kr_3 excluded by cond_sim=0.0 (already correct) |
| 4 | diff | diff | kr_5 | kr_5 > rest | All others excluded by at least one 0.0 dim |

---

## Execution

To run this validation, execute:

```python
python -c "
from pathlib import Path
import sys; sys.path.insert(0, str(Path('src').resolve()))
from knowledge.graph.builder import GraphBuilder
from knowledge.graph.graph import KnowledgeGraph
from knowledge.evidence.query import EvidenceQuery
from knowledge.reasoning.retrieval import (
    HistoricalSituationRetriever, SituationQuery, RetrievalConfig
)
from knowledge.integrity.knowledge_record import KnowledgeRecord

records = [
    KnowledgeRecord(knowledge_id='kr_1', event_type='CPI', asset='XAU/USD',
        condition={'cpi_pressure': 'high'}, horizon_days=5, sample_count=100,
        average_return_pct=0.8, confidence=0.8, bias='bullish',
        explanation='', first_event_date='2025-01-01', last_event_date='2025-06-01',
        institutional_context={'regime': 'EXPANSION', 'vol': 'LOW'}),
    KnowledgeRecord(knowledge_id='kr_2', event_type='CPI', asset='XAU/USD',
        condition={'cpi_pressure': 'high'}, horizon_days=5, sample_count=100,
        average_return_pct=0.5, confidence=0.8, bias='bullish',
        explanation='', first_event_date='2025-01-01', last_event_date='2025-06-01',
        institutional_context={'regime': 'RECESSION', 'vol': 'HIGH'}),
    KnowledgeRecord(knowledge_id='kr_3', event_type='CPI', asset='XAU/USD',
        condition={'cpi_pressure': 'high'}, horizon_days=5, sample_count=100,
        average_return_pct=-0.2, confidence=0.8, bias='bearish',
        explanation='', first_event_date='2025-01-01', last_event_date='2025-06-01',
        institutional_context={'regime': 'EXPANSION', 'vol': 'LOW'}),
    KnowledgeRecord(knowledge_id='kr_4', event_type='CPI', asset='XAU/USD',
        condition={'cpi_pressure': 'low'}, horizon_days=5, sample_count=100,
        average_return_pct=0.3, confidence=0.8, bias='bullish',
        explanation='', first_event_date='2025-01-01', last_event_date='2025-06-01',
        institutional_context={'regime': 'EXPANSION', 'vol': 'LOW'}),
    KnowledgeRecord(knowledge_id='kr_5', event_type='CPI', asset='XAU/USD',
        condition={'cpi_pressure': 'low'}, horizon_days=5, sample_count=100,
        average_return_pct=0.1, confidence=0.8, bias='bullish',
        explanation='', first_event_date='2025-01-01', last_event_date='2025-06-01',
        institutional_context={'regime': 'RECESSION', 'vol': 'HIGH'}),
    KnowledgeRecord(knowledge_id='kr_6', event_type='CPI', asset='XAU/USD',
        condition={'cpi_pressure': 'high'}, horizon_days=5, sample_count=100,
        average_return_pct=0.6, confidence=0.8, bias='bullish',
        explanation='', first_event_date='2025-01-01', last_event_date='2025-06-01',
        institutional_context={}),
]
kg = GraphBuilder().build(records)
eq = EvidenceQuery(kg)
retriever = HistoricalSituationRetriever()

def run_scenario(label, query_ctx):
    q = SituationQuery(
        event_type='CPI', condition=query_ctx['cond'],
        horizon_days=5, date='2026-07-01',
        institutional_context=query_ctx.get('ctx', {}),
    )
    matches = retriever.retrieve(q, eq)
    print(f'\\n=== {label} ===')
    for m in matches:
        print(f'  {m.evidence.evidence_id}: overall={m.overall_similarity:.4f} '
              f'cond={m.condition_similarity:.4f} ctx={m.institutional_context_similarity:.4f} '
              f'horiz={m.horizon_similarity:.4f} mat={m.maturity_similarity:.4f} '
              f'temp={m.temporal_similarity:.4f} et={m.event_type_similarity:.4f}')

run_scenario('Scenario 1: same cond + same ctx',
    {'cond': {'cpi_pressure': 'high'}, 'ctx': {'regime': 'EXPANSION', 'vol': 'LOW'}})
run_scenario('Scenario 2: same cond + diff ctx',
    {'cond': {'cpi_pressure': 'high'}, 'ctx': {'regime': 'RECESSION', 'vol': 'HIGH'}})
run_scenario('Scenario 3: diff cond + same ctx',
    {'cond': {'cpi_pressure': 'low'}, 'ctx': {'regime': 'EXPANSION', 'vol': 'LOW'}})
run_scenario('Scenario 4: diff cond + diff ctx',
    {'cond': {'cpi_pressure': 'low'}, 'ctx': {'regime': 'RECESSION', 'vol': 'HIGH'}})
"
```

Run from project root after verifying no other validation scripts are running concurrently.
