from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict


@dataclass(frozen=True)
class ForecastPoint:
    ds: str
    y: float
    y_lo: float
    y_hi: float


@dataclass(frozen=True)
class ForecastResult:
    model_name: str
    confidence_level: float
    points: tuple[ForecastPoint, ...]
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))
