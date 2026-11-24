"""Sample spot in shadow mode. Optional baseline runs once in an isolated directory."""
import argparse
import json
import sys
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv
from gold_shadow.journal import record, summarize
from gold_shadow.market import UTC, fetch_bars, fetch_quote
from gold_shadow.reference import reference_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "runtime/gold_shadow/shadow.sqlite")
    parser.add_argument("--with-baseline", action="store_true")
    parser.add_argument("--summary", action="store_true", help="report stored shadow outcomes offline")
    args = parser.parse_args()
    if args.summary:
        print(json.dumps(summarize(args.db), indent=2))
        return 0
    load_dotenv(ROOT / ".env")
    legacy = None
    reference_error = None
    if args.with_baseline:
        try:
            legacy = reference_run(ROOT)
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
            reference_error = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
    bars, quote, errors = [], None, []
    for label, fetch in (("bars", lambda: fetch_bars(datetime.now(UTC), 480)), ("quote", fetch_quote)):
        try:
            value = fetch()
            if label == "bars":
                bars = value
            else:
                quote = value
        except (ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
            errors.append(f"{label}: {type(exc).__name__}")
    row = record(args.db, datetime.now(UTC), bars, quote, legacy, errors)
    print(json.dumps(dict(row, legacy=legacy, reference_error=reference_error), ensure_ascii=True))
    return 1 if errors or reference_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
