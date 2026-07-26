# Sprint-007: Architecture Verification — Zero-Impact Analysis

**Date:** 2026-07-25
**Scope:** Institutional Context in ReasoningEngine explanation only

---

## Components Analyzed

| Component | File | Lines | Role |
|-----------|------|-------|------|
| `ReasoningEngine` | `src/knowledge/reasoning/engine.py` | 253 | Orchestrates reasoning phases |
| `ReasoningContext` | `src/knowledge/reasoning/context.py` | 18 | Frozen input context |
| `ReasoningChain` | `src/knowledge/reasoning/chain.py` | 26 | Frozen output chain |
| `ReasoningStep` | `src/knowledge/reasoning/step.py` | 23 | Frozen step with `conclusion` (str) and `details` (dict) |
| `DecisionEngine` | `src/knowledge/decision/engine.py` | 97 | Consumes chain — reads `details`, not `conclusion` |

Note: `EvidenceReview` and `ConclusionBuilder` are not separate classes. They are methods `_build_evidence_review()` and `_build_conclusion()` within `ReasoningEngine`.

---

## Method Inventory — Input/Output/Side-Effects/Consumers

### Methods that would NOT be modified

| Method | Inputs | Outputs | Side effects | Existing consumers |
|--------|--------|---------|--------------|-------------------|
| `reason()` | `EvidenceCollection`, `ReasoningContext` | `ReasoningChain` | None | `InferencePipeline._stage_reason()` |
| `_build_evidence_review()` | `Evidence`, `int` | `ReasoningStep` (type=evidence_review) | None | `reason()` |
| `_add_comparison_steps()` | `EvidenceCollection`, `list[ReasoningStep]` | None | Appends to steps list | `reason()` |
| `_weigh()` | `EvidenceCollection` | `WeightedAggregate` | None | `reason()` |
| `_build_aggregation()` | `EvidenceCollection`, `WeightedAggregate`, `list[ReasoningStep]`, `int` | `ReasoningStep` (type=aggregation) | None | `reason()` |
| `_compute_overall_confidence()` | `EvidenceCollection` | `float` | None | Unused in current code |
| `_format_condition()` | `dict[str,str]` | `str` | None | `_build_evidence_review`, `_build_comparison`, `_build_conclusion` |
| `_average_confidence()` | `list[Evidence]` | `float` | None | `_build_comparison` |

These 8 methods handle ALL reasoning logic: evidence review, grouping, comparison detection, weighting, aggregation, and confidence computation. None would be touched.

### Methods that WOULD be modified (explanation only)

| Method | Inputs | Outputs | Side effects | Existing consumers |
|--------|--------|---------|--------------|-------------------|
| `_build_conclusion()` | `EvidenceCollection`, `WeightedAggregate`, `ReasoningContext`, `list[ReasoningStep]`, `int` | `ReasoningStep` (type=conclusion) | None | `reason()` |
| `_build_comparison()` (optional) | `list[Evidence]`, `str` event_type, `int` | `ReasoningStep` (type=comparison) | None | `_add_comparison_steps()` |
| `_build_chain_id()` (optional) | `ReasoningContext` | `str` | None | `reason()` |

---

## Modification Trace: `_build_conclusion()`

### Current code (lines 179–227)

```
Inputs:
  evidence: EvidenceCollection      # UNCHANGED
  wa: WeightedAggregate              # UNCHANGED
  context: ReasoningContext          # UNCHANGED
  steps: list[ReasoningStep]        # UNCHANGED (used for step_id count only)
  index: int                         # UNCHANGED

Flow:
  1. avg_ret = wa.weighted_avg_return         # UNCHANGED
  2. avg_conf = wa.weighted_avg_confidence     # UNCHANGED
  3. direction determined from avg_ret         # UNCHANGED
  4. context_desc built from context fields    # ← ONLY CHANGE: add institutional_context
  5. conclusion string built from context_desc # ← CHANGED: longer string
  6. attribution lines from wa.attribution     # UNCHANGED
  7. details dict built from context fields    # UNCHANGED (no institutional_context added to details)

Outputs:
  ReasoningStep with:
    step_id           # UNCHANGED
    step_type         # UNCHANGED (CONCLUSION)
    conclusion        # CHANGED: different string content
    confidence        # UNCHANGED (avg_conf)
    supporting_evidence_ids  # UNCHANGED
    details           # UNCHANGED (dict keys identical)
```

