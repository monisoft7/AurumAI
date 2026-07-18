# ROADMAP

## Phase 1 — Foundation (Complete)
- [x] Repository setup & project structure
- [x] Vision definition
- [x] Collector skeletons
- [x] Local economic data ingestion

## Phase 2 — CPI/Gold Knowledge Engine (Complete)
- [x] CPI/Gold LessonBuilder
- [x] Lesson Summary Aggregator
- [x] Knowledge Memory ingestion
- [x] Evidence-Backed Brain Lookup

## Phase 3 — Core Brain Engines (Complete)
- [x] Feature Extraction Engine
- [x] Knowledge Graph (NetworkX)
- [x] Evidence Query & Ranking
- [x] Reasoning Engine
- [x] Decision Engine
- [x] Learning Engine
- [x] Inference Pipeline (6-stage)

## Phase 4 — Intelligence Layers (Complete)
- [x] Economic Intelligence Layer
- [x] Temporal Intelligence Layer
- [x] Causal Intelligence Layer

## Phase 5 — Context Enrichment (Complete)
- [x] US10Y Yield Context
- [x] Multi-Factor Knowledge Records
- [x] Context Comparison Report
- [x] Pipeline artifact generation

## Phase 6 — Knowledge Integrity & Versioning (Complete)
- [x] Provenance system (created_at, created_by, entity_version, previous_version_id)
- [x] LineageRegistry — full entity traceability
- [x] VersionedStore — append-only immutable versioning
- [x] KnowledgeRecord typed entity
- [x] SourceData entity
- [x] Provenance on Decision, ReasoningChain, Evidence, Lesson
- [x] Repository serialization with provenance
- [x] 35 integrity tests (338 total)
- [x] Architectural cleanup
  - [x] Centralized Provenance helpers (removed 3x duplication)
  - [x] VersionedStore factory function for typed deserialization
  - [x] LineageRegistry wired into InferencePipeline (optional)
  - [x] KnowledgeRecord from_dict/to_dict + GraphBuilder accepts both types

## Phase 7 — Intelligence Orchestration (Complete)
- [x] OrchestrationEngine — coordinate Economic + Temporal + Causal + Core layers
- [x] EvidenceAggregator — merge, deduplicate, conflict detection
- [x] OrchestrationContext — unified query + layer references
- [x] OrchestrationReport — per-layer evidence + aggregation + chain + decision
- [x] 13 orchestration tests (351 total)
- [x] Zero external dependencies

## Phase 8 — Adaptive Intelligence Policy Engine (Complete)
- [x] LayerPolicy — callable + condition predicate + priority
- [x] evaluate_policies() — deterministic filter+sort, context-only
- [x] OrchestrationEngine.analyze() accepts optional policies parameter
- [x] Default (no policies) = full backward compatibility
- [x] 6 policy tests (357 total)
- [x] ~25 lines of code, zero new dependencies

## Phase 9 — Institutional Intelligence Validation (Complete)
- [x] 10 validation scenarios across 10 quality categories
- [x] Evidence Quality: uses all relevant, ignores irrelevant
- [x] Knowledge Consistency: consistent records -> consistent decisions
- [x] Temporal Consistency: mixed horizons detected (WARNING documented)
- [x] Causal Consistency: internal causal consistency verified
- [x] Cross-Layer Consistency: conflict gap documented (WARNING)
- [x] Explainability Integrity: full decision->chain->evidence trace
- [x] Deterministic Behavior: same input = same output
- [x] Traceability: lineage verified end-to-end
- [x] Insufficient Evidence: code path works, reachable via orchestration flow (resolved)
- [x] End-to-End: all layers + all step types + decision + lineage
- [x] Unified report generated (institutional_validation_report.md)

## Phase 10 — ADR-0004 Final Closure (Complete)
- [x] EvidenceQuery.matching() is canonical lookup in both pipeline and orchestration
- [x] INSUFFICIENT_EVIDENCE reachable via normal orchestration flow
- [x] Lineage normalized: Decision→ReasoningChain→Evidence→KnowledgeRecord→Lesson→SourceData
- [x] pytest clean from clean clone (no .pytest_tmp)
- [x] Orchestration documented as adapter around InferencePipeline
- [x] Documentation reconciled across PROJECT_STATUS.md, ROADMAP.md, MEMORY.md, ADR-0004

