"""Download DXY (US Dollar Index) data via yfinance and save as CSV."""

import yfinance as yf
import pandas as pd
from pathlib import Path

def download_dxy(output_path: Path | None = None) -> pd.DataFrame:
    if output_path is None:
        output_path = Path("data/context/dxy/dxy.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = yf.download("DX-Y.NYB", start="2014-12-01", end="2026-01-10", auto_adjust=True, progress=False)
    if hasattr(df.columns, "droplevel"):
        try:
            df = df.droplevel(1, axis=1)
        except Exception:
            pass

    df = df.reset_index()[["Date", "Close"]].rename(columns={"Close": "Value"})
    df["Date"] = df["Date"].dt.date.astype(str)
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")
    print(f"NaNs: {df['Value'].isna().sum()}")
    print(f"Range: {df['Value'].min():.2f} - {df['Value'].max():.2f}")
    return df

if __name__ == "__main__":
    download_dxy()
