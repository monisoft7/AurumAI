# Institutional Contract Layer

**Purpose**: Canonical interface specification for all 17 institutional workflows. Every contract defines the producer, consumers, required fields, validation rules, and lifecycle policy. No workflow may communicate with another except through these contracts.

**Status**: Design specification. No implementation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        INSTITUTIONAL CONTRACT LAYER                      │
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  KR      │  │  Regime  │  │  Ind.    │  │  Evid.   │  │  Thesis  │  │
│  │  Record  │  │  Diag.   │  │  Hier.   │  │  Contract│  │  Contract│  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │              │              │              │              │      │
│  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐  │
│  │Confidence│  │ Decision │  │Scenario  │  │Fragility │  │  Audit   │  │
│  │ Contract │  │ Contract │  │ Contract │  │ Contract │  │  Trail   │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    All workflows produce and consume
                    exclusively through these contracts
```

---

## Contract 1: KnowledgeRecord

### Purpose
The canonical knowledge unit encoding a single institutional insight. Every downstream workflow queries, filters, and reasons over these records. This is the atomic unit of institutional memory.

### Owner
Knowledge Engineering (W1)

### Producer Workflow
W1 — Knowledge Record Ingestion & Encoding

### Consumer Workflows
W2 (regime→KR mapping), W3 (briefing context), W4 (prioritization), W5 (signal classification), W6 (evidence collection), W7 (conflict resolution), W8 (thesis formation), W9 (confidence calibration), W10 (thesis update), W11 (causal graph), W12 (scenario analysis), W13 (bias review), W14 (decision journal), W15 (cross-asset confirmation), W16 (multi-window GRAM), W17 (institutional auditor)

### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `knowledge_id` | str | YES | — | Unique identifier, pattern `KR-\d{3}` |
| `event_type` | str | YES | — | Category code from set |
| `asset` | str | YES | "gold" | Asset this KR applies to |
| `condition` | dict[str,str] | YES | {} | Key-value activation condition |
| `bias` | str | YES | — | Directional implication |
| `confidence` | float | YES | — | 0.0–1.0 numeric from KB text |
| `explanation` | str | YES | "" | KR title / short description |
| `mechanism` | str | YES | "" | Causal mechanism description |
| `preconditions` | str | YES | "" | Conditions that must hold |
| `trigger` | str | YES | "" | What activates this KR |
| `expected_impact` | str | YES | "" | Qualitative gold impact |
| `failure_conditions` | str | YES | "" | When this KR stops working |
| `regime_dependence` | str | YES | "" | Regime applicability description |
| `references` | str | YES | "" | Source documents |
| `counter_examples` | str | NO | "" | Historical counter-evidence |
| `methodology_version` | str | NO | "" | KB version string |
| `provenance` | Provenance\|None | NO | None | Source tracking |
| `metadata` | dict | NO | {} | Strength, historical_evidence, kb_source |
| `institutional_context` | dict[str,str] | NO | {} | Regime context annotations |
| `horizon_days` | int | NO | 0 | Statistical field (0 for KB KRs) |
| `sample_count` | int | NO | 0 | Statistical field |
| `positive_return_rate_pct` | float | NO | 0.0 | Statistical field |
| `negative_return_rate_pct` | float | NO | 0.0 | Statistical field |
| `up_direction_rate_pct` | float | NO | 0.0 | Statistical field |
| `down_direction_rate_pct` | float | NO | 0.0 | Statistical field |
| `flat_direction_rate_pct` | float | NO | 0.0 | Statistical field |
| `average_return_pct` | float | NO | 0.0 | Statistical field |
| `median_return_pct` | float | NO | 0.0 | Statistical field |
| `min_return_pct` | float | NO | 0.0 | Statistical field |
| `max_return_pct` | float | NO | 0.0 | Statistical field |
| `first_event_date` | str | NO | "" | Statistical field |
| `last_event_date` | str | NO | "" | Statistical field |
| `source_lesson_ids` | tuple[str] | NO | () | Statistical field |

### Event Type Codes

| Code | Source Category |
|------|----------------|
| `REAL_YIELD` | Real Yields / Interest Rates |
| `USD_FX` | US Dollar / FX |
| `CB_GOLD` | Central Bank Demand |
| `INFLATION` | Inflation / Breakevens |
| `GEOPOLITICAL` | Geopolitical Risk |
| `ETF_FLOW` | ETF Flows |
| `GENERAL` | Uncategorized / cross-cutting |

### Bias Values

`bullish`, `bearish`, `neutral`, `mixed`

### Validation Rules
1. `knowledge_id` must match `KR-\d{3}` pattern
2. `bias` must be one of {bullish, bearish, neutral, mixed}
3. `confidence` in [0.0, 1.0]
4. `event_type` must be a recognized code
5. Required fields must be non-empty for KB-sourced records
6. `metadata["kb_source"]` should be set when applicable

### Versioning Policy
- KB version tracked in `methodology_version`
- Schema changes add fields with defaults (never remove or rename)
- Breaking schema changes increment `KnowledgeRecord` major version
- Records are immutable after ingestion; corrections produce new versions linked via `provenance`

### Backward Compatibility
- New fields must have type-appropriate defaults (empty string, empty dict, 0.0, None)
- `from_dict()` must never raise on unknown or missing keys
- Consumer code must use `.get()` semantics for all optional fields
- Removing a field requires a deprecation period of one minor version

---

## Contract 2: RegimeDiagnosis

### Purpose
The current macro regime diagnosis. This is the central context object that determines which indicators are dominant, which KRs are active, and how evidence should be weighted. Every downstream reasoning step depends on this.

### Owner
Regime Analysis (W2)

### Producer Workflow
W2 — Macro Regime Diagnosis & Indicator Selection

### Consumer Workflows
W3 (data fetching priority), W4 (event triage), W5 (signal filter), W6 (evidence weighting), W7 (conflict resolution), W8 (thesis formation), W9 (confidence calibration), W10 (thesis update), W11 (causal evaluation), W12 (fragility audit), W13 (bias prevention), W14 (decision journal), W15 (cross-asset confirmation), W16 (multi-window aggregation), W17 (institutional auditor)

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `regime` | str | YES | Canonical regime code |
| `label` | str | YES | Human-readable label |
| `confidence` | float | YES | Max probability (0.0–1.0) |
| `probabilities` | dict[str,float] | YES | All 6 regime probabilities |
| `in_transition` | bool | YES | True if max prob < transition threshold |
| `transition_type` | str | YES | Classification of transition |
| `previous_regime` | str | YES | Regime code from prior period |
| `timestamp` | str | YES | ISO 8601 with timezone |
| `transition_confidence` | float | NO | 0.0–1.0 transition certainty |
| `regime_duration_days` | int | NO | Persistence of current regime |
| `gram_residual` | float | NO | Current unexplained variance |
| `gram_trend` | str | NO | "growing", "shrinking", "stable" |
| `indicator_hierarchy` | list[Indicator] | NO | Cached indicators for this regime |
| `trigger_levels` | list[TriggerLevel] | NO | Conditions that would change regime |
| `cross_asset_consistency` | dict | NO | Concordance per asset class |

### Regime Codes

| Code | Label | Meth. §9 Reference |
|------|-------|--------------------|
| `NORMAL_GROWTH` | Normal Growth (Goldilocks) | §9.1 |
| `INFLATIONARY` | Inflationary | §9.2 |
| `STAGFLATIONARY` | Stagflationary | §9.3 |
| `DEFLATIONARY_CRISIS` | Deflationary / Crisis | §9.4 |
| `GEOPOLITICAL_STRESS` | Geopolitical Stress | §9.5 |
| `STRUCTURAL_REGIME_CHANGE` | Structural Regime Change | §9.6 |

### Transition Types
`deterioration`, `improvement`, `regime_break`, `recovery_from_break`, `none`

### Validation Rules
1. `regime` must be one of the 6 canonical codes
2. `probabilities` keys must exactly match the 6 canonical codes
3. `confidence` must equal `max(probabilities.values())` within rounding tolerance
4. `probabilities` values must sum to 1.0 ± 0.01
5. `timestamp` must be ISO 8601 with timezone
6. If `in_transition` is True, `transition_type` must not be "none"
7. `gram_trend` must be one of {growing, shrinking, stable}

### Versioning Policy
- New regime types can be added (backward-compatible addition to `probabilities`)
- Regime codes are immutable once published
- Adding a regime increments minor version
- Removing or renaming a regime code is a major version change

### Backward Compatibility
- `probabilities` may contain additional unknown regimes; consumers must ignore unexpected keys
- Regime code string values are permanent; never reuse a deprecated code
- New fields are added as optional with documented defaults
- `transition_type` set may expand but existing values never change meaning

---

## Contract 3: Indicator

### Purpose
A typed entry within a regime's indicator hierarchy. Specifies which macro variable to monitor, its relative importance, which KRs support it, and its data source. Consumed by data fetching, evidence collection, and weighting stages.

### Owner
Regime Analysis (W2)

### Producer Workflow
W2 — IndicatorHierarchyGenerator (part of Macro Regime Diagnosis)

### Consumer Workflows
W3 (data fetching), W4 (event prioritization scoring), W5 (signal detection), W6 (evidence weighting), W7 (conflict context), W9 (confidence calibration), W15 (cross-asset confirmation), W16 (multi-window GRAM)

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `indicator` | str | YES | Canonical indicator name |
| `weight` | float | YES | 0.0–1.0, relative importance |
| `description` | str | YES | Human-readable label |
| `tier` | str | YES | "dominant", "secondary", "weaker" |
| `associated_kr_ids` | list[str] | NO | KnowledgeRecord IDs supporting this indicator |
| `data_source` | str | NO | FRED series, yfinance ticker, connector name |
| `frequency` | str | NO | "daily", "weekly", "monthly", "quarterly" |
| `unit` | str | NO | "pct", "level", "zscore", "index", "bps" |
| `trigger_levels` | list[TriggerLevel] | NO | Values that change indicator meaning |
| `methodology_citation` | str | NO | Reference to Meth. § section |

### Indicator Naming Convention
- Lowercase snake_case
- Suffix with source/tenor where applicable: `real_yields_10y_tips`, `breakeven_inflation_rate`, `gold_etf_flows`
- Data-source-specific suffixes: `_fred`, `_yfinance`, `_wgc`, `_jp_morgan`

### Tier Definitions
| Tier | Meaning | Weight Range | Consumer Behavior |
|------|---------|--------------|-------------------|
| `dominant` | Primary gold driver in this regime | 0.10–0.30 | Always fetch; highest evidence weight |
| `secondary` | Confirms or moderates the primary view | 0.05–0.10 | Fetch if resources permit |
| `weaker` | Marginal or regime-specific context | 0.01–0.05 | Fetch on-demand or for GRAM |

### Validation Rules
1. `tier` must be one of {dominant, secondary, weaker}
2. `weight` must be in [0.0, 1.0]
3. `indicator` name must match the canonical naming convention
4. If `associated_kr_ids` is non-empty, each ID must exist in the KnowledgeGraph
5. `frequency` must be one of {daily, weekly, monthly, quarterly} if specified

### Versioning Policy
- New indicators can be added at any time
- Indicator names are canonical and permanent
- Weight changes are minor version bumps
- Tier reassignment is a major version change

### Backward Compatibility
- Consumers treat unknown indicator names as `tier: "weaker"` with `weight: 0.0`
- Never remove an indicator; deprecate by setting weight to 0.0
- `associated_kr_ids` is dynamic; consumers should not cache it

---

## Contract 4: Evidence

### Purpose
A piece of evidence derived from a Knowledge Record, conditioned on the current regime and weighted by regime relevance. This is the fundamental unit of reasoning. Evidence is produced by W6 and consumed by every analytical workflow.

### Owner
Evidence Collection (W6)

### Producer Workflow
W6 — Evidence Collection & Regime-Aware Weighting

### Consumer Workflows
W5 (signal validation), W7 (conflict resolution), W8 (thesis formation), W9 (confidence calibration), W11 (causal evaluation), W12 (scenario analysis), W14 (decision journal), W15 (cross-asset confirmation), W16 (multi-window aggregation), W17 (institutional auditor)

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `evidence_id` | str | YES | Unique identifier |
| `source_kr_id` | str | YES | KnowledgeRecord ID |
| `source_kr_node_id` | str | YES | GraphNode ID |
| `event_type` | str | YES | KR category code |
| `condition` | dict[str,str] | YES | Activation condition from KR |
| `bias` | str | YES | bullish, bearish, neutral, mixed |
| `base_confidence` | float | YES | 0.0–1.0, from the KR |
| `regime_weight` | float | YES | 0.0–1.0, relevance in current regime |
| `composite_weight` | float | YES | base_confidence × regime_weight |
| `explanation` | str | YES | Evidence summary |
| `regime` | str | NO | Regime when collected |
| `mechanism` | str | NO | From source KR |
| `failure_conditions` | str | NO | From source KR |
| `counter_examples` | str | NO | From source KR |
| `provenance` | Provenance\|None | NO | Collection provenance |
| `metadata` | dict | NO | Additional annotations |
| `temporal_recency` | float | NO | 0.0–1.0, how recent |

### Evidence ID Convention
`ev_{source_kr_id}_{timestamp_suffix}`

### Validation Rules
1. `bias` must be one of {bullish, bearish, neutral, mixed}
2. `base_confidence` in [0.0, 1.0]
3. `regime_weight` in [0.0, 1.0]
4. `composite_weight` must equal `round(base_confidence * regime_weight, 4)` ± 0.0001
5. `source_kr_id` must reference an existing KnowledgeRecord
6. `evidence_id` must be globally unique
7. `temporal_recency` must be in [0.0, 1.0] if specified

### Versioning Policy
- Evidence schema is stable; extensions add optional fields only
- Composite weight formula changes are major version bumps
- Evidence objects are immutable once created; corrections produce new evidence_id

### Backward Compatibility
- `base_confidence * regime_weight` is the canonical composite formula
- Consumers should recompute composite_weight if the formula changes
- New metadata fields must not affect reasoning logic
- Unknown metadata keys are ignored by all consumers

---

## Contract 5: Thesis

### Purpose
A structured investment thesis formed from weighted, resolved evidence. Expresses a directional view on gold with explicit confidence, timeframe, causal mechanism, key assumptions, risk factors, and scenario analysis. The thesis is the central reasoning artifact.

### Owner
Thesis Formation (W8)

### Producer Workflow
W8 — Investment Thesis Formation

### Consumer Workflows
W9 (confidence calibration), W10 (thesis update), W11 (causal evaluation), W12 (fragility audit), W13 (bias prevention), W14 (decision journal), W17 (institutional auditor)

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `thesis_id` | str | YES | Unique identifier |
| `direction` | str | YES | bullish, bearish, neutral |
| `magnitude` | str | YES | strong, moderate, weak |
| `confidence` | float | YES | 0.0–1.0 |
| `timeframe_days` | int | YES | Investment horizon |
| `primary_mechanism` | str | YES | Causal mechanism driving the view |
| `supporting_evidence_ids` | list[str] | YES | Evidence IDs supporting this thesis |
| `conflicting_evidence_ids` | list[str] | YES | Evidence IDs that conflict |
| `key_assumptions` | list[str] | YES | Conditions that must hold |
| `risk_factors` | list[str] | YES | Things that could invalidate |
| `current_regime` | str | YES | RegimeDiagnosis.regime at formation |
| `created_at` | str | YES | ISO 8601 |
| `previous_thesis_id` | str\|None | NO | Links to prior version |
| `scenarios` | list[Scenario] | NO | Alternative scenarios |
| `trigger_levels` | list[dict] | NO | Data levels that would change thesis |
| `fragility_score` | float | NO | 0.0–1.0 from W12 |
| `bias_flags` | list[str] | NO | Identified biases from W13 |
| `attribution` | dict[str,float] | NO | Contribution of each evidence source |
| `methodology_version` | str | NO | Methodology version used |

### Thesis ID Convention
`th_{W8}_{yyyy_mm_dd}_{sequence}`

### Direction + Magnitude Semantics

| Direction | Magnitude | Meaning |
|-----------|-----------|---------|
| bullish | strong | High-conviction long; position near upper sizing |
| bullish | moderate | Constructive but measured; neutral position sizing |
| bullish | weak | Tentatively bullish; small or no position |
| bearish | strong | High-conviction short or underweight |
| bearish | moderate | Cautiously bearish; reduced exposure |
| bearish | weak | Mildly bearish; hedge only |
| neutral | — | No directional view; flat or market-weight |

### Validation Rules
1. `direction` must be one of {bullish, bearish, neutral}
2. `magnitude` must be one of {strong, moderate, weak}
3. `confidence` in [0.0, 1.0]
4. `timeframe_days` > 0
5. `supporting_evidence_ids` and `conflicting_evidence_ids` must reference existing Evidence
6. `key_assumptions` must have at least 1 entry
7. `risk_factors` must have at least 1 entry
8. `fragility_score` in [0.0, 1.0] if specified

### Versioning Policy
- A new thesis version is created on every update (immutable chain)
- `previous_thesis_id` links versions; null for original thesis
- Breaking schema changes create a new thesis type with a new ID prefix
- Thesis versions are never deleted; old versions remain for audit

### Backward Compatibility
- Old thesis IDs remain valid for journal and review
- `direction` and `magnitude` value sets are frozen; additions only
- `key_assumptions` and `risk_factors` may be empty in urgent theses (relaxed validation on rapid updates)

---

## Contract 6: Confidence

### Purpose
A unified confidence model across all layers: KR confidence, evidence confidence, regime confidence, thesis confidence, and decision confidence. Provides the calibration method, decay function, historical accuracy tracking, and overconfidence detection. Every workflow that produces or consumes confidence uses this contract.

### Owner
Confidence Calibration (W9)

### Producer Workflows
W6 (evidence confidence field), W8 (thesis confidence), W9 (calibrated confidence adjustments), W14 (decision confidence)

### Consumer Workflows
W5 (signal threshold filtering), W6 (evidence weighting), W8 (thesis strength), W9 (calibration), W10 (update triggers), W12 (scenario probability), W13 (overconfidence detection), W14 (decision sizing), W16 (multi-window aggregation), W17 (institutional auditor)

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_type` | str | YES | Layer this confidence applies to |
| `source_id` | str | YES | Entity ID |
| `confidence_value` | float | YES | 0.0–1.0 |
| `calibration_method` | str | YES | How this value was determined |
| `decay_function` | str | NO | "linear", "exponential", "step", "none" |
| `decay_rate` | float | NO | Per-period decay (0.0–1.0) |
| `half_life_days` | int | NO | For exponential decay |
| `oos_accuracy` | float | NO | 0.0–1.0 track record |
| `calibration_bins` | dict | NO | Historical accuracy by confidence bin |
| `overconfidence_flag` | bool | NO | True if accuracy < reported confidence |
| `adjustment_history` | list[dict] | NO | Record of past adjustments |
| `methodology_version` | str | NO | Calibration methodology version |

