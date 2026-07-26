# CER-007A: Design Review Addendum
**Status:** Review Finding  
**Authority:** Independent Architecture Review  
**Reviewer:** Chief Software Architect (design review)  
**Date:** 2026-07-25  
**Subject:** CER-007 Capability Activation Matrix — Accuracy & Feasibility Audit

---

## Purpose

This addendum identifies assumptions, contradictions, and unverified claims in CER-007 that could lead to incorrect prioritization or architecture violations if acted upon without correction. CER-007 itself is not modified.

---

## Finding 1: Frozen Core Contradiction

**Severity:** Critical — invalidates effort estimates for Ranks 3–6

CER-007 declares the following as Frozen Core (§ Active inventory, line 1):

> InferencePipeline, ReasoningEngine, DecisionEngine, EvidenceEngine

CER-007 then assigns these same components as "Production Owner" for capabilities requiring *internal modification*:

| Rank | Capability | Assigned Owner | Required Change |
|------|-----------|---------------|-----------------|
| 3 | C-09 Evidence.explanation | ReasoningEngine | Modify `_build_evidence_review()` to read `ev.explanation` |
| 4 | C-08 CrossEventResult consensus | DecisionEngine | Modify `decide()` signature or input to accept consensus fields |
| 5 | C-01 EvidenceRanker | ReasoningEngine | Insert ranking call before or within reasoning stage |
| 6 | C-02 HistoricalSituationRetriever | ReasoningEngine | Add retrieval step inside reasoning flow |

**Consequence:** These are not "Low effort / single call-site change" as rated. Each requires either:

1. A governance exception to modify frozen core (per `PROJECT_NORTH_STAR.md §4`: *"may only be modified when a verified engineering defect cannot be corrected elsewhere"*), or
2. An interceptor pattern outside frozen core (pre/post hooks in InferencePipeline stages) which would require modifying InferencePipeline — also frozen.

**Recommendation:** CER-007 must clarify the activation path for each. If frozen core cannot be touched, ranks 3–6 require an adapter/wrapper layer that does not exist today, elevating their effort from Low to Medium.

---

## Finding 2: Factually Incorrect Claim (C-02)

**Severity:** High — misdirects implementation

CER-007 states for C-02 (HistoricalSituationRetriever):

> "Instantiate HistoricalSituationRetriever at the existing call site in ReasoningEngine"

**Verified fact:** `ReasoningEngine` (`src/knowledge/reasoning/engine.py`) contains zero references to `HistoricalSituationRetriever`. No import. No call site. No constructor invocation.

The actual reference exists in `OrchestrationContext` (`src/knowledge/orchestration/context.py`, line 42):
```python
retriever: HistoricalSituationRetriever | None = None
```

This is consumed by `OrchestrationEngine.analyze()` (lines 99–110) — which is itself dead code (C-05).

**Consequence:** An implementer following CER-007 would look for a non-existent call site in ReasoningEngine, find nothing, and either abandon the task or make an unauthorized frozen-core change.

---

## Finding 3: Unverified Production Owner Assignments

**Severity:** Medium — creates ambiguous accountability

| ID | Assigned Owner | Actual Owner (verified) | Issue |
|----|---------------|------------------------|-------|
| C-02 | ReasoningEngine | OrchestrationContext | Wrong component; OrchestrationEngine is dead code |
| C-04 | OrchestrationEngine | None (dangling type hint) | `ctx.causal_analyzer` field is never read by any code, including OrchestrationEngine |
| C-10 | OrchestrationEngine | OrchestrationEngine | Correct, but owner itself is dead code — no living owner |
| C-11 | OrchestrationEngine | OrchestrationEngine | Same issue |
| C-12 | — | OrchestrationEngine | Same issue |

**Pattern:** Five capabilities are assigned to OrchestrationEngine, which is itself inactive (C-05, Rank 14). Their production owner is effectively "nobody" until OrchestrationEngine is activated or they are re-routed to InferencePipeline.

---

## Finding 4: Inferred Dependencies Not Proven in Code

| Capability | Claimed Dependency | Verification Status |
|-----------|-------------------|---------------------|
| C-07 (DXY) | "C-15 — OOS must first confirm US10Y value before DXY is introduced per North Star §8" | **Policy dependency, not code dependency.** DXY enricher has zero import-time or runtime dependency on OOS. The constraint is governance, not architecture. |
| C-10 (Temporal) | "C-15 — validate value via OOS before activating" | **Same — governance only.** Temporal layer imports nothing from simulation/OOS. |
| C-13 (Learning chain) | "C-14 — immutable persistence required before feedback writes" | **Inferred.** FeedbackApplicator uses `VersionedStore` internally (constructor line 22) which is append-only by design. Content-addressing (C-14) adds tamper detection but is not a functional prerequisite. FeedbackApplicator works without it. |
| C-08 (Consensus) | "CrossEventAnalyzer (active)" | **Incorrect.** CrossEventAnalyzer is only called within OrchestrationEngine (dead code). It is not part of InferencePipeline. Activating C-08 therefore implicitly requires either activating OrchestrationEngine or calling CrossEventAnalyzer from a new location. |

