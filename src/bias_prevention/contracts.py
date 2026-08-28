"""Bias review contracts: per-bias findings, the aggregate review, and the
gate that makes a final decision consume the review before it is emitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from decision_engine.contracts import InstitutionalDecision
from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import Provenance, serialize_provenance, deserialize_provenance

VALID_SEVERITIES = {"clean", "low", "medium", "high", "critical"}

SEVERITY_RANK = {
    "clean": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

SEVERITY_IMPACT = {
    "clean": 0.0,
    "low": 0.10,
    "medium": 0.15,
    "high": 0.25,
    "critical": 0.40,
}

HUMAN_REVIEW_SEVERITIES = {"high", "critical"}


@dataclass(frozen=True)
class BiasFinding:
    """A single detected bias with severity, evidence, and remediation."""

    bias_name: str
    severity: str
    evidence: str
    required_action: str
    confidence_impact: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "bias_name": self.bias_name,
            "severity": self.severity,
            "evidence": self.evidence,
            "required_action": self.required_action,
            "confidence_impact": self.confidence_impact,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BiasFinding:
        return cls(
            bias_name=str(data.get("bias_name", "")),
            severity=str(data.get("severity", "")),
            evidence=str(data.get("evidence", "")),
            required_action=str(data.get("required_action", "")),
            confidence_impact=float(data.get("confidence_impact", 0.0)),
        )


@dataclass(frozen=True)
class BiasReview:
    """W13 output: bias prevention review consumed before final decision."""

    review_id: str
    thesis_id: str
    update_id: str
    confidence_id: str
    assessment_id: str
    timestamp: str
    regime: str
    findings: tuple[BiasFinding, ...] = ()
    overall_severity: str = "clean"
    total_confidence_impact: float = 0.0
    required_actions: tuple[str, ...] = ()
    human_review_flag: bool = False
    provenance_chain: tuple[Provenance, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "required_actions", tuple(self.required_actions))
        object.__setattr__(self, "provenance_chain", tuple(self.provenance_chain))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "thesis_id": self.thesis_id,
            "update_id": self.update_id,
            "confidence_id": self.confidence_id,
            "assessment_id": self.assessment_id,
            "timestamp": self.timestamp,
            "regime": self.regime,
            "findings": [f.to_dict() for f in self.findings],
            "overall_severity": self.overall_severity,
            "total_confidence_impact": self.total_confidence_impact,
            "required_actions": list(self.required_actions),
            "human_review_flag": self.human_review_flag,
            "provenance_chain": [serialize_provenance(p) for p in self.provenance_chain],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BiasReview:
        return cls(
            review_id=str(data.get("review_id", "")),
            thesis_id=str(data.get("thesis_id", "")),
            update_id=str(data.get("update_id", "")),
            confidence_id=str(data.get("confidence_id", "")),
            assessment_id=str(data.get("assessment_id", "")),
            timestamp=str(data.get("timestamp", "")),
            regime=str(data.get("regime", "")),
            findings=tuple(BiasFinding.from_dict(f) for f in data.get("findings", [])),
            overall_severity=str(data.get("overall_severity", "clean")),
            total_confidence_impact=float(data.get("total_confidence_impact", 0.0)),
            required_actions=tuple(data.get("required_actions", ())),
            human_review_flag=bool(data.get("human_review_flag", False)),
            provenance_chain=tuple(
                deserialize_provenance(p) for p in data.get("provenance_chain", []) if p is not None
            ),
            metadata=dict(data.get("metadata", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.overall_severity not in VALID_SEVERITIES:
            errors.append(f"invalid overall_severity: {self.overall_severity}")
        if not 0.0 <= self.total_confidence_impact <= 1.0:
            errors.append(
                f"total_confidence_impact out of range: {self.total_confidence_impact}"
            )
        for finding in self.findings:
            if finding.severity not in VALID_SEVERITIES:
                errors.append(f"invalid severity for {finding.bias_name}: {finding.severity}")
            if not 0.0 <= finding.confidence_impact <= 1.0:
                errors.append(
                    f"confidence_impact out of range for {finding.bias_name}"
                )
            if not finding.bias_name:
                errors.append("bias_name is required")
            if not finding.required_action:
                errors.append(f"required_action is required for {finding.bias_name}")
        if self.findings and not self.required_actions:
            errors.append("required_actions must be non-empty when findings exist")
        return errors


def apply_bias_review(
    decision: InstitutionalDecision,
    review: BiasReview,
    other_reviews: tuple[BiasReview, ...] | list[BiasReview] = (),
) -> InstitutionalDecision:
    """Consumes a BiasReview into the final decision.

    Final Hardening (Group A, D-04 -- decision vs review scope): the review
    gates the thesis it actually examined.  A human-review block is applied
    only when the reviewed thesis IS the selected thesis (or when no thesis
    was selected).  A review targeting a non-selected candidate is recorded
    as an explicit advisory and never vetoes a decision made on a different
    thesis.

    The review summary is always recorded on the decision metadata, together
    with ``reviewed_thesis_id`` so selected/reviewed identity is auditable.
    """
    summary = {
        "review_id": review.review_id,
        "overall_severity": review.overall_severity,
        "total_confidence_impact": review.total_confidence_impact,
        "human_review_flag": review.human_review_flag,
        "findings": [f.bias_name for f in review.findings],
    }
    metadata = dict(decision.metadata)
    metadata["bias_review"] = summary
    metadata["reviewed_thesis_id"] = review.thesis_id
    others = [
        {
            "thesis_id": r.thesis_id,
            "overall_severity": r.overall_severity,
            "human_review_flag": r.human_review_flag,
        }
        for r in other_reviews
        if r.thesis_id != review.thesis_id
    ]
    if others:
        metadata["other_candidate_reviews"] = others

    explanation = decision.decision_explanation
    decision_value = decision.decision
    selected_id = decision.selected_thesis_id
    review_targets_selection = (not selected_id) or (
        review.thesis_id == selected_id
    )
    if review.human_review_flag and review_targets_selection:
        if decision_value != "NO_TRADE":
            decision_value = "NO_TRADE"
            explanation += (
                " | BLOCKED BY BIAS PREVENTION: human review required "
                f"(overall_severity={review.overall_severity}, "
                f"findings={[f.bias_name for f in review.findings]})"
            )
        else:
            explanation += (
                " | BIAS REVIEW: human review required "
                f"(overall_severity={review.overall_severity}, "
                f"findings={[f.bias_name for f in review.findings]})"
            )
    elif review.human_review_flag:
        explanation += (
            " | BIAS REVIEW ADVISORY: human review required for candidate "
            f"{review.thesis_id} (not the selected thesis "
            f"{selected_id}); recorded, not gating"
        )

    return replace(
        decision,
        decision=decision_value,
        decision_explanation=explanation,
        metadata=metadata,
    )
