# Sprint-004: Schema Stability — KnowledgeRecord `institutional_context`

**Date:** 2026-07-25  
**Status:** Schema Review — No Implementation  

---

## Candidates

| # | Type | Current Precedent |
|---|------|-------------------|
| 1 | `dict[str, str]` | `KnowledgeRecord.condition` |
| 2 | `dict[str, Any]` | `KnowledgeRecord.metadata`, `ReasoningStep.details` |
| 3 | `Mapping[str, str]` | No precedent in knowledge dataclasses |
| 4 | Existing typed structure | Evaluate whether a reusable type already exists |

---

## Candidate 4: Existing Typed Structure

The codebase contains no reusable typed structure for "institutional context." The closest generic key-value types are:

| Type | Used On | Purpose |
|------|---------|---------|
| `dict[str, str]` | `KnowledgeRecord.condition`, `Evidence.condition`, `SituationQuery.condition`, `DecisionCondition.context` | Analytical conditions |
| `dict[str, Any]` | `KnowledgeRecord.metadata`, `Evidence.metadata`, `Provenance.metadata`, `ReasoningStep.details` | Unstructured extension bags |
| `tuple[str, ...]` | `LessonBuilderConfig.institutional_context`, `LessonSummaryConfig.condition_columns` | Configuration column names |

None of these is a dedicated "context value structure." There is no `ContextMap`, `InstitutionalContext`, or equivalent dataclass. The codebase's pattern for named key-value data is `dict[str, str]` when values are homogeneous (always strings). 

**Verdict:** No existing typed structure fits. Option 4 is a `dict[str, str]` with a different name, which adds indirection without value.

---

## Evaluation

### Criterion 1: Backward Compatibility

| Type | Assessment |
|------|------------|
| `dict[str, str]` | **Perfect.** Default `field(default_factory=dict)`. `__post_init__` calls `freeze_dict()`. `from_dict()` uses `data.get("institutional_context", {})`. Existing constructors without the field compile. Existing deserialized JSON without the key loads. |
| `dict[str, Any]` | **Perfect.** Identical backward compatibility characteristics. |
| `Mapping[str, str]` | **Acceptable.** `field(default_factory=dict)` returns a `dict` subclass. `from_dict()` receives `dict`. Same compatibility, but type signature misrepresents the concrete storage (is actually `FrozenDict` which is `dict`). |

### Criterion 2: Future Extensibility

| Type | Assessment |
|------|------------|
| `dict[str, str]` | **Constrained to strings.** If a future context type needs numeric values (e.g., `volatility_index: 25.5`) or booleans (`is_liquidity_crisis: true`), they must be stringified. |
| `dict[str, Any]` | **Maximum flexibility.** Any value type. No migration needed for future value types. |
| `Mapping[str, str]` | Same constraint as `dict[str, str]`. |

This is the central trade-off. Widening to `Any` now avoids a future schema migration, but at the cost of losing type safety and semantic clarity today.

### Criterion 3: Serialization Stability

| Type | Assessment |
|------|------------|
| `dict[str, str]` | **Stable.** All values are JSON-native strings. `json.dumps()` handles them natively. `FrozenDict` is a `dict` subclass. No coercion surprises. |
| `dict[str, Any]` | **Conditionally stable.** `Any` allows non-serializable types (datetime, numpy floats, custom objects). The frozen dataclass itself cannot enforce serializability — that becomes the responsibility of whatever populates the field. In practice, the LessonSummaryAggregator serializes via `json.dumps`, so a runtime error would be caught early. But the type system provides no guard. |
| `Mapping[str, str]` | **Stable.** Same as `dict[str, str]` — values are JSON-native strings. |

### Criterion 4: Type Safety

| Type | Assessment |
|------|------------|
| `dict[str, str]` | **Strong.** Every consumer knows `context["macro_regime"]` is a `str`. No `isinstance` checks needed. Type checker validates all assignments. |
| `dict[str, Any]` | **Weak.** Every consumer must defensively handle unknown types. A `get("volatility_index")` could return `str`, `float`, `int`, or `None`. Adds `isinstance` branches to every downstream component. |
| `Mapping[str, str]` | **Strong.** Same as `dict[str, str]`. |

### Criterion 5: Deterministic Behavior

| Type | Assessment |
|------|------------|
| `dict[str, str]` | **Deterministic.** `freeze_dict()` makes it immutable. String comparison is ordering-independent for equality checks. Iteration order is insertion-order (Python 3.7+), which is deterministic given a frozen dict. |
| `dict[str, Any]` | **Conditionally deterministic.** Depends on whether value types are themselves deterministic and hashable. If all values are simple types (str, int, float, bool), behavior is identical to `dict[str, str]`. If complex nested types are allowed, determinism must be enforced by the caller. |
| `Mapping[str, str]` | **Deterministic.** Same as `dict[str, str]`. |

