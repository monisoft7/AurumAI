# Operational Validation Run 002

Execution command: `python run.py`

Runtime: `runtime_20260809_091544`

Runtime output directory: `C:\AurumAI\AurumAI\outputs\2026-08-09\runtime_20260809_091544`

Checkpoint directory used for stage trace: `C:\Users\THE BLU WALF\AppData\Local\Temp\aurumai_checkpoints\runtime_20260809_091544`

Immediately preceding runtime used for historical comparison: `runtime_20260809_091344`

Preceding checkpoint directory: `C:\Users\THE BLU WALF\AppData\Local\Temp\aurumai_checkpoints\runtime_20260809_091344`

Checklist note: the requested path `docs/audit/OPERATIONAL_VALIDATION_CHECKLIST_002.md` was not present. The available checklist file was `C:\AurumAI\AurumAI\OPERATIONAL_VALIDATION_CHECKLIST_002.md`, and this validation used that checklist content.

No source code, tests, configuration, architecture, or contracts were edited before or during validation.

## Runtime Integrity

Status: PASS

- `summary.json.success`: `true`
- `summary.json.stage_counts`: `{"ok": 26}`
- Expected stage count from checklist/run structure: `26`
- Failed stages: `[]`
- Runtime duration: `140.1 s`
- Runtime log result: `SUCCESS`
- Registry entry: present in `runtime\run_registry.jsonl`
- Registry `run_id`: `runtime_20260809_091544`
- Registry timestamp: `2026-08-09T07:18:08.395195+00:00`
- Registry git commit: `90f0b53`
- Registry exit code: `0`
- Registry pipeline status: `success`
- Output isolation: current runtime artifacts are under `outputs\2026-08-09\runtime_20260809_091544`; preceding runtime artifacts are under `outputs\2026-08-09\runtime_20260809_091344`; checkpoint traces are in separate runtime-named directories.
- Stage-level errors: none in `summary.json`; `run.log` has yfinance/statistical warnings but no stage failure.

Diagnosis: no runtime integrity defect established.

## OI Second Observation

Status: PASS

Previous persisted OI:

- Source checked: tracked pre-runtime content of `data/economic/gold_oi_state.json` via `git show HEAD:data/economic/gold_oi_state.json`
- Timestamp: `2026-08-08T20:54:27.408487+00:00`
- `open_interest`: `298095.0`

Current OI:

- Source checked: current `data/economic/gold_oi_state.json`
- Timestamp: `2026-08-09T07:18:08.178156+00:00`
- `open_interest`: `298095.0`

Calculated delta:

- Formula: `(298095.0 - 298095.0) / 298095.0 * 100`
- Calculated `open_interest_change_pct`: `0.0`

Real-delta determination:

- A prior persisted OI state exists and contains a real prior `open_interest` value.
- The current OI state contains a later timestamp and the same real `open_interest` value.
- The calculated delta is therefore a real second-observation zero delta, not a first-observation fallback.

Propagation:

- Current `pre_market_scan.json`: `PositioningSnapshot(... open_interest_change_pct=0.0, ...)`.
- Preceding `pre_market_scan.json`: `PositioningSnapshot(... open_interest_change_pct=0.0, ...)`.
- Current `signal_assessment.json`: `obs_positioning_20260809` receives the positioning channel and passes `volume_flow` with `score=1.0`, `threshold=0.5`, `passed=True`, detail `ETF accumulating +2.3%; ETF momentum: accumulating`.
- Current `evidence_collection.json`: `ev_kr_synthetic_obs_positioning_20260809_20260809_071808` carries `supporting_observation_ids=('volume_flow',)` into evidence.
- Current `evidence_reasoning.json`: `es_etf_flow` consumes the positioning evidence, with `net_institutional_weight=0.65` and `confidence_contribution=0.65`.
- Current `thesis_update.json`: selected bullish thesis includes `supporting_set_ids=('es_general', 'es_etf_flow')`.
- Current `decision_engine.json`: selected thesis is `th_ef5a7a2391f7.v2`; final decision remains `NO_TRADE`.

Downstream effect:

- The OI delta itself is `0.0`; the passing `volume_flow` detail is driven by ETF accumulation, not by positive OI expansion.
- No unexplained mutation of `open_interest_change_pct` was observed between `pre_market_scan` and `SignalAssessment`; the visible propagated criterion is `volume_flow`.

