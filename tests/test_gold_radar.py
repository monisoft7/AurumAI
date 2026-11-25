"""Regression tests for risk issuance, maturity, cohort isolation and reporting."""

import json
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd
import pytest

from research.gold_lab import radar, radar_metrics, radar_schedule
from research.gold_lab.radar_model import load_frozen


SLOT = pd.Timestamp("2026-11-25T07:00:00Z")


def minutes():
    idx = pd.date_range(
        SLOT - pd.Timedelta(hours=5), SLOT + pd.Timedelta(hours=2), freq="min"
    )
    base = 3500 + np.arange(len(idx)) * 0.015 + np.sin(np.arange(len(idx)) / 20)
    return pd.DataFrame(
        {"open": base, "high": base + 0.3, "low": base - 0.3, "close": base + 0.1},
        index=idx,
    )


class Source:
    def __init__(self, frame, now, quote_age=0):
        self.frame, self.now, self.age = frame, now, quote_age
        self.calls = 0

    def __enter__(self):
        self.calls += 1
        return self

    def __exit__(self, *args):
        pass

    def quote(self):
        return {
            "at": (self.now - pd.Timedelta(seconds=self.age)).isoformat(),
            "bid": 3500.0,
            "ask": 3500.2,
        }

    def minutes(self, closed):
        return self.frame.loc[self.frame.index < closed]


def test_live_window_dedupe_and_settlement_after_reopen(tmp_path):
    model, h = load_frozen()
    path = tmp_path / "risk.sqlite"
    db = radar.open_ledger(path)
    t = SLOT + pd.Timedelta(seconds=10)
    src = Source(minutes(), t)
    assert (
        radar.run_once(db, src, model, h, "smoke", clock=lambda: t)["status"]
        == "issued"
    )
    row = db.execute("SELECT * FROM radar_forecasts").fetchone()
    assert row["outcome"] is None and pd.Timestamp(row["issued_at"]) == t
    assert radar.run_once(db, src, model, h, "smoke", clock=lambda: t) is None
    assert src.calls == 1
    db.close()
    db = radar.open_ledger(path)
    now = SLOT + pd.Timedelta(hours=1, seconds=5)
    radar.run_once(
        db,
        Source(minutes(), now),
        model,
        h,
        "smoke",
        issue_new=False,
        clock=lambda: now,
    )
    assert db.execute("SELECT outcome FROM radar_forecasts").fetchone()[0] is None
    now += pd.Timedelta(seconds=10)
    radar.run_once(
        db,
        Source(minutes(), now),
        model,
        h,
        "smoke",
        issue_new=False,
        clock=lambda: now,
    )
    settled = db.execute("SELECT * FROM radar_forecasts").fetchone()
    assert settled["outcome"] in (0, 1)
    assert (
        settled["end_price"] == minutes().loc[SLOT + pd.Timedelta(minutes=59), "close"]
    )
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    with pytest.raises(ValueError, match="differs"):
        radar.run_once(db, src, model, "changed", "smoke", clock=lambda: now)
    report = radar_metrics.daily_report(db, "smoke", "2026-11-25", now, model)
    assert report["daily"]["issued"] == report["daily"]["settled"] == 1
    assert (
        report["statistical_indication"] is None and not report["evaluation_complete"]
    )
    db.close()


@pytest.mark.parametrize(
    "case,reason", [("stale", "expired"), ("gap", "window"), ("late", "90 seconds")]
)
def test_unsafe_forecasts_record_reason(tmp_path, case, reason):
    model, h = load_frozen()
    db = radar.open_ledger(tmp_path / "risk.sqlite")
    t = SLOT + pd.Timedelta(seconds=95 if case == "late" else 6)
    frame = minutes()
    if case == "gap":
        frame = frame.drop(SLOT - pd.Timedelta(minutes=30))
    radar.run_once(
        db,
        Source(frame, t, 110 if case == "stale" else 0),
        model,
        h,
        "pilot",
        clock=lambda: t,
    )
    assert db.execute("SELECT count(*) FROM radar_forecasts").fetchone()[0] == 0
    assert reason in db.execute("SELECT reason FROM radar_slots").fetchone()[0]
    db.close()


def test_endpoint_requires_exact_path():
    f = minutes()
    assert radar.outcome(f, SLOT, 3500, 0.1)[0] == 1
    with pytest.raises(ValueError, match="1/60"):
        radar.outcome(f.drop(SLOT + pd.Timedelta(minutes=12)), SLOT, 3500, 0.1)


def test_explicit_reserved_window_and_schedule():
    inside = pd.Timestamp("2027-02-01T07:00Z")
    assert radar.allowed_cohort("reserved", inside) and not radar.allowed_cohort(
        "pilot", inside
    )
    assert not radar.allowed_cohort("reserved", SLOT)
    assert not radar.known_open(pd.Timestamp("2026-11-28T11:00Z"))
    xml = ET.fromstring(radar_schedule.artifact("python.exe"))
    assert xml.findtext(".//{*}Enabled") == "false"
    assert xml.findtext(".//{*}Duration") == "PT15H16M"
    assert "--send-research-telegram" not in xml.findtext(".//{*}Arguments")


def test_telegram_dedupes_after_ambiguous_delivery(monkeypatch, tmp_path):
    model, h = load_frozen()
    db = radar.open_ledger(tmp_path / "risk.sqlite")
    calls = []

    def send(message):
        calls.append(message)
        raise RuntimeError("ambiguous response")

    monkeypatch.setattr(radar_metrics, "send_report", send)
    for t in (SLOT, SLOT + radar.QUARTER):
        radar.run_once(db, Source(minutes(), t), model, h, "pilot", clock=lambda: t)
        with db:
            db.execute("UPDATE radar_forecasts SET candidate=1")
        radar_metrics.deliver(db, "pilot", t.isoformat(), t)
    assert (
        len(calls) == 1 and "الاتجاه غير مؤكد" in calls[0] and "غير معاير" in calls[0]
    )
    assert (
        db.execute("SELECT result FROM radar_delivery").fetchone()[0]
        == "failed or unconfirmed"
    )
    db.close()


def test_brier_and_event_metrics():
    predictions = dict(
        model=0.8,
        seasonal=0.4,
        previous_volatility=0.4,
        threshold_distance=0.4,
        threshold_and_hour=0.4,
    )
    rows = [
        {
            "outcome": 1,
            "candidate": 1,
            "resolved_at": "yes",
            "slot": SLOT.isoformat(),
            "predictions": json.dumps(predictions),
        }
    ]
    m = radar_metrics.summarize(rows)
    assert m["brier"]["model"] == pytest.approx(0.04)
    assert m["brier_skill"]["seasonal"] == pytest.approx(1 - 0.04 / 0.36)
    assert m["precision"] == m["recall"] == 1
    assert m["false_alarm_rate"] is None
