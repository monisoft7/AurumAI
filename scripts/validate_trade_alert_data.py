"""Validate exported MT5 data against Challenger data contracts."""

import argparse
import hashlib
import json
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd


def _validate_file(csv_path: Path, info: dict, timeframe: str, export_created_at_utc: str) -> None:
    expected_hash = info.get("sha256")
    expected_row_count = info.get("row_count")
    expected_first_open = info.get("first_bar_open_utc")
    expected_last_close = info.get("last_bar_close_utc")

    if not all([expected_hash, expected_row_count, expected_first_open, expected_last_close]):
        raise ValueError(f"DATA_REQUIRED: missing mandatory metadata for {csv_path.name}")

    with open(csv_path, "rb") as f:
        actual_hash = hashlib.sha256(f.read()).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError(f"DATA_REQUIRED: hash mismatch for {csv_path.name}")
        
    df = pd.read_csv(csv_path)
    
    if len(df) != expected_row_count:
        raise ValueError(f"DATA_REQUIRED: row_count mismatch in {csv_path.name}")

    # Check completeness
    if df.isnull().any().any():
        raise ValueError(f"DATA_REQUIRED: missing values in {csv_path.name}")
        
    required_cols = {'bar_open_utc', 'bar_close_utc', 'open', 'high', 'low', 'close', 'tick_volume', 'real_volume', 'spread_points'}
    if not required_cols.issubset(set(df.columns)):
        raise ValueError(f"DATA_REQUIRED: missing columns in {csv_path.name}")

    # Check non-negative volumes and spread
    if not ((df['tick_volume'] >= 0) & (df['real_volume'] >= 0) & (df['spread_points'] >= 0)).all():
        raise ValueError(f"DATA_REQUIRED: negative volume or spread in {csv_path.name}")

    # Check OHLC validity
    if not ((df['open'] > 0) & (df['high'] > 0) & (df['low'] > 0) & (df['close'] > 0)).all():
        raise ValueError(f"DATA_REQUIRED: invalid negative or zero OHLC in {csv_path.name}")
    if not (df['high'] >= df[['open', 'close', 'low']].max(axis=1)).all():
        raise ValueError(f"DATA_REQUIRED: high is not the highest in {csv_path.name}")
    if not (df['low'] <= df[['open', 'close', 'high']].min(axis=1)).all():
        raise ValueError(f"DATA_REQUIRED: low is not the lowest in {csv_path.name}")
        
    # Check UTC, sorted, unique
    bo = pd.to_datetime(df['bar_open_utc'])
    bc = pd.to_datetime(df['bar_close_utc'])
    if bo.dt.tz is None or str(bo.dt.tz) != 'UTC' or bc.dt.tz is None or str(bc.dt.tz) != 'UTC':
        raise ValueError(f"DATA_REQUIRED: timestamps not UTC in {csv_path.name}")
    if not bo.is_monotonic_increasing:
        raise ValueError(f"DATA_REQUIRED: timestamps not sorted in {csv_path.name}")
    if not bo.is_unique:
        raise ValueError(f"DATA_REQUIRED: duplicate timestamps in {csv_path.name}")

    # Check first/last matches metadata
    if bo.iloc[0].isoformat() != pd.to_datetime(expected_first_open).isoformat():
        raise ValueError(f"DATA_REQUIRED: first_bar_open_utc mismatch in {csv_path.name}")
    if bc.iloc[-1].isoformat() != pd.to_datetime(expected_last_close).isoformat():
        raise ValueError(f"DATA_REQUIRED: last_bar_close_utc mismatch in {csv_path.name}")

    # Check last close <= export_created_at_utc
    if bc.iloc[-1] > pd.to_datetime(export_created_at_utc):
        raise ValueError(f"DATA_REQUIRED: last bar close > export_created_at_utc in {csv_path.name}")

    # Check alignment and bar duration
    if timeframe == "M15":
        if not ((bo.dt.minute % 15 == 0) & (bo.dt.second == 0)).all():
            raise ValueError(f"DATA_REQUIRED: M15 timestamps not aligned in {csv_path.name}")
        if not (bc - bo == timedelta(minutes=15)).all():
            raise ValueError(f"DATA_REQUIRED: bar_close != bar_open + 15m in {csv_path.name}")
    elif timeframe == "H1":
        if not ((bo.dt.minute == 0) & (bo.dt.second == 0)).all():
            raise ValueError(f"DATA_REQUIRED: H1 timestamps not aligned in {csv_path.name}")
        if not (bc - bo == timedelta(hours=1)).all():
            raise ValueError(f"DATA_REQUIRED: bar_close != bar_open + 1h in {csv_path.name}")
            
    # Check 12 months duration
    duration = bo.max() - bo.min()
    if duration.days < 360:
        raise ValueError(f"DATA_REQUIRED: duration less than 12 months ({duration.days} days) in {csv_path.name}")
    

def validate_directory(data_dir: Path) -> None:
    manifest_path = data_dir / "XAUUSD_manifest.json"
    if not manifest_path.exists():
        raise ValueError("DATA_REQUIRED: manifest missing")
        
    with open(manifest_path) as f:
        manifest = json.load(f)
        
    files = manifest.get("files", {})
    timeframes_found = set()
    for fname in files:
        if "M15" in fname:
            timeframes_found.add("M15")
        elif "H1" in fname:
            timeframes_found.add("H1")
            
    if timeframes_found != {"M15", "H1"}:
        raise ValueError("DATA_REQUIRED: manifest must contain exactly M15 and H1 data")

    export_created_at = manifest.get("export_created_at_utc")
    if not export_created_at:
        raise ValueError("DATA_REQUIRED: export_created_at_utc missing from manifest")

    for fname, info in files.items():
        csv_path = data_dir / fname
        if not csv_path.exists():
            raise ValueError(f"DATA_REQUIRED: {fname} missing")
        tf = "M15" if "M15" in fname else "H1"
        _validate_file(csv_path, info, tf, export_created_at)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    
    try:
        validate_directory(args.data_dir)
    except ValueError as e:
        print(e)
        return 1
            
    print("DATA_VALIDATED: READY_FOR_WALK_FORWARD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
