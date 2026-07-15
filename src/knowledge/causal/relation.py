from dataclasses import dataclass, field
from typing import Any

RELATION_CAUSATION = "causation"
RELATION_CORRELATION = "correlation"
RELATION_COINCIDENCE = "coincidence"

VALID_RELATION_TYPES = frozenset({
    RELATION_CAUSATION,
    RELATION_CORRELATION,
    RELATION_COINCIDENCE,
})

DIRECTION_SOURCE_TO_TARGET = "source_to_target"
DIRECTION_BIDIRECTIONAL = "bidirectional"
DIRECTION_UNKNOWN = "unknown"

VALID_DIRECTIONS = frozenset({
    DIRECTION_SOURCE_TO_TARGET,
    DIRECTION_BIDIRECTIONAL,
    DIRECTION_UNKNOWN,
})


@dataclass(frozen=True)
class CausalRelation:
    relation_id: str
    source_id: str
    target_id: str
    relation_type: str
    strength: float
    confidence: float
    direction: str = DIRECTION_UNKNOWN
    evidence_ids: tuple[str, ...] = ()
    temporal_lag: int = 0
    explanation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
