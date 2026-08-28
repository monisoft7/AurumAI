# AurumAI — Funding Readiness Audit 001

Date: 2026-08-09
Branch: `funding-preparation` (commit `d392375`, working tree with intentional runtime artifacts)
Baseline: `main` at `e909caf`
Auditor: funding-preparation audit pass (documentation-only; no core source code changed)

Purpose: establish, for external technical/funding review, what is actually
implemented, what is validated, what is infrastructure only, what remains
experimental, what is incomplete, and which documentation claims are stale.
The audit is deliberately honest: implemented infrastructure is not predictive
value, and active validation findings are disclosed rather than hidden.

---

## 1. Normalization: terms used in this audit

- **IMPLEMENTED + WIRED** — code exists, is reachable from `run.py`/the runtime DAG, and was exercised by a recorded runtime.
- **IMPLEMENTED, NOT WIRED** — code exists and is tested, but no runtime stage imports it.
- **INFRASTRUCTURE ONLY** — code/repository support exists; no evidence it drives any current decision.
- **VALIDATED** — a dated reproducible artifact demonstrates the claim.
- **EXPERIMENTAL** — a recorded experiment or simulation result; scope-limited by construction.
- **UNVALIDATED** — no current artifact demonstrates the claim.
- **KNOWN FAILURE** — a dated validation artifact records a demonstrated defect.

---

## 2. Capability classification (verified 2026-08-09)

