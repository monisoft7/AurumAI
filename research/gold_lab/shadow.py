"""One durable quarter-hour shadow observation, or a separate research report. No trading API."""

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path

import pandas as pd
import requests

from .data import CACHE, ROOT, write_atomic
from .feed import Feed
from .lab import database
from .strategies import Market, Plan
from .ticks import settle

ZONE = "Africa/Tripoli"


def schema(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS probes(slot TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS probe_retries(slot TEXT,attempt INTEGER,payload TEXT,PRIMARY KEY(slot,attempt));
        CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,family TEXT NOT NULL,issued_ms INTEGER NOT NULL,
          plan TEXT NOT NULL, status TEXT NOT NULL, outcome TEXT,masked INTEGER NOT NULL);
    """)


def in_window(slot):
    local = slot.tz_convert(ZONE)
    return local.weekday() < 5 and 540 <= local.hour * 60 + local.minute <= 1380


def reconcile(db, feed, now_ms):
    errors = []
    for key, at, payload in db.execute(
        "SELECT id,issued_ms,plan FROM orders WHERE status='pending'"
    ).fetchall():
        try:
            times, bid, ask = feed.ticks(at, min(now_ms, at + 5 * 3600000 + 300001))
            outcome = settle(times, bid, ask, at, Plan(**json.loads(payload)), now_ms)
        except (RuntimeError, ValueError) as exc:
            errors.append(str(exc))
            if now_ms - at <= 5 * 3600000 + 300000:
                continue
            outcome = {
                "status": "unobserved",
                "filled": None,
                "net_r": None,
                "end": now_ms,
            }
        db.execute(
            "UPDATE orders SET status=?,outcome=? WHERE id=?",
            (outcome["status"], json.dumps(outcome), key),
        )
    return errors


def observation(db, scheduled, feed, clock=lambda: datetime.now(timezone.utc)):
    slot = pd.Timestamp(scheduled).tz_convert("UTC").floor("15min")
    if not in_window(slot):
        return {"state": "outside Tripoli window"}
    key = slot.isoformat()
    with db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute(
            "SELECT payload FROM probes WHERE slot=?", (key,)
        ).fetchone()
        if existing:
            old = json.loads(existing[0])
            retries = db.execute(
                "SELECT count(*) FROM probe_retries WHERE slot=?", (key,)
            ).fetchone()[0]
            if not old["errors"] or old["orders"] or retries >= 2:
                return old
            db.execute(
                "INSERT INTO probe_retries VALUES(?,?,?)",
                (key, retries + 1, existing[0]),
            )
        row = {
            "slot": key,
            "opportunities": 0,
            "orders": 0,
            "rejections": [],
            "errors": [],
            "quote": None,
        }
        prior = db.execute(
            "SELECT max(slot) FROM probes WHERE slot<?", (key,)
        ).fetchone()[0]
        row["missed_slots_since_last"] = (
            sum(in_window(t) for t in pd.date_range(prior, key, freq="15min")[1:-1])
            if prior
            else 0
        )
        active = [
            json.loads(r[0])
            for r in db.execute("SELECT payload FROM experiments")
            if json.loads(r[0])["stage"] == "SHADOW"
        ]
        try:
            with feed as source:
                try:
                    row["quote"] = source.quote()
                except (ValueError, RuntimeError) as exc:
                    row["errors"].append(str(exc))
                now = pd.Timestamp(clock())
                ms = int(now.value // 1_000_000)
                row["errors"].extend(reconcile(db, source, ms))
                if not active:
                    row["rejections"].append("no historically qualified strategy")
                elif not row["quote"] or not 0 <= (now - slot).total_seconds() <= 90:
                    row["rejections"].append(
                        "market closed, feed unverified or slot late"
                    )
                else:
                    market = Market(source.minutes(slot))
                    for exp in active:
                        family = exp["family"]
                        signals = market.signals(family)
                        if not signals or signals[-1][0] != slot:
                            row["rejections"].append(
                                family + ": no setup on completed bar"
                            )
                            continue
                        p = signals[-1][1]
                        masked = (
                            family == "pullback_replication" and p.regime != "trend"
                        )
                        row["opportunities"] += int(not masked)
                        if db.execute(
                            "SELECT 1 FROM orders WHERE family=? AND status='pending'",
                            (family,),
                        ).fetchone():
                            row["rejections"].append(family + ": active order")
                            continue
                        q = row["quote"]
                        side = 1 if p.action.startswith("BUY") else -1
                        price = q["ask"] if side == 1 else q["bid"]
                        moved = (price - p.entry) * side
                        if (p.action.endswith("LIMIT") and moved <= 0) or (
                            p.action.endswith("NOW")
                            and abs(moved) > 0.1 * abs(p.entry - p.stop)
                        ):
                            row["rejections"].append(family + ": entry passed")
                            continue
                        actual = pd.Timestamp(clock())
                        if (actual - slot).total_seconds() > 90 or (
                            actual - pd.Timestamp(q["at"])
                        ).total_seconds() > 90:
                            row["rejections"].append(
                                family + ": late after signal computation"
                            )
                            continue
                        db.execute(
                            "INSERT INTO orders VALUES(?,?,?,?,'pending',NULL,?)",
                            (
                                key + exp["id"],
                                family,
                                actual.value // 1_000_000 + 1,
                                json.dumps(asdict(p)),
                                int(masked),
                            ),
                        )
                        row["orders"] += int(not masked)
        except (ValueError, RuntimeError, ImportError) as exc:
            row["errors"].append(str(exc))
        db.execute(
            "INSERT INTO probes VALUES(?,?) ON CONFLICT(slot) DO UPDATE SET payload=excluded.payload",
            (key, json.dumps(row)),
        )
    return row


def report(db, day):
    first = pd.Timestamp(day, tz=ZONE)
    after = first + pd.Timedelta(days=1)
    a, b = first.tz_convert("UTC").isoformat(), after.tz_convert("UTC").isoformat()
    rows = [
        json.loads(r[0])
        for r in db.execute(
            "SELECT payload FROM probes WHERE slot>=? AND slot<?", (a, b)
        )
    ]
    attempts = rows + [
        json.loads(r[0])
        for r in db.execute(
            "SELECT payload FROM probe_retries WHERE slot>=? AND slot<?", (a, b)
        )
    ]
    events = [
        dict(id=i, family=family, conclusion=conclusion)
        for i, family, conclusion in db.execute(
            "SELECT e.id,x.family,e.conclusion FROM research_events e JOIN experiments x ON e.id=x.id "
            "WHERE e.recorded_at>=? AND e.recorded_at<? ORDER BY x.family",
            (a, b),
        )
    ]
    results = {}
    for family, status, raw in db.execute(
        "SELECT family,status,outcome FROM orders WHERE masked=0 AND outcome IS NOT NULL"
    ):
        out = json.loads(raw)
        if (
            out["net_r"] is not None
            and first.value // 1_000_000 <= out["end"] < after.value // 1_000_000
        ):
            group = results.setdefault(family, {"closed": 0, "net_r": 0.0})
            group["closed"] += 1
            group["net_r"] += out["net_r"]
    return {
        "day": str(day),
        "timezone": ZONE,
        "probes": len(rows),
        "opportunities": sum(r["opportunities"] for r in rows),
        "paper_orders": sum(r["orders"] for r in rows),
        "closed": sum(r["closed"] for r in results.values()),
        "net_r": sum(r["net_r"] for r in results.values()),
        "by_strategy": results,
        "rejections": dict(Counter(x for r in rows for x in r["rejections"])),
        "data_issues": dict(Counter(x for r in attempts for x in r["errors"])),
        "missed_slots_since_previous": sum(r["missed_slots_since_last"] for r in rows),
        "research_lessons": events,
    }


def send_report(content):
    from dotenv import dotenv_values

    env = {**dotenv_values(ROOT / ".env"), **os.environ}
    token = env.get("AURUM_RESEARCH_BOT_TOKEN")
    chat = env.get("AURUM_RESEARCH_CHAT_ID")
    if (
        not token
        or not chat
        or not env.get("TELEGRAM_CHAT_ID")
        or chat == env["TELEGRAM_CHAT_ID"]
        or token == env.get("TELEGRAM_BOT_TOKEN")
    ):
        raise ValueError(
            "distinct research credentials and verified destination required"
        )
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": content},
            timeout=10,
        )
    except requests.RequestException:
        raise RuntimeError("research report delivery unavailable") from None
    if not response.ok:
        raise RuntimeError(f"research report delivery HTTP {response.status_code}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["once", "report"])
    parser.add_argument("--root", type=Path, default=CACHE)
    parser.add_argument("--day", type=pd.Timestamp)
    parser.add_argument("--broker-zone", default="Europe/Helsinki")
    parser.add_argument("--send-report", action="store_true")
    args = parser.parse_args()
    db = database(args.root / "memory.sqlite")
    try:
        schema(db)
        now = pd.Timestamp.now("UTC")
        if args.action == "once":
            if args.send_report:
                parser.error("--send-report requires report")
            if not in_window(now.floor("15min")):
                return
            row = observation(db, now, Feed(args.broker_zone))
            print(json.dumps(row))
            if now.tz_convert(ZONE).hour != 23:
                return
        day = args.day.date() if args.day is not None else now.tz_convert(ZONE).date()
        content = json.dumps(report(db, day), indent=2, ensure_ascii=False)
        write_atomic(args.root / "reports" / f"{day}.json", content.encode())
        if args.send_report:
            send_report(content)
        print(content)
    finally:
        db.close()


if __name__ == "__main__":
    main()
