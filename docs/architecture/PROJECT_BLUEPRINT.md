# AurumAI — Institutional Project Blueprint

**Status:** Permanent CTO Reference  
**Version:** 0.9.0  
**Date:** 2026-07-25  
**Authority:** This document describes the project exactly as it exists.  
It does not prescribe changes.

---

## 1. Global Statistics

| Metric | Value |
|--------|-------|
| Python files (`src/`) | 174 |
| Test files (`tests/`) | 73 |
| Documentation files (`.md`, excluding `archive/`) | 49 |
| Top-level packages under `src/` | 9 |
| Sub-packages under `src/knowledge/` | 22 |
| Public classes (all packages) | ~205 |
| Total tests | 1638+ |
| Benchmarks passing | 18/18 |
| Total experiments completed | 1 (Experiment 001 — REJECT US10Y) |
| Total registries | 4 (EventRegistry, LineageRegistry, ExperimentRegistry, ForecastRegistry) |
| Runtime dependencies | 6 (pandas, numpy, networkx, statsmodels, statsforecast, feedparser) |
| Data files (CSV) | 64 |
| Data files (JSON) | 25 |
| Python version | >=3.10 |
| Project completion estimate | 88% |

---

## 2. Directory Architecture

### Project Root

| Path | Purpose | Files |
|------|---------|-------|
| `src/` | Installable `aurumai` package — 9 packages | 174 `.py` |
| `tests/` | Deterministic test suite mirroring `src/` structure | 73 `.py` |
| `data/` | Regenerable artifacts — CSVs, JSON, knowledge, experiments | 89 files |
| `docs/` | Authoritative documentation — ADRs, architecture, audit, constitution | 49 `.md` |
| `research/` | Candidate evidence for future ADRs | varies |
| `archive/` | Historical sprint reports, bootstrap scripts (not authoritative) | varies |
| `configs/` | Reserved for configuration | empty |
| `models/` | Reserved for trained models | empty |
| `notebooks/` | Reserved for analysis notebooks | empty |

### `src/` Packages

| Package | Purpose | Owner | Files | Classes | Maturity |
|---------|---------|-------|-------|---------|----------|
| `src/knowledge/` | Intelligence Core — events, lessons, knowledge, reasoning, decision | CTO | ~110 | ~105 | **Frozen v1.0** (core); active sub-packages |
| `src/orchestration/` | DAG pipeline orchestrator — stages, caching, checkpointing | CTO | 7 | 7 | Active |
| `src/simulation/` | Backtesting — historical replay, OOS evaluation, experiments | CTO | 10+ | 36 | Active |
| `src/forecasting/` | Time-series forecasting, risk measures, position sizing, decision gate | CTO | 15+ | 32 | Active |
| `src/execution/` | Paper trading — portfolio, slippage, commission, execution engine | CTO | 6 | 15 | Active (paper only) |
| `src/news/` | RSS news collection for macro-relevant articles | CTO | 3 | 3 | Active |
| `src/nlp/` | Sentiment analysis — FOMC (RoBERTa), News (FinBERT) | CTO | 3 | 4 | Active |
| `src/technical/` | Technical indicators — RSI, MACD, EMAs, Bollinger Bands | CTO | 1 | 1 | Active |
| `src/connectors/` | External data connectors — FOMC calendar | CTO | 2 | 2 | Active |

### `src/knowledge/` Sub-packages

| Sub-package | Purpose | Maturity |
|-------------|---------|----------|
| `events/` | MacroEvent ABC + 7 concrete event types (CPI, NFP, GDP, INTEREST_RATE, PPI, PMI, FOMC) | Active |
| `features/` | FeatureExtractionEngine + 9 extractors (CPI, NFP, GDP, PPI, PMI, FOMC, InterestRate, MacroRegime, Technical) | Active |
| `builders/` | LessonBuilder (institutional + legacy) | Active |
| `pipeline/` | InferencePipeline — 7-stage production entry point | **Frozen** |
| `reasoning/` | ReasoningEngine, EvidenceWeighter, CrossEventAnalyzer, HistoricalSituationRetriever | **Frozen** (core); partial (retriever) |
| `decision/` | DecisionEngine, Decision, DecisionContext | **Frozen** |
| `evidence/` | Evidence, EvidenceCollection, EvidenceQuery, EvidenceRanker, EvidenceRepository | **Frozen** (core); dormant (ranker) |
| `graph/` | KnowledgeGraph (NetworkX), GraphBuilder, GraphRepository | Active |
| `integrity/` | Provenance, LineageRegistry, VersionedStore, SourceData, KnowledgeRecord | Active |
| `orchestration/` | OrchestrationEngine, EvidenceAggregator, LayerPolicy | Dormant (dead code path) |
| `learning/` | LearningEngine, LearningSession, KnowledgeFeedback | Dormant (dead code path) |
| `evolution/` | FeedbackApplicator, KnowledgeCalibrator | Dormant (dead code path) |
| `economics/` | EconomicClassifier, EconomicState, EconomicRegime, EconomicEvidenceAdapter | Dormant (dead code path) |
| `temporal/` | TemporalIndexer, TemporalEvidenceAdapter, TemporalState | Dormant (dead code path) |
| `causal/` | CausalAnalyzer, CausalGraph, CausalRelation, CausalHypothesis | Dormant (dead code path) |
| `context/` | YieldContextEnricher, DXYContextEnricher, ContextComparisonReport | Active |
| `regime/` | MacroRegimeDetector, MacroRegimeFeatureExtractor | Dormant (never instantiated) |
| `expansion/` | EventScaffolder, EventValidator, ExpansionLifecycle | Active |
| `models/` | Lesson dataclass (legacy) | Legacy |
| `repository/` | Lesson repository (legacy) | Legacy |
| `validation/` | Schema and data validation utilities | Active |
| `benchmark/` | BenchmarkSuite — 18 benchmarks across 7 classes | Active |

