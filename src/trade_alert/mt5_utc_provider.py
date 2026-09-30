"""MT5 UTC Provider for reading exported UTC OHLCV CSVs."""

import pandas as pd
from datetime import datetime, timezone
from pathlib import Path


class MT5UTCProvider:
    def __init__(self, data_dir: Path):
        self.frames = {}
        for tf in ("M15", "H1"):
            path = data_dir / f"XAUUSD_{tf}_utc.csv"
            if not path.exists():
                raise FileNotFoundError(f"Missing {path}")
            
            df = pd.read_csv(path)
            # Use bar_close_utc as the availability index
            df['available_at'] = pd.to_datetime(df['bar_close_utc'])
            if df['available_at'].dt.tz is None:
                df['available_at'] = df['available_at'].dt.tz_localize('UTC')
                
            df.set_index('available_at', inplace=True)
            df.sort_index(inplace=True)
            
            df.rename(columns={'tick_volume': 'volume', 'spread_points': 'spread'}, inplace=True)
            self.frames[tf] = df

    def completed(self, timeframe: str, as_of: datetime) -> pd.DataFrame:
        if timeframe not in self.frames:
            raise ValueError(f"Timeframe {timeframe} not loaded")
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
            
        as_of_utc = as_of.astimezone(timezone.utc)
        df = self.frames[timeframe]
        return df.loc[:as_of_utc].copy()
