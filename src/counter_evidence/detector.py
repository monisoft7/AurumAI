from __future__ import annotations

from collections import Counter
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

# Regime-to-expected-bias mapping for regime-conflict detection
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
    and source concentration."""

    @staticmethod
    def cross_set_conflicts(
        evidence_sets: tuple[EvidenceSet, ...],
    ) -> tuple[list[str], list[str], list[str]]:
        """Returns (contradicting_set_ids, supporting_set_ids, conflict_pairs).

        A set contradicts if its bias opposes the majority bias across all sets.
        """
        if not evidence_sets:
            return [], [], []

        bias_counts: Counter[str] = Counter()
        for es in evidence_sets:
            if es.bias:
                bias_counts[es.bias] += 1

        if not bias_counts:
            return [], [es.set_id for es in evidence_sets], []

        majority_bias = bias_counts.most_common(1)[0][0]
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
            elif majority_bias in {"bullish", "bearish"} and es.bias in {"neutral", "mixed"}:
                contradicting.append(es.set_id)
                pairs.append(f"{es.set_id}_vs_{majority_bias}")

        return contradicting, supporting, pairs

    @staticmethod
    def regime_conflict(
        evidence_sets: tuple[EvidenceSet, ...],
        regime: str,
    ) -> bool:
        expected_bias = REGIME_EXPECTED_BIAS.get(regime, "neutral")
        if not expected_bias:
            return False
        opposite = OPPOSITE_BIAS.get(expected_bias, "")
        for es in evidence_sets:
            if opposite and es.bias == opposite:
                return True
        return False

    @staticmethod
    def temporal_conflicts(
        evidence_sets: tuple[EvidenceSet, ...],
        low_recency_threshold: float = 0.3,
    ) -> list[str]:
        flags: list[str] = []
        for es in evidence_sets:
            meta = es.metadata or {}
            bias_dist = meta.get("bias_distribution", {})
            if not bias_dist:
                continue
            total = sum(bias_dist.values())
            if total > 0 and es.conflict_score > low_recency_threshold:
                flags.append(es.set_id)
        return flags

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
        present = {es.event_type for es in evidence_sets}
        expected = REGIME_EXPECTED_EVENT_TYPES.get(regime, set())
        return sorted(expected - present)
