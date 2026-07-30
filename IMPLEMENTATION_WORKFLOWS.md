# Implementation Workflows

> **Purpose**: Reorganize remaining work around institutional workflows from the Methodology, Knowledge Base, and Implementation Mapping. Each workflow is a complete end-to-end process that reuses existing capabilities and fills identified gaps. Workflows, not modules, are the unit of implementation.

---

## Workflow Index

| # | Workflow | Meth. Section | Priority Tier |
|---|----------|---------------|---------------|
| W1 | Knowledge Record Ingestion & Encoding | KB (all categories) | **P0 — Foundation** |
| W2 | Macro Regime Diagnosis & Indicator Selection | §9 | **P0 — Foundation** |
| W3 | Pre-Market Intelligence Scan | §1 | **P1 — Daily Core** |
| W4 | Macro Event Prioritization & Triage | §2 | **P1 — Daily Core** |
| W5 | Signal vs Noise Classification | §7 | **P1 — Daily Core** |
| W6 | Evidence Collection & Regime-Aware Weighting | §3, §5 | **P1 — Daily Core** |
| W7 | Conflicting Evidence Resolution | §3 | **P2 — Analytical** |
| W8 | Investment Thesis Formation | §4 | **P2 — Analytical** |
| W9 | Confidence Assignment & OOS Calibration | §5 | **P2 — Analytical** |
| W10 | Thesis Update Cycle | §6 | **P2 — Analytical** |
| W11 | Causal Relationship Evaluation & Graph Maintenance | §8 | **P3 — Advanced** |
| W12 | Fragility Audit & Scenario Analysis | §4, §10 | **P3 — Risk** |
| W13 | Bias Prevention & Decision Review | §10 | **P3 — Quality** |
| W14 | Decision Journal & Post-Mortem | §10 | **P3 — Learning** |
| W15 | Cross-Asset Confirmation Matrix | §7, §8 | **P4 — Enhancement** |
| W16 | Multi-Window Evidence Aggregation (GRAM) | §3, §9 | **P4 — Enhancement** |
| W17 | Institutional Auditor Interface | North Star, §4 | **P4 — Compliance** |

---

## Workflow Specifications

---

### W1: Knowledge Record Ingestion & Encoding

**Objective**: Encode every Knowledge Record from `Institutional_Gold_Knowledge_Base.md` into the system so it becomes machine-readable, queryable, and usable by every downstream workflow.

**Source**: KB (all 19 categories, ~207+ records). Meth. §4 (thesis structure: mechanism, preconditions, trigger, expected impact, strength, confidence, evidence, counter-examples, regime dependence, failure conditions, references).

**Trigger**: New or updated Knowledge Record added to the KB document. Initial batch ingestion of all existing records.

**Inputs**:
- `Institutional_Gold_Knowledge_Base.md` — structured KR documents
- Existing `KnowledgeRecord` schema (knowledge_id, confidence, sample_count, bias, return)
- Implicit KR schema from KB (mechanism, precondition, trigger, expected_impact, strength, regime_dependence, failure_condition, historical_evidence, counter_examples, references)

**Processing Stages**:
1. **Schema extension** — Add missing fields to `KnowledgeRecord`: `failure_conditions`, `regime_dependence`, `references`, `mechanism`, `preconditions`, `trigger`, `expected_impact`, `counter_examples`, `methodology_version`
2. **KR extraction** — Parse each KR's structured fields from the markdown document into typed Python dataclasses
3. **Adapter assignment** — Route each KR to its appropriate adapter (CBI for central bank KRs, CFI for flow KRs, CAI for cross-asset KRs, or Evidence adapter for event KRs)
4. **Graph node creation** — Create `GraphNode` for each KR with typed properties, regime-dependent relation markers, and causal direction flags
5. **Lineage registration** — Register each KR in `LineageRegistry` with source reference to the KB document
6. **Validation** — `EventValidator` checks KR completeness: every field populated, references valid, regime_dependence in valid set

**Existing Capabilities Reused**:
- `KnowledgeRecord`, `SourceData`, `Provenance` — entity contracts
- `GraphBuilder` — creates nodes from records
- `LineageRegistry` — provenance tracking
- `CbiEvidenceAdapter`, `CfiEvidenceAdapter`, `CaiEvidenceAdapter` — KR-to-Evidence conversion
- `EventValidator`, `ExpansionSpec` — validation scaffolding
- `KnowledgeGraph` — stores typed nodes
- `CausalRelation`, `CausalGraph` — causal mechanism encoding

**Missing Capabilities Needed**:
- `KnowledgeRecord` field extensions (failure_conditions, regime_dependence, mechanism, preconditions, trigger, expected_impact, counter_examples, methodology_version)
- KR markdown parser (structured extraction from KB document)
- KR-to-GraphNode adapter with regime-dependent edge properties
- Causal direction and confidence fields on graph edges
- Regime-dependent relation markers on graph edges

**Expected Outputs**:
- Fully populated `KnowledgeGraph` with typed nodes for every KR
- `CausalGraph` with directed, confidence-weighted causal edges
- Every KR queryable by: event_type, condition, regime, horizon, mechanism, failure_condition
- Provenance chain from KR → KB document section → source reference

**Completion Criteria**:
- All 207+ KRs parsed and encoded as graph nodes
- All KR field values (mechanism, preconditions, trigger, expected_impact, regime_dependence, failure_condition) populated
- Graph edges have causal direction, confidence, and regime-dependence markers
- CausalGraph validates as acyclic
- Lineage traceable from any KR node back to its source document section
- Existing 18-benchmark suite passes
- Zero regressions in 1638+ test suite

---

### W2: Macro Regime Diagnosis & Indicator Selection

**Objective**: Classify the current macro regime into one of the six institutional categories (Normal Growth, Inflationary, Stagflationary, Deflationary/Crisis, Geopolitical Stress, Structural Regime Change) and output the correct indicator hierarchy for that regime.

**Source**: Meth. §9 (regimes, dominant indicators, secondary, weaker). KB KR-001–KR-083 (regime_dependence per KR). Bridgewater 3-cycle framework, BlackRock signal library, WGC GRAM rolling windows.

**Trigger**: Daily (pre-market), on-demand (after significant data release), or automatically when regime transition confidence crosses a threshold.

**Inputs**:
- Macro data: GDP growth, CPI, core PCE, unemployment, retail sales, industrial production
- Market data: real yields (TIPS 10Y), DXY, breakeven inflation rate (BEI), VIX, term premium
- Gold-specific data: CB buying volume (8Q rolling avg), gold ETF flows (2W rolling), COMEX managed money z-score, GPR index
- Current `EconomicRegime` state with regime labels and confidence
- Existing `CompositeScore` for Markov regime switching

**Processing Stages**:
1. **Data collection** — Fetch all regime-relevant indicators via connectors (FRED, yfinance, GPR, BEI, term premium)
2. **Composite scoring** — Compute composite macro indicator using current data (reuse `CompositeScore`)
3. **6-regime classification** — Classify into Meth. §9 regimes: Normal Growth, Inflationary, Stagflationary, Deflationary/Crisis, Geopolitical Stress, Structural Regime Change (extend from current 4-regime Markov detector)
4. **Regime transition detection** — Compute transition probabilities between regimes; flag if confidence < 0.5 (regime transition state)
5. **Indicator hierarchy generation** — For the diagnosed regime, output the ordered list (dominant → secondary → weaker) with associated KRs
6. **GRAM residual computation** — Compute unexplained variance: gold return minus predicted return from current regime's dominant indicators. Growing residual → flag Structural Regime Change
7. **Cross-asset consistency check** — Verify all asset classes tell the same regime story; flag inconsistencies

**Existing Capabilities Reused**:
- `MacroRegimeDetector` — Markov 4-regime switching (foundation)
- `CompositeScore` — composite indicator
- `EconomicRegime` — regime dataclass with indicators dict
- `EconomicClassifier`, `EconomicCycle` — regime logic
- `TemporalState`, `TemporalPeriod` — time-aware tracking
- `RegimeRiskOverlay` — regime→risk multiplier mapping
- `fred_client.py`, `dxy_fetcher.py`, `real_yield_fetcher.py` — data connectors
- W1 output — encoded KRs with regime_dependence fields
- `RegimeRiskOverlay` — regime multipliers

**Missing Capabilities Needed**:
- 6-regime classifier (extend Markov detector from 4 → 6 states with gold-specific regime features)
- Regime transition probability computation
- GRAM residual analysis module (rolling regression + unexplained variance tracker)
- Indicator hierarchy generator (regime→ordered list of indicators→associated KRs)
- Term premium data connector (FRED ACM model or equivalent)
- BEI data connector (FRED T5YIE or T10YIE)
- GPR data connector
- Cross-asset regime consistency checker
- Regime transition confidence estimator

**Expected Outputs**:
- Regime classification: label (Normal/Inflationary/Stagflationary/Deflationary/Geopolitical/Structural Change)
- Transition confidence: 0.0–1.0 (low = in transition)
- Indicator hierarchy: list of (indicator_name, weight, associated_KRs, tier: dominant/secondary/weaker)
- GRAM residual: unexplained variance % and trend (growing/stable/shrinking)
- Cross-asset consistency: map of (asset_class, regime_signal, concordance_flag)
- Regime change trigger levels: "if X crosses Y, regime reclassification triggered"

**Completion Criteria**:
- 6-regime classifier outputs labels that match Meth. §9 taxonomy
- Indicator hierarchy matches Meth. §9 specifications per regime
- Regime transition detection within 2σ of retrospective expert classification on 10-year historical sample
- GRAM residual flags the 2022 regime break within 3 months of occurrence
- Cross-asset consistency checker identifies known inconsistency periods (2022 gold/DXY co-move)
- Wired into `InstitutionalOrchestrator` as upstream dependency for all reasoning stages
- All existing tests pass, 18 benchmarks pass

---

### W3: Pre-Market Intelligence Scan

**Objective**: Produce the morning briefing — overnight market moves, news, data releases, positioning, and risk report — before the trading day begins.

**Source**: Meth. §1 (morning routine). KB KR-001–KR-034 (rates, FX), KR-061–KR-072 (geopolitical), KR-073–KR-083 (ETF/positioning).

**Trigger**: Daily, before market open (configurable: 6:00 AM UTC default).

