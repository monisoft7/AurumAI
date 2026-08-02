"""Deterministic, rule-based bias reviewer implementing the institutional
reasoning-mistakes checklist. Reviews the updated thesis against the
counter-evidence assessment and the institutional confidence output.
"""

from __future__ import annotations

import re

from confidence_engine.contracts import InstitutionalConfidence, ThesisConfidence
from counter_evidence.contracts import CounterEvidenceAssessment
from knowledge.integrity.provenance import Provenance
from thesis_construction.contracts import InvestmentThesis
from thesis_update.contracts import ThesisUpdate
from bias_prevention.contracts import (
    SEVERITY_IMPACT,
    SEVERITY_RANK,
    HUMAN_REVIEW_SEVERITIES,
    BiasFinding,
    BiasReview,
)

GENERIC_INVALIDATION_MARKERS = ("No specific invalidating conditions",)

BASE_RATE_CLAIM_KEYWORDS = (
    "will",
    "should",
    "expected",
    "likely",
    "outperform",
    "target",
    "rise",
    "fall",
    "rally",
    "decline",
    "increase",
    "decrease",
)

BASE_RATE_REFERENCE_KEYWORDS = (
    "base rate",
    "historically",
    "historical",
    "since 19",
    "since 20",
    "long-run",
    "long run",
    "drawdown",
    "frequency",
    "mean reversion",
)

OUTCOME_KEYWORDS = (
    "return",
    "outcome",
    "result",
    "profit",
    "loss",
    "win",
    "performed",
    "outperformed",
)

ATTRIBUTION_REVIEW_KEYWORDS = (
    "journal",
    "post-mortem",
    "postmortem",
    "lesson",
    "reviewed",
    "attribution",
    "prior decision",
)

DISCONTINUITY_KEYWORDS = (
    "unprecedented",
    "no precedent",
    "without historical precedent",
    "first time",
    "this time is different",
    "new paradigm",
    "new normal",
    "structural break",
    "regime change",
    "never seen",
)

HISTORICAL_ANALOGUE_KEYWORDS = (
    "historically",
    "analog",
    "since 19",
    "since 20",
    "past",
    "similar",
    "2008",
    "2011",
    "2013",
    "2020",
    "2022",
)

PRECISION_PATTERN = re.compile(r"\d+\.\d+")

RANGE_KEYWORDS = (
    "range",
    "interval",
    "band",
    "confidence interval",
    "+/-",
    "±",
)


