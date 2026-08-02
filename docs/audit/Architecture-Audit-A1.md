# Architecture Audit Report A1 — Repository Inventory

**Auditor**: opencode (Phase A1)
**Date**: 2026-07-31
**Scope**: Full `src/` inventory, dependency analysis, workflow (W1–W13) contract verification
**Mode**: AUDIT ONLY — no code modified, no commits created
**Method**: AST-based static import analysis (265 modules parsed), reachability analysis from tests/scripts entry points, documentation cross-reference (`IMPLEMENTATION_WORKFLOWS.md`, `IMPLEMENTATION_MAPPING.md`, `INSTITUTIONAL_CONTRACTS.md`, `W1_W2_INTEGRATION_REVIEW.md`, `CURRENT_STATE.md`), manual code review of the orchestration hub.

---

## 1. Repository Structure

```
AurumAI/
├── src/                          # 20 packages, 265 modules, 30,391 LOC
│   ├── confidence_engine/        # (W9) confidence assignment
│   ├── connectors/               # data connectors (FRED, yahoo, IMF, FOMC)
│   ├── counter_evidence/         # (W7) conflict detection & counter-evidence
│   ├── decision_engine/          # institutional decision (BUY/SELL/HOLD/NO TRADE)
│   ├── evidence_collection/      # (W6) evidence collection
│   ├── evidence_reasoning/       # (W7) evidence reasoning & weighting
│   ├── execution/                # paper trading (portfolio, slippage, commission)
│   ├── forecasting/              # forecast models, confidence, risk, sizing
│   ├── knowledge/                # core brain — 35 subpackages, ~24k LOC
│   ├── news/                     # RSS news collection
│   ├── nlp/                      # news/FOMC sentiment
│   ├── orchestration/            # InstitutionalOrchestrator + stages (DAG runtime)
│   ├── pre_market/               # (W3) pre-market briefing
│   ├── risk_reward_validation/   # risk/reward validator
│   ├── scenario_generation/      # base/bull/bear scenario generation
│   ├── signal_assessment/        # (W5) signal vs noise
│   ├── simulation/               # historical replay, experiments, validation
│   ├── technical/                # technical indicators
│   ├── thesis_construction/      # (W8) thesis construction
│   └── trade_recommendation/     # trade recommendation engine
├── tests/                        # 96 test files (~30k LOC)
├── scripts/                      # 9 scripts (experiments, data downloads, validation)
├── docs/                         # AOS, ADRs, architecture, audit trail
├── AOS/                          # project operating system docs (11 files)
├── research/  data/  archive/    # knowledge base, datasets, archived docs
└── *.md                          # 20+ root-level governance/status documents
```

### Headline numbers

| Metric | Value |
|---|---|
| Packages under `src/` | 20 (plus root `__init__.py`) |
| Modules (incl. `__init__`) | 265 |
| Total LOC (src) | 30,391 |
| Cross-package dependency edges | 52 |
| Packages in one cyclic SCC | 15 of 19 (all except connectors, news, nlp, technical) |
| Module-level circular imports | 0 |
| Package-level cycles (enumerated) | 875 (all variants of the single SCC) |
| Unused modules (unreachable from tests/scripts) | 8 non-`__init__` + 5 orphaned `__init__` wrappers |
| Oversized modules (>500 LOC) | 5 |
| Oversized functions (>100 LOC) | 10 |
| Oversized dataclasses (>15 fields) | 12 |
| Undeclared third-party deps | 2 (`sklearn`, `transformers`) |

---

## 2. Package Inventory

### 2.1 `confidence_engine` (434 LOC, 4 modules)
- **Purpose**: W9-style confidence assignment — `ConfidenceComputer`, `ConfidenceEngine`, `ConfidenceRanker` + `contracts` (`InstitutionalConfidence`, `ThesisConfidence`).
- **Public API**: `ConfidenceComputer`, `ConfidenceEngine`, `ConfidenceRanker`, `InstitutionalConfidence`, `ThesisConfidence`.
- **Internal modules**: `computer.py`, `contracts.py`, `engine.py`, `ranker.py`.
- **Dependencies**: `knowledge` (provenance, `_compat`), `counter_evidence`, `thesis_construction`.
- **Dependents**: `orchestration` (stage `_confidence_engine`), `scenario_generation`, `decision_engine`.
- **Notes**: Consumes ONLY `ThesisConstruction` — none of the W9-documented inputs (regime, OOS ECE, window consistency, W12 downside case).

### 2.2 `connectors` (615 LOC, 5 modules)
- **Purpose**: External data access — `FredClient`, `DXYFetcher`, `RealYieldFetcher`, `FOMCCalendarConnector`, `CBGoldReserveFetcher`.
- **Public API**: classes above; `EconomicDataFetcher`.
- **Internal modules**: `cb_gold_fetcher.py`, `dxy_fetcher.py`, `fomc_calendar.py`, `fred_client.py`, `real_yield_fetcher.py`.
- **Dependencies**: none (leaf package).
- **Dependents**: `knowledge` (events, regime), `orchestration`, `pre_market`.
- **Notes**: `cb_gold_fetcher.py` is UNUSED (no importer anywhere, including tests).

