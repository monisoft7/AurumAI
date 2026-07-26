# Sprint-003: Institutional Context Propagation — Completion

**Date:** 2026-07-25  
**Status:** Complete  

---

## Objective

Propagate institutional context (starting with `macro_regime`) into lesson objects via LessonBuilder, without modifying any event class.

---

## Verification

### Consumption Trace (from Sprint-002-Consumption-Verification.md)

The consumption verification identified that `macro_regime` was correctly added to `FeatureSet.data` by the `FeatureExtractionEngine` (with global extractors) but was **lost at the lesson construction boundary** — `MacroEvent.build_lesson_fields()` selects specific columns and does not forward `macro_regime`.

### Architectural Decision

ADR-003 confirmed that **Macro Regime is Institutional Context, NOT an Event attribute**. Therefore:
- Events must NOT be modified to forward it
- LessonBuilder is the correct ownership point
- The solution must support future context types (volatility_regime, liquidity_regime, geopolitical_state) without code changes

### Implementation

**File modified:** `src/knowledge/builders/lesson_builder.py`

1. **`LessonBuilderConfig.institutional_context`** — New dataclass field with default `("macro_regime",)`. Setting to `()` disables forwarding.

2. **`LessonBuilder._add_institutional_context()`** — Shared helper method that iterates over `self.config.institutional_context`, checks `if ctx_col in row.index`, and forwards value as `str(row[ctx_col])` to the lesson dict.

3. **`LessonBuilder._build_lessons()`** — Calls `_add_institutional_context(lesson, row)` after `build_lesson_fields()`.

4. **`LegacyLessonBuilder._build_lessons_legacy()`** — Same call added.

### Files Not Modified

- `knowledge/events/base.py` (MacroEvent ABC)
- `knowledge/events/cpi.py` (CPIEvent)
- `knowledge/events/nfp.py` (NFPEvent)
- `knowledge/events/gdp.py` (GDPEvent)
- `knowledge/events/ppi.py` (PPIEvent)
- `knowledge/events/pmi.py` (PMIEvent)
- `knowledge/events/fomc.py` (FOMCEvent)
- `knowledge/events/interest_rate.py` (InterestRateEvent)
- `knowledge/features/engine.py` (FeatureExtractionEngine)
- `knowledge/features/extractors/*` (all extractors)

### Test Results

| Test File | Tests | Result |
|-----------|-------|--------|
| `test_lesson_builder.py` | 10 | All PASS |
| `test_macro_event_standard.py` | 15 | All PASS |
| `test_lesson_summary.py` | 2 | All PASS |
| **Total affected** | **27** | **All PASS** |

### New Tests (5)

| Test | What It Verifies |
|------|------------------|
| `test_legacy_lesson_forwards_institutional_context` | Legacy path forwards `macro_regime` from CSV to lesson dict |
| `test_institutional_lesson_forwards_institutional_context` | Institutional path (with release calendar) forwards `macro_regime` |
| `test_institutional_context_disabled_with_empty_tuple` | Setting `institutional_context=()` suppresses forwarding |
| `test_institutional_context_skips_missing_column_gracefully` | When column doesn't exist in event_data, it's silently skipped |
| `test_custom_institutional_context_column` | Custom column name (`volatility_regime`) is forwarded correctly |

---

## Forward Compatibility

When a new institutional context type is added (e.g., `volatility_regime`):
1. Create the global extractor and register it via `FeatureExtractionEngine.register_global()`
2. Add `"volatility_regime"` to `LessonBuilderConfig.institutional_context`
3. The column flows into lessons automatically

No changes to `LessonBuilder`, `MacroEvent`, or any event class are required.

---

## Gate Readiness

- [x] ADR-003 documented and approved
- [x] No event classes modified
- [x] All 27 affected tests pass
- [x] Backward compatible (existing lessons unchanged)
- [x] Extensible to future context types
- [x] PROJECT_STATUS.md updated (new Sprint, test count 1627)
- [x] Regression-free against Sprint-002 baseline