## Phase 11 — Knowledge Chain Completion (Complete)
- [x] Lineage records reversed for bidirectional traversal (knowledge_record→evidence, evidence→reasoning_chain)
- [x] Orchestration engine records knowledge_record→evidence for core layer
- [x] Backward trace: every Decision reaches its original SourceData
- [x] Forward trace: every SourceData enumerates all downstream entities
- [x] 2 end-to-end lineage tests (360 total passing)
- [x] Documentation updated

## Phase 12 — Core Stabilization Gates (Deferred from Core v1.0)
- [ ] Gate 4: Every knowledge record identifies source lessons + artifact
- [ ] Gate 5: Atomic, immutable, content-addressed persistence
- [ ] Gate 6: Real CPI/US10Y out-of-sample evaluation
- [ ] Gate 7: Clean CI pipeline from fresh clone

See [ADR-0004](docs/adr/ADR-0004-canonical-inference-path.md).

---

## Capability Expansion — Phases 13–19

The following phases expand AurumAI beyond Core v1.0 without modifying
existing frozen architecture. Each phase adds new capabilities by
implementing MacroEvent subclasses, adapters, or external integrations
against the existing stable contracts.

```
Dependency flow:
                                                         ┌─────────────────────────┐
                                                         │  Phase 19: Scaling      │
                                                         │  Neo4j, Vector DB, Prod │
                                                         └──────────┬──────────────┘
                                                                    │
                                                 ┌───────────────────┴───────────────────┐
                                                 │  Phase 18: Execution                  │
                                                 │  Broker Integration, Paper Trading    │
                                                 └───────────────────┬───────────────────┘
                                                                     │
                                                      ┌──────────────┴──────────────┐
                                                      │  Phase 17: Validation        │
                                                      │  Backtesting, Portfolio Opt  │
                                                      └──────────────┬──────────────┘
                                                                     │
                                    ┌────────────────────────────────┼──────────────────────┐
                                    │  Phase 16: Forecasting & Risk  │                      │
                                    │  Time Series, Risk Engine      │                      │
                                    └────────────────┬───────────────┘                      │
                                                     │                                      │
              ┌──────────────────────────────────────┼──────────────────────┐               │
              │  Phase 15: Advanced Context           │                      │               │
              │  FOMC NLP, News Sentiment, Indicators │                      │               │
              └────────────────┬─────────────────────┘                      │               │
                               │                                             │               │
┌─────────────────────────────┼─────────────────────────────────────────────┼───────────────┘
│  Phase 14: New Macro Events  │                      Phase 13: Context      │
│  NFP, FOMC, GDP Events       │                      DXY Layer, Calendar    │
└─────────────────────────────┘                      Econ Calendar Connector  │
                               │                                             │
                               └──────────────────────┬──────────────────────┘
                                                      │
                                              ┌───────┴────────┐
                                              │  Phase 12       │
                                              │  Stabilization  │
                                              └────────────────┘
                                              ┌────────────────┐
                                              │  Core v1.0     │
                                              │  (Frozen)      │
                                              └────────────────┘
```

---

## Phase 13 — Event Context Expansion

### 13.1 DXY Context Layer
| Field | Value |
|-------|-------|
| **Purpose** | Enrich lessons with US Dollar Index context (parallel to existing US10Y yield context). DXY measures USD strength against 6 major currencies. |
| **Reuse** | **Adapt** — `fredapi` (MIT) provides DXY via `DTWEXBGS` (Trade Weighted Dollar Index). Already a project dependency. ~20 lines of adapter code. |
| **Dependencies** | Core v1.0 context framework (`src/knowledge/context/`) |
| **Complexity** | Low |
| **Output** | `DXYContextEnricher` class, analogous to `YieldContextEnricher` |

### 13.2 Economic Calendar Connector
| Field | Value |
|-------|-------|
| **Purpose** | Provide structured economic release calendar (scheduled CPI, NFP, FOMC, GDP dates with actual/forecast/previous values). Replaces manual CSV data loading for live events. |
| **Reuse** | **Adapt** — `ecocal` (MIT) provides worldwide economic calendar as DataFrames. Alternative: `Finnhub` free API. |
| **Dependencies** | Core v1.0 MacroEvent ABC (metadata fields for forecast/actual/previous) |
| **Complexity** | Low–Medium |
| **Output** | `EconomicCalendarConnector` adapter mapping external data → MacroEvent-compatible DataFrames |

