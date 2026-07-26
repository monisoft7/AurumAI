# Sprint-008: Institutional Decision Benchmark Specification

**Date:** 2026-07-25
**Status:** Specification — No Implementation

---

## 1. Benchmark Datasets

### 1.1 Primary Source: Historical Macro Events (2015–2018)

The existing `data/economic/output/lessons.csv` contains CPI release events from March 2015 through September 2018, each annotated with gold returns at 1D, 5D, and 20D horizons. This is the ground-truth corpus.

**Record count**: 35 events × 3 horizons = 105 lesson rows (some with fewer due to data boundaries).

**Fields available in each lesson**:
| Field | Source | Used for benchmark |
|-------|--------|-------------------|
| `event_date` | CPI release date | Temporal split |
| `cpi_value`, `cpi_change_pct` | Release data | Condition computation |
| `cpi_pressure` | Build time (up/down) | Query condition |
| `gold_return_{1,5,20}d_pct` | Historical gold data | **Ground truth outcome** |
| `gold_direction_{1,5,20}d` | Historical gold data | Ground truth direction |
| `primary_horizon_days` | Config (5 or 20) | Query horizon |

### 1.2 Derived Dataset: Knowledge Records

From lessons, the pipeline produces knowledge records (`data/economic/output/knowledge.json`). The existing corpus has 6 records:

| Knowledge record | Condition | Horizon | Records | Avg return | Bias |
|-----------------|-----------|---------|---------|------------|------|
| `CPI_XAU/USD_inflation_pressure_down_1D` | pressure=down | 1 | 8 | +0.604% | positive |
| `CPI_XAU/USD_inflation_pressure_down_5D` | pressure=down | 5 | 8 | +0.012% | mixed |
| `CPI_XAU/USD_inflation_pressure_down_20D` | pressure=down | 20 | 8 | +0.830% | negative |
| `CPI_XAU/USD_inflation_pressure_up_1D` | pressure=up | 1 | 35 | −0.111% | mixed |
| `CPI_XAU/USD_inflation_pressure_up_5D` | pressure=up | 5 | 35 | −0.311% | negative |
| `CPI_XAU/USD_inflation_pressure_up_20D` | pressure=up | 20 | 35 | −0.148% | negative |

### 1.3 Supplementary Data (Available)

| Dataset | Path | Covers | Use |
|---------|------|--------|-----|
| CPI raw | `data/economic/CPIAUCSL.csv` | 2015–2018 | Alternative event extraction |
| Gold | `data/history/gold/gold.csv` | 2015–2018 | Price data for return computation |
| Fed Funds | `data/economic/FEDFUNDS.csv` | 2015–2018 | Institutional context (monetary regime) |
| DGS10 | `data/economic/DGS10.csv` | 2015–2018 | Institutional context (yield environment) |
| GDP | `data/economic/GDP.csv` | 2015–2018 | Multi-event cross-validation |
| PMI | `data/economic/PMI.csv` | 2015–2018 | Multi-event cross-validation |
| UNRATE | `data/economic/UNRATE.csv` | 2015–2018 | Institutional context (labor market) |

### 1.4 Dataset Construction Rules

1. **Temporal split**: All events before a cutoff date form the **knowledge base** (evidence pool). Events on or after the cutoff form the **test set** (queries).
2. **Rolling window**: For each test event, the knowledge base contains only events that occurred before it (no lookahead bias).
3. **Default split**: 70% training (2015-03 through 2016-12, ~24 events), 30% test (2017-01 through 2018-09, ~11 events).
4. **Cross-validation**: 5-fold chronological cross-validation (no random shuffle — time series constraint).

---

## 2. Evaluation Metrics

### Q1: Directional Accuracy — Did AurumAI reach the correct directional conclusion?

**Definition**: The predicted decision type (STRONG_POSITIVE, POSITIVE, NEUTRAL, NEGATIVE, STRONG_NEGATIVE, INSUFFICIENT_EVIDENCE) is compared against the ground-truth directional outcome over the query horizon.

