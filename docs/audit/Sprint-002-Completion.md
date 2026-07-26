# Sprint-002 Completion: MacroRegimeDetector Activation (C-03)

**Date:** 2026-07-25  
**Total Duration:** ~90 minutes (ADR + Ownership Verification + Plan + Implementation + Tests)

---

## Files Modified

| File | Change | Type |
|------|--------|------|
| `src/knowledge/regime/composite_score.py` | NEW — `CompositeScoreBuilder` class reads 5 monthly CSVs, computes z-scores, averages into composite_score | Create |
| `src/knowledge/regime/__init__.py` | Export `CompositeScoreBuilder` and regime constants | Modify |
| `src/knowledge/features/engine.py` | Add `_global_extractors`, `register_global()`, `clear_global()`, multi-extractor chaining in `process()` | Modify |
| `src/orchestration/stages.py` | Add `_ensure_macro_regime_initialized()`, wire into `_ingest_event`, pass detector in `_forecast_confidence` and `_build_context` | Modify |
| `tests/conftest.py` | Add autouse fixture `_clear_global_extractors` for test isolation | Modify |
| `tests/test_composite_score.py` | NEW — 6 tests for CompositeScoreBuilder | Create |
| `tests/test_feature_extraction.py` | Add 5 new tests for global extractors + CPI integration | Modify |

### Documentation Files Created/Modified

| File | Type |
|------|------|
| `docs/adr/ADR-002-macro-regime-activation.md` | Create — Architecture Decision Record |
| `docs/audit/Sprint-002-Ownership-Verification.md` | Create — 5 extension points investigated |
| `docs/audit/Sprint-002-Plan.md` | Create — Sprint implementation plan |
| `docs/audit/Sprint-002-Completion.md` | Create — This file |
| `PROJECT_STATUS.md` | Modify — Add Sprint-002 completion details |

---

## Files NOT Modified (Verified Unchanged)

| File | Reason |
|------|--------|
| `src/knowledge/events/base.py` | MacroEvent ABC is frozen |
| `src/knowledge/events/cpi.py` | No event class modifications needed |
| `src/knowledge/events/nfp.py` | No event class modifications needed |
| `src/knowledge/events/gdp.py` | No event class modifications needed |
| `src/knowledge/events/ppi.py` | No event class modifications needed |
| `src/knowledge/events/pmi.py` | No event class modifications needed |
| `src/knowledge/events/interest_rate.py` | No event class modifications needed |
| `src/knowledge/events/fomc.py` | No event class modifications needed |
| `src/knowledge/features/extractor.py` | FeatureExtractor ABC is frozen |
| `src/knowledge/pipeline/pipeline.py` | InferencePipeline is frozen |
| `src/knowledge/orchestration/orchestrator.py` | No changes needed |

---

## Tests Executed

### New Tests (11)

| Test | File | Verifies |
|------|------|----------|
| `test_build_returns_expected_columns` | `test_composite_score.py` | CompositeScoreBuilder output has Date + composite_score columns |
| `test_build_deterministic` | `test_composite_score.py` | Same inputs → same output |
| `test_build_empty_when_no_files` | `test_composite_score.py` | Graceful handling of missing data |
| `test_build_partial_data` | `test_composite_score.py` | Works with subset of indicators |
| `test_build_z_score_produces_zero_mean` | `test_composite_score.py` | Z-score transformation centers at ~0 |
| `test_cpi_pct_change_compounded` | `test_composite_score.py` | CPI YoY % change computation |
| `test_global_extractor_adds_column` | `test_feature_extraction.py` | Global extractor adds column to engine output |
| `test_global_extractors_chain_in_order` | `test_feature_extraction.py` | Multiple global extractors chain correctly |
| `test_global_extractors_backward_compatible` | `test_feature_extraction.py` | No global extractors → original behavior preserved |
| `test_global_extractors_cleared_by_clear_global` | `test_feature_extraction.py` | clear_global() removes all global extractors |
| `test_event_load_and_extract_with_global_extractor` | `test_feature_extraction.py` | CPIEvent.load_and_extract() includes macro_regime column |

