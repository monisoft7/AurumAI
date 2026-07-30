# Institutional Knowledge Contracts

**Document Classification**: Architecture — Permanent Reference  
**Date**: 2026-07-26  
**Scope**: Canonical knowledge contracts for all four Tier-1 Intelligence Departments  
**Status**: Freeze Candidate — Implementation Reference  
**Authority**: Chief Architect Review

---

## 0. Common Contract Framework

Every knowledge object exported by any Tier-1 department conforms to the following common contract. Department-specific contracts in Sections 1-4 define only the fields unique to each object; the common framework applies implicitly to all.

### 0.1 Identity

Every knowledge object carries an identifier that is unique within the institution. The identifier encodes the producing department, the knowledge object type, and the observation timestamp.

`{department_code}:{object_type}:{observation_date}`

Example: `CBI:PolicyBiasScore:FOMC:2026-07-26`

### 0.2 Confidence

Every knowledge object carries a `confidence` property expressed as a decimal on the standardized institutional scale:

| Value | Label | Meaning |
|-------|-------|---------|
| 0.00 – 0.19 | Speculative | Informed conjecture, limited supporting evidence |
| 0.20 – 0.39 | Low | Some supporting evidence, significant uncertainty |
| 0.40 – 0.59 | Moderate | Multiple evidence sources, moderate agreement |
| 0.60 – 0.79 | High | Strong evidence, cross-source agreement |
| 0.80 – 0.89 | Very High | Preponderance of evidence, near-certain directional view |
| 0.90 – 1.00 | Near-Certain | Reserved for outcomes that are effectively determined (e.g., a rate decision where forward guidance is unambiguous and markets have fully converged) |

Confidence is always a single value, never a range. Where a department wishes to express uncertainty, it uses the `confidence_distribution` optional field (see 0.3).

### 0.3 Common Optional Fields

The following fields MAY appear on any knowledge object. They carry the same semantics across all departments.

| Field | Type | Semantics |
|-------|------|-----------|
| `confidence_distribution` | Distribution summary (e.g., {p10, p50, p90}) | Used when a single confidence value is insufficient. The producing department communicates the full probability distribution. |
| `scenario_analysis` | List of alternative scenarios | Each scenario has a label, a probability, and a deviation from the base case. Used when the base case is insufficient to capture the range of plausible outcomes. |
| `cross_references` | List of knowledge object IDs | References to other institutional knowledge objects that informed, confirm, or contradict this assessment. Enables traceability across departmental boundaries. |
| `methodology_version` | String | Identifies which analytical methodology produced this object. Enables consumers to assess whether methodology changes have affected output comparability over time. |
| `data_quality_flags` | List of issues | Identifies data quality concerns affecting this assessment (e.g., stale data, missing source, conflicting observations). Enables consumers to discount confidence appropriately. |

### 0.4 Departamental Provenance

Every knowledge object carries the following provenance metadata, which is populated by the producing department's infrastructure and must never be altered by consumers.

| Field | Semantics |
|-------|-----------|
| `producing_department` | CBI, CAI, CFI, or NI |
| `object_type` | The knowledge object name from Sections 1-4 |
| `observation_timestamp` | When the underlying observation was made |
| `publication_timestamp` | When this knowledge object was finalized and exported |
| `producing_analyst` | Identifier for the analyst or automated process that produced the assessment |
| `source_data_descriptor` | Description of the source data used (not the data itself, but a descriptor enabling a consumer to identify what data was consulted) |
| `last_updated` | Timestamp of the most recent update to this object instance |

### 0.5 Evidence References

Every knowledge object carries an `evidence_references` field that links to the specific evidence that supports its assessments. Each reference specifies:

- `source_category`: The type of source (e.g., central bank statement, COT report, ETF flow data, financial news article)
- `source_descriptor`: A description sufficient for a consumer to identify the specific source (e.g., "FOMC Statement, March 2026", "COT Report, Release Date 2026-07-23")
- `contribution`: How this source contributed to the assessment (e.g., "primary directional signal", "contradicting signal noted in assessment", "baseline context only")
- `confidence_contribution`: The weight this source contributed to the overall confidence assessment (high, moderate, low, informational)

### 0.6 Validity Period

Every knowledge object specifies its validity period using start and end timestamps.

- `valid_from`: When the object becomes authoritative. Normally equal to `publication_timestamp`.
- `valid_until`: When the object ceases to be authoritative. Set by the producing department based on the expected decay rate of the underlying intelligence.

If `valid_until` is reached and no updated object has been published, consumers MUST NOT use the expired object for active assessment. Knowledge objects in historical archives retain their original validity markers for audit and simulation purposes.

### 0.7 Time Horizon

Every knowledge object specifies its analytical time horizon:

| Horizon Code | Label | Typical Range | Used By |
|-------------|-------|---------------|---------|
| T0 | Event/Now | Current observation | All departments (positioning, policy scores, narrative strength) |
| T1 | Short-Term | 1-5 trading days | NI (collapse warnings, gap alerts), CFI (accumulation signals) |
| T2 | Medium-Term | 1-4 weeks | NI (positioning gap), CAI (divergence alerts), CFI (flow momentum) |
| T3 | Long-Term | 1-12 months | CBI (rate paths, liquidity outlook), CAI (regime assessment) |
| T4 | Structural | 1+ years | CBI (de-dollarization), CFI (structural demand shift), NI (structural narratives) |

---

## 1. Central Bank Intelligence — Knowledge Contracts

### 1.1 PolicyBiasScore

**Object name**: `PolicyBiasScore`  
**Department code**: `CBI`  
**Update cadence**: After every meeting, speech, or minutes release; minimum weekly for Tier 1 banks  
**Time horizon**: T0 (current stance), T3 (expected stance trajectory)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `central_bank` | Identifier | One of: FED, ECB, BOJ, BOE, PBOC, SNB, RBA, RBNZ, BOC |
| `score` | Integer | -5 (aggressively dovish/emergency easing) to +5 (aggressively hawkish/emergency tightening). 0 = assessed neutrality. |
| `direction` | Enum | tightening, easing, neutral |
| `confidence` | Decimal | 0.00 – 1.00 (per 0.2) |
| `score_components` | Map | Breakdown of composite: statement_language_weight, speech_weight, voting_pattern_weight, forward_guidance_weight |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next scheduled meeting for that central bank |

