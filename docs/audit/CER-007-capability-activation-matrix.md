# CER-007: Capability Activation Matrix
**Status:** Official  
**Authority:** Implementation Priority Reference  
**Date:** 2026-07-25  
**Scope:** All inactive capabilities in AurumAI v0.9.0

---

## Objective

Rank every inactive capability by institutional value and produce the official implementation priority for the remainder of AurumAI. No new subsystems are recommended. All capabilities listed exist in the codebase and require only wiring, not construction.

---

## Scoring Methodology

**Priority Score = Institutional Impact × Ease of Activation × Architectural Leverage**

Each dimension scored 1–5:

| Dimension | 1 | 3 | 5 |
|-----------|---|---|---|
| Institutional Impact | Cosmetic / logging | Improves decision quality | Directly answers a North Star question |
| Ease of Activation | Requires new design | Requires moderate wiring | Single call-site change |
| Architectural Leverage | Isolated benefit | Enables one downstream | Unblocks multiple downstream capabilities |

---

## Capability Inventory

### Active (Frozen Core — excluded from ranking)
- InferencePipeline (7-stage production entry point)
- ReasoningEngine, DecisionEngine, EvidenceEngine
- KnowledgeGraph, GraphBuilder
- FeatureExtractionEngine (8 extractors)
- KnowledgeIntegrity (LineageRegistry, VersionedStore, Provenance)
- InstitutionalOrchestrator (DAG runner wrapping InferencePipeline)
- Forecasting layer (MacroForecaster, RiskMeasures, PositionSizing, RiskBudgeting, DecisionGate)
- Execution layer (VirtualPortfolio, ExecutionEngine, Slippage, Commission)
- OOS simulation (ChronologicalOOSEngine, ExperimentFramework)
- NLP (FOMCSentimentAnalyzer, NewsSentimentAnalyzer)
- TechnicalIndicatorExtractor
- FOMCCalendarConnector
- NewsCollector

### Inactive — Subject to Ranking

| ID | Capability | Location | Why Inactive |
|----|-----------|----------|--------------|
| C-01 | EvidenceRanker | `src/knowledge/evidence/ranker.py` | Never called; ReasoningEngine skips ranking step |
| C-02 | HistoricalSituationRetriever | `src/knowledge/reasoning/retrieval.py` | Instantiation site exists but object never created |
| C-03 | MacroRegimeDetector | `src/knowledge/regime/` | FeatureExtractor expects it; no production code creates one |
| C-04 | CausalAnalyzer | `src/knowledge/causal/` | Type-hinted in OrchestrationContext; always None at runtime |
| C-05 | OrchestrationEngine.analyze() | `src/knowledge/orchestration/` | Dead path; production uses InferencePipeline directly |
| C-06 | LearningEngine + FeedbackApplicator + KnowledgeCalibrator | `src/knowledge/learning/`, `src/knowledge/evolution/` | Only reachable through dead FeedbackApplicator path |
| C-07 | DXY Context Enricher | `src/knowledge/context/dxy.py` | Built; never wired into InferencePipeline |
| C-08 | CrossEventResult.overall_consensus + consensus_confidence | `src/knowledge/reasoning/` | Computed by CrossEventAnalyzer; never reaches DecisionEngine |
| C-09 | Evidence.explanation field | `src/knowledge/evidence/` | Populated on every Evidence object; skipped by ReasoningEngine |
| C-10 | Temporal Intelligence Layer | `src/knowledge/temporal/` | Only reachable through dead OrchestrationEngine path |
| C-11 | Economic Intelligence Layer | `src/knowledge/economics/` | Only reachable through dead OrchestrationEngine path |
| C-12 | EvidenceAggregator.merge() | `src/knowledge/orchestration/` | Only reachable through dead OrchestrationEngine path |
| C-13 | Gate 4: KnowledgeRecord → source lesson + artifact traceability | `src/knowledge/integrity/` | ADR-0004 Gate 4 open; lineage chain incomplete at lesson boundary |
| C-14 | Gate 5: Atomic immutable content-addressed persistence | `src/knowledge/integrity/` | ADR-0004 Gate 5 open; atomic_write_json exists but not content-addressed |
| C-15 | Gate 6: Real CPI/US10Y out-of-sample evaluation | `src/simulation/` | ADR-0004 Gate 6 open; OOS engine exists, evaluation not executed |
| C-16 | Gate 7: Clean CI pipeline | root | ADR-0004 Gate 7 open; no CI config present |

