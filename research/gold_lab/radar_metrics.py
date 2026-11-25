"""Research performance summaries and explicitly armed Telegram delivery."""

from collections import Counter
import json
from datetime import timedelta

import pandas as pd

from .radar import HOUR, QUARTER, allowed_cohort, known_open
from .radar_model import REFERENCES, bootstrap
from .shadow import ZONE, send_report


def local_date(text):
    return pd.Timestamp(text).tz_convert(ZONE).date()


def summarize(rows):
    settled = [r for r in rows if r["outcome"] is not None]
    n = len(settled)
    result = {
        "issued": len(rows),
        "settled": n,
        "alert_candidates": sum(r["candidate"] for r in rows),
        "rejected_outcome": sum(
            r["resolved_at"] is not None and r["outcome"] is None for r in rows
        ),
    }
    if not n:
        return result
    y = pd.Series(
        [r["outcome"] for r in settled],
        index=pd.DatetimeIndex(
            [pd.Timestamp(r["slot"]).tz_convert(ZONE) for r in settled]
        ),
    )
    p = pd.DataFrame([json.loads(r["predictions"]) for r in settled], index=y.index)
    errors = p.sub(y, axis=0) ** 2
    raw = errors.mean()
    alerts = p.model >= 0.60
    tp = int((alerts & y.eq(1)).sum())
    fp = int((alerts & y.eq(0)).sum())
    positives = int(y.sum())

    def ratio(a, b):
        return float(a / b) if b else None

    result.update(
        {
            "event_rate": float(y.mean()),
            "events": positives,
            "alert_candidates_settled": int(alerts.sum()),
            "precision": ratio(tp, tp + fp),
            "recall": ratio(tp, positives),
            "false_alarm_rate": ratio(fp, n - positives),
            "mean_prediction": float(p.model.mean()),
            "calibration_bias": float(p.model.mean() - y.mean()),
            "brier": raw.to_dict(),
            "brier_skill": {
                k: 1 - raw.model / raw[k] if raw[k] > 0 else None for k in REFERENCES
            },
            "calibration": [
                {
                    "bin": str(name),
                    "n": len(block),
                    "mean": float(block.p.mean()),
                    "observed": float(block.y.mean()),
                }
                for name, block in pd.DataFrame({"p": p.model, "y": y}).groupby(
                    pd.cut(p.model, [0, 0.2, 0.4, 0.6, 0.8, 1], include_lowest=True),
                    observed=True,
                )
            ],
        }
    )
    result["days"] = len(y.index.normalize().unique())
    # Single-day and sparse reports expose point estimates only.
    if result["days"] >= 10:
        result["paired_daily_bounds"] = {
            k: bootstrap(errors[k] - errors.model, 4) for k in REFERENCES
        }
    return result


def coverage(first_slot, last, now, cohort):
    expected = []
    for day in pd.date_range(first_slot.tz_convert(ZONE).date(), last, freq="B", tz=ZONE):
        slots = pd.date_range(
            day + pd.Timedelta(hours=9), day + pd.Timedelta(hours=23), freq=QUARTER
        )
        expected.extend(
            s.isoformat()
            for s in slots.tz_convert("UTC")
            if first_slot <= s
            and s + pd.Timedelta(seconds=90) <= now
            and allowed_cohort(cohort, s)
            and known_open(s)
        )
    return set(expected)