Diagnosis: expected behavior.

## SignalAssessment

Status: PASS

- `volume_flow` for `obs_XAU/USD_20260809`: score `1.0`, threshold `0.5`, passed `True`; detail `ETF accumulating +2.3%; ETF momentum: accumulating`.
- `volume_flow` for `obs_positioning_20260809`: score `1.0`, threshold `0.5`, passed `True`; detail `ETF accumulating +2.3%; ETF momentum: accumulating`.
- `volume_flow` for DXY, S&P 500 Futures, Brent Crude, EUR/USD, USD/JPY, US10Y Real Yield, US10Y Nominal Yield, Breakeven Inflation, and anomaly observation: score `0.0`, passed `False`.
- `obs_XAU/USD_20260809`: `Weak Signal`, confidence `0.5`, passed `breadth` and `volume_flow`.
- `obs_positioning_20260809`: `Weak Signal`, confidence `0.5`, passed `breadth` and `volume_flow`.
- Downstream consumer: `evidence_collection.json` converts the positioning observation into evidence with `supporting_observation_ids=('volume_flow',)`.
- Downstream effect: `evidence_reasoning.json` forms `es_etf_flow`, which supports the selected bullish thesis.

Diagnosis: expected behavior.

## Knowledge -> Evidence

Status: FAIL

Real KnowledgeRecord retrieval:

- `outputs\2026-08-09\runtime_20260809_091544\artifacts\knowledge.json` exists.
- `record_count`: `6`
- Records are real generated KnowledgeRecords with IDs:
  - `CPI_XAU/USD_inflation_pressure_down_1D`
  - `CPI_XAU/USD_inflation_pressure_down_5D`
  - `CPI_XAU/USD_inflation_pressure_down_20D`
  - `CPI_XAU/USD_inflation_pressure_up_1D`
  - `CPI_XAU/USD_inflation_pressure_up_5D`
  - `CPI_XAU/USD_inflation_pressure_up_20D`
- All six records are for `event_type='CPI'`, `asset='XAU/USD'`, and trace to `artifacts\lessons.csv` with `source_artifact_sha256='cd22f314926f4762a609604e2e14ea5b35d80186b4902cdbed01f194d6183619'`.

Active evidence actually used:

- `evidence_collection.json` creates four decision-relevant Evidence items.
- All four use synthetic `source_kr_id` values:
  - `kr_synthetic_obs_XAU/USD_20260809`
  - `kr_synthetic_obs_DXY_20260809`
  - `kr_synthetic_obs_positioning_20260809`
  - `kr_synthetic_obs_anomaly_XAU/USD_template_violation_gold_and_real_yields_moving_in_same_direction_negative_correlation_expected`
- No active Evidence item uses one of the real `knowledge.json` KnowledgeRecord IDs as `source_kr_id`.

Evidence classes / event types:

- `ev_kr_synthetic_obs_XAU/USD_20260809_20260809_071808`: `event_type='GENERAL'`, source label `overnight_price`, synthetic source.
- `ev_kr_synthetic_obs_DXY_20260809_20260809_071808`: `event_type='USD_FX'`, source label `overnight_price`, synthetic source.
- `ev_kr_synthetic_obs_positioning_20260809_20260809_071808`: `event_type='ETF_FLOW'`, source label `positioning`, synthetic source.
- `ev_kr_synthetic_obs_anomaly_XAU/USD_template_violation_gold_and_real_yields_moving_in_same_direction_negative_correlation_expected_20260809_071808`: `event_type='GENERAL'`, source label `anomaly_flag`, synthetic source.

Duplicate handling:

- `evidence_reasoning.json`: `duplicates_removed=0`.
- Evidence sets have `duplicate_evidence_ids=()`.
- No removed duplicate identities exist.

Checkpoint classification:

- FAIL because decision-relevant evidence depends on synthetic `source_kr_id` values while real KnowledgeRecords exist but are not the active evidence source.
- Issue class: proven defect.
- Proven: yes, directly shown in `knowledge.json` and `evidence_collection.json`.
- Causal: yes, synthetic evidence flows into `evidence_reasoning`, `thesis_update`, `confidence_engine`, and `decision_engine`.
- Decision-material: yes, active evidence determines `evidence_quality`, thesis support, confidence, and decision drivers.

