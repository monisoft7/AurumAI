# ADR-003: Institutional Context Propagation via LessonBuilder

**Date:** 2026-07-25  
**Status:** Active  
**Core v1.0 dependency:** No core changes

---

## 1. Context

Sprint-002 activated the `MacroRegimeFeatureExtractor` as a global extractor on `FeatureExtractionEngine`. The `macro_regime` column is present in `FeatureSet.data` after `engine.process()` and in `event_data` within `LessonBuilder.build()`. However, as documented in Sprint-002-Consumption-Verification.md, the regime column is **never forwarded into lesson dicts** because `MacroEvent.build_lesson_fields()` explicitly selects which columns to copy, and `macro_regime` is not among them.

The information is produced by the engine but consumed by no downstream component — the institutional reasoning pipeline sees zero regime context.

---

## 2. Problem

Institutional context (macro_regime, and future context types such as market_regime, liquidity_regime, volatility_regime, geopolitical_state) must reach the lesson dict — and therefore KnowledgeRecord, Evidence, and Reasoning — without modifying individual event implementations.

The constraints are:
- **No event changes**: CPIEvent, NFPEvent, GDPEvent, PPIEvent, PMIEvent, FOMCEvent, InterestRateEvent must not be modified.
- **No duplicate forwarding logic**: The same pattern must not be replicated across 7 event classes.
- **Extensible**: Future context types must be supported by configuration, not by code changes.
- **Backward compatible**: Existing lessons without context columns must continue to work.

---

## 3. Why LessonBuilder Is the Correct Owner

| Criterion | Assessment |
|-----------|------------|
| **Access to event_data** | LessonBuilder receives the `event_data` DataFrame from `event.load_and_extract()` or `event.load_and_extract_with_calendar()`. This DataFrame already contains `macro_regime` from the global extractor. |
| **Lesson dict construction** | LessonBuilder builds the lesson dict in `_build_lessons()`. It is the last point before lessons leave the extraction layer. Any column added here flows into the lesson CSV and downstream components. |
| **Single change point** | There are exactly two methods that build lesson dicts: `_build_lessons()` (institutional) and `_build_lessons_legacy()` (legacy). Both are in `LessonBuilder`. Modifying both is a two-line change, not a seven-event change. |
| **Configuration-driven** | `LessonBuilderConfig` already exists. Adding an `institutional_context` tuple makes the feature controllable without code changes. |
| **Ownership consistent** | LessonBuilder already owns lesson construction. Adding context columns is a natural extension of its existing responsibility. It does not require changing any other component. |

---

## 4. Why Not an Alternative

| Alternative | Rejected Because |
|-------------|------------------|
| Add `macro_regime` to each event's `condition_columns` | Violates "no event changes" constraint. Duplicates logic across 7 events. |
| Add `macro_regime` to each event's `build_lesson_fields` | Same — 7 modifications, violates ownership boundary. |
| Post-hoc enrichment after CSV write (YieldContextEnricher pattern) | Enriches the CSV file, not the lesson dict. Breaks in-memory lesson access. Does not support conditional forwarding. |
| Wrapper around `build_lesson_fields` | Requires modifying every event's inheritance or adding a proxy to MacroEvent ABC (frozen). |

---

## 5. Architectural Decision

**Forward configured institutional context columns from `event_data` rows into lesson dicts during `_build_lessons()` / `_build_lessons_legacy()`.**

```python
@dataclass(frozen=True)
class LessonBuilderConfig:
    ...
    institutional_context: tuple[str, ...] = ("macro_regime",)

# Inside _build_lessons() and _build_lessons_legacy():
for ctx_col in self.config.institutional_context:
    if ctx_col in row.index:
        lesson[ctx_col] = str(row[ctx_col])
```

The column name must exist in `event_data` (added by a global extractor or other mechanism). If the column does not exist in a row, it is silently skipped — enabling forward compatibility as new context types are added to the config before their corresponding extractors are registered.

---

## 6. Backward Compatibility

| Concern | Mitigation |
|---------|------------|
| Existing lessons lack `macro_regime` | `LessonSummaryAggregator._load_lessons()` only checks for condition_columns + standard columns. Extra columns are silently tolerated. |
| `institutional_context` default is `("macro_regime",)` | Configs that do not set this value get the default, which is the desired behavior. Configs that explicitly set `institutional_context=()` disable forwarding. |
| Forwarded column may not exist in event_data | The `if ctx_col in row.index` guard ensures no KeyError. The column is skipped if absent. |
| CSV schema changes | New column added to lesson CSV. All downstream consumers that use the CSV will see the column but none require it. |

---

## 7. Future Extensibility

When a new institutional context type is added (e.g., `volatility_regime`):

1. Create the extractor and register it via `FeatureExtractionEngine.register_global()`
2. Add the column name to `LessonBuilderConfig.institutional_context`
3. The column flows into lessons automatically

No changes to `LessonBuilder`, `MacroEvent`, or any event class are required.

---

## 8. Acceptance Criteria

1. **macro_regime column present in lesson dicts**: Lessons built by `LessonBuilder` and `LegacyLessonBuilder` include a `macro_regime` field.
2. **Backward compatible**: Existing lessons without `macro_regime` continue to work. Disabling context forwarding (`institutional_context=()`) produces identical output to Sprint-002.
3. **Deterministic**: Same event_data + same config → same lesson dicts.
4. **No event modifications**: CPIEvent, NFPEvent, GDPEvent, PPIEvent, PMIEvent, FOMCEvent, InterestRateEvent are not modified.
5. **Extensible**: Adding a new context column name to the config tuple is sufficient to forward it.
