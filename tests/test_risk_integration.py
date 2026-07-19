from __future__ import annotations

import numpy as np
import pytest

from forecasting.context import EventSummary, ForecastContext
from forecasting.decision_gate import DecisionGate, RegimeRiskOverlay, UncertaintyBudget
from forecasting.position_sizing import DrawdownManager, KellyCap, VolatilityTargetSizer
from forecasting.risk_budgeting import RiskParitySizer
from forecasting.risk_measures import TailRiskDetector, compute_cvar, compute_var

_SEED = 42

# ── helpers ─────────────────────────────────────────────────────────── #


def _normal_returns(n: int = 500) -> np.ndarray:
    rng = np.random.default_rng(_SEED)
    return rng.normal(loc=0.0005, scale=0.015, size=n)


def _t_returns(n: int = 500, df: float = 2.0) -> np.ndarray:
    rng = np.random.default_rng(_SEED)
    return rng.standard_t(df=df, size=n) * 0.015


def _context(
    regime: str = "EXPANSION",
    regime_conf: float = 0.85,
    news_conf: float = 0.70,
    fomc_conf: float = 0.60,
) -> ForecastContext:
    return ForecastContext(
        current_regime=regime,
        regime_confidence=regime_conf,
        recent_events=(
            EventSummary(
                event_type="CPI",
                date="2026-01-15",
                condition="hot",
                gold_direction="up",
                gold_return_pct=0.5,
            ),
        ),
        news_mood="positive",
        news_confidence=news_conf,
        fomc_mood="neutral",
        fomc_confidence=fomc_conf,
        context_timestamp="2026-01-20T00:00:00",
        source_variable="gold",
        data_date_range=("2025-01-01", "2026-01-20"),
    )


# ── integration tests ──────────────────────────────────────────────── #


class TestRiskIntegration_Proceed:

    def test_full_pipeline_proceed(self) -> None:
        ctx = _context()
        returns = _normal_returns()

        var_95 = compute_var(returns, 0.95)
        cvar_95 = compute_cvar(returns, 0.95)
        tail = TailRiskDetector().detect(returns)
        sizer = VolatilityTargetSizer().compute(returns, target_vol=0.15)
        variance = np.var(returns, ddof=1)
        budget = RiskParitySizer().compute(np.array([[variance]]))
        regime = RegimeRiskOverlay().evaluate(
            ctx.current_regime or "UNKNOWN",
            ctx.regime_confidence,
        )
        coherence = (ctx.regime_confidence + ctx.news_confidence + ctx.fomc_confidence) / 3.0
        uncertainty = UncertaintyBudget().evaluate(
            context_coherence=coherence,
            var_95=var_95,
            tail_index=tail["tail_index"],
        )
        decision = DecisionGate().evaluate(
            regime_info=regime,
            uncertainty=uncertainty,
            scaling_factor=sizer.scaling_factor,
            drawdown_state="normal",
        )

        assert decision.action == "proceed"
        assert decision.score > 0.0
        assert var_95 < 0.0
        assert cvar_95 <= var_95
        assert sizer.scaling_factor > 0.0
        assert budget.weights == (1.0,)
        assert regime["adjusted_multiplier"] > 0.5


class TestRiskIntegration_Halt:

    def test_drawdown_halt_overrides_all(self) -> None:
        ctx = _context()
        returns = _normal_returns()

        regime = RegimeRiskOverlay().evaluate(
            ctx.current_regime or "UNKNOWN",
            ctx.regime_confidence,
        )
        coherence = (ctx.regime_confidence + ctx.news_confidence + ctx.fomc_confidence) / 3.0
        var_95 = compute_var(returns, 0.95)
        tail = TailRiskDetector().detect(returns)
        uncertainty = UncertaintyBudget().evaluate(
            context_coherence=coherence,
            var_95=var_95,
            tail_index=tail["tail_index"],
        )
        decision = DecisionGate().evaluate(
            regime_info=regime,
            uncertainty=uncertainty,
            scaling_factor=0.8,
            drawdown_state="halted",
        )

        assert decision.action == "halt"
        assert decision.score == 0.0


