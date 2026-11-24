"""Regression checks for the research archive and the isolated forward paper monitor."""

import json
from types import SimpleNamespace
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from research.gold_lab import data, lab, shadow
from research.gold_lab.feed import broker_utc
from research.gold_lab.schedule import definition
from research.gold_lab.strategies import Plan, completed, simulate
from research.gold_lab.ticks import settle


SLOT = pd.Timestamp("2026-11-24T08:15:00Z")
PLAN = Plan("BUY NOW", "trend", "test", 100.0, 99.0, 101.5)


class Quotes:
    def __init__(self, frozen=False):
        self.frozen = frozen

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def quote(self):
        if self.frozen:
            raise ValueError("no advancing market quote")
        return {"at": SLOT.isoformat(), "bid": 99.98, "ask": 100.02}

    def minutes(self, slot):
        return slot

    def ticks(self, start, end):
        return (
            np.array([start, start + 1000]),
            np.array([99.98, 101.5]),
            np.array([100.02, 101.7]),
        )


def connect(path):
    db = lab.database(path)
    shadow.schema(db)
    return db


def test_market_calendar_quarantine_and_completeness():
    clock = pd.date_range("2024-01-05T10:00Z", periods=30, freq="min")
    clock = clock.append(
        pd.DatetimeIndex([clock[0], pd.Timestamp("2024-01-06T12:00Z")])
    )
    frame = pd.DataFrame(
        {name: 1900.0 for name in ("open", "high", "low", "close")}, index=clock
    )
    valid, audit = data.clean(frame)
    assert (audit["ambiguous_rows"], audit["excluded_closed"], audit["kept"]) == (
        2,
        1,
        29,
    )
    assert completed(valid, 15).index.tolist() == [clock[29] + pd.Timedelta(minutes=1)]
    with pytest.raises(ValueError, match="no usable"):
        data.clean(frame.tail(1))


def test_tampering_with_local_sidecar_does_not_unlock_mismatched_data(tmp_path):
    archive = tmp_path / "histdata-M1-2023.zip"
    archive.write_bytes(b"different version")
    archive.with_suffix(".json").write_text(
        json.dumps({"sha256": data.digest(archive)})
    )
    with pytest.raises(ValueError, match="fingerprint"):
        data.acquire(2023, root=tmp_path)


def test_broker_dst_fold_and_standard_offset():
    zone = ZoneInfo("Europe/Helsinki")
    encoded = pd.Timestamp("2026-11-24T10:20Z").value // 1_000_000
    assert broker_utc(encoded, zone) == pd.Timestamp("2026-11-24T08:20Z")
    autumn = pd.Timestamp("2026-10-25T03:30Z").value // 1_000_000
    with pytest.raises(ValueError, match="ambiguous"):
        broker_utc(autumn, zone)


@pytest.mark.parametrize(
    "action,bids,asks,expected",
    [
        ("BUY NOW", [99.9, 101.5], [100.2, 101.9], 1.2),
        ("SELL NOW", [100.0, 98.3], [100.2, 98.5], 1.4),
    ],
)
def test_executable_side_and_adverse_slippage(action, bids, asks, expected):
    side = 1 if action.startswith("BUY") else -1
    plan = Plan(action, "test", "", 100.0, 100.0 - side, 100.0 + 1.5 * side)
    result = settle(np.array([0, 1000]), np.array(bids), np.array(asks), 0, plan, 2000)
    assert result["status"] == "target"
    assert result["net_r"] == pytest.approx(expected)
    assert result["fill_ms"] == 0


def test_gap_before_exit_censors_returns():
    result = settle(
        np.array([0, 301000]),
        np.array([100, 102]),
        np.array([100.2, 102.2]),
        0,
        PLAN,
        302000,
    )
    assert result["status"] == "unobserved" and result["net_r"] is None


def test_orders_do_not_cross_fold_or_overlap():
    a = pd.Timestamp("2024-01-01T00:00Z")
    b = a + pd.Timedelta(days=8)
    times = [
        a,
        a + pd.Timedelta(days=1),
        a + pd.Timedelta(days=1, minutes=15),
        b - pd.Timedelta(hours=20),
    ]
    market = SimpleNamespace(outcome=lambda *args: ("target", 1.0, 60, True))
    result = simulate(market, [(t, PLAN) for t in times], "london_asia", a, b)
    assert [r[0] for r in result] == [times[1]]


def test_rejections_rehydrate_generate_references_and_seal_stays_closed(tmp_path):
    db = connect(tmp_path / "memory.sqlite")
    protocol = json.loads(data.PROTOCOL.read_bytes())
    queue = lab.discovery_queue(db, protocol)
    assert len(queue["next_round"]) == len(protocol["hypotheses"]) == 4
    assert all(
        r["state"] and r["related"] and r["evidence"] and r["required_data"]
        for r in queue["next_round"]
    )
    for (payload,) in db.execute("SELECT payload FROM experiments"):
        row = json.loads(payload)
        assert (
            row["final"] is None
            and row["stage"] == "RESEARCH"
            and row["validation"]["reasons"]
        )
    assert db.execute("SELECT count(*) FROM seals").fetchone()[0] == 0
    assert lab.lower_bound(np.zeros(30)) == 0.0
    db.close()


@pytest.mark.parametrize(
    "stamp,expected",
    [
        ("2026-11-23 06:45", False),
        ("2026-11-23 07:00", True),
        ("2026-11-23 21:00", True),
        ("2026-11-23 21:15", False),
        ("2026-11-28 10:00", False),
    ],
)
def test_tripoli_slots(stamp, expected):
    assert shadow.in_window(pd.Timestamp(stamp, tz="UTC")) is expected


