# Sprint-007: Institutional Context Aware Reasoning — Readiness

**Date:** 2026-07-25
**Status:** Readiness Analysis — No Implementation

---

## Prerequisites

| Prerequisite | Status |
|-------------|--------|
| FC-001 (Semantic Condition Matching) | ✅ Complete |
| Sprint-004 (Institutional Context Visibility) | ✅ Complete |
| Sprint-005 (Context-Aware Evidence Retrieval) | ✅ Validated |
| Sprint-006 (Context-Aware Evidence Weighting) | ❌ Rejected by CTO |

---

## ReasoningEngine Architecture

### Core data flow

```
EvidenceCollection + ReasoningContext
  │
  ├── Phase 1: Evidence Review (one step per evidence)
  │     Uses: ev.condition, ev.average_return_pct, ev.horizon_days,
  │            ev.confidence, ev.sample_count
  │     Reads institutional_context: NO
  │
  ├── Phase 2: Comparison (one step per event_type with ≥2 evidence)
  │     Uses: ev.condition, ev.horizon_days, ev.average_return_pct, ev.confidence
  │     Groups by: event_type → (condition + horizon)
  │     Reads institutional_context: NO
  │
  ├── Phase 3: Weight (delegates to EvidenceWeighter)
  │     Uses: ev.confidence, ev.sample_count, ev.provenance, ev.bias, ev.event_type
  │     Reads institutional_context: NO (Sprint-006 confirmed this is correct)
  │
  ├── Phase 4: Aggregation (one step)
  │     Uses: WeightedAggregate fields
  │     Reads institutional_context: NO
  │
  └── Phase 5: Conclusion (one step)
        Uses: context.event_type, context.condition, context.horizon_days
        Reads institutional_context: NO (field exists but never accessed)
```

### Current context usage in ReasoningEngine

`ReasoningContext` (from Sprint-004) already contains `institutional_context: dict[str, str]`. However, the engine reads only three fields from context:

| Context field | Used in | Purpose |
|-------------|---------|---------|
| `event_type` | `_build_conclusion()`, `_build_chain_id()` | Identifies which event the reasoning is about |
| `condition` | `_build_conclusion()`, `_build_chain_id()` | Describes the query condition in conclusion text |
| `horizon_days` | `_build_conclusion()`, `_build_chain_id()` | Describes the horizon in conclusion text |
| `institutional_context` | **Nowhere** | Exists but is dead weight in the reasoning path |

### Conclusion text construction

```python
# Current _build_conclusion():
context_desc = f"{context.event_type}"
if context.condition:
    context_desc += f" condition {self._format_condition(context.condition)}"
if context.horizon_days is not None:
    context_desc += f" over {context.horizon_days} days"

conclusion = (
    f"For {context_desc}, the evidence indicates {direction} "
    f"(weighted confidence: {avg_conf:.3f}, "
    f"based on {len(evidence)} evidence items)."
)
```

The `context_desc` assembles a human-readable description of the reasoning context. Institutional context is absent from this description even though it's available in `context.institutional_context`.

### Chain ID construction

```python
def _build_chain_id(self, context: ReasoningContext) -> str:
    parts = ["reason", context.event_type]
    if context.condition:
        for v in context.condition.values():
            parts.append(v.replace(" ", "_"))
    if context.horizon_days is not None:
        parts.append(str(context.horizon_days))
    return "_".join(parts)
```

The chain ID does NOT include institutional context. This means two identical reasoning queries with different institutional contexts would produce the same chain ID — a **determinism gap** because distinct contexts should produce distinct chain IDs. However, this is a correctness issue only if institutional context influences reasoning output, which it currently does not.

---

## Analysis

### 1. Which reasoning responsibility legitimately owns Institutional Context

