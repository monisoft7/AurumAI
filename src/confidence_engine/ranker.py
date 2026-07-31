from __future__ import annotations

from typing import Any

from confidence_engine.computer import ConfidenceComputer
from thesis_construction.contracts import InvestmentThesis

OPPOSITE_DIRECTIONS: dict[str, str] = {
    "bullish": "bearish",
    "bearish": "bullish",
}


class ConfidenceRanker:
    """Ranks theses by confidence, detects low-confidence theses, and
    conflicting high-confidence thesis pairs."""

    def __init__(self, computer: ConfidenceComputer | None = None) -> None:
        self._computer = computer or ConfidenceComputer()

    def rank_by_confidence(
        self,
        thesis_confidence: list[dict[str, Any]],
    ) -> list[str]:
        ordered = sorted(
            thesis_confidence,
            key=lambda tc: tc.get("final_confidence", 0.0),
            reverse=True,
        )
        return [tc["thesis_id"] for tc in ordered]

    def detect_low_confidence(
        self,
        thesis_confidence: list[dict[str, Any]],
        threshold: float = 0.35,
    ) -> list[str]:
        return [
            tc["thesis_id"]
            for tc in thesis_confidence
            if tc.get("final_confidence", 0.0) < threshold
        ]

    def detect_conflicting_high_confidence(
        self,
        theses: list[InvestmentThesis],
        thesis_confidence: list[dict[str, Any]],
        threshold: float = 0.60,
    ) -> list[tuple[str, str]]:
        conf_map = {tc["thesis_id"]: tc for tc in thesis_confidence}
        direction_map = {t.thesis_id: t.direction for t in theses}

        pairs: list[tuple[str, str]] = []
        ids = [t.thesis_id for t in theses]
        for i, tid in enumerate(ids):
            for j in range(i + 1, len(ids)):
                other = ids[j]
                dir_a = direction_map.get(tid, "")
                dir_b = direction_map.get(other, "")
                if dir_a != OPPOSITE_DIRECTIONS.get(dir_b, ""):
                    continue
                conf_a = conf_map.get(tid, {}).get("final_confidence", 0.0)
                conf_b = conf_map.get(other, {}).get("final_confidence", 0.0)
                if conf_a >= threshold and conf_b >= threshold:
                    pairs.append((tid, other))
        return pairs
