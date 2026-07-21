# AurumAI Current State

## 1. Mission

AurumAI is **not** a trading bot. It is an institutional financial intelligence brain that transforms raw economic data into explainable market understanding. Trading execution is the final downstream layer — not the current goal. The system first collects data, converts it into structured lessons, builds knowledge, reasons over market context, and produces evidence-backed decisions that can be traced back to their original source.

## 2. Golden Rules

- **Reuse → Adapt → Build**: Always search for existing open-source solutions first, then adapt, only build what is unique.
- **Core v1.0 Frozen**: InferencePipeline, ReasoningEngine, DecisionEngine, Evidence, EventRegistry, Knowledge Expansion Framework, and Benchmark framework must never be modified.
- **No unnecessary abstractions**: Every layer must earn its existence with measurable value.
- **No duplicate architecture**: One canonical path for every operation.
- **Every capability must pass Benchmark**: The 18-benchmark suite is the acceptance gate.
- **Every change must be deterministic**: Same inputs → same outputs, always.
- **Every change must remain explainable**: Every decision must be traceable to its source evidence.

## 3. Current Architecture

```
Raw Data (CSV, FRED, Yahoo Finance)
         ↓
Macro Events (CPI, NFP, GDP, …)
         ↓
Feature Extraction (FeatureExtractionEngine)
         ↓
Lessons (LessonBuilder)
         ↓
Knowledge (LessonSummaryAggregator → KnowledgeRecord)
         ↓
Knowledge Graph (NetworkX)
         ↓
Evidence Query & Ranking
         ↓
Reasoning Engine (ReasoningChain)
         ↓
Decision Engine (explainable decisions)
         ↓
Learning Engine
         ↓
Institutional Intelligence
         ↑
OrchestrationEngine (Economic + Temporal + Causal + Core)
    LayerPolicy Engine (adaptive policy evaluation)
    EvidenceAggregator (merge, deduplicate, conflict detection)
```

Each layer communicates through stable typed contracts. Orchestration is an adapter pattern around the canonical InferencePipeline.

## 3a. Documentation Authority

This file is governed by the following hierarchy:

1. **PROJECT_NORTH_STAR.md** — Highest engineering authority
2. **PROJECT_CONSTITUTION.md** — Constitutional rules and governance
3. **CURRENT_STATE.md** — This file (canonical project snapshot)
4. **ROADMAP.md** — Phased plan and gates
5. **PROJECT_STATUS.md** — Version, progress, completed items
6. **Historical documents** — Archived records, preserved for reference

## 4. Completed Capabilities

**Core Brain**
Feature Extraction Engine, Knowledge Graph, Evidence Query & Ranking, Reasoning Engine, Decision Engine, Learning Engine, Inference Pipeline

**Macro Events**
CPIEvent, NFPEvent, GDPEvent, InterestRateEvent, Macro Regime Intelligence, EventRegistry, MacroEvent ABC with StandardEventMetadata

**Intelligence Layers**
Economic Intelligence Layer, Temporal Intelligence Layer, Causal Intelligence Layer

**Knowledge Integrity**
Provenance system, LineageRegistry, VersionedStore, KnowledgeRecord entity, SourceData entity, Bidirectional lineage trace

**Orchestration**
OrchestrationEngine, EvidenceAggregator, OrchestrationReport, LayerPolicy Engine (adaptive policy evaluation)

**Risk Intelligence (Phase 17 — Complete)**
Core Risk Measures: VaR (historical/parametric), CVaR, TailRiskDetector (Peaks-over-Threshold EVT)
Position Sizing: VolatilityTargetSizer, DrawdownManager, KellyCap
Risk Budgeting: RiskParitySizer (cyclical coordinate descent)
Decision Gate: RegimeRiskOverlay, UncertaintyBudget, DecisionGate (proceed/scale_down/delay/halt), RiskDecision
Integration: Full Forecast Intelligence → Risk Intelligence pipeline

**Context Enrichment**
US10Y Yield Context, DXY Context, Multi-Factor Context Comparison

**Institutional Memory**
Analogical reasoning, institutional validation (10 scenarios, 8 PASS / 2 WARNING)

**Knowledge Expansion Framework**
EventScaffolder + ExpansionSpec, EventValidator + ValidationReport, ExpansionLifecycle + ExpansionAudit, Onboarding guide

**Benchmark & Validation**
18 benchmark tests, institutional validation report

