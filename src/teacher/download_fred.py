import os
from dotenv import load_dotenv
import pandas as pd
from fredapi import Fred

load_dotenv()

API_KEY = os.getenv("FRED_API_KEY")
# Retrieve API key from environment variable

if not API_KEY:
    raise ValueError("FRED_API_KEY environment variable not set.")

# Initialize Fred client
fred = Fred(api_key=API_KEY)

# Series to download
SERIES_IDS = [
    "FEDFUNDS",
    "CPIAUCSL",
    "UNRATE",
    "PAYEMS",
    "DGS10",
    "DFF",
    "PPIACO"
]

# Output directory
OUTPUT_DIR = "data/economic"
os.makedirs(OUTPUT_DIR, exist_ok=True)

for series_id in SERIES_IDS:
    # Fetch the series (returns a pandas Series with datetime index)
    series = fred.get_series(series_id)

    # Convert to DataFrame with Date and Value columns
    df = series.reset_index()
    df.columns = ["Date", "Value"]

    # Save to CSV
    csv_path = os.path.join(OUTPUT_DIR, f"{series_id}.csv")
    df.to_csv(csv_path, index=False)

print("Download complete.")