**Inputs**:
- Overnight price data: XAU/USD, DXY, US10Y real yield, US10Y nominal yield, BEI, S&P 500 futures, Brent crude, EUR/USD, USD/JPY (from yfinance + FRED)
- Overnight news headlines: RSS feeds from major financial news sources (via `NewsCollector`)
- Overnight research notes: sell-side broker reports (scraped or fed via API)
- Economic release calendar for the day ahead (via `ReleaseCalendar`)
- Current position/P&L snapshot (via `VirtualPortfolio`)
- Risk metrics: VaR, CVaR, drawdown state (via VaR/CVaR/TailRiskDetector)
- Gold-specific: COMEX open interest, gold ETF flow (daily), GLD/IAUM holdings change

**Processing Stages**:
1. **Overnight market data fetch** — Pull all overnight market data across APAC and European sessions. Compute changes from previous close
2. **Overnight news ingestion** — Collect and classify headlines via `NewsSentimentAnalyzer`. Flag geopolitical, central bank, and policy-relevant stories
3. **Research report ingestion** — Parse sell-side notes (if available via API); extract key themes, ratings, target changes
4. **Risk report generation** — Compile overnight P&L, current exposure, VaR utilization, drawdown status via `RiskMeasures`
5. **Positioning data fetch** — Pull COMEX managed money COT (weekly), latest ETF flow data (daily), LBMA/GOFO rates
6. **Anomaly detection** — Flag any position that moved >2σ overnight; flag diverging signals (gold up + real yields up = template violation)
7. **Briefing assembly** — Compile all data into structured `ForecastContext` with:
   - Overnight changes table (instrument, previous close, current, change %, change σ)
   - News summary (headlines, sentiment, relevance score)
   - Risk snapshot (P&L, VaR util%, drawdown status)
   - Positioning snapshot (COT z-score, ETF flow momentum, open interest change)
   - Anomaly flags (template violations, diverging signals, gap risk)
   - Watchlist: key data releases and events for the day

**Existing Capabilities Reused**:
- `ForecastContext`, `ForecastContextBuilder` — context assembly
- `NewsSentimentAnalyzer`, `NewsCollector` — news ingestion
- `FOMCSentimentAnalyzer` — central bank speech analysis
- `EventSummary` — recent event tracking
- `VirtualPortfolio`, `PortfolioSnapshot` — position tracking
- VaR, CVaR, TailRiskDetector — risk metrics
- `DrawdownManager` — drawdown states
- `ReleaseCalendar` — economic calendar
- `dxy_fetcher.py`, `real_yield_fetcher.py`, `fred_client.py` — data connectors
- W2 output — current regime classification for context
- W1 output — encoded KRs for news relevance flagging

**Missing Capabilities Needed**:
- Overnight market data fetcher (orchestrated batch of yfinance/FRED calls for APAC/European session)
- COT positioning connector (CFTC weekly report parser or API)
- Gold ETF daily flow connector (GLD/IAUM holdings change from yfinance or WGC)
- LBMA/GOFO connector
- Anomaly detection engine (template violation detection, cross-asset divergence flagging, position gap risk)
- Overnight news relevance scorer (assign relevance score to each headline based on current positions/KRs)
- Broker research note parser (if notes available via API; otherwise placeholder for manual feed)
- Pre-market briefing output format (structured dict/json for orchestrator downstream consumption)

**Expected Outputs**:
- `ForecastContext` extended with: overnight_market_changes, overnight_news, risk_snapshot, positioning_snapshot, anomaly_flags, day_watchlist
- `PipelineContext` enriched for downstream InferencePipeline consumption
- Structured briefing in machine-readable format (for internal consumption) and human-readable summary (for logging/audit)

**Completion Criteria**:
- All overnight market data fetched and normalized within 5 minutes of scheduled run
- News headlines classified with positive/negative/neutral and relevance score per active position
- COMEX positioning fetched (weekly) and cached
- ETF flow data fetched (daily) and trend-classified
- Template violations flagged: gold/DXY co-move, gold/real-yield divergence, gold/equity correlation shift
- Briefing produced as structured output consumed by W4 (Event Prioritization) and W5 (Noise/Signal)
- Wired into `InstitutionalOrchestrator` as the first scheduled job of the day
- All existing tests pass

---

### W4: Macro Event Prioritization & Triage

**Objective**: Given the macro calendar and current portfolio, classify every upcoming event into Tier 1 (Overriding), Tier 2 (Important), or Tier 3 (Routine). Produce a prioritized watchlist with explicit trigger levels.

**Source**: Meth. §2 (priority tiers, gold-specific prioritization ranking). KB KR-001–KR-083 (strength, expected impact, trigger fields).

**Trigger**: After W3 (Pre-Market Scan). Also triggered on event calendar update or portfolio change.

**Inputs**:
- `ReleaseCalendar` — all scheduled releases (CPI, NFP, GDP, PMI, FOMC, PPI, interest rate decisions)
- Unscheduled event feeds — geopolitical alerts (GPR spikes, sanctions news, war escalations)
- Speech calendar — Fed, ECB, BOJ, PBOC speech schedules
- Current portfolio exposures (from `VirtualPortfolio`): which sectors/assets are most vulnerable
- Current market pricing: what is already discounted (from W3 overnight data)
- Current macro regime (from W2) — determines which event types have highest gold impact
- Gold-specific priority ranking (Meth. §2 ranking 1–9)

**Processing Stages**:
1. **Event inventory** — Merge scheduled calendar + unscheduled alerts + speech calendar into unified event list
2. **Event→portfolio impact mapping** — For each event, compute: "Does this event affect my current positions?" Score 0 (none) to 1 (direct)
3. **Event→regime relevance scoring** — Cross-reference event type against W2 regime indicator hierarchy. Events affecting dominant indicators get higher score
4. **Price impact probability estimation** — Scheduled events: known date + known probability of gold move (from historical beta). Unscheduled: unknown probability, potentially extreme impact
5. **Tier classification** — Apply triplet (portfolio_impact, regime_relevance, price_impact) to classify:
   - Tier 1: portfolio_impact > 0.7 OR regime_relevance > 0.8 OR price_impact > 0.9
   - Tier 2: portfolio_impact > 0.3 OR regime_relevance > 0.5 OR price_impact > 0.5
   - Tier 3: all others
6. **Trigger level assignment** — For Tier 1 and Tier 2 events, assign threshold levels: "If CPI MoM > 0.3%, then reassess gold view. If NFP > 250K, then reduce gold position by 20%."
7. **Watchlist assembly** — Produce ordered watchlist: Tier 1 first (with triggers), Tier 2 second (with triggers), Tier 3 last (check outcome only)

**Existing Capabilities Reused**:
- `EventRegistry` — event type registration
- `ReleaseCalendar` — scheduled release tracking
- W2 output — regime classification and indicator hierarchy
- W3 output — overnight data, position exposure
- W1 output — encoded KRs with trigger and expected_impact fields
- Forecast models — historical beta for price impact estimation

**Missing Capabilities Needed**:
- Event→portfolio impact scorer (exposure overlap analysis)
- Event→regime relevance scorer (indicator hierarchy cross-reference)
- Price impact probability estimator (historical beta lookup from KRs for scheduled events; volatility-based estimate for unscheduled)
- Tier 1/2/3 classification engine
- Trigger level assignment engine (pre-commitment thresholds from KR expected_impact and historical distribution)
- Unscheduled event feed connector (geopolitical alerts, central bank surprises, natural disaster monitoring)
- Black swan classification (extreme impact events with unknown probability)
- Watchlist output format (ordered list with triggers, actions, and monitoring frequency)

**Expected Outputs**:
- Prioritized watchlist: array of (event_type, date, tier, trigger_levels, portfolio_impact_score, regime_relevance_score, monitoring_frequency)
- Trigger level document: "If X prints above Y, then Z action" for each Tier 1/2 event
- Black swan watch: low-probability, high-impact events that don't meet tier threshold but merit monitoring

**Completion Criteria**:
- Watchlist correctly classifies known events (FOMC → Tier 1, routine data → Tier 3) based on current positioning
- Trigger levels match KR expected_impact fields and historical vol distributions
- Unscheduled geopolitical alerts ingested and classified within 15 minutes of publication
- Watchlist consumable by downstream workflows (W6 Evidence Collection, W8 Thesis Formation)
- Wired into orchestrator after W3, before W5
- All existing tests pass

---

### W5: Signal vs Noise Classification

**Objective**: Classify each incoming data point as Signal (act on it), Noise (ignore, monitor), or Ambiguous (set monitoring threshold). Prevent the system from reacting to random volatility.

**Source**: Meth. §7 (5 criteria: persistence, breadth, magnitude vs history, narrative fit, volume/flow). KB KR-001–KR-083 (noise filter thresholds per data type: 1-week COMEX move = noise, 3-week = signal; 1-day ETF flow = noise, 2-week = signal, etc.).

**Trigger**: On every new data point ingested (price change, data release, news headline). Also run as batch after W3 (Pre-Market Scan) for overnight data.

**Inputs**:
- Raw data point: instrument, value, change, timestamp (from W3 overnight data feed)
- Historical distribution of this data point: mean, σ, max, min over configurable windows (1yr, 5yr, full)
- Current macro regime (from W2) — regime-specific thresholds: 1% gold move = noise in normal regime, 3% = signal in stressed regime
- Cross-asset data: correlated instrument moves for breadth check
- Current positions (from `VirtualPortfolio`) — to distinguish "relevant noise" from "irrelevant noise"
- Narrative feed: current consensus story from broker notes/news

**Processing Stages**:
1. **Persistence check** — How long has this deviation persisted? Compare to KR noise filters:
   - COMEX: 1-week = noise, 3-week = signal
   - ETF: 1-day = noise, 2-week = signal
   - CB purchases: 1Q = noise, 8Q rolling avg = signal
   - Gold/real yield: 1-day divergence = noise, 1-month divergence + growing GRAM residual = signal
   - DXY: 0.5% alone = noise, 0.5% + 5bp real yield move = signal
