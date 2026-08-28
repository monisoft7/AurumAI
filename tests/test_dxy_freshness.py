"""Focused tests for DXY cache freshness (DXY Freshness Trace 001 correction).

Covers the same freshness contract as FRED yields: fresh-cache fast path
(no network), stale-cache refresh, refresh failure fallback with explicit
staleness marking, legacy cache-only behavior, cache-miss fetch, and the
runtime DXY pre-run refresh wiring.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from connectors.dxy_fetcher import DXYFetcher


def _series(dates: list[str], values: list[float]) -> pd.Series:
    return pd.Series(values, index=pd.to_datetime(dates), dtype=float)


def _write_cache(tmp_path, series: pd.Series) -> None:
    df = pd.DataFrame({"Date": series.index, "Value": series.values})
    df.to_csv(tmp_path / "dxy.csv", index=False)


def _days_ago(days: int) -> str:
    return (pd.Timestamp.now().normalize() - pd.Timedelta(days=days)).date().isoformat()


def _mock_download(series: pd.Series):
    df = pd.DataFrame({"Close": series.values}, index=series.index)
    return patch("connectors.dxy_fetcher.yf.download", return_value=df)


class TestGetSeriesFreshness:
    def test_fresh_cache_uses_cache_without_network(self, tmp_path: Path) -> None:
        cached = _series([_days_ago(5), _days_ago(4)], [99.0, 99.2])
        _write_cache(tmp_path, cached)
        fetcher = DXYFetcher(cache_dir=str(tmp_path))

        with _mock_download(_series([_days_ago(1)], [99.5])) as download:
            result = fetcher.get_series(use_cache=True, max_age_days=7)

        assert list(result) == list(cached)
        assert not download.called
        assert fetcher.freshness_report()["dxy"]["status"] == "fresh"

    def test_stale_cache_refreshes_and_persists(self, tmp_path: Path) -> None:
        _write_cache(tmp_path, _series([_days_ago(30), _days_ago(29)], [98.0, 98.2]))
        fetcher = DXYFetcher(cache_dir=str(tmp_path))
        fresh = _series([_days_ago(30), _days_ago(29), _days_ago(1)], [98.0, 98.2, 99.4])

        with _mock_download(fresh):
            result = fetcher.get_series(use_cache=True, max_age_days=7)

        assert result.iloc[-1] == 99.4
        assert fetcher.freshness_report()["dxy"]["status"] == "refreshed"
        assert fetcher.freshness_report()["dxy"]["refreshed_last_date"] == _days_ago(1)
        persisted = pd.read_csv(tmp_path / "dxy.csv", parse_dates=["Date"])
        assert persisted["Value"].iloc[-1] == 99.4

    def test_stale_cache_refresh_failure_falls_back_and_marks_stale(
        self, tmp_path: Path
    ) -> None:
        cached = _series([_days_ago(30), _days_ago(29)], [98.0, 98.2])
        _write_cache(tmp_path, cached)
        fetcher = DXYFetcher(cache_dir=str(tmp_path))

        empty = pd.Series(dtype="float64")
        with _mock_download(empty):
            result = fetcher.get_series(use_cache=True, max_age_days=7)

        assert list(result) == list(cached)
        assert fetcher.freshness_report()["dxy"]["status"] == "fallback_stale"
        assert "no DX-Y.NYB data" in fetcher.freshness_report()["dxy"]["error"]
        persisted = pd.read_csv(tmp_path / "dxy.csv", parse_dates=["Date"])
        assert len(persisted) == 2

    def test_stale_cache_refresh_failure_on_exception_marks_stale(
        self, tmp_path: Path
    ) -> None:
        cached = _series([_days_ago(30), _days_ago(29)], [98.0, 98.2])
        _write_cache(tmp_path, cached)
        fetcher = DXYFetcher(cache_dir=str(tmp_path))

        with patch(
            "connectors.dxy_fetcher.yf.download", side_effect=OSError("network down")
        ):
            result = fetcher.get_series(use_cache=True, max_age_days=7)

        assert list(result) == list(cached)
        record = fetcher.freshness_report()["dxy"]
        assert record["status"] == "fallback_stale"
        assert record["error"] == "network down"

    def test_max_age_none_keeps_legacy_cache_only_behavior(self, tmp_path: Path) -> None:
        cached = _series([_days_ago(60), _days_ago(59)], [98.0, 98.2])
        _write_cache(tmp_path, cached)
        fetcher = DXYFetcher(cache_dir=str(tmp_path))

        with _mock_download(_series([_days_ago(1)], [99.5])) as download:
            result = fetcher.get_series(use_cache=True)

        assert list(result) == list(cached)
        assert not download.called
        assert fetcher.freshness_report() == {}

    def test_cache_miss_fetches_and_persists(self, tmp_path: Path) -> None:
        fetcher = DXYFetcher(cache_dir=str(tmp_path))
        fresh = _series([_days_ago(2), _days_ago(1)], [98.0, 99.0])

        with _mock_download(fresh):
            result = fetcher.get_series(use_cache=True, max_age_days=7)

        assert list(result) == list(fresh)
        assert (tmp_path / "dxy.csv").exists()
        assert fetcher.freshness_report() == {}

    def test_cache_miss_fetch_failure_returns_empty(self, tmp_path: Path) -> None:
        fetcher = DXYFetcher(cache_dir=str(tmp_path))

        empty = pd.Series(dtype="float64")
        with _mock_download(empty):
            result = fetcher.get_series(use_cache=True, max_age_days=7)

        assert isinstance(result, pd.Series)
        assert len(result) == 0

    def test_default_cache_path_is_committed_dxy_dataset(self) -> None:
        fetcher = DXYFetcher()
        assert fetcher._cache_path == Path("data/context/dxy/dxy.csv")


class TestRunRefreshWiring:
    def test_refresh_dxy_before_run_reports_freshness(self) -> None:
        import importlib.util
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[0] / ".."))
        spec = importlib.util.spec_from_file_location(
            "runtime_refresh_dxy", Path(__file__).resolve().parents[1] / "run.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        assert hasattr(module, "_refresh_dxy_before_run")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))