# Forecast Pipeline Audit 001

Scope: the `forecast`, `forecast_confidence`, `forecast_validation`, and `build_context`
stages plus their downstream consumers (`risk_measures`, `position_sizing`, `risk_gate`,
`finalize`). Facts only; no fixes, no recommendations.

Baseline: git HEAD `78c9ad4` (working tree has uncommitted sizing-fix modifications).
Reference run: `outputs/2026-08-04/runtime_20260804_215133/` (real pipeline run,
2026-08-04, 25/25 stages ok, 57.0s).

## 1. Module inventory (`src/forecasting/`)

| File | Size (bytes) | Role |
|---|---|---|
| `macro_forecaster.py` | 4482 | StatsForecast model runner (AutoARIMA/AutoETS/AutoTheta) |
| `models.py` | 579 | `ForecastPoint`, `ForecastResult` dataclasses |
| `confidence.py` | 3467 | `ForecastConfidence`, `ForecastConfidenceComputer` |
| `validation.py` | 5317 | `ForecastValidationReport`, `ForecastValidator` |
| `context.py` | 7584 | `ForecastContext`, `ForecastContextBuilder` |
| `knowledge.py` | 6231 | `ForecastPackage`, `ForecastKnowledge` |
| `registry.py` | 2856 | `ForecastModelSpec`, `ForecastRegistry` |
| `provenance.py` | 2029 | `ForecastProvenance` + git commit / data hash |
| `position_sizing.py` | 4274 | `VolatilityTargetSizer`, `RiskParitySizer` (audited in POSITION_SIZING_AUDIT_001) |
| `risk_measures.py` | 4750 | VaR/CVaR, `TailRiskDetector` (downstream consumer of forecast) |
| `risk_budgeting.py` | 2222 | budget partitioning (downstream consumer) |
| `decision_gate.py` | 5146 | `DecisionGate` thresholds (downstream consumer) |
| `evidence.py`, `reasoning.py` | 3919/6646 | not referenced by these stages |

## 2. DAG wiring (`src/orchestration/orchestrator.py`)

| Job | Dependencies | cache_ttl | checkpoint | Line |
|---|---|---|---|---|
| `ingest_event` | () | 600 | True | 350-358 |
| `ingest_news` | () | 300 | True | 360-366 |
| `build_legacy_pipeline` | (`ingest_event`,) | 600 | True | 368-374 |
| `forecast` | (`ingest_event`,) | 600 | True | 376-382 |
| `forecast_confidence` | (`forecast`,) | 600 | True | 384-390 |
| `forecast_validation` | (`forecast`,) | None | True | 392-398 |
| `build_context` | (`forecast`, `ingest_news`) | 600 | True | 400-406 |
| `risk_measures` | (`forecast`,) | 300 | True | 408-414 |
| `position_sizing` | (`forecast`,) | 300 | True | 416-422 |
| `risk_gate` | (`build_context`, `build_legacy_pipeline`, `risk_measures`, `position_sizing`) | 120 | True | 424-431 |
| `finalize` | (`risk_gate`, `position_sizing`, `forecast_confidence`, `forecast_validation`, `decision_engine`) | None | True | 433-440 |

Cache/checkpoint behaviour: `run.py:396` calls `orch.run_all(force=True, ...)`.
`force=True` bypasses both the in-process per-job cache (orchestrator.py:178) and
on-disk checkpoints (orchestrator.py:161). `checkpoint_dir` is `null` in
`runtime_config.json` and defaults to the OS temp dir (orchestrator.py:55-59).
Net effect: every real run recomputes every job; neither cache nor checkpoints hit.

## 3. Complete data flow (per stage, exact locations)

### 3.1 `_ensure_macro_regime_initialized` (stages.py:20-37)
- Process-level memo via module global `_regime_initialized` (stages.py:5, 22).
- `CompositeScoreBuilder().build()` (stages.py:32) → monthly composite from 5 economic
  CSVs: CPIAUCSL, PPIACO, PMI, UNRATE, PAYEMS (`src/knowledge/regime/composite_score.py:21-27`,
  CSV dir `data/economic/` line 39; transform at 130-141, z-score mean at 68-75).
  Falls back to empty DataFrame if files missing (composite_score.py:65-66).
- `MacroRegimeDetector(random_state=42).fit(composite_data)` (stages.py:33).
- Result cached in `params["_regime_detector"]` (stages.py:36).

### 3.2 `_ingest_event` (stages.py:40-53)
- `EventRegistry.get("CPI")`; `event.load_raw(params["data_path"])` where
  `data_path = data/economic/CPIAUCSL.csv` (runtime_config.json). Real data source,
  last row 2026-06-01.