**Metrics**:

| Metric | Formula | Range | Interpretation |
|--------|---------|-------|---------------|
| `directional_accuracy` | `(TP + TN) / N` | [0, 1] | Fraction of non-neutral decisions where sign matches actual |
| `directional_hit_rate` | `TP / (TP + FN)` | [0, 1] | Of positive decisions, fraction that were correct |
| `directional_false_positive_rate` | `FP / (FP + TN)` | [0, 1] | Of negative actuals, fraction called positive |
| `kappa` | Cohen's κ | [−1, 1] | Chance-adjusted agreement |
| `avg_return_if_acted` | Mean return across all test cases if position taken proportional to decision strength | unbounded | Simulated P&L |

**Direction mapping**: The DecisionEngine produces 6 types. For directional accuracy, these map to binary directional predictions:

| Decision type | Directional prediction | Strength |
|---------------|----------------------|----------|
| STRONG_POSITIVE | POSITIVE | 2 |
| POSITIVE | POSITIVE | 1 |
| NEUTRAL | NONE / ABSTAIN | 0 |
| NEGATIVE | NEGATIVE | −1 |
| STRONG_NEGATIVE | NEGATIVE | −2 |
| INSUFFICIENT_EVIDENCE | ABSTAIN | 0 |

**Ground-truth direction**: `gold_direction_{horizon}d` from the lesson record (UP / DOWN / FLAT).

Decision is **correct** if:
- Decision is POSITIVE/STRONG_POSITIVE and actual direction is UP
- Decision is NEGATIVE/STRONG_NEGATIVE and actual direction is DOWN
- Decision is NEUTRAL/INSUFFICIENT_EVIDENCE and any actual direction (abstention is not penalized for directional accuracy)

**Success criteria**: `directional_accuracy ≥ 0.55` (above random chance of 0.5).

### Q2: Internal Consistency — Was the reasoning internally consistent?

**Definition**: Every step in the reasoning chain must be structurally valid.

**Metrics**:

| Metric | Formula | Range | Interpretation |
|--------|---------|-------|---------------|
| `evidence_id_integrity` | fraction of supporting_evidence_ids that exist in collection | [0, 1] | No orphaned evidence references |
| `step_sequence_validity` | fraction of chains with correct step order (review → [comparison] → aggregation → conclusion) | [0, 1] | Step type sequence is valid |
| `chain_id_uniqueness` | fraction of chain IDs that are unique across the benchmark run | [0, 1] | No collisions |
| `comparison_correctness` | fraction of comparisons where direction_summary matches the evidence | [0, 1] | Comparison step honestly reflects its input |
| `consistency_score` | weighted average of the above | [0, 1] | Overall consistency |

**Passing conditions**:
- `evidence_id_integrity > 0` on every chain (IDEALLY 1.0, but edge cases may fail)
- All chains have valid step sequences
- No chain ID collisions
- Comparison steps correctly summarize their evidence

**Success criteria**: `consistency_score = 1.0` (all tests pass for all chains).

### Q3: Retrieval Appropriateness — Was the retrieved historical evidence appropriate?

**Definition**: The historical evidence retrieved by `HistoricalSituationRetriever` should match the query's event type, condition, and horizon. Evidence outside these dimensions should have lower similarity.

**Metrics**:

| Metric | Formula | Range | Interpretation |
|--------|---------|-------|---------------|
| `precision_at_1` | fraction of queries where top-1 match has same event_type | [0, 1] | Top result is from same event |
| `precision_at_3` | fraction of top-3 matches with same event_type | [0, 1] | Top-3 are from same event |
| `exact_match_rate` | fraction of queries where top-1 match is exact (event_type + condition + horizon) | [0, 1] | Best possible match found |
| `broadened_recall` | fraction of same-event-type matches found when exact match count is low | [0, 1] | Fallback retrieval works |
| `context_similarity_correlation` | Spearman ρ between institutional_context similarity and overall similarity | [−1, 1] | Context dimension influences scoring (only when context is non-empty) |

