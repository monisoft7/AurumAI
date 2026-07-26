# Sprint-002-Ownership-Verification

**Date:** 2026-07-25  
**Target Capability:** C-03 (MacroRegimeDetector Activation)  
**Question:** Can `MacroRegimeFeatureExtractor` be activated in the institutional pipeline WITHOUT modifying `FeatureExtractionEngine`?  
**Method:** Exhaustive investigation of all 5 ownership paths against existing code.

---

## 1. Ownership Model (Current State)

Every concrete event owns its own `FeatureExtractionEngine` instance, created in `__init__`:

```
event_cls = CPIEvent, NFPEvent, GDPEvent, InterestRateEvent, PPIEvent, PMIEvent, FOMCEvent

event.__init__:
    self._extraction_engine = FeatureExtractionEngine()   ← private ownership
    self._extractor = CPIFeatureExtractor()               ← private ownership

event.load_and_extract(path):
    raw = self.load_raw(path)
    fs = self._extraction_engine.process(raw, self._extractor)
    return fs.data
```

The orchestrator (`stages.py:_ingest_event`) creates events via `event_cls()` — no args, no DI. The engine is a **private implementation detail** of each event, unreachable from outside.

---

## 2. Five Extension Points — Investigated

### 2.1 Existing Dependency Injection

| Check | Result |
|-------|--------|
| DI framework present? | **No** — no container, no injector, no IoC |
| Constructor injection into engine? | **No** — engine created inside event's `__init__`, no parameterized path from pipeline |
| Setter injection into engine? | **No** — engine has no setter / add-method for additional extractors |
| Event constructor accepts engine? | **No** — `CPIEvent.__init__(release_calendar_path=None)`; other events `__init__()` take no args |

**Verdict:** Cannot reach `FeatureExtractionEngine` via DI. ❌

---

### 2.2 Orchestration Wiring

| Check | Result |
|-------|--------|
| Orchestrator has pre-processing hooks? | **No** — DAG runner, no middleware/interceptors |
| Stage functions accept engine reference? | **No** — `_ingest_event` creates event, stores `params["_event"]`, cannot access `_extraction_engine` (private) |
| Orchestrator can modify event after creation? | Monkey-patching possible but **fragile**: `event.load_and_extract = patched_func.__get__(event)` — breaks determinism guarantees, not architecture-compliant |
| New setup stage can inject into engine? | Not without adding a public method to the event (e.g., `event.add_extractor(...)`) — requires modifying each event class |

**Verdict:** No clean orchestration path that avoids modifying either engine or events. ❌

---

### 2.3 Event Composition

**Option A: Wrapper (RegimeAwareMacroEvent)**
- Creates a `MacroEvent` wrapper that delegates all abstract methods to inner event
- Overrides `load_and_extract` / `load_and_extract_with_calendar` to call `regime_extractor.extract(df)` AFTER engine.process()
- 6 abstract methods must be proxied: `event_type`, `lesson_version`, `condition_columns`, `knowledge_version`, `build_lesson_fields`, `lesson_text`
- Plus optional: `metadata`
- Plus concrete methods: `load_and_extract_with_calendar`, `build_reasoning_condition`

**Does NOT involve FeatureExtractionEngine** — regime is added after `engine.process()` returns.

| Check | Result |
|-------|--------|
| Wrapper possible? | **Yes** — clean delegation, one new file |
| Engine receives regime signal? | **No** — regime added post-process |
| Regime in extracted features? | **Yes** — `fs.data` has `macro_regime` column |
| Changes needed per event? | **Zero** — single wrapper works for all 7 events |
| Determinism preserved? | **Yes** — extractor is deterministic |

**Option B: Mixin / Helper per event**
- Add a `_enrich_with_regime(df)` helper to each event's `load_and_extract`
- Regime added BEFORE calling `engine.process()` (raw data already has `macro_regime`)
- Engine passively processes the regime column (passes through, validate() allows extra columns)

**Involves FeatureExtractionEngine** minimally — engine processes data that already contains `macro_regime`.

| Check | Result |
|-------|--------|
| Modify each event? | **Yes** — 7 files changed |
| Engine receives regime signal? | **Passively** — regime in raw data, but engine doesn't actively run regime extractor |
| Regime in extracted features? | **Yes** |
| Determinism preserved? | **Yes** |

