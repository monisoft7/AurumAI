from __future__ import annotations

from typing import Any

from evidence_collection.contracts import Evidence
from evidence_reasoning.contracts import OPPOSITE_BIAS, EvidenceSet


# Run-003 repair (Phase 3): directional mass shares. A "mixed" item carries
# bidirectional signal, so its weight is split evenly across both sides
# instead of behaving as a pure vote for whichever side it lands on.
MIXED_MASS_SPLIT = 0.5


def directional_masses(items: list[Evidence]) -> tuple[float, float]:
    """Weighted bullish/bearish mass over the given items.

    Weights are the existing ``composite_weight`` masses. Non-finite weights
    contribute nothing. Mixed evidence contributes to both sides at
    ``MIXED_MASS_SPLIT``. Neutral evidence contributes to neither side:
    neutral is uninformative, not a third competing direction.
    """
    bull = 0.0
    bear = 0.0
    for ev in items:
        w = ev.composite_weight
        if w != w or w in (float("inf"), float("-inf")):  # NaN / inf guard
            continue
        w = max(0.0, float(w))
        if ev.bias == "bullish":
            bull += w
        elif ev.bias == "bearish":
            bear += w
        elif ev.bias == "mixed":
            bull += w * MIXED_MASS_SPLIT
            bear += w * MIXED_MASS_SPLIT
    return bull, bear


def mass_bias(bull: float, bear: float) -> str:
    """Set direction from weighted masses: strict majority wins; exact mass
    balance with positive mass is ``mixed``; no directional mass is
    ``neutral``. No insertion-order tie-breaking exists.
    """
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    if bull > 0.0 and bear > 0.0:
        return "mixed"
    return "neutral"


class EvidenceDetector:
    """Detects supporting, contradicting, duplicate, and correlated evidence.

    Run-003 repair (Phase 3/4): the set direction is the weighted-mass
    direction of its deduplicated items (``directional_masses`` +
    ``mass_bias``), not a count-based plurality vote. Supporting /
    contradicting membership follows the established Correction-060
    semantics: matching bias supports, proven opposite polarity (or mixed
    against a directional majority) contradicts, and neutral evidence is
    uninformative -- it votes neither way and joins neither id list.
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

        bull_mass, bear_mass = directional_masses(evidence_group)
        majority_bias = mass_bias(bull_mass, bear_mass)
        opposite = OPPOSITE_BIAS.get(majority_bias, "")

        evidence_ids: list[str] = []
        supporting_ids: list[str] = []
        contradicting_ids: list[str] = []
        duplicate_in_group: list[str] = [d for d in duplicate_ids if d in {e.evidence_id for e in evidence_group}]
        provenance_chain: list[Any] = []
        instruments: set[str] = set()
        bias_distribution: dict[str, int] = {}

        for ev in evidence_group:
            evidence_ids.append(ev.evidence_id)
            if ev.provenance is not None:
                provenance_chain.append(ev.provenance)
            instruments.add(ev.metadata.get("instrument", ""))
            bias_distribution[ev.bias] = bias_distribution.get(ev.bias, 0) + 1

            if majority_bias in {"bullish", "bearish"}:
                if ev.bias == majority_bias:
                    supporting_ids.append(ev.evidence_id)
                elif opposite and ev.bias == opposite:
                    contradicting_ids.append(ev.evidence_id)
                elif ev.bias == "mixed":
                    contradicting_ids.append(ev.evidence_id)
                elif ev.bias == "neutral":
                    # Correction 060 semantics retained: neutral = uninformative.
                    pass
                else:
                    supporting_ids.append(ev.evidence_id)
            elif ev.bias == majority_bias and majority_bias:
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
                "bias_distribution": dict(bias_distribution),
                "directional_mass_bullish": round(bull_mass, 6),
                "directional_mass_bearish": round(bear_mass, 6),
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
