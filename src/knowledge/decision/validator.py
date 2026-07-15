from __future__ import annotations

from knowledge.decision.decision import Decision, VALID_DECISION_TYPES


class DecisionValidator:
    @staticmethod
    def validate(decision: Decision) -> dict[str, list[str]]:
        errors: dict[str, list[str]] = {}
        if decision.decision_type not in VALID_DECISION_TYPES:
            errors["decision_type"] = [
                f"Invalid decision type '{decision.decision_type}'. "
                f"Valid types: {', '.join(sorted(VALID_DECISION_TYPES))}"
            ]
        if not 0.0 <= decision.confidence <= 1.0:
            errors["confidence"] = [
                f"Confidence {decision.confidence} is out of range [0, 1]."
            ]
        if not decision.reasoning_chain_id:
            errors["reasoning_chain_id"] = ["Must not be empty."]
        if decision.evidence_count < 0:
            errors["evidence_count"] = [
                f"Evidence count {decision.evidence_count} must not be negative."
            ]
        if not decision.explanation:
            errors["explanation"] = ["Must not be empty."]
        return errors

    @staticmethod
    def is_valid(decision: Decision) -> bool:
        return not any(DecisionValidator.validate(decision).values())
