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

| Sprint | Tests |
|--------|-------|
| AUR-FINAL Fixes | 5 |
| LINEAGE-PROD Activation | 2 |
| 20.1–20.5 Hardening | 253 |
| 21.1–21.3 Paper Trading | 167 |

| Total Tests | 1611 |

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

#### ⬜ Experiment 001 (Pending)
- CPI baseline vs CPI + US10Y candidate
- Uses Experiment Framework, no new intelligence

#### ⬜ Immutable Persistence (Gate 5)
- Atomic writes, content-addressed versions

#### ⬜ CI Pipeline (Gate 7)
- Clean CI from fresh clone

No new intelligence capability will be added before OOS validation demonstrates measurable predictive value.