| Responsibility | Current owner | Institutional Context fit |
|---------------|--------------|--------------------------|
| **Hypothesis generation** | None — engine has no hypothesis step | ❌ Would require new infrastructure (redesign) |
| **Contradiction detection** | `_build_comparison()` detects directional contradictions | ⚠️ Context could EXPLAIN contradictions but should not change DETECTION logic |
| **Evidence grouping** | `_add_comparison_steps()` groups by event_type, then condition+horizon | ❌ Adding context as a grouping key changes comparison behavior |
| **Causal explanation** | None — engine does no causal analysis | ❌ Would require causal infrastructure |
| **Conclusion generation** | `_build_conclusion()` produces directional conclusion | ⚠️ Context could be INCLUDED in the conclusion description |
| **Explanation only** | Natural extension of `_format_condition()` pattern | ✅ Context is descriptive metadata — extension is architecturally consistent |

**Verdict: Explanation only.** Institutional context belongs in the explanation layer of reasoning — in the conclusion and comparison step texts — because:

- Explanations are the only reasoning output that is purely **descriptive** (no algorithmic consequence)
- `ReasoningContext` already carries institutional context, making it available at zero cost
- The `_format_condition()` pattern already handles arbitrary dicts generically — no `macro_regime` reference needed
- No logic changes are required — conclusions are rendered from existing template text

### 2. What should Institutional Context influence?

| Option | Assessment |
|--------|-----------|
| **Hypothesis generation** | ❌ No hypothesis infrastructure exists. Redesign required. |
| **Contradiction detection** | ❌ Detection logic (directional disagreement) is correct and stable. Context might explain WHY contradiction exists (different contexts) but should not change WHETHER a contradiction is detected — that would alter reasoning behavior. |
| **Evidence grouping** | ❌ Adding institutional_context as a grouping key would change which evidence is compared against which. This is a logic change that affects comparison output and potentially final conclusions. Violates "no redesign." |
| **Causal explanation** | ❌ No causal infrastructure exists. |
| **Conclusion generation** | ❌ The directional bias decision (positive, negative, neutral) should NOT be changed by institutional context. That's a decision logic change. |
| **Explanation only** | ✅ Institutional context should appear in step conclusion texts as a descriptive signal. This uses existing infrastructure (`_format_condition()`), is generic (any dict keys), and changes no logic. |

**Verdict: Explanation only** — institutional context should be rendered in step conclusions as a descriptive element, informing the user that reasoning occurred under a specific institutional context.

### 3. Ownership verification

| Component | File | Should change? |
|-----------|------|---------------|
| `ReasoningContext` | `context.py` | ✅ Already owns `institutional_context` (Sprint-004) — no field change needed |
| `ReasoningEngine` | `engine.py` | ⚠️ Should gain one new private method: `_format_institutional_context()` (pure, static, generic) |
| `ReasoningStep` | `step.py` | ❌ No change — `details` dict already accepts arbitrary keys |
| `ReasoningChain` | `chain.py` | ❌ No change — chain already carries `context` with `institutional_context` |
| `ReasoningRepository` | `repository.py` | ❌ No change — serializes whole chain including context |

**New method**: `_format_institutional_context(ctx: dict[str, str]) -> str` — a static method that formats institutional context as a human-readable string fragment. Identical pattern to `_format_condition()`.

### 4. Deterministic behavior

| Aspect | Assessment |
|--------|-----------|
| `_format_condition()` | Pure function — same dict → same string |
| Institutional context rendering | Would use same pattern → pure function |
| Chain ID | Currently omits institutional context. If context is added to explanation only, the chain ID should ideally include it for content-addressing correctness. But chain ID is a chain-level identifier, not an explanation. Adding context to chain ID would change chain IDs for existing queries — a backward compatibility concern that must be weighed. |
| Explanation text | Would differ when institutional context differs → correct by design (different context → different explanation) |

The determinism concern is limited to the chain ID gap. However, since institutional context does not influence logical conclusions (phase 5 behavior is unchanged), having different chain IDs for the same logical conclusion is acceptable — the chain ID identifies the reasoning chain, and different institutional contexts DO produce different reasoning chains (different explanation text).

### 5. Backward compatibility

| Scenario | Current behavior | With change | Regression? |
|----------|-----------------|-------------|-------------|
| Empty `institutional_context` | Conclusion has no context text | Conclusion has no context text (empty dict → no fragment added) | ❌ None |
| Non-empty `institutional_context` | Conclusion ignores context | Conclusion includes `" under regime=EXPANSION, vol=LOW"` | ❌ None — existing text is preserved, context is additive |
| Existing tests | Assert specific conclusion strings | May fail if they assert exact string content | ⚠️ Test assertions that check conclusion string equality would need updating — but these are text content tests, not behavioral tests |

