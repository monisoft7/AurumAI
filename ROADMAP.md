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

## Phase 16 — Forecasting

### 16.1 Time Series Forecasting
| Field | Value |
|-------|-------|
| **Purpose** | Forecast macro indicators (CPI, GDP, unemployment) and gold price trends using statistical models. Provides forecast features for reasoning. |
| **Reuse** | **Reuse** — `statsforecast` (Nixtla, Apache 2.0). AutoARIMA, AutoETS, AutoTheta. |
| **Dependencies** | Historical data pipelines |
| **Complexity** | Low |
| **Output** | `MacroForecaster` at `src/forecasting/macro_forecaster.py` — thin adapter wrapping StatsForecast. `ForecastResult` frozen dataclass with forecast values + 95% prediction intervals. |
| **Status** | ✅ Capability 16.1 — Time Series Forecasting |

### 16.2 Risk Intelligence (Phase 17)
| Field | Value |
|-------|-------|
| **Purpose** | Portfolio-level risk assessment: VaR, CVaR, tail-risk detection, drawdown analysis, position sizing constraints. Feeds risk-weighted confidence into Decision Gate. |
| **Reuse** | **Build** — pure numpy/pandas implementation. VaR/CVaR (~50 lines), TailRiskDetector (~80 lines). Zero new dependencies. |
| **Dependencies** | Forecast Intelligence (ForecastConfidence, ForecastContext, ForecastValidator) |
| **Complexity** | Medium |
| **Status** | ✅ Phase 17.1 Complete (Core Risk Measures) |

---

## Phase 17 — Risk Intelligence

Risk Intelligence is an **advisory layer**. It evaluates institutional risk. It does NOT make trading decisions. DecisionEngine remains the only component allowed to issue decisions. Execution remains outside Phase 17.

### 17.1 Core Risk Measures ✅
| Field | Value |
|-------|-------|
| **Purpose** | VaR (historical + parametric), CVaR, tail-risk detection via Peaks-over-Threshold EVT. `RiskMetrics` frozen dataclass. |
| **Reuse** | **Build** — pure numpy + math. No external dependencies beyond project std. |
| **Dependencies** | None |
| **Complexity** | Low |
| **Output** | `RiskMetrics`, `compute_var`, `compute_cvar`, `TailRiskDetector` at `src/forecasting/risk_measures.py` |
| **Tests** | 36 tests |

### 17.2 Position Sizing ✅
| Field | Value |
|-------|-------|
| **Purpose** | Volatility-targeted position sizing with drawdown override and fractional Kelly cap. |
| **Reuse** | **Build** — pure numpy/pandas. ~110 lines. |
| **Dependencies** | 17.1 (Risk Measures) |
| **Complexity** | Low |
| **Output** | `VolatilityTargetSizer`, `DrawdownManager`, `KellyCap`, `PositionSizing` frozen dataclass at `src/forecasting/position_sizing.py` |
| **Tests** | 27 tests |

### 17.3 Risk Budgeting ✅
| Field | Value |
|-------|-------|
| **Purpose** | Risk parity allocation via damped iterative solver. Equalizes risk contribution across positions. |
| **Reuse** | **Adapt** — algorithm from Spinu (2013), implemented in pure numpy. ~80 lines. |
| **Dependencies** | 17.1 (Risk Measures) |
| **Complexity** | Medium |
| **Output** | `RiskParitySizer`, `RiskBudget` frozen dataclass at `src/forecasting/risk_budgeting.py` |
| **Tests** | 15 tests |

### 17.4 Decision Gate ✅
| Field | Value |
|-------|-------|
| **Purpose** | State machine that answers 5 questions: trust forecast? act now? regime too risky? uncertainty acceptable? delay execution? |
| **Reuse** | **Build** — consumes existing ForecastContext, ForecastConfidence. ~90 lines. |
| **Dependencies** | 17.1, 17.2, 17.3, Forecast Intelligence |
| **Complexity** | Medium |
| **Output** | `RegimeRiskOverlay`, `UncertaintyBudget`, `DecisionGate`, `RiskDecision` frozen dataclass at `src/forecasting/decision_gate.py` |
| **Tests** | 27 tests |

### 17.5 Integration ✅
| Field | Value |
|-------|-------|
| **Purpose** | Full pipeline integration tests: Forecast Intelligence → Risk Intelligence. Verify end-to-end determinism and consistency. |
| **Reuse** | **Build** |
| **Dependencies** | 17.1–17.4, Forecast Intelligence |
| **Complexity** | Low |
| **Tests** | 12 integration tests |

---

## Phase 18 — Execution

### 18.1 Broker Integration
| Field | Value |
|-------|-------|
| **Purpose** | Connect AurumAI decisions to live broker APIs. Alpaca for US equities, Interactive Brokers for multi-asset. *Paper trading core moved to Phase 21.1.* |
| **Reuse** | **Adapt** — `alpaca-py` (Apache 2.0) for US paper trading. `ib_insync` (BSD) for IB. |
| **Dependencies** | 21.1 (Paper Trading Core), 21.3 (Execution Engine), 21.2 (Slippage & Commission), Phase 17 (Risk Intelligence) |
| **Complexity** | High |
| **Output** | Broker adapter implementations |

---

