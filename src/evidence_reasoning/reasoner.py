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
        historical_analogue: Any | None = None,
    ) -> EvidenceReasoning:
        evidence_items = list(collection.items)
        regime = regime or collection.regime

        # Run-003 repair (Phase 8): the historical analogue adjudication
        # (existing Correction-028 engine output) becomes ONE bounded,
        # provenance-carrying evidence item in the dedicated
        # HISTORICAL_MEMORY channel through the shared
        # ``build_memory_evidence`` adapter.  The matched episodes are the
        # inputs of ONE estimator, never several votes; mixed / flat history
        # maps to an uninformative bias.  When no payload is supplied
        # (NO_HISTORY ablation) no item exists and the reasoning is
        # identical to a memory-less run.
        adjudication: dict[str, Any] | None = None
        if historical_analogue is not None:
            from evidence_reasoning.historical_adjudication import (
                build_historical_adjudication,
            )

            adjudication = build_historical_adjudication(historical_analogue)
            if adjudication is not None:
                from evidence_collection.desk_evidence import build_memory_evidence

                memory_item = build_memory_evidence(
                    adjudication, historical_analogue
                )
                if memory_item is not None:
                    evidence_items.append(memory_item)

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
        factor_rationale = build_cross_factor_rationale(regime=regime)
        if factor_rationale is not None:
            metadata["factor_rationale"] = factor_rationale

        # Run-003 repair (Phase 8): the analogue payload is carried verbatim
        # in metadata for explanation.  Its directional content additionally
        # enters scoring through the SINGLE bounded HISTORICAL_MEMORY
        # evidence item built above (never through a numeric metadata
        # weight).  When absent, the reasoning is identical to a memory-less
        # run.
        if historical_analogue is not None:
            metadata["historical_analogue"] = historical_analogue

        # Correction 028: explanation-only adjudication of the analogue via
        # the existing LegacyReasoningEngine.  Stored in metadata only; the
        # temporary Evidence adapter never enters this collection path.
        # Run-003 repair (Phase 8): the SAME adjudication additionally feeds
        # the single bounded HISTORICAL_MEMORY evidence item above; the
        # metadata copy below preserves the explanation-only record verbatim.
        if historical_analogue is not None:
            if adjudication is not None:
                metadata["historical_adjudication"] = adjudication

                # Correction 030: explanation-only contextual interpretation
                # joining the adjudication, the current factor rationale and
                # the current query.  Stored in metadata only; feeds no
                # scoring field.
                from evidence_reasoning.contextual_historical_adjudication import (
                    build_contextual_historical_adjudication,
                )

                query = (
                    historical_analogue.get("query")
                    if isinstance(historical_analogue, dict)
                    else None
                )
                contextual = build_contextual_historical_adjudication(
                    adjudication,
                    metadata.get("factor_rationale"),
                    query,
                )
                if contextual is not None:
                    metadata["contextual_historical_adjudication"] = contextual

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
