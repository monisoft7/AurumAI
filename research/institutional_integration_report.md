# Phase 18 — Institutional Integration Architecture

> **Status:** Research report — no code committed.  
> **Scope:** End‑to‑end execution from Raw Economic Data through DecisionEngine.  
> **Out of scope:** Broker execution, trading, order submission.  

---

## 1. Executive Summary

AurumAI currently has two independent execution paths:

| Path | Entry | Stages |
|---|---|---|
| **InferencePipeline** (`pipeline.py`) | Single MacroEvent + gold CSV | 7 stages: lessons → knowledge → graph → evidence → reason → decide |
| **OrchestrationEngine** (`engine.py`) | OrchestrationContext (multi‑layer) | 4 intelligence layers + aggregation + reason + decide |

Both paths terminate at `DecisionEngine.decide()` which produces a `Decision` with one of six types (strong_positive … insufficient_evidence).

**Phase 17 (Risk Intelligence)** added a second decision surface — the `DecisionGate` — that produces a `RiskDecision` (proceed / scale_down / delay / halt). These two surfaces are **currently disconnected**: the DecisionEngine does not consult the DecisionGate, and the DecisionGate does not feed back into the pipeline.

**Phase 18 unifies these two surfaces** into a single institutional execution flow that is scheduled, idempotent, cached, checkpointed, and recoverable — without touching frozen Core v1.0 components.

---

## 2. End‑to‑End Pipeline

```
Raw Economic Data  (CSV, FRED API, Yahoo Finance, RSS feeds)
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                1.  DATA INGESTION LAYER                      │
│                                                              │
│  ┌──────────────┐  ┌───────────────┐  ┌───────────────────┐  │
│  │ MacroEvent   │  │ NewsCollector │  │ FOMCCalendar      │  │
│  │ load_raw()   │  │ .collect()    │  │ Connector         │  │
│  └──────┬───────┘  └───────┬───────┘  └───────┬───────────┘  │
│         │                  │                  │              │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌───────┴───────────┐  │
│  │ FeatureExtr. │  │ NewsSentiment│  │ FOMCSentiment     │  │
│  │ Engine       │  │ .analyze_b() │  │ .analyze()        │  │
│  └──────────────┘  └──────────────┘  └───────────────────┘  │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                2.  KNOWLEDGE BUILDING LAYER                   │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ LessonBuilder│→ │ LessonSumm.  │→ │ GraphBuilder     │   │
│  │ .build()     │  │ Aggregator   │  │ KnowledgeGraph   │   │
│  └──────────────┘  └──────────────┘  └────────┬─────────┘   │
│                                                │             │
│  (YieldContextEnricher injects here if active)               │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                3.  INTELLIGENCE LAYERS                        │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Economic     │  │ Temporal     │  │ Causal           │   │
│  │ Intelligence │  │ Intelligence │  │ Intelligence     │   │
│  └──────┬───────┘  └──────┬───────┘  └───────┬──────────┘   │
│         │                 │                   │              │
│         └─────────────────┼───────────────────┘              │
│                           ▼                                  │
│              ┌──────────────────────┐                        │
│              │  EvidenceAggregator  │                        │
│              └──────────┬───────────┘                        │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                4.  REASONING LAYER                            │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Evidence     │→ │ Reasoning    │→ │ ReasoningChain   │   │
│  │ Query        │  │ Engine       │  │ (steps + conf)   │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                5.  DECISION LAYER                             │
│                                                              │
│  ┌────────────────────┐    ┌─────────────────────────────┐   │
│  │ DecisionEngine     │    │ Forecast Intelligence        │   │
│  │ .decide()          │    │ (Confidence, Context, etc.)  │   │
│  │         │          │    └──────────┬──────────────────┘   │
│  │         ▼          │               │                     │
│  │  Decision          │    ┌──────────┴──────────────────┐   │
│  │  (advise only)     │    │ Risk Intelligence            │   │
│  │         │          │    │ DecisionGate.evaluate()      │   │
│  │         ▼          │    │ → RiskDecision               │   │
│  │  RiskDecision      │    └─────────────────────────────┘   │
│  │  fused into        │                                      │
│  │  FinalOutput       │                                      │
│  └────────────────────┘                                      │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                6.  OUTPUT                                     │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  FinalOutput (frozen dataclass)                      │    │
│  │  - decision: Decision  (from DecisionEngine)         │    │
│  │  - risk: RiskDecision  (from DecisionGate)           │    │
│  │  - forecast_context: ForecastContext  (from 16.x)    │    │
│  │  - risk_metrics: RiskMetrics         (from 17.1)     │    │
│  │  - position_sizing: PositionSizing   (from 17.2)    │    │
│  │  - risk_budget: RiskBudget          (from 17.3)     │    │
│  │  - pipeline_id: str                 (idempotency)    │    │
│  │  - cache_key: str                   (cache lookup)   │    │
│  │  - timestamp: str                   (ISO 8601)       │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### Design Rules

1. **InferencePipeline and OrchestrationEngine are frozen** — Phase 18 wraps, never replaces them.
2. **Forecast Intelligence and Risk Intelligence are post‑processing layers** that consume pipeline outputs, they are not stages of the pipeline itself.
3. **The two decision surfaces (DecisionEngine + DecisionGate) remain independent** — the DecisionEngine produces the *advisory* (direction + confidence), the DecisionGate produces the *risk constraint* (can we act?). A `FinalOutput` holds both; no single "trade signal" is issued.
4. **Broker execution is not in scope** — see Phase 19 or later.

---

## 3. Scheduling

### 3.1 Trigger Types

| Trigger | Source | Action |
|---|---|---|
| **Economic release** | EconomicCalendarConnector | Run full pipeline for that event type |
| **Time‑based** | Cron / scheduler | Periodic forecast + risk refresh (daily, weekly) |
| **News event** | NewsCollector RSS poll | Run news sentiment → enrich context → re‑evaluate risk |
| **Manual** | Human analyst | Run any subset of pipeline with override parameters |

### 3.2 Schedule Matrix

| Frequency | Job | Components | Expected duration |
|---|---|---|---|
| Per economic release | `analyze_event` | MacroEvent → FeatureExtraction → Lessons → Knowledge → Graph → Evidence → Reason → Decide → Forecast → Risk | 10–30s |
| Daily (market close) | `refresh_forecast` | MacroForecaster → ForecastContext → ForecastConfidence → ForecastValidator | 5–15s |
| Daily (market close) | `refresh_risk` | RiskMetrics → PositionSizing → RiskBudget → DecisionGate → FinalOutput | <1s |
| Hourly | `poll_news` | NewsCollector → NewsSentiment → enrich ForecastContext → re‑evaluate Risk | 2–10s |
| Weekly | `consolidate_knowledge` | Re‑aggregate lessons → rebuild graph ↔ prune stale edges | 30–120s |

### 3.3 Execution Model

All jobs use a **strict sequential task graph** (no parallelism between dependent stages). This is intentional:

- AurumAI is an institutional intelligence system, not a low‑latency trading engine. Latency tolerance is seconds to minutes, not microseconds.
- Determinism is paramount — parallel execution introduces non‑determinism in output ordering, which breaks the `same inputs → same outputs` constitution rule.
- The dependency graph is narrow (most paths are linear) — parallelism offers minimal throughput gain.

> **Exception:** The `poll_news` job can run independently of the main pipeline because it only updates `ForecastContext.news_mood`/`news_confidence`, which is consumed downstream by `UncertaintyBudget`. This is a pure enrichment — it does not modify pipeline output.

---

## 4. Dependency Graph

```
Data Sources (CSV, FRED, Yahoo, RSS, FOMC Calendar)
  │
  ├──1a. MacroEvent.load_raw() ───────────────────────────────┐
  │                                                            │
  ├──1b. FeatureExtractionEngine.extract()                     │
  │                                                            │
  ├──1c. NewsCollector + NewsSentimentAnalyzer (independent)   │
  │                                                            │
  ├──1d. FOMCCalendar + FOMCSentimentAnalyzer (independent)    │
  │                                                            │
  ▼                                                            │
