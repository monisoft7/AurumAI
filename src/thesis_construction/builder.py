from __future__ import annotations

from collections import Counter
from typing import Any
from uuid import uuid4

from counter_evidence.contracts import CounterEvidenceAssessment
from evidence_reasoning.contracts import EvidenceReasoning, EvidenceSet
from knowledge.integrity.provenance import Provenance
from thesis_construction.contracts import InvestmentThesis

# Map event_types to economic mechanism descriptions
EVENT_TYPE_TO_MECHANISM: dict[str, str] = {
    "REAL_YIELD": "Real yield opportunity cost channel driving gold relative value",
    "USD_FX": "US dollar valuation channel through gold's dollar denomination",
    "INFLATION": "Inflation premium channel as gold serves as inflation hedge",
    "CB_GOLD": "Central bank reserve diversification supporting structural gold demand",
    "GEOPOLITICAL": "Safe-haven demand driven by geopolitical uncertainty",
    "ETF_FLOW": "Gold ETF flow momentum reflecting investor sentiment",
    "GENERAL": "Multi-factor cross-asset transmission affecting gold price",
}


class ThesisBuilder:
    """Builds individual InvestmentThesis objects from W6 evidence and W7 counter-evidence."""

    DEFAULT_TIME_HORIZON_DAYS = 90

    def build_thesis(
        self,
        direction: str,
        reasoning: EvidenceReasoning,
        assessment: CounterEvidenceAssessment,
        supporting_set_ids: list[str],
        counter_set_ids: list[str],
    ) -> InvestmentThesis:
        supporting_sets = [s for s in reasoning.evidence_sets if s.set_id in supporting_set_ids]

        mechanism = self._derive_mechanism(supporting_sets, direction)
        invalidating = self._build_invalidating_conditions(assessment, direction, counter_set_ids)
        unknowns = list(assessment.missing_evidence)
        confidence_inputs = self._build_confidence_inputs(supporting_sets, assessment)
        support = self._compute_institutional_support(supporting_sets, assessment)
        explanation = self._build_explanation(
            direction, len(supporting_set_ids), len(counter_set_ids),
            support, assessment,
        )
        prov = Provenance(
            created_at=assessment.timestamp,
            created_by="W8 ThesisBuilder",
            entity_version="1.0.0",
        )
        provenance = list(assessment.provenance_chain) + [prov]

        thesis_id = f"th_{uuid4().hex[:12]}"

        return InvestmentThesis(
            thesis_id=thesis_id,
            direction=direction,
            supporting_set_ids=tuple(supporting_set_ids),
            counter_evidence_ids=tuple(counter_set_ids),
            regime=reasoning.regime,
            economic_mechanism=mechanism,
            time_horizon_days=self.DEFAULT_TIME_HORIZON_DAYS,
            invalidating_conditions=tuple(invalidating),
            remaining_unknowns=tuple(unknowns),
            confidence_inputs=confidence_inputs,
            institutional_support=support,
            explanation=explanation,
            provenance_chain=tuple(provenance),
        )

    @staticmethod
    def _derive_mechanism(supporting_sets: list[EvidenceSet], direction: str) -> str:
        if not supporting_sets:
            return "No active evidence channels identified"
        event_types = [s.event_type for s in supporting_sets if s.event_type]
        mechanism_parts = []
        for et in event_types:
            desc = EVENT_TYPE_TO_MECHANISM.get(et, f"{et} channel")
            mechanism_parts.append(desc)
        return "; ".join(sorted(set(mechanism_parts)))

    @staticmethod
    def _build_invalidating_conditions(
        assessment: CounterEvidenceAssessment,
        direction: str,
        counter_set_ids: list[str],
    ) -> list[str]:
        conditions: list[str] = []
        if counter_set_ids:
            conditions.append(f"Counter-evidence from sets {', '.join(counter_set_ids)} strengthens")
        if assessment.regime_conflict:
            conditions.append("Current regime conflicts with thesis direction")
        if "regime_conflict" in assessment.bias_flags:
            conditions.append("Regime-dependent evidence weakening thesis")
        if "missing_evidence" in assessment.bias_flags and assessment.missing_evidence:
            missing = ", ".join(assessment.missing_evidence)
            conditions.append(f"Missing evidence channels: {missing}")
        return conditions if conditions else ["No specific invalidating conditions identified"]

    @staticmethod
    def _build_confidence_inputs(
        supporting_sets: list[EvidenceSet],
        assessment: CounterEvidenceAssessment,
    ) -> dict[str, float]:
        avg_set_weight = 0.0
        avg_set_consensus = 0.0
        if supporting_sets:
            avg_set_weight = round(
                sum(s.net_institutional_weight for s in supporting_sets) / len(supporting_sets), 4
            )
            avg_set_consensus = round(
                sum(s.consensus_score for s in supporting_sets) / len(supporting_sets), 4
            )
        return {
            "avg_supporting_weight": avg_set_weight,
            "avg_supporting_consensus": avg_set_consensus,
            "conflict_severity": assessment.conflict_severity,
            "confidence_penalty": assessment.confidence_penalty,
            "raw_support": avg_set_weight * avg_set_consensus,
        }

    @staticmethod
    def _compute_institutional_support(
        supporting_sets: list[EvidenceSet],
        assessment: CounterEvidenceAssessment,
    ) -> float:
        if not supporting_sets:
            return 0.0
        raw = sum(
            s.net_institutional_weight * s.consensus_score
            for s in supporting_sets
        ) / len(supporting_sets)
        penalty = assessment.confidence_penalty
        support = raw * (1.0 - penalty)
        return max(0.0, min(round(support, 4), 1.0))

    @staticmethod
    def _build_explanation(
        direction: str,
        num_supporting: int,
        num_counter: int,
        support: float,
        assessment: CounterEvidenceAssessment,
    ) -> str:
        return (
            f"Thesis direction={direction} | "
            f"supporting_sets={num_supporting} | "
            f"counter_evidence_sets={num_counter} | "
            f"institutional_support={support} | "
            f"conflict_severity={assessment.conflict_severity} | "
            f"confidence_penalty={assessment.confidence_penalty} | "
            f"regime_conflict={assessment.regime_conflict} | "
            f"bias_flags={list(assessment.bias_flags)}"
        )