---

## 3. Institutional Departments

Each `src/` package maps to an institutional department:

```
knowledge
   ↓
Institutional Knowledge Department
   ├── Event Registry Office    (events/)
   ├── Feature Engineering      (features/)
   ├── Lesson Building          (builders/)
   ├── Knowledge Pipeline       (pipeline/)        ← FROZEN
   ├── Reasoning Division       (reasoning/)       ← FROZEN
   ├── Decision Office          (decision/)        ← FROZEN
   ├── Evidence Management      (evidence/)        ← FROZEN
   ├── Knowledge Graph          (graph/)
   ├── Integrity & Audit        (integrity/)
   ├── Economic Intelligence    (economics/)       ← DORMANT
   ├── Temporal Intelligence    (temporal/)        ← DORMANT
   ├── Causal Intelligence      (causal/)          ← DORMANT
   ├── Context Enrichment       (context/)
   ├── Regime Detection         (regime/)          ← DORMANT
   ├── Orchestration Division   (orchestration/)   ← DORMANT
   ├── Learning Division        (learning/)        ← DORMANT
   ├── Evolution Division       (evolution/)       ← DORMANT
   ├── Expansion Office         (expansion/)
   ├── Models Archive           (models/)          ← LEGACY
   ├── Repository Archive       (repository/)      ← LEGACY
   └── Validation Office        (validation/)

orchestration
   ↓
DAG Operations Department
   ├── Stage Execution          (stages.py)
   ├── Dependency Resolution    (dag.py)
   ├── Cache Management         (cache.py)
   ├── Checkpoint Management    (checkpoints.py)
   ├── Job Scheduling           (jobs.py)
   └── Orchestrator             (orchestrator.py)

simulation
   ↓
Simulation & Validation Department
   ├── Historical Replay        (historical_replay.py)
   ├── Out-of-Sample Engine     (oos_engine.py)
   ├── Experiment Framework     (experiment.py, experiment_registry.py)
   └── Validation Reports       (validation.py)

forecasting
   ↓
Forecasting & Risk Department
   ├── Time Series Forecasting  (macro_forecaster.py)
   ├── Risk Measures            (risk_measures.py)
   ├── Position Sizing          (position_sizing.py)
   ├── Risk Budgeting           (risk_budgeting.py)
   ├── Decision Gate            (decision_gate.py)
   ├── Forecast Context         (context.py)
   └── Forecast Registry        (registry.py)

execution
   ↓
Execution Department
   ├── Portfolio Management     (portfolio.py)
   ├── Slippage Models          (slippage.py)
   ├── Commission Models        (commission.py)
   └── Execution Engine         (execution_engine.py)

news
   ↓
News Intelligence Department
   └── News Collection          (news_collector.py)

nlp
   ↓
Natural Language Processing Department
   ├── FOMC Sentiment           (fomc_sentiment.py)
   └── News Sentiment           (news_sentiment.py)

technical
   ↓
Technical Analysis Department
   └── Technical Indicators     (indicators.py)

connectors
   ↓
External Data Connectors Department
   └── FOMC Calendar            (fomc_calendar.py)
```

### Department Dependency Map

| Department | Responsibility | Upstream Dependencies | Downstream Consumers |
|-----------|---------------|----------------------|---------------------|
| Knowledge | Core intelligence — events, lessons, graph, reasoning, decision | Raw data files (CSV) | Orchestration, Simulation |
| DAG Operations | Pipeline execution, caching, checkpointing | Knowledge | Simulation |
| Simulation | Historical replay, OOS evaluation, experiments | Knowledge, Orchestration | Forecasting, Execution |
| Forecasting & Risk | Time-series forecasts, risk metrics, position sizing | Knowledge, Simulation | Execution |
| Execution | Paper portfolio, slippage, commission, order execution | Forecasting, Knowledge | (none — terminal layer) |
| News Intelligence | RSS news collection | Connectors | Knowledge, NLP |
| NLP | Sentiment analysis (FOMC, news) | News, Connectors | Knowledge |
| Technical Analysis | Technical indicators on OHLCV | Knowledge | Knowledge |
| External Connectors | FOMC calendar, data source adapters | (external APIs) | News, Knowledge |

---

## 4. Production Pipeline

The verified production path (from CER-006 runtime trace):