**Optional fields**: `scenario_analysis`, `cross_references`, `methodology_version`, `confidence_distribution`

**Consumers**: Knowledge Department (Evidence Repository, Feature Extraction, Context Enrichment), Forecasting & Risk, CAI (policy context), CFI (official-sector context), NI (high-authority narrative source)

---

### 1.2 RatePathProjection

**Object name**: `RatePathProjection`  
**Department code**: `CBI`  
**Update cadence**: After every meeting; continuous refinement  
**Time horizon**: T3 (next 8 meetings)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `central_bank` | Identifier | One of the 9 covered central banks |
| `base_path` | List of {meeting_date, rate_bps} pairs | Most likely rate at each of the next 8 scheduled meetings |
| `confidence_interval` | Integer | Width of the 80% confidence interval around the base path, in basis points |
| `confidence` | Decimal | 0.00 – 1.00 |
| `current_rate` | Integer | Current policy rate in basis points |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next meeting date for that central bank |

**Optional fields**: `scenario_analysis` (hawkish/dovish alternative paths), `confidence_distribution`, `cross_references` (especially to market-implied rate paths for divergence tracking)

**Consumers**: Forecasting & Risk (primary — rate-sensitive models), Knowledge Department, CFI (official-sector context)

---

### 1.3 ForwardGuidanceRecord

**Object name**: `ForwardGuidanceRecord`  
**Department code**: `CBI`  
**Update cadence**: After every meeting or communication that modifies guidance; weekly integrity check  
**Time horizon**: T3 (valid until next guidance modification)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `central_bank` | Identifier | One of the 9 covered central banks |
| `guidance_type` | Enum | calendar_based, state_contingent, open_ended, quantitative |
| `guidance_text` | String | The canonical formulation of the current forward guidance |
| `credibility_score` | Decimal | 0.00 (no follow-through credibility) to 1.00 (perfect follow-through). Based on historical ratio of actual decisions to guidance signals. |
| `language_delta` | String | What changed from the prior guidance formulation. Empty string if no material change since last record. |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next communication expected to modify guidance |

**Optional fields**: `scenario_analysis` (conditions that would trigger guidance change), `cross_references`, `data_quality_flags`

**Consumers**: Knowledge Department (Evidence Repository, Reasoning Engine), NI (high-authority narrative source)

---

### 1.4 LiquidityOutlook

**Object name**: `LiquidityOutlook`  
**Department code**: `CBI`  
**Update cadence**: Monthly; interim alerts for abrupt liquidity events  
**Time horizon**: T3 (3-month forward)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `classification` | Enum | Expanding, Stable, Contracting |
| `pace_qualifier` | Enum | rapidly, gradually, marginally |
| `g4_balance_sheet_trajectory` | List of {central_bank, direction, pace, magnitude_bps} | Aggregate G4 central bank balance sheet change |
| `reserve_trend` | Enum | accumulating, stable, drawing_down |
| `money_market_stress` | List of {indicator, reading, threshold, stress_level} | SOFR, repo rates, FRA-OIS spreads |
| `fiscal_liquidity_effects` | String | Assessment of TGA balance, RRP facility, and other fiscal liquidity impacts |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next monthly refresh |

**Optional fields**: `scenario_analysis` (liquidity shock scenarios), `cross_references` (to CAI LiquidityRotationMap, CFI LiquidityMigrationMap)

**Consumers**: Knowledge Department, Forecasting & Risk, CFI (liquidity context for flow interpretation)

---

### 1.5 BalanceSheetOutlook

**Object name**: `BalanceSheetOutlook`  
**Department code**: `CBI`  
**Update cadence**: Monthly  
**Time horizon**: T3-T4 (3-12 months)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `central_bank` | Enum | FED, ECB, BOJ |
| `total_balance_sheet_size` | Map | {current, projected_3m, projected_6m, projected_12m} in USD equivalent |
| `govt_bond_holdings_trajectory` | List of {month, holdings_bps} | Government bond holdings projection |
| `qe_qt_pace` | Map | {announced_pace, actual_runoff, deviation_bps, reinvestment_policy} |
| `emergency_facility_usage` | List of {facility_name, outstanding_amount, trend} | Any emergency lending facility usage |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next monthly refresh |

**Optional fields**: none

**Consumers**: Knowledge Department, Forecasting & Risk (liquidity-sensitive models), CAI (yield context)

---

### 1.6 PolicyDivergenceMatrix

**Object name**: `PolicyDivergenceMatrix`  
**Department code**: `CBI`  
**Update cadence**: Weekly  
**Time horizon**: T0 (current divergence state)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `divergence_scores` | 9x9 matrix of integers | Each cell: divergence score between central bank i and central bank j. Positive = bank i more hawkish. Negative = bank i more dovish. |
| `aggregate_divergence_index` | Integer | Single value summarizing overall cross-bank divergence. Higher = more divergence. |
| `aggregate_trend` | Enum | widening, stable, narrowing |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next weekly refresh |

**Optional fields**: none

**Consumers**: Knowledge Department (Regime Detection), Forecasting & Risk, CAI (FX and cross-asset context)

---

### 1.7 HawkDoveScore

**Object name**: `HawkDoveScore`  
**Department code**: `CBI`  
**Update cadence**: After every speech or public appearance; full refresh monthly  
**Time horizon**: T0 (current leaning)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `central_bank` | Identifier | One of the 9 covered central banks |
| `policymaker` | String | Name and title of the committee member |
| `voting_status` | Enum | current_voter, rotating_in, non_voting |
| `score` | Integer | -3 (consistent dove) to +3 (consistent hawk) |
| `score_trend` | Enum | moving_hawkish, stable, moving_dovish |
| `recent_communications` | List of {date, type, summary} | Recent speeches, interviews, or publications that informed the score |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | After next communication by this policymaker or monthly refresh, whichever is sooner |

**Optional fields**: none

**Consumers**: Internal departmental use (feeds PolicyBiasScore), Knowledge Department

---

### 1.8 GlobalMonetaryRegime

