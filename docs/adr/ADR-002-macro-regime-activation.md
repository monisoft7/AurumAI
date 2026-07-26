# ADR-002: Macro Regime Activation via FeatureExtractionEngine

**Date:** 2026-07-25  
**Status:** Active  
**Core v1.0 dependency:** No core changes

---

## 1. Context

`MacroRegimeDetector` (`src/knowledge/regime/macro_regime_detector.py`) and `MacroRegimeFeatureExtractor` (`src/knowledge/features/extractors/macro_regime.py`) are fully built and unit-tested (202 lines of tests). They have never been wired into production code. `ForecastContextBuilder._resolve_regime()` (`src/forecasting/context.py:134`) already accepts a `MacroRegimeDetector` parameter, but no caller ever provides one — it always defaults to `None`, returning `{"label": None, "confidence": 0.0}`.

The acceptance criteria from CER-007 require:
- FeatureExtractionEngine receives regime signal
- Regime field populated in extracted features
- Deterministic

A separate verification (`Sprint-002-Ownership-Verification.md`) established that no existing extension point can satisfy all three criteria.

---

## 2. Problem

The `MacroRegimeFeatureExtractor` must inject a `macro_regime` column into every event's extracted features at pipeline runtime. The column value is a date-keyed lookup into the regime detector's fitted output (EXPANSION / LATE_CYCLE / CONTRACTION / RECOVERY / UNKNOWN).

The regime must appear:
- In the `FeatureSet.data` returned by `FeatureExtractionEngine.process()`
- In every lesson dict built by `LessonBuilder` / `LegacyLessonBuilder`
- In the `ForecastContext` produced by `ForecastContextBuilder`

Additionally, the regime detector requires `composite_score` data — a monthly numeric macro indicator — which is currently **not produced** anywhere in the codebase.

---

## 3. Why Existing Extension Points Were Rejected

| Extension Point | Rejection Reason |
|----------------|------------------|
| **Dependency Injection** | No DI framework. Engine created privately inside each event's `__init__`. No parameterized constructor path from pipeline to engine. |
| **Orchestration Wiring** | No middleware/hooks/interceptors. Stage functions cannot access private `_extraction_engine` attribute without either modifying events or resorting to fragile monkey-patching. |
| **Event Composition** (Wrapper) | `RegimeAwareMacroEvent` wrapper adds regime after `engine.process()`. Engine does **not** receive the signal. 6 abstract methods must be proxied. |
| **Pipeline Composition** (LessonBuilder subclass) | `RegimeAwareLegacyLessonBuilder` adds regime after `event.load_and_extract()`. Engine does **not** receive the signal. Follows YieldContextEnricher pattern but violates AC #1. |
| **Existing Extension Hooks** | No hooks exist — no callbacks, plugins, middleware, or interceptors anywhere in the extraction chain. `FeatureSet.validate()` tolerates extra columns but is passive, not a hook. |

**Conclusion:** Every clean alternative that avoids modifying `FeatureExtractionEngine` adds regime **after** `engine.process()`, violating acceptance criterion #1.

---

## 4. Why FeatureExtractionEngine Is the Correct Owner

| Property | Rationale |
|----------|-----------|
| **Single responsibility** | The engine's purpose is to run extractors and produce `FeatureSet` objects. Regime is a feature, therefore the engine should own it. |
| **Existing pattern** | The engine already runs one extractor per call. Chaining additional extractors is a minimal extension of this pattern. |
| **No event changes** | Adding global extractor support to the engine means zero changes to CPIEvent, NFPEvent, GDPEvent, InterestRateEvent, PPIEvent, PMIEvent, FOMCEvent — all 7 event classes remain untouched. |
| **No ABC changes** | `MacroEvent ABC`, `FeatureExtractor ABC`, `StandardEventMetadata` remain frozen. |
| **Backward compatible** | Existing callers pass a single extractor as before. The global extractor list is empty by default. No caller needs to change. |
| **Deterministic** | Engine runs extractors in registration order with fixed seed (already enforced by detector's `random_state=42`). |

---

## 5. Architectural Decision

**Modify `FeatureExtractionEngine` to support class-level global extractors that run after the primary extractor in `process()`.**

```python
class FeatureExtractionEngine:
    _global_extractors: ClassVar[list[FeatureExtractor]] = []

    @classmethod
    def register_global(cls, extractor: FeatureExtractor) -> None:
        cls._global_extractors.append(extractor)

    @classmethod
    def clear_global(cls) -> None:
        cls._global_extractors.clear()

    def process(self, raw, extractor):
        fs = extractor.extract(raw)
        fs.validate()
        data = fs.data
        for gx in self._global_extractors:
            fs = gx.extract(data)
            fs.validate()
            data = fs.data
        return fs
```

Additionally:
- Create `CompositeScoreBuilder` to produce the composite_score data from raw economic CSVs
- Initialize the detector + extractor at pipeline startup in `_ingest_event`
- Pass the fitted detector to `ForecastContextBuilder` via `params["_regime_detector"]`

---

## 6. Backward Compatibility

| Concern | Mitigation |
|---------|------------|
| Existing `process(raw, extractor)` callers | Keyword unchanged. Global extractors empty by default. Output identical. |
| Event constructors | Unchanged. They create `FeatureExtractionEngine()` as before. |
| Test isolation | `clear_global()` must be called in test teardown to prevent cross-test contamination. |
| Multi-run pipelines | Module-level initialization flag ensures one-time registration. `run_all()` creates fresh state. |

---

## 7. Acceptance Criteria

1. **FeatureExtractionEngine receives regime signal**: `process()` runs `MacroRegimeFeatureExtractor` as a global extractor after the primary extractor.
2. **Regime field populated in extracted features**: Every `FeatureSet.data` returned by `process()` contains a `macro_regime` column.
3. **Regime field flows through to lessons**: `LessonBuilder` and `LegacyLessonBuilder` lessons contain `macro_regime` column.
4. **ForecastContext receives regime**: `ForecastContextBuilder` receives the fitted `MacroRegimeDetector` and its `_resolve_regime()` returns the correct regime label.
5. **Deterministic**: Same pipeline inputs → same regime labels in every run.
6. **All existing tests pass**: No regressions in any frozen or non-frozen component.