---

## Finding 5: CER-006 Runtime Evidence

**Severity:** Low — absence noted

CER-007 cannot be contradicted by CER-006 because **CER-006 does not exist**. The `docs/audit/` directory contains only CER-004 and CER-007. No runtime profiling, execution trace, or performance evidence report is available to validate or contradict CER-007's activation feasibility claims.

**Consequence:** All "Ease of Activation" scores are based on static code analysis and line counts alone. No runtime evidence confirms that:
- EvidenceRanker's 4 ranking methods produce deterministic output on production-scale data
- MacroRegimeDetector.fit() converges reliably with available composite score data
- Temporal/Economic adapters maintain determinism guarantees when removed from OrchestrationEngine scaffolding

---

## Finding 6: Architectural Violation Risk

### 6a. CausalAnalyzer (C-04) requires frozen core changes

CER-007 suggests: *"Instantiate CausalAnalyzer and assign to OrchestrationContext.causal_analyzer"*

Even if done, this field is **never read** — not even by OrchestrationEngine's `_run_causal()` method (which uses `ctx.causal_graph`, a separate field). Activating CausalAnalyzer in the *production* path (InferencePipeline) would require adding a new pipeline stage — a frozen core modification.

### 6b. CrossEventResult (C-08) requires dead code resurrection

CrossEventAnalyzer is only invoked inside OrchestrationEngine. The InferencePipeline has no cross-event analysis stage. Wiring consensus into DecisionEngine requires either:
1. Adding CrossEventAnalyzer to InferencePipeline (frozen core change), or
2. Activating OrchestrationEngine first (C-05, currently Rank 14)

CER-007 rates C-08 at Rank 4 with "no dependencies." This is incorrect — it depends on either C-05 or a frozen core exception.

### 6c. EvidenceRanker (C-01) insertion point unclear

The natural insertion point is between evidence collection and reasoning in InferencePipeline's `_stage_reason()`. But `_stage_reason()` is frozen core. The alternative — a new `_stage_rank_evidence()` — requires modifying the frozen pipeline stage list.

---

## Summary of Corrections Required

| CER-007 Claim | Correction |
|--------------|-----------|
| C-02 "call site in ReasoningEngine" | No such site exists; site is in OrchestrationContext (dead code) |
| C-08 "no dependencies" | Depends on C-05 or frozen core exception |
| C-01, C-02, C-09 "Low effort" | Medium — all require frozen core governance decision |
| C-04 "assign to OrchestrationContext" | Field is never read; actual activation requires new pipeline stage |
| C-13 dependency on C-14 | Governance preference, not functional dependency |
| C-08 "CrossEventAnalyzer (active)" | CrossEventAnalyzer is NOT active in production path |

---

## Revised Risk Assessment for Top 6

| Rank | Capability | CER-007 Risk | Revised Risk | Reason |
|------|-----------|-------------|--------------|--------|
| 1 | C-15 OOS Evaluation | Low | Low | Confirmed — read-only evaluation, no code changes |
| 2 | C-13 Lesson Traceability | Low | Low | Confirmed — additive field on non-frozen entity |
| 3 | C-09 Evidence.explanation | Low | **Medium** | Requires modifying frozen ReasoningEngine |
| 4 | C-08 CrossEventResult | Low | **High** | Requires C-05 activation or frozen core exception; CrossEventAnalyzer is not in production path |
| 5 | C-01 EvidenceRanker | Low | **Medium** | Requires modifying frozen InferencePipeline stage |
| 6 | C-02 HistoricalSituationRetriever | Low | **High** | No call site exists in any active production code; requires new integration design |

---

## Conclusion

CER-007 correctly identifies the dormant capabilities and their general institutional value. Its primary deficiency is a **systematic underestimation of activation effort** caused by not accounting for the Frozen Core governance constraint. Six of the top eight ranked capabilities require modifying components that the project's own constitution forbids changing except for verified defects.

The practical consequence: before ranks 3–8 can be activated, the project must either:

1. **Define an extension mechanism** (pre/post hooks, middleware, or an adapter layer around InferencePipeline stages) that allows capability injection without modifying frozen core, or
2. **Issue a governance exception** via ADR explicitly permitting additive-only modifications to frozen core for capability activation.

Neither option exists today. Until one is established, only **Rank 1 (C-15)** and **Rank 2 (C-13)** are actionable without architectural violation.
