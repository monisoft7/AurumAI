# AurumAI — Validation Status

**Stage: Institutional Readiness / Validation**

## Evidence recorded by the repository

- production-hardening validation with zero reported regressions at the corresponding milestone;
- reproducibility assessment recorded as A / fully deterministic;
- chronological OOS engine with strict train/evaluation separation;
- institutional experiment framework;
- deterministic SHA-256 experiment registry;
- paper-trading portfolio, slippage, commission, and execution-gating components;
- operational validation protocol focused on runtime evidence.

## Experiment 001

CPI baseline vs CPI + US10Y context.

Recorded verdict: **REJECT US10Y**.

The tested context produced no measurable improvement in the reported OOS decision metrics and no decision changes. This is evidence about that experiment, not proof that US10Y is universally useless.

## Operational Validation Run 002

Recorded result:

- Runtime Integrity: PASS
- OI second observation: PASS
- SignalAssessment: PASS
- Knowledge → Evidence: **FAIL**

The failure is material because the validation protocol requires decision-relevant evidence to be traceable to real KnowledgeRecords and rejects unexplained synthetic evidence dependencies.

Therefore the correct external position is:

> AurumAI has an active institutional validation mechanism that has identified a decision-material evidence-integrity issue requiring resolution before full institutional readiness can be claimed.

## Required next sequence

```text
Runtime evidence → causal boundary → smallest correct fix
→ targeted regression → full validation → updated artifact
```

No broad architectural redesign is implied.
