import json
import sys
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
from datetime import datetime, timezone, timedelta

import importlib.util
spec = importlib.util.spec_from_file_location("validate_trade_alert_data", str(Path(__file__).resolve().parent.parent / "scripts/validate_trade_alert_data.py"))
validator = importlib.util.module_from_spec(spec)
sys.modules["validate_trade_alert_data"] = validator
spec.loader.exec_module(validator)


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
    
    import hashlib
    with open(m15_path, "rb") as f: m15_hash = hashlib.sha256(f.read()).hexdigest()
    with open(h1_path, "rb") as f: h1_hash = hashlib.sha256(f.read()).hexdigest()
    
    manifest = {
        "export_created_at_utc": (end_time + timedelta(hours=1)).isoformat(),
        "files": {
            "XAUUSD_M15_utc.csv": {
                "sha256": m15_hash,
                "row_count": len(m15_df),
                "first_bar_open_utc": m15_df["bar_open_utc"].iloc[0],
                "last_bar_close_utc": m15_df["bar_close_utc"].iloc[-1]
            },
            "XAUUSD_H1_utc.csv": {
                "sha256": h1_hash,
                "row_count": len(h1_df),
                "first_bar_open_utc": h1_df["bar_open_utc"].iloc[0],
                "last_bar_close_utc": h1_df["bar_close_utc"].iloc[-1]
            }
        }
    }
    
    with open(data_dir / "XAUUSD_manifest.json", "w") as f:
        json.dump(manifest, f)
        
    return data_dir

def test_validator_success(mock_data_dir, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog", "--data-dir", str(mock_data_dir)])
    assert validator.main() == 0
    out, _ = capsys.readouterr()
    assert "DATA_VALIDATED: READY_FOR_WALK_FORWARD" in out

def test_validator_missing_manifest(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog", "--data-dir", str(tmp_path)])
    assert validator.main() == 1
    out, _ = capsys.readouterr()
    assert "DATA_REQUIRED: manifest missing" in out

def test_validator_missing_timeframe(mock_data_dir, capsys, monkeypatch):
    manifest_path = mock_data_dir / "XAUUSD_manifest.json"
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
    del manifest["files"]["XAUUSD_H1_utc.csv"]
    with open(manifest_path, "w") as f:
        json.dump(manifest, f)
        
    monkeypatch.setattr(sys, "argv", ["prog", "--data-dir", str(mock_data_dir)])
    assert validator.main() == 1
    out, _ = capsys.readouterr()
    assert "DATA_REQUIRED: manifest must contain exactly M15 and H1 data" in out
