# OPERATIONAL VALIDATION RUN #001

Execution command: `python run.py`

Runtime directory: `C:\AurumAI\AurumAI\outputs\2026-08-08\runtime_20260808_224002`

Checkpoint directory used for intermediate stage trace: `C:\Users\THE BLU WALF\AppData\Local\Temp\aurumai_checkpoints\runtime_20260808_224002`

## Stage Completion

Result: successful runtime.

- `summary.json.success`: `true`
- `summary.json.stage_counts.ok`: `26`
- `summary.json.failed_stages`: `[]`
- `summary.json.errors`: `[]`
- `runtime/run_registry.jsonl.exit_code`: `0`
- `runtime/run_registry.jsonl.pipeline_status`: `success`

All 26/26 stages completed successfully.

## OI Second-Observation Path

Previous gold OI state before execution:

- Source checked: tracked pre-run content of `data/economic/gold_oi_state.json`
- Timestamp: `2026-08-08T17:57:58.629825+00:00`
- `open_interest`: `298095.0`

Current gold OI state after execution:

- Source checked: current `data/economic/gold_oi_state.json`
- Timestamp: `2026-08-08T20:42:54.380100+00:00`
- `open_interest`: `298095.0`

Calculated OI change:

- Formula: `(298095.0 - 298095.0) / 298095.0 * 100`
- `open_interest_change_pct`: `0.0`

Producer validation:

- The producer path is `PositioningDataFetcher._fetch_open_interest`.
- The live field consumed is `Ticker("GC=F").get_info()["openInterest"]`.
- The traded `Volume` field is not used as an OI substitute in the OI calculation.
- The value reached `PreMarketBriefing.positioning_snapshot.open_interest_change_pct=0.0`.
- The value reached `SignalAssessment.volume_flow` through the positioning/overnight volume-flow inputs. Because OI delta was exactly `0.0`, the volume-flow criterion did not print an OI detail line; ETF flow was the active confirming component.

## Actual Runtime Chain

Actual chain observed:

`OI / market data -> SignalAssessment -> Evidence -> CounterEvidence -> Thesis -> Confidence -> Scenario -> RiskReward -> Decision`

The chain is present in runtime checkpoints and final output:

- OI / market data: `pre_market_scan.json`
- SignalAssessment: `signal_assessment.json`
- Evidence: `evidence_collection.json`, `evidence_reasoning.json`
- CounterEvidence: `counter_evidence.json`
- Thesis: `thesis_construction.json`, `thesis_update.json`
- Confidence: `confidence_engine.json`
- Scenario: `scenario_generation.json`
- RiskReward: `risk_reward_validation.json`
- Decision: `decision_engine.json`, `finalize.json`, `outcome.json`

## SignalAssessment Values

Runtime regime propagated into SignalAssessment:

- `regime`: `INFLATIONARY`
- `regime_confidence`: `0.6`

Classifications:

- `obs_XAU/USD_20260808`: `Weak Signal`, confidence `0.5`; passed `breadth`, `volume_flow`; volume-flow detail `ETF accumulating +2.3%; ETF momentum: accumulating`
- `obs_DXY_20260808`: `Watch`, confidence `0.3`; passed `breadth`
- `obs_S&P 500 Futures_20260808`: `Noise`, confidence `0.8`
- `obs_Brent Crude_20260808`: `Ignore`, confidence `0.9`
- `obs_EUR/USD_20260808`: `Ignore`, confidence `0.9`
- `obs_USD/JPY_20260808`: `Ignore`, confidence `0.9`
- `obs_US10Y Real Yield_20260808`: `Noise`, confidence `0.8`
- `obs_US10Y Nominal Yield_20260808`: `Ignore`, confidence `0.9`
- `obs_Breakeven Inflation_20260808`: `Noise`, confidence `0.8`
- `obs_positioning_20260808`: `Weak Signal`, confidence `0.5`; passed `breadth`, `volume_flow`; change_pct `2.26`
- `obs_anomaly_XAU/USD_template_violation_gold_and_real_yields_moving_in_same_direction_negative_correlation_expected`: `Watch`, confidence `0.3`

Collection counts:

- `total_classified`: `11`
- `signals_count`: `0`
- `weak_signals_count`: `2`
- `watch_count`: `2`
- `filtered_noise_count`: `3`
- `filtered_ignore_count`: `4`