2. **Breadth check** — Is this move confirmed/contradicted by other assets? Cross-reference against W15 (Cross-Asset Confirmation Matrix) if available, else compute basic: gold up + DXY up + real yields up + equities down = confirmed macro move. Gold up + equities flat + real yields flat = idiosyncratic flow
3. **Magnitude vs history** — Compute z-score: (current_move - historical_mean) / σ. |z| > 2 → potential signal. |z| > 3 → strong signal
4. **Narrative fit** — Does the move have a credible narrative explanation? Check against current news themes. Unexplained moves get "Ambiguous" classification
5. **Volume/flow confirmation** — Is the move accompanied by volume spike, open interest change, or ETF flow? (from W3 positioning data)
6. **Classification** — Integrate 5 criteria into single classification with confidence:
   - **Signal**: at least 3 of 5 criteria positive, or 2 positive with persistence confirmed
   - **Noise**: at least 3 of 5 criteria negative, or magnitude < 1σ with no narrative or volume confirmation
   - **Ambiguous**: neither condition met; set explicit monitoring threshold (e.g., "reclassify if persists for X more days")
7. **Signal/Noise log entry** — Record classification, criteria scores, timestamp. The log is reviewed periodically to assess classification accuracy

**Existing Capabilities Reused**:
- `TemporalIndexer`, `TemporalPeriod` — persistence time windows
- `EvidenceWeighter` — recency factor (analogous to persistence decay)
- `NewsSentimentAnalyzer` — narrative extraction from headlines
- W3 output — overnight data with changes and σ
- W2 output — regime-specific thresholds
- W1 output — KR noise filter fields
- `ForecastContext` — news_mood, event summaries

**Missing Capabilities Needed**:
- Persistence tracker: time-series rolling window buffer per instrument, configurable window lengths (5d, 2w, 3w, 1m, 1q, 8q)
- z-score computer: current move vs historical distribution
- Breadth checker: cross-asset confirmation matrix (see W15)
- Narrative fit scorer: does current news explain the move? (bool + confidence)
- Volume/flow confirmator: volume spike detection vs historical average
- Noise/Signal classifier: integrates 5 criteria into single (label, confidence, evidence_ids)
- Signal/Noise log: persistent record with review capability
- Ambiguous monitoring thresholds: configurable reclassification triggers
- Classification accuracy tracker: retrospective comparison of classification vs outcome

**Expected Outputs**:
- Per data point: Classification (Signal/Noise/Ambiguous), confidence (0–1), evidence (which criteria triggered), timestamp
- Signal/Noise log entry: data_point, classification, confidence, criteria_scores, timestamp, reviewed (bool)
- For Signal items: automatic routing to W6 (Evidence Collection) for ingestion into reasoning
- For Ambiguous items: monitoring threshold set; routed to W10 (Thesis Update) with "watch" flag

**Completion Criteria**:
- Gold-specific noise filters from Meth. §7 correctly implemented (COMEX 1w/3w, ETF 1d/2w, CB 1q/8q, gold/real yield 1d/1m, DXY 0.5%/5bp)
- Classification accuracy >80% on retrospective test against 2022–2025 data (known signal vs noise periods)
- Signal/Noise log persistent, queryable by date and instrument
- Ambiguous items automatically routed with monitoring thresholds
- Wired into orchestrator: runs after W3, feeds classified signals to W6
- All existing tests pass

---

### W6: Evidence Collection & Regime-Aware Weighting

**Objective**: Collect evidence matching the current query, then apply regime-dependent weights so that indicators from the wrong regime do not dominate the reasoning.

**Source**: Meth. §3 (re-weight evidence), §5 (signal strength, signal breadth), §9 (regime-specific indicator dominance). KB KR-001–KR-083 (regime_dependence, strength, confidence).

**Trigger**: Invoked by W8 (Thesis Formation) when evidence is needed for a specific event/condition. Also invoked by W10 (Thesis Update) when new information arrives.

**Inputs**:
- Query: (event_type, condition, horizon_days) from W8 or W10
- Current macro regime (from W2): regime label, indicator hierarchy, transition confidence
- All available evidence from KnowledgeGraph (from W1): raw evidence with bias, confidence, sample_count
- Cross-asset data (from W3, W15): current cross-asset correlation matrix
- Narrative consensus (from W5): current market narrative from broker notes/news

**Processing Stages**:
1. **Evidence query** — Query `EvidenceQuery.matching()` by event_type, condition, horizon_days
2. **Cross-asset confirmation filter** — For each evidence item, check if confirmed by cross-asset data. Unconfirmed evidence gets weight penalty
3. **Regime-adaptive weight computation** — Apply `EvidenceWeighter` with regime-aware modifications:
   - Dominant indicators for current regime get weight_multiplier = 1.5
   - Weaker indicators for current regime get weight_multiplier = 0.5
   - Indicators not in current regime's hierarchy get weight_multiplier = 0.25
   - If regime is in transition (confidence < 0.5), compress all multipliers toward 1.0 (hedging against wrong regime)
4. **Variable substitution check** — If current regime is Inflationary (post-2022-style), check whether term premium should substitute for real yields in evidence weighting (KR-004)
5. **Narrative coherence factor** — Compare evidence weight against current market narrative. Evidence that contradicts consensus gets a variant perception bonus (upweight) but with lower confidence
6. **Attribution computation** — WeightedAggregate with regime-aware attribution: which event types contributed what share, adjusted for regime relevance

**Existing Capabilities Reused**:
- `EvidenceQuery.matching()` — evidence retrieval
- `EvidenceWeighter` — 5-factor weighting (confidence, sample, provenance, consistency, recency)
- `WeightConfig` — configurable exponents and baselines
- `WeightedAggregate` — weighted average, effective sample size, attribution
- `EvidenceRanker` — relevance ranking
- `ContextComparisonReport` — baseline vs contextual comparison
- W1 output — KRs with regime_dependence and strength fields
- W2 output — regime classification and indicator hierarchy
- W5 output — signal/noise classified data points

**Missing Capabilities Needed**:
- Regime-aware weight multipliers: maps (regime, indicator) → weight_multiplier
- Transition mode compression: when regime_confidence < threshold, compress all multipliers toward 1.0
- Variable substitution detector: detect when old indicator's explanatory power has been superseded (e.g., real yields → term premium)
- Narrative coherence weight adjustment: consensus-agreement bonus, variant-perception bonus
- Cross-asset confirmation penalty/bonus per evidence item
- Attribution with regime breakdown: contribution by event_type × regime_relevance

**Expected Outputs**:
- `WeightedAggregate` with regime-adjusted weights
- Attribution: (event_type, raw_weight, regime_adjusted_weight, regime_relevance, dominant_in_current_regime: bool)
- Variable substitution flag: "In current regime, indicator X's weight reduced; indicator Y substituted"
- Narrative coherence score: (narrative_consensus, evidence_alignment, variant_detected: bool)

**Completion Criteria**:
- Regime-aware weights: in Normal Growth regime, real yields weighted x1.5, term premium weighted x0.25
- In Inflationary regime, term premium weighted x1.5, real yields weighted x0.5
- Transition mode: when regime_confidence < 0.4, all multipliers within 0.75–1.25 range
- Variable substitution: real yield weight reduced when term premium data available and regime is Inflationary
- Attribution correctly shows regime-adjusted contribution
- Wired into orchestrator: invoked by W8, consumes W2 + W5 outputs
- All existing tests pass

---

### W7: Conflicting Evidence Resolution

**Objective**: When evidence points in conflicting directions, resolve by returning to causal first principles. Produce a written rationale for which evidence was prioritized and why.

**Source**: Meth. §3 (return to first principles, cross-asset confirmation, temporal stability, 4 resolution actions: re-weight/defer/edge-hedge/flip).

**Trigger**: Invoked by W8 (Thesis Formation) when `WeightedAggregate` shows conflicting evidence (both positive and negative biases from same event type, or high attribution spread across opposing directions).

**Inputs**:
- `WeightedAggregate` from W6 with conflicting evidence identified
- CausalGraph (from W1): causal relationships, competing hypotheses
- Current regime (from W2): regime label, transition confidence
- Cross-asset correlations (from W15 if available, else from W3 overnight data)
- Historical analogue data: when has this conflict occurred before and how was it resolved?
- Narrative consensus (from W5): what does the market currently believe?

**Processing Stages**:
1. **First principles check** — For each conflicting evidence pair, return to causal mechanism. Ask: "Is there a regime-dependent explanation for this conflict?" Example: gold up + real yields up → check if we are in Inflationary regime where term premium dominates (KR-004). If yes, the conflict is resolved by variable substitution
2. **Cross-asset confirmation** — For each side of the conflict, count confirming cross-asset signals. The side with more cross-asset confirmation gets higher weight
3. **Temporal stability check** — Search CausalGraph for this specific conflict pattern in historical data. Has it occurred before? How was it resolved? Use KR counter_examples and historical_evidence fields
4. **Narrative/variant comparison** — Compare each side against current market narrative. Is one side consensus and one side variant? (Goldman Sachs variant view). Variant views that are well-supported get an upweight
5. **Resolution action selection** — Choose from Meth. §3 four actions:
   - **Re-weight**: evidence sides clearly ranked by mechanism strength + confirmation
   - **Defer**: conflict cannot be resolved without more data; set monitoring threshold
   - **Edge hedge**: one side has stronger mechanism but both have evidence; recommend risk overlay
   - **Flip**: conflicting evidence overwhelming; reverse prior thesis
6. **Rationale generation** — Produce structured rationale: which evidence was prioritized, which was down-weighted, which resolution action chosen, and why

**Existing Capabilities Reused**:
- `ReasoningEngine._add_comparison_steps()` — cross-condition comparison within event type
- `CausalGraph.competing_hypotheses()` — competing causal explanations
- `CausalGraph.evaluate_hypothesis()` — supporting vs contradicting evidence
- `ContextComparisonReport` — baseline vs contextual comparison
- `EvidenceWeighter` — consistency factor (majority bias alignment)
- W1 output — CausalGraph with mechanism descriptions
- W6 output — WeightedAggregate with attribution
- W2 output — regime classification
- W5 output — narrative consensus

**Missing Capabilities Needed**:
- First principles conflict resolver: for each conflicting pair, trace to causal mechanism in CausalGraph; check regime-dependent causal relationships
- Cross-asset confirmation counter: for each evidence direction, count confirming signals across unrelated markets
- Historical conflict pattern matcher: search CausalGraph/KR database for similar conflict patterns; retrieve resolution and outcome
- Variant view detector: compare evidence-supported direction against current consensus narrative; flag divergence
- Resolution action selector: rule-based system mapping conflict characteristics to Meth. §3 actions
- Conflict rationale generator: structured output documenting resolution process

