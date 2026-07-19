from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict


@dataclass(frozen=True)
class KnowledgeFeedback:
    feedback_id: str
    source_record_ids: tuple[str, ...]
    event_type: str
    condition: dict[str, str]
    horizon_days: int
    current_confidence: float
    suggested_confidence: float
    accuracy_rate: float
    correct_count: int
    sample_count: int
    explanation: str
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "condition", freeze_dict(self.condition))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))
