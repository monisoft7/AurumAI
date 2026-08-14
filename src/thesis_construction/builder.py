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
        knowledge_chunk = self._compose_knowledge_rationale(supporting_sets)
        if knowledge_chunk:
            explanation += f" | {knowledge_chunk}"
        factor_chunk = self._compose_factor_rationale(reasoning)
        if factor_chunk:
            explanation += f" | {factor_chunk}"
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

    @staticmethod
    def _compose_knowledge_rationale(supporting_sets: list[EvidenceSet]) -> str:
        """Compose the explanation-only KR rationale chunk (Correction 008-B).

        Mirrors the deterministic per-evidence rationale carried in
        ``set.metadata["knowledge_rationale"]`` into a single ``knowledge:``
        suffix.  Returns "" when no supporting set carries a rationale, so
        explanations for non-KR pipelines are byte-identical to before.
        """
        lines: list[str] = []
        for s in supporting_sets:
            for entry in s.metadata.get("knowledge_rationale") or []:
                condition = entry.get("condition") or {}
                cond_str = "; ".join(f"{k}={v}" for k, v in condition.items()) or "any"
                parts = [
                    f"{entry.get('family', '')} {cond_str}: "
                    f"avg {entry.get('average_return_pct', 0.0):+.3f}% "
                    f"over {entry.get('horizon_days', 0)}d | "
                    f"conf {entry.get('confidence', 0.0):.3f} | "
                    f"{entry.get('sample_count', 0)} samples",
                ]
                if "positive_return_rate_pct" in entry:
                    parts.append(
                        f"{entry['positive_return_rate_pct']:.1f}% positive-rate"
                    )
                lines.append(" | ".join(parts))
        if not lines:
            return ""
        return "knowledge: " + "; ".join(lines)

    @staticmethod
    def _compose_factor_rationale(reasoning: EvidenceReasoning) -> str:
        """Compose the explanation-only cross-factor rationale chunk.

        Trace 016-B: mirrors the deterministic gold_rule_001 rationale carried
        in ``reasoning.metadata["factor_rationale"]`` into a single
        ``factor:`` suffix.  Returns "" when no factor rationale is present
        (e.g. inputs unavailable), so explanations are byte-identical to
        before.  Stale inputs are annotated explicitly and never presented as
        current observations.
        """
        rationale = reasoning.metadata.get("factor_rationale")
        if not isinstance(rationale, dict) or not rationale:
            return ""
        parts = [
            f"{rationale.get('rule_id', 'gold_rule_001')} "
            f"bias={rationale.get('composite_bias', '')} "
            f"strength={rationale.get('composite_strength', 0.0):+.4f} "
            f"confidence={rationale.get('composite_confidence', 0.0):.4f} "
            f"dispersion={rationale.get('signal_dispersion', 0.0):.4f}",
        ]
        for f in rationale.get("factors") or []:
            parts.append(
                f"{f.get('factor_id', '')}: obs={f.get('observation_date', '')} "
                f"bias={f.get('influence_bias', '')} "
                f"strength={f.get('influence_strength', 0.0):+.4f} "
                f"conf={f.get('confidence', 0.0):.4f} "
                f"quality={f.get('data_quality', '')} ({f.get('status', '')})"
            )
        summary = "; ".join(parts)
        if rationale.get("freshness_note"):
            summary += f" | {rationale['freshness_note']}"
        adjudicated = [
            f"{key}={rationale[key]}"
            for key in (
                "regime",
                "dominant_factor",
                "weaker_factor",
                "precedence_reason",
                "adjudicated_interpretation",
            )
            if rationale.get(key)
        ]
        if adjudicated:
            summary += " | " + " | ".join(adjudicated)
        return "factor: " + summary