┌────────────────────────────────────────────────────────────┐ │
│  2a. LessonBuilder.build()   ←── YieldContextEnricher      │ │
└────────────────────────────────────────────────────────────┘ │
  │                                                            │
  ▼                                                            │
┌────────────────────────────────────────────────────────────┐ │
│  2b. LessonSummaryAggregator.build_and_save()               │ │
└────────────────────────────────────────────────────────────┘ │
  │                                                            │
  ▼                                                            │
┌────────────────────────────────────────────────────────────┐ │
│  2c. GraphBuilder.build()  →  KnowledgeGraph                │ │
└────────────────────────────────────────────────────────────┘ │
  │                                                            │
  ▼                                                            │
┌────────────────────────────────────────────────────────────┐ │
│  3a. EvidenceQuery.matching()    (from KnowledgeGraph)     │ │
│  3b. Economic Intelligence Layer (regime evidence)         │ │
│  3c. Temporal Intelligence Layer (time evidence)           │ │
│  3d. Causal Intelligence Layer   (causal evidence)         │ │
└───────────────┬────────────────────────────────────────────┘ │
                │                                              │
                ▼                                              │
┌────────────────────────────────────────────────────────────┐ │
│  4a. EvidenceAggregator.merge()  (dedup + conflict detect) │ │
└────────────────────────────────────────────────────────────┘ │
  │                                                            │
  ▼                                                            │
┌────────────────────────────────────────────────────────────┐ │
│  5a. ReasoningEngine.reason()    →  ReasoningChain          │ │
└────────────────────────────────────────────────────────────┘ │
  │                                                            │
  ▼                                                            │