### Critical verification: `_extract_avg_return()` in DecisionEngine

```python
def _extract_avg_return(self, chain: ReasoningChain) -> float:
    for step in reversed(chain.steps):
        if step.step_type in (STEP_AGGREGATION, STEP_CONCLUSION):
            val = step.details.get("avg_return_pct")      # ← reads DETAILS, not CONCLUSION
            if val is not None:
                return val
            val = step.details.get("average_return_pct")  # ← reads DETAILS, not CONCLUSION
            if val is not None:
                return val
    return 0.0
```

DecisionEngine reads `step.details`, NOT `step.conclusion`. The `details` dict would NOT be modified. Therefore DecisionEngine is **completely unaffected**.

---

## Consumer Analysis: Where does `step.conclusion` flow?

All paths from `step.conclusion` to consumers:

```
_build_conclusion() → step.conclusion (str)
  │
  ├── reason() → chain.final_conclusion = steps[-1].conclusion
  │     │
  │     ├── ReasoningChain.final_conclusion (field)
  │     │     │
  │     │     ├── repository.py:32 — serialized to JSON (storage only)
  │     │     ├── pipeline/repository.py:92 — serialized to pipeline result (output only)
  │     │     └── tests: assert checks (verification only)
  │     │
  │     └── repository.py:25 — s.conclusion serialized per-step (storage only)
  │
  └── benchmark/decision.py — mock data construction (no real chain consumed)
```

**Zero feedback paths.** No consumer reads `step.conclusion` or `final_conclusion` and feeds it back into any reasoning, weighting, confidence, evidence selection, or decision logic.

---

## Evidence vs Explanation: The architectural boundary

The ReasoningEngine computes two categories of output for each step:

| Category | Fields | Affected? |
|----------|--------|-----------|
| Inference | `confidence`, `supporting_evidence_ids`, `details.*` | NO |
| Explanation | `conclusion` (human-readable string) | YES |

The inference fields are consumed by DecisionEngine. The explanation field (`conclusion`) is consumed by humans and storage only. This boundary is respected by all existing code.

---

## Answers

**1. Can explanation enrichment accidentally influence reasoning?**

**NO.** The `conclusion` string is never read by any reasoning path. `reason()` reads `len(steps)` and `s.step_id` from prior steps — neither depends on conclusion content. `_build_conclusion()` reads `wa.weighted_avg_return`, `wa.weighted_avg_confidence`, `wa.attribution`, `context.*`, `len(evidence)` — none of these change when conclusion text changes.

**2. Is every added field read-only?**

**YES.** `ReasoningContext.institutional_context` is already frozen (Sprint-004). No new mutable fields would be added. The only new code would be a `_format_institutional_context()` static method (pure function) and string concatenation in `_build_conclusion()`.

**3. Is every modification observational only?**

**YES.** All modifications change `conclusion` string content only. Inference-critical values (avg_return, confidence, direction, evidence count, attribution) are computed before conclusion rendering and stored in `details` dict, which is untouched.

**4. Can the implementation be formally considered "zero-impact on inference"?**

**YES.** Formal proof:
- All inference inputs: `EvidenceCollection`, `WeightedAggregate`, `ReasoningContext`
- All inference outputs: `step.confidence`, `step.supporting_evidence_ids`, `step.details`, `chain.overall_confidence`, `chain.attribution`
- The proposed changes affect ONLY: `step.conclusion` (string) and optionally `chain.chain_id` (identifier)
- `chain.chain_id` is a content-addressable identifier used for storage keys and display — no inference branch depends on its value
- No code path reads `step.conclusion` or `chain.final_conclusion` and uses it to compute any inference output

---

## Summary

| Criterion | Status |
|-----------|--------|
| Changes cannot affect conclusion direction | ✅ Direction from `wa.weighted_avg_return` — unchanged |
| Changes cannot affect evidence ordering | ✅ Evidence iteration order — unchanged |
| Changes cannot affect confidence | ✅ Confidence from `wa.weighted_avg_confidence` — unchanged |
| Changes cannot affect hypothesis generation | ✅ No hypothesis step exists — unchanged |
| Changes cannot affect contradiction detection | ✅ Comparison uses `e.average_return_pct` only — unchanged |
| All added fields are read-only | ✅ Frozen dataclass, pure static method, local string var |
| All modifications are observational | ✅ Only `conclusion` string content changes |
| Zero impact on inference | ✅ Formal proof above |

---

READY FOR IMPLEMENTATION
