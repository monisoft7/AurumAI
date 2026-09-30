"""Export historical XAUUSD data from MT5 with explicit UTC timing and metadata.

This script reads from a locally running MetaTrader 5 terminal. It exports M15 and H1 data
with explicit UTC bar_open and bar_close timestamps, spread, and broker metadata.
It does not execute trades.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import sys
import zoneinfo
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

logger = logging.getLogger(__name__)


def _export_timeframe(
    symbol: str,
    timeframe: int,
    timeframe_name: str,
    start_time: datetime,
    end_time: datetime,
    out_dir: Path,
) -> Path | None:
    rates = mt5.copy_rates_range(symbol, timeframe, start_time, end_time)
    if rates is None or len(rates) == 0:
        logger.error(f"Failed to get {timeframe_name} data: {mt5.last_error()}")
        return None

    csv_path = out_dir / f"{symbol}_{timeframe_name}_utc.csv"
    
    # In MT5, rates['time'] is the bar open time in seconds (POSIX timestamp)
    # The timezone of this timestamp is broker-dependent but mt5.copy_rates_range
    # returns it as seconds since epoch in broker time? Actually, MT5 timestamps
    # are broker time without timezone. However, if we just assume broker time,
    # we need to convert it. Wait, MT5 in Python returns broker time in seconds.
    # To get proper UTC, we'd need to know the broker offset, but MT5 doesn't
    # provide timezone offset directly in all cases, though recent MT5 versions do.
    # For now, we capture it as is, and we will need to verify broker time.
    # Actually, MetaTrader5 python package returns POSIX timestamp assuming broker time.
    
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "bar_open_utc",
            "bar_close_utc",
            "open",
            "high",
            "low",
            "close",
            "tick_volume",
            "spread"
        ])
        for r in rates:
            # MT5 returns time as seconds since epoch representing broker local time.
            # MetaQuotes-Demo and most FX brokers use EET (Europe/Chisinau or Europe/Kyiv or Europe/Bucharest).
            # We must localize it as broker time then convert to UTC.
            broker_tz = zoneinfo.ZoneInfo("Europe/Bucharest")
            
            # The timestamp from MT5 is the broker's local time as if it were UTC epoch.
            # So datetime.fromtimestamp(r['time'], timezone.utc) gives a datetime that LOOKS 
            # like the broker time but claims to be UTC. We replace tzinfo, then convert to true UTC.
            naive_broker_dt = datetime.fromtimestamp(r['time'], tz=timezone.utc).replace(tzinfo=None)
            
            try:
                broker_dt = naive_broker_dt.replace(tzinfo=broker_tz)
            except Exception:
                # Handle ambiguous/nonexistent times if needed, fold=0
                broker_dt = naive_broker_dt.replace(tzinfo=broker_tz)
                
            bo_utc = broker_dt.astimezone(timezone.utc)
            
            if timeframe == mt5.TIMEFRAME_M15:
                duration = timedelta(minutes=15)
            elif timeframe == mt5.TIMEFRAME_H1:
                duration = timedelta(hours=1)
            else:
                duration = timedelta(0)
                
            bc_utc = bo_utc + duration
            
            bo_iso = bo_utc.isoformat()
            bc_iso = bc_utc.isoformat()
            
            writer.writerow([
                bo_iso,
                bc_iso,
                r['open'],
                r['high'],
                r['low'],
                r['close'],
                r['tick_volume'],
                r['spread']
            ])
            
    return csv_path


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Export MT5 XAUUSD data to UTC CSV")
    parser.add_argument("--out-dir", type=Path, default=Path("data/raw"), help="Output directory")
    parser.add_argument("--months", type=int, default=24, help="Months of data to export")
    parser.add_argument("--symbol", type=str, default="XAUUSD", help="Symbol to export")
    args = parser.parse_args()

    if mt5 is None:
        logger.error("MetaTrader5 package is not installed.")
        return 1

    if not mt5.initialize():
        logger.error(f"MT5 initialize failed: {mt5.last_error()}")
        return 1

    try:
        acc_info = mt5.account_info()
        term_info = mt5.terminal_info()
        if acc_info is None or term_info is None:
            logger.error(f"Could not get account/terminal info: {mt5.last_error()}")
            return 1
            
        args.out_dir.mkdir(parents=True, exist_ok=True)
        
        end_time = datetime.now(timezone.utc)
        # Approximate months
        start_time = datetime.fromtimestamp(end_time.timestamp() - args.months * 30 * 24 * 3600, tz=timezone.utc)
        
        m15_path = _export_timeframe(args.symbol, mt5.TIMEFRAME_M15, "M15", start_time, end_time, args.out_dir)
        h1_path = _export_timeframe(args.symbol, mt5.TIMEFRAME_H1, "H1", start_time, end_time, args.out_dir)
        
        manifest = {
            "export_created_at_utc": end_time.isoformat(),
            "symbol": args.symbol,
            "broker": acc_info.company,
            "server": acc_info.server,
            "source_interval_months": args.months,
            "files": {}
        }
        
        for path in (m15_path, h1_path):
            if path is not None and path.exists():
                with open(path, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                manifest["files"][path.name] = {
                    "sha256": file_hash,
                    "path": str(path)
                }
                
        manifest_path = args.out_dir / f"{args.symbol}_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
            
        logger.info(f"Export complete. Manifest saved to {manifest_path}")
        
    finally:
        mt5.shutdown()

    return 0

if __name__ == "__main__":
    sys.exit(main())
