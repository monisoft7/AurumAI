# Operational Validation Checklist 002

**Purpose:** Runtime-only operational validation for the next AurumAI runtime.

**Scope:** Evidence extraction and verification only.  
**No implementation, correction, architecture review, threshold change, contract change, feature addition, or execution/trading work.**

---

## 1. OI — Second Observation

### Required artifacts
- [ ] Previous `gold_oi_state.json`
- [ ] New `gold_oi_state.json`
- [ ] Previous runtime report/artifact containing the OI observation
- [ ] New runtime report/artifact containing the OI observation

### Required checkpoints
- [ ] `open_interest` previous value
- [ ] `open_interest` new value
- [ ] `open_interest_change_pct`
- [ ] Observation identity/timestamp for both observations
- [ ] Explicit determination: real day-over-day delta OR first-observation fallback
- [ ] Confirm the new delta is propagated into `volume_flow`
- [ ] Confirm the same value reaches downstream SignalAssessment inputs
- [ ] Record any unexplained value mutation between producers/consumers

### PASS
A genuine second observation exists, the delta is computed from two real observations, and the value is traceable through `volume_flow` downstream.

### FAIL
The second observation is absent, the delta remains a first-observation fallback without justification, or a real delta is lost/changed without an explained transformation.

---

## 2. SignalAssessment

### Required checkpoints
- [ ] `volume_flow` score
- [ ] `volume_flow` passed/failed status
- [ ] Exact source values consumed by `volume_flow`
- [ ] Volume-flow classification before downstream aggregation
- [ ] Classification after any documented transformation
- [ ] Downstream consumer receiving the result
- [ ] Evidence that the result actually affects the downstream path
- [ ] List of structurally disconnected criteria, if any
- [ ] Distinguish disconnected-but-unused criteria from disconnected criteria required by the active decision path

### PASS
`volume_flow` receives the intended source values, produces a valid result, and the result reaches its intended downstream consumer without unexplained loss.

### FAIL
The active `volume_flow` path is structurally disconnected, consumes an unintended source, or its produced result is silently discarded before the relevant downstream stage.

---

## 3. Knowledge → Evidence

### Required checkpoints
- [ ] KnowledgeRecord count
- [ ] Identity of each relevant KnowledgeRecord
- [ ] `event_type`
- [ ] `evidence_class`
- [ ] `source_kr_id`
- [ ] Whether each `source_kr_id` is real/traceable or synthetic
- [ ] Producer/source of each relevant evidence item
- [ ] `duplicates_removed`
- [ ] Identity of any removed duplicates
- [ ] Reason for duplicate classification
- [ ] Verify evidence class is compatible with its actual producer/source

### PASS
Relevant evidence is traceable to real KnowledgeRecords, classifications match their producers, and duplicate removal is explainable and limited to genuine duplicates.

### FAIL
A decision-relevant evidence item depends on an untraceable synthetic `source_kr_id`, has an incompatible evidence class, or genuine evidence is removed as a duplicate without justification.

---

## 4. CounterEvidence

### Required checkpoints
- [ ] `conflict_severity`
- [ ] `bias_flags`
- [ ] `missing_evidence`
- [ ] `confidence_penalty`
- [ ] Evidence items contributing to each penalty component
- [ ] Count/identity of penalty applications
- [ ] Trace from CounterEvidence output to Confidence
- [ ] Trace downstream to determine whether the same conflict is penalized again
- [ ] Explicit duplicate-application determination

### PASS
The penalty is explainable from admitted evidence, each conflict contributes once through the intended path, and no downstream duplicate application is demonstrated.

### FAIL
The same evidence/conflict is demonstrably penalized more than once, or the penalty contains a decision-material component that cannot be traced to actual evidence.

---

## 5. Confidence

For **every input that materially contributes to final confidence**, record:

| Input | Producer | Value | Type | Used in final confidence? |
|---|---|---:|---|---|
|  |  |  | Real / Derived / Fallback / Synthetic | YES / NO |

### Required checkpoints
- [ ] Producer identified
- [ ] Actual runtime value captured
- [ ] Classification: Real / Derived / Fallback / Synthetic
- [ ] Contribution path to final confidence
- [ ] Determine whether the input is actually consumed by the final confidence calculation
- [ ] Identify any fallback/synthetic value that materially affects final confidence
- [ ] Distinguish available-but-unused fallback values from decision-relevant fallback values

