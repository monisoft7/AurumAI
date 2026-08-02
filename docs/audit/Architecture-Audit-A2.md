# Architecture Audit A2 — Final Certification Audit

**Auditor**: opencode (Phase A2)
**Date**: 2026-08-01
**Scope**: Certification sprint verification against `docs/PROJECT_CONSTITUTION_V2.md`, `IMPLEMENTATION_WORKFLOWS.md`, and `docs/audit/Certification-Summary.md`
**Mode**: AUDIT ONLY — no code modified, no refactor, no commits created, no fixes implemented
**Method**: Source inspection of the 25-job default DAG (`src/orchestration/orchestrator.py`), all 25 stage functions (`src/orchestration/stages.py`), the institutional packages, the conformance registry (`tests/test_workflow_id_conformance.py`), full-suite collection, benchmark gate run, and git-status verification of frozen-core integrity.

---

## 1. Audit Scope and Baseline

The certification sprint implemented W4 (`event_triage`), W10 (`thesis_update`), and W13 (`bias_prevention`) and re-labelled the W-IDs of four pre-existing packages per A1 finding A-001. The audited pipeline is the institutional chain `pre_market_scan → … → trade_recommendation` running inside the 25-job default DAG, which also still registers the legacy chain (`ingest_event → build_legacy_pipeline → forecast → risk_gate → finalize`).

Verification runs performed during A2:

| Run | Result |
| --- | --- |
| Affected suites (7 files, incl. conformance, orchestrator, W4/W10/W13 tests) | **202 passed** |
| Benchmark gate `tests/test_benchmark.py` | **18 passed, 0 failures** |
| Full-suite collection (`pytest --co`) | **2554 tests collected, 2 collection errors** |
| Full-suite execution | Aborted after 30 min (slow tests); full-suite green state not re-established |
| Frozen-core integrity | `git status`: zero modifications under `src/knowledge/` |

---

## 2. Passed Checks

| # | Check | Verdict | Evidence |
| --- | --- | --- | --- |
| P-1 | Workflow order (institutional spine) | **PASS** | DAG order W3→W4→W5→W6→W7→W8→W10→W9→W13→W13(decision)→W14 (`orchestrator.py:234-350`); W4 after W3 before W5 per spec |
| P-2 | Every implemented workflow exists and is reachable from the DAG | **PASS** | All 14 institutional packages registered as jobs; single root `pre_market_scan`; full-pipeline test asserts the 25-job set |
| P-3 | Workflow identity (A-001 remediation) | **PASS** | Conformance registry maps 14 packages to canonical W-IDs; `created_by` strings conform (e.g. `W13 DecisionEngine` `engine.py:56`, `W10 ThesisUpdater` `updater.py:234`, `W4 SignalTierer` `tierer.py:83`, `W13 BiasReviewer` `detector.py:27`); test asserts no module docstring declares an off-workflow ID |
| P-4 | Contract flow along DAG edges | **PASS** | Every institutional stage consumes exactly the result keys of its declared dependencies (`stages.py:379-752`); W4/W10/W13 contracts flow construction→update→confidence→bias→decision |
| P-5 | Every contract has exactly one producer | **PASS (certified layer)** | `SignalTiering`, `ThesisUpdate`, `BiasReview`, `InstitutionalConfidence`, `ThesisConstruction`, `CounterEvidenceAssessment`, `ScenarioGeneration`, `RiskRewardValidation`, `InstitutionalDecision`, `InstitutionalTradeRecommendation` each defined once, in their owning package |
| P-6 | Backward compatibility | **PASS** | Every new stage degrades gracefully when its input is absent (error dicts, `{}` results); `_confidence_engine` falls back to `thesis_construction` when `thesis_update` absent (`stages.py:554-582`); `_decision_engine` applies the bias gate only when `bias_prevention` is present (`stages.py:688-696`); verified by tests |
| P-7 | Circular imports (module level) | **PASS** | Full-suite collection succeeded (2554 tests) with no ImportError; new packages (`event_triage`, `thesis_update`, `bias_prevention`) import forward-only |
| P-8 | Frozen-core integrity | **PASS** | No file under `src/knowledge/` modified (git status clean); benchmark gate 18/18; constitution rules 3, 7, 10, 12 (Section 12) respected by the sprint's additions |
| P-9 | Determinism of new workflows | **PASS** | W4/W10/W13 use content-derived IDs; determinism asserted by tests (e.g. `test_determinism` in `tests/test_bias_prevention.py`) |
| P-10 | W4 threshold compliance | **PASS** | Tier 1 `>0.7/>0.8/>0.9`, Tier 2 `>0.3/>0.5/>0.5` per `IMPLEMENTATION_WORKFLOWS.md` W4 stage 5 |
| P-11 | W10 action set | **PASS** | Actions `no_change/scale/hedge/pause/exit` and triggers `periodic/cumulative_evidence/threshold_crossing/regime_break` per spec W10 |
| P-12 | W13 decision gate | **PASS** | `apply_bias_review` records the review on decision metadata and downgrades directional decisions to NO_TRADE when human review is required (`bias_prevention/contracts.py:153-195`); consumed by `_decision_engine` |
| P-13 | W13 severity/threshold documentation | **PASS** | Fixed documented thresholds (conviction > 0.7 with evidence strength < 0.5; `temporal_recency < 0.5`; horizon ≤ 30 days) per constitution §2.2 |