```
HistoricalReplayEngine.run_all()                    [src/simulation/historical_replay.py]
  │
  ├── _iter_event_types() → ["CPI","NFP","GDP","INTEREST_RATE","PMI","PPI","FOMC"]
  │
  └── _replay_event(event_type, csv_path)
       │
       └── InstitutionalOrchestrator.with_default_pipeline()  [src/orchestration/orchestrator.py]
            │  registers 11 PipelineJob objects
            │
            └── orchestrator.run_all(trigger, **params)
                 │
                 ├── _topological_levels(self._jobs)           [src/orchestration/dag.py]
                 ├── ThreadPoolExecutor per level
                 └── _execute_job(job_id, pipeline_id, force)
                      │
                      ├── CheckpointManager.exists()           [src/orchestration/checkpoints.py]
                      ├── CacheManager.get()                   [src/orchestration/cache.py]
                      └── job.fn() → _bind(stage_fn)(params, results)


Stage Execution DAG (topological order):

  LEVEL 0 (parallel):
    ┌─ _ingest_event
    │    → EventRegistry.get_or_raise(event_type)
    │    → event_cls().load_raw(data_path)
    │    → event.load_and_extract(data_path)
    │         → FeatureExtractionEngine().process(raw, <TypeExtractor>())
    │              → <TypeExtractor>.extract(raw) → FeatureSet
    │
    └─ _ingest_news
         → NewsCollector(topics).collect()
         → FOMCCalendarConnector().upcoming_meetings()


  LEVEL 1 (parallel, depends on LEVEL 0):
    ┌─ _build_legacy_pipeline                          [src/orchestration/stages.py]
    │    → PipelineContext(event, paths...)
    │    → InferencePipeline().run(ctx, lineage_registry)   [src/knowledge/pipeline/pipeline.py]
    │       │
    │       ├── _stage_build_lessons
    │       │    → LessonBuilder(config, event).build_and_save()
    │       │    → YieldContextEnricher.enrich_csv()   (conditional)
    │       │
    │       ├── _stage_build_knowledge
    │       │    → LessonSummaryAggregator(config).build_and_save()
    │       │    → LineageRegistry.add() for lesson→knowledge_record
    │       │    → LineageRegistry.add() for source_data→lesson
    │       │
    │       ├── _stage_compare_context                 (conditional)
    │       │    → ContextComparisonReport(config).build_and_save()
    │       │
    │       ├── _stage_build_graph
    │       │    → GraphBuilder().build(records) → KnowledgeGraph
    │       │    → LineageRegistry.add() for knowledge_record→evidence
    │       │
    │       ├── _stage_query_evidence
    │       │    → EvidenceQuery(graph).matching(...) → EvidenceCollection
    │       │    → LineageRegistry.add() for evidence→reasoning_chain
    │       │
    │       ├── _stage_reason
    │       │    → ReasoningEngine().reason(evidence, context) → ReasoningChain
    │       │       → EvidenceWeighter().weigh(evidence) → WeightedAggregate
    │       │
    │       └── _stage_decide
    │            → DecisionEngine().decide(chain, context) → Decision
    │            → LineageRegistry.add() for reasoning_chain→decision
    │
    └─ _forecast
         → MacroForecaster(season_length, freq).forecast(df, h)
            → StatsForecast([AutoARIMA, AutoETS, AutoTheta]).forecast()


  LEVEL 2 (parallel, depends on LEVEL 1):
    ├── _forecast_confidence    → ForecastConfidenceComputer().compute()
    ├── _forecast_validation    → ForecastValidator().validate()
    ├── _build_context          → ForecastContextBuilder().build()
    └── _risk_measures          → compute_var(), compute_cvar(), TailRiskDetector().detect()


  LEVEL 3 (depends on LEVEL 2):
    └── _position_sizing → VolatilityTargetSizer().compute() + RiskParitySizer().compute()


  LEVEL 4 (depends on LEVEL 3):
    └── _risk_gate → RegimeRiskOverlay, UncertaintyBudget, DecisionGate().evaluate()


  LEVEL 5 (terminal, depends on all):
    └── _finalize → InstitutionalAssessment       [src/orchestration/models.py]
```

**Terminal output:** `InstitutionalAssessment` → `HistoricalReplayEngine._assessment_to_result()` → `EventRunResult`

---

## 5. Capability Inventory

### ACTIVE — Wired and operating in production

