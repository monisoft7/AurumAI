from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import Provenance

# ———————————————————————————————————————
# Factor Categories
# ———————————————————————————————————————

CATEGORY_MONETARY_POLICY = "monetary_policy"
CATEGORY_CENTRAL_BANK = "central_bank"
CATEGORY_MACROECONOMIC = "macroeconomic"
CATEGORY_US_DOLLAR = "us_dollar"
CATEGORY_GEOPOLITICAL = "geopolitical"
CATEGORY_MARKET_STRUCTURE = "market_structure"
CATEGORY_INFLATION = "inflation"
CATEGORY_REAL_YIELDS = "real_yields"
CATEGORY_INVESTMENT_FLOWS = "investment_flows"
CATEGORY_SUPPLY_DEMAND = "supply_demand"
CATEGORY_ENERGY_COMMODITIES = "energy_commodities"
CATEGORY_RISK_SENTIMENT = "risk_sentiment"
CATEGORY_SEASONALITY = "seasonality"
CATEGORY_TECHNICAL = "technical"
CATEGORY_REGULATORY = "regulatory"
CATEGORY_DEMOGRAPHIC = "demographic"
CATEGORY_DIGITAL_COMPETITION = "digital_competition"
CATEGORY_STRUCTURAL_REGIME = "structural_regime"

VALID_CATEGORIES = frozenset({
    CATEGORY_MONETARY_POLICY,
    CATEGORY_CENTRAL_BANK,
    CATEGORY_MACROECONOMIC,
    CATEGORY_US_DOLLAR,
    CATEGORY_GEOPOLITICAL,
    CATEGORY_MARKET_STRUCTURE,
    CATEGORY_INFLATION,
    CATEGORY_REAL_YIELDS,
    CATEGORY_INVESTMENT_FLOWS,
    CATEGORY_SUPPLY_DEMAND,
    CATEGORY_ENERGY_COMMODITIES,
    CATEGORY_RISK_SENTIMENT,
    CATEGORY_SEASONALITY,
    CATEGORY_TECHNICAL,
    CATEGORY_REGULATORY,
    CATEGORY_DEMOGRAPHIC,
    CATEGORY_DIGITAL_COMPETITION,
    CATEGORY_STRUCTURAL_REGIME,
})

# ———————————————————————————————————————
# Tiers (from Gold Influence Map hierarchy)
# ———————————————————————————————————————

TIER_1 = 1  # Regime-defining (score 8–10)
TIER_2 = 2  # Strong (score 6–7)
TIER_3 = 3  # Moderate (score 4–5)
TIER_4 = 4  # Marginal (score ≤3)

VALID_TIERS = frozenset({TIER_1, TIER_2, TIER_3, TIER_4})

# ———————————————————————————————————————
# Influence Bias
# ———————————————————————————————————————

BIAS_BULLISH = "bullish"
BIAS_BEARISH = "bearish"
BIAS_NEUTRAL = "neutral"

VALID_BIASES = frozenset({BIAS_BULLISH, BIAS_BEARISH, BIAS_NEUTRAL})

# ———————————————————————————————————————
# Time Horizons (institutional standard)
# ———————————————————————————————————————

HORIZON_T0 = "T0"  # Event / now
HORIZON_T1 = "T1"  # 1–5 trading days
HORIZON_T2 = "T2"  # 1–4 weeks
HORIZON_T3 = "T3"  # 1–12 months
HORIZON_T4 = "T4"  # 1+ years

VALID_TIME_HORIZONS = frozenset({
    HORIZON_T0, HORIZON_T1, HORIZON_T2, HORIZON_T3, HORIZON_T4,
})

# ———————————————————————————————————————
# Signal Direction (factor movement)
# ———————————————————————————————————————

DIRECTION_RISING = "rising"
DIRECTION_FALLING = "falling"
DIRECTION_STABLE = "stable"
DIRECTION_UNKNOWN = "unknown"

VALID_DIRECTIONS = frozenset({
    DIRECTION_RISING, DIRECTION_FALLING, DIRECTION_STABLE, DIRECTION_UNKNOWN,
})

# ———————————————————————————————————————
# Influence Mechanism
# ———————————————————————————————————————

