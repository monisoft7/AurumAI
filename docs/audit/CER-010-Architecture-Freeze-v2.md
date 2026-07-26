# CER-010: Architecture Freeze v2 — Institutional Architecture Review

**Classification**: Chief Software Architect Review  
**Date**: 2026-07-26  
**Status**: Complete  
**Scope**: Determine freeze candidates, stabilization needs, permanent interfaces, frozen data structures, and expensive-postponed decisions across the entire AurumAI codebase

---

## Executive Summary

AurumAI consists of 29 `knowledge/` subsystems, 11 `src/` subsystems, and 76 test files spanning approximately 90% of planned capability. This review classifies every subsystem against four criteria: maturity (tested, stable, production-quality), interface tightness (is the API stable?), dependency breadth (how many subsystems consume it?), and change cost (what breaks if it changes?).

The finding: **six data structures and two abstract interfaces are mature enough to freeze now**. Three subsystems need standardization before freezing. Five decisions grow more expensive with each sprint postponed. The Architecture Freeze v2 scope is defined below.

---

## Freeze Candidates — Freeze Immediately

These subsystems are mature, tested, tightly interfaced, and widely depended upon. Any change to them propagates across the entire codebase.

### 1. `Evidence` Data Structure (`knowledge/evidence/evidence.py`)

| Property | Assessment |
|---|---|
| Lines | 70 lines, frozen dataclass |
| Fields | 14 fields (evidence_id, event_type, asset, condition, value, confidence, direction, horizon, impact, returns_weight, average_return_pct, bias, source_timestamp, metadata) |
| Dependent subsystems | evidence/collection, weighting, query; reasoning/chain, engine, context; decision/engine; pipeline/context; repositories; learning; features; orchestration; forecasting |
| Test coverage | 10 test files explicitly testing Evidence or its consumers |
| Change cost | Propagates to every file importing from `knowledge.evidence` |

**Verdict**: FREEZE. Add `institutional_context` as a first-class field (currently buried in `metadata`) before the freeze takes effect — this is the last window to add a field. After freeze, adding fields becomes an Architecture Council decision.

**Action**: Merge `metadata.get("institutional_context")` into an explicit `institutional_context: str = ""` field.

### 2. `MacroEvent` ABC (`knowledge/events/base.py`)

| Property | Assessment |
|---|---|
| Lines | ~180 lines with `MacroEvent` ABC + `StandardEventMetadata` |
| Abstract methods | `event_type`, `lesson_version`, `condition_columns`, `knowledge_version` (class methods), `load_raw`, `load_and_extract`, `build_lesson_fields`, `lesson_text` (instance) |
| Concrete subclasses | CPIEvent, NFPEvent, GDPEvent, PPIEvent, PMIEvent, FOMCEvent, InterestRateEvent, UnemploymentClaimsEvent |
| Dependent subsystems | pipeline, repositories, reasoning, decision, learning, orchestration |
| Change cost | Adding an abstract method breaks all 8+ subclasses |

**Verdict**: FREEZE. No new abstract methods. New event types implement the existing interface. The `load_and_extract_with_calendar` variant is an optional extension, not a new abstract method.

### 3. `DecisionEngine._classify()` (`knowledge/decision/engine.py`)

| Property | Assessment |
|---|---|
| Lines | ~200 lines |
| Logic | 6-type threshold classification: STRONG_BUY, BUY, WEAK_BUY, HOLD, WEAK_SELL, SELL with 4 thresholds |
| Dependent subsystems | pipeline, orchestration, repositories, legacy systems |
| Test coverage | Dedicated test file, exercised end-to-end in multiple integration tests |
| Change cost | Changes the meaning of every Decision produced by the system |

**Verdict**: FREEZE. The 6-type system with its 4 threshold parameters (confidence, return magnitude, evidence count, directional strength) is the permanent institutional classification scheme.

### 4. `WeightConfig` and `EvidenceWeighter` (`knowledge/evidence/weighting.py`)

