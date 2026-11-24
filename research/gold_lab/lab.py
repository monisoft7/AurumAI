"""Finite research queue, chronological evaluator and durable hypothesis memory.
Run with python -m research.gold_lab.lab {fetch,propose,run,export}.
"""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .data import (
    CACHE,
    PROTOCOL,
    ROOT,
    acquire,
    digest,
    minute_data,
    pinned_hash,
    tick_audit,
)
from .strategies import Market, simulate

PRIOR = ROOT / "historical_validation/evolution_results.json"
PUBLIC = Path(__file__).with_name("results.json")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def source_digest(path):
    """Fingerprint repository text identically on LF and CRLF checkouts."""
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=60)
    db.execute(
        "CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, family TEXT NOT NULL, payload TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS seals (period TEXT PRIMARY KEY, fingerprint TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS research_events (id TEXT PRIMARY KEY, recorded_at TEXT NOT NULL, conclusion TEXT NOT NULL)"
    )
    if PUBLIC.exists():
        archive = json.loads(PUBLIC.read_bytes())
        seals = archive.get("seals", [])
        if any(r["final"] is not None for r in archive["experiments"]) and not seals:
            raise ValueError("archive missing its consumed holdout seal")
        for period, fingerprint in seals:
            db.execute("INSERT OR IGNORE INTO seals VALUES(?,?)", (period, fingerprint))
            if (
                db.execute(
                    "SELECT fingerprint FROM seals WHERE period=?", (period,)
                ).fetchone()[0]
                != fingerprint
            ):
                raise ValueError("archive conflicts with local holdout seal")
        for r in archive["experiments"]:
            db.execute(
                "INSERT OR IGNORE INTO experiments VALUES(?,?,?)",
                (r["id"], r["family"], canonical(r)),
            )
        for event in archive.get("events", []):
            db.execute("INSERT OR IGNORE INTO research_events VALUES (?,?,?)", event)
        db.commit()
    return db


def proposals(db, protocol):
    previous = json.loads(PRIOR.read_bytes())["holdout"]
    subgroup = previous["combined_weekday_06_16_utc_sensitivity"]["by_regime"]["trend"]
    memory = [
        json.loads(row[0])
        for row in db.execute("SELECT payload FROM experiments ORDER BY id")
    ]
    result = []
    for spec in protocol["hypotheses"]:
        related = [r for r in memory if r["family"] == spec["id"]]
        why = spec["mechanism"]
        if spec["id"] == "pullback_replication":
            why += f" Prior exploratory mean {subgroup['expectancy_net_r']}R over {subgroup['closed']} fills."
        else:
            why += f" Prior unrestricted combined baseline lost {abs(previous['combined']['expectancy_net_r'])}R per fill."
        result.append(
            dict(
                spec,
                rationale=why,
                related=[r["id"] for r in related],
                disposition="requires new evidence"
                if related
                else "test registered mechanism",
                lessons=[r["conclusion"] for r in related],
            )
        )
    return result


