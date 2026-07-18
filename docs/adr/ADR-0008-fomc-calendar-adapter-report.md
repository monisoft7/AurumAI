# ADR-0008: FOMC Calendar Adapter — Implementation Report

**Date:** 2026-07-17  
**Capability:** 14.2 — FOMC Calendar Adapter  
**Status:** Complete — 450 tests pass (25 new + 425 existing), zero regressions

---

## Objective

Build a standalone calendar/metadata acquisition layer for FOMC meeting dates, enabling downstream consumers (event detectors, context enrichers, pipeline stages) to query the FOMC calendar without modifying Core v1.0, the MacroEvent ABC, or EventRegistry.

---

## Solution Architecture

```
scripts/download_fomc_calendar.py   ← Fetch from Fed JSON API / fallback
data/calendar/fomc_meetings.csv      ← Static snapshot (79 rows, 2017-2026)
src/knowledge/calendar/
  └── fomc_calendar.py               ← FOMCCalendar adapter class
```

### FOMCCalendar adapter (`src/knowledge/calendar/fomc_calendar.py`)

- **FOMCMeeting dataclass** — frozen, fields: `start_date`, `end_date`, `is_two_day`, `has_press_conference`, `statement_time`, `meeting_type`
- **FOMCCalendar class** — lazy-loads CSV on first access, exposes query methods:
  - `get_meeting(date)` → `FOMCMeeting | None`
  - `is_fomc_meeting(date)` → `bool`
  - `meetings_between(start, end)` → `list[FOMCMeeting]`
  - `meetings_in_year(year)` → `list[FOMCMeeting]`
  - `upcoming_meetings(after, n=5)` → `list[FOMCMeeting]`
  - `past_meetings(before, n=5)` → `list[FOMCMeeting]`
  - `list_years()` → `list[int]`
  - `refresh()` — clear cache, `count` — total rows
- `FOMCCalendar()` with no args reads `data/calendar/fomc_meetings.csv` by default
- Constructor accepts `Path` for custom CSV location

### Data source (`scripts/download_fomc_calendar.py`)

- Primary: Fed JSON API (`https://www.federalreserve.gov/json/calendar.json`)
  - Provides 2017-2022 and 2025-2026 (47 of 79 meetings, 60%)
  - Missing from API: 2023-2024 (32 meetings, fallback hardcoded schedule)
- Zero external runtime dependencies (Python 3 stdlib + aiohttp for fetch)

---

## Tests (`tests/test_fomc_calendar.py`)

| Class | Tests | Scope |
|-------|-------|-------|
| `TestFOMCCalendarInit` | 4 | Lazy loading, default path, refresh clears cache, missing columns |
| `TestFOMCMeetingDataclass` | 1 | Frozen dataclass contract |
| `TestGetMeeting` | 5 | Exact date (start/end), no match, `is_fomc_meeting` |
| `TestMeetingsBetween` | 3 | Full range, subset, empty |
| `TestMeetingsInYear` | 2 | Returns all for year, empty year |
| `TestUpcomingMeetings` | 2 | After date, large n |
| `TestPastMeetings` | 2 | Before date, empty |
| `TestListYears` | 1 | Sorted years |
| `TestCount` | 1 | Total count |
| `TestWithRealData` | 4 | Real CSV: known meeting, press conference field, count per year |
| **Total** | **25** | |

---

## Reuse Analysis

| Component | Source | Classification | Lines |
|-----------|--------|----------------|-------|
| Fed JSON API (47/79 meetings) | federalreserve.gov | **Reuse** | Data only |
| pandas (CSV read) | Existing project dep | **Reuse** | 1 import |
| stdlib (datetime, pathlib, dataclasses) | Python 3 | **Reuse** | 3 imports |
| pytest (framework) | Existing project dep | **Reuse** | 1 import |
| Lazy-loading pattern | Codebase convention | **Reuse** | Pattern |
| `FOMCCalendar` adapter code | New | **Build** | ~120 lines |
| Tests | New | **Build** | ~195 lines |
| Download script | New | **Build** | ~95 lines |

### Reuse percentage

- **Lines of new code:** ~315 (adapter + tests + script)
- **Reused components:** Fed API data (60% of content), pandas/stdlib/pytest (infrastructure), lazy-loading pattern
- **Estimated reuse by value:** ~55% (data source + infrastructure reuse)
- **Estimated new code by value:** ~45% (adapter, tests, download script)

---

## Key Design Decisions

1. **No Core modifications.** FOMCCalendar is a standalone utility class — zero changes to `brain.py`, `pipeline.py`, `MacroEvent`, or `EventRegistry`.
2. **Static CSV snapshot.** The CSV is committed to the repo and refreshed on demand via `download_fomc_calendar.py`. This avoids live API calls during inference and works offline.
3. **Fed JSON API as primary source.** The API is public, lightweight (no auth, no rate limiting), and covers ~60% of the data. Missing years fall back to a hand-curated schedule.
4. **Lazy loading.** The CSV is parsed only when first queried, enabling `FOMCCalendar()` construction at module level without side effects.

---

## Files Changed

| File | Status | Lines |
|------|--------|-------|
| `src/knowledge/calendar/__init__.py` | Created | 0 (empty marker) |
| `src/knowledge/calendar/fomc_calendar.py` | Created | ~120 |
| `tests/test_fomc_calendar.py` | Created | ~195 |
| `scripts/download_fomc_calendar.py` | Created | ~95 |
| `data/calendar/fomc_meetings.csv` | Created | 80 lines (79 data) |
| `docs/adr/ADR-0008-fomc-calendar-adapter-report.md` | Created | This report |

---

## Future Capabilities Enabled

- **Capability 14.3 — FOMCEvent** will use `FOMCCalendar` inside `meeting_dates()` to discover meeting windows and cross-reference data releases.
- **Context enrichers** can query `upcoming_meetings()` / `past_meetings()` to tag observations with "days since last FOMC" or "days until next FOMC".
- **Pipeline stages** can filter or weight knowledge based on proximity to FOMC meetings.