### Source Types
`kr`, `evidence`, `regime`, `thesis`, `decision`

### Calibration Methods
| Method | Meaning | Default When Calibration Not Possible |
|--------|---------|---------------------------------------|
| `kb_text` | Confidence parsed from KB document | 0.0 |
| `markov_probability` | Markov switching model probability | 0.5 |
| `composite_weight` | base_confidence × regime_weight | 0.0 |
| `empirical` | Historical out-of-sample accuracy | 0.0 |
| `expert` | Manual expert assessment | 0.5 |
| `consensus` | Agreement across multiple sources | 0.5 |

### Validation Rules
1. `confidence_value` in [0.0, 1.0]
2. `source_type` must be one of {kr, evidence, regime, thesis, decision}
3. If `decay_function` specified, `decay_rate` must be in [0.0, 1.0]
4. `oos_accuracy` in [0.0, 1.0] if specified
5. `calibration_method` must be a recognized method key

### Versioning Policy
- Calibration method changes are minor version bumps
- Decay function changes are major version bumps
- `adjustment_history` records are immutable
- Adding a calibration method is backward-compatible

### Backward Compatibility
- Unknown calibration methods default to `confidence_value / 2` (conservative fallback)
- Decay function may be absent; consumers use `decay_function: "none"` as default
- `calibration_bins` structure may change between methodology versions; consumers use `oos_accuracy` as the portable fallback

