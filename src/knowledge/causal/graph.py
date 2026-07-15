from __future__ import annotations

from knowledge.causal.relation import CausalRelation
from knowledge.causal.hypothesis import (
    CausalHypothesis,
    HYPOTHESIS_PROPOSED,
    HYPOTHESIS_SUPPORTED,
    HYPOTHESIS_CONTRADICTED,
    HYPOTHESIS_INCONCLUSIVE,
)
from knowledge.causal.evidence import (
    CausalEvidence,
    EVIDENCE_ROLE_SUPPORTING,
    EVIDENCE_ROLE_CONTRADICTING,
)


class CausalGraph:
    def __init__(self) -> None:
        self._relations: dict[str, CausalRelation] = {}
        self._hypotheses: dict[str, CausalHypothesis] = {}
        self._causal_evidence: dict[str, CausalEvidence] = {}

    # ── Relations ────────────────────────────────────────────────────────────

    def add_relation(self, relation: CausalRelation) -> None:
        self._relations[relation.relation_id] = relation

    def get_relation(self, relation_id: str) -> CausalRelation | None:
        return self._relations.get(relation_id)

    def relations_between(
        self,
        source_id: str,
        target_id: str,
    ) -> list[CausalRelation]:
        return [
            r for r in self._relations.values()
            if (r.source_id == source_id and r.target_id == target_id)
            or (r.source_id == target_id and r.target_id == source_id)
        ]

    def relations_from(self, node_id: str) -> list[CausalRelation]:
        return [r for r in self._relations.values() if r.source_id == node_id]

    def relations_to(self, node_id: str) -> list[CausalRelation]:
        return [r for r in self._relations.values() if r.target_id == node_id]

    def all_relations(self) -> list[CausalRelation]:
        return list(self._relations.values())

    def relation_count(self) -> int:
        return len(self._relations)

    def remove_relation(self, relation_id: str) -> None:
        self._relations.pop(relation_id, None)

    # ── Hypotheses ───────────────────────────────────────────────────────────

    def add_hypothesis(self, hypothesis: CausalHypothesis) -> None:
        self._hypotheses[hypothesis.hypothesis_id] = hypothesis

    def get_hypothesis(self, hypothesis_id: str) -> CausalHypothesis | None:
        return self._hypotheses.get(hypothesis_id)

    def hypotheses_for(
        self,
        cause_node_id: str,
        effect_node_id: str,
    ) -> list[CausalHypothesis]:
        return [
            h for h in self._hypotheses.values()
            if h.cause_node_id == cause_node_id
            and h.effect_node_id == effect_node_id
        ]

    def competing_hypotheses(
        self,
        cause_node_id: str,
        effect_node_id: str,
    ) -> list[CausalHypothesis]:
        return [
            h for h in self._hypotheses.values()
            if (h.cause_node_id == cause_node_id
                and h.effect_node_id == effect_node_id)
            or (h.cause_node_id == effect_node_id
                and h.effect_node_id == cause_node_id)
        ]

    def all_hypotheses(self) -> list[CausalHypothesis]:
        return list(self._hypotheses.values())

    def hypothesis_count(self) -> int:
        return len(self._hypotheses)

    # ── Causal Evidence ──────────────────────────────────────────────────────

    def add_causal_evidence(self, ce: CausalEvidence) -> None:
        self._causal_evidence[ce.causal_evidence_id] = ce

    def get_causal_evidence(self, causal_evidence_id: str) -> CausalEvidence | None:
        return self._causal_evidence.get(causal_evidence_id)

    def evidence_for_hypothesis(self, hypothesis_id: str) -> list[CausalEvidence]:
        return [
            ce for ce in self._causal_evidence.values()
            if ce.hypothesis_id == hypothesis_id
        ]

    def supporting_evidence(self, hypothesis_id: str) -> list[CausalEvidence]:
        return [
            ce for ce in self._causal_evidence.values()
            if ce.hypothesis_id == hypothesis_id
            and ce.role == EVIDENCE_ROLE_SUPPORTING
        ]

    def contradicting_evidence(self, hypothesis_id: str) -> list[CausalEvidence]:
        return [
            ce for ce in self._causal_evidence.values()
            if ce.hypothesis_id == hypothesis_id
            and ce.role == EVIDENCE_ROLE_CONTRADICTING
        ]

    def all_causal_evidence(self) -> list[CausalEvidence]:
        return list(self._causal_evidence.values())

    def causal_evidence_count(self) -> int:
        return len(self._causal_evidence)

    # ── Analysis helpers ─────────────────────────────────────────────────────

    def evaluate_hypothesis(self, hypothesis_id: str) -> str | None:
        hypothesis = self._hypotheses.get(hypothesis_id)
        if hypothesis is None:
            return None

        supporting = self.supporting_evidence(hypothesis_id)
        contradicting = self.contradicting_evidence(hypothesis_id)

        if not supporting and not contradicting:
            return HYPOTHESIS_PROPOSED
        if not supporting and contradicting:
            return HYPOTHESIS_CONTRADICTED
        if supporting and not contradicting:
            sup_confidence = sum(ce.strength for ce in supporting) / len(supporting)
            if sup_confidence >= 0.5:
                return HYPOTHESIS_SUPPORTED
            return HYPOTHESIS_INCONCLUSIVE

        sup_avg = sum(ce.strength for ce in supporting) / len(supporting)
        con_avg = sum(ce.strength for ce in contradicting) / len(contradicting)
        if sup_avg > con_avg and sup_avg >= 0.5:
            return HYPOTHESIS_SUPPORTED
        if con_avg > sup_avg and con_avg >= 0.5:
            return HYPOTHESIS_CONTRADICTED
        return HYPOTHESIS_INCONCLUSIVE

    def clear(self) -> None:
        self._relations.clear()
        self._hypotheses.clear()
        self._causal_evidence.clear()
