# Regression Pack Manifest

Deterministic logical partition of the full regression suite (`tests/`) for staged
execution and triage. Each test module belongs to **exactly one** pack. Packs are
organized by architecture (not alphabetically).

- Test counts per module are approximate (counted test-function definitions; a small
  number of parametrized cases inflate the true collection total).
- Full-suite measured reference: ~2575 collected tests, ~100 minutes wall time
  (single process, Windows, no parallelization).
- Estimated runtimes are proportional to pack size against that reference; they
  should be re-baselined on the target CI host.
- Slow = estimated > 3 minutes; Fast = estimated <= 3 minutes.

---

## Pack 01 - Core / Contracts

- **Purpose:** Cross-cutting contracts, API compatibility, workflow-ID conformance,
  and core brain-level invariants that every other stage depends on.
- **Included test modules:**
  - `test_blocking_contracts.py`
  - `test_compat.py`
  - `test_workflow_id_conformance.py`
  - `test_brain.py`
  - `test_context_comparison.py`
- **Approximate number of tests:** 83
- **Expected runtime:** ~2-3 min
- **Classification:** Fast

---

## Pack 02 - Knowledge / Learning

- **Purpose:** Knowledge graph, retrieval, integrity, calibration, expansion, and the
  learning/lesson-feedback loop (W-level knowledge stages).
- **Included test modules:**
  - `test_knowledge_graph.py`
  - `test_knowledge_integrity.py`
  - `test_knowledge_calibrator.py`
  - `test_retrieval.py`
  - `test_expansion.py`
  - `test_learning_engine.py`
  - `test_lesson_builder.py`
  - `test_lesson_summary.py`
  - `test_feature_extraction.py`
- **Approximate number of tests:** 221
- **Expected runtime:** ~7-9 min
- **Classification:** Slow

---

## Pack 03 - Ingestion & Signals

- **Purpose:** News ingestion/sentiment, pre-market scan, signal tiering
  (W3/W4/W5), technical indicators, and temporal context extraction.
- **Included test modules:**
  - `test_news_pipeline.py`
  - `test_news_sentiment.py`
  - `test_pre_market.py`
  - `test_signal_assessment.py`
  - `test_event_triage.py`
  - `test_event_registry.py`
  - `test_technical_indicators.py`
  - `test_temporal_intelligence.py`
- **Approximate number of tests:** 193
- **Expected runtime:** ~6-8 min
- **Classification:** Slow

---

## Pack 04 - Macro Data, Economic Events & Calendar

- **Purpose:** Economic validation/intelligence, macro regime detection and
  forecasting, and all scheduled macro event implementations (GDP, NFP, PMI, PPI,
  interest rate, FOMC) plus the release calendar.
- **Included test modules:**
  - `test_economic.py`
  - `test_economic_intelligence.py`
  - `test_macro_forecaster.py`
  - `test_macro_regime.py`
  - `test_macro_event_standard.py`
  - `test_gdp_event.py`
  - `test_nfp_event.py`
  - `test_pmi_event.py`
  - `test_ppi_event.py`
  - `test_interest_rate_event.py`
  - `test_fomc_event.py`
  - `test_fomc_sentiment.py`
  - `test_fomc_calendar_connector.py`
  - `test_release_calendar.py`
  - `test_cross_event.py`
- **Approximate number of tests:** 327
- **Expected runtime:** ~11-14 min
- **Classification:** Slow

---

## Pack 05 - Causal Intelligence (CAI / CBI)

- **Purpose:** Causal asset intelligence (cross-asset correlation, spread analysis,
  volatility regime), causal bond intelligence (rate path, policy bias, forward
  guidance), the causal orchestration stage, and the Gold Rule gate.
- **Included test modules:**
  - `test_causal_intelligence.py`
  - `test_cai_cross_asset_correlation.py`
  - `test_cai_orchestration.py`
  - `test_cai_spread_analysis.py`
  - `test_cai_volatility_regime.py`
  - `test_cbi_forward_guidance.py`
  - `test_cbi_policy_bias.py`
  - `test_cbi_rate_path.py`
  - `test_gold_rule_001.py`
- **Approximate number of tests:** 259
- **Expected runtime:** ~9-12 min
- **Classification:** Slow

---

## Pack 06 - Evidence & Reasoning

