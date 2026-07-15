from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EconomicCycle:
    cycle_id: str
    states: tuple["EconomicState", ...]
    start_date: str
    end_date: str | None = None
    regime_ids: tuple[str, ...] = ()
    transitions: tuple[tuple[str, str], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
