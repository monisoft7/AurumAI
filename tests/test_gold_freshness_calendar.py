"""A successful HTTP refresh cannot authorize stale or unfinished daily bars."""

from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from connectors.gold_freshness import assess_gold_freshness
from execution_policy import REQUIRED_SOURCES, final_execution_decision
import run as runtime


@pytest.mark.parametrize(("as_of", "observed", "expected", "status"), [
    ("2026-10-22", "2026-10-21", "2026-10-21", "ok"),
    ("2026-10-22", "2026-10-20", "2026-10-21", "stale"),
    ("2026-10-22", "2026-10-22", "2026-10-21", "unavailable"),
    ("2026-10-26", "2026-10-23", "2026-10-23", "ok"),
    ("2026-10-26", "2026-10-22", "2026-10-23", "stale"),
    ("2026-10-25", "2026-10-23", "2026-10-23", "ok"),
    ("2026-12-26", "2026-12-24", "2026-12-25", "stale"),
])
def test_completed_bar_contract(as_of, observed, expected, status):
    result = assess_gold_freshness({"status": "ok", "observation_date": observed}, date.fromisoformat(as_of))
    assert result["status"] == status
    assert result["expected_observation_date"] == expected


def test_successful_download_without_expected_bar_is_not_execution_fresh(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 22, 13, tzinfo=timezone.utc)

    monkeypatch.setattr(runtime.datetime, "datetime", Clock)
    monkeypatch.setattr("connectors.gold_data_provider.refresh_gold_data", lambda *a, **kw: SimpleNamespace(
        status="ok", rows_before=10, rows_after=10, rows_added=0,
        last_date_before="2026-10-20", last_date_after="2026-10-20",
        timestamp="2026-10-22T13:00:00+00:00", message="download succeeded", source="twelvedata:XAU/USD",
    ))
    result = runtime._refresh_gold_before_run({"gold_path": "unused.csv", "gold_provider": "twelvedata_spot"})
    assert result["status"] == "stale"
    assert result["max_age_days"] == 1


def test_legacy_seven_day_gold_tolerance_cannot_bypass_final_gate():
    sources = {s: {"status": "ok", "observation_date": "2026-10-21", "max_age_days": 7}
               for s in REQUIRED_SOURCES}
    sources["Gold"]["observation_date"] = "2026-10-20"
    result = final_execution_decision("BUY", .95, "proceed", sources,
                                      as_of=date(2026, 10, 22), structure="uptrend")
    assert result["execution_allowed"] is False
    assert "Gold:stale" in result["unavailable_sources"]
