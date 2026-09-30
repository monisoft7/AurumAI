import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock mt5 before importing the script so it doesn't fail if MT5 is not available in CI
sys.modules['MetaTrader5'] = MagicMock()

import importlib.util
spec = importlib.util.spec_from_file_location("export_mt5_xauusd_utc", str(Path(__file__).resolve().parent.parent / "scripts/export_mt5_xauusd_utc.py"))
export_mt5 = importlib.util.module_from_spec(spec)
sys.modules["export_mt5_xauusd_utc"] = export_mt5
spec.loader.exec_module(export_mt5)
main = export_mt5.main


@pytest.fixture
def mock_mt5():
    with patch("export_mt5_xauusd_utc.mt5") as mock:
        mock.initialize.return_value = True
        mock.account_info.return_value = MagicMock(company="TestBroker", server="TestServer")
        mock.terminal_info.return_value = MagicMock(build=4000)
        mock.symbol_info.return_value = MagicMock(digits=2, point=0.01)
        mock.__version__ = "5.0.0"
        mock.TIMEFRAME_M15 = 15
        mock.TIMEFRAME_H1 = 60

        # 1790799521 is 2026-09-30T20:18:41+00:00
        mock.copy_rates_range.return_value = (
            {
                'time': 1790799521,
                'open': 1000.0,
                'high': 1005.0,
                'low': 995.0,
                'close': 1002.0,
                'tick_volume': 100,
                'real_volume': 50,
                'spread': 5
            },
        )
        yield mock


def test_export_mt5_creates_files(mock_mt5, tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog", "--out-dir", str(tmp_path), "--months", "1"])

    # We mock datetime.now to be far enough in the future so the candle is complete
    with patch("export_mt5_xauusd_utc.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 10, 1, tzinfo=timezone.utc)
        mock_datetime.fromtimestamp = datetime.fromtimestamp

        assert main() == 0

    assert (tmp_path / "XAUUSD_M15_utc.csv").exists()
    assert (tmp_path / "XAUUSD_H1_utc.csv").exists()
    assert (tmp_path / "XAUUSD_manifest.json").exists()

    content = (tmp_path / "XAUUSD_M15_utc.csv").read_text()

    # 1790799521 remains 2026-09-30T20:18:41+00:00
    assert "2026-09-30T20:18:41+00:00" in content

def test_export_excludes_incomplete_candle(mock_mt5, tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog", "--out-dir", str(tmp_path), "--months", "1"])

    # Mock datetime.now to be exactly at the open time of the candle + 1 minute (so it's incomplete)
    # Candle open: 2026-09-30 20:18:41
    # Candle close for M15: 2026-09-30 20:33:41
    # now: 2026-09-30 20:20:00 -> Candle incomplete!
    with patch("export_mt5_xauusd_utc.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 9, 30, 20, 20, 0, tzinfo=timezone.utc)
        mock_datetime.fromtimestamp = datetime.fromtimestamp

        assert main() == 0

    # If it's excluded and it was the only candle, files shouldn't exist or should not contain data.
    # The script deletes the file if row_count == 0
    assert not (tmp_path / "XAUUSD_M15_utc.csv").exists()
