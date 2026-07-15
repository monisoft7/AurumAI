from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source_node_id: str
    event_type: str
    condition: dict[str, str]
    horizon_days: int
    sample_count: int
    average_return_pct: float
    confidence: float
    bias: str
    explanation: str
    metadata: dict[str, Any] = field(default_factory=dict)
