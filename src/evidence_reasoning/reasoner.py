from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from evidence_collection.contracts import Evidence, EvidenceCollection
from evidence_reasoning.contracts import EvidenceReasoning, EvidenceSet
from evidence_reasoning.cross_factor_rationale import build_cross_factor_rationale
from evidence_reasoning.detector import EvidenceDetector
from evidence_reasoning.grouper import EvidenceGrouper
from evidence_reasoning.knowledge_rationale import build_knowledge_rationale
from evidence_reasoning.weighter import EvidenceWeighter


class EvidenceReasoner:
    """Orchestrates W6: group → detect → weight → produce EvidenceReasoning."""

    def __init__(
        self,
        grouper: EvidenceGrouper | None = None,
        detector: EvidenceDetector | None = None,
        weighter: EvidenceWeighter | None = None,
    ) -> None:
        self._grouper = grouper or EvidenceGrouper()
        self._detector = detector or EvidenceDetector()
        self._weighter = weighter or EvidenceWeighter()

    def reason(
        self,
        collection: EvidenceCollection,
        regime: str | None = None,
    ) -> EvidenceReasoning:
        evidence_items = list(collection.items)
        regime = regime or collection.regime

        groups, duplicate_ids = self._grouper.group(evidence_items)
        all_duplicates = duplicate_ids[:]

        evidence_sets: list[EvidenceSet] = []
        for g in groups:
            event_type = g[0].event_type if g else "GENERAL"
            set_id = EvidenceGrouper.assign_set_id(event_type)
            raw_set = self._detector.analyze_group(g, set_id, event_type, all_duplicates)
            weighted_set = self._weighter.weight_set(raw_set, evidence_items)
            weighted_set = self._attach_knowledge_rationale(weighted_set, evidence_items)
            evidence_sets.append(weighted_set)

        total_items = sum(len(s.evidence_ids) for s in evidence_sets)

        metadata: dict[str, Any] = {
            "collection_items": len(evidence_items),
            "groups_formed": len(evidence_sets),
        }
        factor_rationale = build_cross_factor_rationale()
        if factor_rationale is not None:
            metadata["factor_rationale"] = factor_rationale

        reasoning = EvidenceReasoning(
            reasoning_id=f"er_{uuid4().hex[:12]}",
            collection_id=collection.collection_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            regime=regime,
            evidence_sets=tuple(evidence_sets),
            total_evidence_sets=len(evidence_sets),
            total_evidence_items=total_items,
            duplicates_removed=len(all_duplicates),
            metadata=metadata,
        )
        return reasoning

    @staticmethod
    def _attach_knowledge_rationale(
        weighted_set: EvidenceSet,
        evidence_items: list[Evidence],
    ) -> EvidenceSet:
        """Mirror the preserved KR semantics as explanation-only rationale.

        Correction 008-B: when a set contains real KnowledgeRecord evidence the
        deterministic rationale (produced by the legacy ReasoningEngine) is
        carried in ``set.metadata["knowledge_rationale"]`` for downstream
        explanation composition.  It feeds no scoring field, so the weighted
        set's numeric state is unchanged.
        """
        group = [
            e for e in evidence_items if e.evidence_id in weighted_set.evidence_ids
        ]
        rationale = build_knowledge_rationale(group)
        if not rationale:
            return weighted_set
        d = weighted_set.to_dict()
        d["metadata"] = dict(d["metadata"])
        d["metadata"]["knowledge_rationale"] = rationale
        return EvidenceSet.from_dict(d)