### 2.3 `counter_evidence` (382 LOC, 4 modules)
- **Purpose**: W7 conflict resolution — `BiasAnalyzer`, `CounterEvidenceAssessor`, `ConflictDetector`, `contracts`.
- **Public API**: `BiasAnalyzer`, `CounterEvidenceAssessor`, `ConflictDetector`, `CounterEvidenceAssessment`.
- **Internal modules**: `analyzer.py`, `assessor.py`, `contracts.py`, `detector.py`.
- **Dependencies**: `evidence_reasoning`, `knowledge` (provenance, `_compat`).
- **Dependents**: `confidence_engine`, `orchestration`, `thesis_construction`.
- **Notes**: wired into production chain (after evidence_reasoning).

### 2.4 `decision_engine` (689 LOC, 3 modules)
- **Purpose**: Institutional decision — scores theses, produces BUY/SELL/HOLD/NO TRADE.
- **⚠️ Docstring declares "W12 Institutional Decision Engine" — ID collision with official W12 (Fragility Audit).**
- **Public API**: `DecisionEngine`, `InstitutionalDecision`, `DecisionDriver`, `RejectedAlternative` + constants.
- **Internal modules**: `contracts.py`, `engine.py` (with `decide()` = 119 LOC, oversized).
- **Dependencies**: `confidence_engine`, `risk_reward_validation`, `scenario_generation`, `thesis_construction`, `knowledge` (provenance, `_compat`).
- **Dependents**: `orchestration`, `trade_recommendation`.
- **Notes**: Second `DecisionEngine` class in the codebase (see `knowledge/decision/engine.py`) — parallel decision path.

### 2.5 `evidence_collection` (438 LOC, 3 modules)
- **Purpose**: W6 evidence collection from signal assessments.
- **Public API**: `EvidenceCollector`, `EvidenceCollection`, `Evidence` (20-field variant).
- **Internal modules**: `collector.py`, `contracts.py`, `strength.py`.
- **Dependencies**: `knowledge` (graph, provenance, `_compat`), `signal_assessment`.
- **Dependents**: `evidence_reasoning`, `orchestration`.
- **Notes**: `contracts.Evidence` (20 fields) duplicates the frozen `knowledge/evidence/evidence.py::Evidence` (12 fields) — both claim canonical status.

### 2.6 `evidence_reasoning` (456 LOC, 5 modules)
- **Purpose**: W7 reasoning — `EvidenceReasoner`, `EvidenceSet`, detector, grouper, weighting.
- **Public API**: `EvidenceReasoner`, `EvidenceSet`, `EvidenceReasoning`, `EvidenceWeighter` (different math from the frozen `knowledge/evidence/weighting.py::EvidenceWeighter` — duplicate name, divergent semantics).
- **Internal modules**: `contracts.py`, `detector.py`, `grouper.py`, `reasoner.py`, `weighter.py`.
- **Dependencies**: `evidence_collection`, `knowledge` (`_compat`).
- **Dependents**: `counter_evidence`, `orchestration`, `thesis_construction`, `confidence_engine` (computer), `scenario_generation`? (no — via contracts only).