### Existing Tests (Passing)

| Test File | Tests | Result |
|-----------|-------|--------|
| `test_composite_score.py` | 6 | ✅ All pass |
| `test_feature_extraction.py` | All | ✅ All pass |
| `test_macro_regime.py` | 14 | ✅ All pass |
| `test_lesson_builder.py` | All | ✅ All pass |
| `test_inference_pipeline.py` | All | ✅ All pass |
| `test_institutional_orchestrator.py` | All | ✅ All pass |
| `test_orchestration.py` | All | ✅ All pass |

**Total verified: 143 tests, all pass** (full suite excluding GraphBuilder performance tests)

---

## Acceptance Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| FeatureExtractionEngine receives regime signal | ✅ | `MacroRegimeFeatureExtractor` registered as global extractor via `register_global()`; engine runs it in `process()` after primary extractor |
| Regime field populated in extracted features | ✅ | `test_event_load_and_extract_with_global_extractor` confirms `macro_regime` column present in CPIEvent output |
| Regime field flows through to lessons | ✅ | Same test pipeline passes; `LegacyLessonBuilder` uses `event.load_and_extract()` which includes regime column |
| ForecastContext receives regime | ✅ | `ForecastContextBuilder(regime_detector=params["_regime_detector"])` passes fitted detector; `_resolve_regime()` returns regime label |
| Deterministic | ✅ | `MacroRegimeDetector(random_state=42)`; composite builder is purely mathematical with no random state; `test_build_deterministic` passes |
| All existing tests pass | ✅ | 143 tests pass across all relevant test files; no regressions |

---

## Architectural Impact

**Before Sprint-002:**
- `MacroRegimeDetector`: built, tested, never instantiated in production
- `MacroRegimeFeatureExtractor`: built, tested, never called
- `ForecastContextBuilder._resolve_regime()`: always returned `{"label": None, "confidence": 0.0}`
- `FeatureExtractionEngine`: single extractor only
- No `composite_score` data source existed

**After Sprint-002:**
- `CompositeScoreBuilder` produces `composite_score` from raw economic CSVs at pipeline startup
- `MacroRegimeDetector` fitted on real composite data during `_ingest_event`
- `MacroRegimeFeatureExtractor` registered as global extractor on `FeatureExtractionEngine`
- All events automatically get `macro_regime` column in their extracted features
- `ForecastContextBuilder` receives the fitted detector, enabling regime-aware forecasts
- `FeatureExtractionEngine` now supports multi-extractor chaining (backward-compatible)

**Architecture Freeze Compliance:**
- ✅ No frozen components modified
- ✅ All 7 event classes unchanged
- ✅ FeatureExtractor ABC unchanged
- ✅ MacroEvent ABC unchanged
- ✅ InferencePipeline unchanged
- ✅ InstitutionalOrchestrator unchanged

---

## Institutional Impact

- **Before**: Every extracted feature set was regime-blind. ForecastContext returned `regime: None` for every decision.
- **After**: Every extracted feature set includes `macro_regime` column (EXPANSION / LATE_CYCLE / CONTRACTION / RECOVERY / UNKNOWN). ForecastContext includes the current regime label and confidence.
- **Downstream effects**: Knowledge records will automatically group by regime (if added to `condition_columns` in a future sprint). Decisions can be evaluated per-regime.

---

## Remaining Follow-Up Work

| Item | Priority | Notes |
|------|----------|-------|
| Add `macro_regime` to event `condition_columns` | Future | Currently `macro_regime` is a feature column but not a condition dimension. Adding it to e.g. `CPIEvent.condition_columns` would enable per-regime knowledge grouping. Requires checking that `macro_regime` values are stable and meaningful. |
| Experiment 002: Measure regime impact | Future | Run an Institutional Experiment comparing regime-aware vs regime-blind pipeline output to quantify whether regime enrichment improves decision quality. |
| Regime-aware RiskGate | Future | `_risk_gate` already uses `context.current_regime`; regime now comes from actual data instead of None. No immediate changes needed. |