**OOS Validation Engine (Milestones A–C)**
Decision correctness evaluation per event type, OOS summary with directional accuracy/precision/recall/ECE, ChronologicalOOSEngine with strict train/eval split via prebuilt_lessons_path mechanism, no future leakage

**Institutional Experiment Framework**
ExperimentConfig/RunConfig configuration-driven comparison, ExperimentRunner composes ChronologicalOOSEngine, ExperimentComparator with delta metrics and per-event decision comparison, ExperimentReportBuilder (human + machine readable), no CPI/US10Y-specific knowledge — experiments are configurations

**Institutional Experiment Registry**
Immutable file-based record of every experiment execution, deterministic SHA-256 IDs (no UUIDs), approval workflow (PENDING/APPROVED/REJECTED/SUPERSEDED), search by name/tag/commit, cross-experiment comparison, atomic_write_json persistence, corrupt-file resilience, 27 tests

**Production Hardening (Phases 20.1–20.5)**
Determinism Hardening (EvidenceWeighter, MacroRegimeDetector, ForecastEvidence)
Data Integrity (FrozenDict, atomic writes across 11 files, 70 tests)
Performance Hardening (GraphBuilder O(n²)→indexed grouping, 16 tests)
Maintainability Hardening (810-line orchestrator → 6 cohesive modules)
Packaging Hardening (pyproject.toml audit, 3 deps removed, 3 added, 27 imports verified)

**Paper Trading (Phases 21.1–21.3)**
VirtualPortfolio with cash/positions/PnL, 63 tests
Slippage & Commission models, 66 tests
Execution Engine with DecisionGate gating, 38 tests

**Production Lineage Activation**
LineageRegistry now instantiated and passed in `_build_legacy_pipeline` (stages.py)
All 4 lineage hooks in InferencePipeline.run() active in production
Backward trace verified: decision→source_data

## 5. Frozen Components

- Core v1.0: InferencePipeline, ReasoningEngine, DecisionEngine, Evidence, EventRegistry
- Knowledge Expansion Framework (EventScaffolder, EventValidator, ExpansionLifecycle)
- Benchmark framework (18 tests — acceptance gate)
- All Core entity contracts (MacroEvent ABC, FeatureExtractor ABC, StandardEventMetadata)
- Architecture layering (Data → Events → Features → Lessons → Knowledge → Graph → Evidence → Reasoning → Decision → Learning)

## 6. Current Metrics

| Metric | Value |
|--------|-------|
| Project Version | 0.9.0 |
| Python Support | >=3.10 |
| Total Tests | 1638 |
| Benchmark Status | 18/18 passing |
| Core Status | Frozen v1.0 |
| Runtime Dependencies | 6 (pandas, numpy, networkx, statsmodels, statsforecast, feedparser) |
| Execution Components | VirtualPortfolio, VirtualPosition, VirtualTrade, PortfolioSnapshot, ExecutionEngine, SlippageModel, CommissionModel |
| Current Phase | Institutional Readiness (Experiment Framework Complete) |

## 7. Current Phase

**Phase Production Hardening & Lineage Activation (COMPLETE).**

- AUR-FINAL-001: Fixed look-ahead gap in `_replay_event_release_by_release`
- AUR-FINAL-002: Wired `reasoning_horizon`/`reasoning_condition` through legacy pipeline
- AUR-FINAL-003: Verified INSUFFICIENT_EVIDENCE guard already functional
- AUR-FINAL-004: Added `min_evidence_count` wiring + 2 threshold tests
- AUR-FINAL-005: Verified `compare_context` validation already correct
- Production Hardening Validation: 1584/1584 pass, 0 regressions, READY
- LINEAGE-PROD-DISCONNECT: LineageRegistry created in `_build_legacy_pipeline`, passed to `pipe.run()`
- 60/60 orchestrator tests pass; 1537/1537 full suite pass
- Full Reproducibility Assessment: A — Fully deterministic (all IDs content-derived, RNG seeded, source CSVs in-repo)

| Task | Component | Tests |
|-------|-----------|-------|
| AUR-FINAL-001 | Look-ahead gap fix | — |
| AUR-FINAL-002 | reasoning_horizon/condition wiring | 3 |
| AUR-FINAL-003 | INSUFFICIENT_EVIDENCE verify | — |
| AUR-FINAL-004 | min_evidence_count wiring | 2 |
| AUR-FINAL-005 | compare_context verify | — |
| LINEAGE-PROD | LineageRegistry production activation | 2 |
| **Phase total** | | **7+** |