def discovery_queue(db, protocol):
    reviewed = proposals(db, protocol)
    ideas = []
    # Propose a different mechanism/data requirement once its predecessor fails.
    # Never infer a trading direction from the sign of the previous P&L.
    alternatives = {
        "pullback_replication": (
            "Cross-asset confirmation",
            "timestamp-aligned USD and real-yield proxy quotes",
            "Test gold pullbacks only after a contemporaneous USD move in the opposite direction; hold gold-only decisions as paired controls.",
        ),
        "ny_exhaustion": (
            "Scheduled-news continuation",
            "consensus vintage, first release timestamp, tradeable gold quotes",
            "Compare the first post-release H1 continuation on surprise days against time-matched non-event days.",
        ),
        "london_asia": (
            "Opening liquidity and fills",
            "two-sided ticks across London open and independent untouched dates",
            "Test whether post-break spread normalisation improves net returns relative to the same break at announcement.",
        ),
        "h4_compression": (
            "Regime-dependent compression",
            "aligned intraday USD cross and gold ticks",
            "Compare expansion following joint USD/gold compression with gold-only compression on paired days.",
        ),
    }
    designs = {
        "pullback_replication": {
            "usd_lookback_minutes": 60,
            "control": "registered gold-only entry",
        },
        "ny_exhaustion": {
            "event": "US CPI first release",
            "holding_hours": 1,
            "control": "same weekday and hour",
        },
        "london_asia": {
            "post_break_minutes": 15,
            "spread_ceiling": "median in preceding 20 London opens",
        },
        "h4_compression": {
            "lookback_h4": 5,
            "compression_ratio": 0.8,
            "control": "gold-only compression",
        },
    }
    for row in reviewed:
        archived = [
            json.loads(payload)
            for (payload,) in db.execute(
                "SELECT payload FROM experiments WHERE family=? ORDER BY id",
                (row["id"],),
            )
        ]
        rejected = [entry for entry in archived if entry["status"] == "rejected"]
        if not rejected:
            continue
        name, data, logic = alternatives[row["id"]]
        diagnostics = []
        for entry in rejected:
            val = entry["validation"]
            diagnostics.append(
                {
                    "experiment": entry["id"],
                    "fold_expectancies_r": [f["expectancy_r"] for f in val["folds"]],
                    "cost_stress_change_r": round(
                        val["double_cost"]["expectancy_r"]
                        - val["summary"]["expectancy_r"],
                        5,
                    )
                    if val["double_cost"]["closed"] and val["summary"]["closed"]
                    else None,
                    "unobserved_paths": val["summary"]["outcomes"].get("unobserved", 0),
                }
            )
        ideas.append(
            {
                "hypothesis": name,
                "related": [r["id"] for r in rejected],
                "evidence": [r["conclusion"] for r in rejected],
                "diagnostics": diagnostics,
                "required_data": data,
                "design": logic,
                "proposed_parameters": designs[row["id"]],
                "state": "needs new preregistration and data",
            }
        )
    return {"registered": reviewed, "next_round": ideas}


def summary(records):
    vals = np.array([v for _, v, _, _ in records if v is not None])
    equity = np.r_[0.0, np.cumsum(vals)]
    return {
        "orders": len(records),
        "filled": sum(bool(row[3]) for row in records),
        "closed": len(vals),
        "outcomes": dict(Counter(row[2] for row in records)),
        "expectancy_r": round(float(vals.mean()), 5) if len(vals) else None,
        "net_r": round(float(vals.sum()), 5),
        "max_dd_r": round(float((np.maximum.accumulate(equity) - equity).max()), 5),
        "win_rate": round(float((vals > 0).mean()), 5) if len(vals) else None,
        "profit_factor": round(float(vals[vals > 0].sum() / -vals[vals < 0].sum()), 5)
        if (vals < 0).any()
        else None,
    }


def daily(records, axis):
    values = pd.Series(0.0, index=axis)
    for t, net, _, _ in records:
        if net is not None:
            values.at[t.normalize()] += net
    return values.to_numpy()