| ID | Capability | Location | Since |
|----|-----------|----------|-------|
| A01 | EventRegistry — type-safe event lookup | `src/knowledge/events/registry.py` | Phase 3 |
| A02 | CPIEvent — CPI data loading & feature extraction | `src/knowledge/events/cpi.py` | Phase 2 |
| A03 | NFPEvent — Non-Farm Payroll event | `src/knowledge/events/nfp.py` | Phase 14 |
| A04 | GDPEvent — GDP event | `src/knowledge/events/gdp.py` | Phase 14 |
| A05 | InterestRateEvent — Interest rate decision event | `src/knowledge/events/interest_rate.py` | Phase 14 |
| A06 | PPIEvent — Producer Price Index event | `src/knowledge/events/ppi.py` | Phase 14 |
| A07 | PMIEvent — Purchasing Managers' Index event | `src/knowledge/events/pmi.py` | Phase 14 |
| A08 | FOMCEvent — FOMC meeting event | `src/knowledge/events/fomc.py` | Phase 14 |
| A09 | MacroEvent ABC — abstract base for all events | `src/knowledge/events/base.py` | Phase 2 |
| A10 | StandardEventMetadata — institutional event metadata | `src/knowledge/events/base.py` | Phase 14 |
| A11 | FeatureExtractionEngine — raw data → validated features | `src/knowledge/features/engine.py` | Phase 3 |
| A12 | CPIFeatureExtractor | `src/knowledge/features/extractors/cpi.py` | Phase 3 |
| A13 | NFPFeatureExtractor | `src/knowledge/features/extractors/nfp.py` | Phase 14 |
| A14 | GDPFeatureExtractor | `src/knowledge/features/extractors/gdp.py` | Phase 14 |
| A15 | InterestRateFeatureExtractor | `src/knowledge/features/extractors/interest_rate.py` | Phase 14 |
| A16 | PPIFeatureExtractor | `src/knowledge/features/extractors/ppi.py` | Phase 14 |
| A17 | PMIFeatureExtractor | `src/knowledge/features/extractors/pmi.py` | Phase 14 |
| A18 | FOMCFeatureExtractor | `src/knowledge/features/extractors/fomc.py` | Phase 14 |
| A19 | LessonBuilder — institutional lesson construction | `src/knowledge/builders/lesson_builder.py` | Phase 2 |
| A20 | LessonSummaryAggregator — aggregate lessons → knowledge | `src/knowledge/lesson_summary.py` | Phase 2 |
| A21 | YieldContextEnricher — US10Y context enrichment | `src/knowledge/context/yields.py` | Phase 5 |
| A22 | DXYContextEnricher — DXY context enrichment | `src/knowledge/context/dxy.py` | Phase 13 |
| A23 | ContextComparisonReport — factor comparison | `src/knowledge/context/comparison.py` | Phase 5 |
| A24 | InferencePipeline — 7-stage production pipeline | `src/knowledge/pipeline/pipeline.py` | Phase 3 |
| A25 | GraphBuilder — NetworkX knowledge graph | `src/knowledge/graph/builder.py` | Phase 3 |
| A26 | EvidenceQuery — graph-based evidence retrieval | `src/knowledge/evidence/query.py` | Phase 3 |
| A27 | EvidenceWeighter — confidence/recency weighting | `src/knowledge/evidence/weighting.py` | Phase 3 |
| A28 | ReasoningEngine — multi-step reasoning chains | `src/knowledge/reasoning/engine.py` | Phase 3 |
| A29 | DecisionEngine — explainable decisions | `src/knowledge/decision/engine.py` | Phase 3 |
| A30 | Provenance system — created_at, source, version | `src/knowledge/integrity/provenance.py` | Phase 6 |
| A31 | LineageRegistry — full entity traceability | `src/knowledge/integrity/lineage.py` | Phase 6 |
| A32 | VersionedStore — append-only versioned persistence | `src/knowledge/integrity/versioning.py` | Phase 6 |
| A33 | KnowledgeRecord — typed knowledge entity | `src/knowledge/integrity/knowledge_record.py` | Phase 6 |
| A34 | SourceData — raw data source metadata | `src/knowledge/integrity/source_data.py` | Phase 6 |
| A35 | ReleaseCalendar — economic release date management | `src/knowledge/events/release_calendar.py` | Phase 12 |
| A36 | InstitutionalOrchestrator — DAG pipeline runner | `src/orchestration/orchestrator.py` | Phase 22 |
| A37 | CacheManager — stage result caching | `src/orchestration/cache.py` | Phase 22 |
| A38 | CheckpointManager — pipeline resume capability | `src/orchestration/checkpoints.py` | Phase 22 |
| A39 | HistoricalReplayEngine — event replay simulation | `src/simulation/historical_replay.py` | Phase 23 |
| A40 | ChronologicalOOSEngine — OOS evaluation | `src/simulation/oos_engine.py` | Phase 23 |
| A41 | ExperimentRunner — config-driven experiments | `src/simulation/experiment.py` | Phase 23 |
| A42 | ExperimentComparator — cross-run delta metrics | `src/simulation/experiment.py` | Phase 23 |
| A43 | ExperimentRegistry — immutable experiment records | `src/simulation/experiment_registry.py` | Phase 23 |
| A44 | MacroForecaster — AutoARIMA/AutoETS/AutoTheta | `src/forecasting/macro_forecaster.py` | Phase 16 |
| A45 | RiskMetrics — VaR, CVaR computation | `src/forecasting/risk_measures.py` | Phase 17 |
| A46 | TailRiskDetector — Peaks-over-Threshold EVT | `src/forecasting/risk_measures.py` | Phase 17 |
| A47 | VolatilityTargetSizer — position sizing | `src/forecasting/position_sizing.py` | Phase 17 |
| A48 | RiskParitySizer — risk parity allocation | `src/forecasting/risk_budgeting.py` | Phase 17 |
| A49 | DecisionGate — proceed/scale_down/delay/halt | `src/forecasting/decision_gate.py` | Phase 17 |
| A50 | VirtualPortfolio — paper trading portfolio | `src/execution/portfolio.py` | Phase 21 |
| A51 | ExecutionEngine — order execution with risk gating | `src/execution/execution_engine.py` | Phase 21 |
| A52 | SlippageModel + CommissionModel | `src/execution/` | Phase 21 |
| A53 | FOMCSentimentAnalyzer — FOMC-RoBERTa | `src/nlp/fomc_sentiment.py` | Phase 15 |
| A54 | NewsSentimentAnalyzer — ModernFinBERT | `src/nlp/news_sentiment.py` | Phase 15 |
| A55 | TechnicalIndicatorExtractor — RSI, MACD, etc. | `src/technical/indicators.py` | Phase 15 |
| A56 | NewsCollector — RSS news pipeline | `src/news/news_collector.py` | Phase 15 |
| A57 | FOMCCalendarConnector — FOMC meeting calendar | `src/connectors/fomc_calendar.py` | Phase 14 |
| A58 | EventScaffolder — new event code generation | `src/knowledge/expansion/scaffolder.py` | Phase 14 |
| A59 | EventValidator — event implementation validation | `src/knowledge/expansion/validator.py` | Phase 14 |
| A60 | ExpansionLifecycle — full event expansion process | `src/knowledge/expansion/lifecycle.py` | Phase 14 |
| A61 | FrozenDict — immutable dict utility | `src/knowledge/_compat.py` | Phase 20 |
| A62 | atomic_write_json — safe atomic file writes | `src/knowledge/_compat.py` | Phase 20 |
| A63 | BenchmarkSuite — 18 institutional benchmarks | `src/knowledge/benchmark/` | Phase 11 |
| A64 | Experiment 001 — CPI vs CPI+US10Y (REJECT US10Y) | (experiment registry) | Phase 23 |
| A65 | Source artifact traceability on lessons (C-13) | `src/knowledge/builders/lesson_builder.py` | Sprint 001 |

### PARTIAL — Active but incomplete

| ID | Capability | Gap | Location |
|----|-----------|-----|----------|
| P01 | EvidenceRanker | Built (58 lines, 4 ranking methods) but never called in production | `src/knowledge/evidence/ranker.py` |
| P02 | CrossEventResult consensus | `overall_consensus` and `consensus_confidence` computed but never reach DecisionEngine | `src/knowledge/reasoning/cross_event.py` |
| P03 | Evidence.explanation field | Populated on every Evidence object; skipped by ReasoningEngine | `src/knowledge/evidence/evidence.py` |
| P04 | Gate 5 — Content-addressed persistence | `atomic_write_json` exists but not content-addressed | `src/knowledge/integrity/versioning.py` |
| P05 | Gate 7 — CI pipeline | No CI configuration present | root |

