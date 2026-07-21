# PROJECT NORTH STAR
**AurumAI Engineering Constitution**
Version: 1.1
Status: Active
Authority: Highest Engineering Reference

## Documentation Authority

This document is the highest engineering authority in the repository. All other documentation must be consistent with this document. In case of conflict:

1. **PROJECT_NORTH_STAR.md** ← This file (highest authority)
2. **PROJECT_CONSTITUTION.md** ← Constitutional rules and governance
3. **CURRENT_STATE.md** ← Canonical project snapshot
4. **ROADMAP.md** ← Phased plan and gates
5. **PROJECT_STATUS.md** ← Version, progress, completed items
6. **Historical documents** ← Archived records, preserved for reference

---

# 1. Mission

AurumAI exists to build an Institutional Financial Intelligence System capable of producing deterministic, explainable and evidence-based investment assessments from historical macroeconomic data.

The project is **not** a trading bot.

Trading execution is only a downstream consumer of AurumAI intelligence.

---

# 2. Final Objective

The final objective is to produce institutional-grade investment decisions that can, only after successful historical validation, paper trading and risk validation, be consumed by a live execution layer.

The execution layer is not the product.

Institutional Intelligence is the product.

---

# 3. Core Engineering Principles

These principles are mandatory.

## 3.1 Reuse before Build

Always prefer mature open-source solutions when they satisfy the architectural requirements.

Never rebuild existing engineering work without evidence.

---

## 3.2 Determinism

The same inputs must always produce the same outputs.

No hidden randomness.

No hidden state.

No time-dependent behavior.

---

## 3.3 Explainability

Every decision must be traceable to:

Source Data

↓

Lessons

↓

Knowledge

↓

Evidence

↓

Reasoning

↓

Decision

No black-box decisions are permitted.

---

## 3.4 Evidence First

Opinions are prohibited.

Every engineering decision must be backed by reproducible evidence.

---

## 3.5 Smallest Correct Fix

Never redesign when a wiring fix is sufficient.

Never expand scope while fixing a bug.

Fix only the verified root cause.

---

## 3.6 Verification Before Implementation

Every reported issue must follow this workflow:

Verification

↓

Reproduction

↓

Root Cause

↓

Smallest Correct Fix

↓

Tests

↓

Regression

↓

Commit

No implementation before verification.

---

## 3.7 Backward Compatibility

Public APIs remain stable whenever reasonably possible.

Breaking changes require explicit architectural justification.

---


## Engineering Philosophy

AurumAI does not optimize for feature count.

AurumAI optimizes for institutional trust.

Every engineering task must increase one or more of:

- Correctness
- Determinism
- Explainability
- Reproducibility
- Measurable predictive value

Any task that does not improve one of these properties should be postponed.

---

# 4. Frozen Core

The following components are considered Frozen Core.

They may only be modified when a verified engineering defect cannot be corrected elsewhere.

- Inference Pipeline
- Reasoning Engine
- Decision Engine
- Evidence Engine
- Knowledge Graph Contracts
- Core Entity Contracts
- Institutional Assessment
- Constitutional Rules

---

# 5. Development Workflow

Every engineering task follows:

Verify

↓

Reproduce

↓

Root Cause

↓

Smallest Correct Fix

↓

Implementation

↓

Targeted Tests

↓

Regression Tests

↓

Commit

↓

Documentation Update (only if milestone changes)

---

# 6. Current Architecture

Raw Data

↓

Events

↓

Feature Extraction

↓

Lessons

↓

Knowledge Records

↓

Knowledge Graph

↓

Evidence

↓

Reasoning

↓

Decision

↓

Institutional Assessment

↓

Paper Execution

↓

Live Execution Adapter (future)

---

# 7. Current Phase

Institutional Readiness (Production Hardening Complete)

Current objective:

Prove institutional correctness using unseen historical data.

All Production Hardening and Core Stability AUR-FINAL items are resolved.
Remaining: OOS validation (Gate 6), immutable artifact persistence (Gate 5),
clean CI pipeline (Gate 7).

---

# 8. Immediate Goal

Build and execute the first complete Out-of-Sample institutional evaluation.

The result must answer:

- Is AurumAI correct?
- Is confidence calibrated?
- Does US10Y improve decisions?
- Should DXY be introduced?

No new intelligence capability will be added before these questions are answered.

---

# 9. Long-Term Roadmap

Institutional Readiness

↓

Out-of-Sample Validation

↓

Historical Production Pipeline

↓

Paper Trading Validation

↓

Live Execution Adapter

↓

Institutional Release v1.0

---

# 10. Out of Scope

Until Out-of-Sample validation succeeds, the following are out of scope:

- New macro indicators
- New event types
- New AI models
- Broker integrations
- Live trading
- Major architectural refactoring
- Cosmetic optimization
- Performance tuning without evidence

---

# 11. Success Criteria

AurumAI will be considered institutionally complete only when:

✓ Knowledge can be rebuilt deterministically from raw historical data.

✓ Institutional decisions are reproducible.

✓ Lineage is complete.

✓ Out-of-Sample evaluation demonstrates measurable predictive value.

✓ Paper Trading validates operational behavior.

✓ Risk controls pass institutional validation.

Only then may the Live Execution Adapter be enabled.

---

# 12. Engineering Rule of Focus

No new capability shall be implemented until the previous capability has demonstrated measurable value.

Engineering effort must always maximize institutional intelligence rather than feature count.

---

## Amendment Log

- 2026-07-21: Version 1.1. Declared highest engineering authority. Added Documentation Authority hierarchy. Updated Current Phase to include Production Hardening completion.