from __future__ import annotations

from collections import Counter
from typing import Any

from evidence_collection.contracts import Evidence
from evidence_reasoning.contracts import OPPOSITE_BIAS, EvidenceSet


class EvidenceDetector:
    """Detects supporting, contradicting, duplicate, and correlated evidence.

    For a group of evidence items with the same event_type:
    - Supporting: bias matches the majority bias of the set
    - Contradicting: bias is the opposite of majority bias
    - Correlated: evidence from the same instrument across different event_types
    """

    @staticmethod
    def analyze_group(
        evidence_group: list[Evidence],
        set_id: str,
        event_type: str,
        duplicate_ids: list[str],
    ) -> EvidenceSet:
        if not evidence_group:
            return EvidenceSet(
                set_id=set_id,
                event_type=event_type,
                bias="neutral",
            )

        bias_counts = Counter(ev.bias for ev in evidence_group)
        majority_bias = bias_counts.most_common(1)[0][0]
        opposite = OPPOSITE_BIAS.get(majority_bias, "")

        evidence_ids: list[str] = []
        supporting_ids: list[str] = []
        contradicting_ids: list[str] = []
        duplicate_in_group: list[str] = [d for d in duplicate_ids if d in {e.evidence_id for e in evidence_group}]
        provenance_chain: list[Any] = []
        instruments: set[str] = set()

        for ev in evidence_group:
            evidence_ids.append(ev.evidence_id)
            if ev.provenance is not None:
                provenance_chain.append(ev.provenance)
            instruments.add(ev.metadata.get("instrument", ""))

            if ev.bias == majority_bias:
                supporting_ids.append(ev.evidence_id)
            elif opposite and ev.bias == opposite:
                contradicting_ids.append(ev.evidence_id)
            elif majority_bias in {"bullish", "bearish"} and ev.bias in {"neutral", "mixed"}:
                contradicting_ids.append(ev.evidence_id)
            else:
                supporting_ids.append(ev.evidence_id)

        return EvidenceSet(
            set_id=set_id,
            event_type=event_type,
            bias=majority_bias,
            evidence_ids=tuple(evidence_ids),
            supporting_evidence_ids=tuple(supporting_ids),
            contradicting_evidence_ids=tuple(contradicting_ids),
            duplicate_evidence_ids=tuple(duplicate_in_group),
            metadata={
                "instrument_count": len(instruments),
                "instruments": sorted(instruments),
                "bias_distribution": dict(bias_counts),
            },
            provenance_chain=tuple(provenance_chain),
        )

    @staticmethod
    def correlated_event_types(evidence_items: list[Evidence]) -> dict[str, list[str]]:
        """Detect correlated groupings: same instrument across event_types."""
        instr_to_types: dict[str, set[str]] = {}
        for ev in evidence_items:
            instr = ev.metadata.get("instrument", "unknown")
            instr_to_types.setdefault(instr, set()).add(ev.event_type)

        return {instr: sorted(types) for instr, types in instr_to_types.items() if len(types) > 1}
