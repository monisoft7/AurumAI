"""Read-only attribution and naive confidence sweep for a private paper ledger.

Usage: python scripts/trade_alert_attribution.py PATH_TO_PRIVATE_LEDGER
No ledger file is opened for writing. Counterfactual returns remain research only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def analyze(root: Path) -> dict:
    predictions = {
        item["prediction_id"]: item
        for path in (root / "predictions").glob("*.json")
        if (item := json.loads(path.read_text(encoding="utf-8")))
    }
    rows = []
    for path in (root / "outcomes").glob("*.json"):
        outcome = json.loads(path.read_text(encoding="utf-8"))
        prediction = predictions.get(outcome.get("prediction_id"))
        if not prediction or outcome.get("status") != "completed":
            continue
        rows.append({
            "prediction": outcome["prediction_id"],
            "date": prediction.get("decision_timestamp"),
            "direction": prediction.get("direction"),
            "confidence": prediction.get("confidence"),
            "composite": (prediction.get("decision_snapshot", {}).get("best_rejected") or {}).get("composite_score"),
            "rr": (prediction.get("decision_snapshot", {}).get("gate_reasons") or {}).get("risk_reward_ratio"),
            "horizon": outcome.get("horizon_sessions"),
            "verdict": outcome.get("abstention_verdict"),
            "counterfactual_return_pct": outcome.get("counterfactual_return_pct"),
            "transaction_cost_pct": (
                (float((prediction.get("transaction_costs") or {}).get("round_trip_cost_bps", 0))
                 + 2 * float((prediction.get("transaction_costs") or {}).get("slippage_bps_per_side", 0))) / 100
            ),
        })
    rows.sort(key=lambda x: (x["date"] or "", x["prediction"], x["horizon"] or 0))
    sweep = []
    for horizon in sorted({r["horizon"] for r in rows if isinstance(r["horizon"], int)}):
        for step in range(30, 61):
            threshold = step / 100
            eligible = [r for r in rows if r["horizon"] == horizon
                        and isinstance(r["confidence"], (int, float))
                        and r["confidence"] >= threshold
                        and isinstance(r["counterfactual_return_pct"], (int, float))
                        and isinstance(r["transaction_cost_pct"], (int, float))]
            net = [r["counterfactual_return_pct"] - r["transaction_cost_pct"] for r in eligible]
            sweep.append({"horizon": horizon, "threshold": threshold, "n": len(net),
                          "mean_net_counterfactual_pct": sum(net) / len(net) if net else None})
    return {"rows": rows, "sweep": sweep,
            "positive_after_costs": any(r["mean_net_counterfactual_pct"] is not None
                                        and r["mean_net_counterfactual_pct"] > 0
                                        for r in sweep)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.ledger), indent=2, ensure_ascii=False))
