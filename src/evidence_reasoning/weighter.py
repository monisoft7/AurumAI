from __future__ import annotations

import math
from typing import Any

from evidence_collection.contracts import Evidence
from evidence_reasoning.contracts import EvidenceSet
from evidence_reasoning.detector import directional_masses


class EvidenceWeighter:
    """Computes net institutional weight, consensus score, conflict score,
    confidence contribution, and explanation for an EvidenceSet.

    Run-003 repair (Phase 3/5) -- evidence discriminability:

    * Consensus is the Beta(1,1) posterior mean of directional agreement
      over the group's weighted composite-weight masses: single-item and
      fully homogeneous groups no longer mechanically saturate at 1.0, and
      the uniform prior keeps genuinely weak evidence from asserting
      perfect agreement.
    * Neutral evidence contributes to neither the numerator nor the
      denominator: uninformative items neither support nor oppose, and they
      no longer dilute directional consensus (this supersedes the Correction
      060 dilution note -- dilution was itself a neutral-as-competitor
      artifact).
    * Conflict remains the observed weighted opposition share among
      directional mass -- actual dissent, not prior uncertainty.
    * A set with no directional mass (neutral or empty) reports consensus
      0.0 / conflict 0.0: there is no directional agreement to measure.
    """

    WEIGHT_RECENCY_FACTOR = 0.3
    WEIGHT_CONFIDENCE_FACTOR = 0.5
    WEIGHT_PROVENANCE_FACTOR = 0.2

    # Beta(1,1) prior pseudo-mass for the consensus posterior mean.
    CONSENSUS_PRIOR_MASS = 1.0

    def weight_set(self, evidence_set: EvidenceSet, all_evidence: list[Evidence]) -> EvidenceSet:
        ev_map = {e.evidence_id: e for e in all_evidence}
        group = [ev_map[eid] for eid in evidence_set.evidence_ids if eid in ev_map]
        if not group:
            return evidence_set

        net_weight = self._compute_net_weight(group)
        consensus, conflict = self._compute_consensus_conflict(group, evidence_set.bias)
        conf_contrib = round(net_weight * consensus, 4)
        explanation = self._build_explanation(evidence_set, net_weight, consensus, conflict, group)

        d = evidence_set.to_dict()
        d["net_institutional_weight"] = net_weight
        d["consensus_score"] = consensus
        d["conflict_score"] = conflict
        d["confidence_contribution"] = conf_contrib
        d["explanation"] = explanation
        return EvidenceSet.from_dict(d)

    def _compute_net_weight(self, evidence_group: list[Evidence]) -> float:
        if not evidence_group:
            return 0.0

        raw = sum(e.composite_weight for e in evidence_group) / len(evidence_group)

        finite_recencies = [
            e.temporal_recency for e in evidence_group
            if math.isfinite(e.temporal_recency)
        ]
        if finite_recencies:
            avg_recency = sum(finite_recencies) / len(finite_recencies)
        else:
            avg_recency = 0.0
        recency_boost = avg_recency * self.WEIGHT_RECENCY_FACTOR

        has_provenance = sum(1 for e in evidence_group if e.provenance is not None)
        prov_ratio = has_provenance / len(evidence_group)
        prov_boost = prov_ratio * self.WEIGHT_PROVENANCE_FACTOR

        adjusted = raw * self.WEIGHT_CONFIDENCE_FACTOR + recency_boost + prov_boost
        return max(0.0, min(round(adjusted, 4), 1.0))

    @classmethod
    def _compute_consensus_conflict(
        cls,
        group: list[Evidence],
        majority_bias: str,
    ) -> tuple[float, float]:
        """Beta(1,1)-shrunk weighted directional agreement (consensus) and
        the observed weighted opposition share (conflict).

        ``s`` / ``o`` are the supporting / opposing weighted masses under the
        set's majority bias (mixed evidence contributes to both sides at its
        mass split). With no directional mass there is nothing to measure:
        consensus and conflict are 0.0.
        """
        if not group:
            return 0.0, 0.0

        if majority_bias not in {"bullish", "bearish", "mixed"}:
            # Neutral set: no directional agreement exists to measure.
            return 0.0, 0.0

        bull, bear = directional_masses(group)
        if majority_bias == "bullish":
            s, o = bull, bear
        elif majority_bias == "bearish":
            s, o = bear, bull
        else:
            s, o = bull, bear

        prior = cls.CONSENSUS_PRIOR_MASS
        consensus = round((s + prior) / (s + o + 2.0 * prior), 4)
        conflict = round(o / (s + o), 4) if (s + o) > 0.0 else 0.0
        return consensus, conflict

    @staticmethod
    def _build_explanation(
        evidence_set: EvidenceSet,
        net_weight: float,
        consensus: float,
        conflict: float,
        group: list[Evidence],
    ) -> str:
        n = len(group)
        supporting = len(evidence_set.supporting_evidence_ids)
        contradicting = len(evidence_set.contradicting_evidence_ids)
        dup = len(evidence_set.duplicate_evidence_ids)

        parts = [
            f"EvidenceSet {evidence_set.set_id}",
            f"event_type={evidence_set.event_type}",
            f"bias={evidence_set.bias}",
            f"items={n}",
            f"supporting={supporting}",
            f"contradicting={contradicting}",
            f"duplicates_removed={dup}",
            f"net_weight={net_weight}",
            f"consensus={consensus}",
            f"conflict={conflict}",
        ]
        return " | ".join(parts)