---

## Priority Matrix

| Rank | Capability | ID | Current Owner | Production Owner | Current Status | Smallest Correct Increment | Effort | Impact | Risk | Dependencies | Acceptance Criteria |
|------|-----------|-----|--------------|-----------------|----------------|---------------------------|--------|--------|------|-------------|---------------------|
| 1 | Gate 6: OOS Evaluation | C-15 | THE BLU WALF | InstitutionalOrchestrator | Engine built; evaluation not run | Execute ChronologicalOOSEngine on held-out CPI + US10Y data; produce institutional report | Low | 5 — directly answers North Star questions: Is AurumAI correct? Is confidence calibrated? Does US10Y improve decisions? | Low — read-only evaluation, no production code changes | OOS engine, historical data CSVs | Evaluation report produced; accuracy, calibration, and US10Y delta metrics present; deterministic on re-run |
| 2 | Gate 4: Lesson → Artifact Traceability | C-13 | THE BLU WALF | LineageRegistry | Lineage exists Decision→SourceData; lesson→artifact link missing | Add `source_artifact` field to `Lesson`; populate in `LessonBuilder`; register in `LineageRegistry` | Low | 4 — completes the full lineage chain required for institutional trust | Low — additive field, no frozen core changes | KnowledgeIntegrity layer (frozen, stable) | Every Lesson has a traceable source artifact; backward trace from Decision reaches raw data file |
| 3 | Evidence.explanation → ReasoningEngine | C-09 | THE BLU WALF | ReasoningEngine | Field populated; never read | Pass `evidence.explanation` into `ReasoningChain` narrative; surface in `InstitutionalAssessment` | Low | 4 — improves explainability of every decision at zero construction cost | Low — additive read of existing field | None | ReasoningChain includes explanation text; InstitutionalAssessment output contains evidence rationale |
| 4 | CrossEventResult consensus → DecisionEngine | C-08 | THE BLU WALF | DecisionEngine | Computed; never forwarded | Forward `overall_consensus` and `consensus_confidence` from `CrossEventAnalyzer` result into `DecisionEngine` input | Low | 4 — multi-event consensus is computed but silently discarded; wiring it improves decision quality | Low — no new computation; pure wiring | CrossEventAnalyzer (active) | DecisionEngine receives consensus signal; decisions reflect cross-event agreement; determinism preserved |
| 5 | EvidenceRanker | C-01 | THE BLU WALF | ReasoningEngine | 58-line module; never called | Insert `EvidenceRanker.rank()` call before evidence is passed to `ReasoningEngine` | Low | 3 — improves evidence quality entering reasoning; reduces noise | Low — module is complete and tested | None | ReasoningEngine receives ranked evidence; ranking is deterministic; existing tests pass |
| 6 | HistoricalSituationRetriever | C-02 | THE BLU WALF | ReasoningEngine | Instantiation site exists; object never created | Instantiate `HistoricalSituationRetriever` at the existing call site in `ReasoningEngine` | Low | 4 — historical analogue retrieval directly improves reasoning quality | Low — instantiation only; module is complete | KnowledgeGraph (active) | ReasoningEngine retrieves historical analogues; analogues appear in ReasoningChain; deterministic |
| 7 | DXY Context Enricher | C-07 | THE BLU WALF | InferencePipeline | Enricher built; not wired into pipeline | Add `DXYContextEnricher` to the context enrichment stage of `InferencePipeline` alongside `YieldContextEnricher` | Low–Medium | 3 — answers North Star question "Should DXY be introduced?" only after OOS validates US10Y first | Low — parallel to existing YieldContextEnricher pattern | C-15 (OOS must first confirm US10Y value before DXY is introduced per North Star §8) | DXY context present in KnowledgeRecords; OOS evaluation can compare DXY vs no-DXY runs |
| 8 | MacroRegimeDetector | C-03 | THE BLU WALF | FeatureExtractionEngine | Module built; never instantiated | Instantiate `MacroRegimeDetector` and pass to `FeatureExtractionEngine` at pipeline initialization | Medium | 3 — regime context enriches feature vectors; improves condition classification | Medium — requires regime data; must verify determinism | Historical economic data (available in data/) | FeatureExtractionEngine receives regime signal; regime field populated in extracted features; deterministic |
| 9 | Gate 5: Content-Addressed Persistence | C-14 | THE BLU WALF | VersionedStore | atomic_write_json exists; not content-addressed | Add SHA-256 content hash to `VersionedStore` artifact filenames; verify on read | Medium | 3 — immutability guarantee required for institutional artifact trust | Low — additive; does not change read path for existing artifacts | VersionedStore (active) | Artifacts have content-addressed filenames; re-writing identical content produces identical filename; corruption detected on read |
| 10 | Temporal Intelligence Layer | C-10 | THE BLU WALF | OrchestrationEngine | Full layer built; only reachable via dead OrchestrationEngine path | Wire `TemporalAdapter` directly into `InferencePipeline` context stage, bypassing OrchestrationEngine | Medium | 3 — temporal context improves horizon-aware reasoning | Medium — requires verifying temporal layer determinism independently | C-15 (validate value via OOS before activating) | Temporal context present in pipeline output; OOS evaluation can measure temporal layer contribution |
| 11 | Economic Intelligence Layer | C-11 | THE BLU WALF | OrchestrationEngine | Full layer built; only reachable via dead OrchestrationEngine path | Wire `EconomicAdapter` directly into `InferencePipeline` context stage | Medium | 3 — economic regime context enriches decisions | Medium — same pattern as C-10; validate determinism | C-10, C-15 | Economic context present in pipeline output; deterministic; OOS measures contribution |
| 12 | CausalAnalyzer | C-04 | THE BLU WALF | OrchestrationEngine | Built; always None in OrchestrationContext | Instantiate `CausalAnalyzer` and assign to `OrchestrationContext.causal_analyzer` | Medium | 3 — causal reasoning improves decision explainability | Medium — causal graph construction must be verified deterministic | KnowledgeGraph (active) | CausalAnalyzer produces CausalGraph; graph referenced in ReasoningChain; deterministic |
| 13 | LearningEngine + FeedbackApplicator + KnowledgeCalibrator | C-06 | THE BLU WALF | FeedbackApplicator | All three built; FeedbackApplicator never instantiated | Instantiate `FeedbackApplicator` with `LearningEngine` and `KnowledgeCalibrator`; call after each OOS evaluation cycle | High | 4 — closes the learning loop; enables knowledge to improve from evaluation results | High — feedback must not corrupt frozen knowledge; requires strict immutability gate | C-15 (OOS must run first to produce feedback signal), C-14 (immutable persistence required before feedback writes) | FeedbackApplicator applies calibrated feedback to KnowledgeRecords; VersionedStore preserves pre-feedback snapshot; deterministic replay possible |
| 14 | OrchestrationEngine.analyze() + EvidenceAggregator | C-05, C-12 | THE BLU WALF | OrchestrationEngine | Full 4-layer orchestration built; dead path | Activate only after C-10, C-11, C-04 are individually validated via OOS | High | 3 — full multi-layer orchestration; value depends on individual layer activation | High — activating all layers simultaneously makes regression attribution difficult | C-04, C-10, C-11, C-15 | OrchestrationEngine.analyze() called in production; EvidenceAggregator merges multi-layer evidence; OOS shows improvement over InferencePipeline baseline |
| 15 | Gate 7: CI Pipeline | C-16 | THE BLU WALF | CI system | No CI config present | Add GitHub Actions workflow: install deps, run pytest, fail on any test failure | Low | 2 — operational hygiene; does not improve intelligence quality | Low — additive infrastructure | None | CI runs on every push to main; all 1638+ tests pass; fresh-clone install verified |

---

## Summary

**Total inactive capabilities:** 15 (across 16 IDs)  
**Immediately activatable (Low effort, no dependencies):** C-15, C-13, C-09, C-08, C-01, C-02  
**Blocked on OOS validation first (per North Star §8, §12):** C-07, C-10, C-11, C-04, C-06, C-05

**Top 3 priorities:**

1. **C-15 — Gate 6 OOS Evaluation** — The North Star's immediate goal. All other capability activation decisions depend on its results.
2. **C-13 — Gate 4 Lesson Traceability** — Completes the lineage chain. Required for institutional correctness claim.
3. **C-09 — Evidence.explanation wiring** — Zero construction cost. Improves explainability of every decision immediately.

**Governing constraint:** Per `PROJECT_NORTH_STAR.md §8`, no new intelligence capability (C-07 through C-14) shall be activated before Gate 6 OOS evaluation answers its four questions. Ranks 1–5 are the only work authorized before that gate closes.
