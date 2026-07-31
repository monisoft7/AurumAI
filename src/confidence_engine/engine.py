from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from confidence_engine.computer import ConfidenceComputer
from confidence_engine.contracts import InstitutionalConfidence, ThesisConfidence
from confidence_engine.ranker import ConfidenceRanker
from knowledge.integrity.provenance import Provenance
from thesis_construction.contracts import ThesisConstruction


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

    def evaluate(self, construction: ThesisConstruction) -> InstitutionalConfidence:
        thesis_confidence: list[dict[str, Any]] = []
        theses_confidence: list[ThesisConfidence] = []

        prov = Provenance(
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="W9 ConfidenceEngine",
            entity_version="1.0.0",
        )

        for thesis in construction.theses:
            result = self._computer.compute(thesis)
            chain = list(thesis.provenance_chain) + [prov]
            tc = ThesisConfidence(
                thesis_id=thesis.thesis_id,
                final_confidence=result["final_confidence"],
                confidence_breakdown=result["confidence_breakdown"],
                positive_contributors=tuple(result["positive_contributors"]),
                negative_contributors=tuple(result["negative_contributors"]),
                confidence_penalties=tuple(result["confidence_penalties"]),
                remaining_uncertainty=result["remaining_uncertainty"],
                reliability_category=result["reliability_category"],
                provenance_chain=tuple(chain),
                metadata=result["metadata"],
            )
            theses_confidence.append(tc)
            thesis_confidence.append(
                {
                    "thesis_id": thesis.thesis_id,
                    "final_confidence": result["final_confidence"],
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
            },
        )