**Passing conditions** (matching Sprint-005 threshold):
- `precision_at_1 ≥ 0.90`
- `exact_match_rate ≥ 0.60`

### Q4: Context Impact — Did institutional context improve the decision?

**Definition**: Run the benchmark twice — once without institutional context (context_weights=0, institutional_context empty) and once with full context. Compare directional accuracy and retrieval quality.

**Metrics**:

| Metric | Formula | Range | Interpretation |
|--------|---------|-------|---------------|
| `accuracy_delta` | `accuracy_with_context − accuracy_without_context` | [−1, 1] | Accuracy improvement from context |
| `retrieval_precision_delta` | `precision_at_1_with − precision_at_1_without` | [−1, 1] | Retrieval precision improvement |
| `confidence_delta` | mean confidence difference (with − without) | [−1, 1] | Confidence shift from context |
| `non_empty_context_fraction` | fraction of queries where context is non-empty | [0, 1] | Context availability in test set |
| `abstention_rate_delta` | fraction of cases where context caused NEUTRAL/INSUFFICIENT vs POSITIVE/NEGATIVE | [−1, 1] | Context causes more cautious decisions |

**Interpreting context impact**:
- Positive `accuracy_delta` → context helps
- Negative `accuracy_delta` → context hurts
- Zero or very small → context is neutral (may still be worth it for explainability)

**Success criteria**: `accuracy_delta ≥ 0.0` (context does not degrade accuracy).

### Q5: Confidence Calibration — Was confidence calibrated?

**Definition**: AurumAI's predicted confidence should correspond to the empirical probability of a correct decision.

**Metrics**:

| Metric | Formula | Range | Interpretation |
|--------|---------|-------|---------------|
| `expected_calibration_error` | `Σ(bins) n_bin/N × | acc_bin − conf_bin |` | [0, 1] | Weighted average calibration error |
| `maximum_calibration_error` | `max_bin | acc_bin − conf_bin |` | [0, 1] | Worst-case calibration error |
| `brier_score` | `mean((pred_conf − actual_correct)²)` | [0, 1] | Overall probabilistic accuracy |
| `confidence_utility` | fraction of decisions where `(conf − 0.5) > 0` when correct AND `(conf − 0.5) < 0` when wrong | [0, 1] | Confidence is useful for ranking |

**Calibration bins**: [0.0–0.5), [0.5–0.6), [0.6–0.7), [0.7–0.8), [0.8–0.9), [0.9–1.0].

Note: N is typically small (≈11 test events), so calibration error will have high variance. The benchmark should report bin counts and note when bins have <3 samples.

**Success criteria**:
- `expected_calibration_error ≤ 0.20` (20% calibration error is acceptable for small samples)
- Consider the metric as **informative** rather than **pass/fail** until more data is available.

### Q6: Actionability — Would the produced Institutional Decision have been actionable?

**Definition**: If a trader followed AurumAI's decisions with a simple position-sizing rule, would the resulting equity curve have positive risk-adjusted returns?

**Position sizing rule**:

| Decision type | Position | Size multiplier |
|---------------|----------|----------------|
| STRONG_POSITIVE | LONG gold | confidence × 1.0 |
| POSITIVE | LONG gold | confidence × 0.5 |
| NEUTRAL | NO POSITION | 0 |
| NEGATIVE | SHORT gold | confidence × 0.5 |
| STRONG_NEGATIVE | SHORT gold | confidence × 1.0 |
| INSUFFICIENT_EVIDENCE | NO POSITION | 0 |

**Return attribution**: For each test event at horizon H, the position P (as fraction of capital) earns `P × gold_return_Hd_pct`. Positions are sized as fraction of portfolio (e.g., 0.5 means 50% of capital).

**Metrics**:

| Metric | Formula | Range | Interpretation |
|--------|---------|-------|---------------|
| `total_return` | `Σ(position_i × return_i)` | unbounded | Cumulative P&L |
| `sharpe_ratio` | `mean(return_i) / std(return_i) × sqrt(252/H)` | unbounded | Risk-adjusted return (annualized) |
| `max_drawdown` | peak-to-trough equity curve decline | [0, 1] | Maximum capital depletion |
| `win_rate` | fraction of positions with positive return | [0, 1] | Per-trade success rate |
| `profit_factor` | gross profit / gross loss | [0, ∞) | Reward-to-risk ratio |
| `avg_hold_return` | mean return per position | unbounded | Average trade P&L |
| `num_trades` | count of non-abstention decisions | integer | Number of opportunities traded |

**Success criteria**:
- `sharpe_ratio ≥ 0.5` (annualized, positive risk-adjusted return)
- `profit_factor ≥ 1.5`
- `num_trades ≥ 5` (sufficient sample size for evaluation)

---

## 3. Experiment Design

### 3.1 Experiment 1: Full Pipeline Backtest (Baseline)

**Objective**: Measure end-to-end institutional decision quality.

**Procedure**:
1. For each test event date D with condition C and horizon H:
   a. Build knowledge base from all lessons before D
   b. Query evidence using (event_type=CPI, condition=C, horizon=H)
   c. Retrieve historical matches using `HistoricalSituationRetriever`
   d. Run `ReasoningEngine.reason()` → produce `ReasoningChain`
   e. Run `DecisionEngine.decide()` → produce `Decision`
   f. Record: decision type, confidence, chain_id, step count, retrieved matches
   g. Compare against ground truth: `gold_return_{H}d_pct`, `gold_direction_{H}d`
2. Aggregate all results into a single report.
3. Compute all metrics from Section 2.

**Configuration**: No modifications to any frozen-core component.

### 3.2 Experiment 2: Context Impact (A/B Comparison)

**Objective**: Determine whether institutional context improves decisions.

**Procedure**:
1. Run Experiment 1 twice:
   - **Run A (Without context)**: `RetrievalConfig(institutional_context_weight=0.0)`, `OrchestrationContext(institutional_context={})`
   - **Run B (With context)**: `RetrievalConfig(institutional_context_weight=0.10)`, context populated from `PipelineContext.institutional_context`
2. For each run, compute all metrics.
3. Compare Run B vs Run A for each metric.
4. Report `_delta` metrics per Section 2 Q4.

**Configuration**: The `retrieval.py` `_institutional_context_similarity()` returns 0.5 for empty context (see Sprint-005). When context is empty, the weight is effectively redistributed. This experiment must ensure that "without context" actually disables the dimension (weight=0).

### 3.3 Experiment 3: Confidence Calibration Study

**Objective**: Assess whether predicted confidence is empirically meaningful.

**Procedure**:
1. Collect all (predicted_confidence, actual_correct) pairs from Experiment 1.
2. Bin confidences into 5 bins: [0.0–0.5), [0.5–0.7), [0.7–0.8), [0.8–0.9), [0.9–1.0].
3. For each bin, compute:
   - Bin center confidence
   - Empirical accuracy within bin
   - Bin sample count
4. Produce a reliability diagram (text-based table).
5. Compute ECE and MCE per Section 2 Q5.
6. Flag any bin with <3 samples as "insufficient data."

**Configuration**: Requires running Experiment 1 with varying test conditions to accumulate sufficient samples. If the default test set (≈11 events) is insufficient, use cross-validation (5 folds × 7 test events = 35 total samples).

### 3.4 Experiment 4: Multi-Event Generalization

**Objective**: Validate that the benchmark generalizes beyond CPI + gold.

**Procedure**:
1. Build equivalent knowledge graphs for NFP + gold and PMI + gold using the same pipeline.
2. Run Experiment 1 for each event type separately.
3. Compare metrics across event types.
4. Report a composite score across all event types.

**Data requirements**: NFP lessons exist (`data/economic/PAYEMS.csv`), PMI lessons exist (`data/economic/PMI.csv`). The pipeline must be run to produce NFP-specific and PMI-specific knowledge records.