### 2.7 `execution` (999 LOC, 6 modules)
- **Purpose**: Paper trading — `VirtualPortfolio`, `ExecutionEngine`, slippage, commission.
- **Public API**: `VirtualPortfolio`, `ExecutionEngine`, `VirtualPosition`, `VirtualTrade`, `PortfolioSnapshot`, slippage/commission models.
- **Internal modules**: `commission.py`, `execution_engine.py`, `models.py`, `portfolio.py`, `slippage.py`.
- **Dependencies**: none local (leaf).
- **Dependents**: **NONE in src/** — test-only package; not wired into the orchestrator or any runtime path.
- **Notes**: `execution_engine.evaluate()` = 102 LOC (oversized).

### 2.8 `forecasting` (1,815 LOC, 16 modules)
- **Purpose**: Statistical forecasting, confidence, risk measures, position sizing, decision gate, OOS validation, registry.
- **Public API**: `MacroForecaster`, `ForecastConfidenceComputer`, `ForecastContextBuilder`, `ForecastKnowledge`, `ForecastRegistry`, `ForecastValidator`, `ChronologicalOOSEngine`, `DecisionGate`, `RegimeRiskOverlay`, `UncertaintyBudget`, `VolatilityTargetSizer`, `RiskParitySizer`, `DrawdownManager`, `KellyCap`, risk measures.
- **Internal modules**: `confidence.py`, `context.py`, `decision_gate.py`, `evidence.py`, `knowledge.py`, `macro_forecaster.py`, `models.py`, `position_sizing.py`, `provenance.py`, `reasoning.py`, `registry.py`, `risk_budgeting.py`, `risk_measures.py`, `validation.py`.
- **Dependencies**: `knowledge` (regime, `_compat`), `nlp` (sentiment).
- **Dependents**: `orchestration` (stages), `pre_market` (risk_reporter).
- **Notes**: Heaviest non-knowledge package; no oversized functions flagged.

### 2.9 `knowledge` (~24,000 LOC, 150+ modules, 35 subpackages)
- **Purpose**: The core brain — events, lessons, evidence, reasoning, decision, graph, regime, pipeline, integrity/provenance, intelligence layers (CBI/CFI/CAI/Economic/Temporal/Causal), expansion, learning, benchmark, factors, features.
- **Key subpackages**: `events` (MacroEvent ABC, CPI/NFP/GDP/PPI/PMI/FOMC events, EventRegistry, ReleaseCalendar), `pipeline` (`InferencePipeline` — frozen v1.0), `reasoning` (`ReasoningEngine`, `ReasoningChain` — frozen), `decision` (`DecisionEngine` v1.0 — frozen, used by pipeline), `evidence` (Evidence, EvidenceQuery, EvidenceWeighter, WeightedAggregate — frozen), `graph` (KnowledgeGraph, GraphBuilder), `integrity` (KnowledgeRecord 35 fields, Provenance, LineageRegistry, VersionedStore), `regime` (MacroRegimeDetector, InstitutionalRegimeDetector, CompositeScore, IndicatorHierarchy, RegimeTransition, GramResidualAnalyzer), `causal` (CausalGraph, CausalAnalyzer), `cbi/cfi/cai` (intelligence contracts + adapters), `benchmark` (18-benchmark suite), `expansion` (EventScaffolder 514 LOC, EventValidator, ExpansionLifecycle), `ingestion` (W1 — ORPHANED), `orchestration` (OrchestrationEngine — production-dead, test-only), `factors` (contracts, adapters, publisher — publisher dead), `temporal`, `economics`, `context`, `features`, `learning`, `evolution`, `builders`, `lesson_summary`, `brain`, `memory`, `rules`.
- **Dependencies**: `connectors`, `simulation` (⚠️ back-edge via `evolution/applicator.py`).
- **Dependents**: every analytic package (12 packages import `knowledge`).
- **Notes**: De-facto "shared hub" — every contracts module imports `knowledge._compat` + `knowledge.integrity.provenance`, making `knowledge` the coupling center of the whole graph.

### 2.10 `news` (155 LOC, 2 modules)
- **Purpose**: RSS news — `NewsArticle`, `NewsCollector`.
- **Public API**: `NewsCollector`, `NewsArticle`, `Topic`.
- **Dependencies**: none. **Dependents**: `pre_market`.
- **⚠️ Module is `news/news_collector.py`, but `orchestration/stages.py` imports `news.collector` — broken import, silently swallowed.**

### 2.11 `nlp` (145 LOC, 2 modules)
- **Purpose**: `NewsSentimentAnalyzer`, `FOMCSentimentAnalyzer` (lazy `transformers` — undeclared dependency).
- **Dependencies**: none local. **Dependents**: `forecasting`, `pre_market`.

### 2.12 `orchestration` (1,344 LOC, 8 modules)
- **Purpose**: Production runtime — `InstitutionalOrchestrator` (DAG job runner with cache/checkpoints/thread pool), 21 stage functions in `stages.py` (636 LOC — oversized).
- **Public API**: `InstitutionalOrchestrator` (+ `with_default_pipeline`), `PipelineJob`, `CacheManager`, `CheckpointManager`, `InstitutionalAssessment`.
- **Dependencies**: every analytic package (stages hub).
- **Dependents**: `simulation` (⚠️ back-edge via `historical_replay.py`).
- **Notes**: `institutional_orchestrator.py` is a re-export facade. The stage hub makes `orchestration` the second coupling center after `knowledge`.

### 2.13 `pre_market` (887 LOC, 9 modules)
- **Purpose**: W3 pre-market briefing — assembler, overnight fetcher, news ingestion, risk reporter, positioning, anomaly detector, watchlist builder.
- **Public API**: `PreMarketBriefingAssembler`, `PreMarketBriefing`, `OvernightDataFetcher`, `OvernightNewsIngestion`, `RiskReportGenerator`, `PositioningDataFetcher`, `AnomalyDetectionEngine`, `WatchlistBuilder`.
- **Dependencies**: `connectors`, `forecasting`, `news`, `nlp`, `knowledge` (`_compat`).
- **Dependents**: `orchestration`, `signal_assessment`.
- **Notes**: Best-structured workflow package (7 stages match the W3 doc).

### 2.14 `risk_reward_validation` (466 LOC, 3 modules)
- **⚠️ Docstring declares "W11 Institutional Risk / Reward Validation" — ID collision with official W11 (Causal Evaluation).**
- **Dependencies**: `knowledge`, `scenario_generation`. **Dependents**: `orchestration`, `decision_engine`.

### 2.15 `scenario_generation` (473 LOC, 3 modules)
- **⚠️ Docstring declares "W10 Institutional Scenario Generation" — ID collision with official W10 (Thesis Update Cycle).**
- **Purpose**: base/bull/bear scenarios from thesis + confidence.
- **Dependencies**: `confidence_engine`, `thesis_construction`, `knowledge`. **Dependents**: `orchestration`, `risk_reward_validation`, `decision_engine`.
- **Notes**: W12-documented inputs (failure conditions, base rates, fragility score) not present.

### 2.16 `signal_assessment` (819 LOC, 8 modules)
- **Purpose**: W5 signal vs noise — assembler (157-LOC `assemble()`), breadth, classifier, narrative, persistence, volume.
- **Dependencies**: `knowledge` (`_compat`), `pre_market` (contracts). **Dependents**: `evidence_collection`, `orchestration`.

### 2.17 `simulation` (3,769 LOC, 8 modules)
- **Purpose**: Historical replay (1,643 LOC), experiment framework + registry (583/522 LOC), validation, economic summary, attribution.
- **Dependencies**: `knowledge` (`_compat`), `orchestration` (⚠️). **Dependents**: `knowledge` (⚠️ via applicator).
- **Notes**: Source of BOTH cycle-breaking back-edges.

### 2.18 `technical` (136 LOC, 1 module)
- **Purpose**: Technical indicators.
- **Dependencies**: `knowledge` (features). **Dependents**: **NONE in src/** — test-only.

### 2.19 `thesis_construction` (431 LOC, 4 modules)
- **Purpose**: W8 thesis — `ThesisConstructor`, `ThesisBuilder`, contracts (`InvestmentThesis`, `ThesisConstruction`).
- **Dependencies**: `counter_evidence`, `evidence_reasoning`, `knowledge`. **Dependents**: `confidence_engine`, `scenario_generation`, `decision_engine`, `orchestration`.
- **Notes**: No fragility-audit (W12) invocation as documented in W8 stage 4.

### 2.20 `trade_recommendation` (390 LOC, 3 modules)
- **⚠️ Docstring declares "W13 Institutional Trade Recommendation (final AurumAI v1.0 workflow)" — ID collision with official W13 (Bias Prevention & Decision Review).**
- **Dependencies**: `decision_engine`, `knowledge`. **Dependents**: `orchestration`.

---

## 3. Repository Dependency Map

```
connectors ──► knowledge ──► forecasting ──► pre_market ──► signal_assessment ──► evidence_collection
     ▲            ▲               │               ▲              │                     │
     │            │               │               │              ▼                     ▼
     └────────────┴───────────────┴──────────────► orchestration ◄── evidence_reasoning ◄──┘
     (leaf)                       (leaf news)         │   │    ▲            │
                                                        │   │    └────────────┘
        knowledge ──► simulation ──► orchestration       │   │
             ▲          │                                │   │
             └──────────┘  (CYCLE EDGE 1)                │   │
        simulation ──► orchestration  (CYCLE EDGE 2)     │   │
                                                         ▼   ▼
        confidence_engine ─► scenario_generation ─► risk_reward_validation ─► decision_engine ─► trade_recommendation
             ▲                      │                        │                     │
             └──────────────────────┴────────────────────────┴─────────────────────┘
```

**Package-level edges (52 total).** The dependency graph is a layered web with **two coupling hubs** (`knowledge` = foundation hub; `orchestration` = runtime hub) and **one giant strongly-connected component of 15 packages**:

> confidence_engine, counter_evidence, decision_engine, evidence_collection, evidence_reasoning, forecasting, knowledge, orchestration, pre_market, risk_reward_validation, scenario_generation, signal_assessment, simulation, thesis_construction, trade_recommendation

**Acyclic leaves**: `connectors`, `news`, `nlp`, `technical`.

**The two edges that cause the entire SCC** (removing just these two makes the whole graph a DAG):
1. `knowledge/evolution/applicator.py → simulation/models.py` (foundation importing the top layer — `FeedbackApplicator` consumes `EventRunResult`).
2. `simulation/historical_replay.py → orchestration/institutional_orchestrator.py` (replay engine instantiating the production orchestrator).

**No module-level circular imports** (0 exact module cycles) — imports are arranged so modules load fine; the cycles exist only at package granularity.

---

## 4. Workflow Dependency Map (W1 → W13)

### 4.1 Documented topology (`IMPLEMENTATION_WORKFLOWS.md`)

```
W1 (KR Ingestion) ─► W2 (Regime) ─► W3 (Pre-Market) ─► W4 (Event Triage)
W1 ─► W5 ─► W6 ─► W7 ─► W8 ─► W9 ─► W10 (Thesis Update) ─► W14
W8 ─► W12 (Fragility) ─► W9          (W9 consumes W12's downside case)
W8 ─► W13 (Bias Prevention); W10 ─► W13
W1,W2 ─► W11 (Causal Eval); W3,W2,W1 ─► W15; W1,W2 ─► W16
```

Key documented contracts:
- W9 consumes: W8 thesis, W6 evidence, W2 regime clarity, W12 downside case, W16 window consistency, OOS ECE.
- W12 is invoked BY W8 (stage 4, fragility audit) BEFORE W9.
- W13 gates finalization after W8 and W10.
- W10 is triggered by W3/W5 and re-invokes W6, W9, W12.

### 4.2 Actual wiring (production DAG in `orchestration/orchestrator.py::with_default_pipeline`)

```
pre_market_scan (W3) ─► signal_assessment (W5) ─► evidence_collection (W6) ─► evidence_reasoning (W7) ─► counter_evidence (W7)
        ─► thesis_construction (W8) ─► confidence_engine (W9)
        ─► thesis_construction (W8) ─► scenario_generation (≈W12) ─► risk_reward_validation ─► decision_engine ─► trade_recommendation
ingest_event ─► build_legacy_pipeline (InferencePipeline: W1/W4/W6/W8 legacy chain)
ingest_event ─► forecast ─► {forecast_confidence, forecast_validation, build_context, risk_measures ─► position_sizing}
risk_gate ─ (build_context, build_legacy_pipeline, risk_measures); finalize ─ (risk_gate, position_sizing, forecast_confidence, forecast_validation)
```

### 4.3 Workflow implementation status

| WF | Official name | Status | Implementing modules |
|----|---------------|--------|----------------------|
| W1 | KR Ingestion & Encoding | **IMPLEMENTED, ORPHANED** | `knowledge/ingestion/*` (3 modules) — no importer; `to_evidence()` uses a `type()` hack (ad-hoc, documented non-functional in `W1_W2_INTEGRATION_REVIEW.md`) |
| W2 | Regime Diagnosis | Implemented (partial) | `knowledge/regime/*`; GRAM residual analyzer exists but is unwired (`gram_residual.py` unused; detector takes `gram_residual_series` param nothing computes) |
| W3 | Pre-Market Scan | Implemented | `pre_market/*`; wired as root job |
| W4 | Event Prioritization & Triage | **NOT IMPLEMENTED** | Only event classes + registry exist; no tier classification, no trigger levels, no watchlist scoring |
| W5 | Signal vs Noise | Implemented | `signal_assessment/*` |
| W6 | Evidence Collection & Weighting | Implemented (partial) | `evidence_collection/*`; regime weight passed as untyped param; knowledge_graph never provided in default DAG |
| W7 | Conflict Resolution | Implemented | `evidence_reasoning/*`, `counter_evidence/*` |
| W8 | Thesis Formation | Implemented (partial) | `thesis_construction/*`; no fragility-audit (W12) invocation, no narrative step |
| W9 | Confidence & OOS Calibration | Implemented (partial) | `confidence_engine/*`; consumes ONLY thesis — no regime/W6/W12/W16/OOS inputs |
| W10 | Thesis Update Cycle | **NOT IMPLEMENTED** | — (ID hijacked by `scenario_generation`) |
| W11 | Causal Evaluation & Graph Maintenance | Implemented (partial) | `knowledge/causal/*`; 5-criteria classifier not present (ID hijacked by `risk_reward_validation`) |
| W12 | Fragility Audit & Scenario Analysis | Partial | `scenario_generation/*` (base/bull/bear only; no assumption extraction, base rates, fragility score) — runs AFTER W9 (documented: before W9) |
| W13 | Bias Prevention & Decision Review | **NOT IMPLEMENTED** | — (ID hijacked by `trade_recommendation`) |

### 4.4 Contract consumption verification (per documented upstreams)

| WF | Documented upstreams | Consumed in code? | Verdict |
|----|---------------------|-------------------|---------|
| W2 | W1 (KRs) | No — detector is KR-agnostic | Under-consumption (Medium) |
| W3 | W2 regime, W1 news relevance | Regime via untyped orchestrator param (empty by default); W1 KRs not consumed | Bypass (High) |
| W4 | W2, W3, W1 | N/A — not implemented | Missing (Critical) |
| W5 | W3, W2, W1, W15 | W3 briefing yes; W2 via param; W1/W15 no | Partial (Medium) |
| W6 | W1, W2, W5, W3, W15 | W5 yes; W1 knowledge_graph param NEVER set in default DAG (`params.get("knowledge_graph")` → `None`) | **Bypass of W1 contract (High)** |
| W7 | W6, W1, W2, W5 | W6 yes; W1/W2/W5 no | Partial (Medium) |
| W8 | W6, W7, W2, W5, W1, W12 | W6/W7 yes; W12 fragility NOT invoked; regime/narrative no | Under-consumption (High) |
| W9 | W8, W6, W2, W12, W16 | W8 only | **Under-consumption (High)** |
| W10 | W3, W5, W6, W8 | N/A — not implemented | Missing (Critical) |
| W11 | W1, W2 | Partial (causal graph from KRs) | Partial (Medium) |
| W12 | W8, W6, W2, W1 | W8 + W9 (inverted order) | **Ordering violation (High)** |
| W13 | W8/W10, W6, W5, W12 | N/A — not implemented | Missing (Critical) |

---

## 5. Detected Issues

### 5.1 Workflow identity contract violation (CRITICAL)

**A-001** — Four packages embed W-labels in their docstrings that collide with different official workflows:
- `scenario_generation` self-declares **W10** (official W10 = Thesis Update Cycle)
- `risk_reward_validation` self-declares **W11** (official W11 = Causal Evaluation)
- `decision_engine` self-declares **W12** (official W12 = Fragility Audit)
- `trade_recommendation` self-declares **W13** (official W13 = Bias Prevention)

Every audit/compliance trace that relies on W-IDs (W17 auditor interface, wave completion docs, engineering rules) is ambiguous. Impact: auditability contract broken.

### 5.2 Missing workflows (CRITICAL)

**A-002** — W4 (Event Prioritization & Triage): no tier classifier, no trigger-level engine, no watchlist scoring — only the raw event registry exists. **A-003** — W10 (Thesis Update Cycle): no thesis version store, no delta quantifier, no update action selector. **A-004** — W13 (Bias Prevention): no 10-mistake checklist, no remediation gate. All three are officially P1–P3 requirements with zero production code.

### 5.3 Duplicate decision paths (CRITICAL)

**A-005** — Two `DecisionEngine` classes run in the same production pipeline: frozen v1.0 `knowledge/decision/engine.py` (via `InferencePipeline`) and institutional `decision_engine/engine.py` (via the stage DAG). `_finalize` reports only the legacy decision; the institutional decision (BUY/SELL/HOLD/NO TRADE) and the trade recommendation are computed and stored in `outputs` but never reconciled into the final assessment. Two "decisions" exist per run with no arbitration — a direct violation of the "one canonical path" golden rule.

### 5.4 Cyclic dependency web (HIGH)

**A-006** — 15 of 19 packages form a single SCC; 875 enumerated package cycles. Root cause is exactly two edges:
- `knowledge/evolution/applicator.py` → `simulation/models.py` (foundation importing top layer)
- `simulation/historical_replay.py` → `orchestration/institutional_orchestrator.py` (replay importing the runtime)

Removing these two edges yields a fully acyclic graph. Module-level import graphs are acyclic (no direct circular imports), so this is a layering/dependency-direction violation, not an import-order hazard.

### 5.5 Duplicate functionality (HIGH)

**A-007** — Two "canonical" `Evidence` contracts: frozen `knowledge/evidence/evidence.py` (12 fields) vs `evidence_collection/contracts.py` (20 fields, self-declared "canonical institutional Evidence"). Different IDs, different weight semantics, serialized across stage boundaries by dict.

**A-008** — Two `EvidenceWeighter` classes with divergent math: frozen 5-factor `knowledge/evidence/weighting.py::EvidenceWeighter` (confidence/sample/provenance/consistency/recency, WeightedAggregate) vs `evidence_reasoning/weighter.py::EvidenceWeighter` (0.5·confidence + 0.3·recency + 0.2·provenance heuristic).

**A-009** — News ingestion exists twice: orchestrator stage `_ingest_news` (broken — see A-010) and `pre_market/OvernightNewsIngestion` (working).

**A-010** — Two orchestration engines: `knowledge/orchestration/engine.py::OrchestrationEngine` (declared current architecture in `CURRENT_STATE.md`, production-dead — only tests import it) vs top-level `orchestration` (the real runtime).

### 5.6 Hidden adapters / hidden coupling / contract bypasses (HIGH)

**A-011** — Broken stage import with silent swallow: `_ingest_news` does `from news.collector import NewsCollector`; the module is `news.news_collector`. ImportError is caught and passed → the orchestrator's news job always no-ops; `build_context` depends on it but never reads its output (declared dependency is dead).

**A-012** — Dict-serialization adapter layer: every stage boundary converts via `to_dict()`/`from_dict()`. Contracts are enforced only by dict shape, error dicts (`{"error": ...}`) flow into downstream `from_dict` calls, and no typed interface exists between stages. This is an undocumented implicit adapter.

**A-013** — Shared mutable coupling: all stages read/write `self._params` / `self._results` (plain dicts) through closures — no typed ports; stage functions read arbitrary undeclared keys.

**A-014** — W1 contract bypass in W6: `_evidence_collection` reads `params.get("knowledge_graph")` which the default DAG never sets → `EvidenceCollector(knowledge_graph=None)` — evidence is collected without the W1 knowledge graph in production.

**A-015** — W3→W2 bypass: `pre_market_scan` is a root job; regime/regime_confidence default to `""`/`0.0` — the briefing runs without the W2 regime diagnosis unless the caller injects params.

**A-016** — W1 adapter hack: `knowledge/ingestion/adapter_dispatch.py::to_evidence()` builds ad-hoc `type("obj", (), {...})` objects instead of invoking the real CBI/CFI/CAI adapters (acknowledged as non-functional in `W1_W2_INTEGRATION_REVIEW.md`).

**A-017** — `_finalize` omits the institutional chain: confidence, scenarios, risk/reward validation, institutional decision, and trade recommendation are produced but excluded from the finalized summary — the "decision" output is the legacy one only.

### 5.7 Unused / unreachable code (MEDIUM)

**A-018** — 8 unused modules (no importer in src, tests, or scripts):
`connectors/cb_gold_fetcher.py`, `knowledge/decision/validator.py`, `knowledge/factors/publisher/{base,models}.py` (+`__init__` wrapper), `knowledge/ingestion/{adapter_dispatch,ingestion_pipeline,kr_parser}.py`, `knowledge/regime/gram_residual.py`.

**A-019** — Production-dead packages: `execution` (no src dependents — paper trading unwired from runtime), `technical` (no src dependents), `knowledge/orchestration` (test-only), `knowledge/benchmark` (test-only by design), `knowledge/factors/publisher` (whole subsystem orphaned).

**A-020** — Orphaned W1: the only W1 implementation (465 LOC) is unreachable; its documented purpose (encode 207+ KRs) is not wired into the legacy pipeline or the institutional chain.

### 5.8 Oversized modules (MEDIUM)

**A-021** — >500 LOC: `simulation/historical_replay.py` (1,643), `orchestration/stages.py` (636), `simulation/experiment.py` (583), `simulation/experiment_registry.py` (522), `knowledge/expansion/scaffolder.py` (514).

### 5.9 Oversized functions (MEDIUM)

**A-022** — 10 functions >100 LOC, worst offenders:
`simulation/historical_replay.py::_replay_event_release_by_release` (215), `orchestration/orchestrator.py::with_default_pipeline` (189), `signal_assessment/assembler.py::assemble` (157), `simulation/historical_replay.py::run` (129), `decision_engine/engine.py::decide` (119), `simulation/validation.py::validate` (204), `simulation/economic.py::compute_economic_summary` (132), `simulation/historical_replay.py::compute_oos_summary` (113), `simulation/experiment.py::_build_human` (103), `execution/execution_engine.py::evaluate` (102).

### 5.10 Oversized dataclasses (MEDIUM)

**A-023** — 12 classes >15 fields: `KnowledgeRecord` (35), `OrchestrationContext` (35), `PipelineContext` (26), `EventRunResult` (25), `InstitutionalTradeRecommendation` (21), `Evidence` (evidence_collection, 20), `Lesson` (19), `OOSSummary` (17), `EconomicSummary` (16), `InstitutionalRiskValidation` (16), `ExperimentRecord` (16), `OrchestrationReport` (16).

### 5.11 Dependency / environment issues (MEDIUM)

**A-024** — Undeclared third-party dependencies: `sklearn` (hard import in `knowledge/regime/gram_residual.py`), `transformers` (lazy import in `nlp/*`). Not in `pyproject.toml`.

**A-025** — `knowledge._compat` + `knowledge.integrity.provenance` imported by 12 packages' contracts modules: contract layer is coupled to knowledge internals — every package's contracts file drags in the foundation package.

**A-026** — Fabricated data in production stages: `_position_sizing` sizes from seeded RNG returns + hardcoded covariance matrix; `_risk_measures` fabricates a residual series when forecast spread is degenerate.

**A-027** — `CURRENT_STATE.md` is stale: describes the pre-workflow architecture (OrchestrationEngine as current, version 0.9.0, "Institutional Readiness" phase) with no mention of the 20 packages, the stage DAG, or W1–W13.

**A-028** — W2 GRAM residual unwired: analyzer module unused; the detector accepts `gram_residual_series` that nothing produces — the 2022-break detection criterion cannot fire in production.

### 5.12 Low severity

**A-029** — 20+ empty package `__init__.py` files → no declared public surface for most packages. **A-030** — `knowledge/regime/__init__.py` empty while sibling knowledge subpackages export. **A-031** — Two test files (`test_dummy_event.py`, `test_test_event_event.py`) fail collection (documented in CURRENT_STATE §10). **A-032** — Test-count claims in docs (1,638 / 1,593) drift from actual file inventory. **A-033** — `decision_engine/engine.py` uses `uuid4()` for `InstitutionalDecision` IDs — breaks the documented determinism rule ("all IDs content-derived") for that contract.

---

## 6. Severity Summary

| Severity | Count | Issues |
|----------|-------|--------|
| Critical | 4 | A-001 W-ID collision; A-002 W4 missing; A-003 W10 missing; A-004 W13 missing (A-005 dual decision paths also Critical-grade; see §5.3) |
| High | 7 | A-005 dual decisions; A-006 cyclic SCC; A-007/A-008/A-009/A-010 duplicates; A-011 broken news stage; A-012 dict adapter layer; A-013 shared mutable state; A-014 W6 bypass; A-015 W3 bypass; A-016 adapter hack; A-017 finalize omission |
| Medium | 8 | A-018 unused modules; A-019 dead packages; A-020 orphaned W1; A-021 oversized modules; A-022 oversized functions; A-023 oversized dataclasses; A-024 undeclared deps; A-025 contract coupling; A-026 fabricated data; A-027 stale state doc; A-028 unwired GRAM |
| Low | 5 | A-029 empty `__init__`; A-030 regime `__init__`; A-031 broken test files; A-032 doc drift; A-033 uuid nondeterminism |

---

## 7. Technical Debt List

1. **TD-1** (Critical): W-ID label collision across 4 packages — requires renaming docstrings/comments + audit-trail reconciliation.
2. **TD-2** (Critical): Missing workflows W4, W10, W13 (three documented institutional gates with zero implementation).
3. **TD-3** (High): Two parallel decision systems (legacy `knowledge/decision` vs institutional `decision_engine`) — reconciliation/arbitration absent.
4. **TD-4** (High): 15-package SCC held together by 2 misplaced imports (`applicator→simulation`, `historical_replay→orchestration`).
5. **TD-5** (High): Duplicated contracts: 2× Evidence, 2× EvidenceWeighter (divergent math), 2× news ingestion, 2× orchestration engine.
6. **TD-6** (High): Implicit dict-serialization adapter layer across 17 stage boundaries; no typed ports.
7. **TD-7** (High): Broken `_ingest_news` import silently no-op'ing; dead `build_context→ingest_news` dependency.
8. **TD-8** (High): W9 under-consumption + W9/W12 ordering inversion vs documented contract.
9. **TD-9** (Medium): Orphaned W1 implementation (465 LOC, `type()`-hack adapter) — the foundation workflow is dead code.
10. **TD-10** (Medium): 8 unused modules + 3 production-dead packages (execution, technical, knowledge/orchestration).
11. **TD-11** (Medium): Monoliths: historical_replay (1,643), stages (636), experiment/registry (~550 avg), scaffolder (514); 10 functions >100 LOC; 12 dataclasses >15 fields.
12. **TD-12** (Medium): Undeclared deps (sklearn, transformers); fabricated data in sizing/risk stages; uuid-based decision IDs vs determinism rule.
13. **TD-13** (Low): Documentation drift: CURRENT_STATE.md, test-count claims, empty public surfaces.

---

## 8. Recommended Fixes (DESCRIBE ONLY — not implemented)

1. **Workflow identity (A-001)**: Rename the embedded W-labels to a distinct scheme (e.g., code-stage IDs `S1..S4` or workflow-adjacent names) so official W-IDs remain unique; add a doc-verification test asserting no module docstring claims an official W-ID that doesn't match `IMPLEMENTATION_WORKFLOWS.md`.
2. **Dependency direction (A-006)**: Move `FeedbackApplicator`'s dependency on `EventRunResult` into a shared contract module (or invert via callback/port); replace `historical_replay`'s direct `InstitutionalOrchestrator` instantiation with a strategy/interface parameter. Both are small, low-risk refactors that break the entire SCC.
3. **Duplicate contracts (A-007/A-008)**: Designate one canonical `Evidence` and one `EvidenceWeighter`; adapt the other path to it (the institutional chain should either reuse the frozen contracts or the frozen layer should be extended via adapter — per the "extend, never replace" rule).
4. **Dual decision paths (A-005)**: Define an explicit arbitration policy (e.g., institutional decision wins with legacy as tie-break, or vice versa) and surface the reconciled decision in `_finalize`.
5. **Stage typing (A-012/A-013)**: Replace dict plumbing with typed stage result objects or `TypedDict`s; make `from_dict` reject unknown/error payloads.
6. **Broken news stage (A-011)**: Fix the import path or delete the stage (news is already handled inside `pre_market`); remove the dead `build_context→ingest_news` edge.
7. **W9/W12 ordering (A-002 area)**: Reorder the DAG so scenarios (fragility) feed confidence; feed regime, OOS ECE, and window consistency into `ConfidenceEngine` per the W9 contract.
8. **Orphaned W1 (A-020)**: Either wire `knowledge/ingestion` into the pipeline (replacing the `type()` hack with real adapters) or formally archive it.
9. **Missing workflows (A-002/A-003/A-004)**: Implement W4 tiering, W10 thesis store + delta engine, W13 checklist gate as new stages against the documented contracts; do not reuse hijacked IDs.
10. **Monoliths (A-021/22/23)**: Split `historical_replay` and `stages`; extract `with_default_pipeline` job definitions into a declarative config; split `KnowledgeRecord`/`OrchestrationContext` into grouped value objects.
11. **Environment (A-024)**: Declare `scikit-learn`/`transformers` as optional extras or remove the imports; remove fabricated-data paths in `_position_sizing`/`_risk_measures` (raise instead of fabricate).
12. **Documentation**: Refresh `CURRENT_STATE.md`; add a module→workflow mapping table owned by the docs; restore a CI check that fails on new unused modules or new cross-package back-edges.

---

## 9. Verification Limits

- Reachability was computed from `tests/` + `scripts/` entry points; modules loaded dynamically (importlib/string-based) are not detected.
- Dataclass field counts are static (annotated assignments only); method bodies were not semantically analyzed.
- No tests were executed; behavioral claims (e.g., `uuid4` usage, RNG fabrication) are from source inspection.
- W-identity claims are based on docstrings in `__init__.py` files and cross-referenced against `IMPLEMENTATION_WORKFLOWS.md` (revision at HEAD `0da02e1`).

**End of report A1. No files in `src/` were modified.**
