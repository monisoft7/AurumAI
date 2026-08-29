from __future__ import annotations

from typing import Any

from evidence_reasoning.contracts import EvidenceReasoning, EvidenceSet, OPPOSITE_BIAS

# Expected event types per regime for missing-evidence detection
REGIME_EXPECTED_EVENT_TYPES: dict[str, set[str]] = {
    "NORMAL_GROWTH": {"REAL_YIELD", "USD_FX", "INFLATION", "ETF_FLOW"},
    "INFLATIONARY": {"INFLATION", "REAL_YIELD", "USD_FX", "CB_GOLD"},
    "STAGFLATIONARY": {"INFLATION", "REAL_YIELD", "USD_FX", "GENERAL"},
    "DEFLATIONARY_CRISIS": {"REAL_YIELD", "USD_FX", "GENERAL", "ETF_FLOW"},
    "GEOPOLITICAL_STRESS": {"GEOPOLITICAL", "CB_GOLD", "USD_FX", "ETF_FLOW"},
    "STRUCTURAL_REGIME_CHANGE": {"REAL_YIELD", "USD_FX", "INFLATION", "GENERAL"},
}

# Event types that have an admitted evidence producer (instrument scanners and
# knowledge/news ingestion). An admitted channel absent from the evidence sets
# reflects upstream filtering, not an unavailable pipeline, so it must not be
# treated as missing evidence. Only channels with no producer (e.g., CB_GOLD)
# remain eligible as missing expected evidence.
# (docs/design/COUNTER_EVIDENCE_CORRECTION_V1.md, section 3.6)
ADMITTED_EVIDENCE_CHANNELS: set[str] = {
    "GENERAL",
    "USD_FX",
    "REAL_YIELD",
    "INFLATION",
    "ETF_FLOW",
    "GEOPOLITICAL",
}

# Regime-to-expected-bias mapping (ARCHIVED — no longer feeds scoring).
#
# Run-003 repair (Phase 7): the repository contains no as-of
# regime-conditional outcome archive from which a directional regime prior
# could be estimated without look-ahead, so the fixed directional prior this
# map once expressed is NEUTRALIZED everywhere it fed scoring:
#   * W7 ``regime_conflict`` — disabled (returns False),
#   * W9 ``regime_alignment`` channel — removed from the confidence weights,
#   * W10 ``regime_blindness`` directional check — disabled.
# Regime remains context (labels, evidence regime_weight, regime_path risk)
# but no longer acts as an unvalidated directional oracle.  The constant is
# retained verbatim for provenance/compatibility and MUST NOT be re-wired
# into any scoring path without an as-of-validated prior.
REGIME_EXPECTED_BIAS: dict[str, str] = {
    "NORMAL_GROWTH": "bullish",
    "INFLATIONARY": "bullish",
    "STAGFLATIONARY": "bearish",
    "DEFLATIONARY_CRISIS": "bearish",
    "GEOPOLITICAL_STRESS": "bullish",
    "STRUCTURAL_REGIME_CHANGE": "neutral",
}


class ConflictDetector:
    """Detects cross-set conflicts, regime conflicts, temporal conflicts,
    and source concentration.

    Run-003 repair (Phase 3): the cross-set majority is the weighted-mass
    direction of the sets (each set weighted by its existing
    ``net_institutional_weight``), replacing the count-based plurality vote
    and its insertion-order tie-breaking.  An exact mass balance carries no
    directional majority: nothing supports and nothing contradicts.
    """

    @staticmethod
    def cross_set_conflicts(
        evidence_sets: tuple[EvidenceSet, ...],
    ) -> tuple[list[str], list[str], list[str]]:
        """Returns (contradicting_set_ids, supporting_set_ids, conflict_pairs).

        A set contradicts if its bias opposes the weighted-mass majority
        bias across all sets.  A set whose bias is neutral carries no proven
        directional polarity (Correction 060), so it is uninformative
        against a directional majority: it enters neither supporting nor
        contradicting and casts no directional vote.
        """
        if not evidence_sets:
            return [], [], []

        bull_mass = 0.0
        bear_mass = 0.0
        for es in evidence_sets:
            w = es.net_institutional_weight
            if w != w or w in (float("inf"), float("-inf")):
                continue
            w = max(0.0, float(w))
            if es.bias == "bullish":
                bull_mass += w
            elif es.bias == "bearish":
                bear_mass += w
            elif es.bias == "mixed":
                bull_mass += w * 0.5
                bear_mass += w * 0.5

        if bull_mass == 0.0 and bear_mass == 0.0:
            return [], [], []
        if bull_mass == bear_mass:
            # Exact directional balance: no majority, no conflict attribution.
            return [], [], []
        majority_bias = "bullish" if bull_mass > bear_mass else "bearish"
        opposite = OPPOSITE_BIAS.get(majority_bias, "")

        supporting: list[str] = []
        contradicting: list[str] = []
        pairs: list[str] = []

        for es in evidence_sets:
            if es.bias == majority_bias:
                supporting.append(es.set_id)
            elif opposite and es.bias == opposite:
                contradicting.append(es.set_id)
                pairs.append(f"{es.set_id}_vs_{majority_bias}")
            elif es.bias == "mixed":
                contradicting.append(es.set_id)
                pairs.append(f"{es.set_id}_vs_{majority_bias}")

        return contradicting, supporting, pairs

    @staticmethod
    def regime_conflict(
        evidence_sets: tuple[EvidenceSet, ...],
        regime: str,
    ) -> bool:
        """Run-003 repair (Phase 7): neutralized.

        The fixed REGIME_EXPECTED_BIAS prior had no as-of validation, so the
        directional influence it produced (a +0.1 confidence penalty on any
        set opposing the hardcoded regime bias, which systematically
        penalized one side — e.g. all bearish evidence in INFLATIONARY
        regimes) is disabled.  Returns False unconditionally; regime remains
        context only.  See the REGIME_EXPECTED_BIAS docstring.
        """
        return False

    @staticmethod
    def source_concentration(
        evidence_sets: tuple[EvidenceSet, ...],
    ) -> bool:
        return len(evidence_sets) <= 1

    @staticmethod
    def missing_event_types(
        evidence_sets: tuple[EvidenceSet, ...],
        regime: str,
    ) -> list[str]:
        """Returns expected channels that are genuinely unavailable.

        Channels with an admitted evidence producer are not reported as missing
        even when absent from the current evidence sets, because their absence
        reflects upstream filtering rather than an unavailable evidence channel.
        (docs/design/COUNTER_EVIDENCE_CORRECTION_V1.md, section 3.6)
        """
        present = {es.event_type for es in evidence_sets}
        expected = REGIME_EXPECTED_EVENT_TYPES.get(regime, set())
        return sorted(expected - present - ADMITTED_EVIDENCE_CHANNELS)