---

## Contract 7: Decision

### Purpose
The final trading decision produced by the institutional reasoning pipeline. Encodes direction, magnitude, position sizing, risk metrics, and the full attribution chain from KR through evidence through thesis. This is the terminal output of the pipeline.

### Owner
Decision Engine (W14, aggregates W8 + W9 + W12 + W13)

### Producer Workflow
W14 — Decision Journal & Post-Mortem

### Consumer Workflows
W14 (self, for post-mortem), W17 (institutional auditor), external execution systems

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `decision_id` | str | YES | Unique identifier |
| `thesis_id` | str | YES | Thesis that drove this decision |
| `direction` | str | YES | long, short, neutral, reduce, add |
| `magnitude` | str | YES | strong, moderate, marginal |
| `confidence` | float | YES | 0.0–1.0 (from W9) |
| `position_size_pct` | float | YES | 0.0–100.0 of portfolio |
| `timeframe_days` | int | YES | Intended holding period |
| `primary_evidence_ids` | list[str] | YES | Key evidence driving the decision |
| `current_regime` | str | YES | Regime at decision time |
| `risk_metrics` | dict | YES | VaR, CVaR, max drawdown |
| `created_at` | str | YES | ISO 8601 |
| `provenance` | Provenance | YES | Full attribution chain |
| `alternatives_considered` | list[dict] | NO | Other evaluated paths |
| `scenario_outcomes` | list[dict] | NO | Expected outcome by scenario |
| `fragility_assessment` | dict | NO | From W12 |
| `bias_review` | dict | NO | From W13 |
| `stop_loss_level` | float | NO | Price stop level |
| `take_profit_level` | float | NO | Price target level |
| `post_mortem` | dict | NO | Outcome analysis (appended after resolution) |
| `actual_return_pct` | float | NO | Filled after position closes |
| `methodology_version` | str | NO | Methodology version |

