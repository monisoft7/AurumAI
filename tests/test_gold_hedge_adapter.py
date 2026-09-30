from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from trade_alert.gold_hedge_adapter import ClockEvidence, GoldHedgeProvider, aggregate_complete, read_m5


def _raw(count=12):
    stamps = pd.date_range("2026-01-05 12:00", periods=count, freq="5min")
    return pd.DataFrame({"timestamp": stamps.strftime("%Y-%m-%d %H:%M:%S"),
                         "open": range(2000, 2000 + count),
                         "high": range(2001, 2001 + count),
                         "low": range(1999, 1999 + count),
                         "close": range(2000, 2000 + count),
                         "volume": [2] * count, "spread_points": [5] * count})


def test_clock_evidence_is_mandatory_before_read(monkeypatch):
    monkeypatch.setattr(pd, "read_csv", lambda path: (_ for _ in ()).throw(AssertionError("read forbidden")))
    with pytest.raises(ValueError, match="DATA_REQUIRED"):
        read_m5("unused.csv", None)
    with pytest.raises(ValueError, match="DATA_REQUIRED"):
        ClockEvidence("UTC", "open", "")


def test_open_time_to_utc_and_spread_once(monkeypatch):
    monkeypatch.setattr(pd, "read_csv", lambda path: _raw(3))
    m5 = read_m5("unused.csv", ClockEvidence("UTC", "open", "source clock log"))
    assert m5.index[0] == pd.Timestamp("2026-01-05 12:05:00+00:00")
    assert m5.spread.tolist() == [.05] * 3
    m15 = aggregate_complete(m5, "M15")
    assert len(m15) == 1
    assert m15.index[0] == pd.Timestamp("2026-01-05 12:15:00+00:00")
    assert m15.iloc[0][["open", "high", "low", "close", "volume", "spread"]].tolist() == [2000, 2003, 1999, 2002, 6, .05]


def test_missing_m5_drops_entire_group_no_fill(monkeypatch):
    raw = _raw(12).drop(index=1).reset_index(drop=True)
    monkeypatch.setattr(pd, "read_csv", lambda path: raw)
    m5 = read_m5("unused.csv", ClockEvidence("UTC", "open", "source clock log"))
    assert len(aggregate_complete(m5, "M15")) == 3
    assert len(aggregate_complete(m5, "H1")) == 0


def test_ambiguous_dst_rejected(monkeypatch):
    raw = _raw(1)
    raw.loc[0, "timestamp"] = "2025-10-26 03:30:00"
    monkeypatch.setattr(pd, "read_csv", lambda path: raw)
    with pytest.raises(ValueError, match="ambiguous DST"):
        read_m5("unused.csv", ClockEvidence("Europe/Helsinki", "open", "verified export"))


def test_provider_never_reveals_future_aggregate(monkeypatch):
    monkeypatch.setattr(pd, "read_csv", lambda path: _raw(12))
    provider = GoldHedgeProvider("unused.csv", ClockEvidence("UTC", "open", "verified export"))
    before = provider.completed("M15", datetime(2026, 1, 5, 12, 14, tzinfo=timezone.utc))
    after = provider.completed("M15", datetime(2026, 1, 5, 12, 15, tzinfo=timezone.utc))
    assert before.empty and len(after) == 1