| Area | Status | Verification |
|---|---|---|
| KnowledgeRecord entity (frozen core) | IMPLEMENTED + WIRED | `src/knowledge/integrity/knowledge_record.py`; 6 real records in `data/economic/output/knowledge.json`; deterministic content-derived IDs |
| Lesson → Knowledge pipeline (legacy chain) | IMPLEMENTED + WIRED | `InferencePipeline._stage_build_lessons/_stage_build_knowledge`, `src/knowledge/pipeline/pipeline.py:56-186`; survives every runtime |
| Knowledge graph (NetworkX) | IMPLEMENTED + WIRED (in-memory) | `src/knowledge/graph/*`; built each run, consumed by W6 evidence collection (`src/orchestration/stages.py:506,518`); JSON persistence unused at runtime |
| Knowledge ingestion (KR parser / KB pipeline) | IMPLEMENTED, NOT WIRED | `src/knowledge/ingestion/*` (465 LOC); zero importers outside package; zero tests; `Institutional_Gold_Knowledge_Base.md` (6 categories / 83+ KRs) is not ingested by any runtime path |
| Evidence query/ranking (frozen core) | IMPLEMENTED + WIRED (legacy chain) | `src/knowledge/evidence/*`; links real KnowledgeRecord IDs (`knowledge_id` reused as `evidence_id`) |
| Institutional evidence collection (W6) | IMPLEMENTED + WIRED, KNOWN FAILURE | `src/evidence_collection/collector.py:132-134`; synthetic `kr_synthetic_*` fallback when corpus does not cover observation class; reproduced independently (see §3) |
| Evidence reasoning (W6) | IMPLEMENTED + WIRED | `src/evidence_reasoning/*`; consumes W6 evidence |
| CounterEvidence (W7) | IMPLEMENTED + WIRED | `src/counter_evidence/*`; RUN_002 PASS, single penalty application verified |
| Thesis construction/update (W8/W10) | IMPLEMENTED + WIRED | `src/thesis_construction/*`, `src/thesis_update/*` |
| Confidence engine (W9) | IMPLEMENTED + WIRED, KNOWN FAILURE (downstream) | `src/confidence_engine/*`; RUN_002 FAIL because synthetic evidence sources materially enter `evidence_quality`, `source_diversity`, `knowledge_record_quality` |
| Scenario generation / risk-reward (W12) | IMPLEMENTED + WIRED | `src/scenario_generation/*`, `src/risk_reward_validation/*`; RUN_002 PASS |
| Decision engine + bias review (W13) | IMPLEMENTED + WIRED | `src/decision_engine/*`, `src/bias_prevention/*`; RUN_002 decision authority PASS; final decision `NO_TRADE` reproducible from frozen gates |
| Reasoning/decision (frozen core) | IMPLEMENTED + WIRED (legacy chain) | `src/knowledge/reasoning/*`, `src/knowledge/decision/*` |
| Forecasting + risk + position sizing + gate | IMPLEMENTED + WIRED | `src/forecasting/*` (statsforecast AutoARIMA/AutoETS/AutoTheta); DAG jobs `forecast`, `forecast_confidence`, `forecast_validation`, `risk_measures`, `position_sizing`, `risk_gate` |
| Regime diagnosis/economic intelligence | IMPLEMENTED + WIRED | `src/orchestration/stages.py:538-594`; `regime_diagnosis.json` each run; indicator metadata (data_source, associated_kr_ids) largely empty — hierarchy is config-level, not evidence-linked |
| Learning / calibration / feedback | IMPLEMENTED, NOT WIRED | `src/knowledge/learning/*`, `src/knowledge/evolution/*`; test-only (30/10/12 tests); no production path |
| Expansion framework | IMPLEMENTED, NOT WIRED | `src/knowledge/expansion/*`; lifecycle explicitly "does NOT execute the steps" |
| OrchestrationEngine (knowledge/orchestration) | IMPLEMENTED, NOT WIRED | 385 LOC adapter; zero runtime importers; institutional DAG uses `src/orchestration/*` instead |
| Causal/temporal intelligence | IMPLEMENTED, NOT WIRED | `src/knowledge/causal/*`, `src/knowledge/temporal/*`; consumed only by the unwired OrchestrationEngine (W11 has no workflow; see Architecture-Audit-A2.md F-3) |
| LineageRegistry / Provenance | IMPLEMENTED + WIRED (in-memory only) | wired into legacy chain; never persisted to disk by any runtime stage |
| VersionedStore | INFRASTRUCTURE ONLY | `src/knowledge/integrity/versioning.py`; only used by FeedbackApplicator (test-only) |
| Chronological OOS engine | IMPLEMENTED, NOT WIRED into daily runtime | `src/simulation/historical_replay.py` (strict chronological split, `prebuilt_lessons_path`, point-in-time gold in forecast stages); 94+17+35 tests; executed only via experiment scripts |
| Experiment framework + registry | IMPLEMENTED, EXPERIMENTAL | `src/simulation/experiment*.py`; deterministic SHA-256 IDs; registry contains 1 canonical record (EXP-001, PENDING) |
| Experiments EXP-001/002/003, RI-001 | EXPERIMENTAL, recorded | see §4 |
| Benchmark gate (18 tests) | IMPLEMENTED; "18/18 passing" assertion not backed by a stored run artifact | `tests/test_benchmark.py`; docs claim 18/18 (CURRENT_STATE, Architecture-Audit-A2, Wave-2-Closure, PROJECT_BLUEPRINT) |
| Paper trading (portfolio/slippage/commission/execution) | IMPLEMENTED + WIRED at infrastructure level | `src/simulation/*` (+63/66/38 tests); not exercised by any recorded live runtime decision |
| Trade recommendation (W14 label) | IMPLEMENTED + WIRED | `src/trade_recommendation/*`; note: spec W14 = decision journal, which does not exist (Architecture-Audit-A2.md F-11) |
| Daily runtime orchestration | IMPLEMENTED + WIRED | 26-job DAG; RUN_002: 26/26 stages OK, 140.1 s, isolated artifacts, registry entry complete |
| Outcome evaluation / continuous monitor | IMPLEMENTED, NOT WIRED | `scripts/evaluate_outcome.py`, `scripts/continuous_monitor.py`; `outcome.json` stays `pending`; `scripts/run_daily.py` never evaluates it |

---

## 3. Known failure — Knowledge → Evidence (RUN_002), exact causal boundary

Recorded artifact: `docs/audit/OPERATIONAL_VALIDATION_RUN_002.md` (runtime `runtime_20260809_091544`, git `90f0b53`).
Status: Failure is proven, causal, decision-material; no correction implemented (validation protocol respected).

**Causal path (verified in source, reproduced independently 2026-08-09):**

1. `src/evidence_collection/collector.py:127` maps each observation's instrument to an event class (`INSTRUMENT_TO_EVENT_TYPE`; e.g. `XAU/USD → GENERAL`, `DXY → USD_FX`, `Gold Positioning → ETF_FLOW`, `US10Y → REAL_YIELD`, `Breakeven Inflation → INFLATION`).
2. `_query_knowledge_records` (`collector.py:179-199`) searches the knowledge graph for that event class, then its evidence-class equivalents (`EVENT_TYPE_TO_EVIDENCE_CLASS`), then `GENERAL`.
3. The production corpus contains only six CPI KnowledgeRecords (event_type `CPI`), so classes `GENERAL/USD_FX/REAL_YIELD/ETF_FLOW` match nothing.
4. `collector.py:133` applies the explicit synthetic fallback: `source_kr_id = f"kr_synthetic_{obs.observation_id}"`.
5. RUN_002's four decision-relevant evidence items (XAU/USD, DXY, Gold Positioning, anomaly — all in uncovered classes) received synthetic `source_kr_id` values, which then flow into `evidence_quality` (0.5583), `source_diversity`, `knowledge_record_quality`, final institutional confidence (0.2584), and the final decision (`NO_TRADE`, first decision driver).

