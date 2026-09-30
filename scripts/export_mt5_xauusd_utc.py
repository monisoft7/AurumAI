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
) -> dict | None:
    rates = mt5.copy_rates_range(symbol, timeframe, start_time, end_time)
    if rates is None or len(rates) == 0:
        logger.error(f"Failed to get {timeframe_name} data: {mt5.last_error()}")
        return None

    csv_path = out_dir / f"{symbol}_{timeframe_name}_utc.csv"

    if timeframe == mt5.TIMEFRAME_M15:
        duration = timedelta(minutes=15)
    elif timeframe == mt5.TIMEFRAME_H1:
        duration = timedelta(hours=1)
    else:
        duration = timedelta(0)

    row_count = 0
    first_bar_open_utc = None
    last_bar_close_utc = None

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
            "real_volume",
            "spread_points"
        ])
        for r in rates:
            bo_utc = datetime.fromtimestamp(int(r['time']), timezone.utc)
            bc_utc = bo_utc + duration

            # Exclude incomplete last candle
            if bc_utc > end_time:
                continue

            bo_iso = bo_utc.isoformat()
            bc_iso = bc_utc.isoformat()

            if first_bar_open_utc is None:
                first_bar_open_utc = bo_iso
            last_bar_close_utc = bc_iso
            row_count += 1

            writer.writerow([
                bo_iso,
                bc_iso,
                r['open'],
                r['high'],
                r['low'],
                r['close'],
                r['tick_volume'],
                r['real_volume'],
                r['spread']
            ])

    if row_count == 0:
        csv_path.unlink(missing_ok=True)
        return None

    with open(csv_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    return {
        "filename": csv_path.name,
        "sha256": file_hash,
        "row_count": row_count,
        "first_bar_open_utc": first_bar_open_utc,
        "last_bar_close_utc": last_bar_close_utc
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Export MT5 XAUUSD data to UTC CSV")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output directory")
    parser.add_argument("--months", type=int, default=12, help="Months of data to export")
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
        sym_info = mt5.symbol_info(args.symbol)

        if acc_info is None or term_info is None or sym_info is None:
            logger.error(f"Could not get account/terminal/symbol info: {mt5.last_error()}")
            return 1

        args.out_dir.mkdir(parents=True, exist_ok=True)

        end_time = datetime.now(timezone.utc)
        # Approximate months (365.25 days / 12)
        start_time = datetime.fromtimestamp(end_time.timestamp() - args.months * (365.25 / 12) * 24 * 3600, tz=timezone.utc)

        m15_info = _export_timeframe(args.symbol, mt5.TIMEFRAME_M15, "M15", start_time, end_time, args.out_dir)
        h1_info = _export_timeframe(args.symbol, mt5.TIMEFRAME_H1, "H1", start_time, end_time, args.out_dir)

        manifest = {
            "export_created_at_utc": end_time.isoformat(),
            "symbol": args.symbol,
            "broker": acc_info.company,
            "server": acc_info.server,
            "digits": sym_info.digits,
            "point": sym_info.point,
            "source_interval_months": args.months,
            "timestamp_source": "MetaTrader5.copy_rates_range",
            "timestamp_semantics": "UTC bar open",
            "completed_bars_only": True,
            "mt5_package_version": mt5.__version__,
            "terminal_build": term_info.build,
            "files": {}
        }

        for info in (m15_info, h1_info):
            if info:
                filename = info.pop("filename")
                manifest["files"][filename] = info

        manifest_path = args.out_dir / f"{args.symbol}_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Export complete. Manifest saved to {manifest_path.name}")

    finally:
        mt5.shutdown()

    return 0

if __name__ == "__main__":
    sys.exit(main())
