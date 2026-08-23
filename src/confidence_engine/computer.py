from __future__ import annotations

from typing import Any

from counter_evidence.detector import REGIME_EXPECTED_BIAS
from knowledge.integrity.provenance import Provenance
from thesis_construction.contracts import InvestmentThesis


class ConfidenceComputer:
    """Computes normalized institutional confidence [0,1] for a single thesis
    with a full breakdown of every contributing factor."""

    POSITIVE_WEIGHTS: dict[str, float] = {
        "evidence_quality": 0.25,
        "evidence_consensus": 0.25,
        "regime_alignment": 0.15,
        "source_diversity": 0.15,
        "knowledge_record_quality": 0.10,
        "temporal_recency": 0.10,
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

        regime_alignment = self._regime_alignment(thesis.direction, thesis.regime)
        source_diversity = min(len(thesis.supporting_set_ids) / 3.0, 1.0)
        kr_quality = min(len(thesis.provenance_chain) / 2.0, 1.0)
        temporal_recency = self._temporal_recency(thesis)
        missing_penalty = min(len(thesis.remaining_unknowns) / 3.0, 1.0)

        positives = {
            "evidence_quality": evidence_quality,
            "evidence_consensus": evidence_consensus,
            "regime_alignment": regime_alignment,
            "source_diversity": round(source_diversity, 4),
            "knowledge_record_quality": round(kr_quality, 4),
            "temporal_recency": temporal_recency,
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

        # Correction 049-B: institutional_support enters exactly ONCE,
        # through evidence_quality / positive_score (the ThesisBuilder mean
        # of supporting net weights).  The former second global
        # multiplication (support_factor) duplicated that contribution and
        # made the 0.5 decision gate unreachable (Trace 049-X: 0/25 crossed;
        # SUPPORT_ONCE counterfactual: 17/25).  Removed verbatim; every
        # other component, weight and penalty is unchanged.
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
    def _regime_alignment(direction: str, regime: str) -> float:
        expected = REGIME_EXPECTED_BIAS.get(regime, "neutral")
        if not expected or direction == "neutral":
            return 0.5
        if direction == expected:
            return 1.0
        return 0.0

    @staticmethod
    def _temporal_recency(thesis: InvestmentThesis) -> float:
        meta = thesis.metadata or {}
        if "avg_temporal_recency" in meta:
            return max(0.0, min(float(meta["avg_temporal_recency"]), 1.0))
        return 1.0

    @staticmethod
    def reliability_category(final_confidence: float) -> str:
        if final_confidence >= 0.70:
            return "high"
        if final_confidence >= 0.50:
            return "moderate"
        if final_confidence >= 0.30:
            return "low"
        return "very_low"
