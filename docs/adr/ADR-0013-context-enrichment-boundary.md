# ADR-0013: Context Enrichment Boundary — Deferred Generic Framework

**Date:** 2026-07-21
**Status:** Active
**Core v1.0 dependency:** Frozen (no core changes)

---

## 1. Summary

This ADR records the deliberate decision **not** to build a generic, pluggable Context
Enricher Framework. Instead, each context enricher is integrated into the pipeline
only after passing an Institutional Experiment. The pipeline currently supports
exactly one context enricher at the source-code level (US10Y via
`YieldContextEnricher`); any additional enricher will be added via the same
pattern — individually wired, individually validated.

---

## 2. Decision

### 2.1 The Pipeline Enriches Only Experimentally Validated Contexts

A context source is integrated into the pipeline *iff* it has been accepted by an
Institutional Experiment (Experiment Framework + Experiment Registry). No context
enricher enters without an experiment record and an institutional verdict.

### 2.2 US10Y Is the First Validation Target

US10Y was selected as the initial context enricher because:
- It is the single most referenced external signal in gold (XAU/USD) analysis.
- The `YieldContextEnricher` implementation is 134 lines, reuses existing data
  (DGS10.csv, 1962–2026), and follows established patterns.
- ADR-0005 §2.2 confirmed that US10Y vs CPI-only achieves
  **context_adds_value** (3 improvements, 2 weakenings).

### 2.3 Future Contexts Enter Only After Institutional Experiments

The following context sources are known candidates but are **not** integrated:

| Context | Status | Reason |
|---------|--------|--------|
| DXY (US Dollar Index) | `DXYContextEnricher` exists (ADR-0005) | Experimentally inconclusive — "not yet helpful alone" (ADR-0005 §7) |
| Oil (WTI/Brent) | No enricher exists | Not yet proposed for experiment |
| Silver (XAG) | No enricher exists | Not yet proposed for experiment |

Each candidate must follow the same lifecycle: create enricher → register
Institutional Experiment → evaluate → accept/reject. Only accepted contexts are
wired into the pipeline.

### 2.4 Generic Context Enricher Framework — Intentionally Deferred

A generic, registry-based enricher framework (e.g., `ContextEnricher(ABC)`,
enricher plugin list, auto-discovery) is **not** built and will not be built at
this stage.

**Reasons:**

| Principle | Application |
|-----------|-------------|
| **Smallest Correct Increment** | N = 1 validated enricher does not justify a registry. A for-loop over one element is an anti-pattern. |
| **Reuse before Build** | The existing pattern — single `if`-block in `_stage_build_lessons` — reuses the pipeline's natural extension point. No new abstraction layer is needed yet. |
| **Evidence before Expansion** | ADR-0005 demonstrates that even well-motivated contexts (DXY) can fail experimental validation. Building a generic framework before accumulating validated instances would be speculative. |

**Result:** The pipeline retains a hardcoded enrichment call. This is a feature, not
a debt — it guarantees that every enrichment path in the codebase corresponds to a
validated experiment.

---

## 3. Trigger for Revisiting

> **When three or more independent context enrichers have been institutionally
> accepted and wired into the pipeline, the team shall revisit the decision to
> defer a generic Context Enricher Framework.**

At N ≥ 3, the hardcoded pattern crosses the threshold where a registry, common
protocol, and generic `PipelineContext` field would reduce per-enricher cost and
improve consistency. Until then, the hardcoded pattern is the smaller correct
increment.

---

## 4. Related Documents

| Document | Relationship |
|----------|-------------|
| `PROJECT_NORTH_STAR.md` | Highest authority — "Smallest Correct Increment," "Evidence before Expansion" |
| ADR-0005 (DXY Context Layer) | Documents DXY enricher and its experimental finding: "not yet helpful alone" |
| ADR-0004 (Canonical Inference Path) | Defines the pipeline architecture that enrichment hooks into |
| `src/knowledge/pipeline/pipeline.py` (`_stage_build_lessons`) | Current single-enricher extension point |
| Institutional Experiment Framework (`src/simulation/experiment.py`) | Gate for context acceptance |
| Experiment Registry (`src/simulation/experiment_registry.py`) | Source of truth for which contexts have passed |

---

## 5. Consequences

### Positive

- Every enrichment path in the codebase corresponds to a validated experiment.
- Zero speculative abstraction; zero unused enricher hooks in `PipelineContext`.
- Adding a new context enricher follows the same simple pattern — one `if`-block,
  one config field — without needing to understand a framework.
- The architecture freeze is not blocked by framework design.

### Negative

- Adding a second validated enricher requires a code change to `pipeline.py`
  (new `if`-block) and `context.py` (new field). This is acceptable because the
  change is ~5 lines and occurs only after experimental validation confirms the
  enricher adds value.
- If three enrichers are accepted quickly, a small refactor will be needed to
  introduce the generic framework. This risk is accepted per "Evidence before
  Expansion."
