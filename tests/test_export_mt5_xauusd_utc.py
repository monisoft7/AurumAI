import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import zoneinfo

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
        mock.terminal_info.return_value = MagicMock()
        mock.TIMEFRAME_M15 = 15
        mock.TIMEFRAME_H1 = 60
        
        # 1790799521 is 2026-09-30 20:18:41 in broker time
        mock.copy_rates_range.return_value = (
            {
                'time': 1790799521,
                'open': 1000.0,
                'high': 1005.0,
                'low': 995.0,
                'close': 1002.0,
                'tick_volume': 100,
                'spread': 5
            },
        )
        yield mock


def test_export_mt5_creates_files(mock_mt5, tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog", "--out-dir", str(tmp_path), "--months", "1"])
    
    assert main() == 0
    
    assert (tmp_path / "XAUUSD_M15_utc.csv").exists()
    assert (tmp_path / "XAUUSD_H1_utc.csv").exists()
    assert (tmp_path / "XAUUSD_manifest.json").exists()
    
    # Check that UTC conversion worked
    content = (tmp_path / "XAUUSD_M15_utc.csv").read_text()
    
    # 1790799521 POSIX is 2026-09-30 20:18:41. If we assume broker is Europe/Bucharest (UTC+3), 
    # true UTC is 2026-09-30 17:18:41.
    assert "2026-09-30T17:18:41+00:00" in content
