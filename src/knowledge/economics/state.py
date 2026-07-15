from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EconomicState:
    state_id: str
    date: str
    indicators: dict[str, float] = field(default_factory=dict)
    regime_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
