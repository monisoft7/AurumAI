# NO_TRADE Audit 001

**Subject:** Why AurumAI still produces `NO_TRADE` after removal of all confirmed production bugs.
**Scope:** Latest successful runtime only — no code, no tests modified. Read-only audit.
**Date:** 2026-08-04
**Status:** FACTS ONLY. No fixes, no recommendations.

---

## 1. Run Identification (latest successful runtime)

- Pipeline ID: `runtime_20260804_230820`
- Output directory: `outputs/2026-08-04/runtime_20260804_230820`
- Exit code: `0` (`runtime/run_registry.jsonl`)
- Run registry `git_commit`: `78c9ad4` (registry field `git_commit`); working tree carried uncommitted modifications to `src/orchestration/stages.py`, `src/orchestration/orchestrator.py`, `src/forecasting/position_sizing.py`, `src/notifications/telegram_notifier.py`, `scripts/generate_institutional_report.py` at execution time. All decision-path modules cited below (`decision_engine`, `confidence_engine`, `counter_evidence`, `scenario_generation`, `risk_reward_validation`, `bias_prevention`, `thesis_construction`) are unmodified vs `78c9ad4`.
- Stage records: 25/25 `ok`, errors: none.
- Event: CPI; asset XAU/USD; horizon 12.

## 2. Observed Decision Output (`finalize.json`)

- `decision.decision` = `NO_TRADE`
- `decision.institutional_confidence` = `0.315`
- `decision.metadata.composite_score` = `0.4937`
- `decision.selected_thesis_id` = `th_5a4e06fcd3a2.v2` (direction `bullish`)
- `decision.selected_scenario_id` = `sc_01125e33683c` (type `base`, p=`0.5`)
- `decision.risk_reward_summary` = status `acceptable`, ratio `0.9529`
- `decision.metadata.bias_review` = overall_severity `high`, human_review_flag `true`, total_confidence_impact `0.65`, findings `[confirmation_bias, anchoring, groupthink, false_precision]`
- `decision.decision_explanation` (verbatim):
  `decision=NO_TRADE; selected_thesis=th_5a4e06fcd3a2.v2 (bullish); selected_scenario=sc_01125e33683c (base, p=0.5); composite_score=0.4937; institutional_confidence=0.315; risk_reward_status=acceptable; risk_reward_ratio=0.9529; reason=no thesis clears institutional confidence and risk/reward thresholds | BIAS REVIEW: human review required (overall_severity=high, findings=['confirmation_bias', 'anchoring', 'groupthink', 'false_precision'])`

## 3. Complete Decision Path (execution order)

