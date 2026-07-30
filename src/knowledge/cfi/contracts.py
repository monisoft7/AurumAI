from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import Provenance

MOMENTUM_ACCELERATING_INFLOWS = "accelerating_inflows"
MOMENTUM_STEADY_INFLOWS = "steady_inflows"
MOMENTUM_DECELERATING_INFLOWS = "decelerating_inflows"
MOMENTUM_NEUTRAL = "neutral"
MOMENTUM_ACCELERATING_OUTFLOWS = "accelerating_outflows"
MOMENTUM_STEADY_OUTFLOWS = "steady_outflows"
MOMENTUM_DECELERATING_OUTFLOWS = "decelerating_outflows"
VALID_MOMENTUM_ASSESSMENTS = frozenset({
    MOMENTUM_ACCELERATING_INFLOWS, MOMENTUM_STEADY_INFLOWS,
    MOMENTUM_DECELERATING_INFLOWS, MOMENTUM_NEUTRAL,
    MOMENTUM_ACCELERATING_OUTFLOWS, MOMENTUM_STEADY_OUTFLOWS,
    MOMENTUM_DECELERATING_OUTFLOWS,
})

TREND_ACCELERATING = "accelerating"
TREND_STABLE = "stable"
TREND_DECELERATING = "decelerating"
VALID_TRENDS = frozenset({TREND_ACCELERATING, TREND_STABLE, TREND_DECELERATING})

FLOW_INFLOW = "inflow"
FLOW_OUTFLOW = "outflow"
VALID_FLOW_DIRECTIONS = frozenset({FLOW_INFLOW, FLOW_OUTFLOW})

SIGNAL_ACCUMULATION = "accumulation"
SIGNAL_DISTRIBUTION = "distribution"
VALID_SIGNAL_TYPES = frozenset({SIGNAL_ACCUMULATION, SIGNAL_DISTRIBUTION})

SIGNAL_DOVE = "dove"
SIGNAL_HAWK = "hawk"
SIGNAL_NEUTRAL = "neutral"

HORIZON_T0 = "T0"
HORIZON_T1 = "T1"
HORIZON_T2 = "T2"
HORIZON_T3 = "T3"
HORIZON_T4 = "T4"
VALID_TIME_HORIZONS = frozenset({HORIZON_T0, HORIZON_T1, HORIZON_T2, HORIZON_T3, HORIZON_T4})


@dataclass(frozen=True)
class CfiBaseContract:
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
class ETFFlowMonitor(CfiBaseContract):
    daily_flows: list = field(default_factory=list)
    momentum_assessment: str = MOMENTUM_NEUTRAL
    price_flow_divergence_flag: bool = False
    composition_analysis: dict = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "composition_analysis",
            freeze_dict(self.composition_analysis),
        )


@dataclass(frozen=True)
class CentralBankReserveFlowReport(CfiBaseContract):
    net_official_purchases_month: float = 0.0
    net_official_purchases_12m: float = 0.0
    net_official_purchases_12m_trend: str = TREND_STABLE
    marginal_buyers: list = field(default_factory=list)
    pboc_track: dict = field(default_factory=lambda: FrozenDict())
    dedollarization_estimate: dict = field(default_factory=lambda: FrozenDict())
    structural_demand_outlook: dict = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "pboc_track", freeze_dict(self.pboc_track))
        object.__setattr__(
            self, "dedollarization_estimate",
            freeze_dict(self.dedollarization_estimate),
        )
        object.__setattr__(
            self, "structural_demand_outlook",
            freeze_dict(self.structural_demand_outlook),
        )


@dataclass(frozen=True)
class GoldPositioningDashboard(CfiBaseContract):
    cot_net_non_commercial: dict = field(default_factory=lambda: FrozenDict())
    etf_flow: dict = field(default_factory=lambda: FrozenDict())
    options_put_call_ratio: dict = field(default_factory=lambda: FrozenDict())
    dealer_gamma_profile: dict = field(default_factory=lambda: FrozenDict())
    gold_lease_rate: float = 0.0
    shanghai_premium: float = 0.0
    institutional_gold_beta: float = 0.0
    cta_sensitivity: str = ""
    composite_assessment: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "cot_net_non_commercial",
            freeze_dict(self.cot_net_non_commercial),
        )
        object.__setattr__(self, "etf_flow", freeze_dict(self.etf_flow))
        object.__setattr__(
            self, "options_put_call_ratio",
            freeze_dict(self.options_put_call_ratio),
        )
        object.__setattr__(
            self, "dealer_gamma_profile",
            freeze_dict(self.dealer_gamma_profile),
        )
