# FINAL REGRESSION REPORT

Date: 2026-08-02
Scope: Full regression campaign per `docs/testing/REGRESSION_PACKS.md` (12 packs, staged execution).
All figures below are measured results from the executed runs in this campaign. No production or test code was modified during reporting.

---

## 1. Regression Summary

- **Total packs:** 12
- **Total test modules:** 98
- **Total collected tests:** 2575 (manifest estimate; Pack 10A actually collected 331 vs. 329 approximate)
- **Packs passed:** 11 (Pack 01-09, Pack 10A, Pack 10B)
- **Packs failed:** 0
- **Packs not run:** 1 (Pack 11 - External Connectors / Slow; network/feed dependent, outside this campaign's scope)

---

## 2. Pack Results

| Pack | Status | Collected | Result |
|---|---|---|---|
| Pack 01 - Core / Contracts | PASS | 83 | 83 passed |
| Pack 02 - Knowledge / Learning | PASS | 221 | 221 passed |
| Pack 03 - Ingestion & Signals | PASS | 193 | 193 passed |
| Pack 04 - Macro Data, Economic Events & Calendar | PASS | 327 | 327 passed (rerun after fix: 327/327) |
| Pack 05 - Causal Intelligence (CAI / CBI) | PASS | 259 | 259 passed |
| Pack 06 - Evidence & Reasoning | PASS | 238 | 238 passed |
| Pack 07 - Thesis / Confidence / Bias | PASS | 139 | 139 passed |
| Pack 08 - Decision / Recommendation / Execution | PASS | 305 | 305 passed |
| Pack 09 - Forecast / Risk | PASS | 356 | 356 passed |
| Pack 10A - Simulation / Orchestration / Integration | PASS | 331 | 331 passed, 0 failed, 0 skipped |
| Pack 10B - Heavy Replay / Real-Data / Chronological | PASS | 19 | 19 passed, 0 failed, 0 skipped |
| Pack 11 - External Connectors / Slow | NOT RUN | 104 | Not executed (outside campaign scope) |

---

## 3. Fixes Completed During Regression

1. **Release calendar signature fix** (Pack 04) — `tests/test_release_calendar.py` updated to pass `data_dir` to the static `_release_calendar_path_for(event_type, data_dir)` helper (2 call sites). Test-side signature fix; Pack 04 rerun: 327/327 PASS.
2. **Historical replay NO_TRADE compatibility** — replay correctness handling for `NO_TRADE`/abstention decisions completed earlier in the campaign; verified by `test_cpi_result_has_correctness_fields` (decision_correct is None on abstention).
3. **FOMC fixture isolation (`auto_refresh=False`)** — FOMC calendar fixture isolated from network refresh behavior during the campaign.
4. **Temporal consistency fix** (production, `src/knowledge/reasoning/engine.py`) — resolved the Pack 10A failure in `test_institutional_validation`:
   - Added `DIRECTION_DOMINANCE_THRESHOLD = 0.6`.
   - Added `_resolve_direction_conflict()`: detects conflicting directions across horizon-separated (condition | horizon) evidence groups produced by the comparison stage.
   - Rule: if one side clearly dominates by weighted magnitude (ratio >= 0.6), that direction is preserved; otherwise the aggregate is neutralized (`avg_return_pct = 0.0`).
   - Records `direction_conflict`, `dominant_direction`, `dominance_ratio` in the aggregation step details.
   - `DecisionEngine` and `EvidenceWeighter` untouched; no test changes.
   - Verified: `tests/test_institutional_validation.py` 1/1 PASS; full Pack 10A green.
5. **Historical replay test-design optimization** (test-only, no assertion/behavior changes) — `tests/test_historical_replay.py` refactored to share identical replay results: module-scoped fixtures, one shared `run_all()` for the 9 report-assertion tests, shared real-data replay, shared chronological OOS run. Full replay invocations reduced from ~24 to 13; test count unchanged (94).

---

## 4. Remaining Known Issues

- **None.** No functional failures remain in any executed pack (Pack 01-09, 10A, 10B).
- Pack 11 (external connectors) was not executed in this campaign; its status is unverified, not failed.

---

## 5. Performance Observations

These are performance observations only, not correctness failures.

- **Pack 10B duration:** 3100.21s (51:40) wall time, single process.
- **Slowest tests (Pack 10B):**
  - `test_real_data_simulation_runs` — 2479.49s setup (full 54-release real-data replay)
  - `test_deterministic` (ChronologicalOOSEngine) — 185.19s call (2 full train/eval runs)
  - `test_engine_creates_synthetic_csvs` — 105.11s call (full 7-type `run_all()`)
  - `test_run_all_structure` — 90.36s setup (shared `report` fixture replay)
  - `test_cpi_separation_produces_results` — 96.41s setup (shared `chrono_report` fixture)
  - `test_cutoff_before_all_data` / `test_cutoff_after_all_data` — 63.84s / 54.57s calls
  - `test_gold_date_column` — 24.83s call
- **Pack 10A duration:** ~3-4 min wall (modules run individually; 331 tests).
- Pack 10B emitted 439 warnings (statsmodels convergence/line-search, numpy/pandas NaN warnings on minimal fixture data) — warnings only, no failures.
- Pre-refactor baseline for `test_historical_replay.py`: ~60-90 min (measured). Post-refactor Pack 10B: ~52 min.

---

## 6. Certification Verdict

- **Regression Status: PASS**
- **Functional Status: PASS**
- **Regression Baseline: Established**
