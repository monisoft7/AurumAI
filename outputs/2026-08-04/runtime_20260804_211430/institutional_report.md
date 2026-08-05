# AurumAI Institutional Daily Report

**Run date: runtime_20260804_211430**

## 1. Executive Summary

- **Decision:** NO\_TRADE
- **Decision confidence:** 0.3145
- **Event type:** CPI
- **Asset:** XAU/USD | **Horizon:** 12 months
- **Economic data:** data/economic/CPIAUCSL.csv
- **Gold data:** data/history/gold/gold.csv
- **Pipeline status:** completed with no errors (stages ok: 25)
- **Pipeline ID:** runtime\_20260804\_211430
- **Run timestamp:** 2026-08-04T19:15:25.637642+00:00
- **Wall time:** 55 s

## 2. Market Regime

- **Current regime:** LATE\_CYCLE
- **Regime confidence:** 0.3535 (35.35%)
- **Regime source variable:** AutoARIMA
- **Data date range:** 2015-01-02 to 2025-12-31
- **News mood:** n/a (confidence 0 (0.00%))
- **FOMC mood:** n/a (confidence 0 (0.00%))
- **Context timestamp:** 2026-08-04T19:15:25.262284+00:00

## 3. Key Economic Events

Focal event type analyzed: **CPI**. No recent economic events were recorded by the pipeline for this run.

## 4. Evidence Summary

- **Evidence quality:** value 0.6087 | score 0.0913 | weight 0.15
- **Counter-evidence quality:** value 0.8 | score 0.12 | weight 0.15

**Bias prevention review**

- **Bias review id:** bias-th\_5bb77c3274de.v2
- **Overall severity:** high
- **Total confidence impact:** 0.65 (65.00%)
- **Human review required:** true
- **Bias findings:** confirmation\_bias, anchoring, groupthink, false\_precision

**Legacy pipeline evidence (for reference)**

- **Legacy evidence count:** 3
- **Legacy chain confidence:** 0.6001 (60.01%)
- **Legacy average return %:** 0.906
- **Legacy reasoning chain:** reason\_CPI\_inflation\_pressure\_down

## 5. Institutional Thesis

- **Selected thesis id:** th\_5bb77c3274de.v2
- **Selected thesis direction:** bullish
- **Theses evaluated:** 1
- **Rejected alternatives:** 0

## 6. Confidence Assessment

- **Overall forecast confidence:** 0.7223 (72.23%)
- **Agreement score:** 1 (100.00%)
- **Context coherence:** 0.1178 (11.78%)
- **Spread score:** 0.9565 (95.65%)
- **Institutional confidence (decision):** 0.3145 (31.45%)
- **Institutional confidence driver:** value 0.3145 | score 0.0944 | weight 0.3

## 7. Scenario Analysis

- **Selected scenario id:** sc\_dcf12a963ade
- **Selected scenario type:** base
- **Scenario probability driver:** value 0.5 | score 0.05 | weight 0.1
- **Scenario detail:** sc\_dcf12a963ade (base, p=0.5) (as recorded in the decision explanation)

## 8. Risk / Reward Summary

- **Risk/reward quality driver:** value 0.6886 | score 0.1377 | weight 0.2
- **Risk/reward status:** acceptable
- **Risk/reward ratio:** 0.9543

## 9. Final Institutional Decision

- **Decision:** NO\_TRADE
- **Decision id:** dec\_0720d8d08458
- **Institutional confidence:** 0.3145 (31.45%)
- **Composite score:** 0.4934

**Decision drivers**

| Driver | Value | Score | Weight |
| --- | --- | --- | --- |
| institutional\_confidence | 0.3145 | 0.0944 | 0.3 |
| risk\_reward\_quality | 0.6886 | 0.1377 | 0.2 |
| evidence\_quality | 0.6087 | 0.0913 | 0.15 |
| counter\_evidence\_quality | 0.8 | 0.12 | 0.15 |
| scenario\_probability | 0.5 | 0.05 | 0.1 |
| regime\_alignment | 0 | 0 | 0.1 |

**Decision explanation (verbatim)**

```
decision=NO_TRADE; selected_thesis=th_5bb77c3274de.v2 (bullish); selected_scenario=sc_dcf12a963ade (base, p=0.5); composite_score=0.4934; institutional_confidence=0.3145; risk_reward_status=acceptable; risk_reward_ratio=0.9543; reason=no thesis clears institutional confidence and risk/reward thresholds | BIAS REVIEW: human review required (overall_severity=high, findings=['confirmation_bias', 'anchoring', 'groupthink', 'false_precision'])
```

## 10. Trade Recommendation

The institutional decision is **NO\_TRADE**; no trade action is recommended.

