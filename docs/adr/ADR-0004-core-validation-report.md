# ADR-0004 Final Core Validation Report: Freeze Recommendation

**Date:** 2026-07-17  
**Validator:** CI Pipeline (full validation suite + Gate 6)

---

## 1. Scope

This report covers the validation of the institutional knowledge pipeline core
(ADR-0004) across all six acceptance criteria using real historical data
(CPIAUCSL, gold, DGS10) across the full overlap window (2015–2025).

Components validated:

| Module | File | Status |
|--------|------|--------|
| LessonBuilder | `src/knowledge/builders/lesson_builder.py` | Verified |
| CPIEvent | `src/knowledge/events/cpi.py` | Verified |
| FeatureExtractionEngine | `src/knowledge/features/engine.py` | Verified |
| CPIFeatureExtractor | `src/knowledge/features/extractors/cpi.py` | Verified |
| YieldContextEnricher | `src/knowledge/context/yields.py` | Fixed, Verified |
| ContextComparisonReport | `src/knowledge/context/comparison.py` | Verified |
| LessonSummaryAggregator | `src/knowledge/lesson_summary.py` | Verified |
| GraphBuilder | `src/knowledge/graph/builder.py` | Verified |
| EvidenceQuery | `src/knowledge/evidence/query.py` | Verified |
| ReasoningEngine | `src/knowledge/reasoning/engine.py` | Verified |
| DecisionEngine | `src/knowledge/decision/engine.py` | Verified |
| InferencePipeline | `src/knowledge/pipeline/pipeline.py` | Verified |
| LineageRegistry | `src/knowledge/integrity/lineage.py` | Verified |
| PipelineValidator | `src/knowledge/pipeline/validator.py` | Verified |
| PipelineRepository | `src/knowledge/pipeline/repository.py` | Verified |
| OrchestrationEngine | `src/knowledge/orchestration/engine.py` | Verified |

---

## 2. Six Criteria Results

### 2.1 Evidence Quality

**Baseline** (CPI-only, 129 lessons → 6 knowledge records):

| Regime | 1D | 5D | 20D |
|--------|----|----|-----|
| CPI down | 0.546 (n=16) | 0.598 (n=16) | 0.694 (n=16) |
| CPI up | 0.534 (n=113) | 0.510 (n=113) | 0.539 (n=113) |

**Contextual** (CPI+US10Y, 129 lessons → 15 knowledge records):

| Regime | 1D | 5D | 20D |
|--------|----|----|-----|
| down+yields_falling | 0.555 (n=7) | 0.708 (n=7) | 0.765 (n=7) |
| down+yields_flat | 0.497 (n=9) | 0.525 (n=9) | 0.418 (n=9) |
| up+yields_falling | 0.534 (n=27) | 0.524 (n=27) | 0.527 (n=27) |
| up+yields_flat | 0.550 (n=47) | 0.533 (n=47) | 0.622 (n=47) |
| up+yields_rising | 0.514 (n=39) | 0.509 (n=39) | 0.540 (n=39) |

**Assessment:** Evidence quality is fundamentally sound. Small-sample regimes
(n=7–16) show higher volatility in confidence. Large-sample regimes (n=27–113)
are stable. The confidence formula (50% sample + 30% edge + 20% move) provides
smooth, interpretable scores.

**Verdict: PASS**

### 2.2 Decision Consistency

| Run | Decision Type | Confidence | Evidence Count |
|-----|--------------|------------|----------------|
| CPI-only | POSITIVE | 0.570 | 6 |
| CPI+US10Y | POSITIVE | 0.555 | 15 |

The decision direction is consistent across both specifications. The contextual
pipeline splits knowledge records from 6 to 15, resulting in more granular evidence
but identical directional recommendation.

**Verdict: PASS**

### 2.3 Explainability