---

## 3. Failed Checks

| # | Check | Verdict | Finding |
| --- | --- | --- | --- |
| F-1 | No legacy path bypasses the institutional pipeline | **FAIL — Critical** | `_finalize` reads `results.get("decision_engine")` (`stages.py:758`) but `finalize` does not declare `decision_engine` as a dependency (`orchestrator.py:433-435`). Level ordering puts `finalize` at level 6 and `decision_engine` at level 11, so the institutional decision (including the bias gate) is **never** present when `finalize` runs. The run bundle's `decision` is therefore always the legacy STRONG_POSITIVE-style decision, and the bias-gated institutional decision is silently dropped from the reported outcome. A1 finding A-005 persists in effect: the stage-level fix exists but the DAG edge is missing. |
| F-2 | Every workflow consumes only documented upstream contracts | **FAIL — High** | W9 consumes only the thesis (`_confidence_engine`, `stages.py:550-586`); the W9-spec inputs (W2 regime clarity, W6 evidence, W12 downside case, W16 window consistency, OOS ECE) are all absent. W13 consumes no W5 consensus narrative, no W1 historical analogues, no W14 journal. W10 consumes no portfolio P&L (realization-bias input per spec). W12 (`scenario_generation`) consumes construction + confidence only; no failure-condition extraction, no base rates, no fragility score (spec W12 stages 1–6), and it runs **after** W9 while the spec requires W12 to be invoked by W8 stage 4, before W9. |
| F-3 | Workflow completeness | **FAIL — High** | 14 of 17 spec workflows exist. W11 (Causal Relationship Evaluation) has no workflow, no package, no conformance entry. W1 (KR Ingestion) is orphaned and unreachable (465 LOC, no importer). W2 (Regime) exists only as partial frozen-core capability, unwired (GRAM residual analyzer unused). W15, W16, W17 absent. |
| F-4 | W13 checklist completeness | **FAIL — High** | Spec W13 mandates the 10-mistake checklist; 5 items have no dedicated check: base_rate_neglect, attribution_error, groupthink, false_precision, this_time_is_different. Implemented checks (7): confirmation, anchoring, overconfidence, recency, narrative-trap-equivalent, plus two non-spec extensions (single_source, regime_blindness). The missing items cannot be implemented without absent upstreams (W1 base rates, W14 journal, W5 narrative). |
| F-5 | Duplicate logic | **FAIL — High (pre-existing, unchanged)** | Two `DecisionEngine` classes (`decision_engine/engine.py` vs frozen `knowledge/decision/engine.py`); two `Evidence` contracts (20-field `evidence_collection/contracts.py:14` vs frozen 14-field `knowledge/evidence/evidence.py:11`); two `EvidenceCollection`; two `EvidenceWeighter` with divergent math (`evidence_reasoning/weighter.py:10` vs frozen `knowledge/evidence/weighting.py:48`); two orchestration engines; two news ingestion paths (one broken). A-007/A-008/A-009/A-010 remain open. |
| F-6 | Dead code | **FAIL — Medium (pre-existing, unchanged)** | `connectors/cb_gold_fetcher.py`, `knowledge/regime/gram_residual.py`, `knowledge/ingestion/ingestion_pipeline.py`, `knowledge/decision/validator.py` have zero importers; `execution/` and `technical/` have no `src/` dependents. A-018/A-019 remain open. |
| F-7 | Hidden coupling | **FAIL — Medium** | (a) Undeclared `finalize → decision_engine` edge (F-1). (b) `_ingest_news` imports `news.collector` which does not exist (module is `news/news_collector.py`); ImportError is silently swallowed (`stages.py:52-57`); A-011 remains open. (c) `_evidence_collection` reads `params.get("knowledge_graph")` which no job ever sets — evidence collected with `knowledge_graph=None` (A-014). (d) `pre_market_scan` runs as a root job with `regime=""`/`regime_confidence=0.0` defaults — W3 runs without W2 regime (A-015). (e) All stage boundaries remain untyped dict plumbing (A-012). |
| F-8 | Dependency direction | **FAIL — Medium (pre-existing, unchanged)** | Package-level SCC persists: `knowledge/evolution/applicator.py → simulation` and `simulation/historical_replay.py → orchestration` (A-006). No module-level import cycle. |
| F-9 | Provenance chain | **FAIL — Low** | W4/W6(collector)/W7/W8/W9/W10/W12/W13/W14 stamp `Provenance` with `created_by`; W5 (`signal_assessment`) and W6 (`evidence_reasoning`) emit contracts whose `provenance_chain` is never populated — the decision→evidence trace is incomplete at the W5/W6 links. |
| F-10 | Determinism (institutional decision) | **FAIL — Low (pre-existing, unchanged)** | `decision_engine/engine.py:147,420` still uses `uuid4()` for `InstitutionalDecision.decision_id`, violating constitution §2.1 ("all IDs content-derived"). A-033 remains open. |
| F-11 | W14 mapping semantics | **FAIL — Low** | `trade_recommendation` is declared W14, but spec W14 = Decision Journal & Post-Mortem; the recommender produces trade recommendations. No decision journal, outcome matching, attribution quadrants, or post-mortem exists anywhere. |
| F-12 | Full-suite green state | **FAIL — Medium (pre-existing, unchanged)** | 2 collection errors (`tests/test_dummy_event.py`, `tests/test_test_event_event.py`); 15 `test_fomc_calendar_connector.py` failures (documented, not re-executed); full-suite execution aborted at 30 min before completing — repo-wide green state not re-established. |