### 13.3 Multi-Event Knowledge Comparison
| Field | Value |
|-------|-------|
| **Purpose** | Compare knowledge records across multiple event contexts (CPI pressure + DXY regime + US10Y trend) instead of single-factor comparison. |
| **Reuse** | **Build** — extends `ContextComparisonReport` to multi-factor |
| **Dependencies** | 13.1 (DXY), existing US10Y context |
| **Complexity** | Medium |

---

## Phase 14 — New Macro Events

### 14.1 NFPEvent Implementation
| Field | Value |
|-------|-------|
| **Purpose** | Implement `MacroEvent` subclass for Non-Farm Payroll releases. Standard fields: event_type="NFP", condition_columns=["nfp_surprise_level"], feature extraction for surprise classification. |
| **Reuse** | **Build** — implements existing `MacroEvent` ABC and `FeatureExtractor` ABC |
| **Dependencies** | MacroEvent standard (completed), FeatureExtractionEngine |
| **Complexity** | Low–Medium |
| **Output** | `NFPEvent`, `NFPFeatureExtractor`, NFP lesson dataset, NFP knowledge records |

### 14.2 Central Bank Calendar
| Field | Value |
|-------|-------|
| **Purpose** | Provide FOMC meeting dates, rate decision schedules, minutes release dates. Foundation for FOMCEvent. |
| **Reuse** | **Adapt** — `ScrapeFOMC` (GitHub: marcburri) scrapes Fed website for meeting dates and documents. |
| **Dependencies** | None (independent) |
| **Complexity** | Low |
| **Output** | `FOMCCalendarConnector` at `src/connectors/fomc_calendar.py` — thin adapter providing `FOMCMeeting` with `minutes_release_date` |
| **Status** | ✅ Capability 14.2 — Central Bank Calendar |

### 14.3 FOMCEvent Implementation
| Field | Value |
|-------|-------|
| **Purpose** | Implement `MacroEvent` subclass for Fed rate decisions. Condition columns for rate change direction (hike/cut/hold), dot plot sentiment. |
| **Reuse** | **Build** — implements existing `MacroEvent` ABC |
| **Dependencies** | 14.2 (FOMC Calendar), MacroEvent standard |
| **Complexity** | Medium |
| **Output** | `FOMCEvent`, `FOMCFeatureExtractor`, FOMC lesson dataset |
| **Status** | ✅ Capability 14.3 — FOMC Event |

### 14.4 GDP Event / PPI Event / Macro Regime Event
| Field | Value |
|-------|-------|
| **Purpose** | Additional macro event type implementations following the established pattern. |
| **Reuse** | **Build** — each implements `MacroEvent` ABC |
| **Status** | ✅ GDP Event (Cap 15.1), ✅ PPI Event (Cap 15.4), ✅ Macro Regime Intelligence (Cap 15.3) |
| **Complexity** | Low each |

### 14.5 PMI Event
| Field | Value |
|-------|-------|
| **Purpose** | Implement MacroEvent for Purchasing Managers' Index releases. |
| **Reuse** | **Build** — implements `MacroEvent` ABC |
| **Dependencies** | MacroEvent standard |
| **Complexity** | Low |
| **Status** | ✅ PMI Event (Cap 15.5) |

---

## Phase 15 — Advanced Context & Intelligence

### 15.0 Macro Regime Intelligence
| Field | Value |
|-------|-------|
| **Purpose** | Classify macro environment into 4 regimes (EXPANSION, LATE_CYCLE, CONTRACTION, RECOVERY) using a 4-regime Markov switching model on composite macro indicators. |
| **Reuse** | **Reuse** — `statsmodels.tsa.regime_switching.markov_regression.MarkovRegression` (BSD-3). Thin adapter wrapping `k_regimes=4, trend="c", switching_variance=True` with EM-based random search. |
| **Dependencies** | None (standalone regime classification) |
| **Complexity** | Medium |
| **Output** | `MacroRegimeDetector`, `MacroRegimeFeatureExtractor` implementing `FeatureExtractor` ABC |

