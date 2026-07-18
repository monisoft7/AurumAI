# Capability 13.3 — Generic Event Registry Report

**Date:** 2026-07-17  
**Status:** Complete  
**Core v1.0 dependency:** Frozen (no core changes)

---

## 1. Summary

The Event Registry provides a lightweight, public, standalone registry for
`MacroEvent` subclasses. It complements the existing private `_build_registry`
inside `EconomicBrain` (Core v1.0) without modifying or replacing it.

**Implementation:** `src/knowledge/events/registry.py` — 77 lines.

**Public API:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `register(event_cls, *, replace=False)` | `type[MacroEvent]` | Register a MacroEvent subclass |
| `get(event_type)` | `str → type[MacroEvent] \| None` | Lookup by event type string |
| `get_or_raise(event_type)` | `str → type[MacroEvent]` | Lookup or raise `UnknownEventError` |
| `list_events()` | `→ list[str]` | Sorted list of registered event types |
| `is_registered(event_type)` | `str → bool` | Check if an event type is registered |
| `clear()` | `→ None` | Remove all registrations (for testing) |

**Custom exceptions:**
- `DuplicateEventError` — raised on duplicate registration (unless `replace=True`)
- `UnknownEventError(KeyError)` — raised by `get_or_raise` for unknown types

---

## 2. Design Decisions

### 2.1 Class-level registry (not instance-level)

`EventRegistry` uses `@classmethod` and a shared `_events` dict. No
instantiation needed. This keeps the registry accessible from anywhere without
dependency injection or global state management.

### 2.2 Registry by event_type string (not by class)

The key is the `event_type` class attribute (a string), not the class itself.
This allows lookup by human-readable name (e.g., `"CPI"`, `"NFP"`) without
importing the class.

### 2.3 Two resolution strategies for event_type

The registry handles two patterns:

1. **Class-attribute** (preferred, used by `CPIEvent`):
   ```python
   class CPIEvent(MacroEvent):
       event_type = "CPI"
   ```
2. **`@property`** (for advanced use):
   ```python
   class DynamicEvent(MacroEvent):
       @property
       def event_type(self) -> str: ...
   ```

### 2.4 No modification to MacroEvent ABC

The registry inspects the existing `event_type` attribute. No new abstract
methods or base class changes were needed.

### 2.5 CPI registered at import time

The single line `EventRegistry.register(CPIEvent)` in
`src/knowledge/events/__init__.py` ensures CPI is registered when the
`knowledge.events` package is imported. Future events follow the same pattern.

---

## 3. CPI Registration (No Behavior Change)

CPIEvent continues to work identically. The registry adds zero overhead to the
existing CPI data pipeline — it is a purely informational index.

**Verified by `test_cpi_behavior_unchanged`:**
- `CPIEvent()` can be instantiated directly (no dependency on registry)
- `load_and_extract()` returns expected columns (`cpi_pressure`,
  `cpi_change_pct`)
- `build_lesson_fields()` returns expected fields
- `lesson_text()` produces expected text
- `CPI` key is registered and discoverable

---

## 4. Future Event Support

The registry supports any `MacroEvent` subclass with a string `event_type`.
Future event types (NFP, FOMC, GDP, PMI) require only:

1. Create the subclass (e.g., `class NFPEvent(MacroEvent): event_type = "NFP"`)
2. Register it: `EventRegistry.register(NFPEvent)` (typically in
   `__init__.py`)

No architectural changes needed. Verified by `test_future_event_type_works` and
`test_registry_supports_all_expected_future_events`.

---

## 5. Tests

19 tests in `tests/test_event_registry.py`:

| Test | Coverage |
|------|----------|
| `test_register_event` | Register a dummy MacroEvent subclass |
| `test_register_multiple_events` | Register multiple event types |
| `test_register_rejects_non_macro_event` | TypeError for non-MacroEvent |
| `test_duplicate_registration_raises_error` | DuplicateEventError without replace |
| `test_duplicate_registration_with_replace` | replace=True allows override |
| `test_duplicate_error_message` | Error message includes type name |
| `test_get_returns_none_for_unknown` | `get()` returns None for unknown |
| `test_get_or_raise_returns_class` | `get_or_raise()` returns registered class |
| `test_get_or_raise_raises_for_unknown` | UnknownEventError for unknown |
| `test_list_events_empty` | Empty list after clear |
| `test_list_events_returns_sorted` | Sorted alphabetical order |
| `test_is_registered_true` | True for registered event |
| `test_clear_removes_all` | Clear removes all registrations |
| `test_clear_is_idempotent` | Consecutive clears are safe |
| `test_cpi_is_registered_by_default` | CPI registered at import time |
| `test_cpi_can_be_instantiated_from_registry` | `CPIEvent()` via registry lookup |
| `test_cpi_behavior_unchanged` | CPIEvent works identically as before |
| `test_future_event_type_works` | Dummy NFP/FOMC/GDP/PMI classes register |
| `test_registry_supports_all_expected_future_events` | All 5 planned types register |

**All 403 tests pass** (376 core + 8 DXY + 19 registry).

---

## 6. Core v1.0 Compliance

| Constraint | Status |
|-----------|--------|
| No core architecture changes | ✅ Standalone registry, no pipeline changes |
| No InferencePipeline changes | ✅ Not touched |
| No Reasoning redesign | ✅ Not touched |
| No Decision redesign | ✅ Not touched |
| No Learning redesign | ✅ Not touched |
| No MacroEvent ABC changes | ✅ No new abstract methods |
| Existing `_build_registry` untouched | ✅ Complements, does not replace |
| Existing `EconomicEvent` enum untouched | ✅ Not modified |
| Zero overhead on existing code paths | ✅ Registry is informational only |
| Future events require no architectural work | ✅ Register any MacroEvent subclass |

---

## 7. Files

| File | Purpose | Lines |
|------|---------|-------|
| `src/knowledge/events/registry.py` | EventRegistry + custom exceptions | 77 |
| `src/knowledge/events/__init__.py` | CPI registration at import time | 47 |
| `tests/test_event_registry.py` | 19 tests | 254 |

---

## 8. Recommendation

**Event Registry is ready for use with Core v1.0.**

- CPI is registered by default at import time
- Future events register with a single line
- No impact on existing functionality
- All 403 tests pass

**Next steps (post-freeze):**
- Register NFP, FOMC, GDP, PMI as MacroEvent subclasses are implemented
- Extend registry with metadata queries if needed (e.g., list events by country,
  importance, or asset)
