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

## 5. Frozen Components

- Core v1.0: InferencePipeline, ReasoningEngine, DecisionEngine, Evidence, EventRegistry
- Knowledge Expansion Framework (EventScaffolder, EventValidator, ExpansionLifecycle)
- Benchmark framework (18 tests — acceptance gate)
- All Core entity contracts (MacroEvent ABC, FeatureExtractor ABC, StandardEventMetadata)
- Architecture layering (Data → Events → Features → Lessons → Knowledge → Graph → Evidence → Reasoning → Decision → Learning)

## 6. Current Metrics

| Metric | Value |
|--------|-------|
| Project Version | 0.0.1 |
| Python Support | >=3.10 |
| Total Tests | 1551 |
| Benchmark Status | 18/18 passing |
| Core Status | Frozen v1.0 |
| Runtime Dependencies | 6 (pandas, numpy, networkx, statsmodels, statsforecast, feedparser) |
| Execution Components | VirtualPortfolio, VirtualPosition, VirtualTrade, PortfolioSnapshot, ExecutionEngine, SlippageModel, CommissionModel |
| Latest Capability | Phase 21.3 — Paper Trading Execution Engine (Complete) |

## 7. Current Phase

**Phase 21.3 — Paper Trading Execution Engine (COMPLETE).**

- Created `src/execution/execution_engine.py` — `ExecutionEngine` class with `evaluate()` method
- `ExecutionDecision` enum: `EXECUTE`, `REJECT`, `HOLD`
- `ExecutionResult` frozen dataclass with `to_dict()` serialization (trade, snapshot, costs, models used)
- Respects RiskDecision: `halt`/`delay` → REJECT, no portfolio mutation
- Decision mapping: POSITIVE/STRONG_POSITIVE → BUY; NEGATIVE/STRONG_NEGATIVE → SELL (if long) or SHORT (if no position); NEUTRAL/INSUFFICIENT_EVIDENCE → HOLD
- Applies slippage (price adjustment) + commission (cash deduction) on execute
- STRONG_NEGATIVE sells full position (capped at held quantity); NEGATIVE sells position_size
- Deterministic, no broker/MT5/forecasting/reasoning, no scope creep
- 38 comprehensive unit tests
- Full regression suite: 1551 passed (zero regressions)

| Task | Component | Tests |
|-------|-----------|-------|
| 20.1 | Determinism Hardening | — |
| 20.2 | Data Integrity (FrozenDict, atomic writes) | 70 |
| 20.3 | Performance Hardening (GraphBuilder indexed, benchmarks) | 16 |
| 20.4 | Maintainability Hardening (orchestrator module split) | — |
| 20.5 | Packaging Hardening (pyproject.toml, deps audit) | — |
| 21.1 | Paper Trading Core (VirtualPortfolio, models) | 63 |
| 21.2 | Slippage & Commission Models | 66 |
| 21.3 | Paper Trading Execution Engine | 38 |
| **Total (20.x–21.x)** | | **253** |

## 8. Immediate Next Capability

**Phase 18 — Execution** — Broker integration, paper trading, execution engine. Depends on earlier phases. See ROADMAP.md for full plan.

## 9. Long-Term Roadmap

```
✅GDP → ✅Interest Rate → ✅Macro Regime → ✅PPI → ✅FOMC Calendar → ✅FOMC Event → ✅PMI →
✅News Pipeline → ✅FOMC NLP → ✅News Sentiment → ✅Technical Indicators →
✅Forecasting Intelligence (Phases 16.1–16.10) → ✅Risk Intelligence (Phase 17.1–17.5) →
✅Phase 20 Hardening (Determinism → Data Integrity → Performance) →
⬜ Execution (Phase 18) → ⬜ Scaling (Phase 19)
```

## 10. AI Instructions

1. **Read this file first.** It is the canonical project snapshot.
2. **Read PROJECT_CONSTITUTION.md second.** It contains the immutable project foundation.
3. **Read ROADMAP.md third.** It contains the full phased plan.
4. **Never redesign completed architecture.** Core v1.0 is frozen. Extend, never replace.
5. **Always search existing OSS before coding.** Reuse → Adapt → Build.
6. **Prefer extension over replacement.** Add new MacroEvent subclasses, adapters, and connectors against existing contracts.
7. **Never add complexity without measurable value.** Every feature must pass the question: "Does this make AurumAI smarter or just more complex?"
8. **Run the full test suite before and after every change.** 786 tests must pass with zero regressions.
9. **Keep this file updated.** After every completed capability, update sections 4, 6, 7, and 8.
