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
| Total Tests | 786 (all passing) |
| Benchmark Status | 18/18 passing |
| Core Status | Frozen v1.0 |
| Latest Capability | Technical Indicators Engine (Capability 15.4) |

## 7. Current Phase

Expanding macro event coverage using the Knowledge Expansion Framework — eight of ten EconomicEvent types now implemented (CPI, NFP, GDP, Interest Rate, Macro Regime, PPI, PMI, FOMC). News Data Pipeline (Cap 15.2) aggregates macro-relevant news via RSS with deterministic testing support, alongside FOMC Calendar Connector (Cap 14.2), FOMC Sentiment Analyzer (Cap 15.1), News Sentiment Engine (Cap 15.3), and Technical Indicators Engine (Cap 15.4).

## 8. Immediate Next Capability

**Technical Indicators Engine** — Implement TechnicalIndicatorExtractor (Capability 15.4) computing RSI, MACD, EMAs, SMAs, Bollinger Bands. Foundation for Time Series Forecasting (16.1).

## 9. Long-Term Roadmap

```
✅GDP → ✅Interest Rate → ✅Macro Regime Intelligence → ✅PPI → ✅FOMC Calendar → ✅FOMC Event → ✅PMI →
✅News Pipeline → ✅FOMC NLP → ✅News Sentiment → ✅Technical Indicators →
Forecasting → Portfolio Intelligence → Paper Trading → Execution
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
