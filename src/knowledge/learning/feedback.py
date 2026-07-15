from dataclasses import dataclass, field
from typing import Any


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
    metadata: dict[str, Any] = field(default_factory=dict)