Every knowledge record includes:
- A `knowledge_id` encoding event_type + asset + condition(s) + horizon
- A `condition` dict mapping dimension names to values
- An `explanation` field with natural-language summary
- Direction rates (up/down/flat), return stats (avg/median/min/max), and bias

Example:
> "For CPI condition cpi_pressure=inflation_pressure_down, us10y_trend=yields_falling,
> 7 historical lessons show GOLD had a positive 20-day return in 85.7% of cases,
> with an average return of 4.3444%."

**Verdict: PASS**

### 2.4 Conflict Detection

The ContextComparisonReport compares single-factor (CPI-only) against multi-factor
(CPI+US10Y) knowledge:

| Decision | Count | Criteria |
|----------|-------|----------|
| context_improves_explanation | 3 | confidence delta >= +0.05 |
| context_neutral | 10 | confidence delta < |0.05| |
| context_weakens_explanation | 2 | confidence delta <= -0.05 |

The framework correctly identifies when adding context improves, weakens, or does
not affect the explanatory power. The `min_confidence_delta` threshold (0.05) and
`min_context_samples` threshold (3) prevent over-interpreting noise.

**Verdict: PASS**

### 2.5 Traceability

LineageRegistry records 787 hops across 6 entity types:

```
source_data → lesson → knowledge_record → evidence → reasoning_chain → decision
```

Every entity in the pipeline is linked by `LineageRelationType`:
- `GENERATES`: source_data→lesson, lesson→knowledge_record, chain→decision
- `REFERENCES`: knowledge_record→evidence, evidence→chain

Backward and forward tracing works:
- From decision: finds source_data path
- From source_data: finds decision path

**Verdict: PASS**

### 2.6 Determinism

Same inputs always produce identical outputs:
- Lessons CSV: byte-identical across runs
- Knowledge JSON: identical scientific content across runs
- Only `source_artifact_path` (output directory) differs between runs

Determinism is preserved across LessonBuilder (deterministic lesson generation),
LessonSummaryAggregator (sorted groupby, sorted lesson IDs), and GraphBuilder
(deterministic graph construction).

**Verdict: PASS**

---

## 3. Bug Fixes Applied During Validation

| Bug | File | Fix |
|-----|------|-----|
| NaN yield values not filtered | `src/knowledge/context/yields.py:60` | Added `dropna(subset=["Value"])` in `_load_yields` |

No other critical bugs were found. The remaining 376 tests all pass.

---

## 4. Known Limitations (Non-Blocking)

1. **Sample fragmentation:** Adding context dimensions splits the 129 CPI lessons
   into smaller groups (7–47 samples). The `down+yields_falling` regime has only
   7 samples, which is below the 12-sample confidence threshold.
2. **Missing regime:** `inflation_pressure_down + yields_rising` has 0 events
   (expected — CPI falling with yields rising is a rare regime).
3. **No DXY or other asset context:** The core supports yield context enrichment
   today but does not yet support FX, equity, or commodity context.
4. **CPI-only event type:** Only CPI→gold is validated. NFP, ISM, retail sales,
   and other MacroEvent subclasses are not yet implemented.

---

## 5. Freeze Recommendation

**Recommendation: FREEZE Core v1.0**

The institutional knowledge pipeline (ADR-0004) passes all six validation criteria
on real historical data with the following qualifications:

1. The core is deterministic, traceable, and produces explainable knowledge records.
2. The yield context enrichment pipeline works correctly and produces meaningful
   comparisons (context_adds_value = 3 improved, 10 neutral, 2 weakened).
3. One critical bug was found and fixed (NaN yield handling).
4. All 376 existing tests pass.
5. The pipeline completes in ~1.2 seconds for 129 lessons + 16834 yield observations.

**Conditions for freeze:**
- Core pipeline (ADR-0004) is frozen at v1.0
- Future event types (NFP, ISM, etc.) and context dimensions (DXY, VIX, etc.)
  will be added as extensions via ADR-0005
- Bug fixes to frozen code require ADR override

**Signed off by:** CI pipeline (automated validation)