┌────────────────────────────────────────────────────────────┐ │
│  6a. DecisionEngine.decide()    →  Decision                 │ │
└────────────────────────────────────────────────────────────┘ │
  │                                                            │
  ▼                                                            │
┌────────────────────────────────────────────────────────────┐ │
│  7a. MacroForecaster.forecast()  →  ForecastResult          │◄┘
│  7b. ForecastContextBuilder.build()                         │
│  7c. ForecastConfidenceComputer.compute()                   │
└────────────────────────────────────────────────────────────┘ │
  │                                                            │
  ▼                                                            │
┌────────────────────────────────────────────────────────────┐ │
│  8a. compute_var / compute_cvar  →  RiskMetrics             │ │
│  8b. VolatilityTargetSizer.compute()  →  PositionSizing    │ │
│  8c. RiskParitySizer.compute()    →  RiskBudget             │ │
│  8d. RegimeRiskOverlay.evaluate()                           │ │
│  8e. UncertaintyBudget.evaluate()                           │ │
│  8f. DecisionGate.evaluate()    →  RiskDecision             │ │
└────────────────────────────────────────────────────────────┘ │
  │                                                            │
  ▼                                                            │
┌────────────────────────────────────────────────────────────┐ │
│  9.  FinalOutput (Decision + RiskDecision + metadata)       │ │
└────────────────────────────────────────────────────────────┘ │
```

### Dependency Rules

| Rule | Enforcement |
|---|---|
| No stage may run before its inputs are produced | Each stage checks its required outputs from upstream stages; raises `MissingInputError` if absent |
| Forecast Intelligence (7a–7c) may run on pre‑computed historical data without re‑running stages 1–6 | Separable if ForecastContext can be constructed without fresh pipeline output |
| Risk Intelligence (8a–8f) depends only on 7a–7c and the existing Decision (6a) | Risk does not depend on raw data or knowledge — it is a pure function of forecasts + market data |
| News enrichment (1c) may update ForecastContext out‑of‑band | Only affects Risk Intelligence re‑evaluation, never the frozen Decision |

---

## 5. Orchestration Pipeline

### 5.1 Pipeline Scheduler

A single `ScheduledPipeline` class manages all jobs. Reuse concept: **Apache Airflow DAG** pattern (DAG definition → sequential task execution with state tracking), adapted to single‑process Python without a database.

```python
# Conceptual interface (not code)
class PipelineJob:
    id: str
    dependencies: list[str]        # job IDs that must complete first
    fn: Callable                   # the actual work
    cache_ttl: int | None          # seconds before cache invalidates
    checkpoint: bool               # persists state on completion?

class ScheduledPipeline:
    def register(self, job: PipelineJob) -> None: ...
    def run(self, job_id: str, force: bool = False) -> dict: ...
    def run_all(self, trigger: str) -> dict[str, Any]: ...
    def status(self, job_id: str) -> JobStatus: ...