**Expected Outputs**:
- Resolution action: one of (re-weight, defer, edge_hedge, flip)
- Conflict analysis: (conflicting_evidence_a, conflicting_evidence_b, mechanism_check, cross_asset_a_count, cross_asset_b_count, temporal_pattern_match, narrative_consensus, variant_flag)
- Rationale: structured document with prioritization reasoning
- If defer: monitoring threshold (what new data would resolve the conflict)
- If edge_hedge: hedging recommendation (e.g., "long gold, buy puts to protect against real yield risk")
- Updated confidence: lower than either side individually (Meth. §3: medium for established conflicts, low for regime-change conflicts)

**Completion Criteria**:
- Known conflict pattern (2022: gold up + real yields up) resolved via variable substitution (term premium → KR-004)
- Cross-asset confirmation correctly counts confirming signals
- Temporal stability correctly identifies repeated vs novel conflict patterns
- Resolution action matches expert assessment on 5+ historical test cases
- Rationale output is audit-ready: machine-readable + human-readable
- Wired into orchestrator: invoked by W8 when conflict detected in W6 output
- All existing tests pass

---

### W8: Investment Thesis Formation

**Objective**: Produce a complete, actionable investment thesis for gold (direction, magnitude, horizon, assumptions, risks, sizing, triggers) following the Goldman Sachs 5-layer chain.

**Source**: Meth. §4 (5-layer chain: narrative → fundamental → valuation → fragility → conclusion). Goldman Sachs thesis structure (narrative, variant view, valuation derivation, target price, upside/downside, thesis risks, evidence references). Output format with all 7 required fields.

**Trigger**: On demand (user query), or when W5 classifies an incoming signal as significant enough to warrant a new thesis.

**Inputs**:
- Market narrative (from W5): current consensus story about gold
- Evidence and regime-adjusted weights (from W6): quantitative evidence base
- Conflicting evidence resolution (from W7, if applicable): how evidence conflicts were resolved
- Current regime and indicator hierarchy (from W2): macro context
- Portfolio constraints (from `VirtualPortfolio`): position limits, VaR budget, liquidity
- Historical analogues (from W1 KRs): similar macro configurations
- User query (if on-demand): event_type, condition, horizon

**Processing Stages**:
The Goldman Sachs 5-layer thesis chain:
1. **Market narrative** — What does the market currently believe? Extract consensus direction and conviction from news sentiment, broker consensus (from W5). Document the consensus view explicitly
2. **Fundamental structure** — What do the gold-specific flow data show? Central bank buying → ETF flows → COMEX positioning → supply/demand balance. Cross-reference W6 evidence for gold-specific indicators
3. **Valuation and drivers** — Given current macro configuration (W2 regime), what is the implied gold direction and magnitude? Use regime-adjusted WeightedAggregate from W6. Compute expected return and confidence
4. **Fragility audit** — What could break this thesis? (Invokes W12). Identify 3–5 key assumptions and their failure conditions. Document the downside scenario that would invalidate every assumption
5. **Conclusion** — Direction (long/short/neutral), magnitude (target return over horizon), position sizing (via W9 confidence), key assumptions, key risks, triggers for exit

Each stage documented as a `ReasoningStep` with:
- Step_type: NARRATIVE, FUNDAMENTAL, VALUATION, FRAGILITY, CONCLUSION
- Input evidence references
- Confidence level per step
- Output conclusion

**Existing Capabilities Reused**:
- `ReasoningEngine.reason()` — step-by-step reasoning chain (to be extended with new step types)
- `ReasoningChain` — chain with overall_confidence, attribution
- `ReasoningStep` — typed steps (extend with NARRATIVE, FRAGILITY step types)
- `DecisionEngine.decide()` — final decision classification
- `Decision` — decision output with decision_type, confidence
- W6 output — regime-adjusted WeightedAggregate
- W7 output — conflict resolution rationale (if conflicts existed)
- W2 output — regime classification
- W5 output — narrative consensus
- W1 output — KR failure_conditions for fragility audit
- `CausalGraph.competing_hypotheses()` — alternative causal explanations

**Missing Capabilities Needed**:
- `NARRATIVE` step type in ReasoningStep (new)
- `FRAGILITY` step type in ReasoningStep (new)
- Market narrative extraction module (from W5 consensus data)
- Fundamental structure analysis (CB buying + ETF flows + COMEX positioning → supply/demand assessment)
- Valuation/driver computation (regime-adjusted WeightedAggregate → expected return, regime-appropriate indicator weight)
- Fragility audit integration (calls W12; returns 3–5 key assumptions + failure conditions)
- Thesis output formatter: structured output with all 7 fields (direction, magnitude, horizon, assumptions, risks, sizing, triggers)
- Thesis version identifier (for W10 thesis update traceability)

**Expected Outputs**:
- Complete thesis: (direction, target_return, horizon, confidence, key_assumptions[\], key_risks[\], failure_conditions[\], position_sizing, exit_triggers[\], evidence_references)
- ReasoningChain with 5 Goldman Sachs step types (NARRATIVE, FUNDAMENTAL, VALUATION, FRAGILITY, CONCLUSION)
- Variant view document: (consensus_view, our_view, disagreement_evidence[\], disagreement_rationale)
- Fragility audit summary: (assumption, failure_condition, trigger_level, consequence)
- Thesis version ID for future update tracking

**Completion Criteria**:
- Thesis contains all 7 required output fields from Meth. §4
- ReasoningChain includes all 5 Goldman Sachs step types
- Variant view explicitly stated when evidence contradicts consensus narrative
- Fragility audit identifies 3+ testable failure conditions per thesis
- Thesis consumable by W10 (Thesis Update) with version ID
- DecisionEngine output integrated (STRONG_POSITIVE → POSITIVE → NEUTRAL → NEGATIVE → STRONG_NEGATIVE) with confidence
- All existing tests pass, 18 benchmarks pass

---

### W9: Confidence Assignment & OOS Calibration

**Objective**: Assign a conviction level (Investment-Grade → Speculative) to every thesis, calibrated by out-of-sample track record and meta-evidence (model R², prediction consistency, cross-method convergence).

**Source**: Meth. §5 (confidence spectrum, meta-evidence, OOS performance, model stability, consensus position, regime clarity). Goldman Sachs 3-question test. Bridgewater holy grail.

**Trigger**: After W8 thesis conclusion formed. Before position sizing or output.

**Inputs**:
- Thesis evidence from W6: weighted aggregate return, confidence, effective sample size
- Model performance data: R² from historical regressions, OOS ECE from `ChronologicalOOSEngine`
- Prediction consistency: agreement across windows (from W16 Multi-Window Aggregation)
- Cross-method convergence: do fundamental, quantitative, and narrative approaches agree?
- Consensus position (from W5): is the thesis contrarian, consensus, or near-agreement?
- Regime clarity (from W2): regime transition confidence
- Goldman Sachs 3 answers: downside case, why not priced in, what breaks view

**Processing Stages**:
1. **Meta-evidence collection** — Gather all inputs: model R², OOS ECE, window consistency, cross-method agreement, consensus position, regime clarity
2. **Goldman Sachs 3-question test** — Answer programmatically:
   - "What is the downside case?" → From W12 fragility audit
   - "Why hasn't the market already priced this in?" → Compare evidence dates to price reaction dates
   - "What breaks your view?" → From W12 failure conditions
   - If any answer is "unknown", confidence capped at Medium
3. **Confidence spectrum assignment** — Map meta-evidence to Meth. §5 spectrum:
   - **Investment-Grade** (5+ independent signals, R² > 80%, OOS ECE < 0.1, cross-method agreement, contrarian)
   - **High** (2+ independent signals, R² > 60%, OOS ECE < 0.15, moderate consensus)
   - **Medium** (1 primary signal, known regime, thesis testable)
   - **Low** (conflicting signals, regime in transition, unknown dependence)
   - **Speculative** (exploratory, lacks evidentiary support)
4. **Position sizing mapping** — Convert confidence to Meth. §5 sizing + entry technique:
   - Low → 0.5–1% portfolio, limit orders, scaling in, tight stops, buy puts
   - Medium → 1–3%, normal entry, standard stops
   - High → 3–5%, market orders, full position, wider stops
   - Investment-Grade → 5%+, full allocation (rare)
5. **Confidence calibration adjustment** — Use OOS ECE to adjust confidence: if OOS calibration shows ECE > 0.15, cap confidence at Medium. If ECE > 0.25, cap at Low

**Existing Capabilities Reused**:
- `ForecastConfidenceComputer` — spread_score, agreement_score, context_coherence
- `ChronologicalOOSEngine` — OOS ECE, directional accuracy, precision, recall
- `ExperimentRegistry` — track record of past thesis outcomes
- `ForecastProvenance` — model version tracking
- W2 output — regime clarity/confidence
- W6 output — evidence strength and breadth
- W8 output — thesis with evidence references
- W12 output — downside case and failure conditions

**Missing Capabilities Needed**:
- Meta-evidence aggregator: collect R², OOS ECE, window consistency, cross-method agreement into single structure
- Goldman Sachs 3-question engine: programmatic downcase, pricing-in, breaking-view assessment
- Confidence spectrum classifier: map meta-evidence to 5-level spectrum with explicit criteria
- Confidence→position sizing: mapping table (Meth. §5 exact specifications)
- OOS calibration cap: confidence ceiling based on ECE
- Entry technique recommender: limit/market order, scaling strategy based on confidence
- Confidence change trigger document: "Conviction would change if [event] occurs"

**Expected Outputs**:
- Confidence level: one of (investment_grade, high, medium, low, speculative) with numerical 0–1 confidence
- Meta-evidence summary: (model_r2, oos_ece, window_consistency, cross_method_agreement, consensus_position, regime_clarity)
- Goldman Sachs 3-answers: (downside_case, why_not_priced_in, what_breaks_view, all_answered: bool)
- Position sizing recommendation: (size_pct, entry_technique, stop_width, hedge_recommendation)
- OOS calibration cap applied (if ECE > 0.15, confidence capped at Medium)
- Change triggers: "Confidence would increase if [data print], decrease if [event]"

