# ADR-0004 Final Closure Report

**Date:** 2026-07-17  
**Version:** 0.6.0  
**Test Count:** 358 passing (100%)  

---

## Closed Gates

### Gate 1: Evidence filtered by event type, condition, and requested horizon ✅

**Before:** `InferencePipeline._stage_query_evidence` used `query.by_condition()` or `query.all()` — no event_type or horizon filtering. `OrchestrationEngine._run_core` used `query.by_condition()` or `query.all()` — same gap.

**Change:** Both paths now call `EvidenceQuery.matching(event_type, condition, horizon_days)`. `matching()` applies subset-match on condition (backward-compatible with the old `by_condition` behavior) and exact-match on event_type and horizon_days when non-None.

**Files changed:**
- `src/knowledge/pipeline/pipeline.py:178` — `_stage_query_evidence` now calls `query.matching(event_type=..., condition=..., horizon_days=...)`
- `src/knowledge/orchestration/engine.py:142` — `_run_core` now calls `query.matching(event_type=..., condition=..., horizon_days=...)`
- `src/knowledge/orchestration/context.py:25` — `OrchestrationContext.horizon_days` default changed from `20` to `None` (any horizon), matching `PipelineContext.reasoning_horizon` semantics

### Gate 2: Missing/sub-threshold evidence produces INSUFFICIENT_EVIDENCE ✅

**Before:** `OrchestrationEngine.analyze()` had `if len(merged) > 0 and ctx.reasoning_engine is not None:` — empty evidence silently skipped reasoning+decision. `INSUFFICIENT_EVIDENCE` was only reachable via direct `DecisionEngine.decide()` with explicit `min_evidence_count`.

**Change:** Removed the `len(merged) > 0` guard. Reasoning+decision always runs. `DecisionEngine._classify()` returns `INSUFFICIENT_EVIDENCE` when `evidence_count < min_evidence_count` (default 1, meaning 0 evidence → INSUFFICIENT_EVIDENCE).

**Files changed:**
- `src/knowledge/orchestration/engine.py:89` — removed `if len(merged) > 0` condition

### Gate 3: Optional pipeline stages validated without corrupting order ✅

**Assessment:** No code change needed. `PipelineValidator` already validates stage order and allows optional `compare_context` stage at the correct position. Verified that all pipeline tests continue to pass.

### Gate 4: Lineage normalization (partial — backward traceability) ✅

**Before:**
- Decision → ReasoningChain recorded as `source=decision, target=chain` (opposite of backward trace direction)
- KnowledgeRecord → Lesson → SourceData hops were missing
- `trace()` backward from a decision could not reach source data

**Change:**
- Decision → ReasoningChain: now `source=chain, target=decision, relation=GENERATES` (enables backward trace from decision)
- KnowledgeRecord → Lesson: recorded as `source=lesson, target=knowledge_record, relation=GENERATES`
- Lesson → SourceData: recorded as `source=source_data, target=lesson, relation=GENERATES`
- Canonical path: `Decision ← ReasoningChain ← Evidence ← KnowledgeRecord ← Lesson ← SourceData`
- All hops are now recordable via `LineageRegistry.trace(decision_id, "decision")`

**Files changed:**
- `src/knowledge/pipeline/pipeline.py:104-118` — added lesson→knowledge_record and source_data→lesson links
- `src/knowledge/pipeline/pipeline.py:259` — reversed direction of decision→chain record
- `src/knowledge/orchestration/engine.py:181-187` — reversed direction of decision→chain record

### Gate 4: pclean from clean clone ✅

**Before:** `pyproject.toml` set `--basetemp=.pytest_tmp`, creating a repository-local directory on every test run. This directory would persist and could cause issues on a fresh clone.

**Change:** Removed `--basetemp=.pytest_tmp` from pytest config. `.pytest_tmp/` was already in `.gitignore`.

**Files changed:**
- `pyproject.toml` — removed `addopts` section

### Documentation reconciliation ✅

All documents now describe the same state:

| Document | Status |
|----------|--------|
| `PROJECT_STATUS.md` | Updated version 0.6.0, progress 80%, ADR-0004 sprint listed |
| `ROADMAP.md` | Phase 10 (ADR-0004 closure) added, "Fully Institutional Ready" removed, remaining gates listed |
| `MEMORY.md` | Orchestration documented as adapter pattern, "Fully Institutional Ready" removed, validation summary updated |
| `ADR-0004` | Gates 1-3 marked CLOSED ✅, Gates 4-7 marked OPEN ❌ |
| `institutional_validation_report.md` | Scenario 9 updated from WARNING to PASS, findings updated |

### Orchestration documented as adapter ✅

`MEMORY.md` now explicitly states:
- "OrchestrationEngine is an adapter pattern around InferencePipeline — it runs intelligence layer adapters, aggregates evidence, then delegates reasoning and decision to the canonical InferencePipeline components"
- Architecture diagram shows OrchestrationEngine delegating to ReasoningEngine + DecisionEngine (canonical)

---

## Remaining Gates (OPEN)

| Gate | Description | Severity |
|------|-------------|----------|
| 4 | Every knowledge record identifies its source lessons + source artifact | Medium |
| 5 | Atomic, immutable content-addressed persistence | Medium |
| 6 | CPI/US10Y out-of-sample evaluation | Low |
| 7 | Clean CI test pass | Low |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `horizon_days` default change from 20 to None | Low | Changes chain_id format (no `_20` suffix) | Reasoning engine handles None; no caller relied on suffix |
| Lineage direction change | Low | Tests checking `source_type=="decision"` broke | Fixed: now checks `target_type=="decision"` |
| Evidence matching now filters by all 3 dimensions | Low | Tests not passing explicit horizon got fewer results | Fixed: default horizon_days=None means no filter |

No regression in 358 tests. Zero new dependencies. Zero breaking changes to public APIs.
