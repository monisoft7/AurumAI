"""Save a fixed, credential-free snapshot for the registered M15 experiment."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv
from gold_shadow.market import SOURCE, UTC, fetch_bars


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    end = datetime(2026, 11, 23, 23, 59, 59, tzinfo=UTC)
    bars = fetch_bars(end, 5000)
    if not bars:
        raise SystemExit("no completed bars")
    with args.output.open("x", encoding="utf-8", newline="\n") as out:
        json.dump({"source": SOURCE, "end": end.isoformat(), "bars": [b.snapshot() for b in bars]}, out, separators=(",", ":"))
    print(len(bars), bars[0].start, bars[-1].start)
