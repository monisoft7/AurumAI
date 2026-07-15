from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DecisionContext:
    event_type: str
    query: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