## Phase 20 — Hardening (Phases 20.1–20.5 Complete)

### 20.1 Determinism Hardening (Complete)
| Field | Value |
|-------|-------|
| **Purpose** | Make EvidenceWeighter, MacroRegimeDetector, and ForecastEvidence fully deterministic. `EvidenceWeighter` accepts `as_of` parameter for stable weight vectors. `MacroRegimeDetector.fit()` saves/restores global random state. `ForecastEvidence.evidence_id` no longer depends on `created_at`. |

### 20.2 Data Integrity — FrozenDict & Atomic Writes (Complete)
| Field | Value |
|-------|-------|
| **Purpose** | Add runtime immutability for mutable dict fields via `FrozenDict` across ~25 frozen dataclasses. Replace all `path.write_text(json.dumps(...))` with `atomic_write_json()` (write-to-tmp + atomic rename) across 11 files. 70 new tests. |

### 20.3 Performance Hardening — GraphBuilder Optimization (Complete)
| Field | Value |
|-------|-------|
| **Purpose** | Replace O(n²) all-pairs comparison in `GraphBuilder.build()` with indexed grouping by dimension (event_type, condition, horizon_days). O(n) grouping + O(k²) per group. No other O(n²) algorithms found in src/. 16 new benchmark/correctness tests. 1384 total tests (zero regressions). |

### 20.4 Maintainability Hardening — Orchestrator Module Split (Complete)
| Field | Value |
|-------|-------|
| **Purpose** | Split 810-line `institutional_orchestrator.py` into 6 cohesive modules (`cache.py`, `checkpoints.py`, `jobs.py`, `dag.py`, `stages.py`, `orchestrator.py`) with backward-compatible shim. 1384 tests (zero regressions). |

### 20.5 Packaging Hardening — Reproducible Build (Complete)
| Field | Value |
|-------|-------|
| **Purpose** | Audit `pyproject.toml`: removed 3 unused deps (fredapi, python-dotenv, yfinance), added 3 missing deps (statsmodels, statsforecast, feedparser), pinned `requires-python = ">=3.10"`. Verified clean installation in fresh venv. All 27 package imports verified. 1384 tests (zero regressions). |

---

## Phase 21 — Paper Trading

### 21.1 Paper Trading Core (Complete)
| Field | Value |
|-------|-------|
| **Purpose** | Implement `VirtualPortfolio` with cash balance, open/closed positions, buy/sell/short/cover operations, weighted-average cost basis, unrealized/realized PnL, equity computation. Immutable models (`VirtualPosition`, `VirtualTrade`, `PortfolioSnapshot`) with `to_dict()` serialization. |
| **Reuse** | **Build** — pure dataclasses. No new runtime dependencies beyond pandas/numpy. |
| **Dependencies** | None (standalone package) |
| **Complexity** | Low |
| **Output** | `src/execution/` package with `VirtualPortfolio`, `VirtualPosition`, `VirtualTrade`, `PortfolioSnapshot` |
| **Tests** | 63 tests (1447 total, zero regressions) |

### 21.2 Slippage & Commission (Complete)
| Field | Value |
|-------|-------|
| **Purpose** | Add configurable slippage model (fixed per-unit, percentage) and commission model (fixed per-trade, percentage with optional minimum) to `VirtualPortfolio`. |
| **Dependencies** | 21.1 (Paper Trading Core) |
| **Tests** | 66 tests (1513 total, zero regressions) |

### 21.3 Execution Engine (Complete)
| Field | Value |
|-------|-------|
| **Purpose** | Bridge between DecisionGate → VirtualPortfolio. Translates risk-weighted decisions into portfolio actions with slippage, commission, and risk gating. |
| **Dependencies** | 21.1, 21.2, Phase 17 (Risk Intelligence) |
| **Tests** | 38 tests (1551 total, zero regressions) |

### 21.4 Broker Adapter Interface (Planned)
| Field | Value |
|-------|-------|
| **Purpose** | Abstract broker adapter protocol with real-time order execution, position sync, account feed. Alpaca (US equities) and Interactive Brokers (multi-asset) implementations. |
| **Dependencies** | 21.3, broker SDKs |

---

## Phase 19 — Scaling & Production (Planned)

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
  ├──16.1 Time Series Forecasting────✅ (Cap 16.1)
  ├──16.2 Risk Intelligence──────────✅ (Phase 17.1 complete)
  │
  ├──17.1 Core Risk Measures─────────✅ (Phase 17.1, 36 tests)
  ├──17.2 Position Sizing────────────Depends on 17.1
  ├──17.3 Risk Budgeting─────────────Depends on 17.1
  ├──17.4 Decision Gate──────────────Depends on 17.1–17.3, Forecast Intelligence
  ├──17.5 Integration───────────────Depends on 17.1–17.4
  │
  ├──18.1 Broker/Paper Trading───────Depends on 17.x, 16.x
  │
  ├──20.1–20.5 Hardening────────────Depends on Core v1.0
  │
  ├──21.1 Paper Trading Core─────────✅ (63 tests, standalone)
  ├──21.2 Slippage & Commission──────✅ (66 tests, standalone)
  ├──21.3 Execution Engine──────────✅ (38 tests, standalone)
  │
  └──19.1–19.3 Scaling──────────────Depends on all above
```