### 3.3 `_ingest_news` (stages.py:56-79)
- `NewsCollector` import wrapped in `try/except ImportError: pass` (63-69).
  `src/news/collector.py` does NOT exist → `news_items` always `[]`.
- `FOMCCalendarConnector.fetch()` wrapped in `try/except (ImportError, AttributeError): pass`
  (71-77). `src/connectors/fomc_calendar.py` exists.
- Output `{"news_items", "fomc_events"}` is **never read** by any downstream stage
  (see 3.6). `finalize` does not include it.

### 3.4 `_forecast` (stages.py:158-180) — REAL training source
- Reads `params["gold_path"]` = `data/history/gold/gold.csv` (line 165).
  CSV: 2765 data rows, 2015-01-02 → 2025-12-31, columns
  `Date,Close,High,Low,Open,Volume` (daily).
- Renames datetime col to `ds` (166-169), sets `y = Close` if absent (170-171).
- `MacroForecaster()` defaults: `season_length=12`, `freq="ME"`, models
  `[AutoARIMA(12), AutoETS(12, "ZZZ"), AutoTheta(12)]`
  (macro_forecaster.py:10-12, 18-24, 26-39).
- `forecast(df, h=horizon)` with `horizon = params.get("horizon", 12)` (line 163).
  Runtime config horizon is 12 → **matches** (metadata `h: 12`).
- Returns ONLY the primary model result: `primary = next(iter(model_results.values()))`
  (176-178). Model order is AutoARIMA first → AutoARIMA is what all consumers see.
  AutoETS and AutoTheta results are computed then **discarded**.
- Training data is daily gold but the frequency spec is `"ME"` (monthly). Output points
  are month-end timestamps (e.g. `2026-01-31 00:00:00`). Metadata `n_obs` reports the raw
  daily row count `len(clean)` (macro_forecaster.py:134) = 2765, not the model-observed
  points.

### 3.5 `_forecast_confidence` (stages.py:183-229)
- Re-reads `gold.csv` WITHOUT `parse_dates` (196).
- `ForecastContextBuilder(regime_detector=params["_regime_detector"])` (197-199).
- `context = build(source_variable=model_name, gold_df)` (200-203). No news_texts,
  fomc_texts, or event_summaries passed → `news_mood=None/0.0`, `fomc_mood=None/0.0`,
  `recent_events=()` (context.py:116-118, 147-149, 166-168).
- `specs = ForecastRegistry.for_target(asset)` (206). **Registry is never populated in
  production** — `ForecastModelSpec`/`ForecastRegistry.register` appear only in
  `tests/`. So `specs == []` and `ForecastRegistry.version() == 0`.
- Provenance constructed (207-215): `model_version="0"`, `registry_version="0"`,
  `resolve_git_commit()` (subprocess `git rev-parse HEAD`, 5s timeout, fallback
  `"unknown"`, provenance.py:23-36), `compute_data_hash(gold_df)` (provenance.py:38-57).
- `ForecastPackage` assembled with the single AutoARIMA result and `model_specs=()`
  (217-224).
- `ForecastConfidenceComputer.compute(pkg, context)` (226-227):
  `overall = 0.30*spread + 0.40*agreement + 0.30*coherence`, clamped [0,1]
  (confidence.py:40-41).
  - spread = 1 - min(avg relative 95%-band width, 1) (confidence.py:49-66).
  - agreement = 1.0 short-circuit when exactly 1 model (confidence.py:75-76).
  - coherence = mean(regime_confidence, news_confidence, fomc_confidence)
    (confidence.py:105-111) → news/fomc always 0.0.
- Returns `{"confidence", "context"}` (229).

### 3.6 `_build_context` (stages.py:250-267)
- Re-reads `gold.csv` (258) and **rebuilds the identical context** as 3.5 (262-265).
- Declared dependency `ingest_news` (orchestrator.py:402) is NOT read here or anywhere.
- Returns context (267) → `finalize["context"]` (stages.py:871).

### 3.7 `_forecast_validation` (stages.py:232-247)
- Re-reads `gold.csv` WITHOUT `parse_dates` (241) → columns are `Date,Close,...`.
- `ForecastValidator.validate(df, {model_name: result}, strategy="walk_forward", horizon=1)`
  (245). Strategy and horizon are hardcoded in the stage.
