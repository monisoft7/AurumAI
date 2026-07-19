from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from execution.commission import CommissionModel, CommissionResult
from execution.models import PortfolioSnapshot, VirtualPosition, VirtualTrade
from execution.portfolio import VirtualPortfolio
from execution.slippage import SlippageModel, SlippageResult

DECISION_STRONG_POSITIVE = "STRONG_POSITIVE"
DECISION_POSITIVE = "POSITIVE"
DECISION_NEUTRAL = "NEUTRAL"
DECISION_NEGATIVE = "NEGATIVE"
DECISION_STRONG_NEGATIVE = "STRONG_NEGATIVE"
DECISION_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

_EXECUTABLE_TYPES = frozenset({
    DECISION_STRONG_POSITIVE,
    DECISION_POSITIVE,
    DECISION_NEGATIVE,
    DECISION_STRONG_NEGATIVE,
})

_HOLD_TYPES = frozenset({
    DECISION_NEUTRAL,
    DECISION_INSUFFICIENT_EVIDENCE,
})

_REJECT_RISK_ACTIONS = frozenset({"halt", "delay"})


class ExecutionDecision(Enum):
    EXECUTE = "execute"
    REJECT = "reject"
    HOLD = "hold"


@dataclass(frozen=True)
class ExecutionResult:
    decision: ExecutionDecision
    reason: str
    assessment_id: str
    trade: VirtualTrade | None = None
    snapshot: PortfolioSnapshot | None = None
    decision_type: str | None = None
    risk_action: str | None = None
    slippage_applied: float = 0.0
    commission_applied: float = 0.0
    executed_price: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "decision": self.decision.value,
            "reason": self.reason,
            "assessment_id": self.assessment_id,
            "decision_type": self.decision_type,
            "risk_action": self.risk_action,
            "slippage_applied": self.slippage_applied,
            "commission_applied": self.commission_applied,
            "executed_price": self.executed_price,
        }
        if self.trade is not None:
            d["trade"] = self.trade.to_dict()
        if self.snapshot is not None:
            d["snapshot"] = self.snapshot.to_dict()
        return d


