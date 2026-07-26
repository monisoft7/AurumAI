# Sprint-005: Semantic Condition Matching — Readiness

**Date:** 2026-07-25  
**Status:** Readiness Analysis — No Implementation  

---

## Problem

`HistoricalSituationRetriever._jaccard_similarity()` computes Jaccard similarity on **condition keys only**, ignoring values. This causes semantically opposite conditions to be treated as identical:

```python
# Current behavior — BUG
_jaccard_similarity({"cpi_pressure": "high"}, {"cpi_pressure": "low"})
# → 1.0  (keys intersect perfectly, values ignored)
```

The condition `{"cpi_pressure": "high"}` and `{"cpi_pressure": "low"}` represent opposite market conditions, yet the retriever gives them a perfect similarity score. Every evidence item with any `cpi_pressure` value receives full condition similarity when the query has any `cpi_pressure` value.

---

## Trace: Where the Bug Manifests

The retrieval flow has two paths:

### Exact-match path (line 76–80)
```
evidence_query.matching(condition=query.condition)
    → exact key-value equality filter
    → all candidates have identical condition dicts
    → _jaccard_similarity() always receives identical dicts
    → result is always 1.0, unaffected by the bug
```

### Broadened path (line 84–91)
When exact matches < `broaden_min_results` (default: 3):
```
evidence_query.by_event_type(query.event_type)
    → ALL evidence for that event type, regardless of condition value
    → candidates include DIFFERENT condition values
    → _jaccard_similarity() compares query.condition vs evidence.condition
    → BUG: opposite values receive similarity 1.0
```

**Impact is limited to the broadened fallback path**, where the bug inflates similarity for evidence with mismatching condition values. These inflated scores can push irrelevant evidence above `min_similarity` (default: 0.3), causing it to appear in the top-k matches.

---

## Analysis

### 1. Intended Matching Semantics

Three distinct mechanisms exist in the codebase:

| Location | Semantics | Correct? |
|----------|-----------|----------|
| `EvidenceQuery.matching()` | **Key-value exact equality** | ✓ Correct |
| `EvidenceQuery.by_condition()` | **Key-value exact equality** | ✓ Correct |
| `GraphBuilder._condition_key()` | **Key-value tuple key** (for `RELATION_SAME_CONDITION` edges) | ✓ Correct |
| `HistoricalSituationRetriever._jaccard_similarity()` | **Key-only Jaccard** | ✗ Bug |

The intended semantics for similarity-based retrieval are **key-value matching**. The function was designed to measure condition similarity between a query and an evidence item; ignoring values was an implementation error. The Jaccard formula is correct in intent but operates on the wrong elements (keys instead of key-value pairs).

The correct semantics are: **two conditions are similar to the degree that their key-value pairs overlap.** This is a standard key-value Jaccard similarity.

### 2. Architectural Owner

| Component | File | Responsibility |
|-----------|------|----------------|
| `HistoricalSituationRetriever._jaccard_similarity()` | `src/knowledge/reasoning/retrieval.py:153` | Measure condition similarity between query and candidate evidence |

This is a `@staticmethod` on the retriever. It is called from `_compute_similarities()` at line 135.

No other component uses this method. No other similarity computation in the codebase has this bug.

### 3. Historical Retrieval Semantics Change

**Yes, the fix changes retrieval semantics in the broadened path.** This is intentional:

| Scenario | Before (key-only Jaccard) | After (key-value Jaccard) |
|----------|---------------------------|---------------------------|
| Query: `cpi_pressure=high`, Evidence: `cpi_pressure=high` | `cond_sim = 1.0` | `cond_sim = 1.0` (unchanged) |
| Query: `cpi_pressure=high`, Evidence: `cpi_pressure=low` | `cond_sim = 1.0` (WRONG) | `cond_sim = 0.0` (CORRECT) |
| Query: `cpi_pressure=high`, Evidence: `(no condition)` | `cond_sim = 0.5` (neutral) | `cond_sim = 0.5` (unchanged) |

The fix causes evidence with opposite condition values to receive a condition similarity of 0.0 in the broadened path. This can cause their overall geometric-mean score to fall below `min_similarity` (0.3), removing them from the top-k matches. Evidence with matching condition values is unaffected.

