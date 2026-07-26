# Git Commit Plan

**Date:** 2026-07-25
**Branch:** `main` (27 modified, 25 untracked)
**Base:** `55001ea` — Institutional Knowledge Evolution

---

## 1. File Classification

### Source Code (14 files)

| File | Change | Action |
|------|--------|--------|
| `src/knowledge/builders/lesson_builder.py` | Modified — `LessonBuilderConfig.institutional_context`, `_add_institutional_context()` | Commit |
| `src/knowledge/decision/context.py` | Modified — `institutional_context` in `DecisionContext` | Commit |
| `src/knowledge/features/engine.py` | Modified — `register_global()`, `clear_global()`, multi-extractor chaining | Commit |
| `src/knowledge/integrity/knowledge_record.py` | Modified — `institutional_context` in `KnowledgeRecord` | Commit |
| `src/knowledge/lesson_summary.py` | Modified — `institutional_context` in `LessonSummaryConfig` | Commit |
| `src/knowledge/orchestration/context.py` | Modified — `institutional_context` in `OrchestrationContext` | Commit |
| `src/knowledge/orchestration/engine.py` | Modified — wired context to `SituationQuery` | Commit |
| `src/knowledge/pipeline/context.py` | Modified — `institutional_context` in `PipelineContext` | Commit |
| `src/knowledge/pipeline/pipeline.py` | Modified — wired through `_stage_build_knowledge`, `_stage_reason`, `_stage_decide` | Commit |
| `src/knowledge/reasoning/context.py` | Modified — `institutional_context` in `ReasoningContext` | Commit |
| `src/knowledge/reasoning/retrieval.py` | Modified — FC-001 Jaccard fix + Sprint-005 context-aware retrieval | Commit |
| `src/knowledge/regime/__init__.py` | Modified — empty → exports `CompositeScoreBuilder`, `MacroRegimeDetector` | Commit |
| `src/knowledge/regime/composite_score.py` | Untracked — new `CompositeScoreBuilder` | Commit |
| `src/orchestration/stages.py` | Modified — wired institutional_context through pipeline stages | Commit |

### Tests (9 files)

| File | Change | Action |
|------|--------|--------|
| `tests/conftest.py` | Modified — shared fixtures | Commit |
| `tests/test_compat.py` | Modified — backward compat assertion | Commit |
| `tests/test_composite_score.py` | Untracked — 6 tests for `CompositeScoreBuilder` | Commit |
| `tests/test_feature_extraction.py` | Modified — 186 lines added (global extractors) | Commit |
| `tests/test_inference_pipeline.py` | Modified — 91 lines added | Commit |
| `tests/test_lesson_builder.py` | Modified — 485 lines added (institutional context) | Commit |
| `tests/test_lesson_summary.py` | Modified — 99 lines added | Commit |
| `tests/test_nfp_event.py` | Modified — 1 line | Commit |
| `tests/test_retrieval.py` | Modified — 126 lines added (FC-001 regression + context-aware) | Commit |

### Documentation (25 files)