- **Purpose:** Institutional evidence pipeline (collection, engine, reasoning,
  weighting), counter-evidence/bias analysis, and the reasoning/inference engines.
- **Included test modules:**
  - `test_evidence_collection.py`
  - `test_evidence_engine.py`
  - `test_evidence_reasoning.py`
  - `test_evidence_weighting.py`
  - `test_counter_evidence.py`
  - `test_reasoning_engine.py`
  - `test_inference_pipeline.py`
- **Approximate number of tests:** 238
- **Expected runtime:** ~8-10 min
- **Classification:** Slow

---

## Pack 07 - Thesis / Confidence / Bias

- **Purpose:** Thesis construction and update cycle, institutional confidence
  engine and composite scoring, and the W13 bias-prevention workflow.
- **Included test modules:**
  - `test_thesis_construction.py`
  - `test_thesis_update.py`
  - `test_confidence_engine.py`
  - `test_composite_score.py`
  - `test_bias_prevention.py`
- **Approximate number of tests:** 139
- **Expected runtime:** ~4-6 min
- **Classification:** Slow

---

## Pack 08 - Decision / Recommendation / Execution

- **Purpose:** Decision engine and gate, trade recommendation, outcome
  applicator, position sizing, and the full execution layer (engine, portfolio,
  commission, slippage).
- **Included test modules:**
  - `test_decision_engine.py`
  - `test_decision_gate.py`
  - `test_trade_recommendation.py`
  - `test_applicator.py`
  - `test_execution_engine.py`
  - `test_execution_portfolio.py`
  - `test_execution_commission.py`
  - `test_execution_slippage.py`
  - `test_position_sizing.py`
- **Approximate number of tests:** 305
- **Expected runtime:** ~10-13 min
- **Classification:** Slow

---

## Pack 09 - Forecast / Risk

- **Purpose:** Forecast lifecycle (context, evidence, confidence, reasoning,
  knowledge, provenance, registry, validation, integration) and the risk layer
  (measures, budgeting, integration, risk/reward validation).
- **Included test modules:**
  - `test_forecast_context.py`
  - `test_forecast_evidence.py`
  - `test_forecast_confidence.py`
  - `test_forecast_reasoning.py`
  - `test_forecast_knowledge.py`
  - `test_forecast_provenance.py`
  - `test_forecast_registry.py`
  - `test_forecast_validation.py`
  - `test_forecast_integration.py`
  - `test_risk_measures.py`
  - `test_risk_budgeting.py`
  - `test_risk_integration.py`
  - `test_risk_reward_validation.py`
- **Approximate number of tests:** 356
- **Expected runtime:** ~12-15 min
- **Classification:** Slow

---

## Pack 10 - Simulation / Replay / Orchestration / Integration

- **Purpose:** Historical replay, simulation validation and scenario generation,
  the institutional acceptance benchmark, performance gates, top-level
  orchestration/institutional orchestrator, and the experiment framework
  (registry + EXP-002).
- **Included test modules:**
  - `test_historical_replay.py`
  - `test_simulation_validation.py`
  - `test_scenario_generation.py`
  - `test_benchmark.py`
  - `test_graph_performance.py`
  - `test_attribution_performance.py`
  - `test_orchestration.py`
  - `test_institutional_orchestrator.py`
  - `test_institutional_validation.py`
  - `test_experiment.py`
  - `test_experiment_002.py`
  - `test_experiment_registry.py`
- **Approximate number of tests:** 348
- **Expected runtime:** ~13-18 min (includes the heavy `test_graph_performance`
  graph-builder stress and the 94-test replay module)
- **Classification:** Slow

---

## Pack 11 - External Connectors / Slow

- **Purpose:** External market-data connectors and adapters (DXY, real yields,
  yield context) - network/feed dependent and the most environment-sensitive
  modules.
- **Included test modules:**
  - `test_dxy_adapter.py`
  - `test_dxy_context.py`
  - `test_dxy_fetcher.py`
  - `test_real_yield_adapter.py`
  - `test_real_yield_fetcher.py`
  - `test_yield_context.py`
- **Approximate number of tests:** 104
- **Expected runtime:** ~4-6 min
- **Classification:** Slow

---

## Totals

- **Total packs:** 11
- **Total test modules:** 98
- **Total collected tests:** 2575
