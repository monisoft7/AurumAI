from __future__ import annotations

from typing import Any

from thesis_construction.contracts import InvestmentThesis


class ThesisRanker:
    """Ranks competing theses by institutional support descending."""

    @staticmethod
    def rank(theses: list[InvestmentThesis]) -> tuple[list[InvestmentThesis], list[str]]:
        sorted_theses = sorted(theses, key=lambda t: t.institutional_support, reverse=True)
        ranked_ids = [t.thesis_id for t in sorted_theses]
        return sorted_theses, ranked_ids
