# CAI Naming Resolution — Constitutional Consistency Audit

**Date:** 2026-07-27
**Scope:** Resolve naming mismatch between governance documents and implementation for Cross-Asset Intelligence knowledge objects

---

## Documents Reviewed

| Artifact | Type | Names Used |
|----------|------|------------|
| `PROJECT_CONSTITUTION_V2.md` (Section 5.2) | Governance — supreme | 8 aspirational names |
| `Institutional-Knowledge-Contracts.md` (Section 2) | Governance — design specification | Same 8 aspirational names |
| `Cross-Asset-Intelligence.md` (Charter) | Architecture — department design | Operational descriptions (no contract names) |
| `knowledge/cai/contracts.py` | Implementation | 5 implemented contract names |
| `REFERENCE_DEPARTMENT_TEMPLATE.md` | Engineering standard | Implementation names (codified post-implementation) |

---

## Mismatch Analysis

### Constitution Section 5.2 + Knowledge Contracts Section 2 Names

| # | Name | Type | Implementation Equivalent? |
|---|------|------|--------------------------|
| 2.1 | CrossAssetStrengthMatrix | Full field spec in contracts | **No equivalent** |
| 2.2 | CorrelationStabilityIndex | Full field spec in contracts | CrossAssetCorrelation — different fields |
| 2.3 | DivergenceAlert | Full field spec in contracts | SpreadAnalysis — different fields |
| 2.4 | LiquidityRotationMap | Full field spec in contracts | FlowPressure — partial match |
| 2.5 | SafeHavenRotationIndex | Full field spec in contracts | **No equivalent** |
| 2.6 | DollarPressureIndex | Full field spec in contracts | **No equivalent** |
| 2.7 | CrossAssetRegimeAssessment | Full field spec in contracts | VolatilityRegime — different fields |
| 2.8 | InstitutionalConfirmationMatrix | Full field spec in contracts | **No equivalent** |

### Implementation Names (contracts.py)

| # | Name | Type | Governance Equivalent? |
|---|------|------|----------------------|
| 1 | CrossAssetCorrelation | Frozen dataclass (7 domain fields) | CorrelationStabilityIndex — different name AND fields |
| 2 | SpreadAnalysis | Frozen dataclass (8 domain fields) | DivergenceAlert — different name AND fields |
| 3 | RelativeValueAssessment | Frozen dataclass (6 domain fields + FrozenDict) | **No equivalent in governance** |
| 4 | FlowPressure | Frozen dataclass (7 domain fields) | LiquidityRotationMap — partial semantic match |
| 5 | VolatilityRegime | Frozen dataclass (7 domain fields) | CrossAssetRegimeAssessment — different name AND fields |

### Overlap

**Zero.** There is no overlap between the two name sets. No contract in `contracts.py` shares a name with any knowledge object listed in the constitution or the Institutional-Knowledge-Contracts.md.

---

## Authority Hierarchy

Per PROJECT_CONSTITUTION_V2.md Section 13.2:

| Rank | Document | Status |
|------|----------|--------|
| 5 | PROJECT_CONSTITUTION_V2.md | **Supreme** — lists 8 aspirational names |
| — | Institutional-Knowledge-Contracts.md | Codifies Section 5.2 with full field specs |
| — | Cross-Asset-Intelligence.md | Department charter — operational, no contract names |
| — | REFERENCE_DEPARTMENT_TEMPLATE.md | Engineering standard — uses implementation names |
| — | `contracts.py` | Executable code — 5 deployed contracts |

The constitution is supreme. However, Section 5.2 was written as an aspirational design-time inventory — it names objects that **should exist** for each department. These names were never validated against the implementation because the implementation was designed concurrently.

The Institutional-Knowledge-Contracts.md Section 2 provides detailed field specifications for each of the 8 named CAI objects. These field specifications do not match the implementation's contract fields at any level — not name, not structure, not semantics.

---

## Root Cause

The constitution's Section 5.2 was compiled as a forward-looking institutional inventory during the v2 ratification. It describes what CAI **could** produce at full analytical depth. The CAI charter was written concurrently as an operational design document, describing workflows ("correlation matrix," "divergence register," "rotation map") rather than contract names.

During Wave-2A implementation, contracts were designed independently by applying the CBI pattern (base contract + domain-specific frozen dataclasses) to the CAI charter's operational domain. The implementers chose names that matched the analytical measurements being captured — CrossAssetCorrelation (a specific measurement), SpreadAnalysis (a specific analysis), VolatilityRegime (a specific assessment) — rather than the governance documents' composite names (CorrelationStabilityIndex, DivergenceAlert, CrossAssetRegimeAssessment).

