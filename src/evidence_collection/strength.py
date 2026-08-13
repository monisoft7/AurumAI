from __future__ import annotations

import math
from typing import Any

from evidence_collection.contracts import Evidence, EvidenceCollection


class EvidenceStrengthComputer:
    """Computes evidence strength and aggregate metrics.

    Strength is a composite of confidence, regime relevance,
    and temporal recency — normalized to [0, 1].
    """

    @staticmethod
    def compute_strength(evidence: Evidence) -> float:
        """Individual evidence strength score 0.0–1.0."""
        score = evidence.composite_weight * 0.5
        if math.isfinite(evidence.temporal_recency):
            score += evidence.temporal_recency * 0.2
        if evidence.supporting_observation_ids:
            score += 0.15 * min(len(evidence.supporting_observation_ids) / 3.0, 1.0)
        if evidence.contradicting_observation_ids:
            score -= 0.1 * min(len(evidence.contradicting_observation_ids) / 3.0, 1.0)
        if evidence.provenance is not None:
            score += 0.05
        return max(0.0, min(round(score, 4), 1.0))

    @staticmethod
    def compute_collection_aggregates(collection: EvidenceCollection) -> dict[str, Any]:
        if not collection.items:
            return {
                "evidence_count": 0,
                "avg_strength": 0.0,
                "max_strength": 0.0,
                "min_strength": 0.0,
                "bias_distribution": {},
            }

        strengths = [EvidenceStrengthComputer.compute_strength(e) for e in collection.items]
        biases: dict[str, int] = {}
        for e in collection.items:
            biases[e.bias] = biases.get(e.bias, 0) + 1

        return {
            "evidence_count": len(collection.items),
            "avg_strength": round(sum(strengths) / len(strengths), 4),
            "max_strength": round(max(strengths), 4),
            "min_strength": round(min(strengths), 4),
            "bias_distribution": biases,
            "avg_composite_weight": collection.avg_composite_weight,
        }
