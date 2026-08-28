"""Technical Research Desk contracts.

Independent research-layer artifact: a TechnicalAssessment describes the
technical state of one instrument on one timeframe as of one timestamp.
It is an observability / research payload only -- it never feeds, gates,
or overrides the institutional decision path (W13/W14).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DIRECTION_BULLISH = "bullish"
DIRECTION_BEARISH = "bearish"
DIRECTION_NEUTRAL = "neutral"
DIRECTION_UNKNOWN = "unknown"

VOLATILITY_EXPANDING = "expanding"
VOLATILITY_CONTRACTING = "contracting"
VOLATILITY_NORMAL = "normal"

OBOS_OVERBOUGHT = "overbought"
OBOS_OVERSOLD = "oversold"

STRUCTURE_UPTREND = "uptrend"
STRUCTURE_DOWNTREND = "downtrend"
STRUCTURE_RANGE = "range"

SUPPORTED_TIMEFRAMES = ("D1", "H4", "H1")

# Minimum bars required before any indicator reading is trusted.  D1 needs
# the EMA-200 warm-up plus ADX smoothing headroom; intraday timeframes use
# the same reasoning over their own bar counts.
MIN_BARS_BY_TIMEFRAME: dict[str, int] = {"D1": 260, "H4": 300, "H1": 300}


class TechnicalDeskError(Exception):
    """Base class for Technical Research Desk failures."""


class TechnicalDataError(TechnicalDeskError):
    """Raised when the provided OHLCV data violates basic validity rules."""


class TechnicalDependencyError(TechnicalDeskError):
    """Raised when the configured technical computation engine cannot be loaded."""


@dataclass(frozen=True)
class TechnicalAssessment:
    """Immutable technical research artifact for one (asset, timeframe, as_of)."""

    assessment_id: str
    asset: str
    as_of: str
    timeframe: str
    trend_direction: str
    momentum_direction: str
    volatility_state: str
    overbought_oversold_state: str
    structure_state: str | None
    technical_confidence: float
    supporting_indicators: tuple[str, ...] = ()
    conflicting_indicators: tuple[str, ...] = ()
    source_data_hash: str = ""
    provenance_chain: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "supporting_indicators", tuple(self.supporting_indicators)
        )
        object.__setattr__(
            self, "conflicting_indicators", tuple(self.conflicting_indicators)
        )
        object.__setattr__(self, "provenance_chain", tuple(self.provenance_chain))

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.timeframe not in SUPPORTED_TIMEFRAMES:
            errors.append(f"unsupported timeframe: {self.timeframe}")
        if not self.as_of:
            errors.append("as_of is required")
        if not 0.0 <= float(self.technical_confidence) <= 1.0:
            errors.append("technical_confidence must be within [0, 1]")
        if self.trend_direction not in (
            DIRECTION_BULLISH, DIRECTION_BEARISH, DIRECTION_NEUTRAL, DIRECTION_UNKNOWN,
        ):
            errors.append(f"invalid trend_direction: {self.trend_direction}")
        if self.momentum_direction not in (
            DIRECTION_BULLISH, DIRECTION_BEARISH, DIRECTION_NEUTRAL, DIRECTION_UNKNOWN,
        ):
            errors.append(f"invalid momentum_direction: {self.momentum_direction}")
        if self.volatility_state not in (
            VOLATILITY_EXPANDING, VOLATILITY_CONTRACTING, VOLATILITY_NORMAL,
            DIRECTION_UNKNOWN,
        ):
            errors.append(f"invalid volatility_state: {self.volatility_state}")
        if self.overbought_oversold_state not in (
            OBOS_OVERBOUGHT, OBOS_OVERSOLD, DIRECTION_NEUTRAL, DIRECTION_UNKNOWN,
        ):
            errors.append(
                f"invalid overbought_oversold_state: {self.overbought_oversold_state}"
            )
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "asset": self.asset,
            "as_of": self.as_of,
            "timeframe": self.timeframe,
            "trend_direction": self.trend_direction,
            "momentum_direction": self.momentum_direction,
            "volatility_state": self.volatility_state,
            "overbought_oversold_state": self.overbought_oversold_state,
            "structure_state": self.structure_state,
            "technical_confidence": self.technical_confidence,
            "supporting_indicators": list(self.supporting_indicators),
            "conflicting_indicators": list(self.conflicting_indicators),
            "source_data_hash": self.source_data_hash,
            "provenance_chain": [dict(p) for p in self.provenance_chain],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TechnicalAssessment":
        return cls(
            assessment_id=str(data["assessment_id"]),
            asset=str(data.get("asset", "")),
            as_of=str(data["as_of"]),
            timeframe=str(data["timeframe"]),
            trend_direction=str(data["trend_direction"]),
            momentum_direction=str(data["momentum_direction"]),
            volatility_state=str(data["volatility_state"]),
            overbought_oversold_state=str(data["overbought_oversold_state"]),
            structure_state=data.get("structure_state"),
            technical_confidence=float(data["technical_confidence"]),
            supporting_indicators=tuple(data.get("supporting_indicators", ())),
            conflicting_indicators=tuple(data.get("conflicting_indicators", ())),
            source_data_hash=str(data.get("source_data_hash", "")),
            provenance_chain=tuple(data.get("provenance_chain", ())),
            metadata=dict(data.get("metadata", {})),
        )
