"""The optional spot feed cannot silently blend with the futures history."""

from __future__ import annotations

import io
import json
from pathlib import Path

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
