from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import Provenance

FED = "FED"
ECB = "ECB"
BOJ = "BOJ"
BOE = "BOE"
PBOC = "PBOC"
SNB = "SNB"
RBA = "RBA"
RBNZ = "RBNZ"
BOC = "BOC"

VALID_CENTRAL_BANKS = frozenset({
    FED, ECB, BOJ, BOE, PBOC, SNB, RBA, RBNZ, BOC,
})

DIRECTION_TIGHTENING = "tightening"
DIRECTION_EASING = "easing"
DIRECTION_NEUTRAL = "neutral"
VALID_DIRECTIONS = frozenset({DIRECTION_TIGHTENING, DIRECTION_EASING, DIRECTION_NEUTRAL})

HORIZON_T0 = "T0"
HORIZON_T1 = "T1"
HORIZON_T2 = "T2"
HORIZON_T3 = "T3"
HORIZON_T4 = "T4"
VALID_TIME_HORIZONS = frozenset({HORIZON_T0, HORIZON_T1, HORIZON_T2, HORIZON_T3, HORIZON_T4})

GUIDANCE_CALENDAR_BASED = "calendar_based"
GUIDANCE_STATE_CONTINGENT = "state_contingent"
GUIDANCE_OPEN_ENDED = "open_ended"
GUIDANCE_QUANTITATIVE = "quantitative"
VALID_GUIDANCE_TYPES = frozenset({
    GUIDANCE_CALENDAR_BASED, GUIDANCE_STATE_CONTINGENT,
    GUIDANCE_OPEN_ENDED, GUIDANCE_QUANTITATIVE,
})

CLASSIFICATION_EXPANDING = "Expanding"
CLASSIFICATION_STABLE = "Stable"
CLASSIFICATION_CONTRACTING = "Contracting"
VALID_CLASSIFICATIONS = frozenset({
    CLASSIFICATION_EXPANDING, CLASSIFICATION_STABLE, CLASSIFICATION_CONTRACTING,
})

PACE_RAPIDLY = "rapidly"
PACE_GRADUALLY = "gradually"
PACE_MARGINALLY = "marginally"
VALID_PACE_QUALIFIERS = frozenset({PACE_RAPIDLY, PACE_GRADUALLY, PACE_MARGINALLY})

RESERVE_ACCUMULATING = "accumulating"
RESERVE_STABLE = "stable"
RESERVE_DRAWING_DOWN = "drawing_down"
VALID_RESERVE_TRENDS = frozenset({RESERVE_ACCUMULATING, RESERVE_STABLE, RESERVE_DRAWING_DOWN})

REGIME_SYNCHRONIZED_EASING = "Synchronized_Easing"
REGIME_SYNCHRONIZED_TIGHTENING = "Synchronized_Tightening"
REGIME_DIVERGENT = "Divergent"
REGIME_TRANSITION = "Transition"
REGIME_EMERGENCY = "Emergency"
VALID_REGIME_TYPES = frozenset({
    REGIME_SYNCHRONIZED_EASING, REGIME_SYNCHRONIZED_TIGHTENING,
    REGIME_DIVERGENT, REGIME_TRANSITION, REGIME_EMERGENCY,
})


@dataclass(frozen=True)
class CbiBaseContract:
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
class PolicyBiasScore(CbiBaseContract):
    central_bank: str = ""
    score: int = 0
    direction: str = DIRECTION_NEUTRAL
    score_components: dict = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "score_components", freeze_dict(self.score_components))


@dataclass(frozen=True)
class RatePathProjection(CbiBaseContract):
    central_bank: str = ""
    base_path: list = field(default_factory=list)
    confidence_interval: int = 0
    current_rate: int = 0


@dataclass(frozen=True)
class ForwardGuidanceRecord(CbiBaseContract):
    central_bank: str = ""
    guidance_type: str = ""
    guidance_text: str = ""
    credibility_score: float = 0.0
    language_delta: str = ""
    data_quality_flags: list | None = None


@dataclass(frozen=True)
class LiquidityOutlook(CbiBaseContract):
    classification: str = ""
    pace_qualifier: str = ""
    g4_balance_sheet_trajectory: list = field(default_factory=list)
    reserve_trend: str = ""
    money_market_stress: list = field(default_factory=list)
    fiscal_liquidity_effects: str = ""


@dataclass(frozen=True)
class GlobalMonetaryRegime(CbiBaseContract):
    regime: str = ""
    regime_description: str = ""
    aggregate_monetary_stance: float = 0.0
    synchronization_measure: float = 0.0
    transition_signals: list = field(default_factory=list)
