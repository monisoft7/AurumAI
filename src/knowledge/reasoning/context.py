from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReasoningContext:
    event_type: str
    condition: dict[str, str] | None = None
    horizon_days: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
