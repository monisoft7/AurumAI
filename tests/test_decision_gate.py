from __future__ import annotations

import pytest

from forecasting.decision_gate import (
    DecisionGate,
    RegimeRiskOverlay,
    RiskDecision,
    UncertaintyBudget,
)


class TestRiskDecision:

    def test_frozen(self) -> None:
        d = RiskDecision(action="proceed", reason="OK", score=0.8, components={"safe": True})
        with pytest.raises(AttributeError):
            d.action = "halt"  # type: ignore[misc]

    def test_all_fields(self) -> None:
        d = RiskDecision(action="halt", reason="Drawdown", score=0.0, components={"safe": False})
        assert d.action == "halt"
        assert d.score == 0.0
        assert d.components == {"safe": False}

    def test_to_dict(self) -> None:
        d = RiskDecision(action="delay", reason="Unsure", score=0.25, components={"a": True, "b": False})
        out = d.to_dict()
        assert out["action"] == "delay"
        assert out["components"] == {"a": True, "b": False}


class TestRegimeRiskOverlay:

    def test_expansion(self) -> None:
        r = RegimeRiskOverlay().evaluate("EXPANSION", 1.0)
        assert r["adjusted_multiplier"] == 1.0

    def test_crisis(self) -> None:
        r = RegimeRiskOverlay().evaluate("CRISIS", 1.0)
        assert r["adjusted_multiplier"] == 0.25

    def test_unknown_regime(self) -> None:
        r = RegimeRiskOverlay().evaluate("UNKNOWN_REGIME", 0.8)
        assert r["adjusted_multiplier"] == 0.4

    def test_low_confidence_reduces_multiplier(self) -> None:
        r_high = RegimeRiskOverlay().evaluate("CONTRACTION", 1.0)
        r_low = RegimeRiskOverlay().evaluate("CONTRACTION", 0.5)
        assert r_high["adjusted_multiplier"] > r_low["adjusted_multiplier"]

    def test_invalid_confidence(self) -> None:
        with pytest.raises(ValueError, match="regime_confidence"):
            RegimeRiskOverlay().evaluate("EXPANSION", 1.5)

    def test_return_structure(self) -> None:
        r = RegimeRiskOverlay().evaluate("RECOVERY", 0.9)
        assert set(r.keys()) == {"regime", "regime_confidence", "base_multiplier", "adjusted_multiplier"}

    def test_all_regimes_have_multipliers(self) -> None:
        regimes = ["EXPANSION", "STAGNATION", "LATE_CYCLE", "CONTRACTION", "RECOVERY", "CRISIS", "UNKNOWN"]
        for regime in regimes:
            r = RegimeRiskOverlay().evaluate(regime, 1.0)
            assert 0.0 < r["adjusted_multiplier"] <= 1.0


class TestUncertaintyBudget:

    def test_all_ok(self) -> None:
        u = UncertaintyBudget().evaluate(
            context_coherence=0.8, var_95=-0.02, tail_index=0.3,
        )
        assert u["acceptable"] is True

    def test_low_coherence(self) -> None:
        u = UncertaintyBudget().evaluate(
            context_coherence=0.1, var_95=-0.02, tail_index=0.3,
        )
        assert u["acceptable"] is False
        assert u["coherence_ok"] is False

    def test_var_breach(self) -> None:
        u = UncertaintyBudget().evaluate(
            context_coherence=0.8, var_95=-0.10, tail_index=0.3,
        )
        assert u["acceptable"] is False
        assert u["var_ok"] is False

    def test_tail_risk(self) -> None:
        u = UncertaintyBudget().evaluate(
            context_coherence=0.8, var_95=-0.02, tail_index=0.7,
        )
        assert u["acceptable"] is False
        assert u["tail_ok"] is False

    def test_none_tail_index(self) -> None:
        u = UncertaintyBudget().evaluate(
            context_coherence=0.8, var_95=-0.02, tail_index=None,
        )
        assert u["acceptable"] is True

    def test_deterministic(self) -> None:
        args = dict(context_coherence=0.6, var_95=-0.03, tail_index=0.2)
        u1 = UncertaintyBudget().evaluate(**args)
        u2 = UncertaintyBudget().evaluate(**args)
        assert u1 == u2


