from dataclasses import dataclass, field
from typing import Any

EVIDENCE_ROLE_SUPPORTING = "supporting"
EVIDENCE_ROLE_CONTRADICTING = "contradicting"
EVIDENCE_ROLE_CONTEXTUAL = "contextual"

VALID_EVIDENCE_ROLES = frozenset({
    EVIDENCE_ROLE_SUPPORTING,
    EVIDENCE_ROLE_CONTRADICTING,
    EVIDENCE_ROLE_CONTEXTUAL,
})


@dataclass(frozen=True)
class CausalEvidence:
    causal_evidence_id: str
    hypothesis_id: str
    evidence_id: str
    role: str
    strength: float = 0.0
    explanation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