### DORMANT — Fully built but never called in production

| ID | Capability | Location | Lines of Code |
|----|-----------|----------|---------------|
| D01 | OrchestrationEngine.analyze() | `src/knowledge/orchestration/engine.py` | 233 |
| D02 | EvidenceAggregator.merge() | `src/knowledge/orchestration/aggregator.py` | ~80 |
| D03 | LayerPolicy evaluation | `src/knowledge/orchestration/policy.py` | ~25 |
| D04 | Economic Intelligence Layer (EconomicClassifier, EconomicState, etc.) | `src/knowledge/economics/` | ~250 |
| D05 | Temporal Intelligence Layer (TemporalIndexer, TemporalEvidenceAdapter) | `src/knowledge/temporal/` | ~300 |
| D06 | CausalAnalyzer (CausalGraph, CausalRelation, CausalHypothesis) | `src/knowledge/causal/` | 268 |
| D07 | HistoricalSituationRetriever | `src/knowledge/reasoning/retrieval.py` | 221 |
| D08 | CrossEventAnalyzer | `src/knowledge/reasoning/cross_event.py` | ~100 |
| D09 | MacroRegimeDetector | `src/knowledge/regime/macro_regime_detector.py` | 103 |
| D10 | FeedbackApplicator | `src/knowledge/evolution/applicator.py` | 94 |
| D11 | KnowledgeCalibrator | `src/knowledge/evolution/knowledge_calibrator.py` | 69 |
| D12 | LearningEngine | `src/knowledge/learning/engine.py` | 163 |
| D13 | ExecutionEngine (in production path — exists but no production consumer) | `src/execution/execution_engine.py` | ~120 |
| D14 | VirtualPortfolio (in production path — no production consumer) | `src/execution/portfolio.py` | ~200 |

### OBSOLETE / LEGACY — Retained for reference only

| ID | Capability | Location | Notes |
|----|-----------|----------|-------|
| O01 | `Lesson` dataclass (models/) | `src/knowledge/models/lesson.py` | Superseded by CSV-based dict lessons |
| O02 | `csv_to_lessons.py` | `src/knowledge/builders/csv_to_lessons.py` | Early schema mapper |
| O03 | `lesson_repository.py` | `src/knowledge/repository/lesson_repository.py` | Early repository wrapper |
| O04 | `EconomicEvent` enum | `src/knowledge/events/__init__.py` | Superseded by MacroEvent ABC |
| O05 | `EconomicBrain` | `src/knowledge/brain.py` | Legacy brain, dead code |
| O06 | `Memory` (flat store) | `src/knowledge/memory.py` | Legacy memory, only in tests |
| O07 | `RULES` fallback | `src/knowledge/rules.py` | Legacy rules, dead code |
| O08 | `build_knowledge.py` | `src/knowledge/build_knowledge.py` | Standalone script, dead code |
| O09 | `historical_teacher.py` | `src/knowledge/builders/historical_teacher.py` | Legacy bootstrap |

---

## 6. Project Timeline

### Phase 1 — Foundation (Complete)
Repository setup, vision, collector skeletons, local economic data.

### Phase 2 — CPI/Gold Knowledge Engine (Complete)
CPI/Gold LessonBuilder, LessonSummaryAggregator, Knowledge Memory, Evidence-Backed Brain.

### Phase 3 — Core Brain Engines (Complete)
FeatureExtractionEngine, KnowledgeGraph (NetworkX), EvidenceQuery, ReasoningEngine, DecisionEngine, LearningEngine, InferencePipeline (6-stage).

### Phase 4 — Intelligence Layers (Complete)
Economic, Temporal, Causal Intelligence Layers.

### Phase 5 — Context Enrichment (Complete)
US10Y Yield Context, Multi-Factor Knowledge Records, ContextComparisonReport.

### Phase 6 — Knowledge Integrity & Versioning (Complete)
Provenance, LineageRegistry, VersionedStore, KnowledgeRecord, SourceData, 35 integrity tests.

### Phase 7 — Intelligence Orchestration (Complete)
OrchestrationEngine, EvidenceAggregator, OrchestrationContext, OrchestrationReport, 13 tests.

### Phase 8 — Adaptive Intelligence Policy Engine (Complete)
LayerPolicy, evaluate_policies(), 6 tests.

### Phase 9 — Institutional Intelligence Validation (Complete)
10 validation scenarios across 10 quality categories.

### Phase 10 — ADR-0004 Final Closure (Complete)
Canonical path, lineage normalization, clean pytest, documentation reconciliation.

### Phase 11 — Knowledge Chain Completion (Complete)
Bidirectional lineage, backward/forward trace, 2 end-to-end tests.

### Phase 12 — Core Stabilization Gates (Partial)
Gates 1-3 CLOSED. Gates 4-7 OPEN.

### Phases 13-14 — Capability Expansion (Complete)
DXY Context, Economic Calendar Connector, Multi-Event Comparison, NFP/FOMC/GDP/PPI/PMI Events.

### Phase 15 — Advanced Context & Intelligence (Complete)
FOMC NLP, News Pipeline, News Sentiment, Technical Indicators, Macro Regime Intelligence.

### Phase 16 — Forecasting (Complete)
Time Series Forecasting (AutoARIMA/AutoETS/AutoTheta).

### Phase 17 — Risk Intelligence (Complete)
VaR/CVaR, Position Sizing, Risk Budgeting, Decision Gate, Integration tests (117 tests).