def test_disabled_weekday_scheduler(tmp_path):
    tree = ElementTree.fromstring(definition(tmp_path / "python.exe", tmp_path))
    assert tree.findtext(".//{*}Enabled") == "false"
    assert tree.findtext(".//{*}Interval") == "PT15M"
    assert len(tree.find(".//{*}DaysOfWeek")) == 5
    assert tree.findtext(".//{*}RunLevel") == "LeastPrivilege"


def test_restarts_reconcile_once_and_retain_failures(tmp_path, monkeypatch):
    path = tmp_path / "research.sqlite"
    db = connect(path)
    experiment = {"stage": "SHADOW", "family": "london_asia", "id": "synthetic"}
    with db:
        db.execute(
            "INSERT INTO experiments VALUES (?,?,?)",
            ("synthetic", "london_asia", json.dumps(experiment)),
        )
    monkeypatch.setattr(
        shadow,
        "Market",
        lambda slot: SimpleNamespace(signals=lambda family: [(SLOT, PLAN)]),
    )
    first = shadow.observation(db, SLOT, Quotes(frozen=True), clock=lambda: SLOT)
    assert first["errors"] and first["orders"] == 0
    assert shadow.observation(db, SLOT, Quotes(), clock=lambda: SLOT)["orders"] == 1
    db.close()

    db = connect(path)
    assert (
        shadow.observation(db, SLOT, Quotes(frozen=True), clock=lambda: SLOT)["orders"]
        == 1
    )
    later = SLOT + pd.Timedelta(minutes=30)
    shadow.observation(db, later, Quotes(), clock=lambda: later)
    summary = shadow.report(db, SLOT.date())
    assert summary["probes"] == 2 and summary["paper_orders"] == summary["closed"] == 1
    assert summary["by_strategy"]["london_asia"]["net_r"] == pytest.approx(1.38)
    assert summary["missed_slots_since_previous"] == 1
    assert summary["data_issues"] == {"no advancing market quote": 1}
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    db.close()


def test_research_telegram_refuses_shared_destination(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "same")
    monkeypatch.setenv("AURUM_RESEARCH_CHAT_ID", "same")
    monkeypatch.setenv("AURUM_RESEARCH_BOT_TOKEN", "test-token")
    monkeypatch.setattr(
        shadow.requests, "post", lambda *a, **k: pytest.fail("unexpected outbound call")
    )
    with pytest.raises(ValueError, match="distinct"):
        shadow.send_report("test")


def test_archive_restores_consumed_seal_and_refuses_conflict(tmp_path, monkeypatch):
    archived = tmp_path / "export.json"
    archived.write_text(
        json.dumps({"experiments": [], "events": [], "seals": [["2025", "locked"]]})
    )
    monkeypatch.setattr(lab, "PUBLIC", archived)
    path = tmp_path / "test.sqlite"
    db = lab.database(path)
    assert db.execute("SELECT * FROM seals").fetchall() == [("2025", "locked")]
    db.close()
    archived.write_text(json.dumps({"experiments": [], "seals": [["2025", "other"]]}))
    with pytest.raises(ValueError, match="conflicts"):
        lab.database(path)


def test_late_invocation_never_creates_order(tmp_path):
    db = connect(tmp_path / "late.sqlite")
    with db:
        record = {"id": "demo", "stage": "SHADOW", "family": "london_asia"}
        db.execute(
            "INSERT INTO experiments VALUES(?,?,?)",
            ("demo", record["family"], json.dumps(record)),
        )
    late = SLOT + pd.Timedelta(seconds=91)
    result = shadow.observation(db, SLOT, Quotes(), clock=lambda: late)
    assert result["orders"] == 0 and any("late" in s for s in result["rejections"])
    db.close()


def test_frozen_feed_and_holiday_rejects_quote(monkeypatch):
    from research.gold_lab import feed

    adapter = feed.Feed("UTC")
    point = SimpleNamespace(time_msc=10, bid=100.0, ask=100.2)
    adapter.mt = SimpleNamespace(symbol_info_tick=lambda symbol: point)
    monkeypatch.setattr(feed.time, "sleep", lambda seconds: None)
    with pytest.raises(ValueError, match="no advancing"):
        adapter.quote()


def test_all_validation_rejections_skip_final_evaluator(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, "PUBLIC", tmp_path / "empty_archive")
    protocol = json.loads(data.PROTOCOL.read_bytes())
    mocked = json.loads((data.PROTOCOL.parent / "results.json").read_bytes())[
        "experiments"
    ]
    called = []

    def replay(year, specs, limits, root, development=False):
        called.append(year)
        assert year in (2023, 2024)
        return {
            r["family"]: r["development" if development else "validation"]
            for r in mocked
        }, {}

    monkeypatch.setattr(lab, "evaluate_year", replay)
    monkeypatch.setattr(
        lab,
        "digest",
        lambda path: data.pinned_hash(path.stem[-4:])
        if path.suffix == ".zip"
        else data.digest(path),
    )
    db = lab.database(tmp_path / "memory.sqlite")
    lab.remember(db, protocol, tmp_path)
    assert called == [2023, 2024]
    assert lab.remember(db, protocol, tmp_path) == "existing results reused"
    assert called == [2023, 2024]
    assert db.execute("SELECT count(*) FROM seals").fetchone() == (0,)
    db.close()
