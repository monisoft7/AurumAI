"""Bounded evaluation and leakage checks for Phase 3."""

import sqlite3

import numpy as np
import pandas as pd
import pytest

from research.gold_lab import predictive as p
from research.gold_lab import predictive_data as data
from research.gold_lab import predictive_knowledge as memory
from research.gold_lab import researcher


def minute_frame(start, days=5):
    idx = pd.date_range(start, periods=days * 1440, freq="min", tz="UTC")
    trend = (
        100 + np.arange(len(idx)) * 0.0002 + np.sin(np.arange(len(idx)) * 0.13) * 0.02
    )
    return pd.DataFrame(
        {"open": trend, "high": trend + 0.005, "low": trend - 0.005, "close": trend},
        index=idx,
    )


def test_reject_sealed_and_nonregistered_archives():
    with pytest.raises(ValueError):
        data.archive("XAUUSD", 2025)
    with pytest.raises(ValueError):
        data.archive("OTHER", 2024)


def test_exact_features_do_not_change_when_future_quotes_are_replaced(monkeypatch):
    frame = minute_frame("2024-02-12")
    now = pd.Timestamp("2024-02-13 14:00", tz="UTC")
    gold = frame.copy()
    fx = frame.copy()
    monkeypatch.setattr(p, "YEARS", (2024,))
    monkeypatch.setattr(p, "load", lambda name, *args: gold if name == "XAUUSD" else fx)
    mf = {"assets": {"XAUUSD": {}, "EURUSD": {}}}
    x, y, _, _ = p.panel(mf)
    assert (
        x.loc[now, "post_cpi"] == 1
        and x.loc[now - pd.Timedelta(minutes=30), "post_cpi"] == 0
    )
    fx.loc[fx.index >= now - pd.Timedelta(minutes=15)] *= 2
    gold.loc[gold.index >= now] *= 0.80
    x2, y2, _, _ = p.panel(mf)
    pd.testing.assert_series_equal(x2.loc[now], x.loc[now])
    assert y2.loc[now, "absolute_return_bps"] != y.loc[now, "absolute_return_bps"]
    assert (
        x2.loc[now + pd.Timedelta(minutes=15), "EURUSD_1"]
        != x.loc[now + pd.Timedelta(minutes=15), "EURUSD_1"]
    )


def test_first_touch_tie_neither_and_missing_minute():
    frame = minute_frame("2024-06-03", 1)
    i = frame.index[:1]
    frame.loc[:, ["high", "low"]] = [100.0, 100.0]

    def test(d):
        return p.first_touch(d, i, np.array([100.0]), np.array([10.0])).iloc[0]

    assert test(frame) == 0
    frame.loc[i, "high"] = 101
    assert test(frame) == 1
    frame.loc[i, "low"] = 99
    assert np.isnan(test(frame))
    assert np.isnan(test(frame.drop(frame.index[20])))


def test_nonoverlap_cost_and_delay():
    f = minute_frame("2024-06-03", 1)
    f["open"] = 100.0
    s = pd.Series([0.7, 0.7, 0.52], index=f.index[[90, 105, 180]])
    r = p.economic(s, f, 1, 1)
    assert (r["opportunities"], r["trades"], r["overlap"]) == (3, 1, 1)
    assert r["net_usd_per_oz"] == pytest.approx(-0.7)
    assert p.economic(s, f, 5, 2)["net_usd_per_oz"] == pytest.approx(-1.4)


def test_probabilities_and_reproducible_uncertainty():
    x = np.arange(100.0).reshape(-1, 1)
    prob = p.fit_predict(x, (x[:, 0] > 45).astype(float), x, 0.01, True)
    assert np.all((prob > 0) & (prob < 1)) and prob[5] < prob[80]
    assert p.bounds(np.ones(60))["lower_corrected"] == pytest.approx(1)
    assert p.bounds(np.arange(45)) == p.bounds(np.arange(45))


def test_benchmarks_use_only_training_targets():
    train = pd.DataFrame(
        {"r1": [1, -1, 1, -1]},
        index=pd.date_range("2024-01-02", periods=4, freq="h", tz="UTC"),
    )
    labels = pd.Series([1, 0, 1, 0], index=train.index)
    refs = p.refs(train, labels, train, "up_15")
    assert np.array_equal(refs["conditional"], [1, 0, 1, 0])
    assert np.all(refs["fair_coin"] == 0.5)


def test_knowledge_is_idempotent_queryable_and_keeps_language_unverified():
    db = sqlite3.connect(":memory:")
    g = memory.build(db)
    n = db.execute("SELECT count(*) FROM predictive_knowledge").fetchone()[0]
    memory.build(db)
    assert db.execute("SELECT count(*) FROM predictive_knowledge").fetchone()[0] == n
    assert len(memory.retrieve(g, ["direction", "gold", "cross"])) == 5
    assert all(
        row["type"] == "descriptive_result" for row in memory.retrieve(g, ["risk"])
    )
    assert all(
        row["type"] == "unverified_interpretation"
        for row in memory.retrieve(g, ["language"])
    )
    assert memory.retrieve(g, ["gold", "not_a_condition"]) == []


def test_rubric_rejects_malformed_or_duplicate_grounding():
    c = researcher.CASES[0]
    correct = {
        "decision": c[4],
        "evidence": c[5],
        "reason": "Two independent engines agree.",
    }
    assert researcher.grade(correct, c) == 3
    with pytest.raises(ValueError):
        researcher.grade({**correct, "evidence": [c[5][0]] * 2}, c)
    with pytest.raises(ValueError):
        researcher.grade({**correct, "stage": "APPROVED"}, c)


def test_selected_reader_note_is_grounded_and_cached(monkeypatch):
    import json
    from types import SimpleNamespace

    db = sqlite3.connect(":memory:")
    calls = []
    monkeypatch.setenv("GROQ_API_KEY", "test")
    note = dict(
        interpretation="Development result.",
        alternative_explanation="Moving scale.",
        falsification="Prospective frozen test.",
        required_data="Independent quotes.",
    )

    def fake(url, headers, json, timeout):
        calls.append(json)
        assert "tools" not in json
        payload = {
            "choices": [{"message": {"content": __import__("json").dumps(note)}}]
        }
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)

    first = researcher.review(db, "large_move", fake)
    assert first["type"] == "unverified_interpretation"
    assert first == researcher.review(db, "large_move", fake)
    assert len(calls) == 1
    evidence = json.loads(calls[0]["messages"][1]["content"])
    assert evidence["period"] == "2024 development only" and set(
        evidence["models"]
    ) == {"gold", "cross", "event"}