**Nuances established by reproduction:**
- `INFLATION`-class observations (Breakeven Inflation) DO link to the real CPI KnowledgeRecords via `EVENT_TYPE_TO_EVIDENCE_CLASS` (`CPI → INFLATION`); in RUN_002 that observation was classified noise and never became evidence.
- Positive control: when a graph node exists for the observation class, the collector links real KnowledgeRecord IDs (verified).
- The frozen core `knowledge/evidence` path is not implicated; it links real KnowledgeRecord IDs whenever queried and is exercised green by EXP-002/EXP-003.

**Boundary conclusion:** the failure is a corpus-coverage + fallback-semantics boundary of the institutional (W6) evidence path — daily market observations reference knowledge classes the current CPI-only corpus does not contain, and the collector silently treats the synthetic fallback as knowledge-backed evidence instead of flagging it. It is not a failure of the frozen core contracts and does not imply architectural redesign.

**Smallest-fix candidates (NOT implemented; decision pending per protocol):**
- (a) Collector semantics: mark synthetic fallback evidence explicitly (e.g. `source_label/type = synthetic`, excluded or down-weighted from `knowledge_record_quality`) so no synthetic source is presented as knowledge-backed; or
- (b) Corpus coverage: ingest real KnowledgeRecords for the observed classes (`GENERAL/USD_FX/REAL_YIELD/ETF_FLOW`) — the unwired `src/knowledge/ingestion/*` pipeline is the existing infrastructure for this but is untested and unowned.

Either option requires the full verify → reproduce → root-cause → smallest-fix → regression → re-validate sequence before implementation. No fix is implemented in this documentation-only pass.

---

## 4. Recorded experiments — what they do and do not prove

| Experiment | Recorded verdict | Reading for external reviewers |
|---|---|---|
| EXP-001 (CPI vs CPI+US10Y, cutoff 2024-01-01) | REJECT US10Y; all deltas 0.0; 0 decisions changed | Canonical registry entry `exp_c3b433e5606b0d15`: baseline & candidate both 75% directional accuracy (24 scored events, 30 evaluation events, ECE 6.65%). Evidence about the tested configuration only. Registry status: PENDING. NOTE: on-disk `report.txt` is a degraded rerun (missing `data/history/economic/*.csv`); the registry entry is canonical. |
| EXP-002 (Evidence Isolation) | Hypothesis falsified — per-condition and merged decisions match (2/2); no regression | Merged aggregation does not lose directional signal for the CPI corpus in this configuration. |
| EXP-003 (Condition Filtering) | Evidence set changes with filtering; decision unchanged | Condition filtering is working as designed at the legacy chain level. |
| RI-001 (Weighted vs Unweighted) | Identical metrics both arms (86.11%, 36 scored, 31 correct); 0 decisions changed | Not in the experiment registry (housekeeping gap). |

These are recorded experiments, not proofs of predictive superiority. Sample sizes are small (24–36 scored events); all are flagged accordingly.

---

## 5. Documentation corrections applied in this pass (smallest safe, dated)