| # | Stage | Function | Location | Produced value |
|---|-------|----------|----------|----------------|
| 1 | Forecast (AutoARIMA, h=12) | `_forecast` | `src/orchestration/stages.py:158` | forecast points; last obs `2026-08-04` |
| 2 | Forecast confidence | `_forecast_confidence` | `stages.py:183` | `confidence.overall=0.7169` (see §4.5) |
| 3 | Forecast validation | `_forecast_validation` | `stages.py:232` | `passed=false, sample_size=0` (§4.9) |
| 4 | Risk measures | `_risk_measures` | `stages.py:270` | `var_95=139.953`, `cvar_95=115.429`, `tail_index=null` |
| 5 | Risk gate | `_risk_gate` | `stages.py:363` | `action=proceed` (§4.10) |
| 6 | Pre-market scan / signal assessment / event triage / evidence collection / evidence reasoning | `_pre_market_scan`…`_evidence_reasoning` | `stages.py:484,403,425,444,504` | evidence produced; all `ok` |
| 7 | W7 Counter-evidence | `_counter_evidence` / `CounterEvidenceAssessor.assess` | `stages.py:522`; `src/counter_evidence/assessor.py:25` | `confidence_penalty=0.2` (implied, §4.2) |
| 8 | W8 Thesis construction | `_thesis_construction` / `ThesisConstructor.construct` | `stages.py:540`; `src/thesis_construction/builder.py:40` | bullish thesis; `avg_supporting_weight=0.6094` |
| 9 | W10 Thesis update | `_thesis_update` | `stages.py:564` | `th_5a4e06fcd3a2.v2` |
| 10 | W9 Confidence engine | `_confidence_engine` / `ConfidenceEngine.evaluate` | `stages.py:619`; `src/confidence_engine/engine.py:26` | `final_confidence=0.315` (§4.6) |
| 11 | W12 Scenario generation | `_scenario_generation` / `ScenarioGenerator.generate` | `stages.py:659`; `src/scenario_generation/generator.py:55` | base p=`0.5` fixed; bull `0.3065`; bear `0.1935` (§4.4) |
| 12 | W12 Risk/reward validation | `_risk_reward_validation` / `RiskRewardValidator.validate` | `stages.py:705`; `src/risk_reward_validation/validator.py:35` | base status `acceptable`, ratio `0.9529` (§4.7) |
| 13 | W13 Bias review | `_bias_prevention` / `BiasReviewer.review` | `stages.py:800`; `src/bias_prevention/detector.py:118` | `human_review_flag=true` (§4.8) |
| 14 | W13 Decision engine | `_decision_engine` / `DecisionEngine.decide` | `stages.py:726`; `src/decision_engine/engine.py:47` | `NO_TRADE` via `_determine_decision` (§4.6, §5) |
| 15 | Bias consumption | `apply_bias_review` | `stages.py:795`; `src/bias_prevention/contracts.py:153` | note appended only (decision already `NO_TRADE`) (§4.8) |
| 16 | W14 Recommendation | `_trade_recommendation` / `RecommendationEngine.recommend` | `stages.py:829`; `src/trade_recommendation/recommender.py:28` | mirrors `NO_TRADE`; no levels (§4.11) |

## 4. Gating Conditions

For each gate: current value / required threshold / pass or fail / source file, function, line.

### 4.1 Evidence Quality

- Current value: `avg_supporting_weight = 0.6094`
  (`finalize.json` `decision_drivers[evidence_quality].value=0.6094`; produced by `ThesisBuilder._build_confidence_inputs`, `src/thesis_construction/builder.py:110-112`).
- Required threshold: none in the decision path. Consumed as a weighted input only: composite weight `0.15` (`src/decision_engine/engine.py:30,180-182,206`) and positive-confidence weight `0.25` (`src/confidence_engine/computer.py:15,35,56-59`). Used as a reference point (≥ `0.5` suppresses narrative/overconfidence bias findings) in `src/bias_prevention/detector.py:131-133,266,287`.
- Pass/fail: PASS (informational; contributes `0.6094 × 0.15 = 0.0914` to composite, `engine.py:206`).

### 4.2 Counter Evidence

- Current value: `counter_evidence_quality = 0.8` ⇒ `confidence_penalty = 0.2`
  (`finalize.json` `decision_drivers[counter_evidence_quality].value=0.8`; `engine.py:183-185` reads `confidence_penalty=0.2` from `thesis.confidence_inputs`, written at `builder.py:120`).
- Penalty formula: `penalty = conflict_severity×0.4 + len(bias_flags)×0.1 + (0.2 if regime_conflict)` (`src/counter_evidence/analyzer.py:47-55`; computed in `src/counter_evidence/assessor.py:49-53`).
- Required threshold: none in the decision path. Consumed as weighted input only: composite `counter_evidence_quality = 1 − penalty`, weight `0.15` (`engine.py:29,207`) and internal-consistency penalty weight `0.40` (`computer.py:26,64,70`).
- Pass/fail: PASS (no hard gate).
- Limitation: `conflict_severity` and the W7 `bias_flags` list are not persisted in run artifacts; only the aggregate penalty `0.2` is observable.

### 4.3 Thesis Score (composite)

