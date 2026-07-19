from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RiskDecision:
    action: str
    reason: str
    score: float
    components: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "score": self.score,
            "components": dict(self.components),
        }


_REGIME_MULTIPLIERS: dict[str, float] = {
    "EXPANSION": 1.0,
    "STAGNATION": 0.75,
    "LATE_CYCLE": 0.75,
    "CONTRACTION": 0.50,
    "RECOVERY": 0.75,
    "CRISIS": 0.25,
    "UNKNOWN": 0.50,
}


class RegimeRiskOverlay:

    def evaluate(self, regime: str, regime_confidence: float) -> dict[str, Any]:
        if regime_confidence < 0.0 or regime_confidence > 1.0:
            raise ValueError("regime_confidence must be in [0, 1]")
        base = _REGIME_MULTIPLIERS.get(regime, 0.50)
        adjusted = base * regime_confidence
        return {
            "regime": regime,
            "regime_confidence": regime_confidence,
            "base_multiplier": base,
            "adjusted_multiplier": round(adjusted, 6),
        }


class UncertaintyBudget:

    def evaluate(
        self,
        context_coherence: float,
        var_95: float,
        tail_index: float | None,
        max_tolerable_var: float = -0.05,
        coherence_threshold: float = 0.30,
        tail_threshold: float = 0.50,
    ) -> dict[str, Any]:
        coherence_ok = bool(context_coherence >= coherence_threshold)
        var_ok = bool(var_95 >= max_tolerable_var)
        tail_ok = True
        if tail_index is not None:
            tail_ok = bool(tail_index <= tail_threshold)
        acceptable = bool(coherence_ok and var_ok and tail_ok)
        return {
            "acceptable": acceptable,
            "coherence_ok": coherence_ok,
            "var_ok": var_ok,
            "tail_ok": tail_ok,
        }


class DecisionGate:

    def evaluate(
        self,
        regime_info: dict[str, Any],
        uncertainty: dict[str, Any],
        scaling_factor: float,
        drawdown_state: str,
        min_scaling: float = 0.30,
    ) -> RiskDecision:
        if scaling_factor < 0.0 or scaling_factor > 1.0:
            raise ValueError("scaling_factor must be in [0, 1]")

        regime_mult = regime_info.get("adjusted_multiplier", 0.5)
        uncertainty_acceptable = uncertainty.get("acceptable", False)
        has_room = bool(scaling_factor >= min_scaling)
        not_halted = bool(drawdown_state != "halted")
        not_caution = bool(drawdown_state != "caution")

        components: dict[str, bool] = {
            "regime_acceptable": bool(regime_mult >= 0.25),
            "uncertainty_acceptable": uncertainty_acceptable,
            "has_room_to_act": has_room,
            "not_halted": not_halted,
            "not_caution": not_caution,
        }

        score = regime_mult * (0.40 if uncertainty_acceptable else 0.15)
        score *= scaling_factor
        if drawdown_state == "halted":
            score *= 0.0
        elif drawdown_state == "caution":
            score *= 0.5
        score = max(0.0, min(1.0, round(score, 4)))

        if not_halted and has_room and uncertainty_acceptable and regime_mult >= 0.25:
            if not_caution:
                return RiskDecision(
                    action="proceed",
                    reason="All risk gates pass. Full allocation advised.",
                    score=score,
                    components=components,
                )
            return RiskDecision(
                action="scale_down",
                reason="Drawdown caution active. Reduce position size.",
                score=score,
                components=components,
            )

        if drawdown_state == "halted":
            return RiskDecision(
                action="halt",
                reason="Drawdown limit breached. All positions halted.",
                score=0.0,
                components=components,
            )

        if not has_room:
            return RiskDecision(
                action="delay",
                reason=f"Scaling factor {scaling_factor:.3f} below minimum {min_scaling:.2f}. "
                       "Insufficient room to act.",
                score=score,
                components=components,
            )

        if not uncertainty_acceptable:
            return RiskDecision(
                action="delay",
                reason="Uncertainty budget exceeded. Forecast confidence too low.",
                score=score,
                components=components,
            )

        if regime_mult < 0.25:
            return RiskDecision(
                action="delay",
                reason=f"Regime multiplier {regime_mult:.3f} too low. "
                       "Market conditions too adverse.",
                score=score,
                components=components,
            )

        return RiskDecision(
            action="scale_down",
            reason="Partial risk gate failure. Reduce allocation.",
            score=score,
            components=components,
        )
