"""W12 Institutional Scenario Generation: builds base/bull/bear scenarios
for every thesis from ThesisConstruction (W8) and InstitutionalConfidence (W9)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from confidence_engine.computer import ConfidenceComputer
from confidence_engine.contracts import InstitutionalConfidence, ThesisConfidence
from knowledge.integrity.provenance import Provenance
from scenario_generation.contracts import (
    SCENARIO_TYPE_LABELS,
    InstitutionalScenario,
    ScenarioGeneration,
)
from thesis_construction.contracts import InvestmentThesis, ThesisConstruction

BULL_REGIME_TARGETS: dict[str, str] = {
    "NORMAL_GROWTH": "NORMAL_GROWTH",
    "INFLATIONARY": "NORMAL_GROWTH",
    "STAGFLATIONARY": "NORMAL_GROWTH",
    "DEFLATIONARY_CRISIS": "NORMAL_GROWTH",
    "GEOPOLITICAL_STRESS": "NORMAL_GROWTH",
    "STRUCTURAL_REGIME_CHANGE": "NORMAL_GROWTH",
}

BEAR_REGIME_TARGETS: dict[str, str] = {
    "NORMAL_GROWTH": "DEFLATIONARY_CRISIS",
    "INFLATIONARY": "STAGFLATIONARY",
    "STAGFLATIONARY": "DEFLATIONARY_CRISIS",
    "DEFLATIONARY_CRISIS": "DEFLATIONARY_CRISIS",
    "GEOPOLITICAL_STRESS": "STRUCTURAL_REGIME_CHANGE",
    "STRUCTURAL_REGIME_CHANGE": "DEFLATIONARY_CRISIS",
}

BASE_PROBABILITY = 0.5

SCENARIO_DIRECTIONS: dict[str, str] = {
    "bull": "bullish",
    "bear": "bearish",
}


class ScenarioGenerator:
    """Generates base/bull/bear scenarios for every thesis.

    Per the frozen W12 specification, W12 runs before W9 (its downside-case
    output is consumed by W9).  The W9 confidence input is therefore optional:
    when it is absent the generator degrades gracefully to a deterministic
    thesis-derived confidence proxy (PROJECT_SCOPE_V1 sec. 6.6).
    """

    def generate(
        self,
        construction: ThesisConstruction,
        confidence: InstitutionalConfidence | None = None,
    ) -> ScenarioGeneration:
        prov = Provenance(
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="W12 ScenarioGenerator",
            entity_version="1.0.0",
        )

        scenarios: list[InstitutionalScenario] = []
        for thesis in construction.theses:
            tc = self._find_confidence(confidence, thesis.thesis_id)
            if tc is not None:
                confidence_value = tc.final_confidence
            elif confidence is None:
                confidence_value = self._fallback_confidence(thesis)
            else:
                confidence_value = 0.0
            probabilities = self._allocate_probabilities(
                thesis.direction, confidence_value
            )
            for scenario_type in ("base", "bull", "bear"):
                scenarios.append(
                    self._build_scenario(
                        thesis=thesis,
                        confidence=tc,
                        scenario_type=scenario_type,
                        probability=probabilities[scenario_type],
                        provenance=prov,
                        regime=construction.regime,
                        confidence_value=confidence_value,
                    )
                )

        thesis_ids = tuple(t.thesis_id for t in construction.theses)
        consistency = {
            tid: round(
                sum(s.probability for s in scenarios if s.thesis_id == tid), 4
            )
            for tid in thesis_ids
        }

        return ScenarioGeneration(
            scenario_generation_id=f"sg_{uuid4().hex[:12]}",
            construction_id=construction.construction_id,
            confidence_id=(
                confidence.confidence_id
                if confidence
                else f"cf_fallback_{construction.construction_id}"
            ),
            timestamp=datetime.now(timezone.utc).isoformat(),
            regime=construction.regime,
            scenarios=tuple(scenarios),
            thesis_ids=thesis_ids,
            total_scenarios=len(scenarios),
            probability_consistency=consistency,
            metadata={
                "total_theses_covered": len(thesis_ids),
                "scenarios_per_thesis": 3,
                "confidence_source": (
                    "w9" if confidence is not None else "thesis_fallback"
                ),
            },
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _find_confidence(
        self,
        confidence: InstitutionalConfidence | None,
        thesis_id: str,
    ) -> ThesisConfidence | None:
        if confidence is None:
            return None
        for tc in confidence.theses_confidence:
            if tc.thesis_id == thesis_id:
                return tc
        return None

    @staticmethod
    def _fallback_confidence(thesis: InvestmentThesis) -> float:
        inputs = thesis.confidence_inputs or {}
        proxy = float(inputs.get("avg_supporting_weight", 0.0))
        return round(max(0.0, min(proxy, 1.0)), 4)

    def _allocate_probabilities(
        self, direction: str, final_confidence: float
    ) -> dict[str, float]:
        confidence = max(0.0, min(float(final_confidence), 1.0))
        remaining = 1.0 - BASE_PROBABILITY
        if direction == "bullish":
            bull = remaining * (0.55 + 0.2 * confidence)
        elif direction == "bearish":
            bull = remaining * (0.45 - 0.2 * confidence)
        else:
            bull = remaining / 2.0
        bull = round(bull, 4)
        return {
            "base": BASE_PROBABILITY,
            "bull": bull,
            "bear": round(remaining - bull, 4),
        }

    def _build_scenario(
        self,
        thesis: InvestmentThesis,
        confidence: ThesisConfidence | None,
        scenario_type: str,
        probability: float,
        provenance: Provenance,
        regime: str,
        confidence_value: float,
    ) -> InstitutionalScenario:
        mechanism = thesis.economic_mechanism or "underlying economic mechanism"
        if scenario_type == "base":
            expected_direction = thesis.direction
        else:
            expected_direction = SCENARIO_DIRECTIONS.get(scenario_type, "neutral")
        regime_path = self._regime_path(regime, scenario_type)
        base_chain = list(
            confidence.provenance_chain if confidence else thesis.provenance_chain
        ) + [provenance]

        return InstitutionalScenario(
            scenario_id=f"sc_{uuid4().hex[:12]}",
            thesis_id=thesis.thesis_id,
            scenario_type=scenario_type,
            probability=probability,
            expected_direction=expected_direction,
            time_horizon_days=thesis.time_horizon_days,
            expected_catalysts=self._catalysts(thesis, scenario_type, mechanism),
            assumptions=self._assumptions(thesis, scenario_type),
            confirmation_conditions=self._confirmation_conditions(
                thesis, scenario_type, mechanism
            ),
            invalidation_conditions=self._invalidation_conditions(
                thesis, scenario_type, mechanism
            ),
            regime_path=regime_path,
            confidence_inputs={
                "final_confidence": (
                    confidence.final_confidence if confidence else confidence_value
                ),
                "remaining_uncertainty": (
                    confidence.remaining_uncertainty
                    if confidence
                    else round(1.0 - confidence_value, 4)
                ),
                "institutional_support": thesis.institutional_support,
                "reliability_category": (
                    confidence.reliability_category
                    if confidence
                    else ConfidenceComputer().reliability_category(confidence_value)
                ),
            },
            provenance_chain=tuple(base_chain),
            metadata={
                "scenario_label": SCENARIO_TYPE_LABELS[scenario_type],
            },
        )

    def _regime_path(self, regime: str, scenario_type: str) -> tuple[str, ...]:
        if scenario_type == "base":
            return (regime,)
        targets = (
            BULL_REGIME_TARGETS if scenario_type == "bull" else BEAR_REGIME_TARGETS
        )
        target = targets.get(regime, regime)
        return (regime, target)

    def _catalysts(
        self, thesis: InvestmentThesis, scenario_type: str, mechanism: str
    ) -> tuple[str, ...]:
        unknowns = thesis.remaining_unknowns
        if scenario_type == "base":
            parts = [f"mechanism sustains: {mechanism}"]
        elif scenario_type == "bull":
            parts = [f"upside catalyst: {mechanism} accelerates"]
            if unknowns:
                parts.append(f"favorable resolution of: {unknowns[0]}")
        else:
            parts = [f"downside catalyst: {mechanism} breaks down"]
            if unknowns:
                parts.append(f"unfavorable resolution of: {unknowns[0]}")
        return tuple(parts)

    def _assumptions(
        self, thesis: InvestmentThesis, scenario_type: str
    ) -> tuple[str, ...]:
        if scenario_type == "base":
            return ("supporting evidence weights persist across the horizon",)
        if scenario_type == "bull":
            return (
                "unknowns resolve favorably",
                "supporting evidence strengthens",
            )
        return (
            "invalidating conditions materialize",
            "counter-evidence strengthens",
        )

    def _confirmation_conditions(
        self, thesis: InvestmentThesis, scenario_type: str, mechanism: str
    ) -> tuple[str, ...]:
        if scenario_type == "base":
            return (f"{mechanism} continues to develop as expected",)
        if scenario_type == "bull":
            return (f"{mechanism} accelerates", "bullish confirmation signals fire")
        return (f"{mechanism} deteriorates", "bearish confirmation signals fire")

    def _invalidation_conditions(
        self, thesis: InvestmentThesis, scenario_type: str, mechanism: str
    ) -> tuple[str, ...]:
        if scenario_type == "bear":
            return (
                f"{mechanism} proves resilient",
                "thesis invalidating conditions fail to materialize",
            )
        return tuple(thesis.invalidating_conditions)