**Forecast risk gate (informs sizing)**

- **Risk gate action:** proceed (score 0.053 (5.30%))
- **Risk gate reason:** All risk gates pass. Full allocation advised.
- **regime_acceptable:** true
- **uncertainty_acceptable:** true
- **has_room_to_act:** true
- **not_halted:** true
- **not_caution:** true

**Position sizing**

| Field | Value |
| --- | --- |
| Scaling factor | 0.4326 (43.26%) |
| Target volatility | 0.15 |
| Current volatility | 0.3468 |
| Drawdown state | normal |
| Kelly cap | n/a |

**Risk budget**

| Field | Value |
| --- | --- |
| Method | risk\_parity |
| Weights | 0.4641, 0.5359 |
| Risk contributions | 0.5, 0.5 |

## 11. Preconditions

- Gold ETF flow momentum reflecting investor sentiment; Multi-factor cross-asset transmission affecting gold price continues to develop as expected

## 12. Invalidation Conditions

- No specific invalidating conditions identified

## 13. Major Risks

**Forecast risk measures**

| Field | Value |
| --- | --- |
| VaR 95 | 97.2374 |
| VaR 99 | 84.2032 |
| CVaR 95 | 80.9446 |
| Tail index | not detected (null) |
| Method | historical |

**Forecast validation**

| Field | Value |
| --- | --- |
| Passed | false |
| Sample size | 0 |
| Strategy | walk\_forward |
| Notes | No aligned forecast- actual pairs available for validation |

**Validation metrics**

| Metric | Value |
| --- | --- |
| RMSE | 0 |
| MAE | 0 |
| MAPE | 0 |
| Coverage | 0 (0.00%) |
| Directional accuracy | 0 (0.00%) |

**Risk gate components**

| Component | Value |
| --- | --- |
| regime\_acceptable | true |
| uncertainty\_acceptable | true |
| has\_room\_to\_act | true |
| not\_halted | true |
| not\_caution | true |

**Bias review**

| Field | Value |
| --- | --- |
| Overall severity | high |
| Total confidence impact | 0.65 (65.00%) |
| Human review required | true |

## 14. Provenance Summary

**Decision provenance chain**

| Created by | Created at | Entity version |
| --- | --- | --- |
| W7 CounterEvidenceAssessor | 2026-08-04T19:15:25.551482+00:00 | 1.0.0 |
| W8 ThesisBuilder | 2026-08-04T19:15:25.551528+00:00 | 1.0.0 |
| W10 ThesisUpdater | 2026-08-04T19:15:25.539180+00:00 | 1.0.0 |
| W12 ScenarioGenerator | 2026-08-04T19:15:25.587122+00:00 | 1.0.0 |
| W12 RiskRewardValidator | 2026-08-04T19:15:25.602013+00:00 | 1.0.0 |
| W13 DecisionEngine | 2026-08-04T19:15:25.622835+00:00 | 1.0.0 |

**Stage execution records**

| Stage | Status | Duration (ms) |
| --- | --- | --- |
| ingest\_news | ok | 4.642 |
| pre\_market\_scan | ok | 13634.2382 |
| ingest\_event | ok | 33482.5778 |
| signal\_assessment | ok | 81.2574 |
| build\_legacy\_pipeline | ok | 1050.6402 |
| forecast | ok | 20943.6968 |
| risk\_measures | ok | 0.8378 |
| event\_triage | ok | 20.6168 |
| build\_context | ok | 136.0001 |
| forecast\_validation | ok | 231.0166 |
| forecast\_confidence | ok | 314.111 |
| position\_sizing | ok | 6.1921 |
| risk\_gate | ok | 7.437 |
| evidence\_collection | ok | 81.4475 |
| evidence\_reasoning | ok | 12.1029 |
| counter\_evidence | ok | 9.9428 |
| thesis\_construction | ok | 10.6057 |
| thesis\_update | ok | 12.6261 |
| scenario\_generation | ok | 19.982 |
| confidence\_engine | ok | 3.5889 |
| risk\_reward\_validation | ok | 11.7686 |
| bias\_prevention | ok | 15.3468 |
| decision\_engine | ok | 0.3406 |
| finalize | ok | 0.0799 |
| trade\_recommendation | ok | 8.9396 |

**Artifacts**

- knowledge.json
- lessons.csv

- **Pipeline ID:** runtime\_20260804\_211430
- **Output directory:** C:\\AurumAI\\AurumAI\\outputs\\2026-08-04\\runtime\_20260804\_211430

---

Generated by scripts/generate_institutional_report.py at 2026-08-04T19:17:40+00:00 from C:\AurumAI\AurumAI\outputs\2026-08-04\runtime_20260804_211430