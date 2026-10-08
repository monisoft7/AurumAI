# AurumAI Institutional Daily Report

**Run date: runtime_20260828_161510**

## 1. Executive Summary

- **Decision:** NO\_TRADE
- **Decision confidence:** 0.5156
- **Event type:** CPI
- **Asset:** XAU/USD | **Horizon:** 12 months
- **Economic data:** data/economic/CPIAUCSL.csv
- **Gold data:** data/history/gold/gold.csv
- **Pipeline status:** completed with no errors (stages ok: 27)
- **Pipeline ID:** runtime\_20260828\_161510
- **Run timestamp:** 2026-08-28T14:18:32.395724+00:00
- **Wall time:** 201 s

## 2. Market Regime

- **Current regime:** LATE\_CYCLE
- **Regime confidence:** 0.3671 (36.71%)
- **Regime source variable:** AutoARIMA
- **Data date range:** 2015-01-02 to 2026-08-28
- **News mood:** n/a (confidence 0 (0.00%))
- **FOMC mood:** n/a (confidence 0 (0.00%))
- **Context timestamp:** 2026-08-28T14:17:40.145212+00:00

## 3. Key Economic Events

Focal event type analyzed: **CPI**. No recent economic events were recorded by the pipeline for this run.

## 4. Evidence Summary

- **Evidence quality:** value n/a | score n/a | weight n/a
- **Counter-evidence quality:** value n/a | score n/a | weight n/a

**Bias prevention review**

- **Bias review id:** bias-th\_61eca403b71a.v2
- **Overall severity:** critical
- **Total confidence impact:** 0.5 (50.00%)
- **Human review required:** true
- **Bias findings:** regime\_blindness, false\_precision

**Legacy pipeline evidence (for reference)**

- **Legacy evidence count:** 3
- **Legacy chain confidence:** 0.5404 (54.04%)
- **Legacy average return %:** 0.3923
- **Legacy reasoning chain:** reason\_CPI\_inflation\_pressure\_up

## 5. Institutional Thesis

- **Selected thesis id:** th\_61eca403b71a.v2
- **Selected thesis direction:** bearish
- **Theses evaluated:** 3
- **Rejected alternatives:** 2

Rejected alternative theses:

| Thesis id | Direction | Composite score | Rejection reason |
| --- | --- | --- | --- |
| th\_857957230262 | neutral | 0.5285 | lower composite score (0.5285) than selected thesis (0.5454) |
| th\_005391d6f262 | bullish | 0.5134 | lower composite score (0.5134) than selected thesis (0.5454) |

## 6. Confidence Assessment

- **Overall forecast confidence:** 0.7194 (71.94%)
- **Agreement score:** 1 (100.00%)
- **Context coherence:** 0.1224 (12.24%)
- **Spread score:** 0.9423 (94.23%)
- **Institutional confidence (decision):** 0.5156 (51.56%)
- **Institutional confidence driver:** value 0.5156 | score 0.2578 | weight 0.5

## 7. Scenario Analysis

- **Selected scenario id:** sc\_fc0f778d87bf
- **Selected scenario type:** bull
- **Scenario probability driver:** value 0.5 | score 0.0833 | weight 0.1667
- **Scenario detail:** sc\_fc0f778d87bf (bull, p=0.1832) (as recorded in the decision explanation)

## 8. Risk / Reward Summary

- **Risk/reward quality driver:** value 0.6127 | score 0.2042 | weight 0.3333
- **Risk/reward status:** borderline
- **Risk/reward ratio:** 2.9631

## 9. Final Institutional Decision

- **Decision:** NO\_TRADE
- **Decision id:** dec\_9593312c443f
- **Institutional confidence:** 0.5156 (51.56%)
- **Composite score:** 0.5454

**Decision drivers**

| Driver | Value | Score | Weight |
| --- | --- | --- | --- |
| institutional\_confidence | 0.5156 | 0.2578 | 0.5 |
| risk\_reward\_quality | 0.6127 | 0.2042 | 0.3333 |
| scenario\_probability | 0.5 | 0.0833 | 0.1667 |

**Decision explanation (verbatim)**

