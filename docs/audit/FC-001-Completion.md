# FC-001: Semantic Condition Matching Fix — Completion

**Date:** 2026-07-25  
**Status:** Complete  
**Classification:** Foundation Correction (not a Sprint)  

---

## Root Cause

`HistoricalSituationRetriever._jaccard_similarity()` at `src/knowledge/reasoning/retrieval.py:159` computed Jaccard similarity on **condition key sets** instead of **condition key-value pair sets**:

```python
# Bug — keys only, values ignored
keys_a = set(a.keys())    # → {"cpi_pressure"}
keys_b = set(b.keys())
```

This caused semantically opposite conditions to receive a perfect similarity score:

```python
_jaccard_similarity({"cpi_pressure": "high"}, {"cpi_pressure": "low"})
# Bug: 1.0  (identical key sets, values ignored)
# Fix: 0.0  (no matching (key, value) pairs)
```

---

## Semantic Impact

The defect affected **only the broadened retrieval path** in `HistoricalSituationRetriever.retrieve()`. When exact matches fell below `broaden_min_results` (default: 3), the retriever broadened to `by_event_type()` — fetching ALL evidence for the event type regardless of condition value. In this broadened path, evidence with opposite condition values (e.g., `cpi_pressure=low` for a query of `cpi_pressure=high`) received an inflated condition similarity of 1.0, which propagated through the 5-factor geometric mean and could push irrelevant evidence above `min_similarity` (0.3).

The exact-match path (`EvidenceQuery.matching()`) was **unaffected** because it already uses correct key-value equality filtering, so candidates always match on both keys and values before reaching `_jaccard_similarity`.

---

## Files Modified

| File | Change | Lines |
|------|--------|-------|
| `src/knowledge/reasoning/retrieval.py` | `set(a.keys())` → `set(a.items())` | 2 |
| `tests/test_retrieval.py` | Added 2 regression tests | 14 |

---

## Tests Added

| Test | What It Verifies |
|------|------------------|
| `test_same_keys_opposite_values` | `{"cpi_pressure": "high"}`, `{"cpi_pressure": "low"}` → `0.0` |
| `test_same_keys_opposite_values_lower_than_identical` | Opposite < Identical similarity |

---

## Tests Passed

| Test Suite | Tests | Result |
|------------|-------|--------|
| `test_retrieval.py` | 60 (58 existing + 2 new) | All PASS |
| `test_reasoning_engine.py` | 33 | All PASS |
| `test_evidence_weighting.py` | 37 | All PASS |
| `test_evidence_engine.py` | 42 | All PASS |
| `test_lesson_builder.py` | 10 | All PASS |
| `test_macro_event_standard.py` | 15 | All PASS |
| **Total** | **197** | **All PASS** |

---

## Architectural Impact

- **Preserved existing Jaccard algorithm** — formula, guards, return type, deterministic behavior unchanged
- **Preserved all 58 existing tests** — zero modifications to existing assertions
- **No new dependencies** — uses only `set()` on `dict.items()`
- **No new classes, methods, or subsystems**

The fix is a one-line correction to an existing static method. It does not change the retrieval interface, the evidence pipeline, the graph builder, or any downstream component.

---

## Institutional Impact

This fix is a **prerequisite** for Sprint-004 (Institutional Context in KnowledgeRecord) and Sprint-005 (Institutional Context Aware Reasoning). Without it:

- The condition similarity dimension would conflate opposite condition values
- An institutional context similarity dimension (planned for HistoricalSituationRetriever) would operate on a contaminated baseline
- Evidence with opposite conditions would receive inflated multi-factor similarity scores, masking the influence of institutional context

With the fix, condition similarity correctly reflects key-value matching. Institutional context can be added as an independent 6th dimension without confounding effects.