**Completion Criteria**:
- Confidence level matches expert assessment on 10+ historical thesis test cases
- Goldman Sachs 3-question test correctly caps confidence when questions unanswered
- OOS calibration correctly caps confidence when ECE exceeds threshold
- Position sizing matches Meth. §5 specifications (low = 0.5–1%, high = 3–5%)
- Entry technique recommended correctly per confidence level
- Wired into orchestrator: after W8, before output
- All existing tests pass

---

### W10: Thesis Update Cycle

**Objective**: When new information arrives, update an existing thesis following the Bridgewater 4-step template: identify changed input → map impact → quantify delta → decide (no change/scale/hedge/pause/exit).

**Source**: Meth. §6 (thesis update: identify → map → quantify → decide). Bridgewater living set of conditional bets. Goldman Sachs full restructure requirement. J.P. Morgan quarterly cycle with ad-hoc revisions.

**Trigger**: New information arrives via W3 (daily scan) or W5 (signal classification). If a thesis exists for the affected event/condition, the update cycle fires.

**Inputs**:
- Existing thesis (from W8): full thesis document with version ID, assumptions, triggers
- New information (from W3, W5): overnight data, data release, headline, signal classification
- Current regime (from W2): may have shifted since thesis was formed
- Current portfolio P&L on the position (from `VirtualPortfolio`) — to manage realization bias
- Evidence re-run (from W6): updated WeightedAggregate with new information included

**Processing Stages**:
Bridgewater 4-step template:
1. **Identify changed input** — Compare new information against thesis assumptions. Which specific assumption changed? Is the change:
   - Cumulative evidence (series of small changes)
   - Threshold-crossing evidence (single data point exceeds pre-specified trigger)
   - Regime-break evidence (structural macro regime change)
2. **Map the impact** — Does the change affect one assumption or multiple? Cascade analysis: if inflation assumption changes, does it affect real yield assumption, which affects gold return assumption?
3. **Quantify the delta** — Re-run W6 with new evidence included. Compare new WeightedAggregate to thesis original. Compute: Δ_return = new_return - thesis_return. Compute: Δ_confidence = new_confidence - thesis_confidence
4. **Decide** — Choose Meth. §6 action:
   - **No change**: Δ_return within confidence bands of original thesis
   - **Scale**: Δ_return significant but thesis structure intact; adjust position size (re-invoke W9)
   - **Hedge**: Δ_confidence dropped significantly but direction unchanged; recommend risk overlay
   - **Pause**: Δ is significant and direction uncertain; exit temporarily
   - **Exit**: Δ invalidates core thesis; close position, invoke W14 (Post-Mortem)

If the update is routine (J.P. Morgan quarterly cycle), the thesis is fully restructured (Goldman Sachs requirement: must recertify all 5 layers, not just update the price target).

**Existing Capabilities Reused**:
- `ReasoningEngine` — re-run reasoning with new evidence
- `DecisionEngine` — re-evaluate decision
- `DecisionGate` — risk gate evaluation for scale/hedge/pause/exit
- `ForecastKnowledge.forecast()` — re-run forecast with updated training data
- `EvidenceQuery.matching()` — re-query evidence with updated parameters
- W2 output — regime update
- W3 output — new information
- W5 output — signal classification
- W6 output — updated evidence and weighting
- W8 output — existing thesis with version ID
- W12 output — updated fragility audit if assumptions changed

**Missing Capabilities Needed**:
- Thesis version store: persistent storage for thesis versions with full history
- Changed input identifier: for each new data point, which thesis assumption is affected?
- Cascade impact mapper: when one assumption changes, which other assumptions are affected?
- Delta quantifier: Δ_return, Δ_confidence, Δ_assumption_values between thesis_version_N and thesis_version_N+1
- Update action selector: rule-based system mapping (change_type, delta_magnitude, delta_direction) to Meth. §6 actions
- Ad-hoc update trigger: when threshold-crossing or regime-break evidence detected, fire non-cyclical update
- Quarterly cycle scheduler: formal update every 90 days even without new information
- Thesis update note generator: structured output documenting what changed, which assumptions affected, new confidence level, new watchlist

**Expected Outputs**:
- Updated thesis document: same structure as W8 output, with new version ID, new evidence, new confidence
- Update note: (thesis_version, date, trigger_event, changed_assumptions[\], cascade_affected_assumptions[\], Δ_return, Δ_confidence, action, new_confidence, new_watchlist)
- Updated position sizing recommendation (if scale action)
- Hedge recommendation (if hedge action)
- Post-mortem trigger (if exit action, invokes W14)

**Completion Criteria**:
- Cumulative evidence (small CPI misses over 3 months) → triggers a Scale or Hedge decision
- Threshold-crossing evidence (CPI MoM exceeds 0.3% trigger) → triggers full reassessment
- Regime-break evidence (R² drops from 85% to 16% like 2022) → triggers Exit + Post-Mortem
- Quarterly cycle: thesis restructured every 90 days even without material new information
- All actions (scale/hedge/pause/exit) correctly chosen on test scenarios
- Thesis history: full version chain preserved for audit
- Wired into orchestrator: triggered by W3 daily scan or W5 signal classification
- All existing tests pass

---

### W11: Causal Relationship Evaluation & Graph Maintenance

**Objective**: For each observed or hypothesized causal relationship involving gold, classify as Causal-Stable, Causal-Regime-Dependent, Correlational-Non-Causal, or Spurious. Maintain the gold causal map (DAG).

**Source**: Meth. §8 (5 criteria: mechanism clarity, directional stability, regime invariance, exogeneity, replication). KB KR-001–KR-083 (mechanism, direction, regime_dependence, counter_examples).

**Trigger**: Initial: encode all KB causal relationships into CausalGraph. Ongoing: when new evidence contradicts or supports an existing causal relationship, re-evaluate.

**Inputs**:
- CausalGraph (from W1): nodes, edges, mechanisms
- KR causal data: mechanism, direction, strength, confidence, regime_dependence, counter_examples (from all KB categories)
- Historical time series: gold, real yields, DXY, CPI, CB reserves, ETF flows, COMEX, VIX, GPR
- Natural experiment periods: 2022 (real yield breakdown), 2008 (CB buying regime shift)
- Academic/industry research: IMF WP/23/008, J.P. Morgan gold research, WGC GRAM

**Processing Stages**:
1. **Causal mechanism verification** — For each edge in CausalGraph, verify mechanism clarity: is the causal chain explicable? Gold has no yield → real yields matter → opportunity cost → demand. If mechanism is unclear, flag for review
2. **Directional stability test** — Run Granger causality test on historical data: does A consistently cause B? Check directionality across multiple subsamples. If direction flips, classify as regime-dependent
3. **Regime invariance test** — Test whether the causal relationship holds across different macro regimes. Split historical data by regime (from W2 retrospective classification). If coefficient changes sign or becomes insignificant in some regimes, classify as regime-dependent
4. **Exogeneity check** — Is the causal variable determined outside the gold market? Real yields → gold: real yields are primarily driven by Fed policy, not gold (exogenous). Gold → ETF flows: partly endogenous (price → flows). Flag as potentially endogenous
5. **Replication check** — Have multiple independent researchers found the same relationship? Cross-reference KR references against known research (IMF, WGC, JPM, GS). If only one source, confidence capped
6. **Classification** — From 5 criteria, classify each relationship:
   - **Causal-Stable**: all 5 criteria positive
   - **Causal-Regime-Dependent**: mechanism + direction positive; regime invariance fails
   - **Correlational-Non-Causal**: no mechanism or endogeneity or direction ambiguous
   - **Spurious**: out-of-sample failure, no mechanism, or reverse causality
7. **Graph update** — Update CausalGraph edge properties: classification, confidence, regime_mask (which regimes the relationship is active in), last_tested_date

**Existing Capabilities Reused**:
- `CausalGraph` — directed graph of causal relationships
- `CausalRelation` — source, target, mechanism, direction, strength, confidence
- `CausalHypothesis` — testable cause→effect hypothesis
- `CausalEvidence` — supporting/contradicting evidence per hypothesis
- `CausalGraph.evaluate_hypothesis()` — supporting vs contradicting balance
- `CausalGraph.competing_hypotheses()` — alternative causal explanations
- W1 output — KRs with mechanism, direction, regime_dependence, counter_examples, references
- W2 output — retrospective regime classification for regime invariance test

**Missing Capabilities Needed**:
- Causal mechanism clarity scorer: structured check of mechanism field completeness (cause → mechanism → effect chain)
- Granger causality tester (or equivalent): directional stability across subsamples
- Regime invariance tester: fit relationship model per regime; test coefficient stability across regimes
- Exogeneity checker: structural knowledge of whether cause is external to gold market
- Replication counter: count of independent sources supporting each relationship
- Causal classifier: integrates 5 criteria into 4-level classification
- Causal graph update protocol: when classification changes, propagate to dependent edges
- Causal confidence decay: relationships not tested in >1 year have reduced confidence

**Expected Outputs**:
- Per causal edge: classification (Causal-Stable / Causal-Regime-Dependent / Correlational / Spurious), confidence, evidence_ids
- Regime mask per edge: which of the 6 regimes the relationship is active in
- Competing hypotheses: for each cause→effect pair, list alternative explanations with their classifications
- Graph update log: (edge_id, previous_classification, new_classification, trigger, date)
- Knowledge gaps: causal relationships with insufficient data to classify

**Completion Criteria**:
- Real yields → gold correctly classified as Causal-Stable (pre-2022) and Causal-Regime-Dependent (post-2022 regime mask: active in Normal Growth, inactive in Inflationary)
- DXY → gold correctly classified as Causal-Stable
- Gold ↔ silver correctly classified as Correlational-Non-Causal
- Term premium → gold correctly classified as Causal-Regime-Dependent (active in Inflationary, inactive in Normal Growth)
- IMF sanctions → CB gold buying correctly classified as Causal-Stable (exogenous + replicated)
- All 207+ KR relationship edges classified
- Wired into orchestrator: runs weekly or when new research indicates relationship change
- All existing tests pass

---

### W12: Fragility Audit & Scenario Analysis

**Objective**: For any thesis, identify 3–5 key assumptions, determine what would break each one, and run scenario analysis: base case (most likely), bear case (assumptions fail), bull case (upside surprise).

**Source**: Meth. §4 (Goldman Sachs fragility audit step), §10 (overconfidence prevention, base rate neglect, false precision remedies). J.P. Morgan multi-scenario forecasting, BlackRock CMA stochastic simulation.

