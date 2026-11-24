"""Transactional local paper journal. First-seen bars and issued decisions are immutable."""
import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta

from .market import Bar, SOURCE, STEP
from .scoring import metrics
from .strategy import HOUR, Plan, activation, decide, evaluate


def fresh_plan(plan, quote, issued):
    if plan.entry is None:
        return plan
    if not quote or not timedelta(0) <= issued - quote[1] <= timedelta(seconds=90):
        return Plan("WAIT", plan.regime, "current spot quote missing or older than 90 seconds")
    sign = 1 if plan.action.startswith("BUY ") else -1
    distance = (plan.entry - quote[0]) * sign
    kind = plan.action.split()[-1]
    if kind == "NOW" and abs(quote[0] - plan.entry) > 0.1 * abs(plan.entry - plan.stop):
        return Plan("WAIT", plan.regime, "market entry moved beyond tolerance")
    if (kind == "LIMIT" and distance >= 0) or (kind == "STOP" and distance <= 0):
        return Plan("WAIT", plan.regime, "entry already reached at issuance")
    return plan


def preview(plan, quote, issued):
    if plan.entry is None:
        return None
    reasons = {"half ATR pullback": "تصحيح بمقدار نصف متوسط المدى الحقيقي",
               "fade nearest range boundary": "ارتداد من أقرب طرف للنطاق",
               "break of 16-bar extreme": "اختراق حد آخر 16 شمعة"}
    return (f"محاكاة داخلية | XAU/USD | {plan.action}\n"
            f"سعر مرجعي {quote[0]:.2f} | {SOURCE} | {quote[1].isoformat()}\n"
            f"دخول {plan.entry:.2f} | وقف {plan.stop:.2f} | هدف {plan.target:.2f} | عائد/مخاطرة 1.50 قبل التكلفة\n"
            f"صفقة لحظية | {reasons.get(plan.reason, plan.reason)}\n"
            f"تفعيل {activation(issued).isoformat()} | إلغاء الأمر غير المنفذ عند {(activation(issued)+HOUR).isoformat()} | إغلاق بعد أربع ساعات من التعبئة")


def record(path, issued, bars, quote, legacy=None, errors=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS bars (start TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS decisions (slot TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS outcomes (slot TEXT PRIMARY KEY, status TEXT NOT NULL, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS legacy (run TEXT PRIMARY KEY, slot TEXT NOT NULL, payload TEXT NOT NULL)")
            slot = issued.replace(minute=issued.minute // 15 * 15, second=0, microsecond=0).isoformat()
            if legacy:
                db.execute("INSERT OR IGNORE INTO legacy VALUES (?,?,?)", (legacy["run"], slot, json.dumps(legacy)))
            db.executemany("INSERT OR IGNORE INTO bars VALUES (?,?)",
                           [(b.start.isoformat(), json.dumps(b.snapshot())) for b in bars if b.start + STEP <= issued])

            def history(query, params):
                result = []
                for (raw,) in db.execute(query, params):
                    row = json.loads(raw)
                    row["start"] = datetime.fromisoformat(row["start"])
                    result.append(Bar(**row))
                return result

            for key, raw in db.execute("SELECT d.slot,d.payload FROM decisions d JOIN outcomes o ON d.slot=o.slot WHERE o.status='pending'").fetchall():
                old = json.loads(raw)
                at = datetime.fromisoformat(old["issued"])
                series = history("SELECT payload FROM bars WHERE start>=? AND start<=? ORDER BY start LIMIT 22",
                                 (activation(at).isoformat(), (issued-STEP).isoformat()))
                result = evaluate(Plan(**old["plan"]), at, series)
                if result["status"] == "pending" and issued >= activation(at) + 5*HOUR + STEP:
                    result["status"] = "unobserved_gap"
                db.execute("UPDATE outcomes SET status=?,payload=? WHERE slot=?",
                           (result["status"], json.dumps(result), key))
            existing = db.execute("SELECT payload FROM decisions WHERE slot=?", (slot,)).fetchone()
            if existing:
                return json.loads(existing[0])
            latest = history("SELECT payload FROM bars WHERE start<=? ORDER BY start DESC LIMIT 33",
                             ((issued-STEP).isoformat(),))[::-1]
            candidate = decide(latest, issued)
            plan = fresh_plan(candidate, quote, issued)
            if plan.entry is not None and (issued.weekday() >= 5 or not 6 <= issued.hour < 16):
                plan = Plan("WAIT", plan.regime, "outside weekday research session 06-16 UTC")
            if plan.entry is not None and db.execute("SELECT 1 FROM outcomes WHERE status='pending' LIMIT 1").fetchone():
                plan = Plan("WAIT", plan.regime, "previous paper order still open")
            if errors:
                plan = Plan("WAIT", plan.regime, "provider unavailable")
            payload = {
                "issued": issued.isoformat(), "symbol": "XAU/USD", "source": SOURCE, "policy": "combined-v1",
                "plan": asdict(plan), "candidate": asdict(candidate), "public_action": "WAIT",
                "quote": {"price": quote[0], "at": quote[1].isoformat()} if quote else None,
                "bar": latest[-1].snapshot() if latest else None,
                "active_from": activation(issued).isoformat(), "entry_expires": (activation(issued)+HOUR).isoformat(),
                "errors": list(errors), "internal_arabic_preview": preview(plan, quote, issued),
            }
            db.execute("INSERT INTO decisions VALUES (?,?)", (slot, json.dumps(payload, ensure_ascii=False)))
            if plan.entry is not None:
                initial = evaluate(plan, issued, [])
                db.execute("INSERT INTO outcomes VALUES (?,?,?)", (slot, "pending", json.dumps(initial)))
            return payload
    finally:
        db.close()

def summarize(path):
    """Read a consistent snapshot without creating or modifying the journal."""
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute("SELECT d.payload,o.payload FROM decisions d LEFT JOIN outcomes o "
                          "ON d.slot=o.slot ORDER BY d.slot").fetchall()
    groups = {}
    outcomes = []
    for decision_json, outcome_json in rows:
        decision = json.loads(decision_json)
        if outcome_json:
            outcome = json.loads(outcome_json)
            plan = decision["plan"]
            name = f"{plan['regime']} / {plan['reason']}"
            groups.setdefault(name, []).append(outcome)
            outcomes.append(outcome)
    return {"all": metrics(outcomes, len(rows)),
            "strategy_regime": {k: metrics(v, 0) for k, v in groups.items()}}