### Phase 20 — Hardening (Complete)
Determinism, Data Integrity (FrozenDict, atomic writes), Performance (GraphBuilder O(n²)→indexed), Maintainability (orchestrator split), Packaging (pyproject.toml audit).

### Phase 21 — Paper Trading (Complete)
VirtualPortfolio, Slippage & Commission, Execution Engine (167 tests).

### Phase 22 — Production Hardening & Lineage Activation (Complete)
AUR-FINAL-001 through 005 fixes, LineageRegistry production activation, Reproducibility Audit (Verdict A).

### Phase 23 — Institutional Readiness (Active — Sprint 001 in progress)
OOS Validation Milestones A-C (Complete), Experiment Framework (Complete), Experiment Registry (Complete), Experiment 001 (Complete — REJECT US10Y), Gate 4 Lesson Traceability (C-13 — Sprint 001), Immutable Persistence (Open), CI Pipeline (Open).

---

## 7. Remaining Roadmap

### ADR-0004 Gates (Open)

| Gate | Capability | Status |
|------|-----------|--------|
| Gate 5 | Immutable content-addressed persistence (C-14) | Not started |
| Gate 7 | Clean CI pipeline (C-16) | Not started |

### Dormant Capability Activation (ranked by CER-007)

| Rank | Capability | Dependency | Status |
|------|-----------|-----------|--------|
| 1 | C-15 Gate 6 OOS Evaluation | None | **Complete** (Experiment 001) |
| 2 | C-13 Gate 4 Lesson → Artifact Traceability | KnowledgeIntegrity | **Complete** (Sprint 001) |
| 3 | C-09 Evidence.explanation → ReasoningEngine (C-09) | Frozen core governance | Blocked |
| 4 | C-08 CrossEventResult consensus → DecisionEngine | Frozen core governance | Blocked |
| 5 | C-01 EvidenceRanker activation | Frozen core governance | Blocked |
| 6 | C-02 HistoricalSituationRetriever instantiation | Frozen core governance | Blocked |
| 7 | C-07 DXY Context Enricher wiring | C-15 (OOS) | Blocked |
| 8 | C-03 MacroRegimeDetector instantiation | Historical economic data | Not started |
| 9 | C-14 Gate 5 Content-addressed persistence | VersionedStore | Not started |
| 10 | C-10 Temporal Intelligence Layer wiring | C-15, frozen governance | Blocked |
| 11 | C-11 Economic Intelligence Layer wiring | C-10, C-15 | Blocked |
| 12 | C-04 CausalAnalyzer instantiation | KnowledgeGraph | Blocked |
| 13 | C-06 LearningEngine + FeedbackApplicator | C-15, C-14 | Blocked |
| 14 | C-05/C-12 OrchestrationEngine.analyze() + EvidenceAggregator | C-04, C-10, C-11, C-15 | Blocked |
| 15 | C-16 Gate 7 CI Pipeline | None | Not started |

### Phase 18 — Broker Integration (Planned but not started)
Broker adapter interface, Alpaca/IB implementations.

### Phase 19 — Scaling & Production (Planned but not started)
Neo4j migration, Vector DB for RAG, production hardening (monitoring, alerting, deployment).

### Future Experiments
- Experiment 002 — next institutional experiment (candidate TBD)

---

## 8. Frozen Decisions

The following architectural decisions are frozen. They may only be modified
when a verified engineering defect cannot be corrected elsewhere.

### Frozen Core Components (PROJECT_NORTH_STAR.md §4)

| Component | Scope | Frozen Since |
|-----------|-------|-------------|
| InferencePipeline | 7-stage production pipeline | v1.0 |
| ReasoningEngine | Multi-step reasoning chain construction | v1.0 |
| DecisionEngine | Explainable decision production | v1.0 |
| Evidence Engine | Evidence retrieval, query, weighting | v1.0 |
| Knowledge Graph Contracts | GraphNode, GraphRelation, KnowledgeGraph interfaces | v1.0 |
| Core Entity Contracts | MacroEvent ABC, FeatureExtractor ABC, StandardEventMetadata | v1.0 |
| Institutional Assessment | Terminal output model | v1.0 |
| Constitutional Rules | PROJECT_CONSTITUTION.md, PROJECT_NORTH_STAR.md | v1.0 |

### Frozen Framework Components (CURRENT_STATE.md §5)

| Component | Scope |
|-----------|-------|
| Knowledge Expansion Framework | EventScaffolder, EventValidator, ExpansionLifecycle |
| Benchmark Framework | 18 benchmarks — acceptance gate |
| Architecture Layering | Data → Events → Features → Lessons → Knowledge → Graph → Evidence → Reasoning → Decision → Learning |

### Frozen Engineering Principles

| Principle | Source |
|-----------|--------|
| Determinism — same inputs → same outputs | NORTH_STAR §3.2 |
| Explainability — every decision traceable to source data | NORTH_STAR §3.3 |
| Evidence First — opinions prohibited | NORTH_STAR §3.4 |
| Smallest Correct Fix — never redesign when wiring suffices | NORTH_STAR §3.5 |
| Verification Before Implementation | NORTH_STAR §3.6 |
| Backward Compatibility — stable public APIs | NORTH_STAR §3.7 |
| No dead code in main branch | CONSTITUTION §6 |
| Lessons immutable once written | CONSTITUTION §8 |
| No layer may skip the layer below it | CONSTITUTION §9 |
| No real trading before backtesting + paper trading pass gates | CONSTITUTION §5 |

### Frozen Governance Constraint (NORTH_STAR §8)

> No new intelligence capability shall be added before OOS validation
> demonstrates measurable predictive value.

This constraint currently blocks capabilities C-07 through C-14 from
activation until the OOS evaluation answers its four questions.
Experiment 001 has answered "Does US10Y improve decisions?" (verdict:
REJECT), but broad institutional correctness and confidence calibration
remain open questions.