**Configuration**: Requires one-time pipeline run for NFP and PMI. After that, all benchmark experiments use the resulting knowledge graph.

---

## 4. Success Criteria

### Phase 1: Structural Validation (Gate 1)

| Criterion | Threshold |
|-----------|-----------|
| `consistency_score (Q2)` | = 1.0 |
| `precision_at_1 (Q3)` | ≥ 0.90 |
| `exact_match_rate (Q3)` | ≥ 0.60 |
| `evidence_id_integrity (Q2)` | = 1.0 |

**Gate decision**: If Phase 1 fails, the system has a structural defect. STOP — fix the defect before proceeding.

### Phase 2: Directional Performance (Gate 2)

| Criterion | Threshold |
|-----------|-----------|
| `directional_accuracy (Q1)` | ≥ 0.55 |
| `accuracy_delta (Q4)` | ≥ 0.0 |
| `sharp_ratio (Q6)` | ≥ 0.5 |
| `profit_factor (Q6)` | ≥ 1.5 |

**Gate decision**: If Phase 2 fails, the system makes poor decisions. Review evidence quality, weighting, or reasoning logic before further investment.

### Phase 3: Calibration and Robustness (Informative)

| Criterion | Threshold |
|-----------|-----------|
| `expected_calibration_error (Q5)` | ≤ 0.20 |
| `num_trades (Q6)` | ≥ 5 |
| `kappa (Q1)` | ≥ 0.1 |

**Gate decision**: These are informative targets, not hard gates. Calibration data improves with more test events.

---

## 5. Failure Criteria

The benchmark is considered **FAILED** if any of the following occur:

| Condition | Action |
|-----------|--------|
| `consistency_score < 1.0` | Investigate chain construction bug |
| `evidence_id_integrity < 1.0` | Evidence ID mismatch — check EvidenceQuery or node properties |
| `directional_accuracy < 0.45` | System performs worse than random — critical review |
| `accuracy_delta < −0.10` | Institutional context actively degrades decisions — investigate |
| `sharpe_ratio < 0.0` | Strategy loses money — review position sizing assumptions |
| `max_drawdown > 0.50` | Strategy has catastrophic loss — review risk assumptions |
| No decisions made (`num_trades = 0`) | Knowledge base is empty or conditions never match |

---

## 6. Required Reports

### 6.1 Per-Event Report (JSON, one per test event)

```json
{
  "event_date": "2017-01-01",
  "event_type": "CPI",
  "condition": {"cpi_pressure": "inflation_pressure_up"},
  "horizon_days": 5,
  "knowledge_base_size": 24,
  "retrieved_matches": [
    {"evidence_id": "...", "overall_similarity": 0.85, "retrieval_method": "exact"},
    ...
  ],
  "chain": {
    "chain_id": "reason_CPI_inflation_pressure_up_5",
    "step_count": 5,
    "step_types": ["evidence_review", "evidence_review", "evidence_review", "aggregation", "conclusion"],
    "overall_confidence": 0.723
  },
  "decision": {
    "decision_type": "NEGATIVE",
    "confidence": 0.723,
    "explanation": "..."
  },
  "ground_truth": {
    "return_pct": -0.45,
    "direction": "DOWN"
  },
  "context": {
    "institutional_context": {"macro_regime": "EXPANSION"},
    "context_used_in_retrieval": true
  }
}
```

### 6.2 Aggregate Benchmark Report (JSON)

Generated by the `BenchmarkSuite` infrastructure or a new `InstitutionalBenchmark` class:

```json
{
  "benchmark_name": "institutional_decision_benchmark",
  "timestamp": "2026-07-25T00:00:00Z",
  "configuration": {
    "train_test_split": "chronological 70/30",
    "cutoff_date": "2017-01-01",
    "context_enabled": true,
    "context_weight": 0.10
  },
  "dataset": {
    "knowledge_base_size": 24,
    "test_set_size": 11,
    "event_types": ["CPI"],
    "asset": "XAU/USD",
    "horizons": [1, 5, 20]
  },
  "metrics": {
    "directional_accuracy": 0.64,
    "directional_hit_rate": 0.71,
    "kappa": 0.28,
    "avg_return_if_acted": 0.35,
    "consistency_score": 1.0,
    "evidence_id_integrity": 1.0,
    "precision_at_1": 0.91,
    "exact_match_rate": 0.73,
    "accuracy_delta": 0.09,
    "expected_calibration_error": 0.15,
    "brier_score": 0.21,
    "sharpe_ratio": 0.72,
    "max_drawdown": 0.18,
    "profit_factor": 2.1,
    "num_trades": 9
  },
  "passed_gate_1": true,
  "passed_gate_2": true,
  "passed": true
}
```

### 6.3 Context Impact Report (Markdown)

A narrative report comparing Run A vs Run B:

```markdown
## Context Impact Analysis

### Retrieval Quality
| Metric | Without Context | With Context | Δ |
|--------|:-:|:-:|:-:|
| Precision@1 | 0.82 | 0.91 | +0.09 |
| Exact match rate | 0.64 | 0.73 | +0.09 |

### Decision Quality
| Metric | Without Context | With Context | Δ |
|--------|:-:|:-:|:-:|
| Directional accuracy | 0.55 | 0.64 | +0.09 |
| Sharpe ratio | 0.41 | 0.72 | +0.31 |

### Conclusion
Context improved retrieval precision by +0.09 and directional accuracy by +0.09.
```

### 6.4 Reliability Diagram (Text Table)

```text
Confidence bin   | Count | Avg Conf | Accuracy | Gap
[0.00–0.50)     |     2 |    0.42  |   0.50   | -0.08
[0.50–0.70)     |     3 |    0.61  |   0.67   | +0.06
[0.70–0.80)     |     4 |    0.74  |   0.75   | +0.01
[0.80–0.90)     |     2 |    0.85  |   1.00   | +0.15
[0.90–1.00]     |     0 |      -   |     -    |    -
ECE: 0.15  MCE: 0.15
```

---

## 7. Existing Benchmark Integration

The new benchmark should extend the existing `Benchmark` class:

```python
from knowledge.benchmark.base import Benchmark, BenchmarkResult, Metric

class InstitutionalDecisionBenchmark(Benchmark):
    def __init__(self):
        super().__init__("institutional_decision")
        # No implementation — specification only
```

The existing benchmarks remain unchanged:

| Existing benchmark | Scope | Sprint |
|-------------------|-------|--------|
| `DecisionBenchmark` | DecisionEngine consistency, discrimination, stability | Pre-Sprint-001 |
| `ReasoningBenchmark` | Accuracy on synthetic reasoning scenarios | Pre-Sprint-001 |
| `RetrievalBenchmark` | Exact match, broadened retrieval precision | Sprint-005 |
| `WeightingBenchmark` | Quality ordering, sample-size sensitivity | Pre-Sprint-001 |
| `CrossEventBenchmark` | Cross-event consensus/conflict detection | Pre-Sprint-001 |
| `DeterminismBenchmark` | Output stability across repeat runs | Pre-Sprint-001 |
| `StabilityBenchmark` | Decision stability under perturbation | Pre-Sprint-001 |

The new `InstitutionalDecisionBenchmark` operates at a higher level — end-to-end on real historical data — and reports the 6-question metrics defined in this specification.

---

## 8. Constraints

- **No new capabilities**: The benchmark uses existing components only (`ReasoningEngine`, `DecisionEngine`, `EvidenceWeighter`, `HistoricalSituationRetriever`, `OrchestrationEngine`).
- **No architecture redesign**: The benchmark is a consumer of the existing API, not a modification of it.
- **No frozen-core changes**: All benchmark code lives in the benchmark module or in experiment scripts, not in `src/knowledge/`.
- **Deterministic**: All experiments are deterministic given the same input data and random seed.
- **Backward compatible**: Existing metrics and benchmarks are not modified. The institutional benchmark is additive.