| File | Change | Action |
|------|--------|--------|
| `PROJECT_STATUS.md` | Modified — sprint completion table, next section | Commit |
| `Sprint-001-Readiness.md` | Untracked — at root level, inconsistent with `docs/audit/` placement | Delete (wrong location) |
| `docs/CER-006-runtime-architecture-trace.md` | Untracked | Commit |
| `docs/adr/ADR-002-macro-regime-activation.md` | Untracked | Commit |
| `docs/adr/ADR-003-institutional-context-propagation.md` | Untracked | Commit |
| `docs/architecture/PROJECT_BLUEPRINT.md` | Untracked | Commit |
| `docs/audit/CER-007-capability-activation-matrix.md` | Untracked | Commit |
| `docs/audit/CER-007A-design-review.md` | Untracked | Commit |
| `docs/audit/CER-008-context-aware-retrieval.md` | Untracked | Commit |
| `docs/audit/FC-001-Completion.md` | Untracked | Commit |
| `docs/audit/Sprint-002-Completion.md` | Untracked | Commit |
| `docs/audit/Sprint-002-Consumption-Verification.md` | Untracked | Commit |
| `docs/audit/Sprint-002-Ownership-Verification.md` | Untracked | Commit |
| `docs/audit/Sprint-002-Plan.md` | Untracked | Commit |
| `docs/audit/Sprint-003-Completion.md` | Untracked | Commit |
| `docs/audit/Sprint-004-Completion.md` | Untracked | Commit |
| `docs/audit/Sprint-004-KnowledgeRecord-Review.md` | Untracked | Commit |
| `docs/audit/Sprint-004-Readiness.md` | Untracked | Commit |
| `docs/audit/Sprint-004-Schema-Stability.md` | Untracked | Commit |
| `docs/audit/Sprint-005-Completion.md` | Untracked | Commit |
| `docs/audit/Sprint-005-Plan.md` | Untracked | Commit |
| `docs/audit/Sprint-005-Readiness.md` | Untracked | Commit |
| `docs/audit/Sprint-006-Readiness.md` | Untracked | Commit |
| `docs/audit/Sprint-007-Readiness.md` | Untracked | Commit |
| `docs/audit/Validation-001-Context-Aware-Retrieval.md` | Untracked | Commit |

### Generated Data (2 files)

| File | Change | Action |
|------|--------|--------|
| `data/economic/output/knowledge.json` | Modified — stale (does not reflect current source) | Regenerate then commit |
| `data/economic/output/lessons.csv` | Modified — stale (does not reflect current source) | Regenerate then commit |

### Experimental Output (3 files)

| File | Change | Action |
|------|--------|--------|
| `data/experiments/EXP-002-Evidence-Isolation/artifacts/knowledge.json` | Modified — transient experiment artifact | Ignore |
| `data/experiments/EXP-002-Evidence-Isolation/artifacts/lessons.csv` | Modified — transient experiment artifact | Ignore |
| `data/experiments/EXP-002-Evidence-Isolation/results.json` | Modified — only `total_elapsed_seconds` changed (0.565 → 0.241, runtime noise) | Ignore |

### Temporary / Should not be committed (1 file)

| File | Issue | Action |
|------|-------|--------|
| `Sprint-001-Readiness.md` | At root instead of `docs/audit/` (inconsistent with all other sprint docs) | Delete (or move to `docs/audit/`) |

---

## 2. Action Summary

| Action | Count | Files |
|--------|-------|-------|
| **Commit** | 46 | All source code, all tests, all docs, PROJECT_STATUS.md |
| **Ignore** | 3 | `data/experiments/EXP-002-Evidence-Isolation/*` |
| **Regenerate** | 2 | `data/economic/output/knowledge.json`, `lessons.csv` |
| **Delete** | 1 | `Sprint-001-Readiness.md` (move to `docs/audit/` if desired) |

---

## 3. Pre-Commit Checklist

Before committing:

1. [ ] **Delete** `Sprint-001-Readiness.md` (or move to `docs/audit/`)
2. [ ] **Regenerate** `data/economic/output/` — run pipeline to produce fresh knowledge.json and lessons.csv
3. [ ] **Add** `data/experiments/EXP-002-Evidence-Isolation/` to `.gitignore` (or `git update-index --assume-unchanged`)
4. [ ] **Verify** all tests pass (`pytest tests/ -x`)
5. [ ] **Verify** the working tree is clean after the final commit

---

## 4. Recommended Commits

### Minimum: 6 commits

The changes naturally split into 5 logical units (FC-001 + 4 sprints) plus a final cleanup commit. Each commits only files from that unit.