## CounterEvidence

Status: PASS

CounterEvidence output:

- Producer: `W7 CounterEvidenceAssessor`
- `conflict_severity`: `0.1667`
- `missing_evidence`: `('CB_GOLD',)`
- `bias_flags`: `('regime_conflict', 'missing_evidence', 'cross_set_conflict')`
- `confidence_penalty`: `0.2667`
- Supporting sets: `('es_general', 'es_etf_flow')`
- Contradicting sets: `('es_usd_fx',)`
- Explanation: `sets=3 | supporting=2 | contradicting=1 | missing_evidence=['CB_GOLD'] | bias_flags=['regime_conflict', 'missing_evidence', 'cross_set_conflict'] | conflict_severity=0.1667 | confidence_penalty=0.2667 | regime_conflict=True`

Propagation:

- `thesis_construction.json` and `thesis_update.json` consume `conflict_severity=0.1667` and `confidence_penalty=0.2667`.
- `confidence_engine.json` records negative contributors:
  - `counter_evidence`: value `0.1667`, weight `0.35`, penalty `0.0583`
  - `missing_evidence`: value `0.3333333333333333`, weight `0.25`, penalty `0.0833`
  - `internal_consistency`: value `0.2667`, weight `0.4`, penalty `0.1067`
- `decision_engine.json` includes `counter_evidence_quality=0.7333`, which is the complement of `0.2667`.

Duplicate penalty determination:

- No unjustified duplicate penalty application is proven.
- The direct CounterEvidence penalty enters thesis/confidence.
- The DecisionEngine driver is expressed as `counter_evidence_quality=0.7333`, a positive quality score, not a second negative penalty.

Diagnosis: expected behavior.

## Confidence

Status: FAIL

Final confidence:

- Producer: `W9 ConfidenceEngine`
- Selected thesis confidence: `0.2584`
- Reliability category: `very_low`
- Remaining uncertainty: `0.7416`
- Consumed downstream by `W13 DecisionEngine` as `institutional_confidence=0.2584`.

Decision-material inputs:

| Input | Producer | Value | Type | Used in final confidence? |
|---|---|---:|---|---|
| `evidence_quality` | W6/W6 evidence reasoning -> W9 | `0.5583` | Derived from synthetic evidence | YES |
| `evidence_consensus` | W6 evidence reasoning -> W9 | `1.0` | Derived | YES |
| `regime_alignment` | W10/W9 | `1.0` | Derived | YES |
| `source_diversity` | W6 evidence reasoning -> W9 | `0.6667` | Derived | YES |
| `knowledge_record_quality` | W9 | `1.0` | Derived, but based on synthetic active evidence source IDs | YES |
| `temporal_recency` | W6 evidence collection -> W9 | `1.0` | Derived | YES |
| `counter_evidence` | W7 CounterEvidenceAssessor -> W9 | `0.1667` | Derived | YES |
| `missing_evidence` | W7 CounterEvidenceAssessor -> W9 | `0.3333333333333333` | Derived | YES |
| `internal_consistency` | W9 | `0.2667` | Derived | YES |

Positive contributors:

- `evidence_quality=0.5583`, weight `0.25`
- `evidence_consensus=1.0`, weight `0.25`
- `regime_alignment=1.0`, weight `0.15`
- `source_diversity=0.6667`, weight `0.15`
- `knowledge_record_quality=1.0`, weight `0.1`
- `temporal_recency=1.0`, weight `0.1`

Negative contributors:

- `counter_evidence=0.1667`, weight `0.35`, penalty `0.0583`
- `missing_evidence=0.3333333333333333`, weight `0.25`, penalty `0.0833`
- `internal_consistency=0.2667`, weight `0.4`, penalty `0.1067`

Checkpoint classification:

- FAIL because synthetic active evidence sources materially enter `evidence_quality`, `source_diversity`, `temporal_recency`, and `knowledge_record_quality`.
- This is not merely available-but-unused fallback data; the synthetic evidence path is consumed by final confidence and downstream decision authority.
- Issue class: proven defect.
- Proven: yes, directly shown by `evidence_collection.json`, `evidence_reasoning.json`, and `confidence_engine.json`.
- Causal: yes, synthetic evidence contributes to final confidence `0.2584`.
- Decision-material: yes, `institutional_confidence=0.2584` is the first DecisionEngine driver and is named in the `NO_TRADE` explanation.