The backward compatibility concern is limited to test assertions that match exact conclusion strings. All 60 existing reasoning tests that check structural properties (step count, step types, chain_id, confidence, evidence_count) would be unaffected. Only tests that match substrings of conclusion text with `in` would be safe; tests using `==` would need updating.

### 6. Explainability

Reasoning remains fully explainable because:

- All steps are preserved (evidence_review → comparison → aggregation → conclusion)
- Conclusion text becomes MORE informative (institutional context is visible)
- `ReasoningContext.institutional_context` is already part of the chain's provenance
- No new hidden state, weights, or heuristics are introduced
- The `_format_institutional_context()` method is a pure string formatter with no side effects

The change improves explainability by making institutional context visible in the reasoning output, closing the gap between "context was used in retrieval" (Sprint-005) and "context is visible in the reasoning chain" (this sprint).

---

## Recommendation

**APPROVE** — with the specific scope of **explanation only**.

### Architectural justification

Institutional context belongs in the reasoning chain's **explanation layer** — not in retrieval (done in Sprint-005), not in weighting (rejected in Sprint-006), and not in decision logic (future sprint). Specifically:

1. **`ReasoningContext.institutional_context` already exists** (Sprint-004). The field carries the data. The engine simply never reads it. This is dead weight that should be activated.

2. **The `_format_condition()` pattern proves the approach is correct.** It renders arbitrary dicts as human-readable text without referencing any specific key. `_format_institutional_context()` would follow the same pattern — generic, no `macro_regime` reference.

3. **Explanation is the only reasoning responsibility that is purely descriptive.** All other responsibilities (grouping, comparison, aggregation, conclusion) involve algorithmic decisions that should remain unchanged. Adding context to explanation text changes nothing about how reasoning works — it changes only what the user sees.

4. **No redesign is required.** The change is additive (add text to existing conclusion template) and uses existing methods (`_format_condition()` pattern). No new infrastructure, no new dependencies, no new heuristics.

5. **Determinism is preserved.** String formatting of a dict is a pure function.

6. **Backward compatibility is preserved for all behavioral tests.** Only exact-string-match tests on conclusion text would need updating, and those tests should include institutional context going forward.

7. **No double-counting.** The retriever uses institutional context for similarity scoring (Sprint-005). The reasoning engine uses it for explanation text (this sprint). These are orthogonal concerns — similarity and explanation share data but not purpose.

### Scope of implementation (for future execution)

- One new method: `Engine._format_institutional_context(ctx: dict[str, str]) -> str` — static, generic, pure
- One changed method: `Engine._build_conclusion()` — add institutional context to `context_desc`
- Optionally: `Engine._build_comparison()` — note when contradictory evidence spans different institutional contexts
- Optionally: `Engine._build_chain_id()` — include institutional context in chain ID for content-addressing correctness (requires analysis of downstream chain ID consumers)

---

## Summary

| Question | Answer |
|----------|--------|
| 1. Which responsibility owns Institutional Context? | Explanation layer — stream rendering in step conclusions |
| 2. Should context influence hypothesis generation? | ❌ No infrastructure exists |
| 2. Should context influence contradiction detection? | ❌ Would change detection logic |
| 2. Should context influence evidence grouping? | ❌ Would change comparison scope |
| 2. Should context influence causal explanation? | ❌ No infrastructure exists |
| 2. Should context influence conclusion generation? | ❌ Would change directional logic |
| **2. Should context influence explanation only?** | **✅ Yes — pure description, no logic change** |
| 3. Ownership correct? | ✅ ReasoningEngine owns `_format_institutional_context()`, ReasoningContext owns the data |
| 4. Deterministic? | ✅ Pure function of dict → string |
| 5. Backward compatible? | ✅ All behavioral tests pass; text tests may need minor updates |
| 6. Remains explainable? | ✅ Improves explainability — context is visible in reasoning output |
| Generic (no macro_regime)? | ✅ Uses `_format_condition()` pattern — any dict keys work |