### Decision ID Convention
`dec_{thesis_id}_{sequence}`

### Direction Values
| Direction | Meaning |
|-----------|---------|
| `long` | Open or add to long position |
| `short` | Open or add to short position |
| `neutral` | Close position, go flat |
| `reduce` | Reduce existing position size |
| `add` | Add to existing position |

### Magnitude Values
| Magnitude | Position Size Implication |
|-----------|--------------------------|
| `strong` | 60–100% of maximum allowed position |
| `moderate` | 25–60% of maximum |
| `marginal` | 0–25% of maximum |

### Risk Metrics Required Fields
- `var_95`: float — 95% Value at Risk (% of portfolio)
- `cvar_95`: float — 95% Conditional VaR
- `max_drawdown_pct`: float — Current drawdown from peak
- `position_concentration`: float — Position as % of liquid assets

### Validation Rules
1. `direction` must be one of {long, short, neutral, reduce, add}
2. `magnitude` must be one of {strong, moderate, marginal}
3. `confidence` in [0.0, 1.0]
4. `position_size_pct` in [0.0, 100.0]
5. `timeframe_days` > 0
6. `thesis_id` must reference an existing Thesis
7. `primary_evidence_ids` must reference existing Evidence
8. `risk_metrics` must contain `var_95`, `cvar_95`, `max_drawdown_pct`, `position_concentration`

