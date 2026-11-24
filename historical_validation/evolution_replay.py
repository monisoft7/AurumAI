"""Walk forward on fixed closed bars; record every eligible clock and cost scenario."""
import argparse
import hashlib
import json
import sys
from bisect import bisect_right
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gold_shadow.market import Bar, SOURCE, STEP
from gold_shadow.scoring import metrics
from gold_shadow.strategy import POLICIES, decide, evaluate


def replay(bars, lo, hi, policy, cost=1, session_only=False):
    records = []
    busy_until = None
    for i in range(lo, hi):
        issued = bars[i].start + STEP
        if session_only and (issued.weekday() >= 5 or not 6 <= issued.hour < 16):
            continue
        if busy_until and issued < busy_until:
            continue
        plan = decide(bars[max(0, i-32):i+1], issued, policy)
        if plan.action == "WAIT":
            continue
        outcome = evaluate(plan, issued, bars[i+1:min(i+23, hi)], spread=.5*cost, slippage=.1*cost)
        if outcome["observed_until"]:
            busy_until = datetime.fromisoformat(outcome["observed_until"])
        records.append(dict(outcome, regime=plan.regime))
    result = metrics(records, hi-lo)
    result["by_regime"] = {}
    for regime in ("trend", "range"):
        group = [r for r in records if r["regime"] == regime]
        result["by_regime"][regime] = metrics(group, 0)
    return result


def experiment(path):
    raw = path.read_bytes()
    data = json.loads(raw)
    if data["source"] != SOURCE:
        raise ValueError("unknown sample source")
    bars = [Bar(**dict(b, start=datetime.fromisoformat(b["start"]))) for b in data["bars"]]
    if not all(a.start < b.start for a, b in zip(bars, bars[1:])):
        raise ValueError("expected unique chronological bars")
    split = len(bars) // 2
    result = {"source": SOURCE, "sha256": hashlib.sha256(raw).hexdigest(), "n": len(bars),
              "first": bars[0].start.isoformat(), "test_start": bars[split].start.isoformat(),
              "end": (bars[-1].start + STEP).isoformat()}
    for name, lo, hi in (("development", 0, split), ("holdout", split, len(bars))):
        result[name] = {p: replay(bars, lo, hi, p) for p in POLICIES}
        result[name]["combined_double_cost"] = replay(bars, lo, hi, "combined", 2)
        result[name]["combined_weekday_06_16_utc_sensitivity"] = replay(bars, lo, hi, "combined", session_only=True)
    baseline = json.loads((ROOT / "historical_validation/evolution_baseline.json").read_bytes())
    paired = []
    closes = [b.start + STEP for b in bars]
    for run, old in baseline.items():
        issued = datetime.fromisoformat(old["issued"])
        i = bisect_right(closes, issued)
        plan = decide(bars[max(i-33, 0):i], issued)
        outcome = evaluate(plan, issued, bars[i:i+23]) if plan.entry else None
        paired.append({"run": run, "issued": old["issued"], "legacy": old["action"], "shadow": asdict(plan),
                       "age_seconds": (issued-closes[i-1]).total_seconds() if i else None,
                       "reference_close": bars[i-1].close if i else None, "outcome": outcome})
    result["paired"] = paired
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(experiment(args.sample), indent=2) + "\n", encoding="utf-8")
