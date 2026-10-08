# AurumAI Institutional Daily Report

**Run date: runtime_20260828_124429**

## 1. Executive Summary

- **Decision:** NO\_TRADE
- **Decision confidence:** 0.4992
- **Event type:** CPI
- **Asset:** XAU/USD | **Horizon:** 12 months
- **Economic data:** data/economic/CPIAUCSL.csv
- **Gold data:** data/history/gold/gold.csv
- **Pipeline status:** completed with no errors (stages ok: 27)
- **Pipeline ID:** runtime\_20260828\_124429
- **Run timestamp:** 2026-08-28T10:46:40.091022+00:00
- **Wall time:** 129.9 s

## 2. Market Regime

- **Current regime:** LATE\_CYCLE
- **Regime confidence:** 0.3671 (36.71%)
- **Regime source variable:** AutoARIMA
- **Data date range:** 2015-01-02 to 2026-08-28
- **News mood:** n/a (confidence 0 (0.00%))
- **FOMC mood:** n/a (confidence 0 (0.00%))
- **Context timestamp:** 2026-08-28T10:46:09.507323+00:00

## 3. Key Economic Events

Focal event type analyzed: **CPI**. No recent economic events were recorded by the pipeline for this run.

## 4. Evidence Summary

- **Evidence quality:** value n/a | score n/a | weight n/a
- **Counter-evidence quality:** value n/a | score n/a | weight n/a

**Bias prevention review**

- **Bias review id:** bias-th\_08765d8c75a0.v2
- **Overall severity:** medium
- **Total confidence impact:** 0.25 (25.00%)
- **Human review required:** false
- **Bias findings:** single\_source\_bias, false\_precision

**Legacy pipeline evidence (for reference)**

- **Legacy evidence count:** 3
- **Legacy chain confidence:** 0.5404 (54.04%)
- **Legacy average return %:** 0.3923
- **Legacy reasoning chain:** reason\_CPI\_inflation\_pressure\_up

## 5. Institutional Thesis

- **Selected thesis id:** th\_08765d8c75a0.v2
- **Selected thesis direction:** neutral
- **Theses evaluated:** 3
- **Rejected alternatives:** 2

Rejected alternative theses:

| Thesis id | Direction | Composite score | Rejection reason |
| --- | --- | --- | --- |
| th\_69d567c87d73 | bullish | 0.5185 | lower composite score (0.5185) than selected thesis (0.5347) |
| th\_3a6a4a6c3b1f | bearish | 0.4068 | no acceptable or borderline scenario: all scenarios rejected by W12 risk/reward validation (best status=reject) |

## 6. Confidence Assessment

- **Overall forecast confidence:** 0.7194 (71.94%)
- **Agreement score:** 1 (100.00%)
- **Context coherence:** 0.1224 (12.24%)
- **Spread score:** 0.9423 (94.23%)
- **Institutional confidence (decision):** 0.4992 (49.92%)
- **Institutional confidence driver:** value 0.4992 | score 0.2496 | weight 0.5

## 7. Scenario Analysis

- **Selected scenario id:** sc\_ab08eeaea1e7
- **Selected scenario type:** base
- **Scenario probability driver:** value 0.5 | score 0.0833 | weight 0.1667
- **Scenario detail:** sc\_ab08eeaea1e7 (base, p=0.5) (as recorded in the decision explanation)

## 8. Risk / Reward Summary

- **Risk/reward quality driver:** value 0.6052 | score 0.2017 | weight 0.3333
- **Risk/reward status:** borderline
- **Risk/reward ratio:** 1.8498

Risk/reward validation notes from rejected alternatives:

- no acceptable or borderline scenario: all scenarios rejected by W12 risk/reward validation (best status=reject)

## 9. Final Institutional Decision

- **Decision:** NO\_TRADE
- **Decision id:** dec\_f7728781bad4
- **Institutional confidence:** 0.4992 (49.92%)
- **Composite score:** 0.5347

**Decision drivers**

| Driver | Value | Score | Weight |
| --- | --- | --- | --- |
| institutional\_confidence | 0.4992 | 0.2496 | 0.5 |
| risk\_reward\_quality | 0.6052 | 0.2017 | 0.3333 |
| scenario\_probability | 0.5 | 0.0833 | 0.1667 |

**Decision explanation (verbatim)**

```
decision=NO_TRADE; selected_thesis=th_08765d8c75a0.v2 (neutral); selected_scenario=sc_ab08eeaea1e7 (base, p=0.5); composite_score=0.5347; institutional_confidence=0.4992; risk_reward_status=borderline; risk_reward_ratio=1.8498; reason=selected thesis th_08765d8c75a0.v2 blocked by conviction gate: institutional_confidence=0.4992 < 0.5 threshold
```

## 10. Trade Recommendation

The institutional decision is **NO\_TRADE**; no trade action is recommended.

**Forecast risk gate (informs sizing)**

- **Risk gate action:** proceed (score 0.1101 (11.01%))
- **Risk gate reason:** All risk gates pass. Full allocation advised.
- **regime_acceptable:** true
- **uncertainty_acceptable:** true
- **has_room_to_act:** true
- **not_halted:** true
- **not_caution:** true

**Position sizing**

| Field | Value |
| --- | --- |
| Scaling factor | 1 (100.00%) |
| Target volatility | 0.15 |
| Current volatility | 0.0043 |
| Drawdown state | normal |
| Kelly cap | n/a |

**Risk budget**

| Field | Value |
| --- | --- |
| Method | risk\_parity |
| Weights | 1 |
| Risk contributions | 1 |

## 11. Preconditions

- Multi-factor cross-asset transmission affecting gold price continues to develop as expected

