"""Calendar truth, source failures, US dates and execution eligibility."""

import json
from datetime import date, datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from connectors.market_calendar import BEA_URL, FED_URL, _fed_events, fetch_market_calendar
from execution_policy import REQUIRED_SOURCES, final_execution_decision
from operational_summary import build_summary, format_telegram_arabic_trade_card

NOW = datetime(2026, 10, 22, 13, tzinfo=timezone.utc)


def _read(url):
    if "api.stlouisfed.org" in url:
        params = parse_qs(urlparse(url).query)
        rid = int(params["release_id"][0])
        assert params["include_release_dates_with_no_data"] == ["true"]
        dates = {10: ["2026-10-14", "2026-11-10", "2026-12-10"],
                 50: ["2026-10-02", "2026-11-06", "2026-12-04"],
                 46: ["2026-10-15", "2026-11-13", "2026-12-15"]}[rid]
        return json.dumps({"count": len(dates), "release_dates": [{"release_id": rid, "date": d} for d in dates]})
    if url == BEA_URL:
        blocks = []
        for title in ("Gross Domestic Pro\r\n duct, National", "Personal Income and Outlays"):
            for d in ("20260930", "20261029", "20261223"):
                blocks.append(f"BEGIN:VEVENT\r\nSUMMARY:{title}\r\nDTSTART:{d}T123000Z\r\nEND:VEVENT")
        return "BEGIN:VCALENDAR\r\n" + "\r\n".join(blocks) + "\r\nEND:VCALENDAR"
    assert url == FED_URL
    return json.dumps({"events": [
        {"type": "Other" if title == "FOMC Meeting" else "FOMC", "title": title,
         "month": month, "days": days,
         "description": "Two-day meeting" if title == "FOMC Meeting" else ""}
        for title, month, days in (
            ("FOMC Meeting", "2026-09", "15-16"), ("FOMC Meeting", "2026-10", "28"),
            ("FOMC Press Conference", "2026-10", "28"), ("FOMC Meeting", "2026-12", "8-9"),
            ("FOMC Meeting", "", "3"),
            ("FOMC Minutes", "2026-10", "7"), ("FOMC Minutes", "2026-11", "18"),
            ("FOMC Minutes", "2026-12", "30"),
        )
    ]})


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "calendar-test-secret")


def _decision(calendar, as_of=date(2026, 10, 22)):
    sources = {s: {"status": "fresh", "observation_date": "2026-10-21", "max_age_days": 7}
               for s in REQUIRED_SOURCES}
    return final_execution_decision("BUY", .85, "proceed", sources, as_of=as_of,
                                    structure="uptrend", asset="XAU/USD",
                                    price_source="twelvedata:XAU/USD", event_calendar=calendar)


def test_live_calendar_has_explicit_scope_provenance_and_no_news_dependency():
    calendar = fetch_market_calendar(now=NOW, read=_read)
    assert calendar["status"] == "verified"
    assert calendar["events_today"] == []
    assert calendar["upcoming_events"][0]["date"] == "2026-10-27"
    assert "calendar-test-secret" not in json.dumps(calendar)
    assert _decision(calendar)["execution_allowed"] is True
    card = format_telegram_arabic_trade_card({"event_calendar": calendar, "news": {"article_count": 20}})
    assert "لا حدث اليوم ضمن التغطية المتحققة" in card
    assert "CPI, NFP, PPI, GDP, PCE, FOMC, FOMC_MINUTES" in card


@pytest.mark.parametrize("day,event", [(27, "FOMC"), (28, "FOMC"), (29, "GDP")])
def test_known_event_days_have_no_trade_permission(day, event):
    now = NOW.replace(day=day)
    calendar = fetch_market_calendar(now=now, read=_read)
    assert calendar["status"] == "verified"
    assert event in [e["event"] for e in calendar["events_today"]]
    # Deduplicate meeting day and press conference into one FOMC entry.
    assert len([e for e in calendar["events_today"] if e["event"] == "FOMC"]) <= 1
    result = _decision(calendar, as_of=now.date())
    assert result["action"] == "WAIT"
    assert "scheduled_high_impact_event_day" in result["reasons"]


@pytest.mark.parametrize("fault", ["timeout", "missing_scope", "truncated", "bad_date"])
def test_partial_or_invalid_calendar_never_becomes_no_event(fault):
    def read(url):
        if url == BEA_URL:
            if fault == "timeout":
                raise TimeoutError("URL might contain calendar-test-secret")
            text = _read(url)
            if fault == "missing_scope":
                return text.replace("Personal Income and Outlays", "Other release")
            if fault == "truncated":
                return text.replace("END:VCALENDAR", "")
            return text.replace("20261029T123000Z", "invalid")
        return _read(url)
    calendar = fetch_market_calendar(now=NOW, read=read)
    assert calendar["status"] == "unavailable"
    assert "calendar-test-secret" not in json.dumps(calendar)
    result = _decision(calendar)
    assert "event_calendar_unverified_or_stale" in result["reasons"]
    card = format_telegram_arabic_trade_card({"event_calendar": calendar})
    assert "تقويم الأحداث غير متحقق" in card
    assert "لا حدث اليوم" not in card


def test_yesterdays_verified_calendar_cannot_authorize_today():
    calendar = fetch_market_calendar(now=NOW.replace(day=21), read=_read)
    assert _decision(calendar)["execution_allowed"] is False


def test_claimed_calendar_without_source_coverage_cannot_authorize_execution():
    calendar = fetch_market_calendar(now=NOW, read=_read)
    del calendar["sources"]["FederalReserve"]
    assert _decision(calendar)["execution_allowed"] is False


def test_calendar_uses_new_york_day_around_utc_midnight():
    calendar = fetch_market_calendar(now=datetime(2026, 10, 28, 1, tzinfo=timezone.utc), read=_read)
    assert calendar["as_of_date"] == "2026-10-27"
    assert any(e["event"] == "FOMC" for e in calendar["events_today"])


def test_missing_calendar_key_blocks_execution_without_leaking_secret(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY")
    calendar = fetch_market_calendar(now=NOW, read=_read)
    assert calendar["sources"]["FRED_BLS"]["status"] == "unavailable"
    assert _decision(calendar)["execution_allowed"] is False


def test_request_urls_and_keys_never_enter_failure_artifacts():
    def read(url):
        raise RuntimeError(url)
    calendar = fetch_market_calendar(now=NOW, read=read)
    assert calendar["status"] == "unavailable"
    assert "calendar-test-secret" not in json.dumps(calendar)
    assert "api_key=" not in json.dumps(calendar)


def test_two_day_fed_meeting_can_cross_month_boundary():
    events = _fed_events(json.dumps({"events": [{
        "title": "FOMC Meeting", "type": "FOMC", "month": "2023-02", "days": "1",
        "description": "Two-day meeting, January 31-February 1",
    }]}))
    assert [e["date"] for e in events] == ["2023-01-31", "2023-02-01"]


def test_summary_preserves_run_calendar_and_wait_reason(tmp_path):
    run_dir = tmp_path / "outputs" / "2026-10-22" / "runtime_test"
    run_dir.mkdir(parents=True)
    calendar = fetch_market_calendar(now=NOW, read=_read)
    (run_dir / "finalize.json").write_text(json.dumps({"event_calendar": calendar,
        "execution_decision": {"action": "WAIT", "execution_allowed": False,
                               "reasons": ["confidence_below_60_threshold"]}}), encoding="utf-8")
    summary = build_summary(run_dir, tmp_path)
    assert summary["event_calendar"] == calendar
    assert "أقل من حد الدخول 60%" in format_telegram_arabic_trade_card(summary)