## Evidence Values

Evidence items: `4`

- `ev_kr_synthetic_obs_XAU/USD_20260808_20260808_204254`
  - `source_kr_id`: `kr_synthetic_obs_XAU/USD_20260808`
  - `event_type`: `GENERAL`
  - `bias`: `bullish`
  - `base_confidence`: `0.5`
  - `regime_weight`: `0.6`
  - `composite_weight`: `0.3`
  - `source_label`: `overnight_price`
- `ev_kr_synthetic_obs_DXY_20260808_20260808_204254`
  - `source_kr_id`: `kr_synthetic_obs_DXY_20260808`
  - `event_type`: `USD_FX`
  - `bias`: `bearish`
  - `base_confidence`: `0.3`
  - `regime_weight`: `0.6`
  - `composite_weight`: `0.18`
  - `source_label`: `overnight_price`
- `ev_kr_synthetic_obs_positioning_20260808_20260808_204254`
  - `source_kr_id`: `kr_synthetic_obs_positioning_20260808`
  - `event_type`: `ETF_FLOW`
  - `bias`: `bullish`
  - `base_confidence`: `0.5`
  - `regime_weight`: `0.6`
  - `composite_weight`: `0.3`
  - `source_label`: `positioning`
- `ev_kr_synthetic_obs_anomaly_XAU/USD_template_violation_gold_and_real_yields_moving_in_same_direction_negative_correlation_expected_20260808_204254`
  - `source_kr_id`: `kr_synthetic_obs_anomaly_XAU/USD_template_violation_gold_and_real_yields_moving_in_same_direction_negative_correlation_expected`
  - `event_type`: `GENERAL`
  - `bias`: `bullish`
  - `base_confidence`: `0.3`
  - `regime_weight`: `0.6`
  - `composite_weight`: `0.18`
  - `source_label`: `anomaly_flag`

Evidence reasoning:

- `total_evidence_sets`: `3`
- `total_evidence_items`: `4`
- `duplicates_removed`: `0`

Evidence-set weights:

- `es_general`: `event_type=GENERAL`, `bias=bullish`, `items=2`, `net_institutional_weight=0.4334`, `consensus_score=1.0`, `conflict_score=0.0`, `duplicates_removed=0`
- `es_usd_fx`: `event_type=USD_FX`, `bias=bearish`, `items=1`, `net_institutional_weight=0.4369`, `consensus_score=1.0`, `conflict_score=0.0`, `duplicates_removed=0`
- `es_etf_flow`: `event_type=ETF_FLOW`, `bias=bullish`, `items=1`, `net_institutional_weight=0.65`, `consensus_score=1.0`, `conflict_score=0.0`, `duplicates_removed=0`

## CounterEvidence Values

- `related_set_ids`: `es_general`, `es_usd_fx`, `es_etf_flow`
- `supporting_set_ids`: `es_general`, `es_etf_flow`
- `contradicting_set_ids`: `es_usd_fx`
- `missing_evidence`: `CB_GOLD`
- `bias_flags`: `regime_conflict`, `missing_evidence`, `cross_set_conflict`
- `conflict_severity`: `0.1667`
- `confidence_penalty`: `0.2667`
- `regime_conflict`: `True`

## Thesis Values

Constructed theses:

- Primary bullish thesis `th_2f89dd995d9e`
  - `supporting_set_ids`: `es_general`, `es_etf_flow`
  - `counter_evidence_ids`: `es_usd_fx`
  - `institutional_support`: `0.3972`
  - `raw_support`: `0.5417`
  - `avg_supporting_weight`: `0.5417`
  - `avg_supporting_consensus`: `1.0`
- Bearish thesis `th_38b7db83cf86`
  - `supporting_set_ids`: `es_usd_fx`
  - `institutional_support`: `0.3204`
- Neutral thesis `th_418f070c4e63`
  - `institutional_support`: `0.0`

Updated thesis:

- `updated_thesis`: `th_2f89dd995d9e.v2`
- `direction`: `bullish`
- `supporting_set_ids`: `es_general`, `es_etf_flow`
- `counter_evidence_ids`: `es_usd_fx`
- `institutional_support`: `0.3972`
- `action`: `no_change`
- `confidence_delta`: `0.0`
- `changed_assumptions`: `missing evidence channels`