**Trigger**: Called by W8 (Thesis Formation) Stage 4 and W10 (Thesis Update) when assumptions change.

**Inputs**:
- Thesis assumptions (from W8): 3–5 key assumptions that must hold
- KR failure_conditions (from W1): for each assumption, what would invalidate it
- Base rates (from Meth. §10): historical probability of similar assumptions failing
- Historical analogues (from W1 KRs): past periods where similar macro configurations broke
- Current regime (from W2): most likely regime + alternative regime scenarios
- Evidence distribution (from W6): not just weighted average, but full distribution of evidence outcomes

**Processing Stages**:
1. **Assumption extraction** — Parse thesis for 3–5 key assumptions. For each, identify: what is the assumption, what evidence supports it, what KR failure_conditions apply
2. **Failure condition enumeration** — For each assumption, list specific trigger levels: "Assumption: real yields stay below 2%. Failure condition: 10Y TIPS yield exceeds 2.5%."
3. **Base rate lookup** — For each failure condition, look up historical base rate: "Since 2000, real yields have crossed 2.5% 40% of the time in a 12-month window."
4. **Scenario construction** — Build 3 scenarios:
   - **Base case**: all assumptions hold; thesis expected return realized
   - **Bear case**: most likely assumption failure occurs; quantify worst-case return
   - **Bull case**: upside surprise on assumptions; quantify best-case return
5. **Probability weighting** — Assign probabilities to each scenario based on base rates and current regime confidence
6. **Fragility score** — Compute how fragile the thesis is: (bear_case_return / base_case_return). Higher ratio = more fragile. If >2.0, flag as too fragile to act on

**Existing Capabilities Reused**:
- W1 output — KR failure_conditions, trigger fields, historical_evidence
- W2 output — regime classification (base case regime, plus alternative regimes)
- W6 output — evidence distribution (not just weighted average)
- W8 output — thesis with assumptions
- KRs with "Counter Examples" field — historical cases of assumption failure
- `ForecastKnowledge.forecast()` — re-run forecast under alternative scenarios

**Missing Capabilities Needed**:
- Assumption extractor: parse thesis for 3–5 key assumptions with supporting evidence references
- Failure condition enumerator: per assumption, generate specific measurable failure thresholds
- Base rate lookup: historical frequency of each failure condition occurring
- Scenario construction engine: base/bear/bull case return computation
- Probability weight assigner: scenario probabilities from base rates + regime confidence
- Fragility score computer: bear/base return ratio with fragility threshold
- Scenario report generator: structured output of all 3 scenarios with evidence

**Expected Outputs**:
- Thesis key assumptions: (assumption, evidence_ids, failure_condition, trigger_level, base_rate)
- 3 scenarios: (base: return, confidence, probability; bear: return, confidence, probability, specific_failure; bull: return, confidence, probability, specific_upside)
- Fragility score: bear_return / base_return ratio; flag if >2.0
- Base rate references: "since 1975, gold has experienced 91 drawdowns of >10%"
- Scenario distribution: not a point estimate but a probability distribution

**Completion Criteria**:
- Fragility audit produces 3+ testable failure conditions for any thesis
- Failure conditions have specific trigger levels, not vague statements
- Bear case has lower bound (worst plausible outcome)
- Bull case has upper bound (best plausible outcome)
- Base rates referenced from KR historical_evidence or external data
- Fragility score correctly flags thesis as too fragile when bear/base >2.0
- Output consumable by W9 (Confidence Assignment) for downside case input
- All existing tests pass

---

### W13: Bias Prevention & Decision Review

**Objective**: Before any decision is finalized, run it through the 10 reasoning mistakes checklist. Flag any that apply and require remediation before the decision can proceed.

**Source**: Meth. §10 (10 reasoning mistakes with institutional remedies). Goldman Sachs variant view, Bridgewater radical transparency, BlackRock MATT cross-check.

**Trigger**: Before any thesis is finalized (after W8) and before any update is committed (after W10).

**Inputs**:
- Thesis (from W8) or thesis update (from W10): complete decision document
- Evidence (from W6): full evidence set, not just summary
- Variant view if applicable (from W7, W8)
- Consensus narrative (from W5)
- Historical analogues (from W1 KRs)
- Past decisions (from W14 Decision Journal if available)

**Processing Stages**:
Check each of 10 mistakes:
1. **Confirmation bias** — Thesis includes a "what would disprove this" statement? If not, require one. Flag if all cited evidence supports the view.
2. **Anchoring** — Pre-commitment triggers exist for exit? (From W8 output). If triggers are missing or vague, flag as anchoring risk.
3. **Overconfidence from narrative coherence** — Is the thesis's conviction higher than the evidence justifies? Cross-check: is the narrative supported by verifiable evidence or is it a compelling story? Flag if conviction > 0.7 but evidence strength < 0.5.
4. **Recency bias** — Multi-window evidence being used? If only short-term windows inform the thesis, flag for recency bias. Require W16 multi-window check.
5. **Base rate neglect** — Are historical base rates explicitly referenced in the thesis? If thesis claims "this time is different," require explicit comparison to historical analogues.
6. **Attribution error** — Is there a decision journal entry for earlier theses on the same question? If a previous similar thesis produced a good outcome from a bad process (or vice versa), flag.
7. **Groupthink** — Is the thesis contrarian to consensus? If the thesis agrees with consensus AND has no variant view, flag for potential groupthink.
8. **Narrative trap** — For every causal claim, verify mechanism + direction + empirical support. If the claim lacks any of the three, flag.
9. **False precision** — Are all outputs presented as ranges with confidence intervals? If point estimates without ranges, flag.
10. **"This time is different"** — If thesis argues current situation has no historical precedent, require explicit comparison to past analogues AND independent evidence. Burden of proof on discontinuity claim.

For each flag: require remediation (add missing documentation, adjust confidence, add missing evidence) before decision can proceed.

**Existing Capabilities Reused**:
- W5 output — consensus narrative
- W8 output — thesis with evidence, assumptions, triggers
- W9 output — confidence assignment
- W12 output — fragility audit, base rates
- W14 output (if exists) — decision journal entries for attribution error check
- W1 output — KR historical_evidence for base rates

**Missing Capabilities Needed**:
- 10-mistake checklist engine: rule-based checker for each mistake
- Confirmation bias checker: does thesis include disconfirming evidence?
- Anchoring checker: are exit/update pre-commitments specified?
- Narrative coherence checker: conviction > evidence_strength → flag
- Recency bias checker: are multi-window estimates available?
- Base rate neglect checker: are historical frequencies referenced?
- Attribution error checker: is there a decision journal entry for the same question?
- Groupthink checker: consensus agreement without variant view → flag
- Narrative trap checker: causal claims with mechanism + direction + support?
- False precision checker: point estimates without ranges → flag
- "This time is different" checker: historical analogue comparison required
- Bias prevention report: (pass/fail per mistake, flags[\], required_remediations[\], remediated: bool)

**Expected Outputs**:
- Bias prevention checklist: array of (mistake, pass/fail, evidence, remediation_required, remediation_applied)
- Flags: list of potential biases identified with specific evidence
- Required remediations: actions the system must take before decision can proceed
- Final bias-prevention sign-off: all 10 checks passed (or remediated)

**Completion Criteria**:
- 10-mistake checklist correctly flags known bias cases on test scenarios
- Confirmation bias: thesis with all-supporting-evidence and no disconfirming evidence → flagged
- Anchoring: thesis without trigger levels → flagged
- Narrative coherence: conviction=0.8, evidence_strength=0.3 → flagged
- Recency bias: only short-window evidence → flagged; prompts W16
- False precision: point estimate without range → flagged
- "This time is different": no historical analogue comparison → flagged
- All flags require remediation; system cannot proceed without remediation
- Wired into orchestrator: gate before decision finalization (after W8, after W10)
- All existing tests pass

---

### W14: Decision Journal & Post-Mortem

**Objective**: Record every thesis and trade decision with full rationale, expected probabilities, and exit triggers. Periodically review the journal to separate outcome quality from decision quality (attribution error remedy).

**Source**: Meth. §10 (Mistake 6: Attribution Error — decision journal). Bridgewater radical transparency, Goldman Sachs research discipline. Meth. §6 (post-mortem on thesis exit).

**Trigger**: Every decision output (from W8 Thesis Formation, W10 Thesis Update). Exit decisions (W10) automatically trigger a post-mortem.

**Inputs**:
- Thesis/decision document (from W8 or W10): rationale, confidence, assumptions, triggers
- Outcome data: later, when the trade/thesis outcome is known (from `VirtualPortfolio` P&L)
- Update history: chain of thesis versions showing what changed and why

**Processing Stages**:
1. **Decision recording** — On every decision output, record full decision document to journal:
   - Decision ID, timestamp, event_type, condition
   - Thesis document (direction, magnitude, horizon, confidence, assumptions, risks, triggers)
   - Evidence references (which KRs, which evidence IDs)
   - Confidence level and methodology version
2. **Outcome matching** — When position/thesis outcome is known (closed, reached horizon, or invalidated), match journal entry to outcome:
   - Actual return vs expected return
   - Did exit triggers fire? If so, were they accurate?
   - Did failure conditions materialize? Were they anticipated?
3. **Decision quality review** — Separately from outcome, assess decision quality:
   - Was the reasoning sound given information available at the time?
   - Were evidence sources appropriate?
   - Were multiple hypotheses considered?
   - Were failure conditions explicitly identified?
4. **Attribution analysis** — Classify as one of four quadrants:
   - Good decision + Good outcome = process works
   - Good decision + Bad outcome = risk materialized (study for risk management)
   - Bad decision + Good outcome = lucky (study for process improvement)
   - Bad decision + Bad outcome = process failure (requires process change)
5. **Post-mortem (on thesis exit)** — When W10 triggers an exit, produce post-mortem:
   - What was the thesis?
   - What changed?
   - Was the change anticipated?
   - Did exit triggers fire correctly?
   - What can be learned for future theses?
6. **Periodic journal review** — Quarterly, review all entries. Look for patterns: repeated same mistake, systematic overconfidence, systematic underconfidence

