from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from confidence_engine.computer import ConfidenceComputer
from confidence_engine.contracts import InstitutionalConfidence, ThesisConfidence
from confidence_engine.ranker import ConfidenceRanker
from knowledge.integrity.provenance import Provenance
from thesis_construction.contracts import InvestmentThesis, ThesisConstruction


class ConfidenceEngine:
    """Orchestrates W9: computes confidence per thesis, ranks theses,
    detects low-confidence and conflicting high-confidence theses."""

    def __init__(
        self,
        computer: ConfidenceComputer | None = None,
        ranker: ConfidenceRanker | None = None,
    ) -> None:
        self._computer = computer or ConfidenceComputer()
        self._ranker = ranker or ConfidenceRanker()

    def evaluate(
        self,
        construction: ThesisConstruction,
        reasoning: Any | None = None,
        generation: Any | None = None,
        oos_ece: float | None = None,
    ) -> InstitutionalConfidence:
        """Evaluate confidence for every thesis.

        Additive spec inputs (all optional; behavior is unchanged when absent):
        - reasoning: W6 evidence (EvidenceReasoning) -- meta-evidence summary
          per thesis and the "why not priced in" evidentiary-basis answer.
        - generation: W12 output (ScenarioGeneration) -- Goldman Sachs
          3-question test; unanswered questions cap confidence at Medium.
        - oos_ece: OOS calibration error -- ECE > 0.15 caps at Medium,
          ECE > 0.25 caps at Low (W9 processing stage 5).
        """
        from evidence_reasoning.contracts import EvidenceReasoning
        from scenario_generation.contracts import ScenarioGeneration

        if reasoning is not None and not isinstance(reasoning, EvidenceReasoning):
            reasoning = EvidenceReasoning.from_dict(reasoning)
        if generation is not None and not isinstance(generation, ScenarioGeneration):
            generation = ScenarioGeneration.from_dict(generation)

        thesis_confidence: list[dict[str, Any]] = []
        theses_confidence: list[ThesisConfidence] = []

        prov = Provenance(
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="W9 ConfidenceEngine",
            entity_version="1.0.0",
        )

        for thesis in construction.theses:
            result = self._computer.compute(thesis)
            final = float(result["final_confidence"])
            gs_test = self._gs_test(thesis, generation)
            gs_cap = "medium" if (generation is not None and not gs_test["all_answered"]) else None
            oos_cap = self._oos_cap(oos_ece)

            if gs_cap == "medium":
                final = min(final, self._computer.HIGH_CONFIDENCE_THRESHOLD)
            if oos_cap == "low":
                final = min(final, self._computer.LOW_CONFIDENCE_THRESHOLD)
            elif oos_cap == "medium":
                final = min(final, self._computer.HIGH_CONFIDENCE_THRESHOLD)
            final = round(max(0.0, min(final, 1.0)), 4)

            metadata: dict[str, Any] = dict(result["metadata"])
            w6_evidence = self._w6_evidence(reasoning, thesis)
            if w6_evidence is not None:
                metadata["w6_evidence"] = w6_evidence
            if generation is not None:
                metadata["gs_test"] = gs_test
                metadata["gs_cap"] = gs_cap or "none"
            if oos_ece is not None:
                metadata["oos_calibration"] = {
                    "oos_ece": round(float(oos_ece), 4),
                    "cap_applied": oos_cap or "none",
                }

            chain = list(thesis.provenance_chain) + [prov]
            tc = ThesisConfidence(
                thesis_id=thesis.thesis_id,
                final_confidence=final,
                confidence_breakdown=result["confidence_breakdown"],
                positive_contributors=tuple(result["positive_contributors"]),
                negative_contributors=tuple(result["negative_contributors"]),
                confidence_penalties=tuple(result["confidence_penalties"]),
                remaining_uncertainty=round(1.0 - final, 4),
                reliability_category=self._computer.reliability_category(final),
                provenance_chain=tuple(chain),
                metadata=metadata,
            )
            theses_confidence.append(tc)
            thesis_confidence.append(
                {
                    "thesis_id": thesis.thesis_id,
                    "final_confidence": final,
                }
            )

        ranked_ids = self._ranker.rank_by_confidence(thesis_confidence)
        low_ids = self._ranker.detect_low_confidence(thesis_confidence)
        conflict_pairs = self._ranker.detect_conflicting_high_confidence(
            list(construction.theses), thesis_confidence,
        )

        return InstitutionalConfidence(
            confidence_id=f"cf_{uuid4().hex[:12]}",
            construction_id=construction.construction_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            regime=construction.regime,
            theses_confidence=tuple(theses_confidence),
            ranked_thesis_ids=tuple(ranked_ids),
            low_confidence_thesis_ids=tuple(low_ids),
            conflicting_high_confidence_pairs=tuple(conflict_pairs),
            primary_thesis_id=construction.primary_thesis_id,
            metadata={
                "total_theses_assessed": len(theses_confidence),
                "total_low_confidence": len(low_ids),
                "total_conflicting_pairs": len(conflict_pairs),
                "meta_evidence": {
                    "w6_evidence_consumed": reasoning is not None,
                    "w12_downside_case_consumed": generation is not None,
                    "oos_ece_consumed": oos_ece is not None,
                },
            },
        )

    def _gs_test(
        self,
        thesis: InvestmentThesis,
        generation: Any | None,
    ) -> dict[str, Any]:
        """Goldman Sachs 3-question test (W9 processing stage 2).

        Downside case / what breaks the view come from the W12 bear scenario
        (fragility audit).  The "why not priced in" answer is satisfied when
        the thesis rests on documented supporting evidence (evidence dates vs
        price reaction dates are not available in the frozen v1.x scope).
        """
        bear = None
        if generation is not None:
            for s in generation.scenarios:
                if s.thesis_id == thesis.thesis_id and s.scenario_type == "bear":
                    bear = s
                    break
        downside_case = bool(bear and bear.invalidation_conditions)
        what_breaks_view = bool(bear and bear.invalidation_conditions)
        why_not_priced_in = bool(thesis.supporting_set_ids)
        return {
            "downside_case": downside_case,
            "why_not_priced_in": why_not_priced_in,
            "what_breaks_view": what_breaks_view,
            "all_answered": downside_case and what_breaks_view and why_not_priced_in,
        }

    @staticmethod
    def _oos_cap(oos_ece: float | None) -> str | None:
        if oos_ece is None:
            return None
        if oos_ece > 0.25:
            return "low"
        if oos_ece > 0.15:
            return "medium"
        return None

    @staticmethod
    def _w6_evidence(
        reasoning: Any | None,
        thesis: InvestmentThesis,
    ) -> dict[str, Any] | None:
        if reasoning is None:
            return None
        sets = [
            s for s in reasoning.evidence_sets if s.set_id in thesis.supporting_set_ids
        ]
        if not sets:
            return None
        return {
            "supporting_sets": len(sets),
            "evidence_items": sum(len(s.evidence_ids) for s in sets),
            "avg_consensus": round(
                sum(s.consensus_score for s in sets) / len(sets), 4
            ),
            "avg_conflict": round(sum(s.conflict_score for s in sets) / len(sets), 4),
        }
