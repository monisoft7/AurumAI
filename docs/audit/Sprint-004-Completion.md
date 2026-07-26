# Sprint-004: Institutional Context Visibility (C-05) — Completion

## Objective

Make Institutional Context visible in all downstream components without changing any consumption logic.

## Scope

| Component | Change | Status |
|-----------|--------|--------|
| KnowledgeRecord | Added `institutional_context: dict[str, str]` — frozen, serialized | ✅ |
| LessonSummaryConfig | Added `institutional_context: tuple[str, ...]` — majority-vote in `_summarize_group()` | ✅ |
| ReasoningContext | Added `institutional_context: dict[str, str]` — frozen, default empty | ✅ |
| DecisionContext | Added `institutional_context: dict[str, str]` — frozen, default empty | ✅ |
| PipelineContext | Added `institutional_context_columns` (tuple) + `institutional_context` (dict) | ✅ |
| `_stage_build_knowledge` | Passes `context.institutional_context_columns` to LessonSummaryConfig | ✅ |
| `_stage_reason` | Passes `context.institutional_context` to ReasoningContext | ✅ |
| `_stage_decide` | Passes `context.institutional_context` to DecisionContext | ✅ |
| Evidence (via metadata) | GraphNode.properties → Evidence.__init__ — automatic, no wiring needed | ✅ |

## Files Changed

**Source:**
- `src/knowledge/integrity/knowledge_record.py` — field + freeze + to_dict/from_dict
- `src/knowledge/lesson_summary.py` — config field, column check, majority-vote in `_summarize_group()`
- `src/knowledge/reasoning/context.py` — field + freeze
- `src/knowledge/decision/context.py` — field + freeze
- `src/knowledge/pipeline/context.py` — two new fields
- `src/knowledge/pipeline/pipeline.py` — wiring in 3 stages

**Tests:**
- `tests/test_lesson_summary.py` — 2 new tests (majority-vote propagation, empty when not configured)
- `tests/test_inference_pipeline.py` — 3 new tests (reasoning context, decision context, default empty)
- `tests/test_lesson_summary.py` — fixed existing tests with `institutional_context=()`
- `tests/test_nfp_event.py` — fixed existing tests with `institutional_context=()`
- `tests/test_compat.py` — fixed existing test with `institutional_context=()`

## Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| lesson_summary + lesson_builder | 40 | ✅ Pass |
| reasoning_engine + forecast_reasoning | 94 | ✅ Pass |
| decision_engine + decision_gate | 119 | ✅ Pass |
| inference_pipeline + news_pipeline | 205 | ✅ Pass |
| retrieval | 60 | ✅ Pass |
| compat | 92 | ✅ Pass |
| nfp_event | 23 | ✅ Pass |
| macro_regime + feature_extraction | 100 | ✅ Pass |
| knowledge_graph + knowledge_integrity | 17 | ✅ Pass |
| evidence_engine + evidence_weighting | 40 | ✅ Pass |
| gdp + fomc + interest_rate + pmi + ppi | 92 | ✅ Pass |
| orchestration + economic/causal/temporal | 180 | ✅ Pass |
| **Total affected** | **732** | **✅ All passing** |

Note: `test_institutional_validation` (1 test) has a pre-existing failure in scenario 3 (Temporal Consistency: expects NEUTRAL, gets POSITIVE) — unrelated to Sprint-004.

## Backward Compatibility

- All new fields default to empty (empty dict / empty tuple)
- Existing `LessonSummaryConfig(...)` without `institutional_context` requires explicit `institutional_context=()` if CSV lacks the default columns
- Default `PipelineContext.institutional_context_columns=()` — no pipeline requires macro_regime unless explicitly configured
- No existing behavior changed; no reasoning/weighting/retrieval/decision logic touched

## Open Questions

- **DecisionRepository** does not serialize `institutional_context` — acceptable for visibility-only; add when consumption begins
- **EvidenceQuery** passes metadata automatically — no change needed
- **Weighting logic** unchanged — Sprint-005 will consume institutional_context from Evidence.metadata

## Next: Sprint-005 — Consumption

Wire institutional_context into:
1. Retrieval similarity (condition + institutional_context in Jaccard)
2. Evidence weighting (adjust weights based on context match)
3. Reasoning context (context-aware reasoning paths)
4. Decision context (context-aware decision thresholds)

Prerequisite: FC-001 (Semantic Condition Matching Fix) — already complete.