## RiskReward

Status: PASS

Selected/base scenario ratio inputs:

| Input | Producer | Value | Type | Used in ratio? |
|---|---|---:|---|---|
| `expected_reward` | W12 RiskRewardValidator | `0.2933` | Derived | YES |
| `expected_risk` | W12 RiskRewardValidator | `0.1427` | Derived | YES |
| `risk_reward_ratio` | W12 RiskRewardValidator | `0.9468` | Derived | YES |
| `maximum_downside` | W12 RiskRewardValidator | `0.2854` | Derived | YES |
| `expected_upside` | W12 RiskRewardValidator | `0.5866` | Derived | YES |
| `tail_risk` | W12 RiskRewardValidator | `0.5453` | Derived | YES |
| `liquidity_risk` | W12 RiskRewardValidator | `0.3733` | Derived | YES |
| `regime_risk` | W12 RiskRewardValidator | `0.3` | Derived | YES |
| `volatility_impact` | W12 RiskRewardValidator | `0.4453` | Derived | YES |

Selected/base scenario:

- Scenario ID: `sc_f6872d51453a`
- Thesis ID: `th_ef5a7a2391f7.v2`
- Scenario type: `base`
- Scenario probability: `0.5`
- Validation status: `acceptable`
- Explanation: `expected reward exceeds expected risk with sufficient margin`
- Downstream consumer: `decision_engine.json` consumes the same risk/reward summary.

Diagnosis: expected behavior.

## Decision Authority

Status: PASS

Selected thesis and scenario:

- Selected thesis: `th_ef5a7a2391f7.v2`
- Thesis direction: `bullish`
- Selected scenario: `sc_f6872d51453a`
- Scenario type: `base`
- Scenario probability: `0.5`

Decision values:

- Final institutional confidence: `0.2584`
- Risk/reward status: `acceptable`
- Risk/reward ratio: `0.9468`
- Composite score: `0.5468`
- Bias review: human review required; `overall_severity='critical'`; findings `['regime_blindness', 'false_precision']`; `total_confidence_impact=0.5`
- Final decision: `NO_TRADE`

Decision drivers:

- `institutional_confidence`: value `0.2584`, weight `0.3`, score `0.0775`
- `risk_reward_quality`: value `0.6277`, weight `0.2`, score `0.1255`
- `evidence_quality`: value `0.5583`, weight `0.15`, score `0.0837`
- `counter_evidence_quality`: value `0.7333`, weight `0.15`, score `0.11`
- `scenario_probability`: value `0.5`, weight `0.1`, score `0.05`
- `regime_alignment`: value `1.0`, weight `0.1`, score `0.1`

Gate result:

- Runtime explanation: `reason=no thesis clears institutional confidence and risk/reward thresholds`.
- `NO_TRADE` reconciles with the low institutional confidence and human-review bias flag.
- The DecisionEngine provenance chain includes W7 CounterEvidenceAssessor, W8 ThesisBuilder, W10 ThesisUpdater, W12 ScenarioGenerator, W12 RiskRewardValidator, and W13 DecisionEngine.

Diagnosis: expected behavior, with the upstream Knowledge->Evidence and Confidence defects remaining decision-material inputs.

## Operational Validation Result

- Runtime: `runtime_20260809_091544`
- Overall status: FAIL
- PASS count: 6
- FAIL count: 2
- NOT PROVABLE count: 0
- OI second observation: PASS
- SignalAssessment: PASS
- Knowledge->Evidence: FAIL
- CounterEvidence: PASS
- Confidence: FAIL
- RiskReward: PASS
- Decision Authority: PASS
- Runtime Integrity: PASS
- Proven correction required: YES
- Architecture reopening required: NO

Correction basis:

- Proven: yes. Active evidence uses synthetic `source_kr_id` values while real KnowledgeRecords exist separately.
- Causal: yes. The active synthetic evidence flows through evidence reasoning, thesis construction/update, confidence, and decision.
- Decision-material: yes. Evidence quality and institutional confidence are decision drivers in `decision_engine.json`.

No correction was implemented in this validation run.
