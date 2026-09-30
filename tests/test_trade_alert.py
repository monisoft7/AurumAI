from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from trade_alert.engine import Alert, evaluate
from trade_alert.shadow import ShadowOutcome, evaluate_exit, metrics, pass_gate
from trade_alert.engine import format_alert, macro_is_fresh
from paper_trading.ledger import _first_gate, REQUIRED_PAPER_SOURCES


NOW = datetime(2026, 1, 5, 12, tzinfo=timezone.utc)


class Provider:
    def __init__(self, timestamp):
        self.frame = pd.DataFrame(
            {"open": [2000.0], "high": [2001.0], "low": [1999.0],
             "close": [2000.0], "volume": [10]},
            index=pd.DatetimeIndex([timestamp]),
        )

    def completed(self, timeframe, as_of):
        assert timeframe in {"M15", "H1"}
        return self.frame


class ForbiddenTechnical:
    def compute(self, frame):
        raise AssertionError("technical engine must not see unverified candles")


def test_future_candle_rejected_before_technical_engine():
    with pytest.raises(ValueError, match="lookahead"):
        evaluate(Provider(NOW + timedelta(minutes=15)), ForbiddenTechnical(), NOW,
                 macro_fresh=True)


def test_macro_filter_emits_no_output_without_reading_candles():
    assert evaluate(Provider(NOW), ForbiddenTechnical(), NOW, macro_fresh=False) is None


def test_alert_contract_rejects_misaligned_levels_and_passed_entry():
    fields = dict(action="TRADE_ALERT BUY", setup="trend_pullback",
                  entry_low=1999.0, entry_high=2001.0, current_price=2000.0,
                  sl=1990.0, tp1=2015.0, tp2=2020.0, tp3=2030.0,
                  rr1=1.5, rr2=2.0, rr3=3.0, directional_conviction=.8,
                  execution_quality=.8, strongest_counterargument="trend reversal",
                  invalidation="close below 1990", valid_until=NOW,
                  reason="measured setup")
    assert "TP3:" in format_alert(Alert(**fields))
    with pytest.raises(ValueError, match="price has passed entry"):
        Alert(**(fields | {"current_price": 2002.0}))
    with pytest.raises(ValueError, match="incorrect R:R"):
        Alert(**(fields | {"rr1": 2.0}))


def test_shadow_metrics_and_pass_gate_require_sufficient_oos():
    outcome = ShadowOutcome("a", NOW, NOW + timedelta(minutes=15),
                            2000, 1990, 2015, 2020, 2030, 2015, "TP1",
                            .1, .1, .1, 2, 15, .2, .25)
    assert metrics([outcome])["expectancy"] == .2
    assert pass_gate([outcome], independent_periods=1, market_regimes=1) == "NO_GO"


def test_canonical_freshness_and_real_confidence_gate():
    snapshot = {"source_freshness": {name: {"status": "fresh"}
                                     for name in REQUIRED_PAPER_SOURCES}}
    assert macro_is_fresh(snapshot)
    snapshot["source_freshness"][REQUIRED_PAPER_SOURCES[0]]["status"] = "stale"
    assert not macro_is_fresh(snapshot)
    outcome = {"decision_snapshot": {"gate_reasons": {"bias_review_blocked": False}}}
    finalize = {"decision": {"metadata": {"gate_reason": "confidence_below_threshold"}}}
    assert _first_gate(outcome, finalize)["gate"] == "confidence_below_threshold"
    assert _first_gate(outcome, {}) is None


def test_paper_exit_uses_next_open_and_stop_first():
    alert = Alert("TRADE_ALERT BUY", "confirmed_breakout", 1999, 2001,
                  2000, 1990, 2015, 2020, 2030, 1.5, 2, 3, .8, .8,
                  "reversal", "below 1990", NOW + timedelta(minutes=15),
                  "measured")
    future = pd.DataFrame({"open": [2000.0], "high": [2016.0],
                           "low": [1989.0], "close": [2005.0]},
                          index=pd.DatetimeIndex([NOW + timedelta(minutes=15)]))
    result = evaluate_exit(alert, future, spread=.1, slippage=.1, alert_id="test")
    assert result.exit_reason == "SL"
    assert result.net_pnl == pytest.approx(-.064375)  # % equity: -1.03R * .25% * 25%
    with_commission = evaluate_exit(alert, future, spread=.1, slippage=.1,
                                    commission_per_lot_per_side=5, alert_id="commission")
    assert with_commission.transaction_costs == pytest.approx(.4)  # USD/oz round trip
    assert with_commission.net_pnl == pytest.approx(-.065)


def test_shadow_units_and_percentage_drawdown():
    first = ShadowOutcome("loss", NOW, NOW + timedelta(minutes=15),
                          2000, 1990, 2015, 2020, 2030, 1990, "SL",
                          .1, .1, .3, 10, 0, -.25, .25)
    report = metrics([first])
    assert report["expectancy"] == -.25  # percent of equity, not USD or fraction
    assert report["max_drawdown"] == pytest.approx(.25)  # percent of peak equity
    with pytest.raises(ValueError, match="risk cap"):
        ShadowOutcome(**(first.__dict__ | {"risk_budget_pct": .51}))