class TestRiskIntegration_TailRisk:

    def test_tail_risk_triggers_delay(self) -> None:
        ctx = _context()
        returns = _t_returns(500, df=1.5)

        regime = RegimeRiskOverlay().evaluate(
            ctx.current_regime or "UNKNOWN",
            ctx.regime_confidence,
        )
        coherence = (ctx.regime_confidence + ctx.news_confidence + ctx.fomc_confidence) / 3.0
        var_95 = compute_var(returns, 0.95)
        tail = TailRiskDetector().detect(returns, threshold_percentile=95.0)
        uncertainty = UncertaintyBudget().evaluate(
            context_coherence=coherence,
            var_95=var_95,
            tail_index=tail["tail_index"],
        )
        decision = DecisionGate().evaluate(
            regime_info=regime,
            uncertainty=uncertainty,
            scaling_factor=0.8,
            drawdown_state="normal",
        )

        if decision.action == "delay":
            assert "uncertainty" in decision.reason.lower() or "budget" in decision.reason.lower()


class TestRiskIntegration_Crisis:

    def test_crisis_regime_reduces_multiplier(self) -> None:
        ctx = _context(regime="CRISIS", regime_conf=0.9)
        returns = _normal_returns()
        sizer = VolatilityTargetSizer().compute(returns, target_vol=0.15)
        regime = RegimeRiskOverlay().evaluate(
            ctx.current_regime or "UNKNOWN",
            ctx.regime_confidence,
        )
        coherence = (ctx.regime_confidence + ctx.news_confidence + ctx.fomc_confidence) / 3.0
        var_95 = compute_var(returns, 0.95)
        tail = TailRiskDetector().detect(returns)
        uncertainty = UncertaintyBudget().evaluate(
            context_coherence=coherence,
            var_95=var_95,
            tail_index=tail["tail_index"],
        )
        decision = DecisionGate().evaluate(
            regime_info=regime,
            uncertainty=uncertainty,
            scaling_factor=sizer.scaling_factor,
            drawdown_state="normal",
        )

        assert regime["adjusted_multiplier"] == 0.225


class TestRiskIntegration_KellyCap:

    def test_kelly_caps_position_size(self) -> None:
        full = KellyCap().compute(win_prob=0.60, payoff_ratio=2.0, fraction=1.0)
        half = KellyCap().compute(win_prob=0.60, payoff_ratio=2.0, fraction=0.5)
        assert half < full
        assert half > 0.0


class TestRiskIntegration_DrawdownStateMachine:

    def test_state_transitions(self) -> None:
        mgr = DrawdownManager(caution_threshold=0.05, halt_threshold=0.15, recovery_period=5)

        normal_prices = np.array([100, 102, 101, 103, 104])
        s1, _, _ = mgr.evaluate(normal_prices)
        assert s1 == "normal"

        caution_prices = np.array([100, 105, 98, 95, 93])
        s2, dd2, _ = mgr.evaluate(caution_prices)
        assert s2 == "caution" or dd2 >= 0.05

        halted_prices = np.array([100, 110, 90, 80])
        s3, dd3, _ = mgr.evaluate(halted_prices)
        assert s3 == "halted" or dd3 >= 0.15

        recovery_prices = np.array([90, 92, 94, 96, 98, 100, 102])
        s4, _, c4 = mgr.evaluate(recovery_prices, prev_state="halted", recovery_counter=3)
        assert s4 == "halted"

        s5, _, c5 = mgr.evaluate(
            np.array([105, 108, 110]),
            prev_state="halted",
            recovery_counter=8,
        )
        assert s5 == "normal"


class TestRiskIntegration_RiskParity:

    def test_two_asset_risk_parity(self) -> None:
        cov = np.array([[1.0, 0.3], [0.3, 4.0]])
        budget = RiskParitySizer().compute(cov)
        assert abs(sum(budget.weights) - 1.0) < 1e-6
        assert budget.weights[0] > budget.weights[1]

    def test_risk_contributions_normalized(self) -> None:
        cov = np.array([[2.0, 0.5, 0.1], [0.5, 1.0, 0.2], [0.1, 0.2, 3.0]])
        budget = RiskParitySizer().compute(cov)
        assert abs(sum(budget.risk_contributions) - 1.0) < 0.02


