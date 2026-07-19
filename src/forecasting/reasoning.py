from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from forecasting.evidence import ForecastEvidence

_STRONG_THRESHOLD = 0.65
_MODERATE_THRESHOLD = 0.35
_WEAK_THRESHOLD = 0.10

_HIGH_CONF = 0.70
_LOW_CONF = 0.30


@dataclass(frozen=True)
class ForecastAssessment:
    overall_assessment: str
    confidence_level: float
    supporting_evidence: tuple[str, ...]
    conflicting_evidence: tuple[str, ...]
    reasoning_summary: str
    reasoning_metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_assessment": self.overall_assessment,
            "confidence_level": self.confidence_level,
            "supporting_evidence": list(self.supporting_evidence),
            "conflicting_evidence": list(self.conflicting_evidence),
            "reasoning_summary": self.reasoning_summary,
            "reasoning_metadata": dict(self.reasoning_metadata),
        }


class ForecastReasoning:

    def assess(self, evidence: "ForecastEvidence") -> ForecastAssessment:
        supporting = self._collect_supporting(evidence)
        conflicting = self._collect_conflicting(evidence)

        confidence_level = evidence.evidence_strength
        overall_assessment = self._classify(confidence_level, len(supporting), len(conflicting))
        reasoning_summary = self._build_summary(overall_assessment, confidence_level, supporting, conflicting)
        reasoning_metadata = self._build_metadata(evidence, overall_assessment)

        return ForecastAssessment(
            overall_assessment=overall_assessment,
            confidence_level=confidence_level,
            supporting_evidence=tuple(sorted(supporting)),
            conflicting_evidence=tuple(sorted(conflicting)),
            reasoning_summary=reasoning_summary,
            reasoning_metadata=reasoning_metadata,
        )

    @staticmethod
    def _collect_supporting(evidence: "ForecastEvidence") -> list[str]:
        factors: list[str] = []
        ctx = evidence.supporting_context
        cs = evidence.confidence_snapshot

        num_models = evidence.metadata.get("num_models", 0)
        if num_models >= 2:
            factors.append(f"Ensemble uses {num_models} models")

        if cs.get("spread_score", 0) >= _HIGH_CONF:
            factors.append("Tight prediction intervals indicate low uncertainty")

        if cs.get("agreement_score", 0) >= _HIGH_CONF:
            factors.append("High cross-model agreement on point forecasts")

        if cs.get("context_coherence", 0) >= _HIGH_CONF:
            factors.append("Coherent context signals (regime, news, FOMC)")

        regime_conf = ctx.get("regime_confidence", 0)
        if regime_conf >= _HIGH_CONF and ctx.get("current_regime") is not None:
            factors.append(f"Strong regime signal ({ctx['current_regime']})")

        news_conf = ctx.get("news_confidence", 0)
        if news_conf >= _HIGH_CONF and ctx.get("news_mood") is not None:
            factors.append(f"Confident news sentiment ({ctx['news_mood']})")

        fomc_conf = ctx.get("fomc_confidence", 0)
        if fomc_conf >= _HIGH_CONF and ctx.get("fomc_mood") is not None:
            factors.append(f"Confident FOMC sentiment ({ctx['fomc_mood']})")

        num_events = ctx.get("num_recent_events", 0)
        if num_events >= 2:
            factors.append(f"{num_events} recent economic events in context")

        return factors

    @staticmethod
    def _collect_conflicting(evidence: "ForecastEvidence") -> list[str]:
        factors: list[str] = []
        ctx = evidence.supporting_context
        cs = evidence.confidence_snapshot

        num_models = evidence.metadata.get("num_models", 0)
        if num_models == 0:
            factors.append("No forecast models produced results")

        if cs.get("spread_score", 1) < _LOW_CONF:
            factors.append("Wide prediction intervals indicate high uncertainty")

        if cs.get("agreement_score", 1) < _LOW_CONF:
            factors.append("Low cross-model agreement on point forecasts")

        if cs.get("context_coherence", 1) < _LOW_CONF:
            factors.append("Weak context signal coherence")

        regime_conf = ctx.get("regime_confidence", 0)
        if regime_conf < _LOW_CONF:
            factors.append("Low confidence in regime detection")

        news_conf = ctx.get("news_confidence", 0)
        if news_conf < _LOW_CONF:
            factors.append("Weak news sentiment signal")

        fomc_conf = ctx.get("fomc_confidence", 0)
        if fomc_conf < _LOW_CONF:
            factors.append("Weak FOMC sentiment signal")

        if ctx.get("current_regime") is None:
            factors.append("No regime classification available")

        if ctx.get("news_mood") is None and ctx.get("fomc_mood") is None:
            factors.append("No sentiment signals available")

        return factors

    @staticmethod
    def _classify(confidence: float, num_supporting: int, num_conflicting: int) -> str:
        if confidence >= _STRONG_THRESHOLD:
            return "STRONG"
        if confidence >= _MODERATE_THRESHOLD:
            if num_supporting > num_conflicting:
                return "MODERATE"
            return "UNCERTAIN"
        if confidence >= _WEAK_THRESHOLD:
            return "WEAK"
        return "INSUFFICIENT"

    @staticmethod
    def _build_summary(
        assessment: str,
        confidence: float,
        supporting: list[str],
        conflicting: list[str],
    ) -> str:
        parts: list[str] = [
            f"Assessment: {assessment} (confidence={confidence:.2f}).",
        ]
        if supporting:
            parts.append("Supporting: " + "; ".join(supporting) + ".")
        if conflicting:
            parts.append("Conflicting: " + "; ".join(conflicting) + ".")
        return " ".join(parts)

    @staticmethod
    def _build_metadata(evidence: "ForecastEvidence", assessment: str) -> dict[str, Any]:
        return {
            "thresholds": {
                "strong": _STRONG_THRESHOLD,
                "moderate": _MODERATE_THRESHOLD,
                "weak": _WEAK_THRESHOLD,
                "high_confidence": _HIGH_CONF,
                "low_confidence": _LOW_CONF,
            },
            "evidence_id": evidence.evidence_id,
            "assessment_method": "rule-based deterministic scoring",
            "num_supporting_factors": len(evidence.evidence_sources),
            "num_conflicting_factors": sum(
                1 for v in evidence.supporting_context.values()
                if isinstance(v, float) and v < _LOW_CONF
            ),
        }