**Object name**: `GlobalMonetaryRegime`  
**Department code**: `CBI`  
**Update cadence**: Monthly; interim alerts on regime transition signals  
**Time horizon**: T3-T4 (3-12 months)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `regime` | Enum | Synchronized_Easing, Synchronized_Tightening, Divergent, Transition, Emergency |
| `regime_description` | String | Narrative description of the current regime and its primary drivers |
| `aggregate_monetary_stance` | Decimal | Weighted average of all 9 PolicyBiasScore values, weighted by each bank's global impact weight |
| `synchronization_measure` | Decimal | Statistical measure of how synchronized policy is across all 9 banks. 1.0 = perfectly synchronized, 0.0 = maximum divergence. |
| `transition_signals` | List of string | Any signals that a regime transition may be approaching |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next monthly refresh |

**Optional fields**: `scenario_analysis` (alternative regime transition paths), `cross_references` (to CAI CrossAssetRegimeAssessment for cross-validation)

**Consumers**: Knowledge Department (Regime Detection — global overlay), Forecasting & Risk

---

### 1.9 CentralBankSurpriseIndex

**Object name**: `CentralBankSurpriseIndex`  
**Department code**: `CBI`  
**Update cadence**: After every meeting; trailing recalculation monthly  
**Time horizon**: T3 (12-24 month trailing window)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `central_bank` | Identifier | One of the 9 covered central banks |
| `decision_surprise_rate` | Decimal | Proportion of meetings where actual decision differed from consensus, trailing 12 months |
| `communication_surprise_rate` | Decimal | Proportion of communications where guidance shifted without data justification, trailing 12 months |
| `balance_sheet_surprise_rate` | Decimal | Proportion of balance sheet announcements differing from announced pace, trailing 12 months |
| `composite_surprise_score` | Decimal | Weighted average of the three surprise rates |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | After next meeting for this central bank |

**Optional fields**: `scenario_analysis` (which specific meetings contributed most to surprise score)

**Consumers**: Knowledge Department (Evidence Weighter — informs confidence weighting of CBI-sourced evidence), Forecasting & Risk

---

### 1.10 PolicyPathAssessment

**Object name**: `PolicyPathAssessment`  
**Department code**: `CBI`  
**Update cadence**: Monthly; interim updates after materially-changing meetings  
**Time horizon**: T3 (12-month forward)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `central_bank` | Identifier | One of the 9 covered central banks |
| `base_case_path` | List of {quarter, expected_rate_bps} | Most likely policy rate path over next 12 months, in quarterly increments |
| `hawkish_scenario` | Map | {probability decimal, path list, trigger_conditions list} |
| `dovish_scenario` | Map | {probability decimal, path list, trigger_conditions list} |
| `market_implied_path_delta` | List of {quarter, cbi_rate_bps, market_implied_rate_bps, delta_bps} | Comparison of department's assessed path vs market-implied path. Positive delta = department sees higher rates than market. |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next scheduled meeting for that central bank, or next monthly refresh, whichever is sooner |

**Optional fields**: `confidence_distribution`, `cross_references` (to RatePathProjection for short-horizon consistency)

**Consumers**: Knowledge Department, Forecasting & Risk, Simulation

---

## 2. Cross-Asset Intelligence — Knowledge Contracts

The following contracts are implemented in `knowledge/cai/contracts.py`. Two additional contracts (RelativeValueAssessment, FlowPressure) are defined as frozen dataclasses with repository methods but have not yet completed evidence adapter or lifecycle testing — they are classified as Institutional Expansion.

### 2.1 CrossAssetCorrelation

**Object name**: `CrossAssetCorrelation`  
**Department code**: `CAI`  
**Event type**: `CAI_CORRELATION`  
**Evidence ID pattern**: `cai_corr_{asset_a}_{asset_b}`  

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `asset_class_a` | Identifier | First asset class (one of `VALID_ASSET_CLASSES`) |
| `asset_class_b` | Identifier | Second asset class |
| `correlation_coefficient` | Decimal | -1.0 to 1.0 correlation measurement |
| `lookback_periods` | Integer | Number of trading periods in the calculation window |
| `trend_direction` | Enum | positive, negative, diverging, converging, decoupling |
| `rolling_window` | Enum | short, medium, long |
| `regime_stability` | Decimal | 0.0–1.0 stability of the correlation regime |
| `confidence` | Decimal | 0.00–1.00 institutional scale |
| `valid_from` | Timestamp | Observation timestamp |
| `valid_until` | Timestamp | Next scheduled refresh |

**Base contract fields**: `provenance`, `evidence_references`, `cross_references`, `methodology_version`, `scenario_analysis`

**Adapter bias mapping**:
| Trend Direction | Evidence Bias |
|----------------|---------------|
| positive | neutral |
| negative | bearish |
| diverging | neutral |
| converging | neutral |
| decoupling | bearish |

**Consumers**: Knowledge Department (Evidence Repository, Regime Detection), Forecasting & Risk

---

### 2.2 SpreadAnalysis

**Object name**: `SpreadAnalysis`  
**Department code**: `CAI`  
**Event type**: `CAI_SPREAD`  
**Evidence ID pattern**: `cai_spread_{instrument_a}_{instrument_b}`  

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `instrument_a` | String | First instrument identifier |
| `instrument_b` | String | Second instrument identifier |
| `current_spread` | Decimal | Current spread value in basis points or percentage |
| `historical_mean` | Decimal | Historical mean spread over the reference window |
| `standard_deviation` | Decimal | Standard deviation of spread over the reference window |
| `z_score` | Decimal | Current z-score deviation from historical mean |
| `trend` | Enum | narrowing, widening, stable, inversion |
| `mean_reversion_signal` | Decimal | -1.0 to 1.0 strength of mean reversion signal |
| `confidence` | Decimal | 0.00–1.00 institutional scale |
| `valid_from` | Timestamp | Observation timestamp |
| `valid_until` | Timestamp | Next scheduled refresh |

**Base contract fields**: `provenance`, `evidence_references`, `cross_references`, `methodology_version`, `scenario_analysis`

**Adapter bias mapping**:
| Spread Trend | Evidence Bias |
|-------------|---------------|
| narrowing | bullish |
| widening | bearish |
| stable | neutral |
| inversion | bearish |

**Consumers**: Knowledge Department (Evidence Repository), Forecasting & Risk

---

### 2.3 RelativeValueAssessment