---

## 9. Institutional Ownership Map

### Knowledge — Intelligence Core (`src/knowledge/`)

| Subsystem | Owner | Creates | Consumes | Consumed By |
|-----------|-------|---------|----------|-------------|
| MacroEvent ABC | CTO | Event contract | Raw data | Event implementations |
| CPIEvent / NFP / GDP / PPI / PMI / FOMC / InterestRate | CTO | Feature-rich DataFrames | Raw CSV data | LessonBuilder, FeatureExtractionEngine |
| FeatureExtractionEngine | CTO | FeatureSet, validated DataFrames | Raw event data | LessonBuilder |
| LessonBuilder | CTO | Lesson CSV | Event DataFrames, Gold prices | LessonSummaryAggregator |
| LessonSummaryAggregator | CTO | KnowledgeRecord list | Lesson CSV | GraphBuilder, InferencePipeline |
| YieldContextEnricher | CTO | Enriched lesson CSV | Lesson CSV, US10Y data | InferencePipeline |
| DXYContextEnricher | CTO | Enriched lesson CSV | Lesson CSV, DXY data | InferencePipeline (not wired) |
| GraphBuilder | CTO | KnowledgeGraph (NetworkX) | KnowledgeRecord list | EvidenceQuery |
| EvidenceQuery | CTO | EvidenceCollection | KnowledgeGraph, query params | ReasoningEngine |
| EvidenceWeighter | CTO | WeightedAggregate | EvidenceCollection | ReasoningEngine |
| ReasoningEngine | CTO | ReasoningChain | EvidenceCollection, context | DecisionEngine |
| DecisionEngine | CTO | Decision | ReasoningChain, context | InferencePipeline |
| InferencePipeline | CTO | PipelineResult | PipelineContext, event data | Orchestrator stages |
| LineageRegistry | CTO | LineageRecord list | Entity references | Pipeline stages, audit |
| VersionedStore | CTO | Versioned entities | Entity data | Integrity operations |
| Provenance | CTO | Provenance metadata | Entity version info | All entities |
| OrchestrationEngine | CTO | OrchestrationReport (dormant) | OrchestrationContext | Nothing (dead) |
| EvidenceAggregator | CTO | AggregationResult (dormant) | Multiple evidence sources | Nothing (dead) |
| LearningEngine | CTO | KnowledgeFeedback (dormant) | Decision outcomes | Nothing (dead) |
| FeedbackApplicator | CTO | Updated KnowledgeRecords (dormant) | KnowledgeFeedback | Nothing (dead) |
| CausalAnalyzer | CTO | CausalGraph (dormant) | Evidence pairs | Nothing (dead) |
| TemporalIndexer | CTO | TemporalState (dormant) | Time-series data | Nothing (dead) |
| EconomicClassifier | CTO | EconomicRegime (dormant) | Economic indicators | Nothing (dead) |
| MacroRegimeDetector | CTO | Regime labels (dormant) | Composite scores | Nothing (dead) |
| EventScaffolder | CTO | Scaffolded event code | ExpansionSpec | New event developers |
| EventValidator | CTO | ValidationReport | Event implementation | Expansion lifecycle |
| BenchmarkSuite | CTO | BenchmarkReport | Pipeline components | Institutional validation |

### Orchestration — DAG Operations (`src/orchestration/`)

| Subsystem | Owner | Creates | Consumes | Consumed By |
|-----------|-------|---------|----------|-------------|
| InstitutionalOrchestrator | CTO | InstitutionalAssessment | PipelineJob list | HistoricalReplayEngine |
| CacheManager | CTO | Cache hit/miss | Stage results | Orchestrator execution |
| CheckpointManager | CTO | CheckpointResult | Stage IDs | Orchestrator execution |
| DAG | CTO | Topological levels | PipelineJob dependencies | Orchestrator execution |
| Stages | CTO | Stage results (dict) | Params + results from prior levels | Orchestrator |

### Simulation — Validation (`src/simulation/`)

| Subsystem | Owner | Creates | Consumes | Consumed By |
|-----------|-------|---------|----------|-------------|
| HistoricalReplayEngine | CTO | EventRunResult | InstitutionalAssessment | ExperimentRunner |
| ChronologicalOOSEngine | CTO | ChronologicalOOSResult | HistoricalReplayEngine | ExperimentRunner |
| ExperimentRunner | CTO | ExperimentResult | ExperimentConfig | ExperimentRegistry |
| ExperimentComparator | CTO | ComparisonMetrics | Multiple ExperimentResults | ExperimentReportBuilder |
| ExperimentRegistry | CTO | ExperimentRecord | ExperimentResult | Scripts, reports |
| InstitutionalValidator | CTO | InstitutionalValidationReport | SimulationReport | Audit |

### Forecasting & Risk (`src/forecasting/`)

| Subsystem | Owner | Creates | Consumes | Consumed By |
|-----------|-------|---------|----------|-------------|
| MacroForecaster | CTO | ForecastResult | Historical data | Orchestrator LEVEL 1 |
| ForecastConfidenceComputer | CTO | ForecastConfidence | ForecastResult | Orchestrator LEVEL 2 |
| ForecastValidator | CTO | ForecastValidationReport | ForecastResult | Orchestrator LEVEL 2 |
| ForecastContextBuilder | CTO | ForecastContext | Multiple forecasts | Orchestrator LEVEL 2 |
| RiskMetrics | CTO | VaR, CVaR | Return series | Orchestrator LEVEL 2 |
| TailRiskDetector | CTO | Tail risk flags | Return series | Orchestrator LEVEL 2 |
| VolatilityTargetSizer | CTO | Position sizes | RiskMetrics | Orchestrator LEVEL 3 |
| RiskParitySizer | CTO | RiskBudget | RiskMetrics | Orchestrator LEVEL 3 |
| DecisionGate | CTO | RiskDecision (proceed/scale/delay/halt) | ForecastContext, RiskMetrics | Orchestrator LEVEL 4 |