MECHANISM_OPPORTUNITY_COST = "opportunity_cost"
MECHANISM_SAFE_HAVEN = "safe_haven"
MECHANISM_INFLATION_HEDGE = "inflation_hedge"
MECHANISM_CURRENCY_SUBSTITUTION = "currency_substitution"
MECHANISM_PORTFOLIO_DIVERSIFICATION = "portfolio_diversification"
MECHANISM_MONETARY_PREMIUM = "monetary_premium"
MECHANISM_CENTRAL_BANK_DEMAND = "central_bank_demand"
MECHANISM_INVESTMENT_DEMAND = "investment_demand"
MECHANISM_JEWELLERY_DEMAND = "jewellery_demand"
MECHANISM_INDUSTRIAL_DEMAND = "industrial_demand"
MECHANISM_SPECULATIVE_POSITIONING = "speculative_positioning"
MECHANISM_SUPPLY_CONSTRAINT = "supply_constraint"
MECHANISM_REGIME_SHIFT = "regime_shift"
MECHANISM_NARRATIVE = "narrative"

VALID_MECHANISMS = frozenset({
    MECHANISM_OPPORTUNITY_COST,
    MECHANISM_SAFE_HAVEN,
    MECHANISM_INFLATION_HEDGE,
    MECHANISM_CURRENCY_SUBSTITUTION,
    MECHANISM_PORTFOLIO_DIVERSIFICATION,
    MECHANISM_MONETARY_PREMIUM,
    MECHANISM_CENTRAL_BANK_DEMAND,
    MECHANISM_INVESTMENT_DEMAND,
    MECHANISM_JEWELLERY_DEMAND,
    MECHANISM_INDUSTRIAL_DEMAND,
    MECHANISM_SPECULATIVE_POSITIONING,
    MECHANISM_SUPPLY_CONSTRAINT,
    MECHANISM_REGIME_SHIFT,
    MECHANISM_NARRATIVE,
})

# ———————————————————————————————————————
# Data Quality
# ———————————————————————————————————————

QUALITY_HIGH = "high"
QUALITY_MODERATE = "moderate"
QUALITY_LOW = "low"
QUALITY_STALE = "stale"
QUALITY_ESTIMATED = "estimated"

VALID_DATA_QUALITIES = frozenset({
    QUALITY_HIGH, QUALITY_MODERATE, QUALITY_LOW, QUALITY_STALE, QUALITY_ESTIMATED,
})

# ———————————————————————————————————————
# Dependency Type
# ———————————————————————————————————————

DEPENDENCY_DIRECT = "direct"
DEPENDENCY_INDIRECT = "indirect"
DEPENDENCY_REGIME_MODULATED = "regime_modulated"
DEPENDENCY_LAGGED = "lagged"

VALID_DEPENDENCY_TYPES = frozenset({
    DEPENDENCY_DIRECT, DEPENDENCY_INDIRECT,
    DEPENDENCY_REGIME_MODULATED, DEPENDENCY_LAGGED,
})

# ———————————————————————————————————————
# Contracts
# ———————————————————————————————————————


@dataclass(frozen=True)
class FactorBase:
    """Common institutional fields for all factor contracts.

    Every factor contract carries these fields implicitly, exactly
    matching the pattern established by CbiBaseContract and
    CaiBaseContract in the existing architecture.
    """
    confidence: float = 0.0
    valid_from: str = ""
    valid_until: str = ""
    time_horizon: str = HORIZON_T0
    provenance: Provenance | None = None
    evidence_references: list = field(default_factory=list)
    cross_references: list | None = None
    methodology_version: str | None = None
    scenario_analysis: list | None = None


@dataclass(frozen=True)
class GoldFactorDefinition:
    """Immutable identity of a gold influence factor.

    This is the canonical registry entry for every factor in the
    Gold Influence Map. It is defined once and never mutated.
    Every FactorSignal refers back to a GoldFactorDefinition
    via its factor_id.

    Why separate from FactorSignal:
    — A factor's identity (name, category, tier) is static metadata
    — Its reading and influence assessment are dynamic, time-bound data
    — Separating avoids duplicating static metadata in every observation
    — Enables a factor catalog / registry pattern
    """
    factor_id: str
    name: str
    category: str = ""
    tier: int = TIER_3
    description: str = ""
    unit: str = ""
    typical_frequency: str = ""
    source_descriptor: str = ""
    mechanism: str = ""
    relationship: str = ""
    depends_on: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))


