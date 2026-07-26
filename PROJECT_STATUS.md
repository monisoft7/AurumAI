# PROJECT STATUS

## Documentation Authority

This file is governed by the following hierarchy:
1. **PROJECT_NORTH_STAR.md** — Highest engineering authority
2. **PROJECT_CONSTITUTION.md** — Constitutional rules and governance
3. **CURRENT_STATE.md** — Canonical project snapshot
4. **ROADMAP.md** — Phased plan and gates
5. **PROJECT_STATUS.md** — This file (version, progress, completed items)
6. **Historical documents** — Archived records, preserved for reference

---

## Current Phase

Institutional Readiness (Experiment Framework Complete)

---

## Version

0.9.0

---

## Progress

88%

---

## Completed

### Core Intelligence (Phases 1–11)
- Repository, vision, collector skeletons, local economic/gold data
- CPI/Gold LessonBuilder, Lesson Summary Aggregator, Knowledge Memory
- Evidence-Backed Brain, Feature Extraction Engine
- NetworkX Knowledge Graph, Evidence Query and Ranking
- Reasoning Engine, Decision Engine, Learning Engine
- End-to-End Inference Pipeline
- Economic, Temporal, Causal Intelligence Layers
- US10Y Yield Context Enrichment
- CPI + Yield Multi-Factor Knowledge Records
- Context Comparison Report
- Knowledge Integrity & Versioning (Provenance, LineageRegistry, VersionedStore)
- Intelligence Orchestration Engine (13 tests)
- Adaptive Intelligence Policy Engine (6 tests)
- Institutional Intelligence Validation (10 scenarios, 8 PASS / 2 WARNING)
- ADR-0004 Final Closure (canonical path, lineage normalization, clean pytest)
- Knowledge Chain Completion (bidirectional lineage, 2 end-to-end tests)
- Project Stabilization (dead code removal, import cleanup, documents sync)
- 786 tests passing (post-stabilization)

### Capability Expansion (Phases 13–21)
- DXY Context Layer (13.1)
- Economic Calendar Connector (13.2)
- Multi-Event Knowledge Comparison (13.3)
- NFPEvent Implementation (14.1)
- FOMC Calendar (14.2), FOMC Event (14.3)
- GDP Event, PPI Event, Macro Regime (14.4)
- PMI Event (14.5)
- FOMC Minutes NLP (15.1)
- News Data Pipeline (15.2), News Sentiment Engine (15.3)
- Technical Indicators Engine (15.4)
- Time Series Forecasting (16.1)
- Risk Intelligence Phase 17 (17.1–17.5, 117 tests)
- Phase 20 Hardening (20.1–20.5)
  - Determinism Hardening, Data Integrity (FrozenDict, atomic writes)
  - Performance Hardening (GraphBuilder indexed)
  - Maintainability Hardening (orchestrator module split)
  - Packaging Hardening (pyproject.toml audit)
  - 253 tests across 20.x–21.x
- Phase 21 Paper Trading (21.1–21.3)
  - VirtualPortfolio, Slippage & Commission, Execution Engine
  - 167 tests across 21.x, 1551 total (all passing)

### Production Hardening & Lineage Activation (Phase 22)
- **AUR-FINAL-001**: Fixed look-ahead gap in `_replay_event_release_by_release`
- **AUR-FINAL-002**: Wired `reasoning_horizon`/`reasoning_condition` through legacy pipeline (3 tests)
- **AUR-FINAL-003**: Verified INSUFFICIENT_EVIDENCE guard already functional
- **AUR-FINAL-004**: Added `min_evidence_count` wiring (2 tests)
- **AUR-FINAL-005**: Verified `compare_context` validation already correct
- **LINEAGE-PROD-DISCONNECT**: LineageRegistry created/passed in `_build_legacy_pipeline` (2 tests)
- **Production Hardening Validation**: 1584/1584 pass, 0 regressions, READY
- **Full Reproducibility Assessment**: Verdict A — Fully deterministic
  - All IDs content-derived (no uuid4)
  - All RNG uses fixed seed 42
  - Only cosmetic timestamps differ across runs

