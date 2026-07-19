from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict


@dataclass(frozen=True)
class ReasoningContext:
    event_type: str
    condition: dict[str, str] | None = None
    horizon_days: int | None = None
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "condition", freeze_dict(self.condition) if self.condition is not None else None)
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))
