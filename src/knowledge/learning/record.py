from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict


@dataclass(frozen=True)
class LearningRecord:
    record_id: str
    decision_id: str
    reasoning_chain_id: str
    event_type: str
    decision_type: str
    decision_confidence: float
    expected_direction: str
    actual_return_pct: float
    direction_correct: bool
    accuracy_score: float
    details: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", freeze_dict(self.details))
