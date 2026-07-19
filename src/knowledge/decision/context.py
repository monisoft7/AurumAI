from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict


@dataclass(frozen=True)
class DecisionContext:
    event_type: str
    query: str = ""
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))