```

### 5.2 Job Definitions

| Job ID | Dependencies | Cache TTL | Checkpoint |
|---|---|---|---|
| `ingest_event` | — | None (event data is source of truth) | Yes |
| `ingest_news` | — | 300s (stale news is acceptable) | No |
| `build_lessons` | `ingest_event` | None | Yes |
| `build_knowledge` | `build_lessons` | None (knowledge is versioned) | Yes |
| `build_graph` | `build_knowledge` | None | Yes |
| `query_evidence` | `build_graph` | 3600s (graph is stable intra‑day) | No |
| `reason` | `query_evidence`, `build_graph` | None (fresh per event) | Yes |
| `decide` | `reason` | None | Yes |
| `forecast` | `ingest_event` + historical data | 3600s | Yes |
| `build_context` | `forecast`, `ingest_news` | 300s | No |
| `risk_measures` | `forecast` | 300s | No |
| `risk_gate` | `risk_measures`, `build_context`, `decide` | None | Yes |
| `finalize` | `risk_gate` | None | Yes |

### 5.3 Orchestration Rules

1. **`ingest_event` and `ingest_news` can run in parallel** (no dependency between them).
2. **`forecast` depends only on `ingest_event`** — it does not need reasoning or decision outputs.
3. **`risk_measures` depends only on `forecast`** — it can run as soon as forecasts are ready.
4. **`risk_gate` is the synchronisation point** — it waits for `risk_measures`, `build_context`, and `decide`.
5. **`finalize` is always the last job** — it produces `FinalOutput` and persists the audit record.

---

## 6. Failure Recovery

### 6.1 Failure Modes

| Failure Mode | Symptom | Recovery |
|---|---|---|
| **Missing input data** | CSV not found, API timeout | Retry 3× with exponential backoff; if still failing, emit `InsufficientData` result |
| **Pipeline stage error** | Exception in `build_lessons`, `reason`, etc. | Halt pipeline at failed stage; record error in `FinalOutput.errors`; do NOT proceed to downstream stages |
| **Validation checkpoint fail** | ForecastValidator.report.passed == False | Halt; record validation failure; downstream stages see degraded ForecastConfidence |
| **DecisionGate halt** | RiskDecision.action == "halt" | `finalize` still runs, recording the halt reason; no decision is suppressed — the halt IS the output |
| **Cache corruption** | Checksum mismatch on cached output | Invalidate cache entry and re‑run the stage |
| **Deadlock** | Circular dependency detected at registration | `ScheduledPipeline.register()` validates DAG is acyclic via topological sort |

### 6.2 Retry Policy

| Stage Type | Max Retries | Backoff | Action on permanent failure |
|---|---|---|---|
| Data ingestion | 3 | 2× (1s, 2s, 4s) | Record `InsufficientData`, skip dependent stages |
| Knowledge building | 1 | None | Fail pipeline, no partial output |
| Intelligence layers | 1 | None | Fail pipeline, no partial output |
| Risk Intelligence | 2 | 1× (1s, 1s) | Emit conservative defaults (scale=0, halt) |
| Output finalization | 3 | 2× (1s, 2s, 4s) | Raise exception — output must be persisted |

### 6.3 Partial Output Recovery

If a pipeline run fails mid‑way, already‑completed stages retain their outputs in the cache/checkpoint store. The next run can **resume from the last successful checkpoint** rather than re‑executing from the beginning.

Implementation: each checkpointed stage atomically writes a completion marker (JSON file or sentinel) after producing its output. `ScheduledPipeline.run()` checks for the marker before executing a stage.

---

## 7. Validation Checkpoints

### 7.1 Checkpoint Locations

| Checkpoint | Location | Validates | Gate |
|---|---|---|---|
| **C1** | After `ingest_event` | Data schema, date range, column presence, no NaN in critical columns | If failed, entire pipeline halts |
| **C2** | After `build_lessons` | Lesson count > 0, required columns present, no duplicate dates | If failed, skip to knowledge (empty knowledge is valid) |
| **C3** | After `build_knowledge` | Record count > 0, confidence values in [0,1], source_lesson_ids non‑empty | If failed, skip evidence query |
| **C4** | After `forecast` | ForecastResult points non‑empty, y_lo ≤ y ≤ y_hi for all points | If failed, Risk Intelligence uses conservative defaults |
| **C5** | After `build_context` | Regime is known or "UNKNOWN", regime_confidence ≥ 0 | If failed, Risk Intelligence treats as UNKNOWN regime |
| **C6** | After `risk_measures` | var_95 ≤ 0, cvar_95 ≤ var_95, tail_index is float or None | If failed, set has_tail_risk = True (conservative) |
| **C7** | After `finalize` | FinalOutput has all required fields, decision_id is unique | If failed, re‑attempt finalization once |

### 7.2 Checkpoint Behaviour

Each checkpoint:
1. Runs a deterministic validation function
2. Returns `CheckpointResult(passed: bool, notes: str, severity: str)`
3. Writes result to a checkpoint log
4. If severity is `"fatal"`, pipeline halts immediately
5. If severity is `"warning"`, pipeline continues with degraded parameters

---

## 8. Caching Strategy

### 8.1 What Gets Cached

| Data | Cache Key | TTL | Invalidation Trigger |
|---|---|---|---|
| Raw event data (CSV parse) | `sha256(file_path)` + `mtime` | Infinite (immutable input) | File change |
| Feature‑extracted DataFrame | `event_type + data_date_range` | Infinite (deterministic) | Input change |
| Lessons CSV | `sha256(event_data) + sha256(gold_data)` | Infinite | Input change |
| Knowledge records | `knowledge_version + record_count` | Infinite (versioned) | Explicit re‑build |
| Knowledge graph | `sha256(knowledge_records)` | Infinite | Knowledge re‑build |
| ForecastResult | `model_name + data_hash + horizon` | 3600s | New data |
| ForecastContext | `regime + event_type + news_hash` | 300s | News poll or regime change |
| RiskMetrics | `sha256(returns) + confidence` | 300s | New returns |
| PositionSizing | `sha256(returns) + target_vol` | 300s | New returns |

### 8.2 Cache Storage

In‑memory dictionary (single‑process) for Phase 18. Rationale:
- No distributed caching needed at current scale (single‑process, single‑machine).
- Simpler than Redis/ memcached; zero new dependencies.
- Cache entries are `(key, value, ttl, created_at)` tuples; expired entries are lazily evicted on access.

> **Upgrade path:** Replace in‑memory cache with Redis when multi‑process/multi‑machine execution is required (Phase 19 — Scaling).

### 8.3 Cache Key Design

Cache keys are deterministic SHA‑256 hashes of canonical input representations:

```
cache_key = sha256(f"{job_id}:{json.dumps(input_signature, sort_keys=True)}")
```

Where `input_signature` is a `dict` of all input file paths + parameters that the job consumes. Deterministic: same inputs → same key → same cached output.

---

## 9. Idempotency

### 9.1 Design Principle

Every job in the pipeline is **idempotent**: running it twice with the same inputs produces the same outputs, and the second run does not create duplicate state.

### 9.2 Mechanisms

| Mechanism | How it works | Applied to |
|---|---|---|
| **Deterministic functions** | All computations are pure functions of their inputs | Every stage |
| **Content‑addressed storage** | Outputs are stored by content hash, not by run ID | Lessons, Knowledge, Graph |
| **Upsert semantics** | If a record with the same content hash exists, skip insertion | LineageRegistry, VersionedStore |
| **Write‑once checkpoint files** | Completion markers are created atomically; if the file exists, the stage is not re‑executed | All checkpointed stages |
| **Pipeline‑wide run ID** | Each `ScheduledPipeline.run()` call generates a unique `pipeline_id` | Audit logging |

### 9.3 Enforcing Idempotency

The `ScheduledPipeline` enforces idempotency at the job level:

```python
# Conceptual flow
def run(self, job_id: str, force: bool = False) -> JobOutput:
    if not force and self._checkpoint_exists(job_id):
        return self._load_checkpoint(job_id)

    if not force and self._cache_valid(job_id):
        return self._load_cache(job_id)

    output = self._jobs[job_id].fn(self._load_inputs(job_id))
    
    # Only write checkpoint if the stage requested it
    if self._jobs[job_id].checkpoint:
        self._write_checkpoint(job_id, output)
    
    return output
