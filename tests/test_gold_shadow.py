"""Regression cases for paper execution, chronology, replay and concurrent retries."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pytest

from gold_shadow.journal import fresh_plan, record
from gold_shadow.market import Bar, STEP, UTC
from gold_shadow.strategy import Plan, decide, evaluate


T = datetime(2026, 11, 23, 9, tzinfo=UTC)
BUY = Plan("BUY LIMIT", "trend", "half ATR pullback", 100, 99, 101.5)


def bar(i, op=101, high=101.2, low=100.6, close=101):
    return Bar(T + i*STEP, op, high, low, close)


def test_ambiguous_path_stop_and_entry_candle_target():
    result = evaluate(BUY, T, [bar(0, 101, 103, 98, 102)])
    assert result["status"] == "stop" and result["net_r"] < -1
    # An intrabar high preceding a limit touch is not a provable target.
    partial = evaluate(BUY, T, [bar(0, 101, 103, 99.6, 100)])
    assert partial["filled"] and partial["status"] == "pending"


def test_expired_censored_and_partial_bar():
    assert evaluate(BUY, T, [bar(i) for i in range(4)])["status"] == "expired_unfilled"
    assert evaluate(BUY, T, [bar(1)])["status"] == "unobserved_gap"
    assert evaluate(BUY, T + timedelta(seconds=1), [bar(0, 101, 102, 96, 99)])["filled"] is False
    assert evaluate(BUY, T, [])["net_r"] is None


@pytest.mark.parametrize("action,entry", [("BUY LIMIT", 99), ("BUY STOP", 101), ("BUY NOW", 100),
                                         ("SELL LIMIT", 101), ("SELL STOP", 99), ("SELL NOW", 100)])
def test_sides_and_quote_age(action, entry):
    p = Plan(action, "trend", "test", entry, entry-1 if action.startswith("BUY") else entry+1,
             entry+1.5 if action.startswith("BUY") else entry-1.5)
    assert fresh_plan(p, (100, T), T) == p
    assert fresh_plan(p, (100, T), T + timedelta(seconds=91)).action == "WAIT"
    assert fresh_plan(p, (100, T + STEP), T).action == "WAIT"
    assert evaluate(p, T, [bar(0, 100, 103, 97, 100)])["filled"]


def test_crossed_limit_rejected_and_future_bar_excluded():
    assert fresh_plan(BUY, (99.5, T), T).action == "WAIT"
    bars = [bar(i) for i in range(-16, 1)]
    assert decide(bars, T).action == "WAIT"
    with pytest.raises(ValueError):
        bar(0, high=float("nan"))


def test_overlapping_probes_are_idempotent_and_keep_old_separate(tmp_path):
    path = tmp_path / "journal.db"
    bars = [Bar(T+i*STEP, 130+i, 131+i, 129+i, 130.8+i) for i in range(-33, 0)]
    old = {"run": "baseline1", "execution": {"action": "WAIT"}}
    def save(_):
        return record(path, T, bars, (130.5, T), old)
    with ThreadPoolExecutor(2) as pool:
        a, b = list(pool.map(save, range(2)))
    assert a == b and a["plan"]["action"] == "BUY LIMIT"
    assert a["public_action"] == "WAIT"
    with sqlite3.connect(path) as db:
        assert db.execute("select count(*) from legacy").fetchone()[0] == 1
        assert db.execute("select count(*) from decisions").fetchone()[0] == 1
    record(path, T+STEP, [Bar(T, 130, 132, 124, 129)], (129, T+STEP))
    with sqlite3.connect(path) as db:
        result = json.loads(db.execute("select payload from outcomes where slot=?", (T.isoformat(),)).fetchone()[0])
    assert result["filled"] and result["status"] == "stop"
