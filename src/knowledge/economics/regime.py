from dataclasses import dataclass, field
from typing import Any

REGIME_HIGH_INFLATION = "HIGH_INFLATION"
REGIME_LOW_INFLATION = "LOW_INFLATION"
REGIME_DEFLATION = "DEFLATION"
REGIME_DISINFLATION = "DISINFLATION"
REGIME_TIGHT_MONETARY = "TIGHT_MONETARY"
REGIME_LOOSE_MONETARY = "LOOSE_MONETARY"
REGIME_RISK_ON = "RISK_ON"
REGIME_RISK_OFF = "RISK_OFF"
REGIME_RECESSION = "RECESSION"
REGIME_EXPANSION = "EXPANSION"
REGIME_STAGFLATION = "STAGFLATION"

VALID_REGIME_TYPES = frozenset({
    REGIME_HIGH_INFLATION,
    REGIME_LOW_INFLATION,
    REGIME_DEFLATION,
    REGIME_DISINFLATION,
    REGIME_TIGHT_MONETARY,
    REGIME_LOOSE_MONETARY,
    REGIME_RISK_ON,
    REGIME_RISK_OFF,
    REGIME_RECESSION,
    REGIME_EXPANSION,
    REGIME_STAGFLATION,
})


@dataclass(frozen=True)
class EconomicRegime:
    regime_id: str
    regime_type: str
    label: str
    description: str
    start_date: str
    end_date: str | None = None
    confidence: float = 0.0
    indicators: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