## 12. Invalidation Conditions

- Current regime conflicts with thesis direction
- Regime-dependent evidence weakening thesis
- Missing evidence channels: CB\_GOLD

## 13. Major Risks

**Forecast risk measures**

| Field | Value |
| --- | --- |
| VaR 95 | 142.5123 |
| VaR 99 | 122.3201 |
| CVaR 95 | 117.2721 |
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
| Overall severity | medium |
| Total confidence impact | 0.25 (25.00%) |
| Human review required | false |

## 14. Provenance Summary

**Decision provenance chain**

| Created by | Created at | Entity version |
| --- | --- | --- |
| W7 CounterEvidenceAssessor | 2026-08-28T10:46:39.966794+00:00 | 1.0.0 |
| W8 ThesisBuilder | 2026-08-28T10:46:39.966845+00:00 | 1.0.0 |
| W10 ThesisUpdater | 2026-08-28T10:46:39.956740+00:00 | 1.0.0 |
| W12 ScenarioGenerator | 2026-08-28T10:46:39.986966+00:00 | 1.0.0 |
| W12 RiskRewardValidator | 2026-08-28T10:46:39.990265+00:00 | 1.0.0 |
| W13 DecisionEngine | 2026-08-28T10:46:40.007311+00:00 | 1.0.0 |

**Stage execution records**

| Stage | Status | Duration (ms) |
| --- | --- | --- |
| ingest\_news | ok | 3784.6858 |
| ingest\_event | ok | 25460.3255 |
| build\_legacy\_pipeline | ok | 3031.123 |
| forecast | ok | 73819.3543 |
| build\_context | ok | 38.3529 |
| forecast\_validation | ok | 221.0059 |
| risk\_measures | ok | 107.4274 |
| position\_sizing | ok | 20.1838 |
| forecast\_confidence | ok | 188.5627 |
| technical\_research | ok | 838.9169 |
| regime\_diagnosis | ok | 23705.4503 |
| risk\_gate | ok | 3.5369 |
| pre\_market\_scan | ok | 5616.9696 |
| signal\_assessment | ok | 15.5441 |
| event\_triage | ok | 7.9197 |
| evidence\_collection | ok | 11.5085 |
| evidence\_reasoning | ok | 1110.5745 |
| counter\_evidence | ok | 5.453 |
| thesis\_construction | ok | 5.6228 |
| thesis\_update | ok | 6.1493 |
| scenario\_generation | ok | 0.4643 |
| risk\_reward\_validation | ok | 0.7851 |
| confidence\_engine | ok | 3.0757 |
| bias\_prevention | ok | 6.8115 |
| decision\_engine | ok | 0.6545 |
| trade\_recommendation | ok | 71.8296 |
| finalize | ok | 1.5532 |

**Artifacts**

- knowledge.json
- lesson\_episodes.json
- lessons.csv
- regime\_diagnosis.json
- technical\_assessment.json
- trade\_recommendation.json

- **Pipeline ID:** runtime\_20260828\_124429
- **Output directory:** C:\\AurumAI\\AurumAI\\outputs\\2026-08-28\\runtime\_20260828\_124429

## 15. Execution Levels

**Recommendation:** NO\_TRADE (levels basis: not\_applicable\_no\_levels)

| Level | Value |
| --- | --- |
| Levels | none emitted for this decision class |

**Risk / reward**

| Measure | Value | Basis |
| --- | --- | --- |
| Market reward:risk | n/a | ATR-anchored levels |
| W12 conviction ratio | 1.8498 | conviction proxy (W12) |

The W12 conviction ratio measures thesis-conviction quality; the market reward:risk ratio is computed from the actual ATR-anchored entry/stop/target levels. They are different measures and are reported side by side.

## 16. News Intelligence

News intelligence channel state (ingest_news stage payload, verbatim). An explicit non-ok status means the news day is not a healthy empty feed.

| Field | Value |
| --- | --- |
| Status | ok |
| Reason | — |
| Articles ingested | 20 |
| Duplicates | 0 |
| Malformed skipped | 0 |
| Excluded after as\_of | 0 |
| FOMC status | ok |
| FOMC events | 2 |
| Sentiment status | skipped\_none |

## 17. DAILY INSTITUTIONAL SNAPSHOT

One-page operational snapshot built from ``daily_operational_summary.json`` (additive; no decision recalculation).

| Question | Answer |
| --- | --- |
| What happened | CPI |
| What AurumAI thinks (decision) | NO\_TRADE |
| Confidence | 0.4992 |
| Why (gate reason) | confidence\_below\_threshold |
| Selected thesis | th\_08765d8c75a0.v2 |
| Regime | LATE\_CYCLE |
| Technical confirmations | trend bullish / momentum bullish / structure uptrend (confidence 0.8696) |
| Technical conflicts | none recorded |
| Market risk | reference 4660.60009765625 \| ATR 80.189956 \| market RR unavailable \| risk gate proceed |
| Execution | unavailable \| tp1 unavailable \| tp2 unavailable |
| News health | status ok \| articles 20 \| directional 2 \| unknown 18 \| sentiment skipped\_none |
| Calibration | dormant (samples 0, OOS ECE unavailable) |
| Bias / governance | severity medium \| human review False \| provenance ok |
| Outcome tracking | pending \| decision correct unavailable \| abstention verdict unevaluable \| realized return unavailable |
| What remains unobservable | outcome pending (horizon not elapsed) |
| Provenance | git 424c532 \| run runtime\_20260828\_124429 |

---

Generated by scripts/generate_institutional_report.py at 2026-08-28T14:13:06+00:00 from C:\AurumAI\AurumAI\outputs\2026-08-28\runtime_20260828_124429