### Phase 21.3 Paper Trading Execution Engine (COMPLETE)
- Created `src/execution/execution_engine.py` — `ExecutionEngine` class with `evaluate()` method
- `ExecutionDecision` enum: `EXECUTE`, `REJECT`, `HOLD`
- Respects RiskDecision: `halt`/`delay` → REJECT, no portfolio mutation
- Applies slippage + commission on execute
- Deterministic, no broker/MT5/forecasting/reasoning

### Sprint-002: MacroRegimeDetector Activation (C-03)
- Created `CompositeScoreBuilder` — reads 5 monthly economic CSVs, computes z-scores, averages into monthly composite_score (6 tests)
- Modified `FeatureExtractionEngine` — added class-level global extractors, `register_global()`, `clear_global()`, multi-extractor chaining in `process()` (5 new tests)
- Wired regime initialization in `_ingest_event` — computes composite_score, fits `MacroRegimeDetector`, registers `MacroRegimeFeatureExtractor` globally
- Wired `ForecastContextBuilder` with fitted detector in `_forecast_confidence` and `_build_context` stages
- All 7 event classes (CPI, NFP, GDP, PPI, PMI, InterestRate, FOMC) unchanged — regime enrichment is transparent
- ADR-002 approved FeatureExtractionEngine as the correct ownership point
- Sprint-002-Ownership-Verification.md rejected 5 alternative extension points

### Sprint-003: Institutional Context Propagation (C-04)
- **Problem**: Consumption verification showed `macro_regime` is correctly added to FeatureSet.data by FeatureExtractionEngine but is **lost at the lesson construction boundary** — `build_lesson_fields()` does not forward it into lesson dicts
- **Architectural insight**: Macro Regime is **Institutional Context**, NOT an Event attribute. Events must NOT be modified to forward it.
- **ADR-003** approved LessonBuilder as the correct owner for institutional context propagation
- **Solution**: Added `institutional_context: tuple[str, ...] = ("macro_regime",)` to `LessonBuilderConfig`; both `_build_lessons()` and `_build_lessons_legacy()` forward configured context columns from event_data rows into lesson dicts via `_add_institutional_context()`
- **No event classes modified**: CPIEvent, NFPEvent, GDPEvent, PPIEvent, PMIEvent, FOMCEvent, InterestRateEvent remain unchanged
- **Backward compatible**: Empty tuple `institutional_context=()` disables forwarding; missing columns are silently skipped
- **Extensible**: Future context types (volatility_regime, liquidity_regime, etc.) require only adding the column name to config
- **5 new tests**: legacy forwarding, institutional forwarding, disabled with empty tuple, missing column skipped gracefully, custom context column
- All 27 affected tests pass (lesson_builder + macro_event_standard + lesson_summary)

### FC-001: Semantic Condition Matching Fix (Foundation Correction)
- **Root cause**: `HistoricalSituationRetriever._jaccard_similarity()` computed Jaccard on condition **key sets** instead of **key-value pair sets**, causing semantically opposite conditions (e.g., `cpi_pressure=high` vs `cpi_pressure=low`) to receive perfect similarity
- **Fix**: `set(a.keys())` → `set(a.items())` — one line in `src/knowledge/reasoning/retrieval.py`
- **Impact**: Corrects the broadened retrieval path only; exact-match path unaffected
- **Prerequisite**: Required before Institutional Context can influence similarity-based retrieval
- **2 new regression tests**: opposite values → 0.0, opposite < identical
- All 197 affected tests pass across retrieval, reasoning, weighting, lesson builder, and macro event suites

| Sprint / FC | Tests |
|-------------|-------|
| AUR-FINAL Fixes | 5 |
| LINEAGE-PROD Activation | 2 |
| 20.1–20.5 Hardening | 253 |
| 21.1–21.3 Paper Trading | 167 |
| Sprint-002 (C-03) | 11 |
| Sprint-003 (C-04) | 5 |
| FC-001 | 2 |
| Sprint-004 (C-05) | 5 |
| Sprint-005 (C-06) | 5 |

| Total Tests | 1639 |

---

## Next

### Institutional Readiness (Phase 23 — Active)

#### ✅ OOS Validation — Milestones A–C (Complete)
- Milestone A: Decision correctness evaluation per event type
- Milestone B: OOS summary (directional accuracy, precision/recall, coverage, ECE)
- Milestone C: ChronologicalOOSEngine (strict train/eval split, no future leakage)
- 6 integration tests

