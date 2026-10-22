"""The optional spot feed cannot silently blend with the futures history."""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

from connectors.gold_data_provider import (
    fetch_twelvedata_spot_history,
    refresh_gold_data,
)


def test_spot_fetch_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TWELVE_DATA_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TWELVE_DATA_API_KEY is missing"):
        fetch_twelvedata_spot_history()


def test_spot_fetch_validates_instrument_and_daily_ohlc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "test-secret")
    payload = {
        "status": "ok", "meta": {"symbol": "XAU/USD"},
        "values": [{
            "datetime": "2025-01-02", "open": "2650", "high": "2675",
            "low": "2640", "close": "2660",
        }],
    }

    def response(request: object, timeout: int) -> io.BytesIO:
        assert "symbol=XAU%2FUSD" in request.full_url
        assert "test-secret" in request.full_url
        assert timeout == 25
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr("urllib.request.urlopen", response)
    frame = fetch_twelvedata_spot_history()
    assert frame.loc[0, "Date"] == "2025-01-02"
    assert frame.loc[0, "Close"] == "2660"
    payload["meta"]["symbol"] = "GC=F"
    with pytest.raises(RuntimeError, match="did not match"):
        fetch_twelvedata_spot_history()


def test_spot_bootstrap_is_separate_from_futures_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    futures_path = tmp_path / "gold.csv"
    futures_path.write_text("Date,Close,High,Low,Open,Volume\n2025-01-02,2700,2701,2699,2700,10\n")
    before = futures_path.read_bytes()
    monkeypatch.setattr(
        "connectors.gold_data_provider.fetch_twelvedata_spot_history",
        lambda: pd.DataFrame([{
            "Date": "2025-01-02", "Open": 2650, "High": 2675,
            "Low": 2640, "Close": 2660,
        }]),
    )
    spot_path = tmp_path / "xauusd_spot.csv"
    result = refresh_gold_data(spot_path, provider="twelvedata_spot")
    assert result.status == "ok"
    assert result.source == "twelvedata:XAU/USD"
    assert pd.read_csv(spot_path).loc[0, "Close"] == 2660
    assert futures_path.read_bytes() == before


def test_spot_provider_rejects_futures_history_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="dedicated xauusd_spot.csv"):
        refresh_gold_data(tmp_path / "gold.csv", provider="twelvedata_spot")


def test_date_only_end_boundary_does_not_drop_previous_completed_bar(monkeypatch):
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "test-secret")

    def response(request, timeout):
        params = parse_qs(urlparse(request.full_url).query)
        # Reproduce the observed provider behavior: a midnight end boundary
        # returns Oct 20; the end-of-day boundary returns the completed Oct 21.
        boundary = params["end_date"][0]
        last = "2026-10-21" if boundary == "2026-10-21 23:59:59" else "2026-10-20"
        return io.BytesIO(json.dumps({"meta": {"symbol": "XAU/USD"}, "values": [{
            "datetime": last, "open": "4100", "high": "4120", "low": "4090", "close": "4110",
        }]}).encode())

    monkeypatch.setattr("urllib.request.urlopen", response)
    frame = fetch_twelvedata_spot_history(now=datetime(2026, 10, 22, 13, tzinfo=timezone.utc))
    assert frame.loc[0, "Date"] == "2026-10-21"


def test_unfinished_bar_is_rejected(monkeypatch):
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "test-secret")
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: io.BytesIO(json.dumps({
        "meta": {"symbol": "XAU/USD"}, "values": [{"datetime": "2026-10-22", "close": "4100"}],
    }).encode()))
    with pytest.raises(RuntimeError, match="unfinished"):
        fetch_twelvedata_spot_history(now=datetime(2026, 10, 22, 13, tzinfo=timezone.utc))