| Property | Assessment |
|---|---|
| Lines | ~500 lines (includes WeightConfig, WeightFactors, WeightedAggregate, EvidenceWeighter) |
| Weighting factors | 5 factors: confidence_weight, sample_size_weight, provenance_weight, consistency_weight, recency_weight |
| Dependent subsystems | reasoning, decision, pipeline, orchestration, forecasting |
| Test coverage | 2 test files, includes algorithm verification |
| Change cost | Adding a factor requires changes across all weighting consumers |

**Verdict**: FREEZE. The 5-factor model is complete. The `institutional_context` factor was considered (CER-009, Sprint-006) and rejected — it belongs in reasoning explanation, not evidence weighting.

### 5. `ReasoningChain` and `ReasoningStep` (`knowledge/reasoning/chain.py`, `reasoning/step.py`)

| Property | Assessment |
|---|---|
| Fields (Chain) | 9 fields: chain_id, context, steps, final_conclusion, overall_confidence, evidence_count, provenance, metadata, attribution |
| Fields (Step) | 5 fields: step_id, step_type, conclusion, confidence, supporting_evidence_ids, details |
| Step type constants | 4 types: EVIDENCE_REVIEW, COMPARISON, AGGREGATION, CONCLUSION |
| Dependent subsystems | decision, learning, repositories, orchestration, forecasting |
| Test coverage | 8 reasoning test files directly test or consume these |
| Change cost | Changes the output contract for every downstream consumer |

**Verdict**: FREEZE. No new step types. No new fields unless proven necessary through production use.

### 6. `KnowledgeRecord` (`knowledge/knowledge_record.py`)

| Property | Assessment |
|---|---|
| Fields | 37 fields including institutional_context (added Sprint-004) |
| Dependent subsystems | repositories, learning, pipeline, orchestration |
| Change cost | Fundamental persistence unit |

**Verdict**: FREEZE. Now complete with institutional_context.

---

## Stabilization Candidates — Too Generic, Freeze After Hardening

These subsystems have correct high-level architecture but need internal standardization before they can be frozen.

### 1. Repository Classes (`knowledge/repositories/` and scattered)

| Assessment | Detail |
|---|---|
| Problem | 9+ repository classes with inconsistent APIs: DecisionRepository, ReasoningRepository, CausalRepository, EvidenceRepository, GraphRepository, LearningRepository, PipelineRepository, TemporalRepository, EconomicRepository. Some use `save()`/`load()`, others use `to_dict()`/`from_dict()`. No base class. |
| Risk | Every new data type adds another ad-hoc repository. Fragmentation increases cognitive load and migration cost. |
| Recommendation | Introduce a `RepositoryBase` ABC with standardized `save()`, `load()`, `list()`, `delete()` signatures. Migrate all existing repositories before any new ones are added. |
| Effort | 2–3 days. |

### 2. Concrete Event Implementations (`knowledge/events/*.py`)

| Assessment | Detail |
|---|---|
| Problem | CPIEvent is production quality. GDPEvent, NFPEvent, PPIEvent, PMIEvent, FOMCEvent, InterestRateEvent, UnemploymentClaimsEvent vary widely in quality. Some predate `StandardEventMetadata` and use ad-hoc metadata structures. |
| Risk | Inconsistent event quality produces inconsistent evidence, which propagates to inconsistent reasoning and decisions. |
| Recommendation | Bring all 8 event implementations to CPIEvent standard: StandardEventMetadata, proper lesson_fields, robust load_and_extract, consistent condition_columns. |
| Effort | 1–2 days per event, 3–5 total. |

### 3. Bias Constants (`knowledge/evidence/weighting.py` + `reasoning/cross_event.py`)

| Assessment | Detail |
|---|---|
| Problem | Bias is defined as string constants in two locations: `weighting.py` (`gold_positive_bias`, `gold_negative_bias`, `mixed_or_context_dependent`) and in `cross_event.py` with similar but independently-maintained strings. |
| Risk | Drift between the two definitions will eventually cause subtle bugs in cross-event reasoning where bias comparison is critical. |
| Recommendation | Extract a shared `Bias` enum into `knowledge/evidence/bias.py`. Re-export from both locations. |
| Effort | 1 hour. |

