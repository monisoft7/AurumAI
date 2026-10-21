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


def apply_institutional_risk_gate(
    decision: str,
    confidence: float,
    structure: str | None = None,
    current_risk_status: str = "proceed",
    human_review: bool = False,
) -> dict[str, Any]:
    """Enforces strict institutional gating rules:
    - Rule A (Confidence Threshold): If confidence < 60.0%, force NEUTRAL / WAIT, set risk_gate = 'hold', mark trade levels as watchlist.
    - Rule B (Gray Zone 60% - 65%): If 60.0% <= confidence < 65.0%, allow directional bias ONLY if structure aligns, force human_review = True.
    - Rule C (Structure vs. Direction Conflict): If BUY in downtrend or SELL in uptrend, penalize confidence by -10% OR require confidence >= 70% with human_review = True.
    """
    conf = float(confidence) / 100.0 if float(confidence) > 1.0 else float(confidence)
    struct = str(structure or "").lower().strip()
    dir_norm = str(decision or "HOLD").upper().strip()
    action_out = dir_norm
    risk_gate_out = str(current_risk_status or "proceed").lower()
    review_out = bool(human_review)
    review_reason = ""
    gate_reason = ""
    watchlist_only = False

    # Check Rule C: Structure vs. Direction Conflict
    is_conflict = (dir_norm == "BUY" and struct == "downtrend") or (dir_norm == "SELL" and struct == "uptrend")
    if is_conflict:
        conf_penalized = max(0.0, conf - 0.10)
        if conf >= 0.70:
            # Macro override allowed, but requires human review
            review_out = True
            review_reason = "مطلوبة - تعارض هيكلي"
            gate_reason = "macro_override_with_structural_conflict"
            if conf_penalized < 0.60:
                action_out = "WAIT"
                risk_gate_out = "hold"
                watchlist_only = True
                gate_reason = "structural_conflict_penalized_below_threshold"
        else:
            conf = conf_penalized
            action_out = "WAIT"
            risk_gate_out = "hold"
            review_out = True
            watchlist_only = True
            review_reason = "مطلوبة - تعارض هيكلي"
            gate_reason = "structural_conflict_rejected"

    # Check Rule A: Confidence Threshold < 60.0%
    if conf < 0.60:
        action_out = "WAIT"
        risk_gate_out = "hold"
        watchlist_only = True
        if not gate_reason:
            gate_reason = "confidence_below_60_threshold"
        if not review_reason and review_out:
            review_reason = "مطلوبة"

    # Check Rule B: Gray Zone 60.0% - 65.0%
    elif 0.60 <= conf < 0.65:
        aligned = (dir_norm == "BUY" and struct == "uptrend") or (dir_norm == "SELL" and struct == "downtrend")
        review_out = True
        if not review_reason:
            review_reason = "مطلوبة"
        if not aligned:
            action_out = "WAIT"
            risk_gate_out = "hold"
            watchlist_only = True
            gate_reason = "gray_zone_structure_unaligned"
        else:
            gate_reason = "gray_zone_structure_aligned"

    return {
        "action": action_out,
        "confidence": conf,
        "risk_status": risk_gate_out,
        "human_review": review_out,
        "human_review_reason": review_reason,
        "gate_reason": gate_reason,
        "watchlist_only": watchlist_only,
    }


class DecisionGate:

    def evaluate(
        self,
        regime_info: dict[str, Any],
        uncertainty: dict[str, Any],
        scaling_factor: float,
        drawdown_state: str,
        min_scaling: float = 0.30,
        confidence: float | None = None,
        market_structure: str | None = None,
        action_bias: str | None = None,
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
            if confidence is not None:
                gate_check = apply_institutional_risk_gate(
                    decision=action_bias or "BUY",
                    confidence=confidence,
                    structure=market_structure,
                    current_risk_status="proceed" if not_caution else "scale_down",
                )
                components["institutional_confidence_acceptable"] = bool(gate_check["risk_status"] != "hold")
                if gate_check["risk_status"] == "hold":
                    return RiskDecision(
                        action="hold",
                        reason=f"Institutional risk gate: {gate_check['gate_reason']}",
                        score=score,
                        components=components,
                    )
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
