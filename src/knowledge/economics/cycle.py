from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict


@dataclass(frozen=True)
class EconomicCycle:
    cycle_id: str
    states: tuple["EconomicState", ...]
    start_date: str
    end_date: str | None = None
    regime_ids: tuple[str, ...] = ()
    transitions: tuple[tuple[str, str], ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))