| # | Commit | Scope | Files |
|---|--------|-------|-------|
| **1** | `fix: FC-001 semantic condition matching (Jaccard key→items)` | FC-001 | `src/knowledge/reasoning/retrieval.py` (Jaccard line), `tests/test_retrieval.py` (2 regression tests), `docs/audit/FC-001-Completion.md` |
| **2** | `feat: Sprint-002 MacroRegimeDetector activation` | C-03 | `src/knowledge/regime/` (composite_score.py, __init__.py), `src/knowledge/features/engine.py`, `tests/test_composite_score.py`, `tests/test_feature_extraction.py`, `tests/conftest.py`, `docs/audit/Sprint-002-*`, `docs/adr/ADR-002-macro-regime-activation.md` |
| **3** | `feat: Sprint-003 institutional context propagation` | C-04 | `src/knowledge/builders/lesson_builder.py`, `tests/test_lesson_builder.py`, `docs/audit/Sprint-003-Completion.md`, `docs/adr/ADR-003-institutional-context-propagation.md` |
| **4** | `feat: Sprint-004 institutional context visibility` | C-05 | `src/knowledge/integrity/knowledge_record.py`, `src/knowledge/lesson_summary.py`, `src/knowledge/reasoning/context.py`, `src/knowledge/decision/context.py`, `src/knowledge/pipeline/context.py`, `src/knowledge/pipeline/pipeline.py`, `src/orchestration/stages.py`, `tests/test_inference_pipeline.py`, `tests/test_lesson_summary.py`, `tests/test_compat.py`, `tests/test_nfp_event.py`, `docs/audit/Sprint-004-*` |
| **5** | `feat: Sprint-005 context-aware evidence retrieval` | C-06 | `src/knowledge/reasoning/retrieval.py` (context-aware additions), `src/knowledge/orchestration/context.py`, `src/knowledge/orchestration/engine.py`, `tests/test_retrieval.py` (context-aware tests), `docs/audit/Sprint-005-*`, `docs/audit/CER-008-*`, `docs/audit/Validation-001-*`, `docs/CER-006-*`, `docs/architecture/PROJECT_BLUEPRINT.md`, `docs/audit/CER-007*.md` |
| **6** | `chore: update status and regenerate data` | Finalize | `PROJECT_STATUS.md`, `data/economic/output/knowledge.json`, `data/economic/output/lessons.csv`, `docs/audit/Sprint-006-Readiness.md`, `docs/audit/Sprint-007-Readiness.md` |

### Ordering constraint

`retrieval.py` is modified in both commit 1 (FC-001: Jaccard fix, 1 line) and commit 5 (Sprint-005: context-aware additions, new methods). These touch different methods and are safe to commit in order — commit 1 applies the Jaccard change, then commit 5 applies the context-aware additions on top without conflict.

### Optimal alternative: 2 commits

If each sprint had been committed incrementally during development, we would have 5+ commits. The most practical restoration path for this working tree is:

| # | Commit | Files |
|---|--------|-------|
| **A** | `feat: institutional context infrastructure (C-03–C-06 + FC-001)` | All source + test files (no conflict when applied together) |
| **B** | `docs: sprint audit documents and status update` | All docs + PROJECT_STATUS.md + regenerated data |

This avoids the ordering constraint in `retrieval.py` entirely (both changes apply in one atomic commit) and is the **true minimum** for a consistent commit history.

### Recommended: 2 commits

Merge all source + test changes into one cohesive feature commit, and all docs + data into a supporting commit. The 5-sprint sequence is a development narrative captured in the docs; the git history should record the final state.

```
A) feat: institutional context infrastructure (FC-001, C-03–C-06)
   - 14 source files, 9 test files
   - Jaccard fix, MacroRegimeDetector, context propagation, visibility, retrieval

B) docs: sprint documentation, status update, and regenerated data
   - 24 documentation files, PROJECT_STATUS.md, 2 regenerated data files
   - Sprint readiness/completion reports, ADRs, validation docs, CER docs
```