@dataclass(frozen=True)
class FactorSignal(FactorBase):
    """A time-bound observation of a factor's value and its assessed
    influence on gold.

    This is the primary publishing contract — every department (CBI, CFI,
    Geopolitical, Macro, Energy, etc.) publishes its gold-relevant
    intelligence as FactorSignal instances.

    Combines three concerns into one atomic contract:
    1. What was observed (value, direction, z-score)
    2. How it influences gold (bias, strength, mechanism)
    3. How reliable it is (confidence, data_quality)

    Fields:
        factor_id: References a GoldFactorDefinition.
        observation_date: When the raw data was captured.
        value: The measured value of the factor.
        z_score: Standard deviations from historical mean.
        percentile: 0–1 percentile rank vs history.
        direction: Is the factor rising, falling, or stable?
        influence_bias: Net directional effect on gold.
        influence_strength: Magnitude -1.0 (max bearish) to +1.0 (max bullish).
        mechanism: How this factor transmits to gold price.
        data_quality: Freshness / reliability of the underlying data.
        regime_sensitivity: Optional map of regime → bias overrides.
    """
    factor_id: str = ""
    observation_date: str = ""
    value: float = 0.0
    z_score: float = 0.0
    percentile: float = 0.0
    direction: str = DIRECTION_UNKNOWN
    influence_bias: str = BIAS_NEUTRAL
    influence_strength: float = 0.0
    mechanism: str = ""
    data_quality: str = QUALITY_MODERATE
    regime_sensitivity: dict = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "regime_sensitivity",
            freeze_dict(self.regime_sensitivity),
        )


@dataclass(frozen=True)
class FactorInteraction:
    """Recorded pairwise relationship between two gold influence factors.

    Why this exists:
    — The Gold Influence Map documents explicit interactions between factors
      (e.g., Real Yields × DXY, Central Bank Purchases × Sanctions)
    — Some interactions are regime-dependent (only active in certain regimes)
    — Enables downstream reasoning about offsetting / reinforcing signals

    Fields:
        factor_a_id, factor_b_id: References to GoldFactorDefinition.
        correlation: Recent empirical correlation.
        interaction_type: How they interact (direct, indirect, regime_modulated).
        regime_stability: 0–1, how stable the interaction is across regimes.
        description: Human-readable explanation of the interaction.
        active_regimes: If regime_modulated, which regimes activate this.
    """
    factor_a_id: str = ""
    factor_b_id: str = ""
    correlation: float = 0.0
    interaction_type: str = DEPENDENCY_INDIRECT
    regime_stability: float = 0.0
    description: str = ""
    active_regimes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))


@dataclass(frozen=True)
class CompositeInfluence(FactorBase):
    """Aggregate view of all active gold factor influences at a point in time.

    This is the output consumed by reasoning, forecasting, and decision
    layers. It provides a single composite picture of what is driving
    gold and with what conviction.

    Why this exists:
    — Decision and reasoning engines need a consolidated view, not raw signals
    — Enables composite opinion formation (weighted by tier × confidence
      × regime_appropriateness)
    — Carries its own confidence based on signal agreement / dispersion

    Fields:
        observation_date: Point in time this composite represents.
        composite_bias: Net directional bias.
        composite_strength: Magnitude -1.0 to +1.0.
        signal_count: Number of FactorSignals that fed this composite.
        contributing_factors: List of factor_ids ordered by contribution.
        top_bullish: Top N bullish factor_ids.
        top_bearish: Top N bearish factor_ids.
        dominant_regime: The macro regime context.
        signal_dispersion: 0–1 measure of agreement among signals.
    """
    observation_date: str = ""
    composite_bias: str = BIAS_NEUTRAL
    composite_strength: float = 0.0
    signal_count: int = 0
    contributing_factors: tuple[str, ...] = ()
    top_bullish: tuple[str, ...] = ()
    top_bearish: tuple[str, ...] = ()
    dominant_regime: str = ""
    signal_dispersion: float = 0.0
    factor_summary: dict = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "factor_summary",
            freeze_dict(self.factor_summary),
        )