In the exact-match path, all candidates already have identical condition values, so behavior is completely unchanged.

### 4. Backward Compatibility

**All existing tests pass without modification.** Verification against `tests/test_retrieval.py`:

| Test Case | Inputs | Current Result | Key-Value Result | Change? |
|-----------|--------|----------------|------------------|---------|
| `test_identical_keys` | `{"a":"1","b":"2"}`, `{"a":"1","b":"2"}` | 1.0 | 1.0 | No |
| `test_partial_overlap` | `{"a":"1","b":"2","c":"3"}`, `{"a":"1","b":"2"}` | 2/3 | 2/3 | No |
| `test_no_overlap` | `{"a":"1"}`, `{"b":"2"}` | 0.0 | 0.0 | No |
| `test_both_empty` | `{}`, `{}` | 0.5 | 0.5 | No |
| `test_query_empty` | `{}`, `{"a":"1"}` | 0.5 | 0.5 | No |
| `test_candidate_empty` | `{"a":"1"}`, `{}` | 0.5 | 0.5 | No |

All 6 existing Jaccard tests pass because they use identical values for matching keys. No existing test exercises the "same keys, different values" case because that's the bug that was never caught.

**Integration compatibility:**
- Exact-match retrieval: zero change (candidates already pass key-value filter)
- Broadened retrieval: fewer irrelevant matches, but still protected by `broaden_on_empty` fallback
- All 613 lines of existing tests remain unchanged

**One new test should be added** to document the fix:
```
test_same_keys_different_values → 0.0
```

### 5. Interaction with Institutional Context

**The fix is a prerequisite for Sprint-004 (Institutional Context in KnowledgeRecord).**

Without this fix, condition similarity would conflate opposite condition values. If institutional context is added as a 6th similarity dimension in `HistoricalSituationRetriever`, the condition dimension's inflated scores would contaminate the multi-factor geometric mean — evidence with opposite conditions would get high condition similarity and potentially high overall similarity, masking the influence of the context dimension.

With the fix, condition similarity correctly reflects value matching, and the institutional context dimension operates on a clean baseline.

### 6. Interaction with Knowledge Evolution

**None.** `KnowledgeCalibrator` produces new KnowledgeRecords with updated confidence/provenance but identical condition values. Condition matching operates on condition dicts, which are stable across calibration. The fix applies equally to calibrated and uncalibrated evidence.

---

## Smallest Deterministic Correction

**One line change** in `_jaccard_similarity`:

```python
# Before (line 159)
keys_a = set(a.keys())
keys_b = set(b.keys())

# After
keys_a = set(a.items())
keys_b = set(b.items())
```

This changes the Jaccard basis from key sets to key-value pair sets. The formula, guards, and return type remain identical.

### Why this is correct

| Property | Assessment |
|----------|------------|
| Deterministic | Pure function of inputs. Same inputs → same outputs. |
| Minimal | Single line. No new methods. No new classes. |
| Backward compatible | All existing tests pass. Identical dicts → 1.0. Different keys → < 1.0. Only "same keys, different values" changes (0.0 vs 1.0). |
| No new behavior | Same Jaccard formula, applied to the correct elements. |
| No new dependencies | Uses only `set()` on existing `dict.items()`. |

### What this does NOT do

- Does not change the Jaccard formula
- Does not add new similarity dimensions
- Does not change `EvidenceQuery.matching()` (already correct)
- Does not change `GraphBuilder` (already correct)
- Does not change `EvidenceWeighter` (not involved in condition matching)
- Does not introduce weights, thresholds, or heuristics
- Does not redesign retrieval

---

## Pre-Implementation Checklist

| Item | Status |
|------|--------|
| The exact-match path is unaffected | Verified |
| All existing `_jaccard_similarity` tests pass unchanged | Verified |
| Only one file changes | `src/knowledge/reasoning/retrieval.py` |
| Only one line changes | `set(a.keys())` → `set(a.items())` |
| A new test documents the fix | `test_same_keys_different_values → 0.0` |
| Institutional Context (Sprint-004) is not blocked | Prerequisite satisfied |
| No Frozen Decision is violated | ✓ |