- Current value: `composite_score = 0.4937` (`finalize.json` metadata; formula `engine.py:203-211`; components sum `0.0945+0.1378+0.0914+0.12+0.05+0.0 = 0.4937`).
- Required threshold: none numeric. Selection = maximum over eligible theses (`engine.py:110`); eligibility requires at least one scenario with `validation_status ∈ ELIGIBLE_STATUSES = {"acceptable","borderline"}` (`engine.py:40,98-108`).
- Pass/fail: PASS (selected; `total_theses_evaluated=1`, no alternatives).

### 4.4 Scenario Selection

- Current value: selected scenario `sc_01125e33683c`, type `base`, probability `0.5` (`finalize.json`).
- Mechanism: base probability is a fixed constant `BASE_PROBABILITY = 0.5` (`src/scenario_generation/generator.py:38,156-157`); bull/bear split remainder by confidence (`generator.py:144-160`). Selection ranks by `(status, −probability, type)` over scenarios whose `validation_status ∈ ELIGIBLE_STATUSES` (`engine.py:223-249`, filter at `engine.py:236-239`).
- Required threshold: scenario must be `acceptable` or `borderline` (`engine.py:40`). Base scenario = `acceptable`.
- Pass/fail: PASS.

### 4.5 Forecast Confidence

- Current value: `overall = 0.7169`, `spread_score = 0.9386`, `agreement_score = 1.0`, `context_coherence = 0.1178` (`finalize.json` `confidence`). Weighted formula `0.30×0.9386 + 0.40×1.0 + 0.30×0.1178 = 0.71692` (`src/forecasting/confidence.py:303`).
- Required threshold: none in the decision path. This object is only persisted in finalize (`stages.py:869`); it is never read by `DecisionEngine`, `ConfidenceEngine`, or `RiskRewardValidator`.
- The only coherence-based gate in the pipeline is `UncertaintyBudget.evaluate(..., coherence_threshold=0.30)` (`src/forecasting/decision_gate.py:57,60,65`), but `_risk_gate` passes a hardcoded `context_coherence=0.5` (`stages.py:378`) instead of the computed `0.1178`.
- Pass/fail: N/A (not gated). Fact: had the actual `0.1178` been passed, `0.1178 < 0.30` would set `coherence_ok=false` and `acceptable=false` (`decision_gate.py:60-65`).

### 4.6 Institutional Confidence — PRIMARY GATE

- Current value: `final_confidence = 0.315` (`finalize.json` `institutional_confidence=0.315`; driver `value=0.315`, `weight=0.30`).
- Computation: `ConfidenceComputer.compute` `final = positive_score × support_factor × (1 − min(penalty_score,1))`, clipped to `[0,1]` (`src/confidence_engine/computer.py:72-74`); uncapped in this run (no `oos_ece` param passed → `oos_cap=None`, `src/confidence_engine/engine.py:65,645-647`; GS test `all_answered=true` → no cap, `engine.py:63-64,137-163`). Clipped/capped at `LOW_CONFIDENCE_THRESHOLD=0.35` only as a lower clamp boundary, not applied here (`computer.py:29,124`).
- Required threshold: `confidence ≥ NO_TRADE_CONFIDENCE = 0.5` (`src/decision_engine/engine.py:33`).
- Gate: `if confidence < NO_TRADE_CONFIDENCE: return "NO_TRADE"` (`engine.py:258-259`).
- Pass/fail: **FAIL** (`0.315 < 0.5`).

### 4.7 Risk/Reward Validation

