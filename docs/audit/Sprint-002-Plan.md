# Sprint-002 Plan: MacroRegimeDetector Activation (C-03)

**Date:** 2026-07-25  
**Target:** C-03 — Wire MacroRegimeDetector into the institutional pipeline  
**ADR:** ADR-002-macro-regime-activation.md  
**Ownership Verification:** Sprint-002-Ownership-Verification.md

---

## Summary

Activate the existing, tested `MacroRegimeDetector` by producing `composite_score` data from raw economic CSVs, adding global extractor support to `FeatureExtractionEngine`, registering `MacroRegimeFeatureExtractor` at pipeline startup, and wiring the fitted detector into `ForecastContextBuilder`.

---

## Files to Create

| File | Purpose |
|------|---------|
| `src/knowledge/regime/composite_score.py` | `CompositeScoreBuilder` — reads raw CSVs, normalizes, produces `composite_score` DataFrame |
| `tests/test_composite_score.py` | Tests for composite score computation |

## Files to Modify

| File | Change |
|------|--------|
| `src/knowledge/features/engine.py` | Add `_global_extractors`, `register_global()`, `clear_global()`, chain in `process()` |
| `src/orchestration/stages.py` | Add regime initialization in `_ingest_event`; pass detector in ForecastContextBuilder calls |
| `src/knowledge/regime/__init__.py` | Export `CompositeScoreBuilder` |
| `src/knowledge/features/__init__.py` | No change needed (engine API extended, not changed) |

## Tests

| Test File | Tests |
|-----------|-------|
| `tests/test_feature_extraction_engine.py` (existing) | Add: global extractors chain, backward compat, clear isolation |
| `tests/test_composite_score.py` (new) | Add: structure, normalization, determinism |
| `tests/test_macro_regime.py` (existing) | Add: full pipeline wiring test with extracted lesson containing macro_regime |

---

## Implementation Order

1. **CompositeScoreBuilder** — produce composite_score from raw CSVs
2. **FeatureExtractionEngine** — global extractor support
3. **Pipeline wiring** — register regime extractor in `_ingest_event`
4. **ForecastContextBuilder wiring** — pass detector via `params["_regime_detector"]`
5. **Tests** — composite, engine, integration
6. **Verification** — run full test suite
7. **Documentation** — update PROJECT_STATUS.md, produce Sprint-002-Completion.md

---

## Risks

| Risk | Mitigation |
|------|------------|
| Cross-test contamination from global extractors | `clear_global()` called in pytest fixture teardown |
| z-score normalization sensitive to outlier periods (e.g., 2020 COVID) | Full-history z-score is stable with 70+ years of data |
| Some events lack Date alignment with regime periods | Extractors return "UNKNOWN" for unmatched dates (already handled) |