**Existing Capabilities Reused**:
- `LearningEngine`, `LearningSession`, `LearningFeedback`, `LearningRecord` — learning infrastructure
- `Decision` — decision output with decision_type, confidence, evidence_count
- `DecisionEngine.decide()` — decision formation
- `VirtualPortfolio` — position P&L tracking for outcome data
- W8 output — thesis document
- W10 output — thesis update note, exit trigger
- `ExperimentRegistry` — experiment tracking (analogous framework)

**Missing Capabilities Needed**:
- Decision journal datastore: persistent, append-only, queryable by date/event_type/outcome/decision_quality
- Outcome matcher: link decision journal entry to eventual outcome (return, trigger_fired, failure_materialized)
- Decision quality assessor: evaluate decision quality independent of outcome (reuse W13 bias prevention output)
- Attribution quadrant classifier: good/bad decision × good/bad outcome
- Post-mortem generator: structured template for thesis exits
- Journal reviewer: pattern detection (e.g., "3 of last 5 theses failed due to same unanticipated failure condition")
- Process improvement suggestion: when pattern detected, suggest process change
- Journal review scheduler: quarterly automated review

**Expected Outputs**:
- Per decision: (decision_id, timestamp, event_type, thesis_snapshot, evidence_references, confidence, expected_return, expected_horizon)
- Per outcome: (decision_id, actual_return, horizon_achieved, triggers_fired[\], failure_materialized[\])
- Attribution quadrant: (decision_id, outcome_quality: good/bad, decision_quality: good/bad, quadrant: 4-class)
- Post-mortem (for exits): (thesis_id, trigger_event, anticipated_risk: bool, lesson, process_change_suggestion)
- Quarterly review: (period, entries_reviewed, patterns[\], recommended_process_changes[\], confidence_calibration_trend)

**Completion Criteria**:
- Every decision recorded in journal automatically on output
- Decision quality assessed independently from outcome
- Attribution quadrant correctly classifies test cases (e.g., profitable trade based on faulty reasoning = Bad Decision + Good Outcome)
- Post-mortem generated on every thesis exit
- Journal queryable by date, event type, outcome, quadrant
- Quarterly review identifies patterns with actionable suggestions
- All existing tests pass

---

### W15: Cross-Asset Confirmation Matrix

**Objective**: For any gold price move, produce a matrix of confirming/disconfirming signals across related assets (DXY, real yields, equities, commodities, rates). Used by W5 (Noise/Signal) and W7 (Conflict Resolution).

**Source**: Meth. §7 (cross-asset confirmation: gold down + silver down + miners down + DXY up = signal; gold down alone = noise). Meth. §8 (causal vs spurious: correlated assets vs independently driven). KB KR-008 (real yields + DXY co-determination), KR-011 (diversification correlation), KR-029 (gold + USD simultaneous rally), KR-055–KR-057 (cross-asset ratios).

**Trigger**: On every significant gold price move (>0.5%). On demand for evidence classification (W5, W7). Batch mode after W3 pre-market scan.

**Inputs**:
- Gold price: XAU/USD spot change
- Related asset changes: DXY, US10Y real yield, US10Y nominal yield, BEI, S&P 500, Brent crude, silver, gold miners index (GDX), EUR/USD, USD/JPY, VIX
- Current regime (from W2): determines which cross-asset relationships are expected to confirm or disconfirm
- Historical correlation matrix (from CAI `CrossAssetCorrelation` contracts): baseline correlations per regime
- Gold-specific ratios: gold/copper, gold/oil, gold/S&P, gold/silver

**Processing Stages**:
1. **Asset data collection** — Fetch current changes for all related assets (from W3 overnight data or live feed)
2. **Expected relationship lookup** — For the current regime (from W2), determine expected relationship between gold and each related asset:
   - Normal Growth: gold inversely correlated with real yields, DXY
   - Inflationary: gold positively correlated with equities, term premium
   - Crisis: gold negatively correlated with VIX initially (sold for liquidity), then positively
3. **Divergence/convergence detection** — For each related asset, classify:
   - **Confirming**: move in expected direction for gold thesis
   - **Disconfirming**: move opposite expected direction
   - **Neutral**: no significant move
4. **Confidence computation** — Overall cross-asset confidence: (confirming_count - disconfirming_count) / total_count
5. **Signal/noise contribution** — Output to W5: a confirming cross-asset matrix supports "signal" classification; a disconfirming matrix supports "noise" classification
6. **Conflict resolution contribution** — Output to W7: when two pieces of evidence conflict, the side with more cross-asset confirmation wins

**Existing Capabilities Reused**:
- CAI `CrossAssetCorrelation` contract — baseline correlation structure
- CAI `CaiEvidenceAdapter` — cross-asset evidence conversion
- CAI `SpreadAnalysis` contract — spread/ratio analysis (gold/copper, gold/oil, gold/S&P)
- W2 output — current regime for expected relationship lookup
- W3 output — overnight market data for all related assets
- `dxy_fetcher.py`, `real_yield_fetcher.py`, `fred_client.py` — asset data connectors

**Missing Capabilities Needed**:
- Regime-specific expected relationship database: (regime, gold, related_asset, expected_correlation_sign, confidence)
- Cross-asset divergence/convergence detector: per related asset, confirming/disconfirming/neutral classification
- Cross-asset confidence computer: aggregate across all related assets
- Cross-asset confirmation matrix generator: structured matrix output
- Gold-specific ratio monitors: gold/copper, gold/oil, gold/S&P, gold/silver with current values and z-scores
- Matrix→signal classification: feed into W5 noise/signal classifier
- Matrix→conflict resolution: feed into W7 when evidence conflicts

**Expected Outputs**:
- Cross-asset matrix: array of (related_asset, direction, expected_relationship, actual_relationship, confirming: bool, confidence)
- Gold-specific ratios: (ratio_name, current_value, historical_mean, z_score, trend)
- Overall cross-asset confidence: (confirming_count, disconfirming_count, neutral_count, net_confidence)
- Regime-specific assessment: "In current Inflationary regime, gold positively correlated with equities is expected — equity confirmation supports gold thesis"

**Completion Criteria**:
- Regime-specific expected relationships match Meth. §9 specifications
- Normal Growth regime: real yields and DXY confirming → high cross-asset confidence
- Inflationary regime: equities and term premium confirming → high cross-asset confidence (even if real yields disconfirm)
- Crisis regime: VIX and liquidity measures dominate
- Cross-asset output consumable by W5 and W7
- Gold-specific ratios correctly computed and trend-classified
- All existing tests pass

---

### W16: Multi-Window Evidence Aggregation (GRAM)

**Objective**: Report evidence coefficients across multiple estimation windows (full sample, 5-year, 1-year) to separate structural relationships from transitory ones. Key remedy for recency bias and overfitting.

**Source**: Meth. §3 (WGC GRAM multiple estimation windows), §10 (recency bias remedy — multi-window reporting). KB KR-002 (window-dependent coefficient variation), KR-003 (2022 regime break detected via rolling windows).

**Trigger**: On demand for any evidence query. Integral to W9 confidence assignment (model stability check). Integral to W10 thesis update (coefficient monitoring).

**Inputs**:
- Historical data for the variable pair (e.g., gold vs BEI, gold vs real yields, gold vs DXY)
- Estimation windows: full sample (14-year), 5-year, 1-year (weekly model)
- Current regime (from W2): for interpreting window differences
- KR expected coefficients: from KB R-squared, strength, confidence per window

**Processing Stages**:
1. **Multi-window regression** — For each variable pair, fit the same model across 3 windows:
   - Full sample (14-year minimum)
   - Medium (5-year)
   - Short (1-year or rolling weekly)
2. **Coefficient comparison** — Report coefficient per window, R² per window, and whether the coefficient is:
   - **Stable**: coefficient within 1σ across all windows
   - **Trending**: coefficient monotonic across windows (growing or shrinking)
   - **Diverging**: short-window coefficient significantly different (>2σ) from long-window
3. **Residual tracking** — Report unexplained variance per window. Growing unexplained variance in short window = potential new driver or regime shift (GRAM residual signal)
4. **Confidence impact** — Feed to W9:
   - Stable coefficients → support higher confidence
   - Trending coefficients → medium confidence (recognizing change)
   - Diverging coefficients → lower confidence (regime-dependent relationship)
5. **Recency bias safeguard** — When short-window coefficient significantly different from long-window, explicitly report both. Prevent the system from overweighting the short window

**Existing Capabilities Reused**:
- `EvidenceWeighter` — recency factor (short-window vs long-window)
- W1 output — KR-002 (window-dependent coefficients)
- W2 output — GRAM residual concept
- `ContextComparisonReport` — baseline vs contextual comparison (conceptually similar to window comparison)
- `ForecastConfidenceComputer._compute_spread_score()` — prediction interval analysis (analogous to window stability)

**Missing Capabilities Needed**:
- Multi-window regression engine: fit same model across N configurable windows (full, 5yr, 1yr)
- Coefficient stability classifier: stable/trending/diverging based on σ thresholds
- R² tracker per window: with trend (growing/shrinking/stable)
- GRAM residual: unexplained variance per window; residual trend flag
- Window-consistency confidence modifier: stable → +confidence, diverging → −confidence
- Recency bias safeguard: when short window diverges, report both windows with equal prominence
- Rolling coefficient monitor: weekly re-estimation of short-window coefficient to detect regime shifts early

**Expected Outputs**:
- Per variable pair: array of (window_label, coefficient, r_squared, residual_variance, sample_count)
- Stability classification: stable/trending/diverging with σ metrics
- GRAM residual trend: (current_residual, 3-month_trend, 6-month_trend, regime_shift_flag: bool)
- Confidence modifier: (base_confidence, window_consistency_multiplier, adjusted_confidence, recency_bias_flag)
- Rolling coefficient chart data: (date, coefficient, upper_ci, lower_ci) for short-window

**Completion Criteria**:
- Windows configurable: full, 5yr, 1yr as default; overrideable
- Coefficient stability correctly classifies: real yields coefficient (stable pre-2022, diverging post-2022)
- GRAM residual correctly flags 2022 regime break (residual spikes from 15% to 84%)
- Recency bias safeguard: when short window diverges from long window, both reported explicitly
- Output consumable by W9 for confidence adjustment
- All existing tests pass

---

### W17: Institutional Auditor Interface

**Objective**: Provide any external auditor with the ability to trace from a final decision back to every intermediate step, evidence source, and knowledge record — without access to the original authors.

