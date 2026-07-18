# Capability 14.1 — NFP Event Report

**Date:** 2026-07-17  
**Status:** Complete  
**Core v1.0 dependency:** Frozen (no core changes)

---

## 1. Summary

NFPEvent is the first new MacroEvent subclass added on top of frozen Core v1.0
using the new EventRegistry. It proves that the architecture is truly generic
and that adding a new event type requires **only event-specific logic** — no
pipeline, builder, aggregator, or registry changes.

**Data source:** `data/economic/PAYEMS.csv` — FRED series PAYEMS (All Employees,
Total Nonfarm), already in the repository.

**NFP→Gold causal pathway (academic):**
- NFP is negatively correlated with gold return volatility (Salisu, Bouri,
  Gupta, *Quarterly Review of Economics and Finance*, 2022)
- Mechanism: NFP beat → USD strengthens → gold falls (inverse dollar channel)
- Unlike CPI (inflation → real yield → gold), NFP operates primarily through
  the dollar channel

---

## 2. Research Classification

Before implementing, 14 candidates were evaluated from OSS and academic sources:

| Candidate | Source | Classification | Rationale |
|-----------|--------|---------------|-----------|
| `MacroEvent` ABC | Codebase | **Reuse** | Core v1.0 frozen |
| `StandardEventMetadata` | Codebase | **Reuse** | Same fields as CPI |
| `FeatureExtractionEngine` | Codebase | **Reuse** | Generic; swap extractor |
| `FeatureExtractor` | Codebase | **Reuse** | ABC, unchanged |
| `Feature` / `FeatureSet` | Codebase | **Reuse** | Unchanged |
| `LessonBuilder` | Codebase | **Reuse** | Accepts any `MacroEvent` |
| `LessonSummaryAggregator` | Codebase | **Reuse** | Generic |
| `EventRegistry` | Codebase | **Reuse** | `register(NFPEvent)` only |
| `CPIFeatureExtractor pattern` | Codebase | **→ Adapt** | NFP-specific columns, thresholds |
| `CPIEvent pattern` | Codebase | **→ Adapt** | NFP-specific logic |
| OpenBB consensus/actual model | OpenBB | **Reject** | No consensus data in local PAYEMS.csv |
| TradingEconomics calendar | OpenBB | **Reject** | Requires live API |
| BLS multi-component report | BLS | **Reject** | Would need multiple FRED series |
| GARCH-MIDAS volatility model | Academic | **Reject** | Too complex for directional classification |
| QuantConnect NFP strategies | QuantConnect | **Reject** | Strategy logic not applicable |

---

## 3. Architecture Verification

Before writing any code, every component was audited for CPI-specific
assumptions that could block NFP:

| Component | CPI References | Blocks NFP? |
|-----------|---------------|-------------|
| `FeatureExtractionEngine` | 0 | ✅ No |
| `FeatureExtractor` (ABC) | 0 | ✅ No |
| `Feature` / `FeatureSet` | 0 | ✅ No |
| `LessonBuilder` | 4 (import, 3 defaults) | ⚠️ Defaults only |
| `InferencePipeline` | 0 | ✅ No |
| `PipelineContext` | 0 | ✅ No |
| `LessonSummaryAggregator` | 5 (defaults only) | ⚠️ Defaults only |
| `EventRegistry` | 0 | ✅ No |

**Finding:** All 11 CPI references are in **default values** and **import
fallbacks** (e.g., `event = event or CPIEvent()`). Every component accepts its
dependencies through constructor/config injection. **Zero refactoring was
required** — NFP simply passes its own event, config, and data paths.

---

## 4. NFP-Specific Design

### 4.1 Feature Extractor (`src/knowledge/features/extractors/nfp.py`, 38 lines)

| Feature | Computation | Purpose |
|---------|-------------|---------|
| `previous_value` | `Value.shift(1)` | Lagged PAYEMS level |
| `nfp_change` | `Value - previous_value` | MoM payrolls change (thousands) |
| `nfp_trend` | Classification | `jobs_market_improving` (>200K),
  `jobs_market_stable` (100-200K),
  `jobs_market_deteriorating` (<100K) |

### 4.2 Event (`src/knowledge/events/nfp.py`, 76 lines)

