import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

import importlib.util
spec = importlib.util.spec_from_file_location("mt5_utc_provider", str(Path(__file__).resolve().parent.parent / "src/trade_alert/mt5_utc_provider.py"))
provider_mod = importlib.util.module_from_spec(spec)
sys.modules["mt5_utc_provider"] = provider_mod
spec.loader.exec_module(provider_mod)
MT5UTCProvider = provider_mod.MT5UTCProvider


@pytest.fixture
def mock_data_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    # Create valid M15 and H1 CSVs
    end_time = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    start_time = end_time - timedelta(days=365)
    
    m15_dates = pd.date_range(start_time, end_time, freq="15min")[:-1]
    m15_df = pd.DataFrame({
        "bar_open_utc": [d.isoformat() for d in m15_dates],
        "bar_close_utc": [(d + timedelta(minutes=15)).isoformat() for d in m15_dates],
        "open": 2000.0, "high": 2005.0, "low": 1995.0, "close": 2002.0,
        "tick_volume": 100, "real_volume": 50, "spread_points": 10
    })
    m15_path = data_dir / "XAUUSD_M15_utc.csv"
    m15_df.to_csv(m15_path, index=False)
    
    h1_dates = pd.date_range(start_time, end_time, freq="1h")[:-1]
    h1_df = pd.DataFrame({
        "bar_open_utc": [d.isoformat() for d in h1_dates],
        "bar_close_utc": [(d + timedelta(hours=1)).isoformat() for d in h1_dates],
        "open": 2000.0, "high": 2005.0, "low": 1995.0, "close": 2002.0,
        "tick_volume": 400, "real_volume": 200, "spread_points": 10
    })
    h1_path = data_dir / "XAUUSD_H1_utc.csv"
    h1_df.to_csv(h1_path, index=False)
    
    return data_dir

def test_provider_initialization(mock_data_dir):
    provider = MT5UTCProvider(mock_data_dir)
    assert "M15" in provider.frames
    assert "H1" in provider.frames
    
    # Check that volume and spread columns were renamed
    m15 = provider.frames["M15"]
    assert "volume" in m15.columns
    assert "spread" in m15.columns
    assert "tick_volume" not in m15.columns

def test_provider_completed(mock_data_dir):
    provider = MT5UTCProvider(mock_data_dir)
    
    as_of = datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc)
    m15 = provider.completed("M15", as_of)
    
    # Assert no future data
    assert m15.index.max().to_pydatetime() <= as_of
    
def test_provider_no_lookahead(mock_data_dir):
    provider = MT5UTCProvider(mock_data_dir)
    
    as_of = datetime(2026, 9, 30, 10, 10, tzinfo=timezone.utc)
    m15 = provider.completed("M15", as_of)
    
    # The last completed M15 candle before 10:10 should be 10:00 (which opened at 09:45)
    assert m15.index.max().to_pydatetime() == datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc)