### Execution (`src/execution/`)

| Subsystem | Owner | Creates | Consumes | Consumed By |
|-----------|-------|---------|----------|-------------|
| VirtualPortfolio | CTO | PortfolioSnapshot | Orders | ExecutionEngine |
| ExecutionEngine | CTO | ExecutionResult, ExecutionDecision | RiskDecision, VirtualPortfolio | Nothing (no production consumer) |
| SlippageModel | CTO | SlippageResult | Order parameters | ExecutionEngine |
| CommissionModel | CTO | CommissionResult | Trade parameters | ExecutionEngine |

### News / NLP / Technical / Connectors

| Subsystem | Owner | Creates | Consumes | Consumed By |
|-----------|-------|---------|----------|-------------|
| NewsCollector | CTO | NewsArticle list | RSS feeds | Orchestrator LEVEL 0 |
| FOMCSentimentAnalyzer | CTO | SentimentResult | FOMC statement text | Orchestrator (not wired) |
| NewsSentimentAnalyzer | CTO | SentimentResult | NewsArticle text | Orchestrator (not wired) |
| TechnicalIndicatorExtractor | CTO | Technical indicators | OHLCV data | Knowledge features |
| FOMCCalendarConnector | CTO | FOMCMeeting list | FOMC calendar CSV | FOMCEvent, Orchestrator |

---

## 10. Project Health

### Strengths

1. **Deterministic at every level.** Full Reproducibility Assessment: Verdict A.
   All IDs content-derived, RNG seeded, source CSVs in-repo. Six sigma-level
   determinism guarantees.

2. **Complete lineage chain.** Every Decision traces back to source data
   through bidirectional lineage records. Production activation of
   LineageRegistry completed in Phase 22.

3. **Proven experiment framework.** Experiment 001 completed with clear
   verdict (REJECT US10Y). The framework is generic (configuration-driven,
   not hardcoded to CPI/US10Y). 50+ integration tests.

4. **Frozen core discipline.** Core v1.0 components (InferencePipeline,
   ReasoningEngine, DecisionEngine, Evidence) are never modified. All new
   capabilities are extensions against stable contracts.

5. **Comprehensive test coverage.** 1638+ tests, 18/18 benchmarks passing.
   Zero regressions across production hardening.

6. **Clean layering.** 7-layer architecture with strict dependency direction.
   No layer skips below it. All packages swappable behind stable interfaces.

7. **Documentation hierarchy.** Clear authority chain: NORTH_STAR →
   CONSTITUTION → CURRENT_STATE → ROADMAP → STATUS. ADRs record every
   architectural decision.

8. **Paper trading complete.** VirtualPortfolio, Slippage & Commission,
   Execution Engine — 167 tests — ready for broker adapter integration.

### Known Gaps

1. **Frozen core governance gap.** Six dormant capabilities (C-01, C-02,
   C-08, C-09, C-10, C-11) require modifying frozen components but lack
   an extension mechanism (pre/post hooks, middleware, adapter layer).
   Per CER-007A, these cannot be activated without either a governance
   exception or a new interceptor pattern.

2. **OrchestrationEngine is dead code.** 233 lines, fully tested, never
   called in production. It contains the only wiring for Economic,
   Temporal, Causal intelligence layers and CrossEventAnalyzer. Its
   dormancy means 5+ full capabilities (~800 lines) are unreachable.

3. **16 of 22 KnowledgeRecord fields never read.** Fields like
   `negative_return_rate_pct`, `up_direction_rate_pct`,
   `median_return_pct`, `source_artifact_sha256` are populated but never
   consumed by business logic.

4. **OOS validation is partial.** Experiment 001 answered "Does US10Y
   improve decisions?" (No — REJECT US10Y). But "Is AurumAI correct?"
   and "Is confidence calibrated?" remain unanswered. Broader evaluation
   across all event types needed.

5. **No CI pipeline (Gate 7).** No GitHub Actions or equivalent
   configuration. Cannot verify fresh-clone determinism automatically.

6. **No content-addressed persistence (Gate 5).** `atomic_write_json`
   exists but artifacts are not content-addressed. Tamper detection and
   deduplication not yet implemented.

7. **No runtime performance evidence.** CER-006 does not exist as a
   completed trace. All "Ease of Activation" scores are based on static
   analysis alone. No profiling data for production-scale workloads.

8. **Legacy code retained.** 9+ legacy modules in `src/knowledge/` are
   retained for reference but not wired. Two test files
   (`test_dummy_event.py`, `test_test_event_event.py`) fail collection
   and must be `--ignore`'d.

### Current Phase

**Institutional Readiness (Phase 23 — Active)**

The project has completed:
- All Core Intelligence (Phases 1-11)
- Capability Expansion (Phases 13-15)
- Forecasting & Risk (Phases 16-17)
- Production Hardening (Phases 20-22)
- Paper Trading (Phase 21)
- OOS Validation Engine (Phase 23 Milestones A-C)
- Experiment Framework & Registry (Phase 23)
- Experiment 001 (REJECT US10Y)
- Gate 4 Lesson → Artifact Traceability (Sprint 001, C-13)

### Overall Completion Estimate

**88%** (per PROJECT_STATUS.md)

Remaining for Institutional Release v1.0:
- Gate 5: Immutable content-addressed persistence (~2%)
- Gate 7: Clean CI pipeline (~1%)
- Dormant capability activation (~5%)
- Broader OOS validation across event types (~2%)
- Broker adapter interface (~2%)

The remaining ~12% is primarily activation of existing dormant code,
not new construction.
