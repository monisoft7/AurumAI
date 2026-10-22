"""Historical knowledge must not contain an episode's future outcome."""

from datetime import date

from historical_validation.snapshot import _outcome_available_before, asof_knowledge_records


def test_current_episode_is_excluded_from_asof_knowledge():
    records = asof_knowledge_records(date(2015, 6, 1))
    assert all(
        "CPI_GOLD_2015-06-01" not in record["source_lesson_ids"]
        for record in records
    )


def test_legacy_episode_remains_quarantined_until_outcomes_mature():
    during_quarantine = asof_knowledge_records(date(2015, 6, 30))
    after_quarantine = asof_knowledge_records(date(2015, 10, 1))
    assert all(
        "CPI_GOLD_2015-06-01" not in record["source_lesson_ids"]
        for record in during_quarantine
    )
    assert any(
        "CPI_GOLD_2015-06-01" in record["source_lesson_ids"]
        for record in after_quarantine
    )


def test_explicit_release_and_outcome_times_control_availability():
    row = {
        "event_date": "2026-09-01",
        "release_timestamp": "2026-10-15T08:30:00",
        "outcome_available_at_1d": "2026-10-16T21:00:00",
    }
    assert not _outcome_available_before(row, 1, date(2026, 10, 16))
    assert _outcome_available_before(row, 1, date(2026, 10, 17))
    assert not _outcome_available_before(row, 5, date(2026, 10, 30))