**Verdict:** Event composition CAN activate regime via wrapper (clean, one file), but engine does NOT receive the signal. ❌ for AC criterion #1. ⚠️ for "regime in extracted features".

---

### 2.4 Pipeline Composition

| Check | Result |
|-------|--------|
| InferencePipeline is frozen? | **Yes** — 7-stage pipeline cannot be modified |
| PipelineContext accepts custom lesson_builder? | **Yes** — `PipelineContext.lesson_builder` is injected in `_build_legacy_pipeline` |
| LessonBuilder subclass can add regime? | **Yes** — `RegimeAwareLegacyLessonBuilder.build()` calls `self.event.load_and_extract()`, then adds regime via extractor, THEN builds lessons |
| This involves FeatureExtractionEngine? | **No** — regime added after engine.process(), same as wrapper approach |
| Existing precedent? | **Yes** — `YieldContextEnricher` adds columns AFTER lesson building (post-extraction enrichment pattern) |

```
Existing flow:
  event.load_and_extract() → engine.process() → feature_set.data
                                                     ↓
                              YieldContextEnricher.enrich(lessons_csv)
                                                     ↓
                                            enriched CSV with yield columns

Proposed analogy:
  event.load_and_extract() → engine.process() → feature_set.data
                                                     ↓
                              regime_extractor.extract(event_data) ← new step
                                                     ↓
                                            build lessons with macro_regime
```

**Verdict:** Clean pipeline composition possible via LessonBuilder subclass, but engine does NOT receive the signal. ❌ for AC criterion #1.

---

### 2.5 Existing Extension Hooks

| Hook Point | Exists? | Can inject regime? |
|------------|---------|-------------------|
| `FeatureExtractor.extract()` called within engine | **No** — single extractor, no chain | — |
| `FeatureSet.validate()` | **Yes**, but only checks defined features exist | Extra columns pass through, but this is passive acceptance, not an extension hook |
| `MacroEvent.load_and_extract_with_calendar()` default impl | **Yes**, calls `self.load_and_extract()` | No pre/post hooks |
| `EventRegistry` | **No** — class-level registration only, no hooks | — |
| `PipelineContext` | Data class with fields, no hooks | — |
| `Orchestrator` | DAG runner, no hooks | — |

**Verdict:** No extension hooks exist that can inject into FeatureExtractionEngine. ❌

---

## 3. Cross-Cutting Finding: FeatureSet Tolerance

`FeatureSet.validate()` only checks that all **defined** features exist in the data. Extra columns (like `macro_regime`) pass through silently regardless of where they're added — before, during, or after extraction. This is **not a hook** but a compatibility property.

This means:
- Regime CAN be added at ANY point in the data flow (before engine, after engine, at lesson level)
- Adding it after the engine is architecturally sound (same pattern as YieldContextEnricher)
- BUT the acceptance criterion "FeatureExtractionEngine receives regime signal" is only satisfied if the engine is involved

---

## 4. Verdict

| Criterion | Wrapper | LessonBuilder Subclass | Modify FeatureExtractionEngine |
|-----------|---------|----------------------|-------------------------------|
| Engine receives regime signal | ❌ | ❌ | ✅ |
| Regime in extracted features | ✅ | ✅ | ✅ |
| Deterministic | ✅ | ✅ | ✅ |
| Zero changes to events | ✅ | ✅ | ✅ |
| One-file change | ✅ | ✅ | ✅ |
| Follows existing pattern | ✅ (delegation) | ✅ (YieldContextEnricher) | ✅ (minimal, backward-compatible) |

**Only modifying `FeatureExtractionEngine` satisfies all three acceptance criteria.**

The modification required is minimal and backward-compatible:
- Add a class-level `_global_extractors` list to `FeatureExtractionEngine`
- Add `register_global()` / `clear_global()` classmethods
- Modify `process()` to run global extractors after the primary extractor
- No changes to `FeatureExtractor ABC`, `MacroEvent ABC`, any event class, or any frozen component

---

## 5. Recommendation

**Approve** modification of `FeatureExtractionEngine` as the smallest correct increment that:

1. Satisfies all acceptance criteria
2. Involves zero changes to events or frozen components
3. Is backward-compatible (all existing callers pass a single extractor as before)
4. Follows a clean ownership transfer: the engine owns extraction, the pipeline registers global extractors, the engine runs them