### 4. `EvidenceQuery` Multi-Event Path (`knowledge/evidence/query.py`)

| Assessment | Detail |
|---|---|
| Problem | `EvidenceQuery.matching()` supports `SINGLE_EVENT` and `MULTI_EVENT` strategies. The single-event path is well-tested. The multi-event path (`_node_to_evidence()`, group-level querying) is untested and undocumented. |
| Risk | Multi-event reasoning (e.g., "what did CPI and NFP together say about gold?") relies on this path. If it has latent defects, cross-event reasoning will produce incorrect results. |
| Recommendation | Write tests for the multi-event path. Document the strategy contract. Consider whether `MULTI_EVENT` should use `CrossEventAnalyzer` directly rather than duplicating graph traversal logic. |
| Effort | 2–3 days. |

### 5. Feature Extraction Engine (`knowledge/features/engine.py` + `extractors/`)

| Assessment | Detail |
|---|---|
| Problem | `FeatureExtractionEngine` uses global state (`_global_extractors` list) which is not thread-safe. Two extraction code paths (direct `extract()` vs `process()` via the engine). `MacroRegimeFeatureExtractor` is the only global extractor; others are invoked per-event. |
| Risk | In a multi-threaded pipeline, concurrent runs could interfere via shared global state. The dual extraction paths create ambiguity about which path is canonical. |
| Recommendation | Remove global state: inject extractors explicitly per-pipeline-run. Unify to a single `extract()` call path. |
| Effort | 1–2 days. |

---

## Permanent Interfaces (Institutional Contracts)

These interfaces, once frozen, cannot change without breaking the entire institutional architecture. They define the contracts between all subsystems.

### Contract 1: `MacroEvent` ABC (5 abstract methods)
```python
# These signatures are permanent
classmethod event_type() -> str
classmethod lesson_version() -> str
classmethod condition_columns() -> list[str]
load_raw(path: str | Path) -> Any
load_and_extract(path: str | Path, knowledge_version: str, ...) -> tuple[list[dict], list[dict], list[dict]]
build_lesson_fields(raw: Any, combined_df: DataFrame, ...) -> list[dict]
lesson_text(raw: Any, combined_df: DataFrame, ...) -> list[LessonField]
```

### Contract 2: `EvidenceWeighter.weigh()` → `WeightedAggregate`
```python
def weigh(collection: EvidenceCollection, ...) -> WeightedAggregate
```
Returns: `WeightedAggregate` with weighted_avg_return, weighted_avg_confidence, effective_sample_size, directional_strength, directional_mode, consistency, factor_breakdown.

### Contract 3: `ReasoningEngine.reason()`
```python
def reason(evidence: EvidenceCollection, context: ReasoningContext) -> ReasoningChain
```

### Contract 4: `DecisionEngine.decide()`
```python
def decide(chain: ReasoningChain, context: DecisionContext | None, min_evidence_count: int) -> Decision
```

### Contract 5: `PipelineLog.explain()` and `explain_structured()`
```python
def explain(event_type: str, asset: str) -> str
def explain_structured(event_type: str, asset: str) -> dict[str, Any]
```

### Contract 6: `PipelineContext` (36 fields)
The dictionary-based configuration contract. New keys = breaking change to all stages.

---

## Data Structures That Must Never Change

The following dataclasses and frozen structures define the data layer. Their *exact field sets* are institutional contracts.