class BiasReviewer:
    """Checks the thesis update cycle against twelve institutional biases."""

    created_by = "W13 BiasReviewer"

    def review(
        self,
        update: ThesisUpdate,
        assessment: CounterEvidenceAssessment,
        confidence: InstitutionalConfidence,
    ) -> BiasReview:
        thesis = update.updated_thesis
        tc = self._find_confidence(confidence, thesis.thesis_id)
        invalidating = tuple(thesis.invalidating_conditions)
        has_explicit = self._has_explicit_invalidating_conditions(invalidating)
        disconfirming = bool(thesis.counter_evidence_ids) or bool(
            assessment.contradicting_set_ids
        )
        evidence_strength = float(
            thesis.confidence_inputs.get("avg_supporting_weight", 0.0)
        )
        final_confidence = tc.final_confidence if tc else 0.0
        temporal_recency = (
            tc.confidence_breakdown.get("temporal_recency", 1.0) if tc else 1.0
        )

        findings = [
            self._check_confirmation_bias(has_explicit, disconfirming, assessment),
            self._check_anchoring(has_explicit),
            self._check_recency_bias(update, thesis, temporal_recency),
            self._check_narrative_bias(thesis, evidence_strength),
            self._check_overconfidence(final_confidence, evidence_strength, tc),
            self._check_single_source_bias(thesis, assessment),
            self._check_regime_blindness(update, assessment),
            self._check_base_rate_neglect(thesis),
            self._check_attribution_error(update),
            self._check_groupthink(thesis, assessment),
            self._check_false_precision(thesis),
            self._check_this_time_is_different(update, thesis),
        ]
        findings = [f for f in findings if f is not None]

        if findings:
            overall = max(
                findings, key=lambda f: SEVERITY_RANK.get(f.severity, 0)
            ).severity
            total_impact = round(min(1.0, sum(f.confidence_impact for f in findings)), 4)
            actions: list[str] = []
            for f in findings:
                if f.required_action not in actions:
                    actions.append(f.required_action)
        else:
            overall = "clean"
            total_impact = 0.0
            actions = []

        prov = Provenance(
            created_at=update.timestamp,
            created_by=self.created_by,
            entity_version="1.0.0",
        )
        return BiasReview(
            review_id=f"bias-{thesis.thesis_id}",
            thesis_id=thesis.thesis_id,
            update_id=update.update_id,
            confidence_id=confidence.confidence_id,
            assessment_id=assessment.assessment_id,
            timestamp=update.timestamp,
            regime=thesis.regime,
            findings=tuple(findings),
            overall_severity=overall,
            total_confidence_impact=total_impact,
            required_actions=tuple(actions),
            human_review_flag=any(
                f.severity in HUMAN_REVIEW_SEVERITIES for f in findings
            ),
            provenance_chain=(prov,),
            metadata={
                "created_by": self.created_by,
                "findings_count": len(findings),
            },
        )

    # ------------------------------------------------------------------
    # Individual bias checks
    # ------------------------------------------------------------------

    def _check_confirmation_bias(
        self,
        has_explicit: bool,
        disconfirming: bool,
        assessment: CounterEvidenceAssessment,
    ) -> BiasFinding | None:
        if has_explicit or disconfirming:
            return None
        severity = "high" if "confirmation_bias" in assessment.bias_flags else "medium"
        return BiasFinding(
            bias_name="confirmation_bias",
            severity=severity,
            evidence=(
                "thesis carries no explicit disconfirming conditions and no "
                "contradicting evidence is present"
            ),
            required_action=(
                "Add explicit disconfirming conditions and seek contradicting evidence"
            ),
            confidence_impact=SEVERITY_IMPACT[severity],
        )

    def _check_anchoring(self, has_explicit: bool) -> BiasFinding | None:
        if has_explicit:
            return None
        return BiasFinding(
            bias_name="anchoring",
            severity="medium",
            evidence="no pre-committed exit or update trigger levels in the thesis",
            required_action="Pre-commit explicit exit and update triggers",
            confidence_impact=SEVERITY_IMPACT["medium"],
        )

    def _check_recency_bias(
        self,
        update: ThesisUpdate,
        thesis: InvestmentThesis,
        temporal_recency: float,
    ) -> BiasFinding | None:
        short_window = (
            thesis.time_horizon_days <= 30
            and update.trigger_type in ("threshold_crossing", "cumulative_evidence")
        )
        if temporal_recency >= 0.5 and not short_window:
            return None
        if temporal_recency < 0.5:
            evidence = (
                f"confidence relies on short-window evidence "
                f"(temporal_recency={temporal_recency:.4f})"
            )
        else:
            evidence = (
                f"short investment horizon ({thesis.time_horizon_days} "
                "days) updated on recent evidence only"
            )
        return BiasFinding(
            bias_name="recency_bias",
            severity="low",
            evidence=evidence,
            required_action="Require multi-window evidence (multi-window check)",
            confidence_impact=SEVERITY_IMPACT["low"],
        )

    def _check_narrative_bias(
        self, thesis: InvestmentThesis, evidence_strength: float
    ) -> BiasFinding | None:
        if not thesis.economic_mechanism or evidence_strength >= 0.5:
            return None
        return BiasFinding(
            bias_name="narrative_bias",
            severity="medium",
            evidence=(
                f"compelling mechanism {thesis.economic_mechanism[:60]!r} with weak "
                f"supporting evidence (avg_supporting_weight={evidence_strength:.4f})"
            ),
            required_action="Rebuild the thesis from verifiable evidence, not narrative coherence",
            confidence_impact=SEVERITY_IMPACT["medium"],
        )

    def _check_overconfidence(
        self,
        final_confidence: float,
        evidence_strength: float,
        tc: ThesisConfidence | None,
    ) -> BiasFinding | None:
        if final_confidence <= 0.7:
            return None
        if evidence_strength >= 0.5 and (
            tc is None or tc.reliability_category not in ("low", "very_low")
        ):
            return None
        return BiasFinding(
            bias_name="overconfidence",
            severity="high",
            evidence=(
                f"conviction {final_confidence:.4f} exceeds evidence strength "
                f"{evidence_strength:.4f}"
            ),
            required_action="Recompute confidence from the evidence set before acting",
            confidence_impact=SEVERITY_IMPACT["high"],
        )

    def _check_single_source_bias(
        self,
        thesis: InvestmentThesis,
        assessment: CounterEvidenceAssessment,
    ) -> BiasFinding | None:
        if len(thesis.supporting_set_ids) > 1:
            return None
        if len(assessment.supporting_set_ids) > 1:
            return None
        severity = (
            "high" if "source_concentration" in assessment.bias_flags else "medium"
        )
        return BiasFinding(
            bias_name="single_source_bias",
            severity=severity,
            evidence="only a single supporting evidence source informs the thesis",
            required_action="Diversify evidence sources before committing capital",
            confidence_impact=SEVERITY_IMPACT[severity],
        )

    def _check_regime_blindness(
        self,
        update: ThesisUpdate,
        assessment: CounterEvidenceAssessment,
    ) -> BiasFinding | None:
        regime_signal = assessment.regime_conflict or update.trigger_type == "regime_break"
        if not regime_signal or update.action not in ("no_change", "scale", "hedge"):
            return None
        severity = (
            "critical"
            if assessment.regime_conflict and update.action == "no_change"
            else "high"
        )
        return BiasFinding(
            bias_name="regime_blindness",
            severity=severity,
            evidence=(
                f"regime signal present (regime_conflict={assessment.regime_conflict}, "
                f"trigger={update.trigger_type}) but update action is {update.action}"
            ),
            required_action="Reassess the thesis under the new regime before any action",
            confidence_impact=SEVERITY_IMPACT[severity],
        )

    def _check_base_rate_neglect(self, thesis: InvestmentThesis) -> BiasFinding | None:
        text = self._thesis_text(thesis)
        if not self._contains_any(text, BASE_RATE_CLAIM_KEYWORDS):
            return None
        if self._contains_any(text, BASE_RATE_REFERENCE_KEYWORDS):
            return None
        return BiasFinding(
            bias_name="base_rate_neglect",
            severity="medium",
            evidence="directional claim made without referencing historical base rates",
            required_action="Reference historical base rates and analogues before finalizing",
            confidence_impact=SEVERITY_IMPACT["medium"],
        )

    def _check_attribution_error(self, update: ThesisUpdate) -> BiasFinding | None:
        if not update.previous_thesis_id:
            return None
        text = update.change_summary or ""
        if not self._contains_any(text, OUTCOME_KEYWORDS):
            return None
        if self._contains_any(text, ATTRIBUTION_REVIEW_KEYWORDS):
            return None
        for prov in update.provenance_chain:
            creator = (prov.created_by or "").lower()
            if "journal" in creator or "lesson" in creator:
                return None
        return BiasFinding(
            bias_name="attribution_error",
            severity="low",
            evidence=(
                f"prior thesis {update.previous_thesis_id} exists but no decision "
                "journal or lesson record is referenced"
            ),
            required_action=(
                "Consult the decision journal for the prior thesis before re-affirming"
            ),
            confidence_impact=SEVERITY_IMPACT["low"],
        )

    def _check_groupthink(
        self,
        thesis: InvestmentThesis,
        assessment: CounterEvidenceAssessment,
    ) -> BiasFinding | None:
        if thesis.direction not in ("bullish", "bearish"):
            return None
        if thesis.counter_evidence_ids or assessment.contradicting_set_ids:
            return None
        return BiasFinding(
            bias_name="groupthink",
            severity="medium",
            evidence="directional thesis with no contradicting or variant view documented",
            required_action="Document a variant view and independent counter-evidence",
            confidence_impact=SEVERITY_IMPACT["medium"],
        )

    def _check_false_precision(self, thesis: InvestmentThesis) -> BiasFinding | None:
        text = thesis.explanation or ""
        if not PRECISION_PATTERN.search(text):
            return None
        if self._contains_any(text, RANGE_KEYWORDS):
            return None
        return BiasFinding(
            bias_name="false_precision",
            severity="low",
            evidence="point estimate presented without a range or confidence interval",
            required_action="Present outputs as ranges with confidence intervals",
            confidence_impact=SEVERITY_IMPACT["low"],
        )

    def _check_this_time_is_different(
        self,
        update: ThesisUpdate,
        thesis: InvestmentThesis,
    ) -> BiasFinding | None:
        text = self._thesis_text(thesis) + " " + (update.change_summary or "")
        if not self._contains_any(text, DISCONTINUITY_KEYWORDS):
            return None
        if self._contains_any(text, HISTORICAL_ANALOGUE_KEYWORDS):
            return None
        return BiasFinding(
            bias_name="this_time_is_different",
            severity="medium",
            evidence="discontinuity claim made without historical analogue comparison",
            required_action=(
                "Provide explicit past analogues and independent evidence "
                "for the discontinuity claim"
            ),
            confidence_impact=SEVERITY_IMPACT["medium"],
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _has_explicit_invalidating_conditions(invalidating: tuple[str, ...]) -> bool:
        for condition in invalidating:
            if condition and not any(
                marker in condition for marker in GENERIC_INVALIDATION_MARKERS
            ):
                return True
        return False

    @staticmethod
    def _find_confidence(
        confidence: InstitutionalConfidence,
        thesis_id: str,
    ) -> ThesisConfidence | None:
        for tc in confidence.theses_confidence:
            if tc.thesis_id == thesis_id:
                return tc
        return confidence.theses_confidence[0] if confidence.theses_confidence else None

    @staticmethod
    def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
        lowered = text.lower()
        return any(k in lowered for k in keywords)

    @staticmethod
    def _thesis_text(thesis: InvestmentThesis) -> str:
        return " ".join(
            [
                thesis.explanation or "",
                thesis.economic_mechanism or "",
            ]
        )

    def __repr__(self) -> str:
        return f"BiasReviewer(created_by={self.created_by!r})"