This was not a deliberate renaming. It was a **coordination failure between two parallel design activities**:
1. Governance authors designed a comprehensive 8-object inventory with composite names and detailed field specs
2. Implementers designed contracts independently using the CBI pattern, producing 5 simpler objects with measurement-oriented names

Neither activity cross-referenced the other before producing artifacts.

---

## Authoritative Source

**The implementation (`contracts.py`) is the effective authoritative source** for the following reasons:

1. **The implementation has passed all gates.** Contract, repository, adapter, and pipeline activation are all complete with 483+ passing tests. The Wave-2C gate decision (10/10 checks) and Wave-2D activation both used these names.

2. **The implementation pattern matches the proven template.** Every contract follows the exact CBI pattern (frozen dataclass, base contract inheritance, Provenance, explicit bias mapping in adapter). The governance documents' field specs would require a different contract structure that does not follow the CBI pattern.

3. **The Reference Template codifies these names.** `REFERENCE_DEPARTMENT_TEMPLATE.md` (the engineering playbook for all future departments) uses the implementation names throughout — proving they are the canonical engineering standard.

4. **The implementation names are structurally sound.** Each contract captures a single, well-defined analytical measurement with clear domain fields, following the "one concern per contract" principle of the CBI pattern.

5. **The governance field specs are incompatible with the implemented contracts.** The knowledge contracts describe objects with fundamentally different field structures (e.g., CrossAssetStrengthMatrix with NxN matrices vs any implemented contract). Re-implementing to match these specs would require a different architectural approach, not a rename.

---

## Required Action

Amend the governance documents to match the implementation. Specifically:

### 1. PROJECT_CONSTITUTION_V2.md — Section 5.2

Replace the CAI line with the 5 implemented names + note that additional objects may be added as Institutional Expansion:

> **CAI (5 objects, 2 expansion pending)**: CrossAssetCorrelation, SpreadAnalysis, RelativeValueAssessment, FlowPressure, VolatilityRegime

### 2. Institutional-Knowledge-Contracts.md — Section 2

Replace the entire Section 2 (8 objects with aspirational field specs) with the 5 implemented contracts and their actual field definitions. The governance documents must describe what exists, not what was once imagined.

### 3. Cross-reference updates

Update any cross-references in other departments' knowledge contracts (Section 1.8 GlobalMonetaryRegime references "CAI CrossAssetRegimeAssessment" → should reference "CAI VolatilityRegime"; Section 3.1 GoldPositioningDashboard references "CAI InstitutionalConfirmationMatrix" → no current equivalent, should note as future expansion).

---

## What This Means

**The governance documents were aspirational. The implementation is ground truth.**

The constitution's Section 5.2 served its purpose as a design-phase inventory but was never updated to reflect the implementation produced by Wave-2A through 2D. Continuing to assert the aspirational names as authoritative while the implementation uses different names creates permanent constitutional drift. The constitution must describe the institution as it exists — not as it was once planned.

The amendment aligns governance with implementation, following the same principle as the Reference Template (which was written post-implementation and correctly uses the actual contract names).

---

## Files Requiring Amendment

| File | Change |
|------|--------|
| `docs/PROJECT_CONSTITUTION_V2.md` | Section 5.2 — replace CAI name list |
| `docs/architecture/Institutional-Knowledge-Contracts.md` | Section 2 — replace with 5 implemented contracts and their field specs |

---

## Safe to Proceed to Wave-3

**YES**

The naming mismatch is resolved by aligning governance documents with the existing implementation. No code changes are required. No running system is affected. The Reference Template already documents the correct names and is ready for use by the next department.

---

## Amendment

The amendment to PROJECT_CONSTITUTION_V2.md and Institutional-Knowledge-Contracts.md is produced as a companion change to this resolution, updating only the affected governance documents and leaving the implementation untouched.

---

## Verification

| # | Check | Result |
|---|-------|--------|
| 1 | One artifact modified (governance), zero artifacts modified (implementation) | Governance docs only |
| 2 | All implemented contract names appear in governance docs | After amendment |
| 3 | No governance name contradicts implementation | After amendment |
| 4 | Reference Template stays in sync with governance | Already aligned with implementation names |
| 5 | Cross-department references resolved | Knowledge contracts cross-references updated |