| Structure | File | Fields | Reach |
|---|---|---|---|
| `FrozenDict` | `_compat.py` | N/A (immutable dict) | Foundation — used everywhere |
| `Evidence` | `evidence/evidence.py` | 14 | Widest reach — every subsystem |
| `EvidenceCollection` | `evidence/collection.py` | 3 (items, event_type, asset) | Pipeline core |
| `WeightFactors` | `evidence/weighting.py` | 7 | Evidence weighting |
| `WeightConfig` | `evidence/weighting.py` | 7 | Config for all weighting |
| `WeightedAggregate` | `evidence/weighting.py` | 7 | Reasoning input |
| `ReasoningStep` | `reasoning/step.py` | 6 | Reasoning output |
| `ReasoningContext` | `reasoning/context.py` | 11 | Reasoning input, now with institutional_context |
| `ReasoningChain` | `reasoning/chain.py` | 9 | Decision input |
| `Decision` | `decision/decision.py` | 9 | Final output |
| `KnowledgeRecord` | `knowledge_record.py` | 37 | Persistent knowledge unit |
| `LessonField` | `models.py` | 7 | Event lesson output |
| `Provenance` | `integrity/provenance.py` | 4 | Audit trail node |
| `PipelineContext` | `pipeline/context.py` | 36 fields in dict | Pipeline configuration |
| `StageRecord` / `CheckpointResult` / `InstitutionalAssessment` | `orchestration/models.py` | varies | Orchestration audit |
| `MacroRegime` | `regime/macro_regime_detector.py` | 4 regimes | Regime classification |
| `CompositeScore` | `regime/composite_score.py` | varies | Regime scoring |
| `AssetContext` | `context/asset_context.py` | varies | Asset context |
| `MarketContext` | `context/market_context.py` | varies | Market context |

---

## Expensive-Postponed Decisions

These decisions carry an escalating cost the longer they remain unresolved.

### 1. Evidence ID Scheme Standardization (Cost: RISING)

**Current**: Evidence ID is a concatenation `{event_type}_{asset}_{condition_key_value}_{horizon}` (e.g., `CPI_XAU/USD_inflation_pressure_down_1D`). This scheme is embedded in knowledge_id, lesson_id, chain_id, decision_id, and all repository storage keys.

**Cost of postponement**: Every new event type and asset pair hardens the current scheme further. A change now requires migrating ~500 stored KnowledgeRecords. In 3 sprints, it could be ~2000. In production, it's impossible without downtime.

**Recommendation**: Freeze the pattern. Write a formal spec in `docs/architecture/naming-conventions.md`.

### 2. Repository API Standardization (Cost: MODERATE → RISING)

**Current**: 9+ repository classes, no base class, inconsistent naming.

**Cost of postponement**: Adding repository #10 (next data type) without a base class adds more tech debt. The migration effort is linear: ~0.3 days per repository now, but each new one increases total migration time.

**Recommendation**: Add `RepositoryBase` ABC before the 10th repository is created.

### 3. Learning Engine Feedback Loop (Cost: HIGH → RISING)

**Current**: `LearningEngine.generate_feedback()` produces `KnowledgeFeedback` with `suggested_confidence` adjustments, but nothing consumes it. The feedback loop is specified but not closed.

**Cost of postponement**: Every sprint without closing the loop means the system is not learning from its decisions. When closed, the integration will be more complex because the pipeline and orchestration layers have hardened around the absence of feedback. The feedback port must be designed into the pipeline contract, which will require breaking changes to add later.

**Recommendation**: Close the loop in Sprint-009. Add a `feedback` stage to `orchestration/stages.py` that consumes `KnowledgeFeedback` and adjusts evidence weights or decision thresholds.

### 4. Economic Evidence Deficiency (Cost: MODERATE → RISING)

**Current**: `EconomicEvidenceAdapter.regime_to_evidence()` returns evidence with `average_return_pct=0.0` and `bias="neutral"`. The economic layer provides regime classification without return prediction.

**Cost of postponement**: Zero-return, neutral-bias evidence in the pipeline dilutes the weighted aggregate towards the mean. As more economic regimes are detected (multi-event scenarios), this dilution compounds. The economic layer is permanently placeholder until return projections are added.

**Recommendation**: Implement `EconomicReturnEstimator` that maps regime + asset to historical return distribution. Wire into `EvidenceWeighter` as a provenance factor.

### 5. Forecasting Subsystem Integration (Cost: MODERATE → HIGH on integration)

