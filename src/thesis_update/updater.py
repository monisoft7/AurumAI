"""Rule-based, deterministic thesis updater implementing the Bridgewater
four-step update template: identify the changed input, map the impact,
quantify the confidence delta, and decide on the update action. The previous
thesis is never mutated; every update emits a new immutable version.
"""

from __future__ import annotations

import re

from counter_evidence.contracts import CounterEvidenceAssessment
from evidence_reasoning.contracts import EvidenceReasoning, EvidenceSet
from knowledge.integrity.provenance import Provenance
from thesis_construction.builder import ThesisBuilder
from thesis_construction.contracts import InvestmentThesis, ThesisConstruction
from thesis_update.contracts import ThesisUpdate

VERSION_SUFFIX_RE = re.compile(r"^(?P<base>.+)\.v(?P<version>\d+)$")

SUPPORT_EROSION_THRESHOLD = 0.05
THRESHOLD_CROSSING_DELTA = 0.25
EXIT_DELTA = 0.5
HEDGE_DELTA = 0.25
VIABILITY_SUPPORT = 0.4


class ThesisUpdater:
    """Creates the next immutable version of an existing thesis."""

    created_by = "W10 ThesisUpdater"

    def update(
        self,
        construction: ThesisConstruction,
        reasoning: EvidenceReasoning,
        assessment: CounterEvidenceAssessment,
    ) -> ThesisUpdate:
        thesis = construction.primary_thesis
        if thesis is None and construction.theses:
            thesis = construction.theses[0]
        if thesis is None:
            raise ValueError("no thesis available to update")

        supporting_sets = [
            s for s in reasoning.evidence_sets if s.set_id in thesis.supporting_set_ids
        ]

        support_new = ThesisBuilder._compute_institutional_support(supporting_sets, assessment)
        confidence_inputs_new = ThesisBuilder._build_confidence_inputs(supporting_sets, assessment)
        counter_set_ids_new = list(assessment.contradicting_set_ids)
        invalidating_new = ThesisBuilder._build_invalidating_conditions(
            assessment, thesis.direction, counter_set_ids_new
        )
        mechanism_new = ThesisBuilder._derive_mechanism(supporting_sets, thesis.direction)

        confidence_delta = round(support_new - thesis.institutional_support, 4)
        regime_break = thesis.regime.upper() != reasoning.regime.upper()

        updated_evidence = self._collect_updated_evidence(reasoning, assessment, thesis)

        base_id, previous_version = self._parse_version(thesis.thesis_id)
        new_version_number = previous_version + 1
        new_thesis_id = f"{base_id}.v{new_version_number}"
        new_version_label = f"v{new_version_number}"

        changed = self._changed_assumptions(
            thesis, assessment, support_new, confidence_delta, regime_break
        )
        trigger_type = self._trigger_type(regime_break, confidence_delta)
        action = self._select_action(regime_break, confidence_delta)

        updated_thesis = self._build_updated_thesis(
            thesis=thesis,
            new_thesis_id=new_thesis_id,
            new_version_number=new_version_number,
            reasoning=reasoning,
            assessment=assessment,
            supporting_sets=supporting_sets,
            counter_set_ids_new=counter_set_ids_new,
            support_new=support_new,
            confidence_inputs_new=confidence_inputs_new,
            invalidating_new=invalidating_new,
            mechanism_new=mechanism_new,
            updated_evidence=updated_evidence,
        )

        prov = Provenance(
            created_at=reasoning.timestamp,
            created_by=self.created_by,
            entity_version="1.0.0",
        )
        update_id = f"update-{base_id}-v{new_version_number}"

        summary = (
            f"Thesis {thesis.thesis_id} ({previous_version}) updated to "
            f"{new_thesis_id} ({new_version_label}): action={action}, "
            f"trigger={trigger_type}, confidence_delta={confidence_delta:+.4f}, "
            f"new_support={support_new:.4f}, changed_assumptions="
            f"{list(changed) if changed else 'none'}"
        )

        return ThesisUpdate(
            update_id=update_id,
            previous_thesis_id=thesis.thesis_id,
            previous_version=f"v{previous_version}",
            new_thesis_version=new_version_label,
            reasoning_id=reasoning.reasoning_id,
            assessment_id=assessment.assessment_id,
            timestamp=reasoning.timestamp,
            updated_evidence=tuple(updated_evidence),
            confidence_delta=confidence_delta,
            changed_assumptions=tuple(changed),
            change_summary=summary,
            action=action,
            trigger_type=trigger_type,
            updated_thesis=updated_thesis,
            provenance_chain=(prov,),
            metadata={
                "created_by": self.created_by,
                "base_thesis_id": base_id,
                "regime": reasoning.regime,
                "previous_support": thesis.institutional_support,
                "new_support": support_new,
            },
        )

    @staticmethod
    def _parse_version(thesis_id: str) -> tuple[str, int]:
        match = VERSION_SUFFIX_RE.match(thesis_id)
        if match:
            return match.group("base"), int(match.group("version"))
        return thesis_id, 1

    @staticmethod
    def _collect_updated_evidence(
        reasoning: EvidenceReasoning,
        assessment: CounterEvidenceAssessment,
        thesis: InvestmentThesis,
    ) -> list[str]:
        collected: list[str] = []
        seen: set[str] = set()
        for s in reasoning.evidence_sets:
            if s.set_id in thesis.supporting_set_ids:
                for evidence_id in s.supporting_evidence_ids:
                    if evidence_id not in seen:
                        seen.add(evidence_id)
                        collected.append(evidence_id)
            if s.set_id in assessment.contradicting_set_ids:
                for evidence_id in s.contradicting_evidence_ids:
                    if evidence_id not in seen:
                        seen.add(evidence_id)
                        collected.append(evidence_id)
        return collected

    @staticmethod
    def _changed_assumptions(
        thesis: InvestmentThesis,
        assessment: CounterEvidenceAssessment,
        support_new: float,
        confidence_delta: float,
        regime_break: bool,
    ) -> list[str]:
        changed: list[str] = []
        if regime_break:
            changed.append("macro regime shift")
        if confidence_delta >= SUPPORT_EROSION_THRESHOLD:
            changed.append("institutional support improvement")
        elif confidence_delta <= -SUPPORT_EROSION_THRESHOLD:
            changed.append("institutional support erosion")
        if len(assessment.contradicting_set_ids) > len(thesis.counter_evidence_ids):
            changed.append("counter-evidence pressure")
        old_conflict = thesis.confidence_inputs.get("conflict_severity", 0.0)
        if assessment.conflict_severity > old_conflict + 0.1:
            changed.append("evidence conflict escalation")
        if support_new < VIABILITY_SUPPORT <= thesis.institutional_support:
            changed.append("support below viability threshold")
        if assessment.missing_evidence:
            changed.append("missing evidence channels")
        return changed

    @staticmethod
    def _trigger_type(regime_break: bool, confidence_delta: float) -> str:
        if regime_break:
            return "regime_break"
        if abs(confidence_delta) > THRESHOLD_CROSSING_DELTA:
            return "threshold_crossing"
        if abs(confidence_delta) >= SUPPORT_EROSION_THRESHOLD:
            return "cumulative_evidence"
        return "periodic"

    @staticmethod
    def _select_action(regime_break: bool, confidence_delta: float) -> str:
        if regime_break and confidence_delta <= -0.3:
            return "exit"
        if confidence_delta <= -EXIT_DELTA:
            return "exit"
        if regime_break and confidence_delta < 0.0:
            return "pause"
        if confidence_delta <= -HEDGE_DELTA:
            return "hedge"
        if confidence_delta > THRESHOLD_CROSSING_DELTA:
            return "scale"
        return "no_change"

    @staticmethod
    def _build_updated_thesis(
        thesis: InvestmentThesis,
        new_thesis_id: str,
        new_version_number: int,
        reasoning: EvidenceReasoning,
        assessment: CounterEvidenceAssessment,
        supporting_sets: list[EvidenceSet],
        counter_set_ids_new: list[str],
        support_new: float,
        confidence_inputs_new: dict[str, float],
        invalidating_new: list[str],
        mechanism_new: str,
        updated_evidence: list[str],
    ) -> InvestmentThesis:
        explanation = ThesisBuilder._build_explanation(
            thesis.direction,
            len(supporting_sets),
            len(counter_set_ids_new),
            support_new,
            assessment,
        )
        knowledge_chunk = ThesisBuilder._compose_knowledge_rationale(supporting_sets)
        if knowledge_chunk:
            explanation += f" | {knowledge_chunk}"
        factor_chunk = ThesisBuilder._compose_factor_rationale(reasoning)
        if factor_chunk:
            explanation += f" | {factor_chunk}"
        analogue_chunk = ThesisBuilder._compose_historical_analogue(reasoning)
        if analogue_chunk:
            explanation += f" | {analogue_chunk}"
        explanation += (
            f" | UPDATED v{new_version_number}: "
            f"evidence={len(updated_evidence)} | "
            f"support={support_new:.4f}"
        )
        prov = Provenance(
            created_at=reasoning.timestamp,
            created_by="W10 ThesisUpdater",
            entity_version="1.0.0",
        )
        metadata = dict(thesis.metadata)
        metadata["thesis_version"] = new_version_number
        metadata["previous_thesis_id"] = thesis.thesis_id
        return InvestmentThesis(
            thesis_id=new_thesis_id,
            direction=thesis.direction,
            supporting_set_ids=tuple(s.set_id for s in supporting_sets),
            counter_evidence_ids=tuple(counter_set_ids_new),
            regime=reasoning.regime,
            economic_mechanism=mechanism_new,
            time_horizon_days=thesis.time_horizon_days,
            invalidating_conditions=tuple(invalidating_new),
            remaining_unknowns=tuple(assessment.missing_evidence),
            confidence_inputs=confidence_inputs_new,
            institutional_support=support_new,
            explanation=explanation,
            provenance_chain=tuple(thesis.provenance_chain) + (prov,),
            metadata=metadata,
        )

    def __repr__(self) -> str:
        return f"ThesisUpdater(created_by={self.created_by!r})"