### Versioning Policy
- Decisions are immutable once journaled
- Post-mortem fields are appended, not edited
- Schema changes are additive only
- Decision IDs are permanent and traceable

### Backward Compatibility
- Old decision formats are supported for replay and audit
- `post_mortem` may be absent (decision not yet resolved)
- `actual_return_pct` is null until position closes
- Unknown `risk_metrics` keys are ignored by consumers

---

### Supplementary Contract: Scenario

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `scenario_id` | str | YES | Unique within parent thesis |
| `name` | str | YES | "base_case", "bull_case", "bear_case", "tail_risk" |
| `probability` | float | YES | 0.0–1.0 |
| `description` | str | YES | Narrative description |
| `gold_price_target` | float | NO | Expected gold price |
| `timeframe_days` | int | NO | Horizon for this scenario |
| `trigger_conditions` | list[str] | NO | What would make this scenario materialize |

### Supplementary Contract: TriggerLevel

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `indicator` | str | YES | Indicator name |
| `condition` | str | YES | Human-readable condition |
| `target` | str | YES | What happens when triggered |
| `threshold_value` | float | NO | Numeric threshold |
| `direction` | str | NO | "above", "below", "crosses" |

---

## Dependency Graph

```
W1 ──────────────────────────────────────────────────────────────────────┐
│ KnowledgeRecord                                                         │
│ KnowledgeGraph                                                          │
└────────┬────────────────────────────────────────────────────────────────┘
         │
         │ KnowledgeRecord refs
         ▼
W2 ──────────────────────────────────────────────────────────────────────┐
│ RegimeDiagnosis                                                         │
│ Indicator[]                                                             │
└────────┬────────────────────────────────────────────────────────────────┘
         │
         │ Regime + Indicator refs
         ▼
W3 ──────────────────────────────────────────────────────────────────────┐
│ PreMarketBriefing (uses Regime + Indicators to fetch data)              │
│ - Overnight price changes                                               │
│ - News summary with sentiment                                           │
│ - Risk snapshot                                                         │
│ - Positioning snapshot                                                  │
│ - Anomaly flags                                                         │
│ - Watchlist                                                             │
└────────┬────────────────────────────────────────────────────────────────┘
         │
         │ Briefing context
         ▼
W4 ──────────────────────────────────────────────────────────────────────┐
│ PrioritizedEventList (uses Regime + Briefing to rank events)            │
│ - Event priority scores                                                 │
│ - Event-regime relevance                                                │
└────────┬────────────────────────────────────────────────────────────────┘
         │
         │ Priority + event context
         ▼
W5 ──────────────────────────────────────────────────────────────────────┐
│ SignalClassification (uses Regime + priority events to filter signals)  │
│ - Signal/noise labels per event                                         │
│ - Confidence per classification                                         │
└────────┬────────────────────────────────────────────────────────────────┘
         │
         │ Classified signals
         ▼
W6 ──────────────────────────────────────────────────────────────────────┐
│ Evidence[] (uses Regime + classified signals + KnowledgeGraph)          │
│ - Creates Evidence from matching KRs                                    │
│ - Applies regime_weight                                                 │
│ - Computes composite_weight                                             │
└────────┬────────────────────────────────────────────────────────────────┘
         │
         │ Weighted Evidence[]
         │
         ├───────────────────────────────────────────────────────────────┐
         │                                                               │
         ▼                                                               ▼
W7 ──────────────────────────────┐   W8 ────────────────────────────────┐
│ ResolvedEvidence (conflict      │   │ Thesis (from weighted evidence)   │
│ resolution across Evidence[])   │   │ - direction, magnitude, conf     │
│ - consensus/disagreement flags  │   │ - supporting + conflicting ev_ids │
│ - conflict-free collection      │   │ - key_assumptions, risk_factors  │
└────────┬────────────────────────┘   └────────┬─────────────────────────┘
         │                                     │
         │ Resolved evidence feed              │ Thesis ref
         ▼                                     ▼
W9 ──────────────────────────────────────────────────────────────────────┐
│ Confidence (calibration applied to thesis + evidence)                  │
│ - Calibrated confidence_value per source_type                          │
│ - Decay function applied                                               │
│ - Overconfidence flags                                                 │
└────────┬────────────────────────────────────────────────────────────────┘
         │
         │ Calibrated confidence refs
         │
         ├───────────────────────────────────────────────────────────────┐
         │                                                               │
         ▼                                                               ▼
W10 ────────────────────────────┐   W11 ────────────────────────────────┐
│ UpdatedThesis (or affirmed)    │   │ CausalGraph (evaluates thesis     │
│ - new thesis_id with           │   │ mechanisms against KnowledgeGraph)│
│   previous_thesis_id link      │   │ - causal validation of mechanism  │
│ - revised fields               │   │ - causal confidence score         │
└────────┬────────────────────────┘   └────────┬─────────────────────────┘
         │                                     │
         │ Updated thesis refs                 │ Causal validation
         ▼                                     ▼
W12 ─────────────────────────────────────────────────────────────────────┐
│ FragilityAssessment (combines thesis + causal + confidence)             │
│ - fragility_score                                                       │
│ - scenario outcomes                                                     │
│ - scenario probabilities                                                │
└────────┬────────────────────────────────────────────────────────────────┘
         │
         │ Fragility ref
         ▼
W13 ─────────────────────────────────────────────────────────────────────┐
│ BiasReview (evaluates thesis + frag + confidence for biases)            │
│ - bias_flags                                                            │
│ - decision quality score                                                │
└────────┬────────────────────────────────────────────────────────────────┘
         │
         │ Bias refs
         ▼
W14 ─────────────────────────────────────────────────────────────────────┐
│ Decision (final output: thesis + frag + bias + confidence combined)     │
│ - decision_id                                                           │
│ - direction, magnitude, position_size                                   │
│ - full attribution chain (provenance)                                   │
│ - post_mortem (appended after resolution)                               │
└────────┬────────────────────────────────────────────────────────────────┘
         │
         │ Decision + all upstream refs
         ▼
W17 ─────────────────────────────────────────────────────────────────────┐
│ InstitutionalAuditor (reads all contracts for compliance)               │
│ - audit trail                                                          │
│ - compliance report                                                    │
│ - methodology adherence verification                                   │
└─────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────────────┐
                              │  W15 Cross-Asset      │
                              │  Confirmation         │
                              │  (feeds W6, W7)       │
                              └─────────┬────────────┘
                                        │
                              ┌─────────┴────────────┐
                              │  W16 Multi-Window     │
                              │  GRAM (feeds W2, W6)  │
                              └──────────────────────┘

```