- Current value (selected base scenario): status `acceptable`, `risk_reward_ratio = 0.9529`, `expected_reward = 0.3633`, `expected_risk = 0.1147`, `maximum_downside = 0.2294`, `expected_upside = 0.7266`, `tail_risk = 0.3203`, `liquidity_risk = 0.2483`, `regime_risk = 1.0`, `volatility_impact = 0.6953` (`finalize.json` `risk_reward_summary`).
- Classification thresholds: `acceptable` iff `risk_reward_ratio ≤ ACCEPTABLE_RATIO_THRESHOLD=1.0` AND `expected_reward ≥ ACCEPTABLE_MIN_REWARD=0.15`; `reject` iff `ratio ≥ REJECT_RATIO_THRESHOLD=3.0` or `expected_reward < REJECT_MAX_REWARD=0.05`; else `borderline` (`src/risk_reward_validation/validator.py:26-29,180-189`). `0.9529 ≤ 1.0` ✓; `0.3633 ≥ 0.15` ✓.
- Decision-path gate: `if validation.risk_reward_ratio > NO_TRADE_RR_RATIO: return "NO_TRADE"`, `NO_TRADE_RR_RATIO=2.0` (`engine.py:35,260-261`).
- Pass/fail: PASS (classification `acceptable`; ratio `0.9529` does not exceed `2.0`, so the decision gate is not triggered).
- Fact: composite driver `risk_reward_quality = 0.6888` is the average across all three scenarios of `1 − min(ratio/10,1)` (`engine.py:193-201`), implying an average scenario ratio ≈ `3.11`; only the selected (base) scenario ratio is used by the `2.0` gate.

### 4.8 Bias Prevention

- Current value: `overall_severity = high`, `human_review_flag = true`, `total_confidence_impact = 0.65`, findings `[confirmation_bias, anchoring, groupthink, false_precision]` (`finalize.json` `metadata.bias_review`).
- Finding severities/impacts (`src/bias_prevention/detector.py`: confirmation `high` at `:206-208`; anchoring `medium` at `:222-231`; groupthink `medium` at `:385-400`; false_precision `low` at `:402-414`): `0.25 + 0.15 + 0.15 + 0.10 = 0.65` (`SEVERITY_IMPACT`, `src/bias_prevention/contracts.py:24-30`).
- Required threshold: findings with severity ∈ `HUMAN_REVIEW_SEVERITIES = {"high","critical"}` set `human_review_flag=true` (`contracts.py:32,186-188`).
- Gate: `apply_bias_review` downgrades a directional decision to `NO_TRADE` when `human_review_flag` is true (`contracts.py:153-194`, block branch `:174-181`); when the decision is already `NO_TRADE` it only appends the `BIAS REVIEW:` note (`:182-187`).
- Pass/fail: PASSED-THROUGH. In this run the decision was already `NO_TRADE`, so the `BLOCKED BY BIAS PREVENTION` branch was not taken; the note-branch was taken (`:182-187`). Fact: this gate would independently have blocked any BUY/SELL in this run (flag was `true`), but it is evaluated after `DecisionEngine.decide` (`stages.py:784-795`).

### 4.9 Forecast Validation

- Current value: `passed=false`, `sample_size=0`, metrics all `0.0`, note `"No aligned forecast-actual pairs available for validation"` (`finalize.json` `validation`).
- Required threshold: none; not consumed by the decision path (persisted only, `stages.py:870`).
- Pass/fail: N/A (not gated).

### 4.10 Risk Gate (pre-decision safety gate)

- Current value: `risk_decision.action = "proceed"`, `score = 0.106`; components `{regime_acceptable: true, uncertainty_acceptable: true, has_room_to_act: true, not_halted: true, not_caution: true}` (`finalize.json` `risk_decision`).
- Thresholds: `regime_mult ≥ 0.25` (`decision_gate.py:94`); `uncertainty.acceptable` (`decision_gate.py:95`); `scaling_factor ≥ min_scaling=0.30` (`decision_gate.py:82,89`); drawdown not halted/caution (`decision_gate.py:90-91`). Regime `LATE_CYCLE` multiplier `0.75` × `regime_confidence 0.3535 = 0.265125` (`decision_gate.py:26,36-46`). Uncertainty budget: hardcoded `context_coherence=0.5` (`stages.py:378`) ≥ `0.30`, `var_95=139.953` ≥ `−0.05`, `tail_index=null` → `tail_ok=true` (`decision_gate.py:51-71`). `score = 0.265125 × 0.40 × 1.0 = 0.10605` (`decision_gate.py:101-102`).
- Pass/fail: PASS (no block).

