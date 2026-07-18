# ADR-0004 Gate 6 Report: US 10Y Yield Context Validation

**Date:** 2026-07-17  
**Status:** Complete  
**Validator:** CI Pipeline (Gate 6 validation script)

---

## Summary

Gate 6 validates that the yield context enrichment pipeline correctly ingests US 10Y
Treasury yield data (`DGS10`), attaches it to CPI event lessons, conditions knowledge
records on yield trend, and produces a comparison report against the CPI-only baseline.

**Overall Assessment:** `context_adds_value`

---

## 1. Data

| Series | Source | Rows | Date Range | NaN |
|--------|--------|------|------------|-----|
| CPIAUCSL | FRED | 954 | 1947-01-01 to 2026-06-01 | 1 (dropped) |
| Gold (Close) | Yahoo Finance | 2765 | 2015-01-02 to 2025-12-31 | 0 |
| DGS10 | FRED | 16834 | 1962-01-02 to 2026-07-10 | 719 (filtered out) |

Overlap period: **2015-02-01 to 2025-12-01** → 129 CPI lessons.

---

## 2. Pipeline Results

### 2.1 CPI-Only Baseline (6 knowledge records)

| Condition | Horizon | Samples | Confidence | Bias | Avg Return |
|-----------|---------|---------|------------|------|------------|
| inflation_pressure_down | 1D | 16 | 0.5464 | mixed | +0.22% |
| inflation_pressure_down | 5D | 16 | 0.5982 | gold_positive | +0.58% |
| inflation_pressure_down | 20D | 16 | 0.6939 | gold_positive | +2.03% |
| inflation_pressure_up | 1D | 113 | 0.5339 | mixed | +0.12% |
| inflation_pressure_up | 5D | 113 | 0.5103 | mixed | +0.06% |
| inflation_pressure_up | 20D | 113 | 0.5390 | mixed | +0.64% |

**Decision:** POSITIVE (conf=0.5703) — gold shows positive returns following CPI changes.

### 2.2 CPI+US10Y Contextual (15 knowledge records)

| Condition | Horizon | Samples | Confidence | Bias | Avg Return |
|-----------|---------|---------|------------|------|------------|
| down + yields_falling | 1D | 7 | 0.5549 | gold_positive | +1.22% |
| down + yields_falling | 5D | 7 | 0.7084 | gold_positive | +2.92% |
| down + yields_falling | 20D | 7 | 0.7654 | gold_positive | +4.34% |
| down + yields_flat | 1D | 9 | 0.4972 | gold_negative | -0.56% |
| down + yields_flat | 5D | 9 | 0.5245 | gold_negative | -1.24% |
| down + yields_flat | 20D | 9 | 0.4179 | mixed | +0.24% |
| up + yields_falling | 1D | 27 | 0.5341 | mixed | +0.02% |
| up + yields_falling | 5D | 27 | 0.5244 | mixed | -0.33% |
| up + yields_falling | 20D | 27 | 0.5265 | mixed | +0.38% |
| up + yields_flat | 1D | 47 | 0.5502 | mixed | +0.14% |
| up + yields_flat | 5D | 47 | 0.5330 | mixed | +0.35% |
| up + yields_flat | 20D | 47 | 0.6216 | gold_positive | +1.28% |
| up + yields_rising | 1D | 39 | 0.5141 | mixed | +0.16% |
| up + yields_rising | 5D | 39 | 0.5086 | mixed | -0.02% |
| up + yields_rising | 20D | 39 | 0.5404 | mixed | +0.05% |

Missing combination: `down + yields_rising` (0 events — expected; CPI falling with yields
rising is a rare regime).

**Decision:** POSITIVE (conf=0.5547) — consistent with baseline.

### 2.3 Context Comparison

| Decision | Count | Details |
|----------|-------|---------|
| context_improves_explanation | 3 | down+yields_falling_5D, down+yields_falling_20D, up+yields_flat_20D |
| context_neutral | 10 | Confidence delta < 0.05 threshold |
| context_weakens_explanation | 2 | down+yields_flat_5D, down+yields_flat_20D |

**Key Insight:** The strongest signal is *CPI down + yields falling* (a deflationary/rate-cut
signal) where gold rallies with high confidence (0.71–0.77). The weakest signal is
*CPI down + yields flat* (conflicting signals), where gold performance is unpredictable.

---

## 3. Critical Bug Fix

**Bug:** `YieldContextEnricher._load_yields` did not filter NaN values from DGS10 data.
When the bond market was closed (holidays), NaN yield values were returned by
`_latest_on_or_before`, causing 9 lessons to have NaN `us10y_value_at_event` while
still getting a `normal_yield_regime` level classification (since `NaN < 2.0` is `False`).

**Fix:** Added `df = df.dropna(subset=["Value"])` in `_load_yields`
(`src/knowledge/context/yields.py:60`).

**Impact:** Post-fix comparison changed the overall assessment from
`context_not_helpful_yet` (0 improve + 2 weaken + 13 neutral) to
`context_adds_value` (3 improve + 2 weaken + 10 neutral).

**Tests:** All 376 existing tests pass. The NaN fix indirectly affects
`test_pipeline_can_build_yield_context_conditioned_knowledge` (synthetic data
with no NaN → no behavioral change in tests).

---

## 4. Six Criteria Validation

| Criterion | Result | Notes |
|-----------|--------|-------|
| 1. Evidence quality | 57.0% avg confidence | CPI-down: 0.55–0.69; CPI-up: 0.51–0.54 |
| 2. Decision consistency | PASS | Both runs produce POSITIVE (0.570 vs 0.555) |
| 3. Explainability | PASS | Clear condition→outcome narratives |
| 4. Conflict detection | context_adds_value | 3 improved, 10 neutral, 2 weakened |
| 5. Traceability | PASS | 787 lineage hops, 6 node types |
| 6. Determinism | PASS | Scientific content identical across runs |

---

## 5. Artifacts

```
data/output/gate6/
  run1_baseline/artifacts/
    lessons.csv           # 129 CPI-only lessons
    knowledge.json        # 6 CPI-only knowledge records
  run2_contextual/artifacts/
    lessons.csv           # 129 lessons with US10Y enrichment
    knowledge.json        # 15 CPI+US10Y knowledge records
    context_comparison.json  # comparison report
  determinism/
    run1b/                # reproducibility verification
```
