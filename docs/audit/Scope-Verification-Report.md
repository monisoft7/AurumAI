# Scope Verification Report

**Date**: 2026-08-01
**Task**: Verify whether `IMPLEMENTATION_WORKFLOWS.md` still reflects the current AurumAI project scope.
**Mode**: Document comparison only — no code inspected or modified, no recommendations.

---

## 1. Documents compared

| Document | Role | Status |
| --- | --- | --- |
| `docs/PROJECT_CONSTITUTION_V2.md` | Supreme governing document (ratified 2026-07-26) | Current |
| `IMPLEMENTATION_WORKFLOWS.md` | Workflow program: W1–W17 index, specs, priority tiers, implementation sequence | Under verification |
| `docs/audit/Certification-Summary.md` | Certified scope record (task PRE-A2, 2026-08-01) | Current |

Cross-references checked: the workflows document's cited sources
(`Institutional_Gold_Knowledge_Base.md`, `INSTITUTIONAL_CONTRACTS.md`,
`IMPLEMENTATION_MAPPING.md`, `W1_W2_INTEGRATION_REVIEW.md`) all exist at repo
root. A `Methodology.md` file was not found under that name ("Meth." section
references could not be verified against a single document).

---

## 2. Determination

**`IMPLEMENTATION_WORKFLOWS.md` describes a hybrid: it is partially current
and partially the previous broader vision.**

### 2.1 What remains current

- **The W-ID registry is the live authority.** The certification sprint and
  the conformance test (`tests/test_workflow_id_conformance.py`) parse the
  Workflow Index directly; the 14 registered workflow packages derive their
  canonical W-IDs from it (W3–W10, W12–W14).
- **The P1–P3 core specs match the implemented pipeline.** W3 (Pre-Market),
  W4 (Event Triage), W5 (Signal vs Noise), W6 (Evidence Collection &
  Weighting), W7 (Conflict Resolution), W8 (Thesis Formation), W9 (Confidence),
  W10 (Thesis Update), W12 (Scenario/Fragility), W13 (Bias Prevention &
  Decision Review), and W14 (as the final output workflow) all have
  corresponding certified packages, DAG stages, and conformance entries.

### 2.2 What is the previous broader vision

- **P0 foundation workflows (W1, W2)** are specified at full scale (batch
  ingestion of "207+ Knowledge Records" from the KB; 6-regime classifier,
  GRAM residual, indicator hierarchy) but are not part of the certified
  project: W1's implementation is orphaned and unreachable; W2 exists only as
  a partial frozen-core capability with its GRAM analyzer unwired.
- **P3 workflow W11 (Causal Relationship Evaluation)** has no workflow, no
  package, and no conformance entry.
- **P4 enhancement workflows (W15, W16, W17)** have no implementation and no
  scheduling record.
- **The W14 spec body (Decision Journal & Post-Mortem) is superseded.** The
  certification sprint mapped W14 to `trade_recommendation`; the journal,
  outcome matching, attribution quadrants, and post-mortem capabilities
  described in the W14 section do not exist.
- The document's **implementation sequence (P0 → P4)** is a build-everything
  roadmap; the certified project has implemented only the P1–P3 subset (minus
  W11).

### 2.3 Conclusion

The document is the **current** authoritative W-ID registry and accurately
describes the **implemented P1–P3 institutional core** (W3–W10, W12, W13, and
the W14 label), but as a whole it still describes the **previous broader
vision**: the P0 foundation (W1/W2 at full spec), W11, the P4 enhancements
(W15–W17), and the original W14 decision-journal spec. The certified project
scope (per `Certification-Summary.md`: 11 W-IDs / 14 packages) is a subset of
the document's 17 workflows.

---

## 3. Workflow classification

### 3.1 Obsolete (no longer describes current project scope)

| Workflow | Reason |
| --- | --- |
| **W1** Knowledge Record Ingestion & Encoding | Spec (207+ KB records → graph via adapters) is superseded by the constitution's department framework (40-object permanent inventory, frozen contracts, adapter-per-department); the only W1 implementation is orphaned (unreachable) and not certified |
| **W2** Macro Regime Diagnosis & Indicator Selection | Spec (6-regime classifier, GRAM residual, indicator hierarchy, transition engine) exceeds current capability: core has a 4-regime detector; the GRAM residual analyzer exists but is unwired; W2's completion criteria cannot fire in production |
| **W14** Decision Journal & Post-Mortem (spec body) | Superseded by the certification mapping W14 = `trade_recommendation`; journaling, outcome matching, and post-mortem are not part of the current project |

### 3.2 Mandatory (current certified scope)

| Workflow | Packages |
| --- | --- |
| **W3** Pre-Market Intelligence Scan | `pre_market` |
| **W4** Macro Event Prioritization & Triage | `event_triage` |
| **W5** Signal vs Noise Classification | `signal_assessment` |
| **W6** Evidence Collection & Regime-Aware Weighting | `evidence_collection`, `evidence_reasoning` |
| **W7** Conflicting Evidence Resolution | `counter_evidence` |
| **W8** Investment Thesis Formation | `thesis_construction` |
| **W9** Confidence Assignment & OOS Calibration | `confidence_engine` |
| **W10** Thesis Update Cycle | `thesis_update` |
| **W12** Fragility Audit & Scenario Analysis | `scenario_generation`, `risk_reward_validation` |
| **W13** Bias Prevention & Decision Review | `bias_prevention`, `decision_engine` |
| **W14** (certified meaning: trade recommendation) | `trade_recommendation` |

### 3.3 Optional (retained in the document, not in current certified scope)

| Workflow | Reason |
| --- | --- |
| **W11** Causal Relationship Evaluation & Graph Maintenance | P3-advanced; no implementation, no conformance entry, no certification claim |
| **W15** Cross-Asset Confirmation Matrix | P4 enhancement; no implementation |
| **W16** Multi-Window Evidence Aggregation (GRAM) | P4 enhancement; no implementation; predicated on the unwired GRAM capability |
| **W17** Institutional Auditor Interface | P4 compliance; no implementation; depends on the absent decision journal |

---

## 4. Verification notes

- The conformance registry and certification record use the document's W-ID
  index, so the index itself must not be treated as obsolete even where the
  surrounding specs describe unimplemented capabilities.
- No recommendation is made in this report; the classification above records
  current scope only.