- `_align` (validation.py:142-165) builds `actual_map` from `row.get("ds","")` / `row["y"]`.
  `gold_df` has neither column → `actual_map` empty → returns `[]` → report
  `sample_size=0`, all metrics 0.0, `passed=False`,
  notes "No aligned forecast-actual pairs available for validation" (validation.py:56-71).
- Independent second cause: even with correct columns, forecast points start
  2026-01-31 and gold ends 2025-12-31 → no date overlap by construction.
- Report is serialized only (`finalize["validation"]`, stages.py:870). No gate,
  decision, or downstream logic consumes `passed`.

### 3.8 `_finalize` (stages.py:854-876)
- Emits: `decision`, `legacy_decision`, `risk_decision`, `forecast_result` (868),
  `confidence` (869), `validation` (870), `context` (871), `risk_metrics` (872),
  `position_sizing`/`risk_budget`/`position_sizing_status` (873-875).
- No provenance field is serialized.

## 4. Runtime effect (run 20260804_215133)

### 4.1 Finalize blocks
- `forecast_result`: model AutoARIMA, `confidence_level` 0.95, 12 points
  (2026-01-31 → 2026-12-31, month-end), metadata `{freq: ME, h: 12, n_obs: 2765, season_length: 12}`.
  First point y=4335.64; bands widen from ±~40 to ±~136 over the horizon.
- `confidence`: spread_score 0.956539, agreement_score 1.0, context_coherence
  0.117833, overall 0.722312. (0.3*0.9565 + 0.4*1.0 + 0.3*0.1178 = 0.7223.)
- `validation`: `{sample_size: 0, passed: false, validation_strategy: walk_forward,
  horizon: 1, metrics: all 0.0}`.
- `context`: current_regime `LATE_CYCLE`, regime_confidence 0.3535 (label-frequency
  ratio, context.py:144), news/fomc null 0.0, recent_events `[]`,
  data_date_range `["2015-01-02", "2025-12-31"]`, source_variable `AutoARIMA`,
  context_timestamp `2026-08-04T19:52:29Z`.

### 4.2 Stage durations (stages.json)
| Stage | ms |
|---|---|
| forecast | 22484.9 (~39% of 57.0s total) |
| forecast_confidence | 326.7 |
| forecast_validation | 224.8 |
| build_context | 209.9 |
| ingest_news | 3.3 (no-op; collector missing) |
| ingest_event | 33928.6 (regime fit dominates) |

## 5. Verification results (task checklist)

- Forecast uses latest available gold data: **No staleness guard exists anywhere in
  `src/forecasting/` or the stages** (no freshness/recency check found). Gold.csv ends
  2025-12-31; run date 2026-08-04 → ~7 months stale. The stale range propagates into
  forecast, confidence, and context.
- Forecast horizon matches runtime config: **Yes**. `runtime_config.json` `horizon: 12`
  == `params["horizon"]` (stages.py:163) == metadata `h: 12` == `_DEFAULT_H`.
- Validation based on real observations: **No**. `_forecast_validation` never produces
  aligned pairs: column mismatch (`ds`/`y` expected, `Date/Close/...` present) and
  zero date overlap by design. `passed` is always false and is not consumed.
- No stale dataset silently propagates: **Stale data propagates silently** (see above);
  nothing downstream detects the 7-month gap.

## 6. Inventories

### 6.1 Real data sources
- `data/history/gold/gold.csv` — forecast training (stages.py:165), also read by
  confidence (196), validation (241), context (258).
- `data/economic/{CPIAUCSL,PPIACO,PMI,UNRATE,PAYEMS}.csv` — regime composite
  (composite_score.py:21-27). CPIAUCSL ends 2026-06-01.
- `src/connectors/fomc_calendar.py` — exists; fetched but never consumed.

### 6.2 Synthetic sources
- None in the forecast path (training data is real gold). Adjacent downstream path
  `_risk_measures` retains a seeded-RNG residual fallback
  (`np.random.default_rng(42).normal(0,1,252)`, stages.py:285) — documented in
  POSITION_SIZING_AUDIT_001.

### 6.3 Fallbacks / placeholders / mocked values
- `_ingest_news` swallows `ImportError`/`AttributeError` → empty lists (stages.py:63-77);
  `src/news/collector.py` missing → news always `[]`.
- `ForecastContextBuilder` with no analyzers returns `{None, 0.0}` for regime/news/fomc
  (context.py:134-136, 147-149, 166-168); news/fomc always null in practice.
- `ForecastRegistry` empty in production → `model_specs=()`, `model_version`/
  `registry_version` = `"0"` (stages.py:206-211).
