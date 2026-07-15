from dataclasses import dataclass, field
from typing import Any


STEP_EVIDENCE_REVIEW = "evidence_review"
STEP_COMPARISON = "comparison"
STEP_AGGREGATION = "aggregation"
STEP_CONCLUSION = "conclusion"


@dataclass(frozen=True)
class ReasoningStep:
    step_id: str
    step_type: str
    conclusion: str
    confidence: float
    supporting_evidence_ids: tuple[str, ...]
    details: dict[str, Any] = field(default_factory=dict)
