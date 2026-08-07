from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from counter_evidence.analyzer import BiasAnalyzer
from counter_evidence.contracts import CounterEvidenceAssessment
from counter_evidence.detector import ConflictDetector
from evidence_reasoning.contracts import EvidenceReasoning, EvidenceSet
from knowledge.integrity.provenance import Provenance


class CounterEvidenceAssessor:
    """Orchestrates W7: detect → analyze → produce CounterEvidenceAssessment."""

    def __init__(
        self,
        detector: ConflictDetector | None = None,
        analyzer: BiasAnalyzer | None = None,
    ) -> None:
        self._detector = detector or ConflictDetector()
        self._analyzer = analyzer or BiasAnalyzer()

    def assess(self, reasoning: EvidenceReasoning) -> CounterEvidenceAssessment:
        sets = reasoning.evidence_sets
        regime = reasoning.regime

        contradicting_ids, supporting_ids, _ = self._detector.cross_set_conflicts(sets)

        bias_flags: list[str] = []

        if self._analyzer.confirmation_bias(sets):
            bias_flags.append("confirmation_bias")
        if self._analyzer.no_dissent(sets) and not contradicting_ids:
            bias_flags.append("no_dissent")
        if self._detector.source_concentration(sets):
            bias_flags.append("source_concentration")
        if self._detector.regime_conflict(sets, regime):
            bias_flags.append("regime_conflict")

        missing = self._detector.missing_event_types(sets, regime)
        if missing:
            bias_flags.append("missing_evidence")

        if contradicting_ids:
            bias_flags.append("cross_set_conflict")

        conflict_severity = self._analyzer.compute_conflict_severity(sets, contradicting_ids)
        regime_conflict_flag = self._detector.regime_conflict(sets, regime)
        confidence_penalty = self._analyzer.compute_confidence_penalty(
            conflict_severity, bias_flags, regime_conflict_flag,
        )

        prov = Provenance(
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="W7 CounterEvidenceAssessor",
            entity_version="1.0.0",
        )

        all_set_ids = tuple(es.set_id for es in sets)
        explanation = self._build_explanation(
            all_set_ids, supporting_ids, contradicting_ids,
            missing, bias_flags, conflict_severity, confidence_penalty,
            regime_conflict_flag,
        )

        return CounterEvidenceAssessment(
            assessment_id=f"cea_{uuid4().hex[:12]}",
            reasoning_id=reasoning.reasoning_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            regime=regime,
            related_set_ids=all_set_ids,
            supporting_set_ids=tuple(supporting_ids),
            contradicting_set_ids=tuple(contradicting_ids),
            missing_evidence=tuple(missing),
            bias_flags=tuple(bias_flags),
            conflict_severity=conflict_severity,
            confidence_penalty=confidence_penalty,
            regime_conflict=regime_conflict_flag,
            explanation=explanation,
            provenance_chain=(prov,),
            metadata={
                "total_evidence_sets": len(sets),
                "total_bias_flags": len(bias_flags),
            },
        )

    @staticmethod
    def _build_explanation(
        all_set_ids: tuple[str, ...],
        supporting_ids: list[str],
        contradicting_ids: list[str],
        missing: list[str],
        bias_flags: list[str],
        conflict_severity: float,
        confidence_penalty: float,
        regime_conflict: bool,
    ) -> str:
        parts = [
            f"sets={len(all_set_ids)}",
            f"supporting={len(supporting_ids)}",
            f"contradicting={len(contradicting_ids)}",
            f"missing_evidence={missing if missing else 'none'}",
            f"bias_flags={bias_flags}",
            f"conflict_severity={conflict_severity}",
            f"confidence_penalty={confidence_penalty}",
            f"regime_conflict={regime_conflict}",
        ]
        return " | ".join(parts)