---

## 4. Remaining Certification Blockers

1. **B-1 (Critical)** — Legacy decision bypass: the run bundle's reported `decision` is the legacy decision because `finalize` lacks the `decision_engine` dependency edge; the institutional, bias-gated decision never reaches the reported outcome. (F-1; A-005 residual.)
2. **B-2 (High)** — W13 spec coverage: 5 of 10 mandated checklist mistakes unimplemented; the bias gate covers 7 checks. (F-4.)
3. **B-3 (High)** — Workflow completeness vs the 17-workflow spec: W11 absent; W1 orphaned; W2 partial; W15/W16/W17 absent. (F-3.) Requires a written scope decision (trim to 14 workflows or implement the remainder).
4. **B-4 (High)** — W9 under-consumption and W9/W12 ordering inversion vs spec. (F-2.)
5. **B-5 (Medium)** — Full-suite green state not established (2 collection errors, 15 fomc failures). (F-12.)

---

## 5. Technical Debt

Inherited, unchanged (from A1/A1.5, re-verified): dual `DecisionEngine`/`Evidence`/`EvidenceWeighter`/orchestration-engine duplicates (A-007…A-010); 15-package SCC from 2 misplaced imports (A-006); broken `_ingest_news` import (A-011); untyped dict stage boundaries (A-012); W1/W2 contract bypasses in W6/W3 (A-014/A-015); 8 unused modules + 3 production-dead packages (A-018/A-019); oversized modules/functions/dataclasses (A-021…A-023); undeclared deps `sklearn`/`transformers` (A-024); fabricated data in `_position_sizing`/`_risk_measures` (A-026); stale `CURRENT_STATE.md` (A-027); unwired GRAM (A-028); `uuid4` decision IDs (A-033).

Introduced during the certification sprint: W14 label on a non-journal workflow (F-11); provenance gaps at W5/W6 (F-9); W13 extension checks (single_source, regime_blindness) documented without spec mapping (F-4).

---

## 6. Production Readiness Assessment

**What is ready**: The institutional chain W3→W14 executes end-to-end with deterministic, tested stages; W4/W10/W13 are correctly wired, backward compatible, conformance-registered, and covered by 61 new tests; the affected-suite run is green (202 passed); the 18-benchmark acceptance gate passes; the frozen core (`src/knowledge/`) is untouched; W-ID provenance is truthful.

**What blocks production-readiness**: The reported final decision bypasses the institutional pipeline (B-1) — a live user of `InstitutionalAssessment.outputs["finalize"]["decision"]` receives a decision that never passed the W13 bias gate or the institutional risk/reward validation. W13 implements 7 of 10 mandated checks (B-2). Three workflows of the 17-workflow spec do not exist and W1/W2 are not operational workflows (B-3). W9 and W12 do not consume their documented upstreams and are ordered against the spec (B-4). The repo-wide suite has never been shown green since the sprint (B-5).

**Assessment**: The certification sprint delivered correct, well-tested increments, but the audit's mandatory check "no legacy path bypasses the institutional pipeline" fails, and the implemented workflows do not fully satisfy the documented contracts of W9/W12/W13. Under `IMPLEMENTATION_WORKFLOWS.md` and `PROJECT_CONSTITUTION_V2.md`, v1.0 certification cannot be validated.

---

## 7. Verdict

# CERTIFICATION FAILED

Per the audit brief, no fixes were implemented, no code was modified, and no commits were generated. The failed checks (Section 3) and blockers (Section 4) are left for the remediation phase. The repository was returned to its pre-audit state (test-dirtied data artifacts reverted; frozen core verified untouched).