**Object name**: `RelativeValueAssessment`  
**Department code**: `CAI`  
**Status**: Institutional Expansion (contract defined, no adapter or lifecycle tests)  
**Event type**: `CAI_RELATIVE_VALUE` (planned)  

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `asset_class_a` | Identifier | First asset class |
| `asset_class_b` | Identifier | Second asset class |
| `relative_z_score` | Decimal | Z-score of relative performance between the two classes |
| `percentile_rank` | Decimal | 0.0–1.0 percentile rank of current relative value |
| `valuation_bias` | String | Directional bias from relative value perspective |
| `regime_consistency` | Decimal | 0.0–1.0 consistency of this valuation signal across regimes |
| `factor_exposures` | Map of string→decimal | FrozenDict of factor exposures (e.g., duration, credit) |
| `confidence` | Decimal | 0.00–1.00 institutional scale |
| `valid_from` | Timestamp | Observation timestamp |
| `valid_until` | Timestamp | Next scheduled refresh |

**Base contract fields**: `provenance`, `evidence_references`, `cross_references`, `methodology_version`, `scenario_analysis`

**Notes**: Adapter method and lifecycle tests pending. `factor_exposures` is auto-frozen to `FrozenDict` on construction.

---

### 2.4 FlowPressure

**Object name**: `FlowPressure`  
**Department code**: `CAI`  
**Status**: Institutional Expansion (contract defined, no adapter or lifecycle tests)  
**Event type**: `CAI_FLOW` (planned)  

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `asset_class` | Identifier | Target asset class |
| `direction` | Enum | inflow, outflow, rotation, stable |
| `intensity` | Decimal | 0.0–1.0 intensity of the flow signal |
| `volume_z_score` | Decimal | Z-score of current volume relative to normal |
| `momentum` | Enum | inflow, outflow, rotation, stable |
| `concentration` | Decimal | 0.0–1.0 concentration of flows across participants |
| `counterparty_risk` | List of string | Identified counterparty risks (optional) |
| `confidence` | Decimal | 0.00–1.00 institutional scale |
| `valid_from` | Timestamp | Observation timestamp |
| `valid_until` | Timestamp | Next scheduled refresh |

**Base contract fields**: `provenance`, `evidence_references`, `cross_references`, `methodology_version`, `scenario_analysis`

**Notes**: Adapter method and lifecycle tests pending.

---

### 2.5 VolatilityRegime

**Object name**: `VolatilityRegime`  
**Department code**: `CAI`  
**Event type**: `CAI_VOLATILITY`  
**Evidence ID pattern**: `cai_vol_{asset_class}`  

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `asset_class` | Identifier | Target asset class |
| `current_state` | Enum | low, moderate, elevated, high, extreme |
| `previous_state` | Enum | Same enum as current_state |
| `regime_persistence` | Decimal | 0.0–1.0 likelihood the current regime persists |
| `mean_reversion_half_life_days` | Decimal | Estimated half-life of volatility mean reversion in days |
| `tail_risk_index` | Decimal | 0.0–1.0 tail risk measurement |
| `regime_drivers` | List of string | Identified drivers of the current regime (optional) |
| `confidence` | Decimal | 0.00–1.00 institutional scale |
| `valid_from` | Timestamp | Observation timestamp |
| `valid_until` | Timestamp | Next scheduled refresh |

**Base contract fields**: `provenance`, `evidence_references`, `cross_references`, `methodology_version`, `scenario_analysis`

**Adapter bias mapping**:
| Volatility State | Evidence Bias |
|-----------------|---------------|
| low | bullish |
| moderate | neutral |
| elevated | bearish |
| high | bearish |
| extreme | bearish |

**Consumers**: Knowledge Department (Regime Detection — market-derived overlay), Forecasting & Risk, CFI (volatility context for flow positioning)

---

## 3. Capital Flow Intelligence — Knowledge Contracts

### 3.1 GoldPositioningDashboard

**Object name**: `GoldPositioningDashboard`  
**Department code**: `CFI`  
**Update cadence**: Daily  
**Time horizon**: T0 (current snapshot)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `cot_net_non_commercial` | Map | {position_contracts, percentile_5yr, 1wk_change, 4wk_change, 13wk_change} |
| `etf_flow` | Map | {4wk_cumulative_flow_usd, 4wk_flow_aum_pct, flow_trend, price_flow_divergence_flag} |
| `options_put_call_ratio` | Map | {25_delta_ratio, ratio_trend, interpretation} |
| `dealer_gamma_profile` | Map | {net_gamma_sign, key_strikes, amplification_regime} |
| `gold_lease_rate` | Decimal | Current lease rate in basis points |
| `shanghai_premium` | Decimal | Shanghai-London premium/discount in USD/oz |
| `institutional_gold_beta` | Decimal | Aggregate 13F institutional beta to gold (quarterly actual, estimated between releases) |
| `cta_sensitivity` | String | Summary of current CTA positioning sensitivity |
| `composite_assessment` | String | One-sentence composite reading of gold positioning |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next daily refresh |

**Optional fields**: `cross_references` (to CAI InstitutionalConfirmationMatrix, NI NarrativePositioningGapReport)

**Consumers**: Knowledge Department, Forecasting & Risk

---

### 3.2 COTPositioningReport

**Object name**: `COTPositioningReport`  
**Department code**: `CFI`  
**Update cadence**: Weekly (Friday release)  
**Time horizon**: T0-T2 (snapshot of positioning at report date, velocity over 1-13 weeks)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `report_date` | Date | The data date (typically Tuesday of release week) |
| `gold` | Map | {net_non_commercial, net_commercial, net_non_reportable, open_interest, non_commercial_pctile_5yr, 1wk_change_pctile, 4wk_change_pctile, 13wk_change_pctile} |
| `cross_market_coordination` | List of {market, non_commercial_net_position, pctile_5yr, coordination_score} | Gold vs silver, copper, oil, SPX, DXY, Treasuries |
| `category_divergence` | Map | {non_commercial_agreement boolean, divergence_direction string, divergence_intensity string} |
| `extreme_detection` | List of {metric, value, percentile, extreme_bound} | Any metric in the top or bottom decile of its 5-year range |
| `velocity_assessment` | String | Assessment of how quickly positioning changed and what that implies |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Report publication time |
| `valid_until` | Timestamp | Next COT release |

**Optional fields**: none

**Consumers**: Knowledge Department (as evidence), Forecasting & Risk, NI (positioning validation)

---

