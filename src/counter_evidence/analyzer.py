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
        """Aggregate W7 penalty from unique, evidence-backed, non-filtered causes.

        Penalty units per docs/design/COUNTER_EVIDENCE_CORRECTION_V1.md:
        - conflict_severity * 0.4 (cross-set contradiction severity)
        - +0.1 when the ``regime_conflict`` flag is set (regime mismatch)
        - +0.1 when the ``missing_evidence`` flag is set (truly unavailable channel)

        ``cross_set_conflict`` is the same fact already counted by severity;
        ``no_dissent`` is a mislabeled heuristic in multi-set contradiction
        cases; and the separate ``regime_conflict`` boolean is a duplicate of
        the flag. None of those add penalty mass.
        """
        penalty = conflict_severity * 0.4
        if "regime_conflict" in bias_flags:
            penalty += 0.1
        if "missing_evidence" in bias_flags:
            penalty += 0.1
        return max(0.0, min(round(penalty, 4), 1.0))
