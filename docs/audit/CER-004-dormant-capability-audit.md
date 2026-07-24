# CER-004: Final Dormant Capability Audit

## Objective
Exhaustive audit of all dormant capabilities — populated-but-unread fields, completed modules never called, outputs never consumed, disconnected services — ranked by institutional value per implementation cost. This is the final gate before implementing Expectations Intelligence (Gap 2).

---

## Methodology
- Traced every production import chain in `src/` (excluding tests and benchmarks)
- For each field, class, and method: identified **definition site**, **population site**, and **consumption site**
- Classified as: "fully used", "written but never read", "dead code path", or "dead class"

---

## Audit Findings

### Category A: Populated-but-unread Fields

| # | Field | File:Line | Populated At | Read In Production | Impact |
|---|-------|-----------|-------------|-------------------|--------|
| A1 | `Lesson.event_surprise` | `models/lesson.py:18` | Never populated in production | Never read | Structural — field exists in schema but `Lesson` never instantiated in `src/` |
| A2 | `CrossEventResult.overall_consensus` | `reasoning/cross_event.py:28` | `cross_event.py:56` | Only in benchmarks (`benchmark/stability.py`, `determinism.py`, `cross_event.py`) | Decision logic has zero awareness of cross-event consensus |
| A3 | `CrossEventResult.consensus_confidence` | `reasoning/cross_event.py:29` | `cross_event.py:57` | Same as A2 | Confidence-weighted consensus never reaches decisions |
| A4 | `Evidence.explanation` | `evidence/evidence.py:21` | Every Evidence construction | **Not read by ReasoningEngine** (`reasoning/engine.py:56-74` reads 7 fields but skips explanation) | Reasoning steps carry no justification from evidence generation |

### Category B: Completed Modules Never Called in Production

| # | Module | File | Capability | Lines | Status |
|---|--------|------|-----------|-------|--------|
| B1 | `EvidenceRanker` | `evidence/ranker.py` | 4 ranking methods (confidence, sample, magnitude, combined) | 58 | Never called in `src/`. Only test coverage. |
| B2 | `CausalAnalyzer` | `causal/analyzer.py` | `analyze_relation()`, `create_hypothesis()`, `update_hypothesis_with_evidence()` | 268 | Type-hinted in `OrchestrationContext.causal_analyzer` but never instantiated. Always `None`. |
| B3 | `HistoricalSituationRetriever` | `reasoning/retrieval.py` | Multi-dimensional similarity retrieval (event_type, condition, horizon, maturity, temporal) | 221 | Call site exists in `OrchestrationEngine.analyze()` (line 99-110) but never instantiated by production. |
| B4 | `MacroRegimeDetector` | `regime/macro_regime_detector.py` | Markov switching regime detection (EXPANSION/LATE_CYCLE/CONTRACTION/RECOVERY) | 103 | `MacroRegimeFeatureExtractor` expects injected instance; no production code creates one. |
| B5 | `FeedbackApplicator` | `evolution/applicator.py` | Full evaluate→calibrate→persist pipeline | 94 | Never instantiated in production. |
| B6 | `KnowledgeCalibrator` | `evolution/knowledge_calibrator.py` | Version-bumped confidence/explanation/provenance update | 69 | Only reachable through `FeedbackApplicator` (dead path). |
| B7 | `LearningEngine` | `learning/engine.py` | `evaluate()`, `create_session()`, `generate_feedback()` | 163 | Only reachable through `FeedbackApplicator` (dead path). |

### Category C: Outputs Never Consumed / Services Disconnected

| # | Service | Produces | Consumed By | Status |
|---|---------|----------|------------|--------|
| C1 | `OrchestrationEngine.analyze()` | `OrchestrationReport` with cross_event_result, chain, decision, historical_matches | **Never called** — production uses `InferencePipeline` directly | Dead class despite being the most complete orchestration adapter |
| C2 | `EvidenceAggregator.merge()` | `AggregationResult` with layer_counts, layer_sources, conflicts | Only through `OrchestrationEngine` | Dead path |
| C3 | `EconomicBrain` | Analysis dict with 10 KnowledgeRecord fields | Only runs as `__main__`. Never imported. | Dead class |

### Category D: Unused KnowledgeRecord Fields by EconomicBrain

| Field | Read by EconomicBrain? | Used Elsewhere? |
|-------|----------------------|-----------------|
| `knowledge_id` | Yes (line 113) | — |
| `asset` | Yes (line 111) | — |
| `condition` | Yes (line 102) | — |
| `horizon_days` | Yes (line 107) | — |
| `sample_count` | Yes (line 114) | — |
| `bias` | Yes (line 115) | — |
| `confidence` | Yes (line 116) | — |
| `positive_return_rate_pct` | Yes (line 117) | — |
| `average_return_pct` | Yes (line 118) | — |
| `explanation` | Yes (line 119) | — |
| `event_type` | NO | Used by EvidenceQuery for matching |
| `negative_return_rate_pct` | NO | Statistical distribution — never read anywhere in `src/` |
| `up_direction_rate_pct` | NO | Never read |
| `down_direction_rate_pct` | NO | Never read |
| `flat_direction_rate_pct` | NO | Never read |
| `median_return_pct` | NO | Never read |
| `min_return_pct` | NO | Never read |
| `max_return_pct` | NO | Never read |
| `first_event_date` | NO | Never read |
| `last_event_date` | NO | Never read |
| `source_lesson_ids` | NO | Never read |
| `source_artifact_path` | NO | Never read |
| `source_artifact_sha256` | NO | Never read |
| `provenance` | NO | Serialized/deserialized, version-bumped by calibrator, but never read by business logic |
| `metadata` | NO | Serialized, appended to by calibrator |

