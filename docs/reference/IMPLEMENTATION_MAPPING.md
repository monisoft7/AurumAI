# Implementation Mapping: Institutional Methodology ↔ Existing Capabilities

> **Purpose**: Map every existing code capability against the Institutional Gold Methodology and Knowledge Base. This document provides the official implementation roadmap — no redesign, no new features, only mapping what exists to what is required.

---

## 1. Core Infrastructure & Architecture

### 1.1 AOS (AurumAI Operating System)

| Document | Status | Alignment | Knowledge Integration | Action |
|----------|--------|-----------|----------------------|--------|
| `00_PROJECT_CONSTITUTION.md` | Complete | Fully aligned. Governance-first approach matches institutional methodological rigor. | KR-000 (project identity) | Keep |
| `01_PROJECT_NORTH_STAR.md` | Complete | Epistemic rigor, institutional transparency, domain authority all map to Meth. Sections 5 (Confidence) and 10 (Bias Prevention). | KR-000 | Keep |
| `02_PROJECT_STATE.md` | Complete | Aligned. Documents "where we are" — mirrors analyst's self-assessment. | KR-000 | Keep |
| `03_ARCHITECTURE_AUTHORITY.md` | Complete | "Separation of Knowledge from Execution" maps directly to institutional divide between research and trading. "Confidence as First-Class Citizen" maps to Meth. Section 5. | KR-000 | Keep |
| `04_ROADMAP.md` | Complete | Phase structure (Foundation → Architecture → Implementation → Validation) mirrors institutional research pipeline. | KR-000 | Keep |
| `05_DECISIONS.md` | Complete | Maps to Meth. Section 10 (Attribution Error remedy — decision journal). | KR-000 | Keep |
| `06_ENGINEERING_RULES.md` | Complete | Maps to institutional engineering discipline. | — | Keep |
| `07_GLOSSARY.md` | Complete | Aligned. | — | Keep |
| `08_ONBOARDING.md` | Complete | Aligned. | — | Keep |
| `09_CONTEXT.md` | Complete | Maps to Meth. Section 1 (analyst's external scanning). | — | Keep |

### 1.2 InferencePipeline (`src/knowledge/pipeline/pipeline.py`)

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `InferencePipeline.run()` — stage orchestration | Complete | Pipeline stages (Lessons → Knowledge → Graph → Evidence → Reason → Decide) map to Meth. Section 4 (thesis formation chain). | Pipeline feeds all KR categories | Keep (frozen v1.0) |
| Stage: `_stage_build_lessons` | Complete | Maps to Meth. Section 1 (data ingestion). Only processes event data, no overnight/scanner inputs. | KR-001–KR-018 (real yields context) | Extend — add overnight scanner stage |
| Stage: `_stage_build_knowledge` | Complete | Maps to Meth. Section 4 (fundamental structure). Knowledge records encode empirical gold-event relationships. | All KR categories via condition columns | Keep |
| Stage: `_stage_compare_context` | Complete | Maps to Meth. Section 3 (conflict resolution via multi-window comparison). WGC GRAM-style. | KR-004 (regime-dependent coefficients) | Keep |
| Stage: `_stage_build_graph` | Complete | Maps to Meth. Section 8 (causal map / DAG). NetworkX knowledge graph. | All KR relations | Keep |
| Stage: `_stage_query_evidence` | Complete | Maps to Meth. Section 2 (event prioritization — matching evidence to query). | KR-001–KR-083 | Keep |
| Stage: `_stage_reason` | Complete | Maps to Meth. Section 4 (reasoning chain). | All KR | Keep (frozen v1.0) |
| Stage: `_stage_decide` | Complete | Maps to Meth. Section 4 (conclusion). Decision engine classifies STRONG_POSITIVE → INSUFFICIENT_EVIDENCE. | All KR | Keep (frozen v1.0) |
| Missing: Overnight market scanner stage | Missing | Meth. Section 1 (overnight APAC/European session data). Currently no pre-market horizon scan. | KR-001–KR-034 (rates, FX, cross-asset) | Add |
| Missing: Signal/Noise classification stage | Missing | Meth. Section 7 (noise filters, persistence thresholds, cross-asset confirmation). Currently no explicit noise classification step. | KR-019–KR-034 (FX noise filters), KR-073–KR-083 (ETF flow noise) | Add |
| Missing: Thesis update cycle | Missing | Meth. Section 6 (thesis update on new information). Pipeline is stateless per query — no incremental update mechanism. | All KR | Add |

---

## 2. Event System

### 2.1 MacroEvent Types (`src/knowledge/events/`)

| Event Type | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `CPIEvent` | Complete | Maps to Meth. Section 1 (economic data release). Encodes CPI → gold condition/return. | KR-051–KR-060 (inflation KRs) | Keep |
| `NFPEvent` | Complete | Maps to Meth. Section 1 (labour market data). | KR-001–KR-018 (rate sensitivity) | Keep |
| `GDPEvent` | Complete | Maps to Meth. Section 9 (growth regime indicator). | KR-051–KR-060 | Keep |
| `InterestRateEvent` | Complete | Maps to Meth. Section 2 (Tier 1 — Fed policy). | KR-001–KR-018 (real yields hierarchy) | Keep |
| `FOMCEvent` | Complete | Maps to Meth. Section 2 (Tier 1 — FOMC decisions). | KR-001–KR-018, KR-068 (CB independence) | Keep |
| `PPIEvent` | Complete | Maps to Meth. Section 1 (inflation data). | KR-051–KR-060 | Keep |
| `PMIEvent` | Complete | Maps to Meth. Section 9 (growth regime). | KR-056 (gold/copper growth signal) | Keep |
| `EventRegistry` | Complete | Maps to Meth. Section 2 (priority queue). Registry organises event types by knowledge version. | All event-linked KR | Keep |
| `ReleaseCalendar` | Complete | Maps to Meth. Section 1 (macro calendar). | — | Keep |
| `MacroEvent ABC` | Complete | Standard metadata, condition columns, knowledge version — maps to Meth. Section 4 (thesis structure). | — | Keep |
| Missing: Geopolitical event type | Missing | Meth. Sections 2, 9 (Geopolitical Stress regime). No event type for GPR spikes, sanctions, wars. | KR-061–KR-072 | Add |
| Missing: Central bank reserve event type | Missing | Meth. Sections 1, 2, 9 (CB buying — structural demand driver). | KR-035–KR-050 | Add |
| Missing: ETF flow event type | Missing | Meth. Section 1 (Western investor sentiment proxy). | KR-073–KR-083 | Add |
| Missing: DXY event type | Missing | Meth. Section 1 (USD direction — Tier 2 priority). DXY exists as context enrichment but not an event type with condition/return. | KR-019–KR-034 | Extend |

### 2.2 Event Priority & Triage

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| Priority queue (Tier 1/2/3) | Partial | `EventRegistry` orders by registration but lacks explicit priority tiers. Meth. Section 2 describes explicit 3-tier system. | Meth. Section 2 priority hierarchy | Extend — add Tier 1/2/3 tagging |
| Trigger levels per event | Missing | Meth. Section 2: "If CPI prints above X, then [action]". No trigger threshold system exists. | All KR with trigger fields | Add |
| Event impact pre-computation | Partial | Condition columns encode expected impact direction. Missing: magnitude quantification and historical correlation reference. | KR-001–KR-083 (strength fields) | Extend |

---

## 3. Knowledge Engineering

### 3.1 Lesson System

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `LessonBuilder` | Complete | Maps to Meth. Section 1 (extracting structured lessons from raw data). Converts event data → features → lessons. | — | Keep |
| `LessonBuilderConfig` | Complete | Horizons, condition columns, release calendar — maps to Meth. Section 2 (multi-horizon analysis). | — | Keep |
| `LessonSummaryAggregator` | Complete | Maps to Meth. Section 5 (confidence via sample count, return rate). Builds KnowledgeRecords from lessons. | All KR via condition/return | Keep |
| `LessonSummaryConfig` | Complete | Condition columns, institutional context — maps to Meth. Section 4 (thesis assumptions). | — | Keep |
| `FeatureExtractionEngine` | Complete | Maps to Meth. Section 1 (feature extraction from raw data). | — | Keep |
| Missing: Multi-window aggregation | Missing | WGC GRAM uses 14-year, 5-year, 1-year windows. Aggregator uses fixed condition → single window. | KR-002 (window-dependent coefficients) | Extend |
| Missing: Institutional context columns | Partial | `institutional_context_columns` exists in config but no pre-built institutional context data. | Meth. Section 4 (institutional framing) | Extend |

### 3.2 Knowledge Records

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `KnowledgeRecord` (`src/knowledge/integrity/knowledge_record.py`) | Complete | Maps to Meth. Section 4 (thesis with evidence, confidence, assumptions). Contains: knowledge_id, confidence, sample_count, bias, return. | KR template (standard fields) | Keep |
| `SourceData` entity | Complete | Maps to Meth. Section 1 (evidence provenance). | — | Keep |
| `VersionedStore` | Complete | Maps to Meth. Section 6 (thesis versioning). | — | Keep |
| `LineageRegistry` | Complete | Maps to Meth. Section 4 (evidence chain). Bidirectional trace: source_data → lesson → knowledge_record → evidence → reasoning_chain → decision. | All KR with provenance | Keep |
| Missing: Institutional methodology version field | Missing | Meth. Section 5 references methodology_version for confidence calibration. Not present in KnowledgeRecord. | KR cross-references | Extend |
| Missing: Failure conditions field | Missing | Every KR in Knowledge Base has explicit Failure Conditions. KnowledgeRecord does not encode this. | All KR failure_conditions | Extend |
| Missing: Regime dependence field | Missing | Every KR specifies Regime Dependence. Not encoded in KnowledgeRecord. | All KR regime_dependence | Extend |
| Missing: Evidence reference field | Partial | `evidence_references` exists in CBI/CFI/CAI contracts but not in core KnowledgeRecord. | All KR references | Extend |

### 3.3 Knowledge Graph

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `KnowledgeGraph` (NetworkX MultiDiGraph) | Complete | Maps to Meth. Section 8 (causal map / DAG for gold). Nodes = knowledge records, edges = relations. | All KR as nodes | Keep |
| `GraphBuilder.build()` | Complete | Builds graph from knowledge records with indexed grouping (O(n²) → O(n)). | — | Keep |
| `GraphNode` / `GraphRelation` | Complete | Typed nodes and relations with properties. | — | Keep |
| Missing: Causal direction on edges | Partial | `GraphRelation` has relation_type but not explicit causal direction. Meth. Section 8 demands DAG with directed causal relationships. | KR-001–KR-083 causal mechanisms | Extend |
| Missing: Relation strength/confidence on edges | Missing | Meth. Section 8 requires confidence per causal relationship. Graph edges lack confidence/strength fields. | All KR strength, confidence | Extend |
| Missing: Regime-dependent relations | Missing | Meth. Section 9: relationships change by regime. Graph is static — no regime-conditional edges. | KR-001–KR-083 regime_dependence | Add |

---

## 4. Evidence System

### 4.1 Evidence Collection & Query

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `Evidence` (`src/knowledge/evidence/evidence.py`) | Complete | Maps to Meth. Section 4 (evidence structure: direction, magnitude, confidence). Contains: bias, confidence, sample_count, average_return_pct. | All KR transformed to evidence | Keep |
| `EvidenceCollection` | Complete | Composite evidence container. | — | Keep |
| `EvidenceQuery.matching()` | Complete | Maps to Meth. Section 2 (evidence prioritization — filter by event_type, condition, horizon). | — | Keep |
| `EvidenceRanker` | Complete | Maps to Meth. Section 3 (evidence weighting by relevance). | — | Keep |
| Missing: Cross-asset confirmation query | Missing | Meth. Section 7: "Is the move confirmed by other assets?" No cross-asset evidence correlation check. | KR-008, KR-011, KR-022 | Add |
| Missing: Historical analogue retrieval | Missing | Meth. Section 4: "Have similar macro configurations occurred before?" No historical pattern matching. | All KR with historical_evidence | Add |

### 4.2 Evidence Weighting

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `EvidenceWeighter` | Complete | Maps to Meth. Section 3 (re-weighting evidence). 5 factors: confidence, sample, provenance, consistency, recency. | — | Keep |
| `WeightConfig` | Complete | Configurable exponents, baselines, decay. | — | Keep |
| `WeightedAggregate` | Complete | Weighted avg return, confidence, effective sample size, attribution. Maps to Meth. Section 4 (quantified thesis). | — | Keep |
| Multi-factor geometric/arithmetic combine | Complete | Maps to Meth. Section 3 (multi-evidence synthesis). | — | Keep |
| Missing: Regime-dependent weighting | Missing | Meth. Section 9: "Do not use Regime 1 indicators in Regime 2." Weighter is regime-agnostic. | KR-001–KR-083 regime_dependence | Extend — add regime-aware weight multipliers |
| Missing: Narrative coherence factor | Missing | Meth. Section 3 (MATT framework — market agreement as cross-check). No narrative/consensus dimension. | KR-061–KR-072 (narrative risk) | Add |
| Missing: Term premium weight adjustment | Missing | Meth. Section 9 / KR-004: term premium replaced real yields post-2022. Weighter has no variable substitution logic. | KR-004 | Extend |

---

## 5. Reasoning Engine

### 5.1 Reasoning Chain

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `ReasoningEngine.reason()` | Complete | Maps to Meth. Section 4 (thesis formation chain). Produces fully traceable ReasoningChain with steps. | — | Keep (frozen v1.0) |
| ReasoningStep types: EVIDENCE_REVIEW, COMPARISON, AGGREGATION, CONCLUSION | Complete | Maps to Meth. Section 4 (Goldman Sachs 5-layer chain: narrative → fundamental → valuation → fragility → conclusion). Missing: fragility audit step. | — | Keep |
| `ReasoningChain.overall_confidence` | Complete | Maps to Meth. Section 5 (aggregated confidence from evidence). | — | Keep |
| `ReasoningChain.attribution` | Complete | Maps to Meth. Section 8 (causal attribution per event type). | — | Keep |
| Cross-event evidence comparison | Complete | `_add_comparison_steps` — maps to Meth. Section 3 (conflict resolution across event types). | — | Keep |
| Missing: Fragility audit step | Missing | Meth. Section 4 (Goldman Sachs step 4): "What could break the thesis?" No explicit fragility/counterfactual reasoning step. | KR failure_conditions | Extend |
| Missing: Variant view step | Missing | Meth. Section 4 (Goldman Sachs variant view): "What does the market think vs what do I think?" No consensus vs variant comparison. | — | Add |
| Missing: Scenario analysis | Missing | Meth. Section 5 (J.P. Morgan multiple scenario paths). ReasoningChain produces single conclusion, not scenario distribution. | KR-009 (asymmetric impact) | Add |
| Missing: Cross-asset confirmation step | Missing | Meth. Section 7: "Gold down alone = noise; gold down + silver down + DXY up = signal." No cross-asset confirmation in reasoning. | KR-008, KR-011, KR-022 | Add |

### 5.2 Reasoning Context

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `ReasoningContext` | Complete | Contains: event_type, condition, horizon_days, institutional_context. Maps to Meth. Section 4 (thesis parameters). | — | Keep |
| Institutional context propagation | Complete | ADR-003. Institutional_context_columns flow through pipeline. Maps to Meth. Section 1 (firm-specific lens). | — | Keep |

---

## 6. Decision Engine

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `DecisionEngine.decide()` | Complete | Maps to Meth. Section 4 (conclusion: adopt/reject/defer thesis). | — | Keep (frozen v1.0) |
| Decision types: STRONG_POSITIVE, POSITIVE, NEUTRAL, NEGATIVE, STRONG_NEGATIVE, INSUFFICIENT_EVIDENCE | Complete | Maps to Meth. Section 5 (confidence spectrum: investment-grade → speculative). Plus explicit "I don't know" via INSUFFICIENT_EVIDENCE. | — | Keep |
| `DecisionContext` | Complete | Event type, query, institutional context. | — | Keep |
| `Decision.confidence` | Complete | Maps to Meth. Section 5 (traceable confidence). | — | Keep |
| Missing: "Monitor" decision type | Missing | Meth. Sections 1, 6: "Monitor — the move is potentially significant but requires more data." Decision engine only outputs directional binaries + INSUFFICIENT_EVIDENCE. No "monitor/watch" state. | — | Extend |
| Missing: "Hedge" decision type | Missing | Meth. Section 6: "Hedge — add a risk overlay while maintaining core view." No hedge recommendation output. | — | Extend |
| Missing: Position sizing output | Missing | Meth. Section 5: confidence → position sizing. Decision outputs direction/confidence but not suggested position size. | — | Extend |
| Missing: Thesis update triggers in output | Missing | Meth. Section 6: "Triggers for exit — price levels, data prints, events." Decision has no trigger level output. | All KR trigger fields | Extend |

---

## 7. Forecasting Intelligence

### 7.1 Forecast Context

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `ForecastContext` | Complete | Contains: regime, news mood, FOMC mood, recent events, data date range. Maps to Meth. Section 1 (morning briefing inputs). | — | Keep |
| `ForecastContextBuilder` | Complete | Aggregates regime + sentiment + events into context. Maps to Meth. Section 1 (integrating overnight inputs). | — | Keep |
| `EventSummary` | Complete | Event_type, date, condition, gold direction, return. Maps to Meth. Section 1 (yesterday's event outcomes). | — | Keep |
| Missing: Overnight market data context | Missing | Meth. Section 1 (overnight APAC/European gold, DXY, yields, equities). Not included in ForecastContext. | KR-001–KR-034 | Extend |
| Missing: Positioning context | Missing | Meth. Section 1 (COT z-score, ETF flows, open interest). Not included. | KR-073–KR-083 (ETF/positioning KRs) | Extend |
| Missing: Risk report context | Missing | Meth. Section 1 (overnight P&L, VaR, margin utilization). Not included. | — | Extend |

### 7.2 Forecast Models & Confidence

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `ForecastKnowledge.forecast()` | Complete | Maps to Meth. Section 4 (quantitative forecasting — training data → forecast). | — | Keep |
| `MacroForecaster` | Complete | Multi-model ensemble forecasting with statsforecast. | — | Keep |
| `ForecastRegistry` | Complete | Model specs with approval workflow. Maps to Meth. Section 5 (model stability, validation). | — | Keep |
| `ForecastConfidenceComputer` | Complete | 3 components: spread_score, agreement_score, context_coherence. Maps to Meth. Section 5 (signal strength + signal breadth + regime clarity). | — | Keep |
| ForecastConfidence weights: 30% spread, 40% agreement, 30% coherence | Complete | Maps to Meth. Section 5 (meta-evidence: prediction intervals, cross-model agreement, cross-signal consistency). | — | Keep |
| `ForecastEvidence` / `ForecastEvidenceBuilder` | Complete | Maps to Meth. Section 4 (evidence structure with provenance). | — | Keep |
| `ForecastProvenance` | Complete | Model version, training window, data hash, git commit. Maps to Meth. Section 5 (model versioning for confidence). | — | Keep |
| `ForecastAssessment` | Complete | STRONG / MODERATE / UNCERTAIN / WEAK / INSUFFICIENT. Maps to Meth. Section 5 (confidence spectrum). | — | Keep |
| Missing: Out-of-sample confidence calibration | Partial | `ChronologicalOOSEngine` exists but not integrated into ForecastConfidence. ECE calibration not used for confidence adjustment. | — | Extend — wire OOS calibration into confidence |
| Missing: Signal breadth across asset classes | Missing | Meth. Section 5: "Is thesis supported by signals across independent asset classes?" Agreement is cross-model, not cross-asset. | KR-008, KR-011, KR-029 | Extend |

### 7.3 Forecasting Validation

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `ForecastValidation` | Complete | Directional accuracy, precision/recall, coverage, ECE. Maps to Meth. Section 5 (model validation). | — | Keep |
| `ChronologicalOOSEngine` | Complete | Strict train/eval split, no future leakage. Maps to Meth. Section 5 (out-of-sample testing). | — | Keep |
| `ExperimentRunner` / `ExperimentComparator` | Complete | A/B testing framework for forecasting changes. Maps to institutional research discipline. | — | Keep |
| `ExperimentRegistry` | Complete | Immutable, deterministic ID, approval workflow. Maps to institutional experiment governance. | — | Keep |
| Missing: GRAM-style rolling window validation | Missing | Meth. Section 8 (WGC GRAM: 14-year, 5-year, 1-year windows). OOS is single split, not rolling/multiple windows. | KR-002 (window-dependent coefficients) | Extend |

---

## 8. Risk Intelligence

### 8.1 Risk Measures

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| VaR (historical/parametric) | Complete | Maps to Meth. Section 1 (risk report — VaR). | — | Keep |
| CVaR | Complete | Maps to institutional risk reporting. | — | Keep |
| TailRiskDetector (Peaks-over-Threshold EVT) | Complete | Maps to Meth. Section 2 (black swan / tail risk identification). | — | Keep |
| Missing: Gold-specific risk measures | Missing | GOFO, gold lease rates, Shanghai premium — not in risk module. | KR-044, KR-072 | Add |

### 8.2 Position Sizing

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `VolatilityTargetSizer` | Complete | Maps to Meth. Section 5 (confidence → position sizing via volatility). | — | Keep |
| `DrawdownManager` | Complete | Maps to Meth. Section 1 (drawdown states: halt/caution/normal). | — | Keep |
| `KellyCap` | Complete | Position sizing with Kelly criterion. | — | Keep |
| `RiskParitySizer` | Complete | Maps to Bridgewater risk parity approach. | — | Keep |
| Missing: Confidence → position sizing mapping | Missing | Meth. Section 5: low confidence = 0.5-1%, high confidence = 3-5%. No explicit confidence→size table. | — | Extend |
| Missing: Entry technique recommendation | Missing | Meth. Section 5: low confidence = limit orders/scaling in; high confidence = market orders. Sizer doesn't recommend entry method. | — | Extend |

### 8.3 Decision Gate

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `DecisionGate` | Complete | Maps to Meth. Section 6 (scale/exit/pause/halt decisions). Evaluates: regime, uncertainty, scaling, drawdown. | — | Keep |
| `RegimeRiskOverlay` | Complete | Maps to Meth. Section 9 (regime-specific risk multipliers: EXPANSION=1.0, CRISIS=0.25). | KR-001–KR-083 regime_dependence | Keep |
| `UncertaintyBudget` | Complete | Maps to Meth. Section 3 (defer decision when uncertainty exceeds budget). | — | Keep |
| `RiskDecision` | Complete | Actions: proceed, scale_down, delay, halt. Maps to Meth. Section 6 decision options. | — | Keep |
| Missing: "Reverse" and "Flip" decision actions | Missing | Meth. Section 3 (flip — conflicting evidence strong enough to reverse core view). Meth. Section 6 (exit — thesis invalidated). Not in DecisionGate actions. | — | Extend |
| Missing: "Monitor" decision action | Missing | Meth. Section 3 (defer — wait for additional data). "Delay" exists but is risk-based, not information-based. | — | Extend |

---

## 9. Institutional Intelligence Layers

### 9.1 Central Bank Intelligence (CBI)

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `PolicyBiasScore` contract | Complete | Maps to Meth. Section 2 (Tier 1 — Fed policy). Central bank direction + confidence. | KR-001–KR-006, KR-013 | Keep |
| `RatePathProjection` contract | Complete | Maps to Meth. Section 6 (rate path — thesis update trigger). | KR-006, KR-013 | Keep |
| `ForwardGuidanceRecord` contract | Complete | Maps to Meth. Section 1 (overnight research — Fed speeches). | KR-014 (rate sensitivity) | Keep |
| `LiquidityOutlook` contract | Complete | Maps to Meth. Section 9 (Deflationary/Crisis regime — liquidity measures). | KR-022 (dollar liquidity) | Keep |
| `GlobalMonetaryRegime` contract | Complete | Maps to Meth. Section 9 (global regime classification). | KR-017 (fiscal dominance) | Keep |
| `CbiEvidenceAdapter` (5 adapters) | Complete | Converts CBI contracts to Evidence. Maps to Meth. Section 4 (evidence input for reasoning). | All CBI KRs | Keep |
| `CbiRepository` | Complete | Storage for CBI records. | — | Keep |
| Missing: Fed credibility scoring | Missing | KR-068 (CB independence threat), KR-004 (term premium as fiscal credibility proxy). No Fed credibility metric. | KR-068, KR-004 | Add |
| Missing: Central bank policy surprise index | Missing | Meth. Section 2: "Has the market already priced this in?" No policy surprise / central bank communication delta. | KR-001–KR-018, KR-068 | Add |

### 9.2 Capital Flow Intelligence (CFI)

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `ETFFlowMonitor` contract | Complete | Maps to Meth. Section 1 (gold ETF flows — Western investor sentiment). Momentum assessment, price/flow divergence. | KR-073–KR-083 | Keep |
| `CentralBankReserveFlowReport` contract | Complete | Maps to Meth. Section 1 (central bank buying — structural demand). Net purchases, trend, marginal buyers. | KR-035–KR-050 | Keep |
| `GoldPositioningDashboard` contract | Complete | Maps to Meth. Section 1 (COT z-score, options, dealer gamma). Composite assessment. | KR-073–KR-083 (ETF/positioning) | Keep |
| `CfiEvidenceAdapter` (3 adapters) | Complete | Converts CFI contracts to Evidence. | KR-035–KR-050, KR-073–KR-083 | Keep |
| Missing: Swiss refinery export monitor | Missing | KR-036: WGC triangulates true CB demand via Swiss customs data. No Swiss export connector. | KR-036 | Add |
| Missing: COMEX open interest connector | Missing | Meth. Section 1 (managed money net positioning COT z-score). Positioning dashboard references COT but no live connector. | KR-073, KR-078 | Add |
| Missing: Shanghai premium monitor | Missing | KR-081: Shanghai premium signals Asian demand vs Western. Referenced in GoldPositioningDashboard but no connector. | KR-081 | Add |

### 9.3 Cross-Asset Intelligence (CAI)

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `CrossAssetCorrelation` contract | Complete | Maps to Meth. Section 8 (correlation structure — causal vs spurious). Asset class pairs with trend direction. | KR-008 (real yields + DXY), KR-011 (diversification) | Keep |
| `SpreadAnalysis` contract | Complete | Maps to Meth. Section 8 (relative value — gold/copper, gold/oil, gold/S&P). Z-scores, mean reversion signals. | KR-055 (gold/oil), KR-056 (gold/copper), KR-057 (gold/S&P) | Keep |
| `VolatilityRegime` contract | Complete | Maps to Meth. Section 9 (volatility regime — crisis indicator). State transitions, tail risk index. | KR-016 (real yield volatility), KR-072 (gold vol) | Keep |
| `FlowPressure` contract | Complete | Maps to Meth. Section 6 (flow-driven markets). Intensity, volume z-score, concentration. | KR-022 (dollar liquidity), KR-077 (ETF reversal) | Keep |
| `RelativeValueAssessment` contract | Complete | Maps to Meth. Section 4 (valuation — implied equilibrium vs current). Z-score, percentile rank. | KR-055–KR-057 (cross-asset ratios) | Keep |
| `CaiEvidenceAdapter` (4 adapters) | Complete | Converts CAI contracts to Evidence. | All CAI KRs | Keep |
| `CaiRepository` | Complete | Storage for CAI records. | — | Keep |
| Missing: DXY-real yield co-dependence analysis | Missing | KR-008: real yields and DXY co-determine gold in normal regimes. No dedicated cross-asset analysis for this joint effect. | KR-008 | Add |
| Missing: Term premium → gold correlation monitor | Missing | KR-004: term premium replaced real yields as primary driver post-2022. No term premium connector or analysis. | KR-004 | Add |
| Missing: Gold-bitcoin ratio monitor | Missing | KR-053 (geopolitical stress — safe-haven competition). Referenced in methodology as regime indicator. | KR-053 | Add |
| Missing: Cross-asset confirmation matrix | Missing | Meth. Section 7: cross-asset confirmation for signal/noise classification. No matrix of confirming/cross signals. | KR-008, KR-011, KR-029 | Add |

### 9.4 Economic Intelligence

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `EconomicRegime` (`src/knowledge/economics/regime.py`) | Complete | 11 regime types: HIGH_INFLATION, STAGFLATION, RECESSION, etc. Maps to Meth. Section 9 (regime classification). | KR-051–KR-060 (inflation regimes) | Keep |
| `EconomicRegime` indicators dict | Complete | Maps to Meth. Section 9 (indicator hierarchy for each regime). | All KR with regime_dependence | Keep |
| `EconomicAdapter` | Complete | Adapter layer for economic data. | — | Keep |
| `EconomicClassifier` | Complete | Regime classification logic. | — | Keep |
| `EconomicCycle` | Complete | Cycle analysis. | — | Keep |
| `EconomicState` | Complete | State tracking. | — | Keep |
| Missing: Bridgewater 3-cycle framework | Missing | Meth. Section 4 / 9: productivity trend, long-term debt cycle (50-75yr), business cycle (5-8yr). Current regime system only has ~business cycle regimes. | KR-017 (fiscal dominance), KR-063 (lost decades) | Add |
| Missing: BlackRock MATT-style signal library | Missing | Meth. Section 2 / 4: cross-sectional signal library with non-negative constraint. Current system uses rule-based condition matching, not signal-weighted optimization. | All KR signals | Add |

### 9.5 Temporal Intelligence

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `TemporalAdapter` | Complete | Time series adapter for temporal reasoning. | — | Keep |
| `TemporalContext` | Complete | Time-aware context for reasoning. | — | Keep |
| `TemporalIndexer` | Complete | Indexing temporal events. | — | Keep |
| `TemporalPeriod` | Complete | Period analysis. | — | Keep |
| `TemporalState` | Complete | State tracking over time. | — | Keep |
| Missing: Rate of change detection | Missing | Meth. Section 7: "Is it a one-day blip or the start of a trend?" No velocity/acceleration signal for persistence classification. | KR-002, KR-016 | Add |
| Missing: Regime transition detection | Missing | Meth. Section 9: "Confidence lowest during regime transitions." No explicit regime transition classifier. | KR-003 (2022 structural break detection) | Add |

---

## 10. Macro Regime Intelligence

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `MacroRegimeDetector` (Markov 4-regime) | Complete | Maps to Meth. Section 9 (regime diagnosis). 4 states: EXPANSION, LATE_CYCLE, CONTRACTION, RECOVERY. | Meth. Section 9 regime framework | Keep |
| `CompositeScore` | Complete | Composite macro indicator for regime detection. | — | Keep |
| Regime labels: EXPANSION, LATE_CYCLE, CONTRACTION, RECOVERY | Complete | Maps partially to Meth. Section 9 regimes. | — | Keep |
| Missing: Meth. Section 9 regime alignment | Partial | Meth. Section 9 defines 6 regimes: Normal Growth, Inflationary, Stagflationary, Deflationary/Crisis, Geopolitical Stress, Structural Regime Change. Current detector has 4 business-cycle regimes (no inflation-specific, no geopolitical, no structural break). | KR-001–KR-083 regime_dependence | Extend — add 6-regime classifier |
| Missing: Regime-conditional indicator weighting | Missing | Meth. Section 9: indicator hierarchy changes by regime. Detector outputs regime label but doesn't provide indicator weights. | All KR regime_dependence | Add |
| Missing: Regime transition confidence | Missing | Meth. Section 9: confidence is lowest during transitions. Detector doesn't estimate transition probability. | KR-003 (break detection) | Extend |
| Missing: GRAM residual analysis | Missing | Meth. Section 9: "GRAM residual — unexplained variance as regime-change signal." No unexplained variance computation. | KR-003, KR-081 (regime change) | Add |

---

## 11. Causal Intelligence

### 11.1 Causal Graph

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `CausalGraph` (DAG) | Complete | Maps to Meth. Section 8 (directed causal graph for gold). Nodes = causal variables, edges = relations with direction. | All KR causal mechanisms | Keep |
| `CausalRelation` | Complete | Source → target with mechanism, direction, strength, confidence. Maps to Meth. Section 8 (causal classification). | All KR | Keep |
| `CausalHypothesis` | Complete | Testable hypothesis: cause → effect with evidence. Maps to Meth. Section 4 (thesis formation). | All KR | Keep |
| `CausalEvidence` | Complete | Supporting or contradicting evidence with strength. Maps to Meth. Section 8 (evidence for/against causal claim). | All KR | Keep |
| `CausalGraph.evaluate_hypothesis()` | Complete | Returns: PROPOSED / SUPPORTED / CONTRADICTED / INCONCLUSIVE. Maps to Meth. Section 8 (causal evaluation conclusion). | All KR | Keep |
| `CausalGraph.competing_hypotheses()` | Complete | Maps to Meth. Section 3 (competing narratives — Bridgewater's thoughtful disagreement). | All KR | Keep |
| Missing: Directed acyclic graph validation | Missing | Meth. Section 8: causal map is a DAG. CausalGraph doesn't validate acyclicity. | — | Extend |
| Missing: Causal mechanism description per edge | Missing | Meth. Section 8: "Mechanism clarity — is the causal chain explicable?" CausalRelation has mechanism field but no structured format. | All KR mechanism field | Extend |

### 11.2 Causal Analysis

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `CausalAnalyzer` | Complete | Analysis engine for causal relationships. | — | Keep |
| `CausalEvidence` collection | Complete | Supporting/contradicting evidence tracking. | — | Keep |
| Missing: Natural experiment identification | Missing | Meth. Section 8: "Periods where one driver changed while others stayed stable." No natural experiment detector for causal identification. | KR-003 (2022 natural experiment) | Add |
| Missing: Spurious correlation detection | Missing | Meth. Section 8: "No mechanism, breaks out of sample, reverse causality." No spurious correlation checker. | All KR counter_examples | Add |
| Missing: Regime-invariance testing | Missing | Meth. Section 8: "Does the relationship hold across different macro regimes?" No cross-regime stability test. | All KR regime_dependence | Add |

---

## 12. Context Enrichment

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `YieldContextEnricher` / `YieldContextConfig` | Complete | Maps to Meth. Section 1 (US10Y real yield context for event enrichment). | KR-001–KR-018 | Keep |
| `DXYContextEnricher` | Complete | Maps to Meth. Section 1 (DXY context). | KR-019–KR-034 | Keep |
| `ContextComparisonReport` / `ContextComparisonConfig` | Complete | Maps to Meth. Section 3 (comparing baseline vs contextual — WGC multi-window comparison). | — | Keep |
| `MultiFactorContextComparison` | Complete | Multi-factor context comparison. | — | Keep |
| Missing: BEI context enricher | Missing | KR-012, KR-053: breakeven inflation rate as separate signal. No BEI enrichment in pipeline. | KR-012, KR-053 | Add |
| Missing: Term premium context enricher | Missing | KR-004: term premium replaced real yields post-2022. No term premium enrichment. | KR-004 | Add |
| Missing: GPR context enricher | Missing | KR-061: Geopolitical Risk Index quantified impact on gold. No GPR enrichment. | KR-061–KR-072 | Add |

---

## 13. NLP / Sentiment

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `NewsSentimentAnalyzer` | Complete | Maps to Meth. Section 1 (overnight news scanning). Positive/negative/neutral classification. | — | Keep |
| `FOMCSentimentAnalyzer` | Complete | Maps to Meth. Section 2 (Fed speech analysis — hawkish/dovish). | KR-014, KR-068 | Keep |
| `NewsCollector` | Complete | RSS/news feed collection. | — | Keep |
| Missing: BlackRock MATT-style broker consensus | Missing | Meth. Section 1: "MLP applies LLM scorers to millions of broker notes." No multi-source broker note aggregation or sentiment consensus. | — | Add |
| Missing: Market narrative extraction | Missing | Meth. Section 4: "What does the market currently believe?" No narrative extraction or consensus classification. | — | Add |
| Missing: Signal/noise classification in NLP | Missing | Meth. Section 7: "Is the move explained by narrative?" Sentiment is binary — doesn't classify as signal vs noise. | KR-061–KR-072 | Extend |

---

## 14. Learning Engine

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `LearningEngine` | Complete | Maps to Meth. Section 6 (thesis refinement — learn from new data). | — | Keep (frozen v1.0) |
| `LearningSession` | Complete | Session tracking for learning episodes. | — | Keep |
| `LearningFeedback` | Complete | Feedback recording for outcome-based learning. | — | Keep |
| `LearningRecord` | Complete | Persistent record of learning. | — | Keep |
| `LessonSummaryAggregator` | Complete | Aggregates lessons into knowledge for learning. | All KR | Keep |
| Missing: Decision journal (attribution error remedy) | Missing | Meth. Section 10: "Maintain a decision journal — every thesis and trade is documented." No decision journal with outcome tracking. | — | Add |
| Missing: Post-mortem analysis | Missing | Meth. Section 10: "Good decisions that produced losses are studied." No post-mortem / retrospective analysis capability. | — | Add |
| Missing: Confidence calibration from outcomes | Missing | Meth. Section 5: confidence should be calibrated from out-of-sample track record. No automated confidence calibration loop. | — | Extend |

---

## 15. Knowledge Expansion Framework

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `EventScaffolder` + `ExpansionSpec` | Complete | Maps to Meth. Section 4 (new thesis scaffolding — structured template). | All KR templates | Keep |
| `EventValidator` + `ValidationReport` | Complete | Maps to Meth. Section 5 (validation — model stability checks). | All KR | Keep |
| `ExpansionLifecycle` + `ExpansionAudit` | Complete | Maps to Meth. Section 6 (thesis lifecycle — active, deprecated, retired). | — | Keep |
| Missing: WGC GRAM-style rolling coefficient monitoring | Missing | Meth. Section 9: "GRAM model's rolling windows detect regime shifts by showing which coefficients change." Expansion framework validates once, not continuously. | KR-002, KR-003 | Extend |

---

## 16. Integrity & Provenance

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `Provenance` (`knowledge/integrity/provenance.py`) | Complete | Created_at, source, model_version, git_commit, data_hash. Maps to Meth. Section 4 (evidence provenance). | — | Keep |
| `LineageRegistry` | Complete | Bidirectional trace: source_data ↔ lesson ↔ knowledge_record ↔ evidence ↔ reasoning_chain ↔ decision. | — | Keep |
| `LineageRelationType` | Complete | GENERATES, REFERENCES relationship types. | — | Keep |
| `VersionedStore` | Complete | Versioning for knowledge records. Maps to Meth. Section 6 (thesis versioning). | — | Keep |
| `FrozenDict` / atomic writes | Complete | Determinism hardening — maps to Meth. Section 4 (deterministic, auditable outputs). | — | Keep |
| Missing: Institutional auditor interface | Missing | Meth. Section 1 / North Star: "External auditors can validate reasoning without access to original authors." No auditor-facing export format or interactive trace view. | — | Add |

---

## 17. Connectors & Data Sources

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `fred_client.py` (FRED API) | Complete | Economic data source. Maps to Meth. Section 1 (macro data). | KR-001–KR-018 (yields, CPI, etc.) | Keep |
| `dxy_fetcher.py` (Yahoo Finance) | Complete | DXY index data. Maps to Meth. Section 1 (USD direction). | KR-019–KR-034 | Keep |
| `real_yield_fetcher.py` (FRED) | Complete | 10-year TIPS yield. Maps to Meth. Section 1 (real yields). | KR-001–KR-018 | Keep |
| `fomc_calendar.py` (FRED API) | Complete | FOMC meeting calendar. Maps to Meth. Section 2 (Tier 1 event scheduling). | — | Keep |
| `cb_gold_fetcher.py` (IMF IFS) | Complete | Central bank gold reserve data. Maps to Meth. Section 1 (CB buying). | KR-035–KR-050 | Keep |
| `yfinance` dependency | Complete | Gold spot, ETF data, general market data. | KR-073–KR-083 | Keep |
| Missing: COMEX positioning connector | Missing | Meth. Section 1 (COT report — managed money net positioning). | KR-073, KR-078 | Add |
| Missing: GPR index connector | Missing | KR-061: Geopolitical Risk Index. Maps to Meth. Section 2 (geopolitical prioritization). | KR-061–KR-072 | Add |
| Missing: Term premium data connector | Missing | KR-004: 10-year term premium (ACM model or similar). | KR-004 | Add |
| Missing: LBMA/GOFO connector | Missing | KR-044: gold lease rates, GOFO. Maps to Meth. Section 1 (gold-specific data). | KR-044 | Add |
| Missing: Swiss customs data connector | Missing | KR-036: Swiss refinery export data for CB demand triangulation. | KR-036 | Add |
| Missing: WGC demand data connector | Missing | Meth. Section 1 (WGC Gold Demand Trends quarterly). | KR-035–KR-050, KR-073–KR-083 | Add |
| Missing: BEI data connector | Missing | KR-012: 10-year breakeven inflation rate. | KR-012, KR-053 | Add |
| Missing: VIX/volatility connector | Missing | KR-016: MOVE index, VIX for volatility regime. | KR-016, KR-072 | Add |

---

## 18. Orchestration

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `InstitutionalOrchestrator` | Complete | Maps to Meth. Section 1 (morning routine orchestration). DAG-based pipeline job orchestration. | — | Keep |
| `Orchestrator` (core) | Complete | Base orchestrator with stage execution. | — | Keep |
| Orchestration stages: `_ingest_event`, `_ingest_news`, `_forecast`, `_forecast_confidence`, `_forecast_validation`, `_risk_measures`, `_position_sizing`, `_risk_gate`, `_build_context`, `_finalize` | Complete | Maps to Meth. Section 1 (systematic morning routine flow). | All KR | Keep |
| `CacheManager` | Complete | Stage caching for performance. | — | Keep |
| `CheckpointManager` | Complete | Restart capability from any stage. | — | Keep |
| `PipelineJob` | Complete | Job definition with DAG. | — | Keep |
| `DAG` (topological ordering) | Complete | Maps to Meth. Section 2 (priority ordering — dependencies before dependents). | — | Keep |
| `Aggregator` | Complete | Evidence aggregation across layers. | — | Keep |
| `LayerPolicy Engine` | Complete | Adaptive policy evaluation per intelligence layer. | — | Keep |
| Missing: Overnight scanner job | Missing | Meth. Section 1: pre-market scan of APAC/European moves, news, positioning. No scheduled overnight job. | KR-001–KR-034 | Add |
| Missing: Signal/noise classification job | Missing | Meth. Section 7: daily signal/noise log. No scheduled classification job. | All KR noise_filter fields | Add |
| Missing: Thesis update job | Missing | Meth. Section 6: formal thesis update when new information arrives. No trigger-based update pipeline. | — | Add |

---

## 19. Simulation & Experimentation

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `HistoricalReplay` | Complete | Maps to Meth. Section 6 (backtesting — how similar configurations behaved). | All KR historical_evidence | Keep |
| `ExperimentConfig` / `RunConfig` | Complete | A/B comparison framework. Maps to institutional research process. | — | Keep |
| `ExperimentRunner` | Complete | Runs OOS comparisons. | — | Keep |
| `ExperimentComparator` | Complete | Delta metrics: directional accuracy, precision, recall, coverage, ECE. | — | Keep |
| `ExperimentReportBuilder` | Complete | Human + machine-readable reports. | — | Keep |
| `ExperimentRegistry` | Complete | Immutable, deterministic, approval workflow. Maps to Meth. Section 5 (experiment governance). | — | Keep |
| `SimulationValidation` | Complete | Simulation validation framework. | — | Keep |
| `Attribution` (simulation) | Complete | Return attribution analysis. | — | Keep |
| Missing: Gold-specific scenario analysis | Missing | Meth. Section 4: Oxford Economics scenarios for gold under different macro paths. No scenario engine for gold. | KR-001–KR-083 | Add |
| Missing: Monte Carlo / stochastic simulation | Missing | Meth. Section 10 (BlackRock CMA: thousands of return pathways). No stochastic simulation for confidence intervals. | — | Add |

---

## 20. Paper Trading

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `VirtualPortfolio` | Complete | Cash, positions, P&L tracking. Maps to Meth. Section 1 (position and risk reports). | — | Keep |
| `ExecutionEngine` | Complete | Gated by DecisionGate. Maps to Meth. Section 6 (execute / scale / hedge / pause). | — | Keep |
| `SlippageModel` | Complete | Realistic execution cost modeling. | — | Keep |
| `CommissionModel` | Complete | Transaction cost modeling. | — | Keep |
| `PortfolioSnapshot` | Complete | Periodic portfolio state capture. | — | Keep |
| Missing: Gold-specific execution constraints | Missing | COMEX gold futures contract specs, LBMA spot settlement, ETF creation/redemption. Not modeled. | KR-044, KR-072 | Extend |

---

## 21. Benchmark & Validation

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| 18 benchmark tests | Complete | Maps to Meth. Section 5 (validation gate — system must pass before acceptance). | — | Keep |
| `InstitutionalValidation` (10 scenarios) | Complete | 10 institutional scenarios, 8 PASS / 2 WARNING. Maps to Meth. Section 4 (fragility audit). | — | Keep |
| `OOSValidationEngine` | Complete | Decision correctness, directional accuracy, ECE calibration. Maps to Meth. Section 5 (out-of-sample performance). | — | Keep |
| Full test suite (1638 tests) | Complete | Determinism, reproducibility verified (Grade A). | — | Keep |
| Missing: Institutional expert validation workflow | Missing | Meth. Section 2 / 10: "System outputs reviewed by domain experts." No workflow for expert feedback ingestion. | — | Add |

---

## 22. Gold Rule & Domain-Specific Logic

| Capability | Status | Alignment | Knowledge Integration | Action |
|-----------|--------|-----------|----------------------|--------|
| `gold_rule_001.py` | Complete | Domain-specific gold reasoning rule. | KR-001–KR-083 | Keep |
| `RULES` dict (`knowledge/rules.py`) | Complete | Static event→gold mapping (CPI→bullish, NFP→bearish, etc.). Maps to Meth. Section 1 (baseline heuristics). | KR-001–KR-060 | Keep — but note: these are simplistic heuristics, not institutional-grade |

---

## Summary: Action Priority

| Action | Count | Key Items |
|--------|-------|-----------|
| **Keep** | ~90 | All frozen v1.0 components, complete contracts, connectors, validators |
| **Extend** | ~35 | Add regime-aware weighting, OOS calibration into confidence, multi-window aggregation, missing decision action types, confidence→size mapping, thesis update triggers |
| **Add** | ~30+ | Overnight scanner stage, signal/noise classification, 6-regime classifier (Meth. Section 9), GRAM residual analysis, GPR/term premium/BEI connectors, narrative extraction, scenario analysis, fragility audit, variant view, decision journal, cross-asset confirmation matrix |
| **Replace** | 0 | No existing capability needs replacement — the codebase is well-engineered with clean contracts |
| **Remove** | 0 | No obsolete capabilities |
| **Freeze** | ~15 | Core v1.0: InferencePipeline, ReasoningEngine, DecisionEngine, Evidence, EventRegistry, Knowledge Expansion Framework, Benchmark |

---

## Institutional Methodology Coverage by Section

| Meth. Section | Capability Coverage | Gaps |
|--------------|-------------------|------|
| Section 1: Morning Routine | ~40% | No overnight scanner, no positioning data, no risk report context, no signal/noise log |
| Section 2: Event Prioritization | ~50% | No Tier 1/2/3 tagging, no trigger levels, no black swan classification |
| Section 3: Conflicting Evidence | ~60% | No re-weight by regime, no "defer until new data" decision action, no narrative coherence check |
| Section 4: Thesis Formation | ~55% | No fragility audit, no variant view, no scenario analysis, no explicit "what would disprove" |
| Section 5: Confidence Assignment | ~50% | No confidence→size mapping, no signal breadth across assets, no OOS calibration integration |
| Section 6: Thesis Update | ~20% | No incremental update mechanism, no pre-commitment triggers, no post-mortem |
| Section 7: Noise vs Signal | ~15% | No persistence analysis, no cross-asset confirmation, no signal/noise log |
| Section 8: Causal Evaluation | ~60% | No DAG acyclicity validation, no spurious correlation check, no natural experiment identification |
| Section 9: Regime Indicators | ~30% | Detector has 4 regimes (need 6), no regime-conditional weights, no GRAM residual, no transition detection |
| Section 10: Bias Prevention | ~25% | No decision journal, no pre-commitment triggers, no attribution error check |

## Knowledge Base Coverage by Category

| KR Category | Records | Code Integration | Coverage |
|-------------|---------|-----------------|----------|
| 1. Real Yields (KR-001–018) | 18 | ~60% | Yield enricher, CBI contracts, event conditions. Missing: term premium connector, multi-window aggregation |
| 2. USD/FX (KR-019–034) | 16 | ~50% | DXY context enricher, FX connectors. Missing: gold-DXY breakdown monitor, EM currency stress analysis |
| 3. Central Bank Demand (KR-035–050) | 16 | ~40% | CB gold fetcher, CFI contracts. Missing: Swiss customs connector, WGC demand data, country-level analysis |
| 4. Inflation/BE (KR-051–060) | 10 | ~30% | CPI event, PPI event. Missing: BEI connector, gold/oil/copper ratio monitors |
| 5. Geopolitical Risk (KR-061–072) | 12 | ~5% | No dedicated event types, no GPR connector, no sanctions analysis |
| 6. ETF Flows (KR-073–083) | 11 | ~30% | CFI contracts reference ETF flows. Missing: live ETF data connector, COT connector, flow momentum analysis |
| 7+ (remaining categories) | ~100+ | ~0% | Not yet mapped — knowledge records exist in document but no code adapters |

---

## Engineering Rules for Implementation

Per the AOS engineering rules and the constraint "Do NOT implement new features":

1. **Read the mapping before coding**. This document is the source of truth for what exists and what is missing.
2. **Extend, never replace**. Every "Extend" action above means add to existing contracts, not redesign them.
3. **Keep frozen components frozen**. Core v1.0 (InferencePipeline, ReasoningEngine, DecisionEngine, Evidence, EventRegistry, Knowledge Expansion Framework, Benchmark) must never be modified.
4. **Prefer adapters over new modules**. Where a methodology concept maps to an existing contract (e.g., CBI/CFI/CAI adapters), extend via adapter rather than creating a new module.
5. **Every new capability must pass the 18-benchmark suite**. No exceptions.
6. **Run full test suite before and after every change**. 1638+ tests must pass with zero regressions.