### Criterion 6: Versioning Compatibility

| Type | Assessment |
|------|------------|
| `dict[str, str]` | **Versioning-ready.** Future schema evolution follows existing patterns: (a) new field with new name, e.g., `institutional_context_v2: dict[str, Any]`, or (b) `Provenance.entity_version` bump + migration function. The codebase already uses `entity_version` for tracking KnowledgeRecord versions through calibration. |
| `dict[str, Any]` | **No migration needed for value types.** But "no migration needed" is not the same as "versioned." The schema contract says nothing about what values to expect. |
| `Mapping[str, str]` | Same as `dict[str, str]`. |

---

## Analysis: Future Value Types

The argument for `dict[str, Any]` rests on this question: **will institutional context ever need non-string values?**

Examining the concrete and proposed context types:

| Context | Proposed Values | Value Type |
|---------|----------------|------------|
| `macro_regime` | EXPANSION, CONTRACTION, RECOVERY, LATE_CYCLE | Categorical label |
| `liquidity_regime` | HIGH, NORMAL, STRESSED | Categorical label |
| `volatility_regime` | LOW, MODERATE, HIGH, EXTREME | Categorical label |
| `geopolitical_state` | STABLE, ELEVATED_TENSION, CONFLICT | Categorical label |

All four are **categorical classifications**. They are labels assigned by classifiers (Markov-switching model, threshold detectors, rule-based systems, NLP classifiers). In every case the output is a string label.

If a future context needs structured data (e.g., a probability distribution across regimes), that data belongs in one of:

1. **The extractor output** — the extractor produces the full distribution; the KnowledgeRecord stores only the majority label
2. **The lesson source data** — per-event distributions; aggregation reduces to majority
3. **A separate field** — a new `institutional_context_distribution: dict[str, dict[str, float]]` added when the requirement materializes

The KnowledgeRecord is a **summary**, not a raw data store. Its context field should summarize the context distribution across aggregated lessons. A single categorical label per dimension is the correct level of abstraction. If downstream components need the full distribution, they should consult the lesson source data.

This is consistent with how `condition` works: the condition values are categorical labels, not raw numbers. The underlying lesson data has the detail.

---

## Recommendation

### `dict[str, str]`

| Criterion | Score |
|-----------|-------|
| Backward compatibility | ★★★★★ |
| Future extensibility | ★★★★☆ |
| Serialization stability | ★★★★★ |
| Type safety | ★★★★★ |
| Deterministic behavior | ★★★★★ |
| Versioning compatibility | ★★★★★ |

### Why not `dict[str, Any]`

> **Don't widen the type today for a requirement that does not exist and is architecturally inconsistent with the abstraction.**

`Any` is the wrong choice because:
1. Every current and planned context type produces **string categorical values**.
2. Non-string values indicate a different abstraction (probability distributions, numerical indices) that should be a separate field.
3. `Any` pushes type-uncertainty cost to every consumer (checks, coercion, error handling).
4. The codebase already uses `dict[str, str]` for `condition` — the parallel structure reinforces the architectural intent.

### Why not `Mapping[str, str]`

`Mapping` is an abstract interface. The codebase consistently uses concrete `dict` in frozen dataclass field signatures:
- `KnowledgeRecord.condition: dict[str, str]`
- `KnowledgeRecord.metadata: dict[str, Any]`
- `Evidence.condition: dict[str, str]`
- `ReasoningStep.details: dict[str, Any]`
- `Provenance.metadata: dict[str, Any]`

`Mapping` is not JSON-serializable and does not match the concrete storage type (`FrozenDict`, which is a `dict` subclass). The field signature should describe the serialized form.

### How future extensions should be handled

If a future institutional context type genuinely requires non-string values (e.g., a regime confidence score), the correct approach is:

1. **Ship `dict[str, str]` as v1** — all current and planned context types are categorical strings
2. **When the need arises, create a v2 field** — either by:
   - Adding `institutional_context_v2: dict[str, Any] | None = None` alongside the v1 field
   - Or defining a new `InstitutionalContext` dataclass with typed fields
3. **Use `Provenance.entity_version`** to track schema version of the KnowledgeRecord
4. **Write a migration function** to convert v1 → v2 when upgrading

This is consistent with the codebase's existing versioning strategy: `Provenance.entity_version` (bumped by `KnowledgeCalibrator` on calibration), `LineageRegistry`, and content-derived IDs all support versioned evolution.

---

## Final Recommendation

```python
institutional_context: dict[str, str] = field(default_factory=dict)
```
