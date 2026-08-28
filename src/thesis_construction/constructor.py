from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from counter_evidence.contracts import CounterEvidenceAssessment
from evidence_reasoning.contracts import EvidenceReasoning, OPPOSITE_BIAS
from thesis_construction.builder import ThesisBuilder
from thesis_construction.contracts import InvestmentThesis, ThesisConstruction
from thesis_construction.ranker import ThesisRanker


class ThesisConstructor:
    """Orchestrates W8: determines competing directions, builds theses,
    ranks by institutional support, produces ThesisConstruction."""

    def __init__(
        self,
        builder: ThesisBuilder | None = None,
        ranker: ThesisRanker | None = None,
    ) -> None:
        self._builder = builder or ThesisBuilder()
        self._ranker = ranker or ThesisRanker()

    def construct(
        self,
        reasoning: EvidenceReasoning,
        assessment: CounterEvidenceAssessment,
        technical_context: dict[str, Any] | None = None,
    ) -> ThesisConstruction:
        """Build the candidate thesis set.

        ``technical_context`` (Final Hardening, Group F / D-07): compact,
        non-scoring research context from the Technical Research Desk
        (trend/structure/confirmations/contradictions).  It is recorded on
        each thesis's metadata so the research layer can reason with it --
        it never enters institutional_support, confidence, or selection.
        """
        directions = self._determine_thesis_directions(reasoning, assessment)
        theses: list[InvestmentThesis] = []

        for direction in directions:
            supporting_ids = self._supporting_set_ids(reasoning, direction)
            counter_ids = self._counter_set_ids(reasoning, assessment, direction)
            thesis = self._builder.build_thesis(
                direction=direction,
                reasoning=reasoning,
                assessment=assessment,
                supporting_set_ids=supporting_ids,
                counter_set_ids=counter_ids,
                technical_context=technical_context,
            )
            theses.append(thesis)

        sorted_theses, ranked_ids = self._ranker.rank(theses)

        primary_id = ranked_ids[0] if ranked_ids else ""

        return ThesisConstruction(
            construction_id=f"tc_{uuid4().hex[:12]}",
            reasoning_id=reasoning.reasoning_id,
            assessment_id=assessment.assessment_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            regime=reasoning.regime,
            theses=tuple(sorted_theses),
            ranked_thesis_ids=tuple(ranked_ids),
            total_theses=len(sorted_theses),
            primary_thesis_id=primary_id,
            metadata={
                "directions_evaluated": len(directions),
                "total_evidence_sets": len(reasoning.evidence_sets),
            },
        )

    @staticmethod
    def _determine_thesis_directions(
        reasoning: EvidenceReasoning,
        assessment: CounterEvidenceAssessment,
    ) -> list[str]:
        bias_counts: Counter[str] = Counter()
        for es in reasoning.evidence_sets:
            if es.bias:
                bias_counts[es.bias] += 1

        if not bias_counts:
            return ["neutral"]

        directions: list[str] = list(bias_counts.keys())

        has_bullish = "bullish" in directions
        has_bearish = "bearish" in directions

        if has_bullish and has_bearish:
            return ["bullish", "bearish", "neutral"]
        if has_bullish:
            return ["bullish", "neutral"]
        if has_bearish:
            return ["bearish", "neutral"]
        return ["neutral"]

    @staticmethod
    def _supporting_set_ids(
        reasoning: EvidenceReasoning,
        direction: str,
    ) -> list[str]:
        return [
            es.set_id for es in reasoning.evidence_sets
            if es.bias == direction
        ]

    @staticmethod
    def _counter_set_ids(
        reasoning: EvidenceReasoning,
        assessment: CounterEvidenceAssessment,
        direction: str,
    ) -> list[str]:
        opposite = OPPOSITE_BIAS.get(direction, "")
        opposing = [
            es.set_id for es in reasoning.evidence_sets
            if opposite and es.bias == opposite
        ]
        contra = list(assessment.contradicting_set_ids)
        combined = list(set(opposing + contra))
        return combined