### 3.3 ETFFlowMonitor

**Object name**: `ETFFlowMonitor`  
**Department code**: `CFI`  
**Update cadence**: Daily data; weekly analytical report  
**Time horizon**: T1-T2 (1-13 week flow momentum)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `daily_flows` | List of {instrument, daily_flow_usd, 4wk_cumulative, 13wk_cumulative, flow_aum_pct, flow_direction} | Per-instrument flow data for all tracked gold ETFs |
| `momentum_assessment` | Enum | accelerating_inflows, steady_inflows, decelerating_inflows, neutral, accelerating_outflows, steady_outflows, decelerating_outflows |
| `price_flow_divergence_flag` | Boolean | True if 4-week flow direction and gold price direction are opposite |
| `composition_analysis` | Map | {primary_inflow_source, primary_outflow_source, non_us_share_pct, gld_vs_iau_ratio} |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next daily refresh |

**Optional fields**: `cross_references`

**Consumers**: Knowledge Department

---

### 3.4 CentralBankReserveFlowReport

**Object name**: `CentralBankReserveFlowReport`  
**Department code**: `CFI`  
**Update cadence**: Monthly  
**Time horizon**: T3-T4 (trend over 12 months; outlook 12 months)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `net_official_purchases_month` | Decimal | Tonnes purchased/sold in the reporting month |
| `net_official_purchases_12m` | Decimal | Rolling 12-month total in tonnes |
| `net_official_purchases_12m_trend` | Enum | accelerating, stable, decelerating |
| `marginal_buyers` | List of {central_bank, estimated_purchase_tonnes, probable_motivation} | Identified marginal buyers and their motivations |
| `pboc_track` | Map | {monthly_purchase_tonnes, purchase_pattern string, cumulative_holdings_tonnes} |
| `dedollarization_estimate` | Map | {usd_reserve_share_change, gold_reserve_share_change, observation_period} |
| `structural_demand_outlook` | Map | {12m_forecast_tonnes, confidence, primary_drivers list, primary_risks list} |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next monthly refresh |

**Optional fields**: `cross_references` (to CBI PolicyBiasScore for policy motivation context, CBI BalanceSheetOutlook for reserve composition context)

**Consumers**: Knowledge Department, Forecasting & Risk, Simulation, CBI (policy context co-validation), NI (structural narrative validation)

---

### 3.5 MarketStructureGammaProfile

**Object name**: `MarketStructureGammaProfile`  
**Department code**: `CFI`  
**Update cadence**: Gamma wall daily; full report weekly  
**Time horizon**: T0-T1 (current structure, 1-5 day forward)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `dealer_gamma` | Map | {net_gamma_sign, gamma_walls list of {strike, gamma_intensity, gamma_type}, amplification_regime boolean, key_support list of strike, key_resistance list of strike} |
| `cta_sensitivity` | Map | {estimated_net_position, direction, entry_triggers list of {price_level, estimated_volume}, exit_triggers list of {price_level, estimated_volume}} |
| `options_profile` | Map | {put_call_ratio, open_interest_concentration, implied_volatility_skew, max_pain_strike} |
| `physical_market` | Map | {lease_rate, shanghai_premium, forward_curve_basis, lbma_clearing_volume_trend} |
| `fragility_assessment` | String | Assessment of whether current structure amplifies or dampens price moves |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next daily (gamma) or weekly (full) refresh |

**Optional fields**: none

**Consumers**: Knowledge Department, Forecasting & Risk

---

### 3.6 SafeHavenFlowIndex

