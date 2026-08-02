# PROJECT SCOPE v1.x

**Status**: Ratified (freeze)
**Date**: 2026-08-01
**Authority**: Subordinate to `docs/PROJECT_CONSTITUTION_V2.md` (supreme). Where conflict exists, the constitution prevails.
**Consistent with**: `docs/audit/Certification-Summary.md`, `docs/audit/Scope-Verification-Report.md`, `docs/audit/Architecture-Audit-A2.md`, and `IMPLEMENTATION_WORKFLOWS.md` (Workflow Index only).
**Effect**: Defines the permanent scope of AurumAI v1.x. No workflow, package, contract, or boundary named here may change without the amendment process in Section 6.

---

## 1. Official Project Objective

AurumAI v1.x is an **Institutional Financial Intelligence System** that produces deterministic, explainable, and evidence-based investment assessments from historical macroeconomic data.

- AurumAI is **not** a trading bot. Trading execution is a downstream consumer of AurumAI intelligence; the execution layer is not part of the v1.x product.
- The product is **Institutional Intelligence** (assessments, theses, decisions, and audit trails), optimized for institutional trust — correctness, determinism, explainability, reproducibility, and measurable predictive value — not for feature count.

## 2. Official Project Boundaries

1. **Pipeline boundary**: The institutional pipeline is the certified 25-job DAG (`pre_market_scan` root through `trade_recommendation`), comprising the 14 certified workflow packages. The legacy chain (InferencePipeline branch, forecasting branch) remains registered in the DAG as declared capability but is not part of the certified institutional product surface.
2. **Frozen core**: `src/knowledge/` (InferencePipeline, ReasoningEngine, frozen DecisionEngine, Evidence, EvidenceWeighter, WeightConfig, ReasoningChain, ReasoningStep, KnowledgeRecord, MacroEvent ABC, EventRegistry, Knowledge Expansion Framework, Benchmark Framework, Core Entity Contracts, Institutional Assessment models, Provenance, and the frozen data structures of constitution Section 12.2) is permanently frozen. No modification without a verified defect and Architecture Council approval per constitution Section 14.5.
3. **Layer rules**: Data flow is one-directional (Event → Evidence → Aggregate → Reasoning → Decision → Record). No layer skipping. No circular dependencies. No black-box decisions; every output carries a documented confidence method and traceable provenance.
4. **Determinism**: All IDs content-derived; no hidden randomness or state; deterministic reproduction of every number the system surfaces. (Known exception pending closure: `decision_engine` decision IDs — recorded in Architecture-Audit-A2, F-10.)
5. **Evidence rules**: Evidence weighting is the frozen 5-factor model (constitution Section 7.2). Insufficient evidence produces explicit `INSUFFICIENT_EVIDENCE`, never a guess.
6. **Risk rules**: No real trading and no execution wiring before backtesting and paper trading gates pass (constitution Section 2.7, Rule 2). Risk controls are stricter than the layer's confidence in itself.
7. **Certification boundary**: v1.x certification covers the in-scope workflows of Section 3. Workflows outside this scope are not part of v1.x certification, regardless of any code that exists for them.
8. **Documentation boundary**: `IMPLEMENTATION_WORKFLOWS.md` is authoritative **only for the Workflow Index (W-IDs)**. Its P0/P4 implementation-sequence and the spec bodies of out-of-scope workflows are not binding on v1.x.

## 3. In-Scope Workflows

The following 11 W-IDs / 14 packages constitute the certified v1.x workflow scope. W-ID mapping is fixed per `IMPLEMENTATION_WORKFLOWS.md` Workflow Index and enforced by the conformance registry.

| W-ID | Workflow | Package(s) |
| --- | --- | --- |
| W3 | Pre-Market Intelligence Scan | `pre_market` |
| W4 | Macro Event Prioritization & Triage | `event_triage` |
| W5 | Signal vs Noise Classification | `signal_assessment` |
| W6 | Evidence Collection & Regime-Aware Weighting | `evidence_collection`, `evidence_reasoning` |
| W7 | Conflicting Evidence Resolution | `counter_evidence` |
| W8 | Investment Thesis Formation | `thesis_construction` |
| W9 | Confidence Assignment & OOS Calibration | `confidence_engine` |
| W10 | Thesis Update Cycle | `thesis_update` |
| W12 | Fragility Audit & Scenario Analysis | `scenario_generation`, `risk_reward_validation` |
| W13 | Bias Prevention & Decision Review | `bias_prevention`, `decision_engine` |
| W14 | Final output workflow (certified meaning: trade recommendation) | `trade_recommendation` |

The official W14 label in `IMPLEMENTATION_WORKFLOWS.md` is "Decision Journal & Post-Mortem"; the certified v1.x meaning of W14 is the final output workflow `trade_recommendation`. The label mapping is fixed as recorded in the conformance registry and `Certification-Summary.md`.

## 4. Out-of-Scope Workflows

The following W-IDs are **permanently out of v1.x scope**. No code under these workflows may be claimed as v1.x certified capability, and no implementation is required for v1.x:

| W-ID | Workflow | Status |
| --- | --- | --- |
| W1 | Knowledge Record Ingestion & Encoding (batch ingestion of 207+ KB records) | Superseded by the constitution's department/knowledge-object framework; any existing implementation is not part of v1.x |
| W2 | Macro Regime Diagnosis & Indicator Selection (6-regime + GRAM + indicator hierarchy spec) | Not a v1.x workflow; existing partial core capability is not certified as W2 |
| W11 | Causal Relationship Evaluation & Graph Maintenance | Not implemented; out of v1.x scope |
| W15 | Cross-Asset Confirmation Matrix | Not implemented; out of v1.x scope |
| W16 | Multi-Window Evidence Aggregation (GRAM) | Not implemented; out of v1.x scope |
| W17 | Institutional Auditor Interface | Not implemented; out of v1.x scope |
| W14 (spec body) | Decision Journal & Post-Mortem | Not part of v1.x; the W14 label is reserved for the certified meaning in Section 3 |

## 5. Deferred Capabilities

Deferred capabilities are recorded, not removed. They remain eligible for a future v2.x amendment; none is required for v1.x completion:

1. W11 causal relationship evaluation and graph maintenance.
2. W15 cross-asset confirmation matrix.
3. W16 multi-window evidence aggregation.
4. W17 institutional auditor interface.
5. W14 decision journal, outcome matching, attribution quadrants, and post-mortem generation (as specified in `IMPLEMENTATION_WORKFLOWS.md`).
6. W13 checklist completeness beyond the certified 7 checks (base-rate neglect, attribution error, groupthink, false precision, and "this time is different" remain unimplemented).
7. W9 full documented input consumption (regime clarity, W6 evidence, W12 downside case, multi-window consistency, OOS ECE) and W12 fragility-score/base-rate inputs.
8. OOS validation gate (Gate 6) and paper-trading validation.
9. GRAM residual analysis wiring.
10. Execution-layer wiring (paper trading) into the runtime.

Items 6 and 7 are recognized conditions of the v1.x certification audit (blockers B-2 and B-4 in `Architecture-Audit-A2.md`); their status may be resolved by completing them within v1.x or by an explicit amendment, but certification remains open until closure or amendment.

## 6. Version Policy

1. **v1.x scope is frozen** as of this document's ratification date. The in-scope list (Section 3), the W-ID mapping, the package ownership, and the out-of-scope list (Section 4) are permanent for v1.x.
2. **Amendments** require: a written proposal (exact change, rationale, impact on certification), review against the constitution, and approval by the Chief Architect (Architecture Council for anything touching frozen core, contracts, or benchmarks). Every amendment is appended to the Amendment Log below with date and summary.
3. **W-IDs are permanent.** No W-ID in `IMPLEMENTATION_WORKFLOWS.md` may be re-labeled, re-assigned, or removed. Changes are made only by adding to the index, never by reusing or repurposing an existing W-ID.
4. **Contracts**: institutional contracts are versioned; breaking changes require the constitution's contract-change procedure (Section 5.4). Certified contract semantics may not silently change.
5. **Benchmarks**: the 18-benchmark gate is permanent; thresholds may only be raised.
6. **Backward compatibility**: stage boundaries must degrade gracefully; new stages must not alter behavior when their inputs are absent.
7. **Minor releases** (v1.x) may only add capabilities inside the in-scope set; anything outside Section 3 requires a v2.x amendment.

## 7. Definition of Done for v1.x

v1.x is complete only when **all** of the following hold:

1. All in-scope workflows (Section 3) are implemented, conformance-registered, and reachable from the DAG root.
2. The DAG is acyclic; every stage consumes only declared dependencies; the final run bundle's `decision` is the institutional, bias-gated decision (A2 finding F-1 closed).
3. The full test suite passes from a clean clone: zero collection errors, zero failures (reported baseline: 2554 collected tests; 2 collection errors pending closure).
4. The 18-benchmark acceptance gate passes with zero regressions.
5. The conformance registry tests pass (W-ID truthfulness incl. `created_by`).
6. Audit A2 blockers B-2 (W13 checklist) and B-4 (W9/W12 spec alignment) are closed by completion or by ratified amendment; blocker B-3 is closed by this scope freeze; blocker B-5 (suite green) is closed per item 3.
7. No in-scope contract has more than one producer; no workflow consumes an undeclared upstream.
8. Frozen core (`src/knowledge/`) is untouched by any v1.x change, and the constitution's inviolable rules (Section 12) hold.
9. Provenance chain is populated for every in-scope workflow output (W5/W6 provenance gap closed).
10. Certification is re-validated by an audit pass over this list; the result is recorded in `docs/audit/`.

---

## Amendment Log

- 2026-08-01: v1.x scope ratified. Frozen 11 W-IDs / 14 packages as certified scope; declared W1, W2, W11, W15, W16, W17 and the W14 journal spec out of scope; recorded deferred capabilities; defined version policy and Definition of Done.