**Current**: `src/forecasting/` is a parallel 15-file subsystem producing `ForecastAssessment` rather than `Decision`. It has its own evidence, reasoning, context, and confidence modules.

**Cost of postponement**: The forecasting subsystem and the knowledge pipeline are converging on similar concepts but through different code. The longer they diverge, the harder the eventual merge or interface layer will be. Forecast context and knowledge context should share a base class.

**Recommendation**: Define an integration contract: `ForecastAssessment → Evidence` adapter. This lets forecasting produce evidence that the knowledge pipeline can consume without rewriting either subsystem.

---

## Architecture Freeze v2 Scope

### Freeze Immediately (DONE — no code changes needed)
- `Evidence` data structure (after adding `institutional_context` field)
- `MacroEvent` ABC abstract method signatures
- `DecisionEngine._classify()` 6-type threshold system
- `WeightConfig` / `EvidenceWeighter` 5-factor weighting model
- `ReasoningChain` / `ReasoningStep` output contracts
- `KnowledgeRecord` field set

### Freeze After Standardization (code changes required)
1. Repository standardization: `RepositoryBase` ABC by Sprint-010
2. Event implementations: all 8 events to CPIEvent quality by Sprint-010
3. Bias enum deduplication: extract to shared enum, Sprint-009
4. EvidenceQuery multi-event path: test and document, Sprint-009
5. Feature extraction: remove global state, Sprint-009

### Do Not Freeze Yet
- Forecasting subsystem (`src/forecasting/`): too immature, parallel codebase
- Execution subsystem (`src/execution/`): paper trading only, not production
- Simulation subsystem (`src/simulation/`): experiment infrastructure, not core
- Connectors (`src/connectors/`): data source integration, inherently volatile
- News subsystem (`src/news/`): data ingestion, inherently volatile
- NLP subsystem (`src/nlp/`): analysis pipeline, subject to improvement
- Technical subsystem (`src/technical/`): analysis toolkit, subject to expansion

### In-Scope for Freeze v2 (this document)
- All items under "Freeze Immediately" and "Freeze After Standardization"
- Documents the 20 frozen data structures
- Defines 6 permanent interface contracts
- Identifies 5 expensive-postponed decisions with recommendations

### Out of Scope
- New feature requests (covered by CER-009)
- Code implementation (covered by Sprint tasks)
- Roadmap or timeline (covered by project management)

---

## Dependency Graph Summary

```
MacroEvent ABC ────────────────────┐
                                   ▼
Evidence (frozen) ←── EvidenceCollection
                                   │
                                   ▼
EvidenceWeighter ──→ WeightedAggregate
                                   │
                                   ▼
ReasoningEngine ──→ ReasoningChain
                        │
                        ▼
DecisionEngine ──→ Decision
                        │
                        ▼
KnowledgeRecord (persisted)
```

No circular dependencies exist. All data flow is one-directional: Event → Evidence → Aggregate → Reasoning → Decision → Record. This directional purity is a key architectural strength that must be preserved.

---

## Conclusion

The AurumAI codebase is approximately 90% complete and structurally sound. The 6 core data structures and 2 abstract interfaces identified above are mature enough to freeze — they have stable fields, broad test coverage, and wide dependency graphs. The 5 stabilization items require 5–14 person-days of standardization work. The 5 expensive-postponed decisions (Evidence ID scheme, Repository API, Learning feedback loop, Economic evidence, Forecasting integration) should be addressed in the next 2–3 sprints before architecture hardening makes changes costly.

**Total stabilization effort**: 8–20 person-days (repository standardization 2–3d, event implementations 3–5d, bias enum 1h, multi-event path 2–3d, feature engine 1–2d).

**Total expensive-postponed effort**: 10–20 person-days (Evidence ID spec 1d, Repository ABC 2–3d, Learning feedback loop 3–5d, Economic return estimator 2–5d, Forecasting integration 2–5d).

**Combined follow-on effort**: 18–40 person-days to complete the Architecture Freeze v2 program.
