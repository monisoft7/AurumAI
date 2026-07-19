from __future__ import annotations

import pytest

from execution.commission import FixedCommissionModel, PercentageCommissionModel
from execution.execution_engine import (
    DECISION_INSUFFICIENT_EVIDENCE,
    DECISION_NEGATIVE,
    DECISION_NEUTRAL,
    DECISION_POSITIVE,
    DECISION_STRONG_NEGATIVE,
    DECISION_STRONG_POSITIVE,
    ExecutionDecision,
    ExecutionEngine,
    ExecutionResult,
)
from execution.portfolio import VirtualPortfolio
from execution.slippage import FixedSlippageModel, PercentageSlippageModel


class TestExecutionDecision:
    def test_values(self) -> None:
        assert ExecutionDecision.EXECUTE.value == "execute"
        assert ExecutionDecision.REJECT.value == "reject"
        assert ExecutionDecision.HOLD.value == "hold"


class TestExecutionResult:
    def test_construction(self) -> None:
        r = ExecutionResult(
            decision=ExecutionDecision.EXECUTE,
            reason="test",
            assessment_id="A001",
        )
        assert r.decision == ExecutionDecision.EXECUTE
        assert r.reason == "test"
        assert r.assessment_id == "A001"

    def test_frozen(self) -> None:
        r = ExecutionResult(
            decision=ExecutionDecision.EXECUTE,
            reason="test",
            assessment_id="A001",
        )
        with pytest.raises(AttributeError):
            r.reason = "changed"  # type: ignore[misc]

    def test_to_dict_execute(self) -> None:
        r = ExecutionResult(
            decision=ExecutionDecision.EXECUTE,
            reason="Executed BUY 10 @ 100.50",
            assessment_id="A001",
            decision_type=DECISION_STRONG_POSITIVE,
            risk_action="proceed",
            slippage_applied=0.50,
            commission_applied=1.00,
            executed_price=100.50,
        )
        d = r.to_dict()
        assert d["decision"] == "execute"
        assert d["reason"] == "Executed BUY 10 @ 100.50"
        assert d["assessment_id"] == "A001"
        assert d["slippage_applied"] == 0.50
        assert d["commission_applied"] == 1.00

    def test_to_dict_reject(self) -> None:
        r = ExecutionResult(
            decision=ExecutionDecision.REJECT,
            reason="Risk gate rejected: action='halt'",
            assessment_id="A001",
            decision_type=DECISION_STRONG_POSITIVE,
            risk_action="halt",
        )
        d = r.to_dict()
        assert d["decision"] == "reject"
        assert "trade" not in d
        assert "snapshot" not in d


class TestExecutionEngineReject:
    def test_missing_decision_type(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, assessment_id="A001")
        assert r.decision == ExecutionDecision.REJECT
        assert "Unknown" in r.reason

    def test_unknown_decision_type(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type="UNKNOWN",
                         assessment_id="A001")
        assert r.decision == ExecutionDecision.REJECT

    def test_risk_action_halt(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         risk_action="halt", assessment_id="A001")
        assert r.decision == ExecutionDecision.REJECT
        assert "halt" in r.reason

    def test_risk_action_delay(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         risk_action="delay", assessment_id="A001")
        assert r.decision == ExecutionDecision.REJECT
        assert "delay" in r.reason

    def test_portfolio_unchanged_on_reject(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        _ = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         risk_action="halt", assessment_id="A001")
        assert p.cash == 100_000.0
        assert len(p.positions) == 0

    def test_neutral_decision_returns_hold(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_NEUTRAL,
                         assessment_id="A001")
        assert r.decision == ExecutionDecision.HOLD
        assert "NEUTRAL" in r.reason

    def test_insufficient_evidence_returns_hold(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0,
                         decision_type=DECISION_INSUFFICIENT_EVIDENCE,
                         assessment_id="A001")
        assert r.decision == ExecutionDecision.HOLD

    def test_zero_position_size_returns_hold(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=0.0, decision_type=DECISION_STRONG_POSITIVE,
                         assessment_id="A001")
        assert r.decision == ExecutionDecision.HOLD

    def test_negative_position_size_returns_hold(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=-5.0, decision_type=DECISION_STRONG_POSITIVE,
                         assessment_id="A001")
        assert r.decision == ExecutionDecision.HOLD


