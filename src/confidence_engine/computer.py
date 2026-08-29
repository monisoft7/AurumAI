from __future__ import annotations

from typing import Any

from knowledge.integrity.provenance import Provenance  # noqa: F401 (contract parity)
from thesis_construction.contracts import InvestmentThesis


class ConfidenceComputer:
    """Computes normalized institutional confidence [0,1] for a single thesis
    with a full breakdown of every contributing factor.

    Run-003 repair (Phase 5) -- confidence semantics.  Confidence must
    estimate actual decision reliability, not support volume.  Three
    mechanically saturated quantities were removed or made
    saturation-free:

    * ``regime_alignment`` channel REMOVED (weight 0.15): it scored 1.0/0.0
      against the fixed REGIME_EXPECTED_BIAS prior, which has no as-of
      validation (Phase 7 neutralization).  The remaining positive weights
      are renormalized to sum to 1.0.
    * ``source_diversity`` now ``n / (n + 3)``: diminishing returns that
      never mechanically saturate at 3 sets (was ``min(n / 3, 1)``).
    * ``knowledge_record_quality`` now ``p / (p + 2)``: diminishing returns
      that never mechanically saturate at 2 provenance entries (was
      ``min(p / 2, 1)`` -- every thesis saturated at 1.0).

    The consensus input feeding ``evidence_consensus`` is itself repaired
    upstream (W6 Beta(1,1)-shrunk weighted agreement over deduplicated
    items), so single-item and homogeneous-neutral sets no longer inject
    perfect consensus here.
    """

    POSITIVE_WEIGHTS: dict[str, float] = {
        "evidence_quality": 0.35,
        "evidence_consensus": 0.35,
        "source_diversity": 0.20,
        "knowledge_record_quality": 0.10,
    }

    PENALTY_WEIGHTS: dict[str, float] = {
        "counter_evidence": 0.35,
        "missing_evidence": 0.25,
        "internal_consistency": 0.40,
    }

    LOW_CONFIDENCE_THRESHOLD = 0.35
    HIGH_CONFIDENCE_THRESHOLD = 0.60

    def compute(self, thesis: InvestmentThesis) -> dict[str, Any]:
        inputs = thesis.confidence_inputs or {}

        evidence_quality = float(inputs.get("avg_supporting_weight", 0.0))
        evidence_consensus = float(inputs.get("avg_supporting_consensus", 0.0))
        conflict_severity = float(inputs.get("conflict_severity", 0.0))
        internal_penalty = float(inputs.get("confidence_penalty", 0.0))
        institutional_support = thesis.institutional_support

        source_diversity = self._diversity(len(thesis.supporting_set_ids))
        kr_quality = self._provenance_quality(len(thesis.provenance_chain))
        missing_penalty = min(len(thesis.remaining_unknowns) / 3.0, 1.0)

        positives = {
            "evidence_quality": evidence_quality,
            "evidence_consensus": evidence_consensus,
            "source_diversity": round(source_diversity, 4),
            "knowledge_record_quality": round(kr_quality, 4),
        }

        positive_score = sum(
            positives[name] * weight
            for name, weight in self.POSITIVE_WEIGHTS.items()
        )

        penalties = {
            "counter_evidence": conflict_severity,
            "missing_evidence": missing_penalty,
            "internal_consistency": internal_penalty,
        }

        penalty_score = sum(
            penalties[name] * weight
            for name, weight in self.PENALTY_WEIGHTS.items()
        )

        # Correction 049-B retained: institutional_support enters exactly
        # ONCE, through evidence_quality / positive_score (the ThesisBuilder
        # mean of supporting net weights).
        final = positive_score * (1.0 - min(penalty_score, 1.0))
        final = round(max(0.0, min(final, 1.0)), 4)

        positive_contributors = [
            {"name": name, "value": value, "weight": self.POSITIVE_WEIGHTS[name]}
            for name, value in positives.items()
        ]
        negative_contributors = [
            {"name": name, "value": value, "weight": self.PENALTY_WEIGHTS[name]}
            for name, value in penalties.items()
        ]

        return {
            "final_confidence": final,
            "confidence_breakdown": {**positives, **penalties},
            "positive_contributors": positive_contributors,
            "negative_contributors": negative_contributors,
            "confidence_penalties": [
                {"name": name, "value": value, "penalty": round(value * self.PENALTY_WEIGHTS[name], 4)}
                for name, value in penalties.items()
            ],
            "remaining_uncertainty": round(1.0 - final, 4),
            "reliability_category": self.reliability_category(final),
            "metadata": {
                "institutional_support": institutional_support,
            },
        }

    @staticmethod
    def _diversity(n_sets: int) -> float:
        """Independent-source diversity: diminishing returns, never saturates."""
        n = max(0, int(n_sets))
        return n / (n + 3.0)

    @staticmethod
    def _provenance_quality(n_entries: int) -> float:
        """Provenance depth quality: diminishing returns, never saturates."""
        p = max(0, int(n_entries))
        return p / (p + 2.0)

    @staticmethod
    def reliability_category(final_confidence: float) -> str:
        if final_confidence >= 0.70:
            return "high"
        if final_confidence >= 0.50:
            return "moderate"
        if final_confidence >= 0.30:
            return "low"
        return "very_low"