## Institutional Confidence

- `confidence_id`: `cf_8a35d1a38a67`
- `primary_thesis_id`: `th_2f89dd995d9e.v2`
- `final_confidence`: `0.2494`
- `remaining_uncertainty`: `0.7506`
- `reliability_category`: `very_low`

Positive contributors:

- `evidence_quality`: value `0.5417`, weight `0.25`
- `evidence_consensus`: value `1.0`, weight `0.25`
- `regime_alignment`: value `1.0`, weight `0.15`
- `source_diversity`: value `0.6667`, weight `0.15`
- `knowledge_record_quality`: value `1.0`, weight `0.1`
- `temporal_recency`: value `1.0`, weight `0.1`

Negative contributors and penalties:

- `counter_evidence`: value `0.1667`, weight `0.35`, penalty `0.0583`
- `missing_evidence`: value `0.3333333333333333`, weight `0.25`, penalty `0.0833`
- `internal_consistency`: value `0.2667`, weight `0.4`, penalty `0.1067`

Meta-evidence:

- `w6_evidence_consumed`: `True`
- `w12_downside_case_consumed`: `True`
- `oos_ece_consumed`: `False`

## Scenario Values

Scenario generation:

- `scenario_generation_id`: `sg_5d5d757f2f5c`
- `confidence_id`: `cf_fallback_update-th_2f89dd995d9e-v2`
- `confidence_source`: `thesis_support`
- `total_scenarios`: `3`
- Probability consistency for `th_2f89dd995d9e.v2`: `1.0`

Scenarios:

- Base `sc_cb61e6f8e57b`: probability `0.5`, expected_direction `bullish`, regime_path `INFLATIONARY`
- Bull `sc_bc34d00ec7df`: probability `0.3147`, expected_direction `bullish`, regime_path `INFLATIONARY -> NORMAL_GROWTH`
- Bear `sc_d38aff916a48`: probability `0.1853`, expected_direction `bearish`, regime_path `INFLATIONARY -> STAGFLATIONARY`

## RiskReward Values

Validation summary:

- `acceptable`: `1`
- `borderline`: `1`
- `reject`: `1`

Selected base scenario `sc_cb61e6f8e57b`:

- `validation_status`: `acceptable`
- `expected_reward`: `0.289`
- `expected_risk`: `0.1444`
- `risk_reward_ratio`: `0.9682`
- `maximum_downside`: `0.2888`
- `expected_upside`: `0.578`
- `volatility_impact`: `0.4514`
- `regime_risk`: `0.3`
- `liquidity_risk`: `0.3733`
- `tail_risk`: `0.5514`
- Reason: expected reward exceeds expected risk with sufficient margin

Other scenarios:

- Bull `sc_bc34d00ec7df`: `borderline`, expected_reward `0.1819`, expected_risk `0.0909`, risk_reward_ratio `1.8862`, maximum_downside `0.2888`, expected_upside `0.578`, volatility_impact `0.6764`, regime_risk `0.75`, liquidity_risk `0.3733`, tail_risk `0.5514`
- Bear `sc_d38aff916a48`: `reject`, expected_reward `0.0428`, expected_risk `0.1338`, risk_reward_ratio `8.5164`, maximum_downside `0.722`, expected_upside `0.2312`, volatility_impact `0.6764`, regime_risk `0.75`, liquidity_risk `0.3733`, tail_risk `0.5514`

## Decision Values

Institutional decision:

- `decision_id`: `dec_af8df2150978`
- `decision`: `NO_TRADE`
- `selected_thesis_id`: `th_2f89dd995d9e.v2`
- `selected_scenario_id`: `sc_cb61e6f8e57b`
- `institutional_confidence`: `0.2494`
- `composite_score`: `0.5403`
- `selected_thesis_direction`: `bullish`
- `selected_scenario_type`: `base`

Decision drivers:

- `institutional_confidence`: value `0.2494`, weight `0.3`, score `0.0748`
- `risk_reward_quality`: value `0.621`, weight `0.2`, score `0.1242`
- `evidence_quality`: value `0.5417`, weight `0.15`, score `0.0813`
- `counter_evidence_quality`: value `0.7333`, weight `0.15`, score `0.11`
- `scenario_probability`: value `0.5`, weight `0.1`, score `0.05`
- `regime_alignment`: value `1.0`, weight `0.1`, score `0.1`

