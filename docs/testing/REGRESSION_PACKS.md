# Regression Pack Manifest

Deterministic logical partition of the full regression suite (`tests/`) for staged
execution and triage. Each test belongs to **exactly one** pack; each test *module*
belongs to exactly one pack, with a single documented exception:
`test_historical_replay.py` is split at test level between Pack 10A (fast subset)
and Pack 10B (heavy replay / real-data / chronological — Release Validation only).
Packs are organized by architecture (not alphabetically).

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

## Pack 10A - Simulation / Orchestration / Integration (Developer Loop)

- **Purpose:** Fast simulation and orchestration tests for the practical developer
  loop: the unit-level subset of the replay suite (models, aggregation, helpers,
  edge cases), simulation validation and scenario generation, acceptance benchmarks,
  performance gates, the institutional orchestrator, and the experiment framework.
  Excludes **only** the genuinely heavy replay tests (full `run_all()` /
  `ChronologicalOOSEngine.run()` executions), which live in Pack 10B.
- **Included test modules:**
  - `test_historical_replay.py` — fast subset only (75 tests); the heavy tests are
    split out to Pack 10B at test level (see Pack 10B for the exact exclusion list)
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
- **Approximate number of tests:** 329
- **Expected runtime:** ~8-15 min (dominated by the non-replay modules;
  re-baseline on the target CI host)
- **Classification:** Fast (developer loop)

---

## Pack 10B - Heavy Replay / Real-Data / Chronological (Release Validation)

- **Purpose:** The genuinely heavy replay tests from `test_historical_replay.py`:
  full 7-type institutional-pipeline replays (`run_all()`), the real-data acceptance
  replay against the repository `data/` directory (including the 54-release CPI
  release-by-release path), and the ChronologicalOOSEngine training/evaluation
  simulations. These dominate module runtime (measured 30-90 min pre-refactor;
  estimated ~25-50 min after the test-design refactor — re-baseline on the target
  host).
- **Usage:** Release Validation only. Not part of the developer loop; run before
  releases/tags, on CI, or on demand.
- **No code changes / no test logic changes:** the split is purely organizational —
  each test listed below executes identically to its Pack 10A definition.
- **Included tests** (exact node IDs; this is the documented module-level split
  exception) and why each is heavy:

  **Full `run_all()` replays — `TestHistoricalReplayEngine` (11):**
  - `test_historical_replay.py::TestHistoricalReplayEngine::test_engine_creates_synthetic_csvs`
    — executes a full 7-type `run_all()` replay (every event type through the
    institutional pipeline) on the fixture dataset (~1-3 min).
  - `test_historical_replay.py::TestHistoricalReplayEngine::test_run_all_structure`
  - `test_historical_replay.py::TestHistoricalReplayEngine::test_each_event_type_has_result`
  - `test_historical_replay.py::TestHistoricalReplayEngine::test_result_has_metrics`
  - `test_historical_replay.py::TestHistoricalReplayEngine::test_forecast_summary_aggregated`
  - `test_historical_replay.py::TestHistoricalReplayEngine::test_risk_summary_aggregated`
  - `test_historical_replay.py::TestHistoricalReplayEngine::test_report_to_dict_roundtrip`
  - `test_historical_replay.py::TestHistoricalReplayEngine::test_run_simulation_convenience`
  - `test_historical_replay.py::TestHistoricalReplayEngine::test_cpi_result_has_correctness_fields`
  - `test_historical_replay.py::TestHistoricalReplayEngine::test_non_cpi_result_no_correctness`
    — the 9 tests above share the module-scoped `report` fixture, which executes one
    full `run_all()` replay (~10-15 min); none of them can run without triggering it.
  - `test_historical_replay.py::TestHistoricalReplayEngine::test_gold_date_column`
    — executes its own full `run_all()` replay on a custom dataset (~1-3 min).

  **Real-data acceptance replays — `TestRealDataSimulation` (2):**
  - `test_historical_replay.py::TestRealDataSimulation::test_real_data_simulation_runs`
    — the primary Phase 19.1 acceptance test: full replay against the real
    `data/` directory, including the 54-release CPI release-by-release path
    (~8-20 min).
  - `test_historical_replay.py::TestRealDataSimulation::test_real_data_serialisable`
    — shares the same real-data replay via the module-scoped `real_report` fixture.

  **Chronological train/eval simulations — `TestChronologicalOOSEngine` (6):**
  Each of these executes `ChronologicalOOSEngine.run()`, which replays the full
  pipeline twice: a training phase (7 pre-cutoff pipeline runs building lessons)
  plus an evaluation phase (7 post-cutoff runs, CPI release-by-release):
  - `test_historical_replay.py::TestChronologicalOOSEngine::test_cpi_separation_produces_results`
  - `test_historical_replay.py::TestChronologicalOOSEngine::test_knowledge_dir_created`
  - `test_historical_replay.py::TestChronologicalOOSEngine::test_prebuilt_lessons_injected`
    — the 3 tests above share the module-scoped `chrono_report` fixture (one `run()`).
  - `test_historical_replay.py::TestChronologicalOOSEngine::test_deterministic`
    — executes **two** full `run()` executions (r1 vs r2 determinism comparison).
  - `test_historical_replay.py::TestChronologicalOOSEngine::test_cutoff_after_all_data`
    — one full `run()`.
  - `test_historical_replay.py::TestChronologicalOOSEngine::test_cutoff_before_all_data`
    — one full `run()`.

- **Approximate number of tests:** 19
- **Expected runtime:** ~25-50 min (estimate; re-baseline on the target CI host)
- **Classification:** Slow — Release Validation only

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

- **Total packs:** 12
- **Total test modules:** 98 (one module — `test_historical_replay.py` — split
  across Pack 10A and Pack 10B at test level)
- **Total collected tests:** 2575 (Pack 10A: 329 + Pack 10B: 19)