**Source**: North Star (institutional transparency, external auditability). Meth. §1 (evidence provenance). AOS §4.2 (Explicit Reasoning Paths), §6.4 (Correctness > Performance > Transparency).

**Trigger**: On demand — auditor query by decision_id, date range, or event type.

**Inputs**:
- Any decision output (from W8, W10): decision_id, timestamp, event_type
- LineageRegistry (from W1, InferencePipeline): full provenance chain
- ReasoningChain (from W8): step-by-step reasoning
- Evidence set (from W6): all evidence items with weights
- KR source data (from W1): which KRs were referenced
- Methodology version (from AOS): which methodology version was used

**Processing Stages**:
1. **Decision lookup** — Accept decision_id. Retrieve the decision document from the journal (W14). Present: decision_type, confidence, timestamp, event_type, query
2. **Reasoning trace** — Show the full ReasoningChain: each step with its input evidence, confidence, conclusion. Auditor can expand any step
3. **Evidence provenance** — For each evidence item in the chain, show: evidence_id, source_node_id (KR reference), condition, sample_count, confidence. Trace back through LineageRegistry: evidence → knowledge_record → lesson → source_data
4. **KR trace** — For each referenced knowledge record, show the full KR document: mechanism, preconditions, historical evidence, regime_dependence, failure_conditions
5. **Weight audit** — Show EvidenceWeighter factors per evidence item: confidence_factor, sample_factor, provenance_factor, consistency_factor, recency_factor, regime_multiplier, composite_weight. Auditor can verify each computation
6. **Export** — Export full audit trail as: JSON (machine-readable), Markdown (human-readable), PDF (formal audit)

**Existing Capabilities Reused**:
- `LineageRegistry` — full provenance chain
- `Provenance` — created_at, source, model_version, git_commit, data_hash
- `ReasoningChain` — step-by-step reasoning with evidence references
- `WeightedAggregate` — weight factors per evidence item
- `Decision` — decision document with reasoning_chain_id
- W1 output — KR documents with full fields
- W8 output — thesis with reasoning chain
- W14 output — decision journal

**Missing Capabilities Needed**:
- Auditor query interface: lookup by decision_id, date_range, event_type, outcome
- Full trace renderer: decision → reasoning_chain → evidence → KR → source_data in single view
- Evidence provenance viewer: per evidence item, show all 5 weight factors with explanations
- KR document viewer: full KR with all fields (mechanism, preconditions, trigger, evidence, counter_examples, regime_dependence, failure_conditions, references)
- Export formats: JSON schema, Markdown report template, PDF generation
- Methodology version display: which version of the knowledge base and methodology was active at decision time
- Audit trail completeness checker: verify that every step has a valid backward trace to source data

**Expected Outputs**:
- Per decision: full audit report with (decision_summary, reasoning_chain, evidence_detail, weight_factors, KR_references, source_data_trace, methodology_version)
- Exportable in 3 formats: JSON (machine), Markdown (human), PDF (formal)
- Completeness certificate: "Every evidence item in this decision traces to a validated source data record"
- Auditor notes field: auditor can add annotations to the audit trail

**Completion Criteria**:
- Any decision traceable to source data in <5 steps
- Each evidence weight factor explainable: "confidence_factor = 0.64 = confidence 0.8 ^ exponent 2.0"
- KR documents displayed with all fields from KB specification
- Export in JSON and Markdown working
- Completeness checker verifies 100% backward traceability
- No access to original author required — all context in the audit trail
- All existing tests pass

---

## Priority Ranking

### Ranking Criteria

Each workflow is ranked by:
1. **Dependency**: does this workflow unblock others? (P0 = unblocks 3+, P1 = unblocks 1–2, P2 = downstream only)
2. **Daily use**: is this workflow executed every trading day? (higher priority)
3. **Decision impact**: does this workflow directly affect decision quality? (higher priority)
4. **Risk reduction**: does this workflow prevent systematic errors? (higher priority)
5. **Existing coverage**: how much existing capability can we reuse? (higher = easier to implement)

### Ranked List

| Rank | ID | Workflow | Tier | Dependencies | Daily | Impact | Risk | Reuse | Rationale |
|------|----|----------|------|-------------|-------|--------|------|-------|-----------|
| 1 | W1 | Knowledge Record Ingestion & Encoding | P0 | None | No | Critical | Low | High | Unlocks every downstream workflow — without encoded KRs, nothing else has knowledge to reason over |
| 2 | W2 | Macro Regime Diagnosis & Indicator Selection | P0 | W1 | Daily | Critical | High | Medium | Every weighting, reasoning, and decision step depends on regime. Current 4-regime detector is insufficient |
| 3 | W3 | Pre-Market Intelligence Scan | P1 | W2 | Daily | Critical | High | Medium | The daily entry point — without it, there are no inputs for evidence, reasoning, or decisions |
| 4 | W5 | Signal vs Noise Classification | P1 | W3, W2 | Daily | Critical | High | Low | Prevents the system from acting on noise. Current system has no noise filter — highest methodology gap (15% coverage) |
| 5 | W4 | Macro Event Prioritization & Triage | P1 | W3, W2 | Daily | High | Medium | Medium | Ensures the system focuses on what matters. Without it, all events are treated equally |
| 6 | W6 | Evidence Collection & Regime-Aware Weighting | P1 | W2, W5, W1 | Daily | Critical | Medium | High | Core reasoning step. Weighter exists; just needs regime-awareness extension |
| 7 | W8 | Investment Thesis Formation | P2 | W6, W7, W2, W1 | On-demand | Critical | Low | High | Core output. ReasoningEngine exists; needs 2 new step types and fragility audit integration |
| 8 | W9 | Confidence Assignment & OOS Calibration | P2 | W8, W6, W2, W1 | On-demand | High | Medium | Medium | Confidence exists but needs OOS calibration and meta-evidence integration |
| 9 | W7 | Conflicting Evidence Resolution | P2 | W6, W2, W1 | On-demand | High | High | Medium | Resolution exists at reasoning level but needs the full 4-action institutional framework |
| 10 | W10 | Thesis Update Cycle | P2 | W3, W5, W6, W8 | Daily | High | High | Low | Major gap (20% coverage). Enables the "living thesis" — critical for ongoing accuracy |
| 11 | W12 | Fragility Audit & Scenario Analysis | P3 | W8, W6, W2 | On-demand | High | High | Low | Prevents overconfidence and ensures downside awareness. "What could break this?" |
| 12 | W13 | Bias Prevention & Decision Review | P3 | W8, W6, W5 | On-demand | High | High | Low | Institutional safeguard against cognitive biases. Directly addresses Meth. §10 |
| 13 | W11 | Causal Relationship Evaluation | P3 | W1, W2 | Weekly | Medium | Medium | High | CausalGraph exists; needs the 5-criteria evaluation framework and ongoing maintenance |
| 14 | W14 | Decision Journal & Post-Mortem | P3 | W8, W10 | Quarterly | Medium | Medium | Medium | Attribution error remedy. LearningEngine exists; needs journal infrastructure |
| 15 | W15 | Cross-Asset Confirmation Matrix | P4 | W3, W2, W1 | Daily | Medium | Low | Medium | Enhancement for W5 and W7. Can initially use simpler checks |
| 16 | W16 | Multi-Window Evidence Aggregation | P4 | W1, W2 | Weekly | Medium | Low | Medium | Enhancement for W9 confidence. Recency bias remedy |
| 17 | W17 | Institutional Auditor Interface | P4 | W1, W8, W14 | On-demand | Low | Low | High | Compliance feature. High reuse of existing provenance/lineage infrastructure |

### Implementation Sequence

```
P0 — Foundation (must be built first)
  W1 ─────────────────────────────────────────────────────────────────┐
  W2 ──────────────────────────────────────────────────────┐          │
                                                            │          │
P1 — Daily Core (must be built next)                         │          │
  W3 ◄──────────────────────────────────────────────────────┤          │
  W5 ◄──────────────────── W3 ── W2                          │          │
  W4 ◄──────────────────── W3 ── W2                          │          │
  W6 ◄──────────────────── W5 ── W2 ── W1                    │          │
                                                            │          │
P2 — Analytical (core value delivery)                         │          │
  W8 ◄──────────────────── W6 ── W7 ── W2 ── W1              │          │
  W9 ◄──────────────────── W8 ── W6 ── W2 ── W1              │          │
  W7 ◄──────────────────── W6 ── W2 ── W1                    │          │
  W10 ◄──────────────────── W3 ── W5 ── W6 ── W8            │          │
                                                            │          │
P3 — Risk & Quality                                           │          │
  W12 ◄──────────────────── W8 ── W6 ── W2                   │          │
  W13 ◄──────────────────── W8 ── W6 ── W5                   │          │
  W11 ◄──────────────────── W1 ── W2                          │          │
  W14 ◄──────────────────── W8 ── W10                        │          │
                                                            │          │
P4 — Enhancement                                              │          │
  W15 ◄──────────────────── W3 ── W2 ── W1                   │          │
  W16 ◄──────────────────── W1 ── W2                          │          │
  W17 ◄──────────────────── W1 ── W8 ── W14                  │          │
                                                            ▼          ▼
                                                    All workflows depend on W1 (encoded KRs)
                                                    All analytical workflows depend on W2 (regime)
```

### Engineering Rules for Workflow Implementation

1. **Workflow = implementation unit.** Each workflow is implementable independently. Do not start W8 (Thesis Formation) until W6 (Evidence Collection) is complete.
2. **Reuse before build.** Every workflow reuses existing capabilities. The "Existing Capabilities Reused" section is mandatory reading before coding.
3. **Frozen components are frozen.** InferencePipeline, ReasoningEngine, DecisionEngine, Evidence, EventRegistry, Knowledge Expansion Framework, Benchmark — never modify. Extend via adapters.
4. **Completion criteria are gates.** A workflow is not done until all completion criteria pass. The 18-benchmark suite must pass before marking any workflow complete.
5. **Dependency discipline.** W1 (KR Ingestion) must complete before W2 (Regime Diagnosis) uses KR regime data. W6 (Evidence Weighting) must complete before W8 (Thesis Formation) uses regime-aware weights.
6. **Test at workflow boundaries.** Each workflow must have end-to-end integration tests that feed expected inputs and verify expected outputs — not just unit tests on internal components.
7. **Audit trail per workflow.** Every workflow execution must produce an audit record consumable by W17 (Auditor Interface).