```
decision=NO_TRADE; selected_thesis=th_61eca403b71a.v2 (bearish); selected_scenario=sc_fc0f778d87bf (bull, p=0.1832); composite_score=0.5454; institutional_confidence=0.5156; risk_reward_status=borderline; risk_reward_ratio=2.9631; reason=selected thesis th_61eca403b71a.v2 blocked by risk/reward gate: ratio=2.9631 > 2.0 threshold | BIAS REVIEW: human review required (overall_severity=critical, findings=['regime_blindness', 'false_precision'])
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

- Gold ETF flow momentum reflecting investor sentiment; US dollar valuation channel through gold's dollar denomination accelerates
- bullish confirmation signals fire

## 12. Invalidation Conditions

- Counter-evidence from sets es\_inflation strengthens
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
| Overall severity | critical |
| Total confidence impact | 0.5 (50.00%) |
| Human review required | true |

## 14. Provenance Summary

**Decision provenance chain**

| Created by | Created at | Entity version |
| --- | --- | --- |
| W7 CounterEvidenceAssessor | 2026-08-28T14:18:32.173134+00:00 | 1.0.0 |
| W8 ThesisBuilder | 2026-08-28T14:18:32.173210+00:00 | 1.0.0 |
| W10 ThesisUpdater | 2026-08-28T14:18:32.158353+00:00 | 1.0.0 |
| W12 ScenarioGenerator | 2026-08-28T14:18:32.205072+00:00 | 1.0.0 |
| W12 RiskRewardValidator | 2026-08-28T14:18:32.212590+00:00 | 1.0.0 |
| W13 DecisionEngine | 2026-08-28T14:18:32.239628+00:00 | 1.0.0 |

**Stage execution records**

| Stage | Status | Duration (ms) |
| --- | --- | --- |
| ingest\_news | ok | 1835.9415 |
| ingest\_event | ok | 39520.062 |
| build\_legacy\_pipeline | ok | 3080.9754 |
| forecast | ok | 108816.6331 |
| position\_sizing | ok | 13.6986 |
| forecast\_validation | ok | 231.6714 |
| build\_context | ok | 54.3241 |
| risk\_measures | ok | 19.8599 |
| forecast\_confidence | ok | 406.3074 |
| technical\_research | ok | 1176.8305 |
| regime\_diagnosis | ok | 43286.4892 |
| risk\_gate | ok | 30.4033 |
| pre\_market\_scan | ok | 6999.9196 |
| signal\_assessment | ok | 27.5207 |
| event\_triage | ok | 15.3728 |
| evidence\_collection | ok | 19.7132 |
| evidence\_reasoning | ok | 1880.9712 |
| counter\_evidence | ok | 10.1957 |
| thesis\_construction | ok | 7.2714 |
| thesis\_update | ok | 11.6383 |
| scenario\_generation | ok | 0.7254 |
| risk\_reward\_validation | ok | 0.9002 |
| confidence\_engine | ok | 5.302 |
| bias\_prevention | ok | 12.9465 |
| decision\_engine | ok | 0.7444 |
| trade\_recommendation | ok | 138.9777 |
| finalize | ok | 1.9388 |

**Artifacts**

- knowledge.json
- lesson\_episodes.json
- lessons.csv
- regime\_diagnosis.json
- technical\_assessment.json
- trade\_recommendation.json

- **Pipeline ID:** runtime\_20260828\_161510
- **Output directory:** C:\\AurumAI\\AurumAI\\outputs\\2026-08-28\\runtime\_20260828\_161510

## 15. Execution Levels

**Recommendation:** NO\_TRADE (levels basis: not\_applicable\_no\_levels)

| Level | Value |
| --- | --- |
| Levels | none emitted for this decision class |

**Risk / reward**

| Measure | Value | Basis |
| --- | --- | --- |
| Market reward:risk | n/a | ATR-anchored levels |
| W12 conviction ratio | 2.9631 | conviction proxy (W12) |

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
| Confidence | 0.5156 |
| Why (gate reason) | risk\_reward\_ratio\_above\_threshold |
| Selected thesis | th\_61eca403b71a.v2 |
| Regime | LATE\_CYCLE |
| Technical confirmations | trend bullish / momentum bullish / structure uptrend (confidence 0.8696) |
| Technical conflicts | none recorded |
| Market risk | reference 4660.60009765625 \| ATR 80.189956 \| market RR unavailable \| risk gate proceed |
| Execution | no absolute levels emitted for this decision class |
| News health | status ok \| articles 20 \| directional 2 \| unknown 18 \| sentiment skipped\_none |
| Calibration | dormant (samples 0, OOS ECE unavailable) |
| Bias / governance | severity critical \| human review True \| provenance ok |
| Outcome tracking | unavailable \| decision correct unavailable \| abstention verdict unavailable \| realized return unavailable |
| What remains unobservable | none recorded in this summary |
| Provenance | git c5aa5f7 \| run runtime\_20260828\_161510 |

---

Generated by scripts/generate_institutional_report.py at 2026-08-28T14:18:33+00:00 from C:\AurumAI\AurumAI\outputs\2026-08-28\runtime_20260828_161510