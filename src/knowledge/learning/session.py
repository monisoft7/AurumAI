from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.learning.record import LearningRecord


@dataclass(frozen=True)
class LearningSession:
    session_id: str
    records: tuple[LearningRecord, ...]
    total_records: int
    correct_count: int
    accuracy_rate: float
    avg_confidence: float
    summary: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "summary", freeze_dict(self.summary))