### 4.11 Recommendation

- Current value: `recommendation_action = "NO_TRADE"`, no entry/stop/target levels, `risk_pct=0.0` (recommender mirrors the decision; `src/trade_recommendation/recommender.py:46-47,92-118`).
- Pass/fail: N/A (derived, no additional gate).

## 5. First Gate That Makes BUY or SELL Impossible

**`src/decision_engine/engine.py:258` — `_determine_decision` institutional-confidence gate:**

```
if confidence < NO_TRADE_CONFIDENCE:   # engine.py:258  (NO_TRADE_CONFIDENCE = 0.5, engine.py:33)
    return "NO_TRADE"                  # engine.py:259
```

- Current value: `confidence = tc.final_confidence = 0.315`
- Required threshold: `≥ 0.5`
- Result: **FAIL → returns `NO_TRADE` before the bullish/bearish direction mapping (`engine.py:262-265`).**

This is the first gate in the decision path where a BUY or SELL becomes impossible. It is evaluated before the risk/reward `NO_TRADE_RR_RATIO` gate (`engine.py:260`), and before the bias-review consumption (`stages.py:795`). The risk/reward gate (`0.9529 ≤ 2.0`) and the pre-decision risk gate (`action=proceed`) both pass; the bias gate (`human_review_flag=true`) would also have blocked any BUY/SELL but is downstream and, in this run, only appended a note.

## 6. Composite Score Reproduction (fact check)

`0.30×0.315 + 0.20×0.6888 + 0.15×0.6094 + 0.15×0.8 + 0.10×0.5 + 0.10×0.0 = 0.0945 + 0.13776 + 0.09141 + 0.12 + 0.05 + 0.0 = 0.49367 → 0.4937` (`engine.py:203-211`). Matches `finalize.json` `composite_score=0.4937`.

## 7. Regime Facts

- `context.current_regime = "LATE_CYCLE"`, `regime_confidence = 0.3535`, `source_variable = "AutoARIMA"` (`finalize.json` `context`). `LATE_CYCLE` originates from the macro-regime detector (`src/knowledge/regime/macro_regime_detector.py:8,12`).
- `LATE_CYCLE` is not a key in `REGIME_EXPECTED_BIAS` (`src/counter_evidence/detector.py:19-26`), so `_regime_alignment` defaults expected bias to `"neutral"` and returns `0.0` for the bullish thesis (`src/confidence_engine/computer.py:102-109`). Driver `regime_alignment = 0.0` (weight `0.10`; contributes `0.0`).
- `LATE_CYCLE` is not in `INSTITUTIONAL_REGIMES` (`src/knowledge/regime/constants.py:10-17`), so `_regime_risk` returns `1.0` for the base-scenario regime path (`src/risk_reward_validation/validator.py:169-178`). Observed `regime_risk=1.0`.
- Regime multipliers include `LATE_CYCLE: 0.75` (`src/forecasting/decision_gate.py:26`).

## 8. Observable Limitations (facts)

- Per-thesis `confidence_inputs` (`avg_supporting_consensus`, `conflict_severity`, `raw_support`, `institutional_support`, `source_diversity`, `kr_quality`, `temporal_recency`, `missing_penalty`) are computed in-memory and are not persisted in run artifacts; the only thesis-level numbers persisted are the six `decision_drivers` and the bias review. The exact decomposition of `final_confidence=0.315` beyond the values in §4 is therefore not reproducible from run outputs alone.
- `finalize.json` `confidence` (forecast confidence) is computed (`_forecast_confidence`) but never consumed downstream.