| Attribute | Value |
|-----------|-------|
| `event_type` | `"NFP"` |
| `lesson_version` | `"nfp_gold_v1"` |
| `condition_columns` | `["nfp_trend"]` |
| `knowledge_version` | `"nfp_gold_summary_v1"` |
| `metadata.country` | `"US"` |
| `metadata.importance` | `3` |
| `metadata.source` | `"Bureau of Labor Statistics"` |
| `metadata.unit` | `"thousands"` |

---

## 5. Files

| File | Status | Lines | Type |
|------|--------|-------|------|
| `src/knowledge/features/extractors/nfp.py` | **New** | 38 | Adapted |
| `src/knowledge/events/nfp.py` | **New** | 76 | Adapted |
| `src/knowledge/events/__init__.py` | Modified | +2 | Import + register |
| `tests/test_nfp_event.py` | **New** | 389 | New |
| `tests/test_event_registry.py` | Modified | +3 lines | Fixture scope |
| `src/knowledge/features/extractors/__init__.py` | Unchanged | 0 | — |

**Core v1.0**: 0 files modified.  
**EventRegistry**: 0 files modified (one `register()` call).  
**LessonBuilder / LessonSummaryAggregator / InferencePipeline**: 0 files modified.

---

## 6. Reuse Percentage

| Category | Lines | Components |
|----------|-------|------------|
| **Reused** (untouched) | ~658 | MacroEvent ABC, StandardEventMetadata, FeatureExtractionEngine,
  FeatureExtractor, Feature, FeatureSet, LessonBuilder,
  LessonSummaryAggregator, EventRegistry |
| **Adapted** (new, NFP-specific) | 114 | NFPEventFeatureExtractor, NFPEvent |
| **New tests** | 389 | test_nfp_event.py |

**System code reuse: ~85%** (658 / 772 lines).  
**Infrastructure reuse: 100%** — every pipeline, builder, aggregator, and
registry component was reused without modification.

---

## 7. Acceptance Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| No Core modifications | ✅ | 0 Core files changed |
| Existing tests pass | ✅ | 403 → **425 passed** (403 existing + 22 new) |
| New NFP tests pass | ✅ | 22/22 passed |
| EventRegistry auto-exposes NFP | ✅ | `EventRegistry.get("NFP")` returns NFPEvent |
| ADR report | ✅ | This document |

### 7.1 Proving Generic Architecture

The most important test: `test_lesson_builder_with_nfp_event` proves that
`LessonBuilder` works with `NFPEvent` without any code changes:

```python
builder = LessonBuilder(config=config, event=NFPEvent())
lessons = builder.build()
assert list(lessons["event_type"]) == ["NFP", "NFP"]
assert "After NFP changed by" in lessons.iloc[0]["lesson_text"]
```

The end-to-end test `test_knowledge_from_nfp_lessons` proves that the full
pipeline (LessonBuilder → LessonSummaryAggregator) produces correct NFP
knowledge records without any changes to either component.

---

## 8. Comparison: CPI vs NFP Architecture

| Aspect | CPI | NFP | Same Code? |
|--------|-----|-----|------------|
| Event class | `CPIEvent` | `NFPEvent` | Subclass of MacroEvent |
| Feature extractor | `CPIFeatureExtractor` | `NFPEventFeatureExtractor` | Subclass of FeatureExtractor |
| Feature engine | `FeatureExtractionEngine` | `FeatureExtractionEngine` | **Identical** |
| Lesson builder | `LessonBuilder` | `LessonBuilder` | **Identical** |
| Lesson aggregator | `LessonSummaryAggregator` | `LessonSummaryAggregator` | **Identical** |
| Event registry | `EventRegistry` | `EventRegistry` | **Identical** |
| Data source | `CPIAUCSL.csv` | `PAYEMS.csv` | Same Date/Value format |
| NFP-specific code | — | 114 lines | Only the delta |

---

## 9. Recommendation

**NFPEvent is complete and the architecture is proven generic.**

- Adding a new event type required **only** a feature extractor (38 lines) and
  an event class (76 lines) — no pipeline, builder, or infrastructure changes.
- Core v1.0 remains frozen.
- All 425 tests pass.

**Next steps (post-freeze):**
- Register FOMC, GDP, PMI, PPI as MacroEvent subclasses (each follows the same
  pattern; estimated ~40–80 lines of event-specific code each)
- Implement event-to-event chaining (e.g., combine NFP + CPI conditions in a
  single knowledge record)
- Add `scripts/nfp_capability.py` to run a full NFP→gold validation pipeline
  (analogous to `dxy_capability.py`)
