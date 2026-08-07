# COUNTER_EVIDENCE_CORRECTION_V1

**Purpose:** Design the smallest architectural correction to W7 CounterEvidence so that only justified penalties affect downstream institutional recommendation quality.

**Scope:** Design only. No implementation. No changes to contracts, public interfaces, pipeline ordering, DecisionEngine thresholds, ConfidenceEngine formulas, or stage boundaries.

**Audit basis:**

- `docs/audit/COUNTER_EVIDENCE_VALIDATION_001.md`
- `docs/audit/DECISION_SENSITIVITY_ANALYSIS_001.md`
- `docs/audit/DECISION_TRACE_001.md`
- `docs/audit/SIGNAL_ASSESSMENT_ARCHITECTURE_001.md`
- `docs/audit/WATCH_CLASSIFICATION_TRACE_001.md`

---

## 1. Correction Summary

The current W7 `confidence_penalty` is:

```text
confidence_penalty
  = conflict_severity * 0.4
  + len(bias_flags) * 0.1
  + 0.2 if regime_conflict
```

For `runtime_20260806_234356`, this produced:

```text
0.25 * 0.4 + 4 * 0.1 + 0.2 = 0.7
```

The smallest correction is to preserve the same output fields and downstream formulas, but restrict penalty-bearing W7 facts to unique, evidence-backed, non-filtered causes:

```text
corrected confidence_penalty = 0.3

0.10 cross-set contradiction severity
0.10 regime conflict flag
0.10 missing evidence flag, limited to truly unavailable expected evidence
```

Removed from penalty calculation:

- duplicate `cross_set_conflict` flag charge
- duplicate `regime_conflict` boolean charge
- mislabeled `no_dissent` charge
- missing-evidence charge for `INFLATION` and `REAL_YIELD`, because those observations existed but were filtered out before EvidenceCollection

This is not a new architecture. It is a pruning of unjustified penalty sources inside the existing W7 assessment semantics.

---

## 2. Invariants Preserved

The correction must preserve:

| Area | Preservation requirement |
|---|---|
| Contracts | `CounterEvidenceAssessment` fields remain unchanged. |
| Public interfaces | W7 still emits `missing_evidence`, `bias_flags`, `conflict_severity`, `confidence_penalty`, and `regime_conflict`. |
| Pipeline ordering | W7 remains after EvidenceReasoning and before ThesisConstruction. |
| Stage boundaries | W7 still consumes only `EvidenceReasoning`; no new cross-stage dependency is introduced. |
| DecisionEngine thresholds | `NO_TRADE_CONFIDENCE = 0.5`, `HOLD_CONFIDENCE = 0.35`, `NO_TRADE_RR_RATIO = 2.0` remain unchanged. |
| ConfidenceEngine formulas | Positive weights, penalty weights, and `final = positive_score * support_factor * (1 - penalty_score)` remain unchanged. |
| ConfidenceEngine consumers | `counter_evidence`, `missing_evidence`, and `internal_consistency` remain as existing penalty channels. |

---

## 3. Current Penalty Inventory and Correction

### 3.1 Cross-Set Conflict: Severity Term

**Current producer:** `BiasAnalyzer.compute_conflict_severity`.

**Current formula:**

```text
conflict_severity = 0.5 * (len(contradicting_ids) / len(evidence_sets))
                  + 0.5 * avg(evidence_set.conflict_score)

penalty unit = conflict_severity * 0.4
```

Observed:

```text
conflict_severity = 0.5 * (1 / 2) + 0.5 * 0.0 = 0.25
penalty unit = 0.25 * 0.4 = 0.10
```

**Justification:** Justified. The run had two real evidence sets with opposing gold implications: `es_usd_fx` bearish and `es_general` bullish. The underlying market configuration was real: DXY rose while XAU/USD also rose, creating a genuine cross-set contradiction.

**Correction:** Remain.

**Expected downstream effect:** No direct change. `conflict_severity` remains `0.25`, so the ConfidenceEngine `counter_evidence` channel remains:

```text
0.25 * 0.35 = 0.0875
```

### 3.2 Cross-Set Conflict: Bias Flag

**Current producer:** `CounterEvidenceAssessor.assess`, appending `cross_set_conflict` when `contradicting_ids` is non-empty.

**Current formula:**

```text
penalty unit = 1 bias_flag * 0.1 = 0.10
```

