"""Durable quarter-hour XAUUSD endpoint-risk forecasts on the existing read-only feed."""

import argparse
import json
import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .data import CACHE, write_atomic
from .feed import Feed
from .predictive import gold_features
from .radar_model import load_frozen, predict
from .shadow import ZONE, in_window

ROOT = CACHE.parent / "phase4"
QUARTER = pd.Timedelta(minutes=15)
HOUR = pd.Timedelta(hours=1)
MAX_AGE = 90
ALERT = 0.60
MODE = ("smoke", "pilot", "reserved")


class BidFeed(Feed):
    def __enter__(self):
        super().__enter__()
        symbol = self.mt.symbol_info("XAUUSD")
        if symbol is None or getattr(symbol, "chart_mode", None) != 0:
            self.mt.shutdown()
            raise ValueError("MT5 bid-chart mode could not be verified")
        return self


def open_ledger(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    with db:
        db.executescript("""
          CREATE TABLE IF NOT EXISTS radar_slots (
            cohort TEXT NOT NULL, slot TEXT NOT NULL, checked_at TEXT NOT NULL,
            status TEXT NOT NULL, reason TEXT, PRIMARY KEY(cohort,slot));
          CREATE TABLE IF NOT EXISTS radar_forecasts (
            cohort TEXT NOT NULL, slot TEXT NOT NULL, model TEXT NOT NULL, fingerprint TEXT NOT NULL,
            issued_at TEXT NOT NULL, due TEXT NOT NULL, quote TEXT NOT NULL, reference REAL NOT NULL,
            threshold_bps REAL NOT NULL, threshold_usd_up REAL NOT NULL, threshold_usd_down REAL NOT NULL,
            predictions TEXT NOT NULL, candidate INTEGER NOT NULL, session TEXT NOT NULL,
            outcome INTEGER, end_price REAL, resolved_at TEXT, failure TEXT,
            PRIMARY KEY(cohort,slot), FOREIGN KEY(cohort,slot) REFERENCES radar_slots(cohort,slot));
          CREATE TABLE IF NOT EXISTS radar_delivery (
            attempted_at TEXT PRIMARY KEY, cohort TEXT NOT NULL, slot TEXT NOT NULL, result TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS radar_cohorts (
            cohort TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);
        """)
        db.execute("PRAGMA foreign_keys=ON")
    return db


def ts():
    return pd.Timestamp.now("UTC")


def iso(value):
    return value.isoformat()


def known_open(slot):
    # Conservative common XAUUSD hours. Check both the feature origin and last
    # minute of the outcome against the published weekly maintenance pattern.
    for instant in (slot, slot + HOUR - pd.Timedelta(minutes=1)):
        local = instant.tz_convert("America/New_York")
        closed = (
            local.weekday() == 5
            or local.hour == 17
            or (local.weekday() == 4 and local.hour >= 17)
            or (local.weekday() == 6 and local.hour < 18)
        )
        if closed:
            return False
    return True


def session(slot):
    london = 8 <= slot.tz_convert("Europe/London").hour < 17
    ny = 8 <= slot.tz_convert("America/New_York").hour < 17
    if london and ny:
        return "London/New York"
    if london:
        return "London"
    if ny:
        return "New York"
    return "Other"


def outcome(frame, slot, reference, threshold):
    expected = pd.date_range(slot, periods=60, freq="min")
    candles = frame.reindex(expected)
    if candles.close.isna().any():
        raise ValueError(
            f"incomplete outcome: {int(candles.close.isna().sum())}/60 minutes missing"
        )
    end = float(candles.close.iat[-1])
    return int(abs(1e4 * np.log(end / reference)) > threshold), end


def settle(db, cohort, frame, now):
    key = iso(now)
    for row in db.execute(
        "SELECT * FROM radar_forecasts WHERE cohort=? AND outcome IS NULL AND resolved_at IS NULL AND due<=?",
        (cohort, key),
    ).fetchall():
        try:
            if frame is None:
                raise ValueError("minute history unavailable")
            result, price = outcome(
                frame, pd.Timestamp(row["slot"]), row["reference"], row["threshold_bps"]
            )
        except ValueError as exc:
            final = (
                key
                if now - pd.Timestamp(row["due"]) >= pd.Timedelta(hours=72)
                else None
            )
            db.execute(
                "UPDATE radar_forecasts SET failure=?,resolved_at=? WHERE cohort=? AND slot=?",
                (str(exc), final, cohort, row["slot"]),
            )
        else:
            db.execute(
                "UPDATE radar_forecasts SET outcome=?,end_price=?,resolved_at=?,failure=NULL WHERE cohort=? AND slot=?",
                (result, price, key, cohort, row["slot"]),
            )


def issue(db, artifact, fingerprint, cohort, slot, quote, frame, clock):
    price, _, features = gold_features(frame.loc[frame.index < slot])
    if slot not in features.index or not np.isfinite(features.loc[slot]).all():
        raise ValueError(
            "incomplete gold feature window (17 complete M15 bid candles required)"
        )
    reference = float(price.loc[slot])
    bps = 1.5 * float(features.at[slot, "v4"])
    upside = reference * np.expm1(bps / 1e4)
    downside = -reference * np.expm1(-bps / 1e4)
    distance = pd.Series([upside], index=[slot])
    probs = {
        k: float(v[0])
        for k, v in predict(
            artifact["parameters"], features.loc[[slot]], distance
        ).items()
    }
    now = clock()
    age = (now - pd.Timestamp(quote["at"])).total_seconds()
    if not 0 <= age <= MAX_AGE or not 0 <= (now - slot).total_seconds() <= MAX_AGE:
        raise ValueError("quote or slot expired before insert")
    if (
        not all(np.isfinite(p) and 0 <= p <= 1 for p in probs.values())
        or not np.isfinite(bps)
        or bps <= 0
    ):
        raise ValueError("nonfinite or zero threshold / invalid probability")
    quote = dict(quote, age_at_issue_seconds=age)
    db.execute(
        "INSERT INTO radar_slots VALUES(?,?,?,'issued',NULL)",
        (cohort, iso(slot), iso(now)),
    )
    db.execute(
        """INSERT INTO radar_forecasts
        (cohort,slot,model,fingerprint,issued_at,due,quote,reference,threshold_bps,threshold_usd_up,
        threshold_usd_down,predictions,candidate,session) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            cohort,
            iso(slot),
            artifact["version"],
            fingerprint,
            iso(now),
            iso(now + HOUR),
            json.dumps(quote),
            reference,
            bps,
            float(upside),
            float(downside),
            json.dumps(probs),
            int(probs["model"] >= ALERT),
            session(slot),
        ),
    )


def allowed_cohort(cohort, slot):
    local = slot.tz_convert(ZONE)
    inside = local.year == 2027 and local.month <= 6
    # Reserved validation is opt-in and isolated from routine pilot and smoke forecasts.
    return inside if cohort == "reserved" else not inside


def run_once(db, feed, artifact, fingerprint, cohort, *, issue_new=True, clock=ts):
    start = clock()
    slot = start.floor("15min")
    eligible = issue_new and in_window(slot) and allowed_cohort(cohort, slot)
    with db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute(
            "SELECT fingerprint FROM radar_cohorts WHERE cohort=?", (cohort,)
        ).fetchone()
        mismatched = db.execute(
            "SELECT 1 FROM radar_forecasts WHERE cohort=? AND fingerprint<>? LIMIT 1",
            (cohort, fingerprint),
        ).fetchone()
        if (previous and previous[0] != fingerprint) or mismatched:
            raise ValueError("frozen model differs within the forecast cohort")
        db.execute(
            "INSERT OR IGNORE INTO radar_cohorts VALUES(?,?)", (cohort, fingerprint)
        )
        if (
            eligible
            and db.execute(
                "SELECT 1 FROM radar_slots WHERE cohort=? AND slot=?",
                (cohort, iso(slot)),
            ).fetchone()
        ):
            eligible = False
        if eligible and cohort == "pilot":
            days = [
                row[0]
                for row in db.execute(
                    "SELECT DISTINCT substr(datetime(slot,'+2 hours'),1,10) FROM radar_forecasts WHERE cohort='pilot' ORDER BY 1"
                )
            ]
            eligible = len(days) < 20 or str(slot.tz_convert(ZONE).date()) in days[:20]
        if eligible and (start - slot).total_seconds() > MAX_AGE:
            db.execute(
                "INSERT INTO radar_slots VALUES(?,?,?,'missed',?)",
                (cohort, iso(slot), iso(start), "start over 90 seconds late"),
            )
            eligible = False
        if eligible and not known_open(slot):
            db.execute(
                "INSERT INTO radar_slots VALUES(?,?,?,'closed',?)",
                (
                    cohort,
                    iso(slot),
                    iso(start),
                    "known maintenance or weekend in horizon",
                ),
            )
            eligible = False
        due = db.execute(
            "SELECT 1 FROM radar_forecasts WHERE cohort=? AND resolved_at IS NULL AND due<=?",
            (cohort, iso(start)),
        ).fetchone()
        if not (eligible or due):
            return None
        frame = None
        issue_error = None
        try:
            with feed as source:
                if eligible:
                    try:
                        quote = source.quote()
                    except (RuntimeError, ValueError) as exc:
                        issue_error = str(exc)
                if due or (eligible and issue_error is None):
                    frame = source.minutes(clock().floor("min"))
                if eligible and issue_error is None:
                    issue(db, artifact, fingerprint, cohort, slot, quote, frame, clock)
        except (RuntimeError, ValueError, ImportError) as exc:
            issue_error = issue_error or str(exc)
        if eligible and issue_error is not None:
            db.execute(
                "INSERT INTO radar_slots VALUES(?,?,?,'unavailable',?)",
                (cohort, iso(slot), iso(clock()), issue_error),
            )
        if due:
            settle(db, cohort, frame, clock())
        row = db.execute(
            "SELECT * FROM radar_slots WHERE cohort=? AND slot=?", (cohort, iso(slot))
        ).fetchone()
        return dict(row) if row else None


def smoke(db, feed, artifact, fingerprint):
    now = ts()
    slot = now.floor("15min")
    if (now - slot).total_seconds() > 30:
        slot += QUARTER
    if not (in_window(slot) and known_open(slot) and allowed_cohort("smoke", slot)):
        raise ValueError("next quarter is outside the smoke-test window")
    print(f"awaiting smoke slot {slot.isoformat()}", flush=True)
    time.sleep(max(0, (slot - ts()).total_seconds() + 2))
    print(json.dumps(run_once(db, feed, artifact, fingerprint, "smoke")), flush=True)
    row = db.execute(
        "SELECT * FROM radar_forecasts WHERE cohort='smoke' AND slot=?", (iso(slot),)
    ).fetchone()
    if row is None:
        raise SystemExit("smoke forecast did not issue")
    print(json.dumps(dict(row)), flush=True)
    time.sleep(max(0, (pd.Timestamp(row["due"]) - ts()).total_seconds() + 3))
    run_once(db, feed, artifact, fingerprint, "smoke", issue_new=False)
    row = dict(
        db.execute(
            "SELECT * FROM radar_forecasts WHERE cohort='smoke' AND slot=?",
            (iso(slot),),
        ).fetchone()
    )
    print(json.dumps(row), flush=True)
    if row["outcome"] is None:
        raise SystemExit("smoke outcome unobserved")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["once", "reconcile", "report", "summary", "smoke", "review"]
    )
    parser.add_argument("--cohort", choices=MODE, default="pilot")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--broker-zone", default="Europe/Helsinki")
    parser.add_argument("--day")
    parser.add_argument("--send-research-telegram", action="store_true")
    args = parser.parse_args()
    if args.send_research_telegram and (
        args.action != "once" or args.cohort != "pilot"
    ):
        parser.error("Telegram is restricted to explicit pilot once invocation")
    artifact, fingerprint = load_frozen()
    db = open_ledger(args.root / "risk.sqlite")
    try:
        feed = BidFeed(args.broker_zone)
        if args.action == "smoke":
            smoke(db, feed, artifact, fingerprint)
            return
        from .radar_metrics import daily_report, deliver

        if args.action in ("report", "summary", "review"):
            report = daily_report(db, args.cohort, args.day, ts(), artifact)
            if args.action == "summary":
                print(report["arabic_summary"])
                return
            if args.action == "review":
                from .researcher import review_evidence

                evidence = {
                    "protocol": artifact["protocol_sha256"],
                    "model": fingerprint,
                    "purpose": "Review aggregate data quality, drift and methodological limitations.",
                    "report": report,
                }
                report = review_evidence(
                    db, f"risk/{args.cohort}/{report['day']}", evidence
                )
            print(json.dumps(report, indent=2))
        else:
            row = run_once(
                db,
                feed,
                artifact,
                fingerprint,
                args.cohort,
                issue_new=args.action == "once",
            )
            print(json.dumps(row))
            if args.send_research_telegram and row and row["status"] == "issued":
                deliver(db, args.cohort, row["slot"], ts())
            local = ts().tz_convert(ZONE)
            if local.hour == 0 and local.minute >= 15:
                day = (local - pd.Timedelta(days=1)).date().isoformat()
                report = daily_report(db, args.cohort, day, ts(), artifact)
                write_atomic(
                    args.root / "reports" / args.cohort / f"{day}.json",
                    json.dumps(report, indent=2, ensure_ascii=False).encode(),
                )
    finally:
        db.close()


if __name__ == "__main__":
    main()
