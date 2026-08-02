"""W14 Institutional Trade Recommendation: transforms the W13
InstitutionalDecision into a complete, explainable trading recommendation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from decision_engine.contracts import InstitutionalDecision
from knowledge.integrity.provenance import Provenance
from trade_recommendation.contracts import InstitutionalTradeRecommendation

DEFAULT_INSTRUMENT = "XAU/USD"

ENTRY_BUFFER_PCT = 0.25
MAX_RISK_PCT = 2.0
MIN_HOLDING_DAYS = 30
BASE_HOLDING_DAYS = 120

SUPPORTING_DRIVER_MIN = 0.5


class RecommendationEngine:
    """Produces exactly one recommendation per decision; the action always
    mirrors the decision, and no trading level is emitted for HOLD/NO TRADE."""

    def recommend(
        self,
        decision: InstitutionalDecision,
        instrument: str = DEFAULT_INSTRUMENT,
        reference_price: float | None = None,
    ) -> InstitutionalTradeRecommendation:
        prov = Provenance(
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="W14 RecommendationEngine",
            entity_version="1.0.0",
        )
        chain = list(decision.provenance_chain) + [prov]

        summary = self._decision_summary(decision)
        thesis_summary = self._thesis_summary(decision)
        supporting = self._major_supporting_evidence(decision)
        counter = self._major_counter_evidence(decision)

        action = decision.decision
        if action in {"BUY", "SELL"}:
            levels = self._trading_levels(decision, action, reference_price)
            risk_pct = min(
                round(0.25 + 1.0 * decision.institutional_confidence, 2),
                MAX_RISK_PCT,
            )
            liquidity_risk = float(
                decision.risk_reward_summary.get("liquidity_risk", 0.0)
            )
            holding_days = max(
                MIN_HOLDING_DAYS,
                round(BASE_HOLDING_DAYS - 90.0 * liquidity_risk),
            )
            position_size = (
                f"risk {risk_pct}% of capital against stop loss at "
                f"{levels['stop_loss']}"
            )
            return InstitutionalTradeRecommendation(
                recommendation_id=f"rec_{uuid4().hex[:12]}",
                decision_id=decision.decision_id,
                recommendation_action=action,
                instrument=instrument,
                entry_zone=levels["entry_zone"],
                stop_loss=levels["stop_loss"],
                take_profit_1=levels["take_profit_1"],
                take_profit_2=levels["take_profit_2"],
                position_size_recommendation=position_size,
                risk_pct=risk_pct,
                expected_holding_days=holding_days,
                confidence=decision.institutional_confidence,
                decision_summary=summary,
                institutional_thesis_summary=thesis_summary,
                major_supporting_evidence=supporting,
                major_counter_evidence=counter,
                preconditions=decision.preconditions,
                invalidation_conditions=decision.invalidation_conditions,
                monitoring_conditions=self._monitoring_conditions(decision),
                provenance_chain=tuple(chain),
                metadata={
                    "selected_thesis_id": decision.selected_thesis_id,
                    "selected_scenario_id": decision.selected_scenario_id,
                    "reference_price": reference_price,
                },
            )

        return InstitutionalTradeRecommendation(
            recommendation_id=f"rec_{uuid4().hex[:12]}",
            decision_id=decision.decision_id,
            recommendation_action=action,
            instrument=instrument,
            entry_zone=(),
            stop_loss="",
            take_profit_1="",
            take_profit_2="",
            position_size_recommendation="",
            risk_pct=0.0,
            expected_holding_days=0,
            confidence=decision.institutional_confidence,
            decision_summary=summary,
            institutional_thesis_summary=thesis_summary,
            major_supporting_evidence=supporting,
            major_counter_evidence=counter,
            preconditions=decision.preconditions,
            invalidation_conditions=decision.invalidation_conditions,
            monitoring_conditions=self._monitoring_conditions(decision),
            provenance_chain=tuple(chain),
            metadata={
                "selected_thesis_id": decision.selected_thesis_id,
                "selected_scenario_id": decision.selected_scenario_id,
                "reference_price": reference_price,
            },
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _trading_levels(
        self,
        decision: InstitutionalDecision,
        action: str,
        reference_price: float | None,
    ) -> dict[str, Any]:
        rr = decision.risk_reward_summary or {}
        maximum_downside = float(rr.get("maximum_downside", 0.0))
        expected_upside = float(rr.get("expected_upside", 0.0))
        stop_pct = round(0.5 + 1.5 * maximum_downside, 2)
        upside_pct = round(0.75 + 2.25 * expected_upside, 2)
        tp1_pct = round(0.5 * upside_pct, 2)

        def level(base_pct: float) -> str:
            if reference_price is not None:
                return f"{reference_price * (1.0 + base_pct / 100.0):.2f}"
            prefix = "+" if base_pct >= 0.0 else "-"
            return f"anchor {prefix}{abs(base_pct)}%"

        if action == "BUY":
            entry_zone = (level(0.0), level(ENTRY_BUFFER_PCT))
            return {
                "entry_zone": entry_zone,
                "stop_loss": level(-stop_pct),
                "take_profit_1": level(tp1_pct),
                "take_profit_2": level(upside_pct),
            }
        entry_zone = (level(-ENTRY_BUFFER_PCT), level(0.0))
        return {
            "entry_zone": entry_zone,
            "stop_loss": level(stop_pct),
            "take_profit_1": level(-tp1_pct),
            "take_profit_2": level(-upside_pct),
        }

    @staticmethod
    def _decision_summary(decision: InstitutionalDecision) -> str:
        rr = decision.risk_reward_summary or {}
        return (
            f"decision={decision.decision}; confidence={decision.institutional_confidence}; "
            f"risk_reward_status={rr.get('status', 'n/a')}; "
            f"risk_reward_ratio={rr.get('risk_reward_ratio', 'n/a')}; "
            f"selected_thesis={decision.selected_thesis_id or 'none'}"
        )

    @staticmethod
    def _thesis_summary(decision: InstitutionalDecision) -> str:
        return decision.decision_explanation or "no institutional thesis summary available"

    @staticmethod
    def _major_supporting_evidence(decision: InstitutionalDecision) -> tuple[str, ...]:
        evidence: list[str] = []
        for driver in decision.decision_drivers:
            if driver.value >= SUPPORTING_DRIVER_MIN:
                evidence.append(
                    f"{driver.name}={driver.value} (weight {driver.weight})"
                )
        if not evidence and decision.decision != "NO_TRADE":
            evidence.append("no driver exceeded the supporting evidence threshold")
        return tuple(evidence)

    @staticmethod
    def _major_counter_evidence(decision: InstitutionalDecision) -> tuple[str, ...]:
        counter: list[str] = []
        for driver in decision.decision_drivers:
            if driver.name == "counter_evidence_quality" and driver.value < 1.0:
                counter.append(
                    f"counter-evidence penalty={round(1.0 - driver.value, 4)} "
                    f"(counter_evidence_quality={driver.value})"
                )
        for alt in decision.rejected_alternatives:
            counter.append(
                f"rejected thesis {alt.thesis_id} ({alt.thesis_direction}, "
                f"score {alt.composite_score}): {alt.rejection_reason}"
            )
        return tuple(counter)

    @staticmethod
    def _monitoring_conditions(decision: InstitutionalDecision) -> tuple[str, ...]:
        conditions: list[str] = [
            "re-evaluate when new evidence arrives or institutional confidence changes by more than 0.1",
            "review on regime transition or when invalidation triggers come into proximity",
        ]
        for condition in decision.invalidation_conditions:
            conditions.append(f"monitor: {condition}")
        return tuple(conditions)