### Data Flow Rules

1. **Downstream-only edges**: A workflow may only consume contracts produced by upstream or same-level workflows. No circular dependencies.

2. **Contract version compatibility**: A consumer must accept any version of a contract within the same major version as when the consumer was built.

3. **Optional field discipline**: A consumer that requires an optional field must provide a documented default behavior when the field is absent.

4. **Provenance chain**: Every Decision must be traceable through its Thesis → Evidence[] → KnowledgeRecord[] chain. W17 validates this.

5. **Update propagation**: When W10 produces an updated thesis, W14 must re-consume W12 (fragility) and W13 (bias) before producing a new decision. The update cycle is full-stack from W8 → W9 → W10 → W11 → W12 → W13 → W14.

---

## Contract Lifecycle

```
  DRAFT ──→ APPROVED ──→ DEPRECATED ──→ RETIRED
     │           │            │              │
     │           │            │              │
     ▼           ▼            ▼              ▼
  Active       Active        Consumers      Historical
  dev.         in use        must migrate   reference only
```

| State | Meaning | Duration |
|-------|---------|----------|
| `DRAFT` | Under design, not yet consumed | 1–2 weeks |
| `APPROVED` | All consumers confirmed compatible | Indefinite |
| `DEPRECATED` | Replacement exists, migration period | 2 minor versions |
| `RETIRED` | No longer in use | Permanent |

