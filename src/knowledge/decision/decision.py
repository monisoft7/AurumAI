from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.decision.context import DecisionContext
from knowledge.integrity.provenance import Provenance


DECISION_STRONG_POSITIVE = "STRONG_POSITIVE"
DECISION_POSITIVE = "POSITIVE"
DECISION_NEUTRAL = "NEUTRAL"
DECISION_NEGATIVE = "NEGATIVE"
DECISION_STRONG_NEGATIVE = "STRONG_NEGATIVE"
DECISION_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

VALID_DECISION_TYPES = frozenset({
    DECISION_STRONG_POSITIVE,
    DECISION_POSITIVE,
    DECISION_NEUTRAL,
    DECISION_NEGATIVE,
    DECISION_STRONG_NEGATIVE,
    DECISION_INSUFFICIENT_EVIDENCE,
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
    provenance: Provenance | None = None
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))
