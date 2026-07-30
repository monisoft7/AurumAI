from __future__ import annotations

from collections import Counter
from typing import Any

from counter_evidence.detector import ConflictDetector
from evidence_reasoning.contracts import EvidenceReasoning, EvidenceSet


class BiasAnalyzer:
    """Analyzes confirmation bias, missing evidence, and computes
    contradiction severity and confidence penalty."""

    @staticmethod
    def confirmation_bias(evidence_sets: tuple[EvidenceSet, ...]) -> bool:
        """Confirmation bias flagged when all sets agree (no dissenting bias)."""
        if len(evidence_sets) <= 1:
            return True
        biases = {es.bias for es in evidence_sets if es.bias}
        return len(biases) <= 1

    @staticmethod
    def no_dissent(evidence_sets: tuple[EvidenceSet, ...]) -> bool:
        """No dissent when every set has zero conflict_score."""
        if not evidence_sets:
            return True
        return all(es.conflict_score == 0.0 for es in evidence_sets)

    @staticmethod
    def compute_conflict_severity(
        evidence_sets: tuple[EvidenceSet, ...],
        contradicting_ids: list[str],
    ) -> float:
        if not evidence_sets:
            return 0.0

        n = len(evidence_sets)
        n_contra = len(contradicting_ids)
        cross_ratio = n_contra / n if n > 0 else 0.0

        avg_conflict = sum(es.conflict_score for es in evidence_sets) / n

        severity = round(cross_ratio * 0.5 + avg_conflict * 0.5, 4)
        return max(0.0, min(severity, 1.0))

    @staticmethod
    def compute_confidence_penalty(
        conflict_severity: float,
        bias_flags: list[str],
        regime_conflict: bool,
    ) -> float:
        penalty = conflict_severity * 0.4
        penalty += len(bias_flags) * 0.1
        if regime_conflict:
            penalty += 0.2
        return max(0.0, min(round(penalty, 4), 1.0))