| File | Correction |
|---|---|
| `institutional_validation_report.md` | Added dated scope+status qualifier: component-scenario assessment on in-memory scenarios; "Fully Institutional Ready" is not a production/release-readiness claim; superseded in external communication by `docs/external/VALIDATION_STATUS.md`; conflicts with RUN_002 FAIL dated one day later. Note: the file is a generated artifact (`.gitignore:57`, produced by `tests/test_institutional_validation.py`) — the qualifier is a documentation edit and the generator itself should carry the same wording in future regenerations. |
| `CURRENT_STATE.md` | Institutional validation snapshot 8/2 → latest dated 9/1 (2026-08-08 report) with qualifier; metrics table: tests 1638 → dated snapshot + current 2759 collected/0 errors; benchmark 18/18 → asserted, no stored run artifact found; deps "6 (removed 3)" → pyproject declares 10 (removal intent not executed); version 0.9.0 → pyproject declares 0.0.1 (lag documented); reproducibility assessment scoped to frozen legacy core (W-stage uuid4/clock IDs excluded, A2 F-10); Experiment 002 "pending" → EXP-001/002/003/RI-001 recorded with verdicts and registry caveats; test-suite instruction updated (legacy scaffold files deleted, `--ignore` flags obsolete). |
| `MEMORY.md` | Test status section updated to dated snapshot 2759 collected / 0 errors; obsolete exclusion command removed; reproducibility claim scoped to legacy core. |
| `ROADMAP.md` | Phase 20.5: "removed 3 unused deps" → "identified 3 unused deps" with 2026-08-09 reconciliation note that all 10 remain declared in `pyproject.toml`. |
| `docs/external/VALIDATION_STATUS.md` | Completed the previously empty "Required next sequence" section with the established causal boundary (§3) and pointer to this audit. |
| `docs/audit/FUNDING_READINESS_AUDIT_001.md` | This file. |

Intentionally not modified (historical snapshots preserved per `docs/audit/DOCUMENTATION_RECONCILIATION.md`): `PROJECT_STATUS.md` (1639 snapshot), `docs/audit/Certification-Summary.md` (202 passing / 14 workflows / 2 collection errors + fomc failures — both collection errors and fomc failures are now resolved in the current suite, recorded here as a current-state note), `docs/audit/Architecture-Audit-A2.md` (dated audit).

Current test-suite state (2026-08-09): 2759 tests collected, 0 collection errors (verified `py -3 -m pytest tests --collect-only`); W6 evidence collection/reasoning + workflow conformance: 73 passed. Historical counts (786–1990) are dated milestone snapshots.

---

## 6. Funding readiness assessment

### Strong existing evidence
- Functioning 26-stage daily runtime with isolated artifacts, run registry, and a repeatable operational-validation protocol that demonstrably catches decision-material issues (RUN_002 is evidence the process works).
- Deterministic frozen core: KnowledgeRecord → graph → evidence → reasoning → decision, all content-derived IDs, immutable records, lineage hooks active in the legacy chain.
- Real validated components: OI second-observation propagation, SignalAssessment, CounterEvidence single-penalty path, RiskReward inputs, DecisionEngine gate reproducibility (RUN_002 PASSes).
- Genuine OOS infrastructure with strict chronological splits, no-leakage lesson injection, and an experiment registry (`EXP-001 confirmed no US10Y improvement`).
- 2759-test suite with deterministic fixtures (no network), 0 collection errors.
- Honest external package already present (`docs/external/*`) with correct disclosure discipline.

### Weak / unvalidated areas (do not overclaim)
- No demonstrated predictive value: only 1 registered experiment, PENDING, 24 scored events, 75% accuracy vs implied coin-flip baseline for one configuration.
- Knowledge → Evidence lineage FAIL (RUN_002) unresolved — the headline blocker.
- Knowledge cloud: corpus = 6 CPI records only; KB ingestion unwired; `Institutional_Gold_Knowledge_Base.md` not consumed; non-CPI classes uncovered (root cause of the FAIL).
- Learning/calibration loop unwired — no evidence the system improves from outcomes.
- Outcome evaluation unwired — `outcome.json` stays `pending`; no recorded evaluation of decisions against realizations.
- "18/18 benchmark" assertion has no stored run artifact.
- Institutional W-stage determinism not assessed (uuid4/clock-time IDs in several stage objects; A2 F-10).
- Experiment housekeeping: EXP-001 on-disk report degraded vs canonical registry; RI-001 unregistered; approval statuses PENDING.

### Remaining blockers
1. Resolve the Knowledge → Evidence lineage failure at its established boundary (§3) with the smallest correct fix, then re-run operational validation.
2. Decide W11/17-workflow scope (trim to 14 or implement remainder; A2 F-3) — a written scope decision for the spec gap.
3. Wire outcome evaluation + a first learning/calibration loop for at least one recorded experiment.
4. Reconcile full-suite claim with a dated run artifact (command, environment, commit) — the accepted pattern for every numeric claim.
5. Data corpus: reproducible snapshots for CPI/NFP/PPI/PMI/GDP/FOMC/DXY/US10Y + news archive with provenance (required for real OOS breadth).

---

## 7. Recommended funding narrative (truthful, funding-focused)

