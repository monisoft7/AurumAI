from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from evidence_collection.contracts import Evidence, EvidenceCollection
from evidence_reasoning.contracts import EvidenceReasoning, EvidenceSet
from evidence_reasoning.detector import EvidenceDetector
from evidence_reasoning.grouper import EvidenceGrouper
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
            evidence_sets.append(weighted_set)

        total_items = sum(len(s.evidence_ids) for s in evidence_sets)

        reasoning = EvidenceReasoning(
            reasoning_id=f"er_{uuid4().hex[:12]}",
            collection_id=collection.collection_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            regime=regime,
            evidence_sets=tuple(evidence_sets),
            total_evidence_sets=len(evidence_sets),
            total_evidence_items=total_items,
            duplicates_removed=len(all_duplicates),
            metadata={
                "collection_items": len(evidence_items),
                "groups_formed": len(evidence_sets),
            },
        )
        return reasoning