### 15.1 FOMC Minutes NLP
| Field | Value |
|-------|-------|
| **Purpose** | Classify FOMC minutes/dot plots as hawkish/dovish/neutral. Feeds into FOMC feature extraction as a sentiment condition column. |
| **Reuse** | **Reuse** — `gtfintechlab/FOMC-RoBERTa` (HuggingFace, CC BY-NC 4.0). ACL 2023 paper, pre-trained for hawkish-dovish classification. Zero-shot usable via `pipeline()`. |
| **Dependencies** | 14.2 (FOMC Calendar), 14.3 (FOMCEvent) |
| **Complexity** | Low (single `pipeline()` call) |
| **Output** | `FOMCSentimentAnalyzer` at `src/nlp/fomc_sentiment.py` — thin adapter with lazy model loading, deterministic inference, `analyze()` and `analyze_batch()` |
| **Status** | ✅ Capability 15.1 — FOMC Minutes NLP |

### 15.2 News Data Pipeline
| Field | Value |
|-------|-------|
| **Purpose** | Fetch macro-relevant financial news (Fed, gold, USD, geopolitics) from RSS feeds/APIs. |
| **Reuse** | **Reuse** — `feedparser` (BSD, already installed). RSS feeds from Federal Reserve and Google News. No API key required. |
| **Dependencies** | None (feedparser is already installed) |
| **Complexity** | Low |
| **Output** | `NewsCollector` at `src/news/news_collector.py` — RSS + deterministic `data_source` mode, dedup by URL, sorted reverse-chronological |
| **Status** | ✅ Capability 15.2 — News Data Pipeline |

### 15.3 News Sentiment Engine
| Field | Value |
|-------|-------|
| **Purpose** | Score news articles for gold-positive/gold-negative/macro-relevant sentiment. |
| **Reuse** | **Reuse** — `tabularisai/ModernFinBERT` (HuggingFace, Apache 2.0). Outperforms FinBERT by up to 48% on FIQA/Twitter benchmarks. Single `pipeline()` call. |
| **Dependencies** | 15.2 (News Pipeline) |
| **Complexity** | Low |
| **Output** | `NewsSentimentAnalyzer` at `src/nlp/news_sentiment.py` — thin adapter, lazy loading, native batch inference (`batch_size=32`), custom model name override |
| **Status** | ✅ Capability 15.3 — News Sentiment Engine |

