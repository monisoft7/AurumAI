from dataclasses import dataclass, field
from typing import Any

from knowledge.decision.context import DecisionContext


DECISION_STRONG_POSITIVE = "STRONG_POSITIVE"
DECISION_POSITIVE = "POSITIVE"
DECISION_NEUTRAL = "NEUTRAL"
DECISION_NEGATIVE = "NEGATIVE"
DECISION_STRONG_NEGATIVE = "STRONG_NEGATIVE"

VALID_DECISION_TYPES = frozenset({
    DECISION_STRONG_POSITIVE,
    DECISION_POSITIVE,
    DECISION_NEUTRAL,
    DECISION_NEGATIVE,
    DECISION_STRONG_NEGATIVE,
})


@dataclass(frozen=True)
class Decision:
    decision_id: str
    decision_type: str
    confidence: float
    reasoning_chain_id: str
    evidence_count: int
    explanation: str
    context: DecisionContext
    metadata: dict[str, Any] = field(default_factory=dict)
