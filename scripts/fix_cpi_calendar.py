"""Truncate CPI release calendar to match gold data availability (ends 2025-12-31)."""
import pandas as pd

df = pd.read_csv("data/calendar/cpi_releases.csv")
before = len(df)
df = df[df["release_timestamp"] <= "2025-12-31"].copy()
df.to_csv("data/calendar/cpi_releases.csv", index=False)
print(f"CPI calendar: {before} -> {len(df)} rows (removed {before - len(df)})")
print(f"Last entry: {df.iloc[-1]['release_timestamp']}")
