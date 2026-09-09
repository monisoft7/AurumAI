from __future__ import annotations

import datetime as dt
import subprocess
import urllib.request
from pathlib import Path

import pandas as pd
import pytest

import run as runtime
from connectors.fred_client import FredClient
from paper_trading.ledger import build_paper_evaluation


SERIES_ID = "CPIAUCSL"
NOW = dt.datetime(2026, 9, 9, 8, 10, tzinfo=dt.timezone.utc)


class _FredStub:
    def __init__(self, series: pd.Series) -> None:
        self.series = series

    def get_series(self, *args, **kwargs) -> pd.Series:
        return self.series


class _CpiClient:
    def __init__(
        self,
        *,
        live: pd.Series | Exception,
        cached: pd.Series | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.live = live
        self.cached = cached
        self.metadata = metadata

    def get_series(self, series_id: str, **kwargs) -> pd.Series:
        assert series_id == SERIES_ID
        assert kwargs == {"use_cache": False}
        if isinstance(self.live, Exception):
            raise self.live
        return self.live

    def read_cached_series(self, series_id: str) -> pd.Series | None:
        assert series_id == SERIES_ID
        return self.cached

    def cache_metadata(self, series_id: str) -> dict[str, object] | None:
        assert series_id == SERIES_ID
        return self.metadata


def _series(latest: str = "2026-07-01") -> pd.Series:
    return pd.Series(
        [330.0, 332.8],
        index=pd.to_datetime(["2026-06-01", latest]),
        dtype=float,
    )


def _calendar(tmp_path: Path, *, next_release: str = "2026-09-11") -> Path:
    path = tmp_path / "cpi_releases.csv"
    path.write_text(
        "reference_period,release_date,release_time,timezone,release_timestamp\n"
        "2026-07-01,2026-08-12,08:30,US/Eastern,2026-08-12 08:30:00\n"
        f"2026-08-01,{next_release},08:30,US/Eastern,{next_release} 08:30:00\n",
        encoding="utf-8",
    )
    return path


def _config(tmp_path: Path, *, next_release: str = "2026-09-11") -> dict[str, str]:
    return {
        "data_path": str(tmp_path / "CPIAUCSL.csv"),
        "release_calendar_path": str(_calendar(tmp_path, next_release=next_release)),
    }


def _trusted_metadata(retrieved_at: str) -> dict[str, object]:
    return {
        "series_id": SERIES_ID,
        "source": "FRED",
        "retrieval_status": "live",
        "retrieved_at_utc": retrieved_at,
        "latest_observation_date": "2026-07-01",
        "cache_status": "refreshed",
    }


def test_live_fred_persists_cpi_retrieval_provenance(tmp_path: Path) -> None:
    client = FredClient(api_key="test", cache_dir=tmp_path)
    client._fred = _FredStub(_series())
    client.get_series(SERIES_ID, use_cache=False)
    metadata = client.cache_metadata(SERIES_ID)
    assert metadata is not None
    assert metadata["series_id"] == SERIES_ID
    assert metadata["source"] == "FRED"
    assert metadata["retrieval_status"] == "live"
    assert metadata["latest_observation_date"] == "2026-07-01"
    assert str(metadata["retrieved_at_utc"]).endswith("+00:00")


def test_live_old_monthly_observation_is_latest_available_not_stale(
    tmp_path: Path,
) -> None:
    record = runtime._refresh_cpi_before_run(
        _config(tmp_path), client=_CpiClient(live=_series()), now_utc=NOW
    )
    assert record["status"] == "fresh"
    assert record["latest_observation_date"] == "2026-07-01"
    assert record["retrieval_status"] == "live"
    assert record["threshold"]["contract"] == "release_calendar"


@pytest.mark.parametrize(
    "next_release,expected",
    [("2026-09-11", "fresh"), ("2026-09-01", "stale")],
)
def test_trusted_fallback_uses_release_calendar_threshold(
    tmp_path: Path, next_release: str, expected: str
) -> None:
    client = _CpiClient(
        live=RuntimeError("offline"), cached=_series(),
        metadata=_trusted_metadata("2026-08-13T13:00:00+00:00"),
    )
    record = runtime._refresh_cpi_before_run(
        _config(tmp_path, next_release=next_release), client=client, now_utc=NOW
    )
    assert record["status"] == expected
    assert record["retrieval_status"] == "fallback"
    assert record["cache_status"] == "trusted"


def test_fallback_without_retrieval_timestamp_is_unknown(tmp_path: Path) -> None:
    metadata = _trusted_metadata("")
    client = _CpiClient(
        live=RuntimeError("offline"), cached=_series(), metadata=metadata
    )
    record = runtime._refresh_cpi_before_run(
        _config(tmp_path), client=client, now_utc=NOW
    )
    assert record["status"] == "unknown"
    assert record["cache_status"] == "untrusted"
    assert "timestamp" in record["freshness_reason"]


def test_runtime_cpi_metadata_is_consumed_by_harness_and_keeps_reliability(
    tmp_path: Path,
) -> None:
    cpi = runtime._refresh_cpi_before_run(
        _config(tmp_path), client=_CpiClient(live=_series()), now_utc=NOW
    )
    explicit = {
        "status": "fresh",
        "observation_date": "2026-09-09",
        "retrieved_at": NOW.isoformat(),
        "max_age_days": 7,
    }
    outputs = {
        "confidence_engine": {
            "primary_thesis_id": "selected",
            "theses_confidence": [
                {"thesis_id": "selected", "reliability_category": "low"}
            ],
        },
        "decision_engine": {"selected_thesis_id": "selected"},
        "finalize": {
            "source_freshness": {
                **{
                    source: dict(explicit)
                    for source in (
                        "DGS10", "DFII10", "T5YIE", "Gold", "DXY", "outcome_price"
                    )
                },
                "CPI": cpi,
            }
        },
    }
    evaluation = build_paper_evaluation(outputs, {}, {})
    assert evaluation["source_freshness"]["CPI"]["status"] == "fresh"
    assert evaluation["reliability_category"] == "low"
    assert evaluation["financially_eligible"] is True


def test_cpi_provenance_path_is_hermetic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("network and git are forbidden")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    record = runtime._refresh_cpi_before_run(
        _config(tmp_path), client=_CpiClient(live=_series()), now_utc=NOW
    )
    assert record["status"] == "fresh"
    assert not (Path("data") / "outputs" / "runtime").exists()
