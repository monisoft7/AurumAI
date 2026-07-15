from dataclasses import dataclass, field
from typing import Any


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
    details: dict[str, Any] = field(default_factory=dict)