---

## Contract Compatibility Matrix

| Consumer ↓ \ Producer → | KR | Regime | Indicator | Evidence | Thesis | Confidence | Decision |
|-------------------------|:--:|:------:|:---------:|:--------:|:------:|:----------:|:--------:|
| W2 Macro Regime | ✓ | — | — | — | — | — | — |
| W3 Pre-Market | ✓ | ✓ | ✓ | — | — | — | — |
| W4 Event Priority | — | ✓ | ✓ | — | — | — | — |
| W5 Signal/Noise | ✓ | ✓ | — | ✓ | — | ✓ | — |
| W6 Evidence Collection | ✓ | ✓ | ✓ | — | — | ✓ | — |
| W7 Conflict Resolution | — | ✓ | — | ✓ | — | — | — |
| W8 Thesis Formation | — | ✓ | — | ✓ | — | ✓ | — |
| W9 Confidence Calibr. | ✓ | ✓ | — | ✓ | ✓ | — | — |
| W10 Thesis Update | — | ✓ | — | ✓ | ✓ | ✓ | — |
| W11 Causal Evaluation | ✓ | — | — | ✓ | ✓ | — | — |
| W12 Fragility Audit | — | ✓ | — | ✓ | ✓ | ✓ | — |
| W13 Bias Prevention | — | — | — | ✓ | ✓ | ✓ | ✓ |
| W14 Decision Journal | ✓ | ✓ | — | ✓ | ✓ | ✓ | — |
| W15 Cross-Asset | ✓ | ✓ | ✓ | ✓ | — | — | — |
| W16 Multi-Window GRAM | ✓ | ✓ | ✓ | ✓ | — | ✓ | — |
| W17 Institutional Auditor | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |

---

## Implementation Sequence by Contract

The contracts must be implemented in dependency order. A contract cannot be implemented until all contracts it depends on (by consuming them) are approved.

```
Phase 1 (P0):  KR Record ──→ Regime ──→ Indicator
                    ↓
Phase 2 (P1):  Evidence
                    ↓
Phase 3 (P2):  Thesis ──→ Confidence
                    ↓
Phase 4 (P3):  Scenario (supplementary)
                    ↓
Phase 5 (P3):  Decision
                    ↓
Phase 6 (P4):  TriggerLevel (supplementary)
```

This ordering ensures that every contract is fully defined and approved before any consuming workflow begins implementation.

---

## Key Design Decisions

1. **Immutable records**: KnowledgeRecord, Evidence, Thesis, and Decision are immutable once created. Corrections produce new versions with provenance links. This ensures full traceability and satisfies W17 auditor requirements.

2. **Confidence is a separate contract**: Confidence is not embedded in other contracts because it is produced and calibrated by a dedicated workflow (W9), has its own decay semantics, and is consumed by multiple layers independently.

3. **Regime is first-class**: RegimeDiagnosis is not a metadata field on other contracts; it is a standalone contract because it is the central context object that coordinates all downstream stages.

4. **Optional with defaults**: Every optional field has a documented default behavior. No consumer may assume optional fields are present.

5. **No cross-contract references in required fields**: A required field on one contract may reference another contract's optional field, but if that optional field is absent, the consumer must handle it gracefully.

6. **Provenance is a chain, not a tree**: The provenance chain is linear: KB → KR → Evidence → Thesis → Decision. Cross-references (e.g., Evidence citing multiple KRs) create a directed acyclic graph with the Decision as the terminal sink.