def daily_report(db, cohort, day, now, artifact):
    day = pd.Timestamp(day).date() if day is not None else now.tz_convert(ZONE).date()
    stop = pd.Timestamp(day + timedelta(days=1), tz=ZONE).tz_convert("UTC").isoformat()
    rows = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM radar_forecasts WHERE cohort=? AND slot<? ORDER BY slot",
            (cohort, stop),
        )
    ]
    slots = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM radar_slots WHERE cohort=? AND slot<? ORDER BY slot",
            (cohort, stop),
        )
    ]
    selected = [r for r in rows if local_date(r["slot"]) == day]
    day_slots = [r for r in slots if local_date(r["slot"]) == day]
    all_days = list(dict.fromkeys(local_date(r["slot"]) for r in rows))
    last = all_days[-1] if len(all_days) >= 20 and cohort == "pilot" else day
    overall_planned = (
        coverage(pd.Timestamp(slots[0]["slot"]), last, now, cohort)
        if slots and cohort != "smoke"
        else set()
    )
    planned = {slot for slot in overall_planned if local_date(slot) == day}
    daily = summarize(selected)
    total = summarize(rows)
    resolved = total["settled"]
    fully_aged = sum(
        pd.Timestamp(r["due"]) + pd.Timedelta(hours=72) <= now for r in rows
    )
    fully_aged_ok = sum(
        r["outcome"] is not None
        and pd.Timestamp(r["due"]) + pd.Timedelta(hours=72) <= now
        for r in rows
    )
    coverage_rate = (
        len(overall_planned & {r["slot"] for r in rows}) / len(overall_planned)
        if overall_planned
        else None
    )
    maturity = fully_aged_ok / fully_aged if fully_aged else None
    recent = summarize([r for r in rows if local_date(r["slot"]) in all_days[-7:]])
    drift = []
    if recent["settled"] >= 100:
        params = artifact["parameters"]
        if abs(recent["event_rate"] - params["incidence"]) >= 0.10:
            drift.append("event incidence")
        if abs(recent["mean_prediction"] - params["mean_prediction"]) >= 0.10:
            drift.append("forecast level")
        if (
            recent["brier_skill"]["threshold_and_hour"] is not None
            and recent["brier_skill"]["threshold_and_hour"] < 0
        ):
            drift.append("lower skill vs threshold and hour")
    selected_bounds = total.get("paired_daily_bounds", {})
    stats = bool(
        resolved >= 500
        and total["events"] >= 30
        and total["alert_candidates_settled"] >= 20
        and abs(total["calibration_bias"]) <= 0.05
        and total["false_alarm_rate"] is not None
        and total["false_alarm_rate"] <= 0.20
        and len(selected_bounds) == 4
        and all(v["lower_corrected"] > 0 for v in selected_bounds.values())
    )
    min_days = {"pilot": 20, "reserved": 60}.get(cohort)
    full_window = (
        min_days is not None
        and len(all_days) >= min_days
        and all_days[-1] < now.tz_convert(ZONE).date()
    )
    recovery_done = fully_aged == len(rows)
    delivery = dict(
        Counter(
            r[0]
            for r in db.execute(
                "SELECT result FROM radar_delivery WHERE cohort=? AND substr(datetime(attempted_at,'+2 hours'),1,10)=?",
                (cohort, str(day)),
            )
        )
    )
    return {
        "day": str(day),
        "cohort": cohort,
        "issue_days": len(all_days),
        "required_issue_days": min_days,
        "evaluation_complete": bool(full_window and recovery_done),
        "expected_slots_today": len(planned),
        "missing_invocations_today": len(planned - {r["slot"] for r in day_slots}),
        "issue_failures": dict(Counter(r["reason"] for r in day_slots if r["reason"])),
        "unobserved_outcomes_today": dict(
            Counter(r["failure"] for r in selected if r["failure"])
        ),
        "recorded_days": len({local_date(r["slot"]) for r in slots}),
        "overall_expected_slots": len(overall_planned),
        "issue_coverage": coverage_rate,
        "resolved_rate_after_72h": maturity,
        "operations_pass": bool(
            full_window
            and recovery_done
            and coverage_rate is not None
            and coverage_rate >= 0.9
            and maturity is not None
            and maturity >= 0.95
        ),
        "statistical_indication": stats if full_window and recovery_done else None,
        "daily": daily,
        "overall": total,
        "by_session": {
            name: summarize([r for r in selected if r["session"] == name])
            for name in sorted({r["session"] for r in selected})
        },
        "overall_by_session": {
            name: summarize([r for r in rows if r["session"] == name])
            for name in sorted({r["session"] for r in rows})
        },
        "drift_last_7_issue_days": drift,
        "drift_sample": recent["settled"],
        "delivery": delivery,
        "arabic_summary": f"رادار مخاطر الذهب | {day}\nتوقعات {daily['issued']} · محسومة {daily['settled']} · مرشحة للتنبيه {daily['alert_candidates']}\nمواضع تعذر إصدارها {sum(r['status'] in ('missed', 'unavailable') for r in day_slots)} · مواعيد بلا تشغيل {len(planned - {r['slot'] for r in day_slots})}",
    }


def alert_text(row):
    issued = pd.Timestamp(row["issued_at"]).tz_convert(ZONE)
    endpoint = (pd.Timestamp(row["slot"]) + HOUR).tz_convert(ZONE)
    p = json.loads(row["predictions"])["model"]
    return (
        f"تنبيه بحثي لمخاطر حركة الذهب\n"
        f"التوقع {issued:%Y-%m-%d %H:%M:%S} طرابلس · التقييم عند {endpoint:%H:%M} (نافذة ساعة من إغلاق الشمعة)\n"
        f"سعر Bid المرجعي {row['reference']:.2f} دولار للأونصة\n"
        f"الحدث هو تجاوز التغير المطلق {row['threshold_bps']:.2f} نقطة أساس عند نهاية النافذة، "
        f"نحو {row['threshold_usd_up']:.2f} دولار صعودًا أو {row['threshold_usd_down']:.2f} هبوطًا.\n"
        f"تقدير النموذج {p:.0%} · غير معاير ميدانيًا · الاتجاه غير مؤكد"
    )


def deliver(db, cohort, slot, now):
    # Log the attempt before external I/O. Failed/ambiguous delivery is not retried.
    at = now.isoformat()
    with db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT * FROM radar_forecasts WHERE cohort=? AND slot=?", (cohort, slot)
        ).fetchone()
        if (
            not row
            or not row["candidate"]
            or now - pd.Timestamp(row["issued_at"]) > pd.Timedelta(seconds=90)
        ):
            return
        if db.execute(
            "SELECT 1 FROM radar_delivery WHERE (cohort=? AND slot=?) OR attempted_at>?",
            (cohort, slot, (now - HOUR).isoformat()),
        ).fetchone():
            return
        db.execute(
            "INSERT INTO radar_delivery VALUES(?,?,?,'attempted')", (at, cohort, slot)
        )
    status = "sent"
    try:
        send_report(alert_text(row))
    except (RuntimeError, ValueError):
        status = "failed or unconfirmed"
    with db:
        db.execute(
            "UPDATE radar_delivery SET result=? WHERE attempted_at=?", (status, at)
        )