### PASS
Every decision-relevant confidence input is traceable, typed correctly, and its contribution to final confidence is demonstrable.

### FAIL
A fallback/synthetic input materially affects final confidence without an institutionally justified path, or a confidence contribution cannot be traced to its producer.

---

## 6. RiskReward

For **every input used by the ratio**, record:

| Input | Producer | Value | Type | Used in ratio? |
|---|---|---:|---|---|
|  |  |  | Real / Derived / Fallback / Synthetic | YES / NO |

### Required checkpoints
- [ ] Producer identified
- [ ] Actual runtime value captured
- [ ] Classification: Real / Derived / Fallback / Synthetic
- [ ] Input-to-ratio trace
- [ ] Confirm the ratio uses the intended institutional upstream inputs
- [ ] Identify any proxy/fallback/synthetic input that materially affects the ratio
- [ ] Do not evaluate or alter thresholds

### PASS
All ratio-driving inputs are traceable and institutionally justified, with no unexplained fallback/synthetic input materially determining the ratio.

### FAIL
A materially influential ratio input is untraceable, unjustified, or is a fallback/synthetic proxy contrary to the established institutional input path.

---

## 7. Final Decision

### Required checkpoints
- [ ] Selected thesis
- [ ] Final institutional confidence
- [ ] Final `risk_reward_ratio`
- [ ] Applicable frozen decision gates
- [ ] Gate-by-gate pass/fail result
- [ ] Final decision
- [ ] Any bias override, if present
- [ ] Upstream evidence/inputs responsible for the decision
- [ ] Trace whether the final decision follows the frozen DecisionEngine path

### PASS
The final decision is reproducible from the frozen DecisionEngine gates and the traced upstream inputs/evidence. `NO_TRADE` is considered valid when the frozen gates produce it.

### FAIL
The final decision cannot be reconciled with the frozen gates, an unexplained override changes decision authority, or decision-relevant upstream values are demonstrably inconsistent with their producers.

---

## 8. Runtime Integrity

### Required checkpoints
- [ ] Total stage count
- [ ] Expected stage count
- [ ] Failed stages
- [ ] Stage-level errors
- [ ] Stage-level warnings that are decision-material
- [ ] Runtime duration
- [ ] Complete `run_registry.jsonl` entry
- [ ] `run_id`
- [ ] Timestamp
- [ ] Git commit
- [ ] Output directory
- [ ] Output isolation from previous runs
- [ ] Required artifacts exist inside the current runtime/output boundary
- [ ] No unexplained cross-run artifact contamination

### PASS
The runtime completes through the expected stage structure, has no blocking errors, has no decision-material warning that invalidates the run, and produces isolated, traceable artifacts.

### FAIL
A stage fails, a decision-material runtime error/warning invalidates evidence, the registry entry is incomplete/untraceable, or outputs are contaminated by another runtime.

---

# Final Validation Classification

## PASS
All decision-material checkpoints are supported by direct runtime evidence, with no unexplained data-path break, duplicate penalty, synthetic/fallback dependency, or DecisionEngine inconsistency.

## FAIL
At least one decision-material checkpoint is disproven by runtime evidence.

A mere reduction in producer coverage, absence of an optional producer, `NO_TRADE`, or a non-improving metric is **not** a FAIL unless it produces a demonstrated decision-material inconsistency.

## Conditions for Opening a New Correction

A new correction may be considered **only when all three conditions hold**:

1. **Proven:** The issue is demonstrated by direct runtime/artifact evidence rather than inference alone.
2. **Causal:** The affected boundary and causal path to the observed behavior are traceable.
3. **Decision-material:** The issue materially affects evidence integrity, confidence, risk/reward, or final institutional decision correctness/consistency.

If any one of these conditions is absent:
- [ ] Do not open a correction.
- [ ] Continue Operational Validation or classify the finding as insufficiently evidenced.

---

## Validation Rule

This checklist does not authorize implementation.

It is an evidence-extraction and classification protocol for the next runtime only.
