# Architecture Audit A1.5 — Critical Findings: Root Cause, Impact, and Remediation

**Date:** 2026-07-31
**Extends:** [Architecture-Audit-A1.md](Architecture-Audit-A1.md)
**Scope:** The five Critical findings from A1 only (A-001 … A-005).
**Method:** Source inspection only. No tests executed, no code modified. Static-analysis artifacts (`a1_analyze.py`, `a1_result.json`) live outside the repository per audit rule.
**Sources consulted:** `IMPLEMENTATION_WORKFLOWS.md`, `INSTITUTIONAL_CONTRACTS.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `CURRENT_STATE.md`, `Wave-2D-Completion.md`, `docs/Wave-1*.md`, `W1_W2_INTEGRATION_REVIEW.md`, and the source files cited per finding.

---

## 1. Verdict Summary

| ID | Finding | Root cause | Classification | Effort | Redesign required? |
|----|---------|------------|----------------|--------|--------------------|
| A-001 | W-ID collision (W10–W13 mislabeled in code) | Self-attributed W-IDs in docstrings/`created_by`; no enforcement | **Blocks v1.0 certification** (validates all completion criteria) | Trivial (mechanical) | No |
| A-002 | W4 Event Prioritization & Triage missing | Never scheduled in any wave; no stage exists | **Blocks v1.0** (W4 completion criteria unmet) | Small (new stage) | No |
| A-003 | W10 Thesis Update Cycle missing | W8 producer exists; no update machinery; `VersionedStore` never applied to theses | **Blocks v1.0** (W10 criteria; W14/W17 dependents) | Medium (new module) | No |
| A-004 | W13 Bias Prevention missing (fragment only) | Only `counter_evidence.confirmation_bias` exists; no checklist/remediation | **Blocks v1.0** (W13 criteria) | Medium (new module) | No |
| A-005 | Dual decision paths, bundle reports legacy decision | Institutional DAG runs legacy pipeline + institutional engine in parallel; `_finalize` records only legacy | **Blocks v1.0** (reporting contract inconsistent; audit risk) | Low–medium (adapter) | No |

The five findings are independent; none is a prerequisite of another, so the remediation sequence below is a safe ordering, not a dependency chain.

---

## 2. A-001 — W-ID Collision: Code Self-Attributes W10–W13 Incorrectly

**Restatement:** `scenario_generation` claims "W10", `risk_reward_validation` claims "W11", `decision_engine` claims "W12", `trade_recommendation` claims "W13". The official mapping (`IMPLEMENTATION_WORKFLOWS.md`; also lines 45 and 135 of `INSTITUTIONAL_CONTRACTS.md`) is: W10 = Thesis Update, W11 = Causal Evaluation, W12 = Fragility Audit & Scenario Analysis, W13 = Bias Prevention.

**Root cause:** The four packages were built in the institutional waves with self-descriptive wave titles ("scenario analysis" ≈ W12 by name, "risk-reward validation" ≈ W11-ish) and each package embeds its chosen label in module docstrings and in `created_by="W1x …"` provenance strings without consulting the workflow registry. No linter, doc-check, or test enforces W-ID truthfulness, so the collision survived wave completion reviews. Note that the *documents* use official W-IDs consistently (e.g., `W1_W2_INTEGRATION_REVIEW.md:291` correctly names W11 = CausalGraph consumer); only the *code* drifted.

**Code evidence:**
- `src/decision_engine/engine.py`, `contracts.py`, `__init__.py` — "W12 DecisionEngine" (also `created_by="W12 DecisionEngine"`)
- `src/risk_reward_validation/` — "W11 RiskRewardValidator"
- `src/scenario_generation/` — "W10 ScenarioGenerator"
- `src/trade_recommendation/` — "W13 TradeRecommender"

**Affected workflows/contracts:** W10, W11, W12, W13 completion claims; the producer columns in `INSTITUTIONAL_CONTRACTS.md` (a reader of Contract 5 Thesis finds `bias_flags` and `fragility_score` attributed to W13/W12 producers that do not exist under the official name); any future tooling that scans `created_by` for workflow provenance.

**Production impact:** None at runtime (strings only). Impact is on auditability: it makes the workflow-completion dashboard claim W10–W13 "implemented" when the official W10–W13 are not, and it will misdirect any W14 decision-journal or W17 auditor implementation that discovers producers by W-label.

**Migration complexity:** Trivial. Rename docstrings and `created_by` strings to the official IDs (`scenario_generation` → W12, `risk_reward_validation` → W11, `decision_engine` → W12 Fragility-adjacent — see A-005 note — `trade_recommendation` → W14-adjacent, see below).

**Classification: Blocks v1.0.** Certification cannot be validated while W-ID claims contradict the registry. Fix is a mechanical rename plus (recommended) a small test asserting the four packages' declared W-IDs against the registry map.

**No-redesign verification:** String-only edits; zero behavior change. Note for `trade_recommendation`: under the official map, W13 is Bias Prevention and W14 is Decision Journal; trade recommendation's correct official owner is W14's output consumer — decide the exact owner during the rename, but this is labeling, not architecture.

---

## 3. A-002 — W4 (Event Prioritization & Triage) Is Not Implemented

**Restatement:** W4 has no producer anywhere in `src/`.

**Root cause:** No wave ever scheduled W4. The stage DAG was assembled around W3 (watchlist) → W5 (signal classification) → W6 (evidence) → …; the institutional DAG (`src/orchestration/orchestrator.py::with_default_pipeline`) contains no triage/prioritization stage. The only "tier"/"trigger" concepts in the codebase are factor tiers (`knowledge/factors/contracts.py`) and regime indicator tiers — unrelated to event triage.

**Code evidence:**
- Default DAG stages (A1 inventory): no prioritization stage; `watchlist_builder` (W3) feeds `signal_classification` (W5) directly.
- No module under `src/` implements event-tier scoring or trigger-level scheduling.

**Affected workflows/contracts:** W4 (and its contract position: W4 is a listed consumer of Contract 1 KnowledgeRecord and the producer of the prioritized event list). W5–W9 all consume unprioritized input by inheritance.

**Production impact:** Every event in the day watchlist is processed with equal priority — no triage ordering, no trigger levels. Cost and signal-dilution grow linearly with event count; in live operation the analyst is shown an unordered event list. Currently mitigated by small event volume; not acceptable at scale.

**Migration complexity:** Small. One new stage (e.g., `event_triage`) inserted between W3 and W5, a prioritized-event contract, and a default-pipeline wiring change. Follows the existing stage + contract pattern exactly.

**Classification: Blocks v1.0** (W4 completion criteria in `IMPLEMENTATION_WORKFLOWS.md` are part of the 17-workflow gate; project is 88% / 0.9.0 "Institutional Readiness").

**No-redesign verification:** Additive stage in an existing DAG; no frozen-core module touched.

---

## 4. A-003 — W10 (Thesis Update Cycle) Is Not Implemented

**Restatement:** Theses are created (W8) but never updated. There is no thesis lifecycle.

**Root cause:** `thesis_construction` (W8) produces `InvestmentThesis`; no consumer ever mutates or re-issues it. The generic `VersionedStore` primitive (`knowledge/integrity/versioning.py`) is used only for knowledge records (via `knowledge/evolution/applicator.py`); nobody applied it to theses. Contract 5 in `INSTITUTIONAL_CONTRACTS.md` declares the update surface (`previous_thesis_id`, `trigger_levels`, `fragility_score`, `bias_flags`) but marks the contract layer "Design specification. No implementation."

**Code evidence:**
- `src/thesis_construction/builder.py:57` — sole thesis producer (`InvestmentThesis(...)`)
- `src/thesis_construction/contracts.py` — thesis fields incl. `previous_thesis_id` (always null in practice) and `counter_evidence_ids`
- `src/knowledge/integrity/versioning.py::VersionedStore` — exists, generic, unapplied to theses
- No module matches "thesis update" / W10 in `src/`

**Affected workflows/contracts:** W10 (producer), W14 Decision Journal and W17 Institutional Auditor (consumers of the thesis chain); Contract 5 Thesis lifecycle ("a new thesis version is created on every update — immutable chain").

**Production impact:** No thesis evolution; every run yields a fresh thesis with no link to prior views, so journaling, drift detection, and auditor functions cannot be built on top. Paper-trading/decision-journal records cannot answer "what changed and why."

**Migration complexity:** Medium. New module (e.g., `thesis_engine`/`thesis_update`) implementing versioning on the existing `InvestmentThesis` contract via the existing `VersionedStore`, plus a DAG stage consuming W8 output and W12/W13 outputs (`fragility_score`, `bias_flags` per Contract 5). Entirely additive.

**Classification: Blocks v1.0** (W10 completion criteria; also required by W14/W17 contract consumer lists).

**No-redesign verification:** Reuses two existing artifacts (contract, version store); no frozen module touched; no new dependency.

---

## 5. A-004 — W13 (Bias Prevention & Decision Review) Is a Fragment, Not a Workflow

**Restatement:** The only bias-prevention artifact is a single `confirmation_bias` check inside the counter-evidence analyzer. No checklist, no remediation, no audit trail; the thesis `bias_flags` field has no producer.

**Root cause:** The Wave-1E counter-evidence package (`src/counter_evidence/`) implemented one bias-detection heuristic; the institutional waves never returned to W13. The W13 completion criteria (bias checklist, remediation, flags on the thesis artifact) were never mapped to code.

**Code evidence:**
- `src/counter_evidence/analyzer.py:15` — `confirmation_bias(evidence_sets)` (single boolean heuristic)
- `src/counter_evidence/assessor.py:33-34` — appends `"confirmation_bias"` flag
- `src/thesis_construction/contracts.py` — `bias_flags` field exists but no code populates it
- No W13 module, checklist, or remediation logic anywhere in `src/`

**Affected workflows/contracts:** W13; Contract 5 Thesis (`bias_flags`), W14/W17 as downstream consumers.

**Production impact:** Decisions carry no documented bias review; the confirmation-bias check is present but unlabeled as W13 and disconnected from the thesis. Audit trail for "what biases were considered and mitigated" is absent.

**Migration complexity:** Medium. Extend `counter_evidence` (or new `bias_prevention` module) with: (1) the checklist per `IMPLEMENTATION_WORKFLOWS.md` W13 criteria, (2) a remediation decision, (3) population of `InvestmentThesis.bias_flags`. Additive; the existing analyzer/assessor is a usable seed.

**Classification: Blocks v1.0** (W13 completion criteria). If v1.0 scope is formally trimmed (see Open Questions), W13 is the strongest defer candidate — but as the gate stands today it blocks.

**No-redesign verification:** New module + one existing contract field; no frozen-core changes.

---

## 6. A-005 — Dual Decision Paths: the Run Bundle Reports the Legacy Decision

**Restatement:** The institutional DAG runs both the frozen legacy pipeline and the institutional decision engine, and `_finalize` records only the legacy decision in the run bundle — while every other institutional stage (position sizing, risk gate, trade recommendation) is driven by the institutional decision. The bundle is internally inconsistent.

**Root cause:** Wave-1F added the institutional chain as a parallel path rather than replacing the legacy one (correct under the "extend, never replace" rule and the frozen-core policy — legacy `DecisionEngine` is frozen per `CURRENT_STATE.md:10`). The orchestrator therefore keeps `build_legacy_pipeline` as a stage (it also supplies reasoning context), and `_finalize` was written when only the legacy decision existed.

**Code evidence:**
- `src/orchestration/stages.py:70-131` — `_build_legacy_pipeline` runs the full `InferencePipeline` (includes legacy DecisionEngine) inside the institutional DAG
- `src/orchestration/stages.py:627` — `_finalize` bundle decision: `results.get("build_legacy_pipeline", {}).get("decision")` (legacy STRONG_POSITIVE/… space)
- `src/orchestration/orchestrator.py:341-398` — `build_legacy_pipeline` stage and finalize job dependents
- `src/decision_engine/engine.py` — institutional decision (BUY/SELL/HOLD/NO_TRADE) consumed by `trade_recommendation`/`risk_gate`/`position_sizing`
- `tests/test_institutional_orchestrator.py:796-809` — `test_finalize_with_all_outputs` asserts only that a bundle dict is produced; nothing asserts the bundle's decision field equals the institutional decision

**Affected workflows/contracts:** W9 (confidence) and W14 (journal), W17 (auditor), and any downstream consumer of the run bundle (paper trading, replay stats). Contract ambiguity: the bundle's `decision` field is documented by position (it sits in the institutional run), but its value is legacy.

**Production impact:** High for auditability: a single run reports a legacy "STRONG_POSITIVE" decision while its own trade recommendation was built from an institutional "BUY/…" decision. Replay-based backtests that score bundle decisions will score the wrong signal. No runtime crash — silent semantic mismatch.

**Migration complexity:** Low–medium. Two compliant options (both additive, neither modifies frozen code):
1. **Preferred:** adapter in the bundle layer — record both decisions with provenance (`decision` = institutional, `legacy_decision` = legacy, both tagged by source pipeline), mirroring the existing provenance pattern.
2. Or deprecate the legacy stage's decision output and translate legacy → institutional space in `_finalize`.

**Classification: Blocks v1.0** (reporting contract must be unambiguous before certification; W14/W17 depend on truthful bundles).

**No-redesign verification:** Adapter-layer change at the stage boundary; the frozen `InferencePipeline`/legacy `DecisionEngine` are not modified — compliant with the "extend, never replace" rule.

---

## 7. Remediation Sequence (Ordered)

1. **A-001** W-ID rectification — mechanical rename + one registry-conformance test. Do first: it unblocks trustworthy validation of every other item (1–2 h).
2. **A-005** Bundle decision adapter — record institutional + legacy decisions with provenance in `_finalize`; extend `test_finalize_with_all_outputs` to assert the institutional decision is the bundle's canonical `decision` (0.5–1 d incl. tests).
3. **A-002** W4 triage stage — new prioritized-event contract + stage between W3 and W5 in the default DAG (1–2 d).
4. **A-003** W10 thesis update module — `VersionedStore`-backed thesis versions on the existing `InvestmentThesis` contract; stage consuming W8/W12/W13 outputs (1–3 d).
5. **A-004** W13 bias-prevention module — checklist + remediation + `bias_flags` producer, seeded by `counter_evidence` (1–2 d).

Sequence rationale: label truth → report truth → new pipeline stages in dependency order (triage before thesis update; bias prevention feeds the thesis flags).

---

## 8. No-Redesign Verification (per Finding)

- A-001: string-only edits. A-002/A-003/A-004: new stages/modules added to an existing DAG and existing contracts. A-005: adapter at the stage boundary. None touches the frozen v1.0 core (`InferencePipeline`, `ReasoningEngine`, legacy `DecisionEngine`, `Evidence`, `EventRegistry`); all comply with "extend, never replace" (`CURRENT_STATE.md:224`). The existing stage-DAG + contract pattern is sufficient for every remediation — no architectural redesign is required. The risk is scope/effort, not design.

---

## 9. Open Questions and Residual Notes (for A2)

1. **Wave-2D "activation" targeted the dead engine.** `Wave-2D-Completion.md` wires Cross-Asset Intelligence into `knowledge/orchestration` — the engine A1 found production-dead (test-only), while the production path is the top-level `orchestration` DAG. Waves are extending a test-only engine; recommend A2 scope item (extend/port to the stage DAG or formally retire `knowledge/orchestration`).
2. **3 pre-existing test failures** cited in `Wave-2D-Completion.md` (`test_institutional_validation` temporal scenario NEUTRAL vs POSITIVE; `test_release_calendar` ×2 missing `data_dir`) — confirm resolution before v1.0 certification.
3. **Test-count drift:** 786 (post-stabilization) → 1638 (Wave-2C era) → 1990 (Wave-2D) per docs. Re-baseline the suite in A2.
4. **v1.0 scope trim question:** if the v1.0 gate is formally scoped to a subset of the 17 workflows (or W4/W10/W13 are pushed to v1.1 by a roadmap amendment), re-classify A-002/A-003/A-004 as "defer v1.1" with a written scope decision. Today, un-amended, they block.
5. **A1 High findings** (cycle edges via `knowledge/evolution/applicator.py` and `simulation/historical_replay.py`; duplicate `Evidence`/`EvidenceWeighter`; `_ingest_news` broken import; 8 unused modules; undeclared `sklearn`/`transformers` deps; `uuid4` in decision_engine) remain open and are candidates for the A2 or A1.6 deep-dive; none blocks v1.0 except `_ingest_news` (news stage silently no-ops) — recommend a quick A1.6 follow-up for that single finding.