class TestExecutionEngineBuy:
    def test_strong_positive_buys(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         assessment_id="A001")
        assert r.decision == ExecutionDecision.EXECUTE
        assert "BUY" in r.reason
        assert r.trade is not None
        assert r.trade.action == "BUY"
        assert r.trade.quantity == 10.0
        assert r.snapshot is not None
        assert 10.0 * 2000.0 < p.initial_capital - p.cash + 1e-9

    def test_positive_buys(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=5.0, decision_type=DECISION_POSITIVE,
                         assessment_id="A001")
        assert r.decision == ExecutionDecision.EXECUTE
        assert r.trade is not None
        assert r.trade.action == "BUY"
        assert r.trade.quantity == 5.0

    def test_portfolio_updated_after_buy(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        _ = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         assessment_id="A001")
        assert len(p.positions) == 1
        pos = p.positions[0]
        assert pos.asset_id == "XAU/USD"
        assert pos.quantity == 10.0
        assert p.cash == 100_000.0 - 10.0 * 2000.0

    def test_insufficient_cash_rejected(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(10_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         assessment_id="A001")
        assert r.decision == ExecutionDecision.REJECT
        assert "Insufficient cash" in r.reason

    def test_slippage_applied_to_buy_price(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        slip = FixedSlippageModel(0.50)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         slippage_model=slip, assessment_id="A001")
        assert abs(r.executed_price - 2000.50) < 1e-9
        assert r.slippage_applied == 5.0
        cash_spent = 100_000.0 - p.cash
        assert abs(cash_spent - 10.0 * 2000.50) < 1e-9

    def test_commission_deducted_on_buy(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        comm = FixedCommissionModel(15.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         commission_model=comm, assessment_id="A001")
        assert r.commission_applied == 15.0
        assert p.cash == 100_000.0 - 10.0 * 2000.0 - 15.0

    def test_both_slippage_and_commission(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        slip = FixedSlippageModel(0.10)
        comm = PercentageCommissionModel(0.001)
        r = eng.evaluate(p, "XAU/USD", 1000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         slippage_model=slip, commission_model=comm,
                         assessment_id="A001")
        assert r.decision == ExecutionDecision.EXECUTE
        assert abs(r.executed_price - 1000.10) < 1e-9
        assert r.slippage_applied == 1.0
        expected_comm = 10.0 * 1000.10 * 0.001
        assert abs(r.commission_applied - expected_comm) < 1e-9


class TestExecutionEngineSell:
    def test_negative_sells_long_position(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T01:00:00",
                         position_size=5.0, decision_type=DECISION_NEGATIVE,
                         assessment_id="A001")
        assert r.decision == ExecutionDecision.EXECUTE
        assert r.trade is not None
        assert r.trade.action == "SELL"
        assert r.trade.quantity == 5.0
        assert r.snapshot is not None

    def test_strong_negative_sells_full_long(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T01:00:00",
                         position_size=20.0, decision_type=DECISION_STRONG_NEGATIVE,
                         assessment_id="A001")
        assert r.decision == ExecutionDecision.EXECUTE
        assert r.trade is not None
        assert r.trade.action == "SELL"
        assert r.trade.quantity == 10.0

    def test_sell_excessive_quantity_raises(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 5.0, 1950.0, "2026-01-01T00:00:00")
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T01:00:00",
                         position_size=10.0, decision_type=DECISION_NEGATIVE,
                         assessment_id="A001")
        assert r.decision == ExecutionDecision.REJECT
        assert "held long" in r.reason

    def test_sell_slippage_applied(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        slip = FixedSlippageModel(0.25)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T01:00:00",
                         position_size=5.0, decision_type=DECISION_NEGATIVE,
                         slippage_model=slip, assessment_id="A001")
        assert abs(r.executed_price - 1999.75) < 1e-9


class TestExecutionEngineShort:
    def test_negative_without_position_shorts(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_NEGATIVE,
                         assessment_id="A001")
        assert r.decision == ExecutionDecision.EXECUTE
        assert r.trade is not None
        assert r.trade.action == "SHORT"
        assert r.trade.quantity == 10.0

    def test_short_with_slippage(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        slip = FixedSlippageModel(0.50)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_NEGATIVE,
                         slippage_model=slip, assessment_id="A001")
        assert abs(r.executed_price - 1999.50) < 1e-9
        cash_increase = p.cash - 100_000.0
        assert abs(cash_increase - 10.0 * 1999.50) < 1e-9

    def test_short_with_commission(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        comm = PercentageCommissionModel(0.001)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_NEGATIVE,
                         commission_model=comm, assessment_id="A001")
        assert r.decision == ExecutionDecision.EXECUTE
        expected_comm = 10.0 * 2000.0 * 0.001
        assert abs(r.commission_applied - expected_comm) < 1e-9


class TestExecutionEngineEmptyModels:
    def test_no_slippage_model(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         assessment_id="A001")
        assert abs(r.executed_price - 2000.0) < 1e-9
        assert r.slippage_applied == 0.0

    def test_no_commission_model(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         assessment_id="A001")
        assert r.commission_applied == 0.0
        assert p.cash == 100_000.0 - 10.0 * 2000.0


class TestExecutionEngineResultFields:
    def test_execute_result_has_trade_and_snapshot(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         assessment_id="A001")
        assert r.trade is not None
        assert r.snapshot is not None

    def test_execute_result_to_dict_contains_trade_and_snapshot(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         assessment_id="A001")
        d = r.to_dict()
        assert "trade" in d
        assert "snapshot" in d

    def test_reject_result_has_no_trade(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         risk_action="halt", assessment_id="A001")
        assert r.trade is None
        assert r.snapshot is None

    def test_hold_result_has_no_trade(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_NEUTRAL,
                         assessment_id="A001")
        assert r.trade is None
        assert r.snapshot is None


class TestExecutionEngineDeterminism:
    def test_same_input_same_result(self) -> None:
        eng = ExecutionEngine()
        slip = PercentageSlippageModel(0.0005)
        comm = FixedCommissionModel(5.0)

        p1 = VirtualPortfolio(100_000.0)
        r1 = eng.evaluate(p1, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                          position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                          slippage_model=slip, commission_model=comm,
                          assessment_id="A001")

        p2 = VirtualPortfolio(100_000.0)
        r2 = eng.evaluate(p2, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                          position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                          slippage_model=slip, commission_model=comm,
                          assessment_id="A001")

        assert r1.executed_price == r2.executed_price
        assert r1.slippage_applied == r2.slippage_applied
        assert r1.commission_applied == r2.commission_applied
        assert p1.cash == p2.cash


class TestExecutionEngineEdgeCases:
    def test_assessment_id_preserved(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         assessment_id="ASSESS-042")
        assert r.assessment_id == "ASSESS-042"

    def test_risk_action_preserved_in_result(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        r = eng.evaluate(p, "XAU/USD", 2000.0, "2026-01-01T00:00:00",
                         position_size=10.0, decision_type=DECISION_STRONG_POSITIVE,
                         risk_action="proceed", assessment_id="A001")
        assert r.risk_action == "proceed"

    def test_sell_from_short_not_allowed(self) -> None:
        eng = ExecutionEngine()
        p = VirtualPortfolio(100_000.0)
        p.short("XAU/USD", 10.0, 2000.0, "2026-01-01T00:00:00")
        r = eng.evaluate(p, "XAU/USD", 1900.0, "2026-01-01T01:00:00",
                         position_size=5.0, decision_type=DECISION_NEGATIVE,
                         assessment_id="A001")
        assert r.decision == ExecutionDecision.EXECUTE
        assert r.trade is not None
        assert r.trade.action == "SHORT"