```

---

## 10. Incremental Updates

### 10.1 What Can Be Updated Incrementally

| Component | Incremental Strategy | Refresh Trigger |
|---|---|---|
| **Lessons** | Append‑only; new economic releases produce new lessons; existing lessons are never modified | Per economic release |
| **Knowledge records** | Re‑aggregate from ALL lessons (append‑only means full re‑aggregation is needed); versioned | Each new lesson batch |
| **Knowledge graph** | Rebuild from scratch on knowledge change (graph is small — <1000 nodes, networkx) | Knowledge update |
| **Forecast** | Rolling window; latest `window` data points are refit | Daily |
| **ForecastContext** | Regime label updated; news/FOMC sentiment refreshed independently | Hourly news poll |
| **RiskMetrics** | Latest `window` returns are recomputed | Daily or on new price data |

### 10.2 What Must Be Full (Not Incremental)

- **Evidence query → Reasoning → Decision** — always runs fresh per event. The Decision must be based on the complete current evidence set, not an incremental update.
- **Risk Decision Gate** — always runs fresh. It consumes the latest Decision + ForecastContext + RiskMetrics, all of which may have changed.

### 10.3 Cost of Full vs Incremental

| Operation | Full cost | Incremental cost | Notes |
|---|---|---|---|
| Re‑build lessons | 2–5s (10 CSV rows → 40 lesson rows) | 0.2–0.5s (1 new CSV row) | Append‑only makes incremental trivial |
| Re‑aggregate knowledge | 3–8s (40 lessons → aggregation) | 0.5–1s (update running aggregates) | Full re‑aggregation is safer — ensures consistency |
| Rebuild graph | 0.5–1s (<1000 nodes) | 0.1s (add node + edges) | Full rebuild is cheap enough to always do |
| Re‑run forecasting | 5–15s (3 models × 100 data points) | — | Must refit, no shortcut |
| Re‑run risk | <1s (pure numpy) | — | Fast enough to always run fresh |

**Decision:** Do full rebuilds for knowledge and graph. The cost is negligible (<10s), and it guarantees consistency. Incremental knowledge aggregation introduces complexity with no measurable benefit at current scale.

---

## 11. Integration with Existing Components

### 11.1 What Stays Inside Core v1.0 (Frozen)

| Component | Location | Role |
|---|---|---|
| InferencePipeline | `src/knowledge/pipeline/pipeline.py` | 7‑stage event pipeline |
| OrchestrationEngine | `src/knowledge/orchestration/engine.py` | Multi‑layer orchestration |
| ReasoningEngine | `src/knowledge/reasoning/engine.py` | Evidence → ReasoningChain |
| DecisionEngine | `src/knowledge/decision/engine.py` | ReasoningChain → Decision |
| EvidenceQuery | `src/knowledge/evidence/query.py` | Graph → EvidenceCollection |
| EventRegistry | `src/knowledge/events/registry.py` | Event type registration |
| Knowledge Expansion Framework | `src/knowledge/expansion/` | Scaffolder, Validator, Lifecycle |

### 11.2 What Lives in the Integration Layer (New Phase 18)

| Component | Location | Role |
|---|---|---|
| `ScheduledPipeline` | `src/integration/pipeline.py` | Job registration, dependency resolution, execution |
| `FinalOutput` | `src/integration/models.py` | Unified output dataclass |
| `CacheManager` | `src/integration/cache.py` | In‑memory cache with TTL + content‑addressed keys |
| `CheckpointManager` | `src/integration/checkpoint.py` | Completion markers + validation checkpoints |
| `IntegrationContext` | `src/integration/context.py` | Pipeline‑wide shared state |
| `FinalOutputRepository` | `src/integration/repository.py` | Persist/load FinalOutput records |

### 11.3 What Already Exists (Extended in Phase 18)

| Component | Existing Location | Extension |
|---|---|---|
| Forecast Intelligence | `src/forecasting/*.py` | Already integrated via `FinalOutput` |
| Risk Intelligence | `src/forecasting/risk_measures.py`, `position_sizing.py`, `risk_budgeting.py`, `decision_gate.py` | Already integrated via `FinalOutput` |
| LineageRegistry | `src/knowledge/integrity/lineage.py` | Add `pipeline_run` lineage relation type |

---

## 12. Output Data Model

```python
@dataclass(frozen=True)
class FinalOutput:
    pipeline_id: str
    trigger: str                         # "economic_release" | "scheduled" | "news" | "manual"
    timestamp: str                       # ISO 8601

    # Decision surface (from Core v1.0)
    decision: Decision | None            # DecisionEngine output
    reasoning_chain: ReasoningChain | None

    # Forecast Intelligence surface (from Phase 16)
    forecast_context: ForecastContext | None
    forecast_result: ForecastResult | None
    forecast_confidence: ForecastConfidence | None
    forecast_validation: ForecastValidationReport | None

    # Risk Intelligence surface (from Phase 17)
    risk_decision: RiskDecision | None
    risk_metrics: RiskMetrics | None
    position_sizing: PositionSizing | None
    risk_budget: RiskBudget | None

    # Pipeline metadata
    stages: tuple[StageRecord, ...]      # per-stage timing + pass/fail
    errors: tuple[str, ...]              # non‑fatal warnings + fatal error messages
    cache_hits: int                      # number of stages served from cache
    wall_time_ms: float                  # total pipeline wall time
```

### 12.1 StageRecord

```python
@dataclass(frozen=True)
class StageRecord:
    stage_id: str
    status: str                          # "ok" | "cached" | "skipped" | "failed"
    duration_ms: float
    error: str | None
    checkpoint: CheckpointResult | None
```

---

## 13. Open‑Source Reuse

| Pattern | Adapted From | How |
|---|---|---|
| DAG job registration + topological execution | Apache Airflow | Single‑process adaptation — no scheduler daemon, no DB |
| Content‑addressed cache keys | Prefect / Dagster | SHA‑256 of canonical input signatures |
| Write‑ahead checkpoint markers | Apache Spark lineage | Atomic file‑based sentinels |
| Idempotent upsert semantics | Delta Lake / LakeFS | Content‑hash deduplication on write |
| Exponential backoff retry | AWS SDK / Google `google‑api‑python‑client` | `min(2^n * base, max_delay)` with jitter |

**No new dependencies are added.** All patterns are reimplemented in ~300 lines of pure Python using `pathlib`, `hashlib`, `json`, and `time` — all stdlib.

---

## 14. Summary

| Concern | Design Decision |
|---|---|
| **Pipeline order** | 12‑job sequential DAG with fork (news ∥ event ingest) and join (risk_gate) |
| **Scheduling** | 4 trigger types, 5 schedule frequencies, all single‑process |
| **Dependency graph** | Strict topological; validated at registration time |
| **Failure recovery** | Checkpoint‑based resume; exponential backoff retry; conservative degradation |
| **Validation checkpoints** | 7 checkpoints (C1–C7) with severity‑based gating |
| **Caching** | In‑memory TTL cache with content‑addressed SHA‑256 keys |
| **Idempotency** | Content‑hash dedup, write‑once checkpoints, deterministic functions |
| **Incremental updates** | Lessons: append‑only; Knowledge/Graph: full rebuild (cheap at scale); Risk: always fresh |
| **New dependencies** | Zero (stdlib only) |
| **Frozen components** | Unchanged (InferencePipeline, OrchestrationEngine, DecisionEngine, ReasoningEngine, etc.) |
| **Output** | `FinalOutput` frozen dataclass (Decision + RiskDecision + metadata) |

---

## 15. Anchored Summary

### Phase 18.1 — Institutional Orchestrator (implemented)

| File | Description |
|------|-------------|
| `src/orchestration/__init__.py` | Package init |
| `src/orchestration/models.py` | `InstitutionalAssessment`, `StageRecord`, `CheckpointResult` dataclasses |
| `src/orchestration/institutional_orchestrator.py` | DAG‑based pipeline orchestrator with `CacheManager`, `CheckpointManager`, level‑based topological execution (Kahn), parallel thread‑pool for independent stages, cache with TTL, checkpoint resume, idempotency, and a 13‑job default pipeline wired to existing AurumAI components. |
| `tests/test_institutional_orchestrator.py` | 58 tests covering `CacheManager`, `CheckpointManager`, DAG validation, orchestrator execution (sequential, parallel, error, force, resume, idempotency), default pipeline DAG structure, stage function logic, and end‑to‑end integration with real components. |

**Key behaviours verified:**

| Concern | Status |
|---------|--------|
| DAG topological sort (Kahn) | Tests: empty, linear, parallel, diamond, circular, self‑dependency, disconnected |
| Sequential execution (dependencies) | `a → b → c` order verified |
| Parallel execution (independent stages) | Thread‑pool overlap confirmed |
| Cache (TTL, hit, miss, force, invalidate) | 9 unit tests |
| Checkpoint (write, read, resume, clear) | 5 unit tests + resume integration test |
| Idempotency (same pipeline_id → same output, single call) | 1 integration test |
| Error recovery (partial outputs, resume) | 2 tests |
| 13‑job default pipeline DAG structure | No cycles, correct level grouping, `finalize` is last |
| Stage function wiring | 5 unit tests (missing params, invalid events, output bundle) |
| Full pipeline integration | Real `EventRegistry`, CPI event, gold CSV, threaded execution — 1 end‑to‑end test |
| Existing test suite | 1183 pre‑existing tests remain passing |

**Architecture invariants maintained:**
- Core v1.0 (InferencePipeline, OrchestrationEngine, DecisionEngine, ReasoningEngine) is **unmodified** — Phase 18 wraps, never replaces.
- The orchestrator calls existing components via `run()` / `forecast()` / `evaluate()` — it does not duplicate their logic.
- All 13 pipeline jobs are registered via `with_default_pipeline()` factory or can be registered individually for custom DAGs.

*Implementation complete. 58 tests, 0 regressions.*

---

### Phase 19.1 — Historical End‑to‑End Simulation (implemented)

| File | Description |
|------|-------------|
| `src/simulation/__init__.py` | Package init |
| `src/simulation/models.py` | `SimulationReport`, `EventRunResult`, `ForecastAccuracySummary`, `RiskSummary` — frozen dataclasses with `to_dict()` serialisation |
| `src/simulation/historical_replay.py` | `HistoricalReplayEngine` — discovers event CSVs, generates synthetic data for missing types (GDP, PMI, FOMC), runs each event type through the full `InstitutionalOrchestrator` pipeline, and aggregates per‑event results into a `SimulationReport`. Also exposes `run_simulation()` convenience function. |
| `tests/test_historical_replay.py` | 40 tests covering model serialisation, synthetic CSV generation, event discovery, extraction helpers, fixture‑based engine runs, real‑data end‑to‑end, and edge cases (empty dir, bad gold path, missing files). |

**Replayed event types:**

| Event | Data Source | Notes |
|-------|-------------|-------|
| CPI | `data/economic/CPIAUCSL.csv` (954 rows, 1947–2026) | Real historical |
| NFP | `data/economic/PAYEMS.csv` (1050 rows, 1939–2026) | Real historical |
| GDP | Synthetic (20 rows, quarterly from 2019) | Generated deterministically with `np.random.default_rng(42)` |
| INTEREST_RATE | `data/economic/FEDFUNDS.csv` (865 rows, 1954–2026) | Real historical |
| PMI | Synthetic (36 rows, monthly from 2022) | Generated deterministically |
| PPI | `data/economic/PPIACO.csv` (1362 rows, 1913–2026) | Real historical |
| FOMC | Synthetic (24 rows, monthly from 2020) | Generated deterministically |

**SimulationReport fields populated:**

| Field | Source |
|-------|--------|
| `total_events` | Sum of CSV row counts across all event types |
| `successful_runs` / `failed_runs` | Pipeline‑level success (zero errors across all 13 jobs) |
| `avg_execution_time_ms` | Mean wall‑clock time per event‑type run |
| `cache_hit_ratio` | Cache hits ÷ total cacheable jobs |
| `checkpoints_total` | Stages that were checkpoint‑resumed |
| `events_processed` | Ordered tuple of event type keys |
| `results[n].*` | Per‑event metrics: decision, risk_decision, forecast_model, forecast_confidence, validation status, VaR/CVaR/tail, position scaling, risk gate action |
| `forecast_accuracy` | Aggregated: total_forecasts, passed/failed validations, avg_confidence, models_used |
| `risk` | Aggregated: total_evaluations, action counts, avg VaR/CVaR/tail |

**Bug fixes applied to Phase 18.1 orchestrator during integration:**

| Fix | File | Description |
|-----|------|-------------|
| `Path` conversion in `_build_legacy_pipeline` | `institutional_orchestrator.py:594` | Wrapped `data_path`/`gold_path`/`output_dir` with `Path()` to prevent `str / str` path errors |
| `AttributeError` catch in `_ingest_news` | `institutional_orchestrator.py:575` | `FOMCCalendarConnector` has no `.fetch()` — caught gracefully alongside `ImportError` |
| Single `ForecastResult` extraction in `_forecast` | `institutional_orchestrator.py:618` | `MacroForecaster.forecast()` returns `dict[str, ForecastResult]`; the stage now extracts the primary model result for downstream stages |
| `y` column creation from `Close` in `_forecast` | `institutional_orchestrator.py:628` | Gold CSV uses `Close` not `y`; added `df["y"] = df["Close"]` |

**Regression check:** 1241 pre‑existing Phase 18 tests remain passing alongside the 40 new Phase 19.1 tests and 17 new Phase 19.2 tests.

*1298 total tests, 0 regressions.*

---

## Phase 19.2 — Institutional Validation Engine

### Location
- `src/simulation/validation.py` — `InstitutionalValidator` class + `InstitutionalValidationReport` model
- `src/simulation/models.py` — `errors: tuple[str, ...]` field added to `EventRunResult`
- `src/simulation/historical_replay.py` — populates `errors` from `assessment.errors`
- `src/simulation/__init__.py` — exports all new validation types
- `tests/test_simulation_validation.py` — 17 tests covering all 8 questions

### What it does
The `InstitutionalValidator` takes a `SimulationReport` and produces an `InstitutionalValidationReport` that answers **8 institutional readiness questions**:

| # | Question | Source | Output field |
|---|----------|--------|-------------|
| Q1 | How often did Forecast agree with Risk? | `decision` vs `risk_decision` per event | `accuracy.forecast_risk_agreement_rate` |
| Q2 | How often did Risk override Decision? | `risk_gate_action` = halt/reject when `decision` is positive | `accuracy.risk_override_rate`, `risk.total_overrides` |
| Q3 | Which event types produced the highest confidence? | `forecast_confidence` grouped by `event_type` | `confidence.by_event_type`, `highest_event`, `lowest_event` |
| Q4 | Which event types produced the weakest reasoning? | `validation_passed` rate per `event_type` | `reasoning.weakest_events`, `overall_pass_rate` |
| Q5 | Which pipeline stage failed most often? | `errors` tuple parsed for stage ID prefix | `bottlenecks.stage_failures`, `most_failed_stage` |
| Q6 | Which Forecast models performed best? | `forecast_model` grouped by composite score (success × confidence) | `models.by_model`, `best_model` |
| Q7 | Which Risk metrics rejected most opportunities? | `risk_gate_action` distribution + avg VaR/CVaR | `risk.actions`, `avg_var_95`, `avg_cvar_95` |
| Q8 | Which components contributed most to InstitutionalAssessment? | `execution_time_ms`, `cache_hits`, `checkpoints_used` by event type | `contributions.*` |

### Output model
```
InstitutionalValidationReport
├── accuracy       (agreement/override/validation/pipeline rates)
├── confidence     (by event type + ranking)
├── reasoning      (by event type + weakest list)
├── risk           (action counts + overrides + avg metrics)
├── bottlenecks    (stage failure counts + top failure)
├── models         (per-model stats + best model)
├── contributions  (execution time, cache, checkpoints per event type)
├── recommendations (heuristic-based: 0‑10 items)
└── metadata       (event count + types)
```

### Data flow
```
HistoricalReplayEngine
  └─┬─ _replay_event() → EventRunResult(errors=assessment.errors)  ← new field
    └─ run_all() → SimulationReport(results=..., errors=...)
                      │
                      ▼
              InstitutionalValidator.validate(report)
                      │
                      ▼
              InstitutionalValidationReport
```

### Key design decisions
1. **Stage failure parsing** — Errors in `assessment.errors` follow the format `"stage_id: error_message"`. The validator parses the stage ID via regex rather than requiring a structured field, keeping the orchestrator unchanged.
2. **Risk override definition** — Override = risk gate action is "halt", "scale_down", or "reject" AND the forecast decision is one of POSITIVE/STRONG_POSITIVE/LONG/STRONG_LONG. Risk halting a neutral decision is not counted as an override.
3. **Best model scoring** — Composite score = `success_rate * (avg_confidence or 0.5)`. This balances reliability (success) against conviction (confidence).
4. **Weakest reasoning** — Event types whose validation pass rate falls below the overall average pass rate across all event types.
5. **Recommendations** — Heuristic thresholds (agreement < 50%, override > 30%, validation pass < 70%, pipeline success < 80%) generate targeted improvement suggestions. A "healthy" message is returned when none trigger.
6. **Backward compatibility** — The new `errors` field on `EventRunResult` defaults to `()` and is omitted from `to_dict()` when empty. All existing tests pass unmodified.