#### ✅ Institutional Experiment Framework (Complete)
- ExperimentConfig / RunConfig: configuration-driven, no CPI/US10Y specifics
- ExperimentRunner, ExperimentComparator, ExperimentReportBuilder
- DecisionComparison: decisions changed/improved/degraded
- 12 unit tests, 29/29 tests pass (12 + 11 HistoricalReplayEngine + 6 ChronologicalOOSEngine)

#### ✅ Institutional Experiment Registry (Complete)
- ExperimentRecord: immutable record with id, config snapshot, metrics summary
- Deterministic SHA-256 IDs (no UUIDs), file-based persistence (atomic_write_json)
- Registry API: register, get, list, search, compare, approval workflow
- 27 unit tests

#### ✅ Experiment 001 (Complete — REJECT US10Y)
- CPI baseline vs CPI + US10Y candidate
- Zero measurable difference across all OOS metrics
- Δ directional accuracy = 0.00%, Δ precision = 0.00%, Δ recall = 0.00%
- 0 decisions changed, 0 improved, 0 degraded
- Verdict: **REJECT US10Y** — context enrichment produced no effect on gold directional decisions
- Registry ID: exp_c3b433e5606b0d15
- Tag: `cpi/us10y/context-enrichment/experiment-001`

#### ✅ Sprint-002: MacroRegimeDetector Activation (C-03) (Complete)
- CompositeScoreBuilder produces monthly composite_score from 5 indicators
- FeatureExtractionEngine chains global extractors after primary extractors
- MacroRegimeFeatureExtractor registered at pipeline startup
- ForecastContextBuilder receives fitted detector
- 11 new tests, all existing tests pass

#### ✅ Sprint-003: Institutional Context Propagation (C-04) (Complete)
- ADR-003 approved LessonBuilder as institutional context owner
- LessonBuilderConfig.institutional_context enables config-driven forwarding
- macro_regime now reaches lesson dicts in both canonical and legacy paths
- 5 new tests, 27 affected tests pass
- No event classes modified

#### ✅ FC-001: Semantic Condition Matching Fix (Complete)
- `HistoricalSituationRetriever._jaccard_similarity()` now compares key-value pairs, not keys only
- Opposite conditions (e.g., `cpi_pressure=high` vs `cpi_pressure=low`) produce lower similarity than identical conditions
- 2 new tests, 197 affected tests pass
- Prerequisite for Institutional Context in retrieval

#### ✅ Sprint-004: Institutional Context Visibility (C-05) (Complete)
- ADR-003 verified as sound architecture (LessonBuilder ownership)
- Added `institutional_context: dict[str, str]` to `KnowledgeRecord` — frozen, serialized
- Added `institutional_context` to `LessonSummaryConfig` — majority-vote in `_summarize_group()`
- Added `institutional_context` to `ReasoningContext`, `DecisionContext`, `PipelineContext`
- Wired through `_stage_build_knowledge`, `_stage_reason`, `_stage_decide`
- 5 new tests, backward compatible
- Visibility achieved in all downstream components

#### ✅ Sprint-005: Context-Aware Evidence Retrieval (C-06) (Complete)
- Added 6th similarity dimension (`institutional_context`) to `HistoricalSituationRetriever`
- `SituationQuery`: new `institutional_context` field for query-level context
- `SituationMatch`: new `institutional_context_similarity` for score transparency
- `RetrievalConfig`: `institutional_context_weight=0.10`, rebalanced (cond 0.30→0.25, horiz 0.15→0.10)
- `_institutional_context_similarity()`: generic Jaccard on `dict.items()` — no `macro_regime` reference
- `OrchestrationContext` + `OrchestrationEngine`: wired context to `SituationQuery`
- **Influence: evidence selection ONLY** — no change to weighting, reasoning, confidence, decision
- **Backward compatible**: empty context → neutral score 0.5, existing weights adjusted
- 5 new tests, 518 affected pass
- IRL 3→4: retriever now context-aware

---

## Next

### Institutional Readiness (Phase 23 — Active)

#### ⬜ Sprint-006: Context-Aware Evidence Weighting
- Use institutional_context in EvidenceWeighter (adjust weights based on context match)
- Consume institutional_context from Evidence.metadata
- Do NOT change reasoning, confidence, decision, or explanation