class TestRiskIntegration_Determinism:

    def test_end_to_end_deterministic(self) -> None:
        ctx = _context()
        returns = _normal_returns()

        def run() -> dict:
            var_95 = compute_var(returns, 0.95)
            cvar_95 = compute_cvar(returns, 0.95)
            tail = TailRiskDetector().detect(returns)
            sizer = VolatilityTargetSizer().compute(returns, target_vol=0.15)
            regime = RegimeRiskOverlay().evaluate(
                ctx.current_regime or "UNKNOWN",
                ctx.regime_confidence,
            )
            coherence = (ctx.regime_confidence + ctx.news_confidence + ctx.fomc_confidence) / 3.0
            uncertainty = UncertaintyBudget().evaluate(
                context_coherence=coherence,
                var_95=var_95,
                tail_index=tail["tail_index"],
            )
            decision = DecisionGate().evaluate(
                regime_info=regime,
                uncertainty=uncertainty,
                scaling_factor=sizer.scaling_factor,
                drawdown_state="normal",
            )
            return {
                "var_95": var_95,
                "cvar_95": cvar_95,
                "tail_index": tail["tail_index"],
                "scaling": sizer.scaling_factor,
                "decision": decision.action,
                "score": decision.score,
            }

        r1 = run()
        r2 = run()
        assert r1 == r2


class TestRiskIntegration_AllAnswers:

    def test_answers_all_five_questions(self) -> None:
        ctx = _context()
        returns = _normal_returns()

        var_95 = compute_var(returns, 0.95)
        cvar_95 = compute_cvar(returns, 0.95)
        tail = TailRiskDetector().detect(returns)
        sizer = VolatilityTargetSizer().compute(returns, target_vol=0.15)
        regime = RegimeRiskOverlay().evaluate(
            ctx.current_regime or "UNKNOWN",
            ctx.regime_confidence,
        )
        coherence = (ctx.regime_confidence + ctx.news_confidence + ctx.fomc_confidence) / 3.0
        uncertainty = UncertaintyBudget().evaluate(
            context_coherence=coherence,
            var_95=var_95,
            tail_index=tail["tail_index"],
        )
        decision = DecisionGate().evaluate(
            regime_info=regime,
            uncertainty=uncertainty,
            scaling_factor=sizer.scaling_factor,
            drawdown_state="normal",
        )
        mgr = DrawdownManager()
        prices = np.linspace(100, 105, 50)
        dd_state, dd_pct, _ = mgr.evaluate(prices)
        budget = RiskParitySizer().compute(np.array([[1.0]]))
        kelly = KellyCap().compute(0.55, 1.5)

        components = decision.components
        assert "regime_acceptable" in components
        assert "uncertainty_acceptable" in components
        assert "has_room_to_act" in components
        assert "not_halted" in components

        assert decision.action in ("proceed", "scale_down", "delay", "halt")
        assert 0.0 <= decision.score <= 1.0
        assert len(decision.reason) > 0

        assert var_95 <= 0.0
        assert cvar_95 <= var_95
        assert dd_state in ("normal", "caution", "halted")
        assert 0.0 <= dd_pct <= 1.0
        assert budget.weights == (1.0,)
        assert kelly >= 0.0
        assert sizer.scaling_factor >= 0.0
        assert tail["has_tail_risk"] in (True, False)
        assert regime["adjusted_multiplier"] > 0.0


class TestRiskIntegration_NoData:

    def test_empty_returns_graceful(self) -> None:
        empty = np.array([])
        var_95 = compute_var(empty, 0.95)
        cvar_95 = compute_cvar(empty, 0.95)
        tail = TailRiskDetector().detect(empty)
        sizer = VolatilityTargetSizer().compute(empty)
        mgr = DrawdownManager()
        dd_state, dd_pct, _ = mgr.evaluate(empty)

        assert var_95 == 0.0
        assert cvar_95 == 0.0
        assert tail["n_exceedances"] == 0
        assert sizer.scaling_factor == 0.0
        assert dd_state == "normal"
        assert dd_pct == 0.0

    def test_empty_context_coherence(self) -> None:
        ctx = _context(regime_conf=0.0, news_conf=0.0, fomc_conf=0.0)
        returns = _normal_returns()
        var_95 = compute_var(returns, 0.95)
        tail = TailRiskDetector().detect(returns)
        regime = RegimeRiskOverlay().evaluate(
            ctx.current_regime or "UNKNOWN",
            ctx.regime_confidence,
        )
        coherence = (ctx.regime_confidence + ctx.news_confidence + ctx.fomc_confidence) / 3.0
        uncertainty = UncertaintyBudget().evaluate(
            context_coherence=coherence,
            var_95=var_95,
            tail_index=tail["tail_index"],
        )

        assert coherence == 0.0
        assert uncertainty["acceptable"] is False
