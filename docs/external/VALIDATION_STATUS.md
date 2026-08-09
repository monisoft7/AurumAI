# AurumAI — Validation Status

**Stage: Institutional Validation**

Production hardening and substantial intelligence infrastructure are recorded in the repository. However, full institutional release readiness has not yet been established.

## Evidence recorded by the repository

- production-hardening validation with zero reported regressions at the corresponding milestone;
- reproducibility assessment recorded as A / fully deterministic;
- chronological OOS engine with strict train/evaluation separation;
- institutional experiment framework;
- deterministic SHA-256 experiment registry;
- paper-trading portfolio, slippage, commission, and execution-gating components;
- operational validation protocol focused on runtime evidence.

Implemented infrastructure is not, by itself, evidence of predictive value or profitability.

## Experiment 001

CPI baseline vs CPI + US10Y context.

Recorded verdict: **REJECT US10Y**.

The tested context produced no measurable improvement in the reported OOS decision metrics and no decision changes.

This is evidence about the tested experiment and configuration. It is not proof that US10Y is universally useless.

## Operational Validation Run 002

Recorded result:

- Runtime Integrity: PASS
- OI second observation: PASS
- SignalAssessment: PASS
- Knowledge → Evidence: **FAIL**

The failure is material because the validation protocol requires decision-relevant evidence to be traceable to real KnowledgeRecords and rejects unexplained synthetic evidence dependencies.

Therefore the correct external position is:

> AurumAI has an active institutional validation mechanism that has identified a decision-material evidence-integrity issue requiring resolution before full institutional release readiness can be claimed.

## Current validation boundary

The current objective is not to add features indiscriminately.

The immediate objective is to:

1. establish the exact causal boundary of the Knowledge → Evidence failure;
2. apply the smallest correct correction;
3. run targeted regression validation;
4. repeat the complete operational validation;
5. record the resulting evidence as a dated reproducible artifact.

## Causal boundary status (2026-08-09)

The exact causal boundary of the Knowledge → Evidence failure has been established from source evidence and independently reproduced:

- The institutional evidence path (`EvidenceCollector`, `src/evidence_collection/collector.py:132-134`) links an evidence item to a real KnowledgeRecord only when the knowledge graph contains a node matching the observation's mapped event class (or its evidence-class equivalent, or `GENERAL`).
- The current production knowledge corpus contains only six CPI KnowledgeRecords (`data/economic/output/knowledge.json`). Daily pre-market observations map to `GENERAL` / `USD_FX` / `REAL_YIELD` / `ETF_FLOW` event classes, none of which exist in the corpus; the collector therefore takes its explicit synthetic fallback (`source_kr_id = kr_synthetic_<observation_id>`).
- Result: in Operational Validation Run 002, all four decision-relevant evidence items carry synthetic `source_kr_id` values that flow into evidence quality, confidence, and the final decision — the decision-materiality the validation protocol requires to be eliminated.
- The frozen core knowledge/evidence path is not implicated: it links real KnowledgeRecord IDs whenever queried. `INFLATION`-class observations (Breakeven Inflation) can already link to the real CPI records via `EVENT_TYPE_TO_EVIDENCE_CLASS`.

Full boundary analysis and reproduction: `docs/audit/FUNDING_READINESS_AUDIT_001.md`. No core source code has been changed to reach this conclusion; the correction decision and smallest safe scope remain open per the validation protocol.