class ExecutionEngine:
    def evaluate(
        self,
        portfolio: VirtualPortfolio,
        asset_id: str,
        price: float,
        timestamp: str,
        position_size: float = 0.0,
        decision_type: str | None = None,
        risk_action: str | None = "proceed",
        assessment_id: str = "",
        *,
        slippage_model: SlippageModel | None = None,
        commission_model: CommissionModel | None = None,
    ) -> ExecutionResult:
        if decision_type is None or decision_type not in _EXECUTABLE_TYPES | _HOLD_TYPES:
            return ExecutionResult(
                decision=ExecutionDecision.REJECT,
                reason=f"Unknown or missing decision_type: {decision_type!r}",
                assessment_id=assessment_id,
                decision_type=decision_type,
                risk_action=risk_action,
            )

        if risk_action in _REJECT_RISK_ACTIONS:
            return ExecutionResult(
                decision=ExecutionDecision.REJECT,
                reason=f"Risk gate rejected: action={risk_action!r}",
                assessment_id=assessment_id,
                decision_type=decision_type,
                risk_action=risk_action,
            )

        if decision_type in _HOLD_TYPES:
            return ExecutionResult(
                decision=ExecutionDecision.HOLD,
                reason=f"Decision type {decision_type!r} requires no action",
                assessment_id=assessment_id,
                decision_type=decision_type,
                risk_action=risk_action,
            )

        if position_size <= 0.0:
            return ExecutionResult(
                decision=ExecutionDecision.HOLD,
                reason="Position size is zero or negative",
                assessment_id=assessment_id,
                decision_type=decision_type,
                risk_action=risk_action,
            )

        pos = self._find_position(portfolio, asset_id)

        slip_result = self._apply_slippage(slippage_model, price, position_size, decision_type, pos)
        exec_price = slip_result.executed_price
        slip_amount = slip_result.slippage_amount

        comm_result = self._apply_commission(commission_model, exec_price, position_size)
        comm_amount = comm_result.commission

        if decision_type in (DECISION_STRONG_POSITIVE, DECISION_POSITIVE):
            cash_needed = position_size * exec_price + comm_amount
            if cash_needed > portfolio.cash:
                return ExecutionResult(
                    decision=ExecutionDecision.REJECT,
                    reason=f"Insufficient cash: need {cash_needed:.2f}, have {portfolio.cash:.2f}",
                    assessment_id=assessment_id,
                    decision_type=decision_type,
                    risk_action=risk_action,
                    slippage_applied=slip_amount,
                    commission_applied=comm_amount,
                )
            orig_cash = portfolio.cash
            trade = portfolio.buy(asset_id, position_size, exec_price, timestamp)
            if comm_amount > 0.0:
                portfolio._cash -= comm_amount
            return self._success(
                ExecutionDecision.EXECUTE,
                f"Executed BUY {position_size} @ {exec_price:.4f}",
                assessment_id,
                trade,
                portfolio,
                timestamp,
                decision_type,
                risk_action,
                slip_amount,
                comm_amount,
                exec_price,
            )

        if decision_type in (DECISION_STRONG_NEGATIVE, DECISION_NEGATIVE):
            return self._execute_sell_or_short(
                portfolio, asset_id, price, timestamp, position_size,
                decision_type, risk_action, assessment_id,
                slip_result, comm_result, exec_price,
            )

        return ExecutionResult(
            decision=ExecutionDecision.REJECT,
            reason=f"Unhandled decision type: {decision_type!r}",
            assessment_id=assessment_id,
            decision_type=decision_type,
            risk_action=risk_action,
        )

    # -- helpers -------------------------------------------------------------

    def _execute_sell_or_short(
        self,
        portfolio: VirtualPortfolio,
        asset_id: str,
        price: float,
        timestamp: str,
        position_size: float,
        decision_type: str,
        risk_action: str | None,
        assessment_id: str,
        slip_result: SlippageResult,
        comm_result: CommissionResult,
        exec_price: float,
    ) -> ExecutionResult:
        pos = self._find_position(portfolio, asset_id)
        is_strong = decision_type == DECISION_STRONG_NEGATIVE

        if pos is not None and pos.quantity > 0:
            qty = min(position_size, pos.quantity) if is_strong else position_size
            if qty > pos.quantity:
                return ExecutionResult(
                    decision=ExecutionDecision.REJECT,
                    reason=f"Cannot sell {qty} units: only {pos.quantity} held long",
                    assessment_id=assessment_id,
                    decision_type=decision_type,
                    risk_action=risk_action,
                    slippage_applied=slip_result.slippage_amount,
                    commission_applied=comm_result.commission,
                )
            trade = portfolio.sell(asset_id, qty, exec_price, timestamp)
            if comm_result.commission > 0.0:
                portfolio._cash -= comm_result.commission
            action_label = "SELL" if qty == position_size else f"SELL {qty}"
            return self._success(
                ExecutionDecision.EXECUTE,
                f"Executed {action_label} {qty} @ {exec_price:.4f}",
                assessment_id,
                trade,
                portfolio,
                timestamp,
                decision_type,
                risk_action,
                slip_result.slippage_amount,
                comm_result.commission,
                exec_price,
            )

        trade = portfolio.short(asset_id, position_size, exec_price, timestamp)
        if comm_result.commission > 0.0:
            portfolio._cash -= comm_result.commission
        return self._success(
            ExecutionDecision.EXECUTE,
            f"Executed SHORT {position_size} @ {exec_price:.4f}",
            assessment_id,
            trade,
            portfolio,
            timestamp,
            decision_type,
            risk_action,
            slip_result.slippage_amount,
            comm_result.commission,
            exec_price,
        )

    def _find_position(
        self,
        portfolio: VirtualPortfolio,
        asset_id: str,
    ) -> VirtualPosition | None:
        for p in portfolio.positions:
            if p.asset_id == asset_id:
                return p
        return None

    def _apply_slippage(
        self,
        model: SlippageModel | None,
        price: float,
        position_size: float,
        decision_type: str,
        pos: VirtualPosition | None,
    ) -> SlippageResult:
        if model is None:
            return SlippageResult(executed_price=price, slippage_amount=0.0, slippage_bps=0.0)
        if decision_type in (DECISION_STRONG_POSITIVE, DECISION_POSITIVE):
            return model.apply(price, position_size)
        if pos is not None and pos.quantity > 0:
            return model.apply(price, -position_size)
        return model.apply(price, -position_size)

    def _apply_commission(
        self,
        model: CommissionModel | None,
        price: float,
        position_size: float,
    ) -> CommissionResult:
        if model is None:
            return CommissionResult(commission=0.0, commission_per_unit=0.0)
        return model.apply(price, position_size)

    def _success(
        self,
        decision: ExecutionDecision,
        reason: str,
        assessment_id: str,
        trade: VirtualTrade,
        portfolio: VirtualPortfolio,
        timestamp: str,
        decision_type: str | None,
        risk_action: str | None,
        slippage_applied: float,
        commission_applied: float,
        executed_price: float,
    ) -> ExecutionResult:
        snapshot = PortfolioSnapshot(
            timestamp=timestamp,
            cash=portfolio.cash,
            equity=portfolio.equity,
            unrealized_pnl=portfolio.unrealized_pnl,
            realized_pnl=portfolio.realized_pnl,
            positions=portfolio.positions,
        )
        return ExecutionResult(
            decision=decision,
            reason=reason,
            assessment_id=assessment_id,
            trade=trade,
            snapshot=snapshot,
            decision_type=decision_type,
            risk_action=risk_action,
            slippage_applied=slippage_applied,
            commission_applied=commission_applied,
            executed_price=executed_price,
        )