### 15.4 Technical Indicators Engine
| Field | Value |
|-------|-------|
| **Purpose** | Compute standard technical indicators (RSI, MACD, EMAs, Bollinger Bands) on gold/asset price data for feature extraction. |
| **Reuse** | **Build** — pure pandas implementation. Avoids `pandas-ta` transitive dependency on `numba` (compiled binary). RSI (Wilder's smoothing), MACD (12/26/9), EMAs (20/50/200), SMAs (20/50/200), Bollinger Bands (20, 2 with `ddof=1`). |
| **Dependencies** | Core v1.0 feature extraction framework |
| **Complexity** | Low |
| **Output** | `TechnicalIndicatorExtractor` at `src/technical/indicators.py` implementing `FeatureExtractor` ABC |
| **Status** | ✅ Capability 15.4 — Technical Indicators Engine |

---

## Phase 16 — Forecasting & Risk

### 16.1 Time Series Forecasting
| Field | Value |
|-------|-------|
| **Purpose** | Forecast macro indicators (CPI, GDP, unemployment) and gold price trends using statistical and ML models. Provides forecast features for reasoning. |
| **Reuse** | **Reuse** — `statsforecast` (Nixtla, MIT). 500x faster than Prophet. AutoARIMA, ETS, Theta, MSTL. |
| **Dependencies** | Historical data pipelines |
| **Complexity** | Low |
| **Output** | MacroForecaster adapter producing forecast feature columns |

### 16.2 Risk Management Engine
| Field | Value |
|-------|-------|
| **Purpose** | Portfolio-level risk assessment: VaR, CVaR, drawdown analysis, position sizing constraints. Feeds risk-weighted confidence into Decision Engine. |
| **Reuse** | **Adapt** — `Pyfolio` (Apache 2.0) for tear sheets + `squarequant` (MIT) for VaR/CVaR |
| **Dependencies** | All event types, Backtesting (17.1) |
| **Complexity** | Medium |

---

## Phase 17 — Validation & Backtesting

### 17.1 Backtesting Engine
| Field | Value |
|-------|-------|
| **Purpose** | Test AurumAI decision quality against historical data. Simulate decision→execution with realistic slippage, commissions, holding periods. |
| **Reuse** | **Adapt** — `vectorbt` (CC BY-NC 4.0) for fast vectorized backtesting or `backtrader` (GPL v3) for event-driven realism |
| **Dependencies** | All event types, all intelligence layers, LessonBuilder with multiple event types |
| **Complexity** | High |
| **Priority** | Before paper trading; after all macro events |

### 17.2 Portfolio Optimization
| Field | Value |
|-------|-------|
| **Purpose** | Optimize position allocation across multiple event-driven signals. Mean-variance, risk parity, or Black-Litterman integration. |
| **Reuse** | **Reuse** — `PyPortfolioOpt` (MIT, 5.9k stars) |
| **Dependencies** | 17.1 (Backtesting) |
| **Complexity** | Medium |

---

## Phase 18 — Execution

### 18.1 Broker Integration / Paper Trading
| Field | Value |
|-------|-------|
| **Purpose** | Connect AurumAI decisions to a broker for paper trading (simulated execution). Alpaca for US equities, Interactive Brokers for multi-asset. |
| **Reuse** | **Adapt** — `alpaca-py` (Apache 2.0) for US paper trading. `ib_insync` (BSD) for IB. |
| **Dependencies** | 17.1 (Backtesting passed), 16.2 (Risk Engine) |
| **Complexity** | High |
| **Output** | ExecutionEngine (last architectural layer per Constitution) |

---

## Phase 19 — Scaling & Production

### 19.1 Neo4j Knowledge Graph Migration
| Field | Value |
|-------|-------|
| **Purpose** | Replace NetworkX in-memory graph with Neo4j for persistence, Cypher queries, and production-scale graph operations. |
| **Reuse** | **Adapt** — `neo4j` Python driver + `neo4j-graphrag-python` (Apache 2.0) |
| **Dependencies** | Core v1.0 Graph module (replaceable interface) |
| **Complexity** | Medium |

### 19.2 Vector Database for RAG
| Field | Value |
|-------|-------|
| **Purpose** | Store knowledge records as embeddings for semantic similarity search across lessons, enabling natural-language knowledge queries. |
| **Reuse** | **Reuse** — `ChromaDB` (Apache 2.0, dev) → `Qdrant` (Apache 2.0, production) |
| **Dependencies** | Knowledge records, Lesson text |
| **Complexity** | Medium |

### 19.3 Production Hardening
| Field | Value |
|-------|-------|
| **Purpose** | Monitoring, alerting, logging, configuration management, deployment automation, API surface. |
| **Reuse** | **Build** — infrastructure-specific |
| **Dependencies** | All above |
| **Complexity** | High |

---

## Dependency Graph (Text Summary)

```
Core v1.0 (frozen)
  │
  ├──12. Stabilization Gates──────────No downstream deps (prerequisite)
  │
  ├──13.1 DXY Context─────────────────No downstream deps
  ├──13.2 Economic Calendar───────────Supports 14.1, 14.4
  ├──13.3 Multi-Event Comparison──────Depends on 13.1
  │
  ├──14.1 NFP Event──────────────────Depends on 13.2
  ├──14.2 FOMC Calendar───────────────✅ (Cap 14.2)
  ├──14.3 FOMC Event─────────────────✅ (Cap 14.3)
  ├──14.4 GDP Event / PPI Event / Regime───✅ (14.1, 15.4, 15.3)
├──14.5 PMI Event────────────────────────✅ (Cap 15.5)
  │
  ├──15.1 FOMC NLP───────────────────✅ (Cap 15.1)
  ├──15.2 News Pipeline──────────────✅ (Cap 15.2)
  ├──15.3 News Sentiment─────────────✅ (Cap 15.3)
  ├──15.4 Technical Indicators───────✅ (Cap 15.4)
  │
  ├──16.1 Time Series Forecasting────No downstream deps
  ├──16.2 Risk Engine────────────────Depends on 17.1
  │
  ├──17.1 Backtesting────────────────Depends on 14.x (multiple events)
  ├──17.2 Portfolio Optimization─────Depends on 17.1
  │
  ├──18.1 Broker/Paper Trading───────Depends on 17.1, 16.2
  │
  └──19.1–19.3 Scaling──────────────Depends on all above
```