class TestDecisionGate:

    def test_proceed(self) -> None:
        d = DecisionGate().evaluate(
            regime_info={"adjusted_multiplier": 1.0},
            uncertainty={"acceptable": True},
            scaling_factor=0.8,
            drawdown_state="normal",
        )
        assert d.action == "proceed"
        assert d.score > 0.0

    def test_halt(self) -> None:
        d = DecisionGate().evaluate(
            regime_info={"adjusted_multiplier": 0.5},
            uncertainty={"acceptable": True},
            scaling_factor=0.8,
            drawdown_state="halted",
        )
        assert d.action == "halt"
        assert d.score == 0.0

    def test_scale_down_in_caution(self) -> None:
        d = DecisionGate().evaluate(
            regime_info={"adjusted_multiplier": 1.0},
            uncertainty={"acceptable": True},
            scaling_factor=0.8,
            drawdown_state="caution",
        )
        assert d.action == "scale_down"

    def test_delay_low_scaling(self) -> None:
        d = DecisionGate().evaluate(
            regime_info={"adjusted_multiplier": 1.0},
            uncertainty={"acceptable": True},
            scaling_factor=0.1,
            drawdown_state="normal",
        )
        assert d.action == "delay"

    def test_delay_uncertainty(self) -> None:
        d = DecisionGate().evaluate(
            regime_info={"adjusted_multiplier": 1.0},
            uncertainty={"acceptable": False},
            scaling_factor=0.8,
            drawdown_state="normal",
        )
        assert d.action == "delay"

    def test_delay_low_regime_mult(self) -> None:
        d = DecisionGate().evaluate(
            regime_info={"adjusted_multiplier": 0.1},
            uncertainty={"acceptable": True},
            scaling_factor=0.8,
            drawdown_state="normal",
        )
        assert d.action == "delay"

    def test_invalid_scaling(self) -> None:
        with pytest.raises(ValueError, match="scaling_factor"):
            DecisionGate().evaluate(
                regime_info={"adjusted_multiplier": 1.0},
                uncertainty={"acceptable": True},
                scaling_factor=-0.1,
                drawdown_state="normal",
            )

    def test_scale_down_fallback(self) -> None:
        d = DecisionGate().evaluate(
            regime_info={"adjusted_multiplier": 0.2},
            uncertainty={"acceptable": False},
            scaling_factor=0.4,
            drawdown_state="caution",
        )
        assert d.action in ("scale_down", "delay")

    def test_score_reflects_risk(self) -> None:
        d_low = DecisionGate().evaluate(
            regime_info={"adjusted_multiplier": 1.0},
            uncertainty={"acceptable": True},
            scaling_factor=1.0,
            drawdown_state="normal",
        )
        d_high = DecisionGate().evaluate(
            regime_info={"adjusted_multiplier": 0.5},
            uncertainty={"acceptable": True},
            scaling_factor=0.5,
            drawdown_state="normal",
        )
        assert d_low.score >= d_high.score

    def test_components_in_decision(self) -> None:
        d = DecisionGate().evaluate(
            regime_info={"adjusted_multiplier": 1.0},
            uncertainty={"acceptable": True},
            scaling_factor=0.8,
            drawdown_state="normal",
        )
        assert "regime_acceptable" in d.components
        assert "uncertainty_acceptable" in d.components
        assert "has_room_to_act" in d.components
        assert "not_halted" in d.components

    def test_deterministic(self) -> None:
        args = dict(
            regime_info={"adjusted_multiplier": 0.75},
            uncertainty={"acceptable": True},
            scaling_factor=0.6,
            drawdown_state="normal",
        )
        d1 = DecisionGate().evaluate(**args)
        d2 = DecisionGate().evaluate(**args)
        assert d1.action == d2.action
        assert d1.score == d2.score
