# BASELINE V1 CERTIFICATION

Date: 2026-08-02
Baseline commit: `447c04573ee804cc551c7121f92cfa8b42d5d9dd`
Status: **CERTIFIED FOR V1.X DEVELOPMENT**

---

## 1. Executive Summary

The V1 engineering baseline is certified. All executed regression packs pass
(Pack 01-09, Pack 10A, Pack 10B; 11/11 executed packs green, 0 failures).
The architecture boundary is frozen (CER-010), workflow-ID conformance is
verified, the institutional acceptance benchmark passes, and determinism is
established. This commit `447c045` becomes the certified engineering baseline
from which all future v1.x work must branch.

---

## 2. Scope

### PROJECT_SCOPE_V1
- Governing document: `docs/PROJECT_SCOPE_V1.md` (referenced by production code,
  e.g. scenario generation confidence proxy, `src/scenario_generation/generator.py:52`).

### Certified workflow IDs
- Canonical workflow index: `IMPLEMENTATION_WORKFLOWS.md` (Workflow Index table).
- Workflow-ID conformance verified by `tests/test_workflow_id_conformance.py`
  (Pack 01, PASS): every implemented institutional workflow package declares its
  canonical W-ID (W1-W17 scheme), e.g. `thesis_update`=W10,
  `scenario_generation`=W12, `risk_reward_validation`=W12,
  `bias_prevention`=W13, `decision_engine`=W13.

### Frozen architecture boundary
- `docs/audit/CER-010-Architecture-Freeze-v2.md` — architecture freeze in effect.
- Architecture audits A1, A1.5, A2 (`docs/audit/Architecture-Audit-A*.md`) — PASS.
- No production code modified during certification reporting.

---

## 3. Certification Evidence

| Evidence | Source | Result |
|---|---|---|
| Architecture Audit | `docs/audit/CER-010-Architecture-Freeze-v2.md`, Architecture-Audit-A1/A1.5/A2 | PASS |
| Workflow conformance | `tests/test_workflow_id_conformance.py` (Pack 01) | PASS |
| Regression packs | Pack 01-09, Pack 10A, Pack 10B (`docs/testing/REGRESSION_PACKS.md`) | 11/11 executed packs PASS |
| Benchmark gate | `tests/test_benchmark.py` — institutional acceptance benchmark (reasoning_accuracy >= 0.8, precision_at_1 >= 0.9, retrieval_accuracy >= 0.75, consensus_accuracy >= 0.8, conflict_detection_rate >= 0.5, determinism_score >= 1.0, ...) | PASS |
| Determinism | `TestHistoricalReplayEngine::test_deterministic` / `TestChronologicalOOSEngine::test_deterministic` (Pack 10B) + benchmark `determinism_score` | PASS |
| Backward compatibility | `tests/test_compat.py` (Pack 01) | PASS |

---

## 4. Regression Results

| Pack | Status | Collected |
|---|---|---|
| Pack 01 - Core / Contracts | PASS | 83 |
| Pack 02 - Knowledge / Learning | PASS | 221 |
| Pack 03 - Ingestion & Signals | PASS | 193 |
| Pack 04 - Macro Data, Economic Events & Calendar | PASS | 327 |
| Pack 05 - Causal Intelligence (CAI / CBI) | PASS | 259 |
| Pack 06 - Evidence & Reasoning | PASS | 238 |
| Pack 07 - Thesis / Confidence / Bias | PASS | 139 |
| Pack 08 - Decision / Recommendation / Execution | PASS | 305 |
| Pack 09 - Forecast / Risk | PASS | 356 |
| Pack 10A - Simulation / Orchestration / Integration | PASS | 331 |
| Pack 10B - Heavy Replay / Real-Data / Chronological | PASS | 19 |

Note: Pack 11 (External Connectors / Slow) is network/feed-dependent and was not
executed as part of this certification; its status is unverified, not failed.

---

## 5. Fixed During Certification

Every fix verified during this certification campaign:

1. **Release calendar signature fix** (test-side) — `tests/test_release_calendar.py`
   updated to pass `data_dir` to `_release_calendar_path_for(event_type, data_dir)`.
   Pack 04 rerun: 327/327 PASS.
2. **Historical replay NO_TRADE compatibility** — replay correctness for
   `NO_TRADE`/abstention decisions; verified by
   `test_cpi_result_has_correctness_fields` (Pack 10B).
3. **FOMC fixture isolation (`auto_refresh=False`)** — FOMC calendar fixture
   isolated from network refresh behavior.
4. **Temporal consistency fix** (production, `src/knowledge/reasoning/engine.py`) —
   added horizon-separated direction-conflict resolution (`DIRECTION_DOMINANCE_THRESHOLD`,
   `_resolve_direction_conflict`, records `direction_conflict` / `dominant_direction` /
   `dominance_ratio`; neutralized aggregate when no side dominates). Resolved the
   Pack 10A `test_institutional_validation` failure. `DecisionEngine` and
   `EvidenceWeighter` untouched.
5. **Historical replay test-design optimization** (test-only) — shared
   module-scoped replay fixtures in `tests/test_historical_replay.py`; replay
   invocations reduced ~24 -> 13; test count unchanged (94); assertions unchanged.

---

## 6. Remaining Non-Functional Observations

Performance observations only — not correctness failures:

- Pack 10B wall time: 3100.21s (51:40), single process.
- Slowest tests: `test_real_data_simulation_runs` (2479.49s setup — full 54-release
  real-data replay), `test_deterministic` ChronologicalOOS (185.19s — 2 full
  train/eval runs), `test_engine_creates_synthetic_csvs` (105.11s), shared
  fixture setups (~90-96s), cutoff tests (~54-64s each).
- Pack 10B emitted 439 warnings (statsmodels convergence/line-search, numpy/pandas
  NaN warnings on minimal fixture data) — warnings only, no failures.
- Pack 11 (external connectors) not executed — out of certification run scope.

---

## 7. Certified Baseline

This commit — **`447c04573ee804cc551c7121f92cfa8b42d5d9dd`** — is the **v1.x
certified engineering baseline**. All future v1.x development must branch from
this commit. Changes landing on this baseline without certification-gate approval
are prohibited.

---

## 8. Baseline Metrics

- **Test modules:** 98
- **Total collected tests:** 2575
- **Regression packs:** 12 defined; 11 executed and PASS; 1 not executed (Pack 11, external connectors)
- **Benchmark status:** PASS (institutional acceptance benchmark gate)
- **Architecture status:** PASS (architecture freeze CER-010 + audits A1/A1.5/A2)

---

## 9. Certification Verdict

**CERTIFIED FOR V1.X DEVELOPMENT**
