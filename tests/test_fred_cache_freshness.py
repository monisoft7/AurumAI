"""Focused tests for FRED cache freshness behavior (Targeted Correction 003).

Covers: fresh-cache fast path (no network), stale-cache refresh, refresh
failure fallback with explicit staleness marking, legacy cache-only behavior,
and OvernightDataFetcher freshness propagation.
"""

from __future__ import annotations

import pandas as pd
import pytest

from connectors.fred_client import FredClient
from pre_market.overnight_fetcher import OvernightDataFetcher


class _FredStub:
    def __init__(self, series: pd.Series, error: Exception | None = None):
        self._series = series
        self._error = error
        self.calls: list[tuple[str, dict]] = []

    def get_series(self, series_id: str, **kwargs):
        self.calls.append((series_id, kwargs))
        if self._error is not None:
            raise self._error
        return self._series


def _series(dates: list[str], values: list[float]) -> pd.Series:
    return pd.Series(values, index=pd.to_datetime(dates), dtype=float)


def _client(tmp_path, fred_stub) -> FredClient:
    client = FredClient(api_key="test", cache_dir=str(tmp_path))
    client._fred = fred_stub
    return client


def _write_cache(tmp_path, series_id: str, series: pd.Series) -> None:
    df = pd.DataFrame({"Date": series.index, "Value": series.values})
    df.to_csv(tmp_path / f"{series_id}.csv", index=False)


def _days_ago(days: int) -> str:
    return (pd.Timestamp.now().normalize() - pd.Timedelta(days=days)).date().isoformat()


_FRED_INSTRUMENTS = {"US10Y Real Yield", "US10Y Nominal Yield", "Breakeven Inflation"}


def _fred_changes(changes) -> list:
    return [c for c in changes if c.instrument in _FRED_INSTRUMENTS]


def test_fresh_cache_uses_cache_without_network(tmp_path) -> None:
    dates = [_days_ago(5), _days_ago(4)]
    cached = _series(dates, [2.40, 2.42])
    _write_cache(tmp_path, "DFII10", cached)
    stub = _FredStub(_series([_days_ago(1)], [2.50]))
    client = _client(tmp_path, stub)

    result = client.get_series("DFII10", use_cache=True, max_age_days=7)

    assert list(result) == list(cached)
    assert stub.calls == []
    report = client.freshness_report()["DFII10"]
    assert report["status"] == "fresh"


def test_stale_cache_refreshes_and_persists(tmp_path) -> None:
    _write_cache(tmp_path, "DGS10", _series([_days_ago(30), _days_ago(29)], [4.50, 4.52]))
    fresh = _series([_days_ago(30), _days_ago(29), _days_ago(1)], [4.50, 4.52, 4.60])
    client = _client(tmp_path, _FredStub(fresh))

    result = client.get_series("DGS10", use_cache=True, max_age_days=7)

    assert result.iloc[-1] == 4.60
    assert len(client._fred.calls) == 1
    report = client.freshness_report()["DGS10"]
    assert report["status"] == "refreshed"
    assert report["refreshed_last_date"] == _days_ago(1)
    persisted = pd.read_csv(tmp_path / "DGS10.csv", parse_dates=["Date"])
    assert persisted["Value"].iloc[-1] == 4.60


def test_stale_cache_refresh_failure_falls_back_and_marks_stale(tmp_path) -> None:
    cached = _series([_days_ago(30), _days_ago(29)], [2.18, 2.16])
    _write_cache(tmp_path, "T5YIE", cached)
    client = _client(tmp_path, _FredStub(pd.Series(dtype=float), error=RuntimeError("network down")))

    result = client.get_series("T5YIE", use_cache=True, max_age_days=7)

    assert list(result) == list(cached)
    report = client.freshness_report()["T5YIE"]
    assert report["status"] == "fallback_stale"
    assert report["error"] == "network down"
    persisted = pd.read_csv(tmp_path / "T5YIE.csv", parse_dates=["Date"])
    assert len(persisted) == 2