**Object name**: `SafeHavenFlowIndex`  
**Department code**: `CFI`  
**Update cadence**: Event-driven  
**Time horizon**: T0-T1 (stress episode duration)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `episode_active` | Boolean | Whether a stress episode is currently active |
| `asset_ranking_by_inflow` | List of {asset, inflow_magnitude, inflow_velocity} | Ranked by inflow magnitude: gold, Treasuries, CHF, JPY, USD cash |
| `marginal_buyer` | Map | {buyer_type, instrument_preference, estimated_share} |
| `migration_velocity` | Map | {day1_velocity, day2_velocity, day3_velocity, persistence_score decimal} |
| `gold_safe_haven_share` | Decimal | Percentage of total safe-haven flows captured by gold |
| `gold_share_trend` | Enum | increasing, stable, decreasing |
| `historical_comparison` | String | How this episode compares against the most similar historical episodes |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_until` | Timestamp | Episode closure report |

**Optional fields**: `cross_references` (to CAI SafeHavenRotationIndex for price-based confirmation)

**Consumers**: Knowledge Department, CAI (safe-haven flow confirmation)

---

### 3.7 DeDollarizationFlowIndex

**Object name**: `DeDollarizationFlowIndex`  
**Department code**: `CFI`  
**Update cadence**: Monthly  
**Time horizon**: T3-T4 (trailing 12 months, structural outlook)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `index_value` | Integer | -100 (maximum de-dollarization) to +100 (maximum re-dollarization). 0 = neutral. |
| `index_trend` | Enum | accelerating_dedollarization, stable_dedollarization, decelerating, neutral, re_dollarizing |
| `components` | Map of {component, current_value, weight_pct} | usd_reserve_share_change, foreign_official_treasury_change, central_bank_gold_change, china_treasury_trajectory, non_usd_reserve_share_change, bräs_reserve_signal |
| `assessment` | String | Qualitative assessment of what the index is indicating |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next monthly refresh |

**Optional fields**: `cross_references` (to CBI policy context for reserve motivation, NI DeDollarization narrative lifecycle)

**Consumers**: Knowledge Department, CBI (official-sector flow confirmation), Forecasting & Risk

---

### 3.8 SpeculativeFlowAsymmetryAssessment

**Object name**: `SpeculativeFlowAsymmetryAssessment`  
**Department code**: `CFI`  
**Update cadence**: Weekly  
**Time horizon**: T2 (current asymmetry, 1-4 week outlook)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `indicators` | List of {indicator_name, current_reading, available_space_pct, reversal_distance, interpretation} | Per-indicator analysis |
| `composite_asymmetry_score` | Decimal | 0.00 (maximum reversal risk — fully positioned) to 1.00 (maximum in-trend runway — room to add). Normalized from percentile rank. |
| `asymmetry_assessment` | String | Qualitative summary of whether risk/reward is favorable or unfavorable based on positioning |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next weekly refresh |

**Optional fields**: `cross_references` (to NI NarrativePositioningGapReport for the narrative overlay)

**Consumers**: Knowledge Department (Reasoning Engine — conviction calibration input)

---

### 3.9 InstitutionalAccumulationSignal

**Object name**: `InstitutionalAccumulationSignal`  
**Department code**: `CFI`  
**Update cadence**: Event-driven  
**Time horizon**: T1-T2 (expected accumulation horizon)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `signal_type` | Enum | accumulation, distribution |
| `triggered_indicators` | List of {indicator, value, threshold, triggered boolean} | Which detection thresholds were triggered |
| `flow_magnitude` | Map | {estimated_volume_usd, normalized_to_aum_pct, comparison_to_prior_events} |
| `likely_source` | Enum | hedge_fund, cta, central_bank, etf_investor, physical_buyer |
| `implied_price_impact` | String | Department's assessment of expected price impact direction and magnitude |
| `expected_duration` | String | Assessment of how long accumulation/distribution is expected to persist |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Alert issuance |
| `valid_until` | Timestamp | Signal resolved or superseded |

**Optional fields**: none

**Consumers**: Knowledge Department (high-priority evidence), Forecasting & Risk

---

### 3.10 LiquidityMigrationMap

**Object name**: `LiquidityMigrationMap`  
**Department code**: `CFI`  
**Update cadence**: Monthly  
**Time horizon**: T2-T3 (current cycle phase, 1-3 month outlook)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `flow_map` | List of {cluster, flow_direction, flow_intensity} | Clusters: cash_money_markets, short_term_bonds, long_term_bonds, equities, credit, commodities, gold, real_estate, alternatives. Direction: inflow, outflow, neutral. Intensity: strong, moderate, marginal. |
| `cycle_phase` | Enum | Early_Expansion, Mid_Expansion, Late_Expansion, Early_Contraction, Mid_Contraction, Late_Contraction |
| `cycle_phase_confidence` | Decimal | 0.00 – 1.00 |
| `gold_position` | String | Gold's specific position within the current cycle phase |
| `previous_phase` | String | The prior cycle phase, for trajectory context |
| `comparison_to_historical` | String | How the current cycle compares to historical precedents |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next monthly refresh |

**Optional fields**: `cross_references` (to CBI LiquidityOutlook for central bank liquidity context, CAI LiquidityRotationMap for price-based rotation confirmation)

**Consumers**: Knowledge Department, CAI (flow-based rotation confirmation), Forecasting & Risk

---

## 4. Narrative Intelligence — Knowledge Contracts

### 4.1 NarrativeStrengthDashboard

**Object name**: `NarrativeStrengthDashboard`  
**Department code**: `NI`  
**Update cadence**: Daily  
**Time horizon**: T0 (current snapshot), T1-T2 (trailing 1-4 week trends)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `narratives` | List of {narrative_id, strength_score, strength_trend, lifecycle_phase, 1wk_change, 4wk_change, confirmation_score, conflict_flag, gold_relevance} | Per-narrative snapshot |
| `lifecycle_phases` | Map of {narrative_id, phase} | Enum: Emergence, Adoption, Consensus, Exhaustion, Persistence |
| `gold_relevant_narratives` | List of narrative_id | Subset of narratives flagged as currently gold-relevant |
| `landscape_summary` | String | One-sentence characterization of the current narrative environment |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next daily refresh |

**Optional fields**: none

**Consumers**: Knowledge Department, All Intelligence Departments

---

### 4.2 NarrativeConflictMatrix

**Object name**: `NarrativeConflictMatrix`  
**Department code**: `NI`  
**Update cadence**: Weekly; interim updates on conflict changes >1 point  
**Time horizon**: T0 (current conflict state)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `conflict_matrix` | 15x15 matrix of integers | 0 (no conflict) to 10 (direct factual contradiction) for each narrative pair |
| `aggregate_conflict_index` | Decimal | Average conflict intensity across all active pairs |
| `aggregate_conflict_trend` | Enum | intensifying, stable, resolving |
| `top_conflicts` | List of {pair, intensity, type, resolution_assessment} | Top 3 most intense active conflicts with resolution analysis |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next weekly refresh or interim update |

**Optional fields**: none

**Consumers**: Knowledge Department, Forecasting & Risk (confidence interval calibration)

---

### 4.3 NarrativePositioningGapReport

**Object name**: `NarrativePositioningGapReport`  
**Department code**: `NI`  
**Update cadence**: Weekly  
**Time horizon**: T0 (current gap), T2 (1-4 week outlook)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `narratives` | List of {narrative_id, narrative_strength, positioning_implementation_score, quadrant, assessment} | Per-narrative gap analysis |
| `quadrant_breakdown` | Map of {quadrant, count, narratives list} | Quadrant: HighNarrative_HighPositioning, HighNarrative_LowPositioning, LowNarrative_HighPositioning, LowNarrative_LowPositioning |
| `opportunity_quadrant` | List of narrative_id | Narratives in HighNarrative_LowPositioning — most actionable for institutional conviction |
| `risk_quadrant` | List of narrative_id | Narratives in HighNarrative_HighPositioning — most vulnerable to reversal |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next weekly refresh |

**Optional fields**: `cross_references` (to CFI SpeculativeFlowAsymmetryAssessment and GoldPositioningDashboard)

**Consumers**: Knowledge Department, CFI (narrative overlay to positioning assessment)

---

### 4.4 NarrativeRegimeAssessment

**Object name**: `NarrativeRegimeAssessment`  
**Department code**: `NI`  
**Update cadence**: Monthly  
**Time horizon**: T2-T3 (current regime, 1-3 month outlook)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `dominant_narrative` | Map | {narrative_id, strength_score, lifecycle_phase, rationale} |
| `regime_characterization` | Enum | Coherent_single_story, Fragmented_competing_stories, Unstable_transition, Structural_acceptance |
| `lifecycle_assessments` | List of {narrative_id, phase, runway_assessment} | Lifecycle position and remaining runway for each tracked narrative |
| `transition_scenarios` | List of {target_narrative, probability, trigger_catalyst, timeframe, asset_price_implications} | Top 3 most probable regime transitions |
| `cross_department_coherence` | Decimal | Cross-Department Narrative Coherence Score value (Product 14.9) |
| `coherence_analysis` | String | If coherence < 40, fracture analysis. Otherwise, confirmation. |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next monthly refresh |

**Optional fields**: `cross_references` (to CBI GlobalMonetaryRegime, CAI CrossAssetRegimeAssessment)

**Consumers**: Knowledge Department, All Intelligence Departments, Forecasting & Risk

---

### 4.5 NarrativeDataGapAlert

**Object name**: `NarrativeDataGapAlert`  
**Department code**: `NI`  
**Update cadence**: Event-driven  
**Time horizon**: T1 (7-14 days before data release)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `narrative_at_risk` | Narrative identifier | Which narrative is about to be tested |
| `testing_event` | String | The data release or policy event |
| `event_date` | Date | Expected date of the testing event |
| `narrative_claim` | String | The specific claim the narrative is making that the event will test |
| `expected_outcome` | String | The department's objective expected data outcome |
| `narrative_confirms_impact` | String | Market impact if data confirms the narrative |
| `narrative_contradicts_impact` | String | Market impact if data contradicts the narrative |
| `gold_impact_scenarios` | Map | {confirms_scenario: gold_direction_estimate, contradicts_scenario: gold_direction_estimate, confidence} |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Alert issuance |
| `valid_until` | Timestamp | 24 hours after the testing event |

**Optional fields**: none

**Consumers**: Knowledge Department, Forecasting & Risk

---

### 4.6 NarrativeCollapseWarning

**Object name**: `NarrativeCollapseWarning`  
**Department code**: `NI`  
**Update cadence**: Event-driven; daily updates while active  
**Time horizon**: T0-T1 (collapse underway or imminent)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `narrative` | Narrative identifier | The narrative experiencing or approaching collapse |
| `decay_score` | Integer | 0-100. Current decay score (0 = no decay, 100 = imminent collapse). |
| `collapse_trigger` | String | The trigger event, if already materialized. "Pre-emptive warning" if issued before trigger. |
| `collapse_velocity` | Enum | hours, days, weeks |
| `positioning_vulnerability` | String | Assessment of how much capital is at risk of forced unwinding |
| `successor_narrative` | String | Most likely narrative to replace the collapsing one |
| `gold_implication` | String | What the collapse means for gold |
| `warning_status` | Enum | pre_emptive, active, updating, withdrawn |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Warning issuance |
| `valid_until` | Timestamp | Collapse resolved or warning withdrawn |

**Optional fields**: `cross_references`

**Consumers**: Knowledge Department (high-priority evidence), Forecasting & Risk

---

### 4.7 SellSideConsensusIndex

**Object name**: `SellSideConsensusIndex`  
**Department code**: `NI`  
**Update cadence**: Weekly  
**Time horizon**: T0 (current consensus snapshot)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `gold_analyst_consensus` | Decimal | 0.00 (all sell) to 1.00 (all buy). Composite of buy/hold/sell ratings for gold-equity analysts. |
| `gold_target_dispersion` | Decimal | 0.00 (no dispersion — all targets identical) to 1.00 (maximum dispersion). |
| `macro_house_consensus` | Map | {bullish_share, neutral_share, bearish_share} |
| `composite_score` | Decimal | Average of gold_analyst_consensus, (1 - gold_target_dispersion), and macro_house_consensus (mapped to 0-1). |
| `consensus_confirmation_gap` | Map | {ni_narrative_strength, sell_side_consensus, gap, interpretation} |
| `consensus_trend` | Enum | becoming_more_bullish, stable_bullish, becoming_more_bearish, stable_bearish, mixed |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next weekly refresh |

**Optional fields**: none

**Consumers**: Knowledge Department (Evidence Repository), CFI (consensus context for positioning)

---

### 4.8 NarrativeImpactDecomposition

**Object name**: `NarrativeImpactDecomposition`  
**Department code**: `NI`  
**Update cadence**: Monthly  
**Time horizon**: T2 (trailing month decomposition)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `observation_month` | Year-month | The month being decomposed |
| `actual_gold_return` | Decimal | Gold return in percent for the observation month |
| `fundamental_contribution` | Map | {real_yields, dxy, cpi, pce, other, total} — estimated contribution in basis points |
| `positioning_contribution` | Map | {cot_extreme, etf_momentum, other, total} — estimated contribution in basis points |
| `narrative_contribution` | Map | {narrative_id: contribution_bps, aggregate_narrative_total} — per-narrative contribution |
| `unexplained_residual` | Decimal | Gold return not explained by the model |
| `narrative_share_of_return` | Decimal | Proportion of gold return attributable to narrative factors |
| `interpretation` | String | What the decomposition implies about gold's current price structure |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next monthly decomposition |

**Optional fields**: none

**Consumers**: Knowledge Department, Forecasting & Risk

---

### 4.9 CrossDepartmentNarrativeCoherenceScore

**Object name**: `CrossDepartmentNarrativeCoherenceScore`  
**Department code**: `NI`  
**Update cadence**: Weekly  
**Time horizon**: T0 (current coherence snapshot)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `coherence_score` | Integer | 0 (maximum fracture, all departments identify different narratives) to 100 (maximum coherence, all departments identify the same narrative) |
| `coherence_trend` | Enum | improving, stable, deteriorating |
| `department_narratives` | Map of {department, dominant_narrative, evidence_basis} | CBI policy narrative, CAI price narrative, CFI positioning narrative, NI discourse narrative |
| `consistent_pairs` | List of {department_pair, agreement_level} | Pairwise agreement between departments |
| `fracture_analysis` | String | Only present when coherence < 40. Describes where the fractures are and what they imply. |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next weekly refresh |

**Optional fields**: none

**Consumers**: All Intelligence Departments, Knowledge Department

---

### 4.10 NarrativeCatalystCalendar

**Object name**: `NarrativeCatalystCalendar`  
**Department code**: `NI`  
**Update cadence**: Weekly; reviewed daily  
**Time horizon**: T1-T2 (4-week forward)

**Mandatory fields**:

| Field | Type | Definition |
|-------|------|------------|
| `week_start` | Date | First day of the calendar week |
| `events` | List of {event_date, event_name, event_type, affected_narratives list, narrative_claim string, expected_outcome string, impact_if_confirms string, impact_if_contradicts string, probability_weighted_outcome string, gold_impact_severity enum} | All tracked events for the week |
| `high_impact_events` | List of event_name | Subset of events with maximum expected gold impact |
| `summary` | String | One-paragraph summary of the week's key narrative catalysts |
| `confidence` | Decimal | 0.00 – 1.00 |
| `valid_from` | Timestamp | Publication timestamp |
| `valid_until` | Timestamp | Next weekly refresh |

**Optional fields**: none

**Consumers**: Knowledge Department, Forecasting & Risk, All Intelligence Departments

---

## 5. Cross-Department Knowledge Object Dependencies

The following table maps every knowledge object to every other knowledge object that it references in its `cross_references` optional field, or that a consumer of the object is expected to cross-reference against in normal institutional operation.

| Producing Object | Cross-References To | Semantics |
|-----------------|--------------------|-----------|
| CBI:GlobalMonetaryRegime | CAI:CrossAssetRegimeAssessment | Fundamental vs market-derived regime cross-validation |
| CBI:LiquidityOutlook | CAI:LiquidityRotationMap, CFI:LiquidityMigrationMap | Three-way liquidity assessment reconciliation |
| CBI:CentralBankSurpriseIndex | All CBI objects | Surprise index informs confidence weighting of all CBI-sourced evidence |
| CBI:PolicyPathAssessment | CBI:RatePathProjection | Short-horizon and long-horizon consistency check |
| CAI:CrossAssetRegimeAssessment | CBI:GlobalMonetaryRegime, CFI:LiquidityMigrationMap | Three-way regime cross-validation (policy, price, flow) |
| CAI:SafeHavenRotationIndex | CFI:SafeHavenFlowIndex | Price-based vs flow-based safe-haven confirmation |
| CAI:LiquidityRotationMap | CBI:LiquidityOutlook, CFI:LiquidityMigrationMap | Three-way liquidity reconciliation |
| CFI:GoldPositioningDashboard | CAI:InstitutionalConfirmationMatrix, NI:NarrativePositioningGapReport | Positioning + confirmation + narrative composite |
| CFI:CentralBankReserveFlowReport | CBI:PolicyBiasScore, CBI:BalanceSheetOutlook | Policy context for official-sector flow interpretation |
| CFI:DeDollarizationFlowIndex | CBI: policy context, NI:NarrativeStrengthDashboard | Flow measurement + policy motivation + narrative lifecycle |
| CFI:SafeHavenFlowIndex | CAI:SafeHavenRotationIndex | Flow-based vs price-based safe-haven confirmation |
| CFI:LiquidityMigrationMap | CBI:LiquidityOutlook, CAI:LiquidityRotationMap | Three-way liquidity reconciliation |
| CFI:SpeculativeFlowAsymmetryAssessment | NI:NarrativePositioningGapReport | Positioning asymmetry vs narrative positioning gap |
| NI:NarrativeRegimeAssessment | CBI:GlobalMonetaryRegime, CAI:CrossAssetRegimeAssessment | Three-way regime assessment (policy, price, narrative) |
| NI:NarrativePositioningGapReport | CFI:SpeculativeFlowAsymmetryAssessment, CFI:GoldPositioningDashboard | Narrative vs positioning cross-reference |
| NI:CrossDepartmentNarrativeCoherenceScore | CBI, CAI, CFI dominant narratives | Departmental narrative agreement measurement |

---

## 6. Contract Compliance Rules

The following rules govern all institutional knowledge contracts and must not be violated by any implementation.

**Rule 1 — Common fields must never be removed**: The fields specified in Sections 0.2 through 0.7 (confidence, provenance, evidence_references, valid_from, valid_until, time_horizon) are mandatory on every knowledge object. No department may omit them.

**Rule 2 — Mandatory fields must always be populated**: Fields specified as mandatory in Sections 1-4 must never be null, empty, or absent. If a department cannot produce a mandatory field, the containing knowledge object must not be published.

**Rule 3 — Optional fields may be omitted but must not change semantics**: If an optional field is present, its semantics must match the specification in this document. Optional fields may not be repurposed.

**Rule 4 — Confidence must use the institutional scale**: The 0.00-1.00 scale with its six labels (Speculative through Near-Certain) is the only authorized confidence representation. No department may introduce an alternative confidence scale.

**Rule 5 — Validity periods must be set correctly**: `valid_until` must be set to a date no later than the next scheduled update of the same object type. If no next update is scheduled (e.g., for event-driven objects), `valid_until` must be set to the expected date when the underlying observation becomes stale.

**Rule 6 — Consumer contracts are additive**: A department may add consumers beyond those listed in Sections 1-4, but must never remove a consumer listed here without Architecture Council approval. Any new consumer must have a documented institutional use case.

**Rule 7 — Object names must not change**: The knowledge object names specified in Sections 1-4 are permanent. No name may be changed, deprecated, or reassigned.

**Rule 8 — Field semantics must not change**: The definition of each mandatory and optional field is permanent. A field's meaning must not be reinterpreted or extended beyond this specification.

**Rule 9 — Cross-references must be resolvable**: Any knowledge object ID appearing in a `cross_references` field must correspond to a published knowledge object that exists at the time of reference. Dead references are not permitted.

**Rule 10 — New knowledge objects require Architecture Council approval**: Any new institutional knowledge object not listed in this document must be approved by the Architecture Council before publication. This rule applies to all four Tier-1 departments.

---

## 7. Contract Change Procedure

Proposed changes to this document follow a defined procedure:

1. **Initiation**: A department head proposes a change, specifying the exact contract element to be modified, the proposed new specification, and the institutional rationale.

2. **Impact Assessment**: The proposing department identifies all knowledge objects that reference the affected contract element, all consumers that depend on it, and the estimated cost of migration.

3. **Review**: The Architecture Council reviews the proposal. Review criteria include: backward compatibility, migration cost, effect on institutional coherence, and consistency with the common contract framework.

4. **Approval**: Changes are approved by majority of the Architecture Council. Changes affecting the common contract framework (Section 0) require unanimous approval.

5. **Migration**: After approval, the change is implemented. An implementation transition period is specified during which both old and new contract forms may be active.

6. **Archive**: The superseded contract specification is archived with its effective date range.

---

*Institutional Knowledge Contracts — Permanent Reference*  
*AurumAI Institutional Architecture*
