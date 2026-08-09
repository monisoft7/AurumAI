# AurumAI

AurumAI is a **Market Intelligence Operating System** for gold and macroeconomic markets.

It is **not a trading bot**. Its purpose is to transform market and economic observations into historical lessons, structured knowledge, evidence, reasoning, and explainable institutional assessments.

## Current stage

**Institutional Validation**

Production hardening is complete, while operational validation and empirical out-of-sample validation remain active.

The project is deliberately being validated before any live-execution capability is considered.

## What AurumAI does

The current intelligence path is:

```text
Market / Economic Data
        ↓
Events & Feature Extraction
        ↓
Historical Lessons
        ↓
Knowledge Records
        ↓
Knowledge Graph
        ↓
Evidence Retrieval & Ranking
        ↓
Institutional Reasoning
        ↓
Decision
        ↓
Institutional Assessment
```

The system can also incorporate contextual macro factors and compare context-conditioned knowledge against single-factor knowledge before accepting additional context.

## Major capabilities

The repository contains infrastructure for:

- Knowledge Records and knowledge aggregation
- NetworkX knowledge graph
- Evidence retrieval and ranking
- Explainable reasoning
- Institutional decision gating
- Economic, temporal, and causal intelligence
- Forecasting
- Risk intelligence
- Provenance and lineage
- Chronological out-of-sample evaluation
- Institutional experiment management
- Paper-trading infrastructure
- Production hardening and operational validation

These capabilities describe implemented infrastructure; they are **not by themselves claims of profitability or predictive superiority**.

## Validation status

| Area | Current position |
|---|---|
| Core runtime | Operational |
| Production hardening | Complete |
| Reproducibility | Validated at the documented milestone |
| OOS validation infrastructure | Implemented |
| Institutional experiments | Active |
| Paper-trading infrastructure | Implemented |
| Operational validation | Active |
| Predictive value | Still under empirical validation |

### Current known validation issue

Operational Validation Run 002 identified a **decision-material Knowledge → Evidence lineage failure**.

The validation process is intentionally designed to expose this type of defect rather than hide it behind a successful downstream decision.

The current engineering sequence is therefore:

```text
Verify runtime evidence
        ↓
Identify causal boundary
        ↓
Apply smallest correct fix
        ↓
Run targeted regression
        ↓
Re-run operational validation
        ↓
Update the dated validation artifact
```

No broad architectural redesign is implied by this finding.

## Engineering principles

AurumAI prioritizes:

- Deterministic behavior
- Explainability
- Provenance and lineage
- Versioned institutional knowledge
- Auditable decisions
- Testability
- Smallest-correct-fix discipline
- Empirical validation before expansion

The project does not treat feature count or model count as evidence of intelligence quality.

## Repository guidance

Start with:

- `PROJECT_NORTH_STAR.md` — highest engineering authority
- `PROJECT_CONSTITUTION.md` — operating doctrine
- `CURRENT_STATE.md` — current project state
- `ROADMAP.md` — development roadmap
- `PROJECT_STATUS.md` — status snapshot
- `docs/external/` — external technical and funding material
- `docs/audit/` — repository and documentation audit

## Validation

Validation is intentionally split into targeted regression tests, operational validation runs, chronological OOS experiments, and full-suite verification at milestone gates.

Do not interpret the existence of a large test suite as proof of predictive performance.

For the external validation position, see:

`docs/external/VALIDATION_STATUS.md`

## External / funding review

For a concise technical overview, current validation position, infrastructure funding plan, and disclosure boundary, see:

`docs/external/`

AurumAI is seeking resources primarily to improve:

1. validation and reproducibility;
2. data quality and provenance;
3. controlled AI/model experimentation;
4. research compute;
5. operational auditability.

The objective is to establish reliable institutional intelligence through evidence, not to add AI models for their own sake.

## Status discipline

AurumAI must not be represented as:

- a proven profitable trading bot;
- an autonomous live trader;
- a guaranteed investment system;
- a validated alpha engine;

unless a current, reproducible artifact explicitly supports the claim.

See `docs/external/DISCLOSURE_BOUNDARY.md`.