**Justification:** Unjustified as a penalty. It is the same fact already counted by `conflict_severity`: one contradicting set among two evidence sets. The flag is useful as an explanation label, but not as an additional confidence penalty.

**Correction:** Merge into the severity term for penalty purposes. The contradiction remains represented by `conflict_severity` and `contradicting_set_ids`; it should not add a second `0.10`.

**Expected downstream effect:** W7 `confidence_penalty` decreases by `0.10`. Thesis support rises because the same raw support is multiplied by a smaller `(1 - confidence_penalty)`.

### 3.3 Regime Conflict: Bias Flag

**Current producer:** `ConflictDetector.regime_conflict`, called by `CounterEvidenceAssessor.assess`.

**Current formula:**

```text
expected_bias = REGIME_EXPECTED_BIAS[regime]
regime_conflict = any(evidence_set.bias == OPPOSITE_BIAS[expected_bias])
penalty unit = 1 bias_flag * 0.1 = 0.10
```

Observed:

```text
regime = INFLATIONARY
expected_bias = bullish
selected evidence bias includes bearish
regime_conflict = True
```

**Justification:** Justified as one W7 penalty unit. The regime was `INFLATIONARY`, the expected gold bias table maps that regime to bullish, and the selected thesis-supporting evidence set was bearish through the USD channel. The mapping is static, but the triggering facts are runtime facts.

**Correction:** Remain as exactly one W7 penalty unit. It must not be charged again through the separate `regime_conflict` boolean addition.

**Expected downstream effect:** No direct change for this unit. The diagnostic field `regime_conflict=True` remains available to downstream stages and explanations.

### 3.4 Regime Conflict: Boolean Add-On

**Current producer:** The same `ConflictDetector.regime_conflict` call, passed into `BiasAnalyzer.compute_confidence_penalty`.

**Current formula:**

```text
if regime_conflict:
    penalty += 0.2
```

Observed:

```text
penalty unit = 0.20
```

**Justification:** Unjustified as a separate penalty. It uses the same boolean fact that already produced the `regime_conflict` bias flag. In this run, the regime mismatch also remains visible downstream through the unchanged ConfidenceEngine `regime_alignment` positive contributor.

**Correction:** Remove as penalty-bearing duplicate. Preserve the public `regime_conflict` output field for traceability and downstream diagnostics.

**Expected downstream effect:** W7 `confidence_penalty` decreases by `0.20`. ConfidenceEngine `internal_consistency` decreases because it consumes the corrected W7 aggregate penalty. DecisionEngine thresholds and formulas remain unchanged.

### 3.5 No Dissent

**Current producer:** `BiasAnalyzer.no_dissent`.

**Current formula:**

```text
no_dissent = all(evidence_set.conflict_score == 0.0 for evidence_set in evidence_sets)
penalty unit = 1 bias_flag * 0.1 = 0.10
```

Observed:

```text
es_usd_fx.conflict_score = 0.0
es_general.conflict_score = 0.0
no_dissent = True
```

**Justification:** Unjustified. The trigger measures within-set unanimity, not absence of dissent. The same run simultaneously had cross-set dissent: bearish `es_usd_fx` versus bullish `es_general`. Penalizing "no dissent" while also penalizing cross-set conflict is internally contradictory.

**Correction:** Remove as a penalty-bearing flag in multi-set cases where cross-set contradiction exists. It may remain a diagnostic concept only when it accurately means a one-sided evidence surface, but not in this run's configuration.

**Expected downstream effect:** W7 `confidence_penalty` decreases by `0.10`. No evidence is lost; the actual dissent remains represented by `conflict_severity`.

### 3.6 Missing Evidence

**Current producer:** `ConflictDetector.missing_event_types`.

**Current formula:**

```text
present = {evidence_set.event_type for evidence_set in evidence_sets}
expected = REGIME_EXPECTED_EVENT_TYPES[regime]
missing = expected - present

if missing:
    penalty unit = 1 bias_flag * 0.1 = 0.10
```

Observed:

```text
regime = INFLATIONARY
expected = {INFLATION, REAL_YIELD, USD_FX, CB_GOLD}
present = {USD_FX, GENERAL}
missing = {CB_GOLD, INFLATION, REAL_YIELD}
```

**Justification:** Partly justified.