def lower_bound(values):
    # Circular blocks sample trading days including zero-return days.
    rng = np.random.default_rng(1951)
    n = len(values)
    starts = rng.integers(0, n, (2000, (n + 4) // 5))
    ix = ((starts[:, :, None] + np.arange(5)) % n).reshape(2000, -1)[:, :n]
    return round(float(np.quantile(values[ix].mean(axis=1), 0.05 / 4)), 6)


def assess(folds, references, sensitivities, stress, axis, limits):
    records = sum(folds, [])
    sums = summary(records)
    dr = daily(records, axis)
    bounds = {"cash": lower_bound(dr)}
    bounds.update({k: lower_bound(dr - daily(r, axis)) for k, r in references.items()})
    each = [summary(f) for f in folds]
    neighbors = [summary(s)["expectancy_r"] for s in sensitivities]
    stressed = summary(stress)
    reasons = []
    if sums["closed"] < limits["min_closed_validation"] or any(
        s["closed"] < limits["min_closed_per_fold"] for s in each
    ):
        reasons.append("insufficient closed fills")
    if any((s["expectancy_r"] or 0) <= 0 for s in each):
        reasons.append("nonpositive chronological fold")
    if min(bounds.values()) <= 0:
        reasons.append("adjusted lower bound fails cash or active references")
    if sums["max_dd_r"] > limits["max_drawdown_r"]:
        reasons.append("drawdown exceeds budget")
    if (stressed["expectancy_r"] or 0) <= 0 or any((n or 0) <= 0 for n in neighbors):
        reasons.append("cost or parameter sensitivity")
    if sums["outcomes"].get("unobserved", 0) > 0.01 * len(records):
        reasons.append("unobserved execution paths")
    return {
        "summary": sums,
        "folds": each,
        "lower_daily_r": bounds,
        "double_cost": stressed,
        "neighbor_expectancies": neighbors,
        "reasons": reasons,
        "references": {k: summary(v) for k, v in references.items()},
    }


def utc(value):
    return pd.Timestamp(value, tz="UTC")


def evaluate_year(year, specs, limits, root, development=False):
    frame, quality = minute_data(root / f"histdata-M1-{year}.zip")
    market = Market(frame)
    first, mid, end = (
        utc(f"{year}-01-01"),
        utc(f"{year}-07-01"),
        utc(f"{year + 1}-01-01"),
    )
    bounds = [(first, end)] if development else [(first, mid), (mid, end)]

    def folds(family, signals, cost=1):
        return [simulate(market, signals, family, a, b, cost) for a, b in bounds]

    refs = {k: sum(folds(k, market.signals(k)), []) for k in ("long_only", "momentum")}
    data = {}
    for spec in specs:
        family = spec["id"]
        base_parameter = {
            "pullback_replication": 0.5,
            "london_asia": 2,
            "ny_exhaustion": 2,
            "h4_compression": 0.8,
        }[family]
        if spec["parameter"] != base_parameter:
            raise ValueError("unsupported parameter in this preregistered round")
        signals = market.signals(family)
        base = folds(family, signals)
        if development:
            data[family] = summary(base[0])
            continue
        neighbors = [
            sum(folds(family, market.signals(family, scale)), [])
            for scale in (0.8, 1.2)
        ]
        axis = pd.bdate_range(first, end - pd.Timedelta(days=1))
        data[family] = assess(
            base, refs, neighbors, sum(folds(family, signals, 2), []), axis, limits
        )
    return data, dict(quality, full_m15=len(market.m15))


def remember(db, protocol, root):
    candidates = proposals(db, protocol)
    hashes = {str(y): digest(root / f"histdata-M1-{y}.zip") for y in (2023, 2024, 2025)}
    if any(value != pinned_hash(year) for year, value in hashes.items()):
        raise ValueError("data version differs from the registered cohort")
    ids = {
        s["id"]: hashlib.sha256(
            canonical([s["id"], s["parameter"], hashes, protocol]).encode()
        ).hexdigest()[:20]
        for s in candidates
    }
    todo = [
        s
        for s in candidates
        if not db.execute(
            "SELECT 1 FROM experiments WHERE id=?", (ids[s["id"]],)
        ).fetchone()
    ]
    if not todo:
        return "existing results reused"
    if any(s["related"] for s in todo):
        raise ValueError(
            "related experiment already archived; a separate preregistered independent cohort is required"
        )
    dev, q1 = evaluate_year(2023, todo, protocol["gates"], root, True)
    valid, q2 = evaluate_year(2024, todo, protocol["gates"], root)
    survivors = [s for s in todo if not valid[s["id"]]["reasons"]]
    final = {}
    if survivors:
        lock = hashlib.sha256(
            canonical(
                [
                    ids,
                    hashes,
                    sorted(s["id"] for s in survivors),
                    source_digest(Path(__file__)),
                    source_digest(Path(__file__).with_name("strategies.py")),
                ]
            ).encode()
        ).hexdigest()
        with db:
            db.execute("INSERT OR IGNORE INTO seals VALUES (?,?)", ("2025", lock))
            if (
                db.execute(
                    "SELECT fingerprint FROM seals WHERE period='2025'"
                ).fetchone()[0]
                != lock
            ):
                raise ValueError(
                    "final cohort is already consumed by a different experiment"
                )
        final, _ = evaluate_year(2025, survivors, protocol["gates"], root)
    with db:
        for s in todo:
            k = s["id"]
            failed = valid[k]["reasons"] or final.get(k, {}).get("reasons", [])
            row = {
                "id": ids[k],
                "family": k,
                "hypothesis": s["mechanism"],
                "rationale": s["rationale"],
                "parameter": s["parameter"],
                "required_data": s["data"],
                "protocol": source_digest(PROTOCOL),
                "data_sha256": hashes,
                "windows": [
                    protocol["development"],
                    protocol["validation"],
                    protocol["sealed"],
                ],
                "execution": protocol["execution"],
                "development": dev[k],
                "validation": valid[k],
                "quality": {"development": q1, "validation": q2},
                "final": final.get(k),
                "stage": "RESEARCH" if failed else "SHADOW",
                "status": "rejected" if failed else "candidate",
                "conclusion": "; ".join(failed)
                if failed
                else "historical gates passed; forward evaluation pending",
            }
            db.execute(
                "INSERT OR IGNORE INTO experiments VALUES(?,?,?)",
                (ids[k], k, canonical(row)),
            )
            db.execute(
                "INSERT OR IGNORE INTO research_events VALUES (?,?,?)",
                (row["id"], datetime.now(timezone.utc).isoformat(), row["conclusion"]),
            )
    return (
        f"recorded {len(todo)} experiments, {len(survivors)} reached sealed evaluation"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["fetch", "propose", "run", "export", "verify"]
    )
    parser.add_argument("--root", type=Path, default=CACHE)
    args = parser.parse_args()
    if args.action == "fetch":
        for year in (2023, 2024, 2025):
            print(year, minute_data(acquire(year, root=args.root))[1])
        print(tick_audit(acquire(2023, 4, args.root)))
        return
    p = json.loads(PROTOCOL.read_bytes())
    db = database(args.root / "memory.sqlite")
    try:
        if args.action == "run":
            print(remember(db, p, args.root))
        elif args.action == "propose":
            print(json.dumps(discovery_queue(db, p), indent=2))
        elif args.action == "verify":
            for year in (2023, 2024, 2025):
                if digest(args.root / f"histdata-M1-{year}.zip") != pinned_hash(year):
                    raise ValueError(f"data version differs for {year}")
            dev, _ = evaluate_year(2023, p["hypotheses"], p["gates"], args.root, True)
            val, _ = evaluate_year(2024, p["hypotheses"], p["gates"], args.root)
            for s in p["hypotheses"]:
                row = json.loads(
                    db.execute(
                        "SELECT payload FROM experiments WHERE family=?", (s["id"],)
                    ).fetchone()[0]
                )
                if (
                    dev[s["id"]] != row["development"]
                    or val[s["id"]] != row["validation"]
                ):
                    raise ValueError(
                        "replay differs from archived experiment: " + s["id"]
                    )
            print("verified every development and validation result")
        else:
            rows = [
                json.loads(row[0])
                for row in db.execute("SELECT payload FROM experiments ORDER BY family")
            ]
            events = list(
                db.execute(
                    "SELECT id,recorded_at,conclusion FROM research_events ORDER BY id"
                )
            )
            seals = list(
                db.execute("SELECT period,fingerprint FROM seals ORDER BY period")
            )
            print(
                json.dumps(
                    {"experiments": rows, "events": events, "seals": seals}, indent=2
                )
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