- `resolve_git_commit()` fallback `"unknown"` on subprocess failure (provenance.py:31-34).
- `params.get("_regime_detector")` is `None` only if `_ensure_macro_regime_initialized`
  was never called; in the pipeline it is always set (stages.py:36).

### 6.4 Stale-data paths
- `gold.csv` frozen at 2025-12-31; no freshness gate.
- `_forecast_validation` cannot detect staleness (no pairs).
- `context.data_date_range` exposes the gap but is consumed by no decision logic.

### 6.5 Caches
- In-process per-job TTL cache (orchestrator.py:178) — bypassed by `force=True`
  (run.py:396).
- On-disk checkpoints (orchestrator.py:161-176) — `checkpoint_dir` null →
  tempdir default; bypassed by `force=True`.
- Process-level memo `_regime_initialized` (stages.py:5, 20-37) — regime detector fit
  once per process (33.9s in run).
- No persistent forecast artifact cache.

### 6.6 Validation steps
- `ForecastValidator` (validation.py): `mape < 20.0 and coverage > 0.80 and da > 0.50`
  (thresholds at validation.py:8-10; pass rule at 125-129). Never satisfiable in the
  current wiring (sample_size always 0).

## 7. Findings (trace-level facts)

1. **Unused model outputs**: `_forecast` computes AutoETS and AutoTheta but returns only
   AutoARIMA (stages.py:176-178). ~22.5s stage pays for 3 models; 2 discarded.
2. **Unused stage output**: `ingest_news` result (`news_items`, `fomc_events`) is never
   read (build_context ignores it; orchestrator.py:402 declares the dependency only).
3. **Unused provenance**: `_forecast_confidence` builds `ForecastProvenance` incl. a
   subprocess git call (stages.py:207-215) but nothing serializes or consumes it
   (`finalize` has no provenance key).
4. **Inert validation**: `forecast_validation` always returns `passed=False,
   sample_size=0` (validation.py:56-71 + `_align` 150-157); not consumed by any gate.
5. **Duplicated gold reads**: `pd.read_csv(gold_path)` executed 4×/run (stages.py:165,
   196, 241, 258), 3× without `parse_dates` and without the `ds`/`y` rename that
   `_forecast` applies.
6. **Duplicated context build**: identical `ForecastContextBuilder.build` runs in
   `_forecast_confidence` (200-203) and `_build_context` (262-265).
7. **Degenerate agreement**: `agreement_score` short-circuits to 1.0 for a single model
   (confidence.py:75-76); overall = 0.4 constant + 0.3*spread + 0.3*coherence.
8. **Degenerate coherence**: news/fomc confidences always 0.0 → coherence = regime/3
   (confidence.py:105-111; runtime 0.1178).
9. **Dead code**: `MacroForecaster._column_re` (macro_forecaster.py:45-49) never called
   (real parsing is `_parse_model_cols`).
10. **Unused production class**: `ForecastKnowledge` (knowledge.py:67-179) is not
    imported by the orchestrator; its registry-driven flow returns `{}` results when the
    registry is empty (knowledge.py:136-137). Registry populated only in tests.
11. **Hardcoded assumptions**: `season_length=12`, `freq="ME"`, `h=12` defaults
    (macro_forecaster.py:10-12); `level=[95]` (macro_forecaster.py:103); daily gold fed
    with monthly freq spec; validation strategy/horizon hardcoded (stages.py:245);
    `random_state=42` regime fit (stages.py:33); confidence weights 0.3/0.4/0.3
    (confidence.py:40).
12. **Misleading metadata**: `n_obs=2765` reports raw daily rows (macro_forecaster.py:134)
    although output frequency is monthly.

## 8. Method and sources
- Static reads: `src/orchestration/stages.py` (all lines cited), `src/orchestration/orchestrator.py:355-442`,
  `run.py:382-413`, all `src/forecasting/*.py`, `composite_score.py:1-148`.
- Runtime artifacts: `outputs/2026-08-04/runtime_20260804_215133/{stages.json, finalize.json, run.log}`.
- Data: `data/history/gold/gold.csv` (2765 rows, 2015-01-02..2025-12-31),
  `data/economic/CPIAUCSL.csv` (last 2026-06-01), `runtime_config.json`.
- Grep: `ForecastRegistry|ForecastModelSpec|ForecastKnowledge` (register only in tests);
  `stale|freshness|max_date|last_date` (no matches in `src/forecasting` or stages).
- Prior audits for cross-reference: `RUNTIME_TRACE_AUDIT_001.md`, `POSITION_SIZING_AUDIT_001.md`.