> AurumAI is an institutional market-intelligence operating system that converts macroeconomic history into deterministic, explainable, evidence-linked assessments. It already operates a research-grade daily intelligence pipeline (knowledge records, knowledge graph, evidence, reasoning, decision gating, forecasting, risk, paper-execution scaffolding) with an operational-validation protocol that has demonstrably caught a decision-material evidence-integrity issue before any live use. What it needs external API/compute/data resources for is not more models — it is (1) resolving and re-validating the established evidence-lineage boundary, (2) breadth and reproducibility of the economic data corpus (only CPI is currently covered), (3) controlled model/NLP experimentation with reproducible harnesses, (4) wired outcome evaluation and learning/calibration so recorded experiments become real evidence, and (5) machine-readable validation artifacts for institutional review. Progress is measured by dated, reproducible validation results, not by claims.

Do NOT claim: profitability, alpha, Sharpe, live readiness, superiority vs benchmarks, or institutional release readiness.

## 8. Recommended resource requirements

### API/model
- Access to frontier APIs under a reproducible experimentation harness (hypothesis generation, document/NLP analysis of news and FOMC minutes, code review) — explicitly bounded so models never become opaque decision authorities (per `docs/external/AI_INFRASTRUCTURE_PLAN.md` Priority 3).

### Compute
- Batch computing for: chronological OOS expansion across event types (CPI/NFP/PPI/PMI/GDP/FOMC), forecast walk-forward evaluation, parameter-space experiments, and full-suite clean-clone regression runs (currently ~2,759 tests; daily runtime 140 s single-machine).

### Data
- Licensed/high-quality archives: US economic releases (full history, revision-tracked), gold (LBMA/CME OI + positioning), DXY, US10Y real/nominal + breakeven (already partially built), event calendars with revision dates, news/FOMC transcripts with timestamps — all versioned with provenance for replayable snapshots.

### Operations (later tranche)
- CI with artifact retention, secured environment, observability, access control, audit logging.

---

## 9. Files changed in this audit pass (documentation only)

- `institutional_validation_report.md` (qualifier)
- `CURRENT_STATE.md` (6 surgical corrections)
- `MEMORY.md` (2 surgical corrections)
- `ROADMAP.md` (phase 20.5 reconciliation note)
- `docs/external/VALIDATION_STATUS.md` (causal boundary status)
- `docs/audit/FUNDING_READINESS_AUDIT_001.md` (this audit, new)

## 10. Files intentionally untouched

- All `src/` code (frozen core and institutional packages) — no core code changes in this pass.
- All 5 runtime-generated artifacts (`data/economic/gold_oi_state.json`, `data/economic/output/{knowledge.json,lessons.csv,regime_diagnosis.json}`, `data/experiments/EXP-002-Evidence-Isolation/results.json`) — treated as runtime/validation artifacts, not committed or overwritten.
- Historical audit docs (`Architecture-Audit-A1/A1.5/A2`, `Certification-Summary`, sprints, waves) — preserved per DOCUMENTATION_RECONCILIATION.
- `PROJECT_NORTH_STAR.md`, `PROJECT_CONSTITUTION.md`, `PROJECT_STATUS.md` — no correction required or intentionally preserved as history.

## 11. Checks executed (2026-08-09)

| Check | Command | Result |
|---|---|---|
| Suite collection | `py -3 -m pytest tests --collect-only -q` | 2759 collected, 0 errors |
| Targeted W6 suite | `py -3 -m pytest tests/test_evidence_collection.py tests/test_evidence_reasoning.py tests/test_workflow_id_conformance.py -q` | 73 passed |
| Causal boundary reproduction | Independent repro against `KnowledgeGraph` + `EvidenceCollector` (temp script) | Synthetic `kr_synthetic_*` fallback reproduced for GENERAL/USD_FX/REAL_YIELD/ETF_FLOW; real-KR link reproduced for INFLATION class and for a graph containing a GENERAL node |

## 12. Next engineering sequence (recommended, outside this pass)

1. Decide and implement the smallest correct fix for the knowledge-corpus/evidence-fallback boundary (§3 candidates a/b) under the verify→reproduce→root-cause→fix→regression→re-validate protocol.
2. Re-run Operational Validation 003; update `docs/external/VALIDATION_STATUS.md` with the dated result.
3. Create the dated institutional validation package per `docs/external/IMPLEMENTATION_PLAN.md` section E.
4. Register RI-001 and complete EXP-001 approval notes in the experiment registry.