**16 of 22 KnowledgeRecord fields never read in production.** The 6 that ARE read are used only by `EconomicBrain`, which itself is dead code.

---

## Ranked by Institutional Value per Implementation Cost

### Tier 1: Implement Before Expectations Intelligence

These directly enable Gap 2 or cost almost nothing.

| Rank | Finding | Gap Enabled | Effort | Rationale |
|------|---------|-------------|--------|-----------|
| **1** | `event_surprise` — populate from external data + pass through Lesson→Evidence | Gap 2 (Expectations-Surprise Separation) | **Low** (add surprise field to Evidence, populate during Lesson creation) | The core primitive for surprise-aware reasoning. Without this, every decision ignores whether the market expected the event. |
| **2** | `ReasoningEngine` — read `Evidence.explanation` in evidence review step | Reasoning quality | **Trivial** (one line: `"explanation": ev.explanation` in `_build_evidence_review` details) | The explanation field is populated on every Evidence object but completely ignored during reasoning. Downstream decisions lack context for why this evidence exists. |
| **3** | `CrossEventResult` — wire `consensus_confidence` and `overall_consensus` into DecisionEngine | Gap 9 (Consensus Awareness) | **Low** (pass through ReasoningChain or OrchestrationReport to DecisionEngine) | Cross-event consensus is already computed but never influences decisions. This is the cheapest value unlock in the entire codebase. |

### Tier 2: Implement Alongside or Immediately After Gap 2

| Rank | Finding | Gap Enabled | Effort | Rationale |
|------|---------|-------------|--------|-----------|
| **4** | `EvidenceRanker` — call before `ReasoningEngine.reason()` to prioritize evidence | Reasoning quality | **Low** (one call in pipeline) | Evidence is currently fed to reason() in arbitrary order. Ranking by confidence/recency would improve decision quality with no new data. |
| **5** | `EvidenceAggregator.conflicts` — surface layer conflicts to user | Transparency | **Low** (conflicts already computed, just need to surface in response) | The aggregator already detects cross-layer bias conflicts; they're stored in the report but never shown to any caller. |

### Tier 3: Foundation Gaps (Medium Cost, High Value)

| Rank | Finding | Gap Enabled | Effort | Rationale |
|------|---------|-------------|--------|-----------|
| **6** | `HistoricalSituationRetriever` — instantiate in `InferencePipeline` | Gap 5 (Historical Analogy Engine) | **Medium** (retriever is complete, just needs construction and wiring) | Full multi-dimensional similarity engine exists. The call site is ready in `OrchestrationEngine`. Needs to be ported to `InferencePipeline` or `OrchestrationEngine` needs to replace `InferencePipeline` as production path. |
| **7** | `MacroRegimeDetector` — instantiate and inject into `MacroRegimeFeatureExtractor` | Gap 4 (Regime Change Detection) | **Medium** (detector is complete, just needs construction) | Statsmodels is a heavy dependency but already installed. The detector is deterministic and tested. Just needs one construction call. |
| **8** | `CausalAnalyzer` — instantiate in orchestration context | Gap 3 (Directed Causal Model) + Gap 10 (Feedback-Driven Causal Model Update) | **Medium** (analyzer is complete, `analyze_relation()` just needs to be called with evidence pairs) | `CausalAnalyzer` is 268 lines of fully tested code. The type hint exists in `OrchestrationContext`. Only instantiation is missing. |

### Tier 4: Close the Learning Loop (Medium-High Cost, Foundational)

| Rank | Finding | Gap Enabled | Effort | Rationale |
|------|---------|-------------|--------|-----------|
| **9** | `FeedbackApplicator` — integrate into event processing pipeline after decision is evaluated | Learning Loop (foundational for ALL gaps) | **Medium-High** (requires decision→outcome matching, scheduling, persistence) | Closes the identify-decide-learn loop. Without this, the system never improves from experience. KnowledgeCalibrator and LearningEngine are already built and integrated into FeedbackApplicator. |

### Tier 5: Structural Improvements (High Cost, Strategic)

| Rank | Finding | Gap Enabled | Effort | Rationale |
|------|---------|-------------|--------|-----------|
| **10** | Port `EconomicBrain` to use `KnowledgeRecord` directly and wire into production path | All gaps | **High** (reads dict instead of KnowledgeRecord; dead code; needs re-architecture) | Currently reads only 6/22 fields using fragile dict access. Should accept `KnowledgeRecord` directly. But dead class means the entire production memory/analysis path needs reconstruction. |
| **11** | Replace `InferencePipeline` with `OrchestrationEngine` as production path | Systemic | **High** (`OrchestrationEngine` is dead; `InferencePipeline` is the real production entry point) | `OrchestrationEngine` has more capabilities (economic, temporal, causal, cross-event, historical, lineage) but `InferencePipeline` is what actually runs. Consolidating would unlock C2, C3, but requires careful migration. |

---

## Summary

**25 dormant capabilities identified** across 5 categories:
- 4 populated-but-unread fields
- 7 completed modules never called
- 3 disconnected services
- 16 KnowledgeRecord fields never read
- 3 computed-but-unconsumed outputs

**Top 3 priorities before Expectations Intelligence:**
1. `event_surprise` — add to Evidence, populate from external data
2. `Evidence.explanation` — read during reasoning (one line)
3. `CrossEventResult.consensus_confidence` — wire into decision logic

These three cost essentially nothing and unlock two full gaps (Gaps 2 and 9). All other dormant capabilities can be activated incrementally after Expectations Intelligence is live.