Bias review applied:

- `overall_severity`: `critical`
- `total_confidence_impact`: `0.5`
- `human_review_flag`: `True`
- `findings`: `regime_blindness`, `false_precision`

RiskDecision, separately:

- `action`: `proceed`
- `score`: `0.106`
- `reason`: `All risk gates pass. Full allocation advised.`
- Components: `regime_acceptable=True`, `uncertainty_acceptable=True`, `has_room_to_act=True`, `not_halted=True`, `not_caution=True`

## Material Fallbacks, Defaults, Synthetic Values

Material participants:

- `source_kr_id` values are synthetic for all four evidence items. These are material because evidence provenance and grouping use them.
- COT positioning defaults to `cot_z_score=0.0`, `cot_regime=neutral`; this materially participates in the positioning observation persistence criterion and positioning snapshot.
- GOFO defaults to `gofo_rate=0.0`; this is material only insofar as it enters the positioning snapshot, though no downstream scoring in this run depended on GOFO.
- News inputs are empty, causing `narrative_fit=0.0` with detail `no news headlines available` across market observations. This materially suppresses narrative-fit criteria.
- Several instruments have unavailable sigma values represented as `nan`; those materially cause magnitude criteria to fail for real yield and breakeven observations.
- Scenario generation used `confidence_source=thesis_support` and `confidence_id=cf_fallback_update-th_2f89dd995d9e-v2`. This is material because scenario probabilities were generated before consuming `confidence_engine`.
- `oos_ece_consumed=False`; no OOS calibration error participated in confidence.
- Risk gate uses portfolio defaults: `portfolio_equity=0.0`, `daily_pnl=0.0`, `unrealized_pnl=0.0`, `exposure=0.0`, `var_utilization_pct=0.0`. These materially support `RiskDecision.action=proceed`.

Not material:

- Random/hash-like IDs such as `sa_20260808_204237`, `ec_abad6f884964`, and `dec_af8df2150978` are cosmetic identifiers unless used as provenance keys.

## Preceding Runtime Comparison

Immediately preceding runtime: `C:\AurumAI\AurumAI\outputs\2026-08-08\runtime_20260808_195528`

Useful comparisons only:

- Both runs completed successfully with `26/26` stages ok.
- Both runs produced `NO_TRADE`.
- Both runs produced institutional confidence `0.2494`.
- Both runs had `open_interest_change_pct=0.0`.
- Both runs used the same market snapshot values for the key SignalAssessment observations.

The current run used git commit `10a33ec`; the preceding registry record shows `97c8e72`. No market-driven runtime value above is attributed to code changes without direct evidence.

## Recent Correction Checks

- Volume-flow wiring: intact. `open_interest_change_pct` reaches pre-market positioning and the SignalAssessment volume-flow path; ETF flow is the active positive component in this run.
- Real OI producer: intact. The producer reads Yahoo `openInterest` and does not substitute traded `Volume`.
- Anomaly identity: intact. The anomaly observation ID includes the anomaly type and full semantic description instead of collapsing into a generic XAU/USD identifier.
- CounterEvidence correction: intact. Runtime W7 identifies supporting sets, contradicting set `es_usd_fx`, missing `CB_GOLD`, flags, severity, and penalty.
- RiskReward correction: intact. Runtime W12 validates all three scenarios with scenario-specific reward/risk inputs and statuses.
- ScenarioGeneration no longer consuming `confidence_engine`: intact. Orchestration has `scenario_generation` upstream of `confidence_engine`; runtime metadata shows `confidence_source=thesis_support`.
- W2 regime propagation: intact. `regime_diagnosis=INFLATIONARY`, pre-market uses `INFLATIONARY`, SignalAssessment uses `INFLATIONARY`, and evidence uses `INFLATIONARY`.
- KnowledgeGraph to Evidence integration: structurally active because evidence collection is run with the legacy pipeline knowledge graph, but this runtime produced synthetic `source_kr_id` values rather than concrete KG KR ids. This is a material provenance limitation of this run, not evidence of a failed runtime.

OPERATIONALLY COHERENT — CONTINUE VALIDATION
