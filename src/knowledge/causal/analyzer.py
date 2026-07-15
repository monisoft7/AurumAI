from __future__ import annotations

from knowledge.causal.relation import (
    CausalRelation,
    RELATION_CAUSATION,
    RELATION_CORRELATION,
    RELATION_COINCIDENCE,
    DIRECTION_SOURCE_TO_TARGET,
    DIRECTION_BIDIRECTIONAL,
    DIRECTION_UNKNOWN,
)
from knowledge.causal.hypothesis import (
    CausalHypothesis,
    HYPOTHESIS_PROPOSED,
)
from knowledge.causal.evidence import (
    CausalEvidence,
    EVIDENCE_ROLE_SUPPORTING,
    EVIDENCE_ROLE_CONTRADICTING,
    EVIDENCE_ROLE_CONTEXTUAL,
)
from knowledge.causal.graph import CausalGraph


_DEFAULT_THRESHOLDS: dict[str, float] = {
    "causation_min_confidence": 0.65,
    "causation_min_strength": 0.5,
    "causation_min_evidence": 2,
    "correlation_min_confidence": 0.4,
    "correlation_min_strength": 0.3,
    "coincidence_max_confidence": 0.3,
    "high_confidence": 0.7,
    "moderate_confidence": 0.5,
}


class CausalAnalyzer:
    def __init__(self, thresholds: dict[str, float] | None = None):
        self._thresholds = {**_DEFAULT_THRESHOLDS, **(thresholds or {})}

    # ── Core analysis ────────────────────────────────────────────────────────

    def analyze_relation(
        self,
        relation_id: str,
        source_id: str,
        target_id: str,
        source_evidence: list[dict],
        target_evidence: list[dict],
    ) -> CausalRelation:
        source_returns = [e.get("average_return_pct", 0.0) for e in source_evidence]
        target_returns = [e.get("average_return_pct", 0.0) for e in target_evidence]
        source_conf = [e.get("confidence", 0.0) for e in source_evidence]
        target_conf = [e.get("confidence", 0.0) for e in target_evidence]
        source_horizons = [e.get("horizon_days", 0) for e in source_evidence]
        target_horizons = [e.get("horizon_days", 0) for e in target_evidence]

        avg_source_return = sum(source_returns) / max(len(source_returns), 1)
        avg_target_return = sum(target_returns) / max(len(target_returns), 1)
        avg_source_conf = sum(source_conf) / max(len(source_conf), 1)
        avg_target_conf = sum(target_conf) / max(len(target_conf), 1)

        combined_evidence = source_evidence + target_evidence
        avg_horizon = (
            sum(source_horizons + target_horizons)
            / max(len(source_horizons + target_horizons), 1)
        )
        total_evidence = len(combined_evidence)

        directional_consistency = self._compute_directional_consistency(
            source_returns, target_returns,
        )
        co_movement = self._compute_co_movement(
            source_returns, target_returns,
        )
        avg_confidence = (avg_source_conf + avg_target_conf) / 2

        evidence_ids = tuple(
            e.get("evidence_id", f"ev_{i}")
            for i, e in enumerate(combined_evidence)
        )

        if (
            directional_consistency >= self._thresholds["causation_min_strength"]
            and avg_confidence >= self._thresholds["causation_min_confidence"]
            and total_evidence >= self._thresholds["causation_min_evidence"]
        ):
            relation_type = RELATION_CAUSATION
            direction = DIRECTION_SOURCE_TO_TARGET
            strength = directional_consistency
            explanation = (
                f"Source '{source_id}' shows directional consistency "
                f"of {directional_consistency:.2f} with target '{target_id}' "
                f"across {total_evidence} evidence items "
                f"(confidence {avg_confidence:.2f}, avg horizon {avg_horizon:.0f}d)"
            )
        elif (
            co_movement >= self._thresholds["correlation_min_strength"]
            and avg_confidence >= self._thresholds["correlation_min_confidence"]
        ):
            relation_type = RELATION_CORRELATION
            direction = DIRECTION_BIDIRECTIONAL
            strength = co_movement
            explanation = (
                f"Source '{source_id}' and target '{target_id}' show "
                f"co-movement of {co_movement:.2f} across {total_evidence} "
                f"evidence items (confidence {avg_confidence:.2f})"
            )
        else:
            relation_type = RELATION_COINCIDENCE
            direction = DIRECTION_UNKNOWN
            strength = co_movement
            explanation = (
                f"Relationship between '{source_id}' and '{target_id}' "
                f"appears coincidental: directional {directional_consistency:.2f}, "
                f"co-movement {co_movement:.2f}, "
                f"confidence {avg_confidence:.2f}, evidence count {total_evidence}"
            )

        return CausalRelation(
            relation_id=relation_id,
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            strength=strength,
            confidence=avg_confidence,
            direction=direction,
            evidence_ids=evidence_ids,
            temporal_lag=int(avg_horizon),
            explanation=explanation,
        )

    def create_hypothesis(
        self,
        hypothesis_id: str,
        name: str,
        description: str,
        cause_node_id: str,
        effect_node_id: str,
        evidence_list: list[CausalEvidence],
        graph: CausalGraph | None = None,
    ) -> CausalHypothesis:
        supporting_ids: list[str] = []
        contradicting_ids: list[str] = []
        for ce in evidence_list:
            if ce.role == EVIDENCE_ROLE_SUPPORTING:
                supporting_ids.append(ce.evidence_id)
            elif ce.role == EVIDENCE_ROLE_CONTRADICTING:
                contradicting_ids.append(ce.evidence_id)

        confidence = self._compute_hypothesis_confidence(
            evidence_list,
        )

        hypothesis = CausalHypothesis(
            hypothesis_id=hypothesis_id,
            name=name,
            description=description,
            cause_node_id=cause_node_id,
            effect_node_id=effect_node_id,
            direction="cause_to_effect",
            status=HYPOTHESIS_PROPOSED,
            supporting_evidence_ids=tuple(supporting_ids),
            contradicting_evidence_ids=tuple(contradicting_ids),
            confidence=confidence,
        )

        if graph is not None:
            graph.add_hypothesis(hypothesis)
            for ce in evidence_list:
                graph.add_causal_evidence(ce)

        return hypothesis

    def update_hypothesis_with_evidence(
        self,
        hypothesis: CausalHypothesis,
        new_evidence: list[CausalEvidence],
        graph: CausalGraph | None = None,
    ) -> CausalHypothesis:
        sup_ids = set(hypothesis.supporting_evidence_ids)
        con_ids = set(hypothesis.contradicting_evidence_ids)
        all_evidence = list(graph.evidence_for_hypothesis(hypothesis.hypothesis_id)) if graph else []

        existing = {ce.causal_evidence_id for ce in all_evidence}
        for ce in new_evidence:
            if ce.causal_evidence_id not in existing:
                all_evidence.append(ce)
                if ce.role == EVIDENCE_ROLE_SUPPORTING:
                    sup_ids.add(ce.evidence_id)
                elif ce.role == EVIDENCE_ROLE_CONTRADICTING:
                    con_ids.add(ce.evidence_id)
                if graph is not None:
                    graph.add_causal_evidence(ce)

        confidence = self._compute_hypothesis_confidence(all_evidence)
        status = graph.evaluate_hypothesis(hypothesis.hypothesis_id) if graph else HYPOTHESIS_PROPOSED

        return CausalHypothesis(
            hypothesis_id=hypothesis.hypothesis_id,
            name=hypothesis.name,
            description=hypothesis.description,
            cause_node_id=hypothesis.cause_node_id,
            effect_node_id=hypothesis.effect_node_id,
            direction=hypothesis.direction,
            status=status if status else HYPOTHESIS_PROPOSED,
            supporting_evidence_ids=tuple(sorted(sup_ids)),
            contradicting_evidence_ids=tuple(sorted(con_ids)),
            confidence=confidence,
            created_at=hypothesis.created_at,
            metadata=hypothesis.metadata,
        )

    # ── Private helpers ──────────────────────────────────────────────────────

    def _compute_directional_consistency(
        self,
        source_returns: list[float],
        target_returns: list[float],
    ) -> float:
        if not source_returns or not target_returns:
            return 0.0
        pairs = min(len(source_returns), len(target_returns))
        consistent = 0
        for i in range(pairs):
            src = source_returns[i]
            tgt = target_returns[i]
            if (src > 0 and tgt > 0) or (src < 0 and tgt < 0):
                consistent += 1
            if src > 0 and tgt < 0:
                consistent -= 0.5
            if src < 0 and tgt > 0:
                consistent -= 0.5
        return max(0.0, consistent / max(pairs, 1))

    def _compute_co_movement(
        self,
        source_returns: list[float],
        target_returns: list[float],
    ) -> float:
        if not source_returns or not target_returns:
            return 0.0
        pairs = min(len(source_returns), len(target_returns))
        same_direction = 0
        for i in range(pairs):
            src = source_returns[i]
            tgt = target_returns[i]
            if (src >= 0 and tgt >= 0) or (src < 0 and tgt < 0):
                same_direction += 1
        return same_direction / max(pairs, 1) if pairs > 0 else 0.0

    def _compute_hypothesis_confidence(
        self,
        evidence_list: list[CausalEvidence],
    ) -> float:
        if not evidence_list:
            return 0.0
        total = 0.0
        for ce in evidence_list:
            if ce.role == EVIDENCE_ROLE_SUPPORTING:
                total += abs(ce.strength)
            elif ce.role == EVIDENCE_ROLE_CONTRADICTING:
                total -= abs(ce.strength)
        return max(-1.0, min(1.0, total / len(evidence_list)))

    @property
    def thresholds(self) -> dict[str, float]:
        return dict(self._thresholds)
