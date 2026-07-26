from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import Provenance

EQUITIES = "equities"
FIXED_INCOME = "fixed_income"
FX = "fx"
COMMODITIES = "commodities"
CREDIT = "credit"
RATES = "rates"
VOLATILITY = "volatility"
REAL_ESTATE = "real_estate"
CRYPTO = "crypto"
EM = "em"

VALID_ASSET_CLASSES = frozenset({
    EQUITIES, FIXED_INCOME, FX, COMMODITIES, CREDIT,
    RATES, VOLATILITY, REAL_ESTATE, CRYPTO, EM,
})

CORRELATION_POSITIVE = "positive"
CORRELATION_NEGATIVE = "negative"
CORRELATION_DIVERGING = "diverging"
CORRELATION_CONVERGING = "converging"
CORRELATION_DECOUPLING = "decoupling"
VALID_CORRELATION_DIRECTIONS = frozenset({
    CORRELATION_POSITIVE, CORRELATION_NEGATIVE,
    CORRELATION_DIVERGING, CORRELATION_CONVERGING,
    CORRELATION_DECOUPLING,
})

VOL_LOW = "low"
VOL_MODERATE = "moderate"
VOL_ELEVATED = "elevated"
VOL_HIGH = "high"
VOL_EXTREME = "extreme"
VALID_VOLATILITY_STATES = frozenset({
    VOL_LOW, VOL_MODERATE, VOL_ELEVATED, VOL_HIGH, VOL_EXTREME,
})

FLOW_INFLOW = "inflow"
FLOW_OUTFLOW = "outflow"
FLOW_ROTATION = "rotation"
FLOW_STABLE = "stable"
VALID_FLOW_DIRECTIONS = frozenset({
    FLOW_INFLOW, FLOW_OUTFLOW, FLOW_ROTATION, FLOW_STABLE,
})

WINDOW_SHORT = "short"
WINDOW_MEDIUM = "medium"
WINDOW_LONG = "long"
VALID_TIME_WINDOWS = frozenset({WINDOW_SHORT, WINDOW_MEDIUM, WINDOW_LONG})

SPREAD_NARROWING = "narrowing"
SPREAD_WIDENING = "widening"
SPREAD_STABLE = "stable"
SPREAD_INVERSION = "inversion"
VALID_SPREAD_TRENDS = frozenset({
    SPREAD_NARROWING, SPREAD_WIDENING, SPREAD_STABLE, SPREAD_INVERSION,
})


@dataclass(frozen=True)
class CaiBaseContract:
    confidence: float = 0.0
    valid_from: str = ""
    valid_until: str = ""
    time_horizon: str = ""
    provenance: Provenance | None = None
    evidence_references: list = field(default_factory=list)
    cross_references: list | None = None
    methodology_version: str | None = None
    scenario_analysis: list | None = None


@dataclass(frozen=True)
class CrossAssetCorrelation(CaiBaseContract):
    asset_class_a: str = ""
    asset_class_b: str = ""
    correlation_coefficient: float = 0.0
    lookback_periods: int = 0
    trend_direction: str = CORRELATION_CONVERGING
    rolling_window: str = WINDOW_MEDIUM
    regime_stability: float = 0.0


@dataclass(frozen=True)
class SpreadAnalysis(CaiBaseContract):
    instrument_a: str = ""
    instrument_b: str = ""
    current_spread: float = 0.0
    historical_mean: float = 0.0
    standard_deviation: float = 0.0
    z_score: float = 0.0
    trend: str = SPREAD_STABLE
    mean_reversion_signal: float = 0.0


@dataclass(frozen=True)
class RelativeValueAssessment(CaiBaseContract):
    asset_class_a: str = ""
    asset_class_b: str = ""
    relative_z_score: float = 0.0
    percentile_rank: float = 0.0
    valuation_bias: str = "neutral"
    regime_consistency: float = 0.0
    factor_exposures: dict = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "factor_exposures", freeze_dict(self.factor_exposures))


@dataclass(frozen=True)
class FlowPressure(CaiBaseContract):
    asset_class: str = ""
    direction: str = FLOW_STABLE
    intensity: float = 0.0
    volume_z_score: float = 0.0
    momentum: str = FLOW_STABLE
    concentration: float = 0.0
    counterparty_risk: list | None = None


@dataclass(frozen=True)
class VolatilityRegime(CaiBaseContract):
    asset_class: str = ""
    current_state: str = VOL_MODERATE
    previous_state: str = VOL_MODERATE
    regime_persistence: float = 0.0
    mean_reversion_half_life_days: float = 0.0
    tail_risk_index: float = 0.0
    regime_drivers: list | None = None