- `CB_GOLD` is justified: no central-bank gold producer existed in the observed scan universe.
- `INFLATION` is unjustified as a missing-data penalty: breakeven inflation existed in the runtime but was filtered out because `change_sigma = NaN`.
- `REAL_YIELD` is unjustified as a missing-data penalty: US10Y real yield existed in the runtime but was filtered out because `change_sigma = NaN`.

**Correction:** Become conditional. Missing-evidence penalties may apply only to expected channels with no available runtime observation or admitted evidence producer. They must not be generated from evidence that existed and was filtered out upstream.

For the audited run:

```text
corrected missing_evidence = {CB_GOLD}
penalty unit remains = 0.10
```

**Expected downstream effect:** W7 keeps one justified missing-evidence penalty unit. Downstream ConfidenceEngine `missing_evidence` also shrinks because `remaining_unknowns` should contain only the truly unavailable channel:

```text
current missing_penalty = min(3 / 3, 1.0) = 1.0
current weighted penalty = 1.0 * 0.25 = 0.25

correct missing_penalty = min(1 / 3, 1.0) = 0.3333
correct weighted penalty = 0.3333 * 0.25 = 0.0833
```

---

## 4. Downstream Penalty Effects

This section does not change ConfidenceEngine formulas. It describes the expected effect of corrected W7 outputs on existing consumers.

### 4.1 Thesis Support Dampening

**Current producer:** ThesisConstruction consumes W7 `confidence_penalty`.

**Current formula:**

```text
institutional_support = avg_supporting_weight * (1 - confidence_penalty)
```

Observed current:

```text
0.4601 * (1 - 0.7) = 0.1380
```

Corrected:

```text
0.4601 * (1 - 0.3) = 0.3221
```

**Reason:** The raw evidence support is unchanged. Only unjustified penalty mass is removed.

### 4.2 ConfidenceEngine Counter-Evidence Penalty

**Current producer:** ConfidenceEngine consumes `conflict_severity`.

**Current formula:**

```text
counter_evidence penalty = conflict_severity * 0.35
```

Current and corrected:

```text
0.25 * 0.35 = 0.0875
```

**Reason:** The underlying cross-set contradiction is real and remains penalty-bearing.

### 4.3 ConfidenceEngine Missing-Evidence Penalty

**Current producer:** ConfidenceEngine consumes thesis `remaining_unknowns`, derived from W7 `missing_evidence`.

**Current formula:**

```text
missing_penalty = min(len(remaining_unknowns) / 3, 1.0)
weighted penalty = missing_penalty * 0.25
```

Observed current:

```text
remaining_unknowns = {CB_GOLD, INFLATION, REAL_YIELD}
missing_penalty = 1.0
weighted penalty = 0.25
```

Corrected:

```text
remaining_unknowns = {CB_GOLD}
missing_penalty = 0.3333
weighted penalty = 0.0833
```

**Reason:** `INFLATION` and `REAL_YIELD` were not absent from the runtime; they were filtered out. A missing-evidence penalty must not be generated from filtered-out evidence.

### 4.4 ConfidenceEngine Internal-Consistency Penalty

**Current producer:** ConfidenceEngine consumes thesis `confidence_inputs["confidence_penalty"]`, derived from W7.

**Current formula:**

```text
internal_consistency penalty = confidence_penalty * 0.40
```

Observed current:

```text
0.7 * 0.40 = 0.28
```

Corrected:

```text
0.3 * 0.40 = 0.12
```

**Reason:** The aggregate W7 penalty no longer includes duplicate or filtered-evidence charges.

### 4.5 DecisionEngine Counter-Evidence Quality Driver

**Current producer:** DecisionEngine consumes thesis `confidence_inputs["confidence_penalty"]`.

**Current formula:**

```text
counter_evidence_quality = 1 - confidence_penalty
decision driver score = counter_evidence_quality * 0.15
```

Observed current:

```text
(1 - 0.7) * 0.15 = 0.0450
```

Corrected:

```text
(1 - 0.3) * 0.15 = 0.1050
```

**Reason:** DecisionEngine thresholds and weights remain unchanged; the corrected W7 value removes unjustified penalty mass.

---

## 5. Expected End-to-End Numeric Effect

Using the audited run values and preserving all existing formulas:

```text
positive_score = 0.6150
corrected_support_factor = 0.3221
corrected_penalty_score = 0.0875 + 0.0833 + 0.1200 = 0.2908

corrected_final_confidence
  = 0.6150 * 0.3221 * (1 - 0.2908)
  ~= 0.1405
```

Expected composite score:

```text
0.30 * 0.1405  = 0.0422
0.20 * 0.6393  = 0.1279
0.15 * 0.4601  = 0.0690
0.15 * 0.7000  = 0.1050
0.10 * 0.5000  = 0.0500
0.10 * 0.0000  = 0.0000
--------------------------------
corrected composite ~= 0.3941
```

Expected decision remains `NO_TRADE` under frozen thresholds because:

- corrected confidence remains below `0.5`
- selected risk/reward ratio remains above `2.0`

The correction improves institutional recommendation quality by making the confidence trace more faithful. It is not expected to force an executable recommendation.

---

## 6. Final Penalty Table

| Penalty | Current Weight | Correct Weight | Reason |
|---|---:|---:|---|
| W7 conflict_severity term | 0.10 | 0.10 | Real cross-set contradiction between bearish USD_FX evidence and bullish GENERAL anomaly evidence. |
| W7 cross_set_conflict flag | 0.10 | 0.00 | Duplicate of conflict_severity; same contradicting set fact already counted. |
| W7 regime_conflict flag | 0.10 | 0.10 | One justified regime mismatch charge: bearish evidence conflicts with INFLATIONARY expected bullish bias. |
| W7 regime_conflict boolean add-on | 0.20 | 0.00 | Duplicate of the same regime_conflict fact; also visible downstream through unchanged regime_alignment. |
| W7 no_dissent flag | 0.10 | 0.00 | Mislabeled heuristic: within-set unanimity is not absence of dissent when cross-set contradiction exists. |
| W7 missing_evidence flag | 0.10 | 0.10 | Remains only for truly unavailable `CB_GOLD`; must not count filtered-out `INFLATION` or `REAL_YIELD`. |
| W9 counter_evidence penalty | 0.0875 | 0.0875 | Driven by unchanged `conflict_severity = 0.25`; justified contradiction remains. |
| W9 missing_evidence penalty | 0.2500 | 0.0833 | `remaining_unknowns` shrinks from three channels to one true missing channel. |
| W9 internal_consistency penalty | 0.2800 | 0.1200 | Consumes corrected W7 aggregate penalty `0.3` instead of `0.7`. |
| Decision counter_evidence_quality loss | 0.1050 | 0.0450 | Decision quality loss falls because `1 - confidence_penalty` rises from `0.3` to `0.7`. |

Note: the last row is expressed as lost driver contribution relative to a zero-penalty maximum of `0.15`.

---

## 7. Verification Against Required Constraints

### No Double Counting

Verified after correction.

- Cross-set contradiction is counted once through `conflict_severity`.
- Regime conflict is counted once inside W7 through the `regime_conflict` flag.
- The separate `regime_conflict` boolean add-on no longer contributes penalty mass.

### No Duplicated Penalties

Verified after correction.

- `cross_set_conflict` no longer adds a separate `0.10` for the same fact already counted by severity.
- `regime_conflict` no longer adds both a `0.10` flag and a `0.20` boolean charge.
- `no_dissent` no longer penalizes the same evidence surface already represented by cross-set contradiction.

### No Heuristic-Only Penalties

Verified after correction.

- `no_dissent` is removed from penalty-bearing status in this configuration because it is a mislabeled heuristic.
- Regime conflict remains only when both runtime facts exist: a runtime regime label and an opposing evidence-set bias. The static regime-to-bias table is not sufficient by itself to create a penalty.
- Missing evidence remains only for channels that are genuinely unavailable, not for categories produced and then excluded by filtering.

### No Penalty Generated From Filtered-Out Evidence

Verified after correction.

- `INFLATION` is not penalty-bearing because breakeven inflation existed in the runtime.
- `REAL_YIELD` is not penalty-bearing because US10Y real yield existed in the runtime.
- `CB_GOLD` remains penalty-bearing because no central-bank gold evidence producer was present in the observed scan universe.

---

## 8. Final Design Decision

The complete CounterEvidence correction is:

```text
Keep W7 contracts and outputs.
Keep W7 position in the pipeline.
Keep all downstream formulas and thresholds.
Correct only the penalty-bearing interpretation of W7 facts.

Current W7 penalty:   0.7
Corrected W7 penalty: 0.3
```

This is the smallest architectural correction because it does not redesign CounterEvidence, add a model, introduce a new stage, change a public interface, or alter the DecisionEngine or ConfidenceEngine. It only removes unjustified penalty mass already identified by the audits.