**OOS Validation — Milestones A–C (COMPLETE).**
- Milestone A: Decision correctness evaluation per event type, gold return computation
- Milestone B: OOS summary with directional accuracy, precision/recall, coverage, ECE
- Milestone C: ChronologicalOOSEngine with strict train/eval split, prebuilt_lessons_path, no future leakage
- ChronologicalOOSResult model with to_dict()
- 6 integration tests (ChronologicalOOSEngine)

**Institutional Experiment Framework (COMPLETE).**
- ExperimentConfig / RunConfig: configuration-driven, no hardcoded event types
- ExperimentRunner: composes ChronologicalOOSEngine for baseline + candidate arms
- ExperimentComparator: delta metrics (directional accuracy, precision, recall, coverage, abstention, strong error rate, ECE)
- DecisionComparison: per-event-type decisions changed/improved/degraded tracking
- ExperimentReportBuilder: human-readable text + machine-readable dict
- 12 unit tests covering all models, comparator, config, report
- 29/29 tests pass (12 experiment + 11 HistoricalReplayEngine + 6 ChronologicalOOSEngine)

**Institutional Experiment Registry (COMPLETE).**
- ExperimentRecord: immutable record with id, config snapshot, metrics summary, approval status, tags
- Deterministic IDs: SHA-256 of config + git commit (no UUIDs)
- File-based persistence via atomic_write_json (no databases, no services)
- Registry API: register, get, list, latest, latest_approved, compare_two, find_by_name/find_by_tag/find_by_commit
- Approval workflow: PENDING → APPROVED / REJECTED / SUPERSEDED with timestamped notes
- Serialization: to_dict (machine), to_json, summary_text (human)
- Corrupt-file resilience, idempotent registration
- 27 unit tests

| Milestone | Component | Tests |
|-----------|-----------|-------|
| A | Decision correctness | — |
| B | OOS summary | 5 |
| C | ChronologicalOOSEngine | 6 |
| Experiment Framework | ExperimentConfig/Comparator/Report | 12 |
| Experiment Registry | ExperimentRecord/Registry API/Approval | 27 |
| **OOS total** | | **50** |

## 8. Immediate Next Capability

**Experiment 001** — First institutional experiment: CPI baseline vs CPI + US10Y candidate. Uses the Institutional Experiment Framework. No new intelligence.

## 9. Long-Term Roadmap

```
✅CPI → ✅Interest Rate → ✅Macro Regime → ✅PPI → ✅FOMC Calendar → ✅FOMC Event → ✅PMI →
✅News Pipeline → ✅FOMC NLP → ✅News Sentiment → ✅Technical Indicators →
✅Forecasting Intelligence (Phases 16.1–16.10) → ✅Risk Intelligence (Phase 17.1–17.5) →
✅Phase 20 Hardening (Determinism → Data Integrity → Performance) →
✅Phase 21 Paper Trading (Core → Slippage → Execution Engine) →
✅Lineage Production Activation → ✅Full Reproducibility Verified →
⬜ OOS Validation (Gate 6) → ⬜ Immutable Persistence (Gate 5) → ⬜ CI Pipeline (Gate 7)
```

## 10. AI Instructions

1. **Read this file first.** It is the canonical project snapshot.
2. **Read PROJECT_NORTH_STAR.md second.** It is the highest engineering authority.
3. **Read PROJECT_CONSTITUTION.md third.** It contains the immutable project foundation.
4. **Read ROADMAP.md fourth.** It contains the full phased plan.
5. **Never redesign completed architecture.** Core v1.0 is frozen. Extend, never replace.
6. **Always search existing OSS before coding.** Reuse → Adapt → Build.
7. **Prefer extension over replacement.** Add new MacroEvent subclasses, adapters, and connectors against existing contracts.
8. **Never add complexity without measurable value.** Every feature must pass the question: "Does this make AurumAI smarter or just more complex?"
9. **Run the full test suite before and after every change.** 1593 tests must pass with zero regressions. Note: 2 legacy scaffolded test files (`test_dummy_event.py`, `test_test_event_event.py`) fail collection due to removed scaffolding modules — exclude with `--ignore` flags.
10. **Keep this file updated.** After every completed capability, update sections 4, 6, 7, and 8.