def test_max_age_none_keeps_legacy_cache_only_behavior(tmp_path) -> None:
    cached = _series([_days_ago(60), _days_ago(59)], [2.0, 2.1])
    _write_cache(tmp_path, "DFII10", cached)
    client = _client(tmp_path, _FredStub(_series([_days_ago(1)], [9.9])))

    result = client.get_series("DFII10", use_cache=True)

    assert list(result) == list(cached)
    assert client._fred.calls == []
    assert client.freshness_report() == {}


def test_cache_miss_fetches_and_persists(tmp_path) -> None:
    fresh = _series([_days_ago(2), _days_ago(1)], [2.3, 2.4])
    client = _client(tmp_path, _FredStub(fresh))

    result = client.get_series("DFII10", use_cache=True, max_age_days=7)

    assert list(result) == list(fresh)
    assert len(client._fred.calls) == 1
    assert (tmp_path / "DFII10.csv").exists()


def test_overnight_fetcher_passes_max_age_and_reports_freshness(tmp_path) -> None:
    series = _series([_days_ago(2), _days_ago(1)], [2.4, 2.42])
    _write_cache(tmp_path, "DFII10", series)
    _write_cache(tmp_path, "DGS10", series)
    _write_cache(tmp_path, "T5YIE", series)
    client = _client(tmp_path, _FredStub(series))
    fetcher = OvernightDataFetcher(fred_client=client, max_age_days=7)

    result = fetcher.fetch_all(session="APAC")

    assert "overnight_changes" in result
    assert "yield_freshness" in result
    for series_id in ("DFII10", "DGS10", "T5YIE"):
        assert result["yield_freshness"][series_id]["status"] == "fresh"
    assert client._fred.calls == []


def test_overnight_fetcher_explicit_none_keeps_legacy_cache_only(tmp_path) -> None:
    cached = _series([_days_ago(60), _days_ago(59)], [2.4, 2.42])
    for series_id in ("DFII10", "DGS10", "T5YIE"):
        _write_cache(tmp_path, series_id, cached)
    client = _client(tmp_path, _FredStub(_series([_days_ago(1)], [9.9])))
    fetcher = OvernightDataFetcher(fred_client=client, max_age_days=None)

    changes = fetcher.fetch_overnight_changes(session="APAC")

    assert client._fred.calls == []
    assert client.freshness_report() == {}
    fred_changes = _fred_changes(changes)
    assert len(fred_changes) == 3
    assert fred_changes[0].instrument == "US10Y Real Yield"
    assert fred_changes[0].current_price == pytest.approx(2.42)


def test_overnight_fetcher_default_enforces_freshness_policy(tmp_path) -> None:
    cached = _series([_days_ago(30), _days_ago(29)], [2.4, 2.42])
    for series_id in ("DFII10", "DGS10", "T5YIE"):
        _write_cache(tmp_path, series_id, cached)
    fresh = _series([_days_ago(30), _days_ago(29), _days_ago(1)], [2.4, 2.42, 2.5])
    client = _client(tmp_path, _FredStub(fresh))
    fetcher = OvernightDataFetcher(fred_client=client)

    result = fetcher.fetch_all(session="APAC")

    assert len(client._fred.calls) == 3
    for series_id in ("DFII10", "DGS10", "T5YIE"):
        record = result["yield_freshness"][series_id]
        assert record["status"] == "refreshed"
        assert record["refreshed_last_date"] == _days_ago(1)


def test_overnight_fetcher_default_falls_back_on_refresh_failure(tmp_path) -> None:
    cached = _series([_days_ago(30), _days_ago(29)], [2.4, 2.42])
    for series_id in ("DFII10", "DGS10", "T5YIE"):
        _write_cache(tmp_path, series_id, cached)
    client = _client(tmp_path, _FredStub(pd.Series(dtype=float), error=RuntimeError("network down")))
    fetcher = OvernightDataFetcher(fred_client=client)

    result = fetcher.fetch_all(session="APAC")

    assert len(client._fred.calls) == 3
    for series_id in ("DFII10", "DGS10", "T5YIE"):
        record = result["yield_freshness"][series_id]
        assert record["status"] == "fallback_stale"
        assert record["error"] == "network down"
    fred_changes = _fred_changes(result["overnight_changes"])
    assert len(fred_changes) == 3
    assert fred_changes[0].instrument == "US10Y Real Yield"
    assert fred_changes[0].current_price == pytest.approx(2.42)
