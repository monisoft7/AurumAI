import json
from pathlib import Path

from knowledge.temporal.context import (
    TimeContext,
    CALENDAR_CALENDAR,
    CALENDAR_BUSINESS,
    VALID_CALENDAR_TYPES,
    FREQUENCY_DAILY,
    FREQUENCY_MONTHLY,
    FREQUENCY_QUARTERLY,
    VALID_FREQUENCIES,
)
from knowledge.temporal.period import (
    TimePeriod,
    PERIOD_QUARTER,
    PERIOD_ROLLING,
    PERIOD_CUSTOM,
    VALID_PERIOD_TYPES,
)
from knowledge.temporal.state import (
    TemporalState,
    SOURCE_TYPE_EVIDENCE,
    SOURCE_TYPE_KNOWLEDGE,
    SOURCE_TYPE_ECONOMIC,
    SOURCE_TYPE_DECISION,
    SOURCE_TYPE_LESSON,
    VALID_SOURCE_TYPES,
)
from knowledge.temporal.indexer import TemporalIndexer
from knowledge.temporal.repository import TemporalRepository
from knowledge.temporal.adapter import TemporalEvidenceAdapter


# ── TimeContext ──────────────────────────────────────────────────────────────

def test_time_context_defaults() -> None:
    ctx = TimeContext()
    assert ctx.calendar == CALENDAR_CALENDAR
    assert ctx.timezone == "UTC"
    assert ctx.frequency == FREQUENCY_DAILY
    assert ctx.business_calendar is None


def test_time_context_custom() -> None:
    ctx = TimeContext(
        calendar=CALENDAR_BUSINESS,
        timezone="US/Eastern",
        frequency=FREQUENCY_MONTHLY,
        business_calendar="NYSE",
    )
    assert ctx.calendar == CALENDAR_BUSINESS
    assert ctx.business_calendar == "NYSE"


def test_valid_calendar_types() -> None:
    assert CALENDAR_CALENDAR in VALID_CALENDAR_TYPES
    assert CALENDAR_BUSINESS in VALID_CALENDAR_TYPES


def test_valid_frequencies() -> None:
    assert FREQUENCY_DAILY in VALID_FREQUENCIES
    assert FREQUENCY_MONTHLY in VALID_FREQUENCIES
    assert FREQUENCY_QUARTERLY in VALID_FREQUENCIES


# ── TimePeriod ───────────────────────────────────────────────────────────────

def test_time_period_defaults() -> None:
    p = TimePeriod(
        period_id="p1",
        start_date="2020-01-01",
        end_date="2020-03-31",
    )
    assert p.period_id == "p1"
    assert p.period_type == PERIOD_CUSTOM
    assert p.inclusive_start is True
    assert p.inclusive_end is True


def test_time_period_quarter() -> None:
    p = TimePeriod(
        period_id="q1_2020",
        start_date="2020-01-01",
        end_date="2020-03-31",
        period_type=PERIOD_QUARTER,
        label="Q1 2020",
    )
    assert p.period_type == PERIOD_QUARTER
    assert p.label == "Q1 2020"


def test_valid_period_types() -> None:
    assert PERIOD_QUARTER in VALID_PERIOD_TYPES
    assert PERIOD_ROLLING in VALID_PERIOD_TYPES
    assert PERIOD_CUSTOM in VALID_PERIOD_TYPES


# ── TemporalState ────────────────────────────────────────────────────────────

def test_temporal_state_defaults() -> None:
    ts = TemporalState(
        state_id="ts1",
        date="2020-01-15",
        source_type=SOURCE_TYPE_EVIDENCE,
        source_id="ev_001",
    )
    assert ts.state_id == "ts1"
    assert ts.tags == ()
    assert ts.metadata == {}


def test_temporal_state_full() -> None:
    ts = TemporalState(
        state_id="ts2",
        date="2022-06-01",
        source_type=SOURCE_TYPE_ECONOMIC,
        source_id="st_001",
        tags=("high_inflation", "regime"),
        metadata={"inflation": 8.5},
    )
    assert SOURCE_TYPE_ECONOMIC in VALID_SOURCE_TYPES
    assert ts.tags == ("high_inflation", "regime")


def test_temporal_state_with_lesson_source() -> None:
    ts = TemporalState(
        state_id="ts3",
        date="2020-01-01",
        source_type=SOURCE_TYPE_LESSON,
        source_id="lesson_001",
    )
    assert ts.source_type in VALID_SOURCE_TYPES


# ── TemporalIndexer: Indexing ────────────────────────────────────────────────

def test_indexer_empty() -> None:
    idx = TemporalIndexer()
    assert idx.entry_count() == 0
    assert idx.date_range() is None


def test_indexer_single_entry() -> None:
    idx = TemporalIndexer()
    ts = TemporalState("ts1", "2020-01-15", SOURCE_TYPE_EVIDENCE, "ev_001")
    idx.index(ts)
    assert idx.entry_count() == 1
    assert idx.date_range() == ("2020-01-15", "2020-01-15")


def test_indexer_multiple_entries() -> None:
    idx = TemporalIndexer()
    states = [
        TemporalState("ts1", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-06-15", SOURCE_TYPE_ECONOMIC, "st_001"),
        TemporalState("ts3", "2020-12-31", SOURCE_TYPE_DECISION, "dec_001"),
    ]
    idx.index_many(states)
    assert idx.entry_count() == 3
    assert idx.date_range() == ("2020-01-01", "2020-12-31")


# ── TemporalIndexer: Query by date ───────────────────────────────────────────

def test_query_by_date_exact() -> None:
    idx = TemporalIndexer()
    idx.index_many([
        TemporalState("ts1", "2020-01-15", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-01-15", SOURCE_TYPE_ECONOMIC, "st_001"),
        TemporalState("ts3", "2020-06-01", SOURCE_TYPE_EVIDENCE, "ev_002"),
    ])
    results = idx.query_by_date("2020-01-15")
    assert len(results) == 2
    ids = {s.state_id for s in results}
    assert ids == {"ts1", "ts2"}


def test_query_by_date_no_match() -> None:
    idx = TemporalIndexer()
    idx.index(TemporalState("ts1", "2020-01-15", SOURCE_TYPE_EVIDENCE, "ev_001"))
    results = idx.query_by_date("2020-06-01")
    assert results == []


# ── TemporalIndexer: Query by period ─────────────────────────────────────────

def test_query_by_period_inclusive() -> None:
    idx = TemporalIndexer()
    idx.index_many([
        TemporalState("ts1", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-03-15", SOURCE_TYPE_ECONOMIC, "st_001"),
        TemporalState("ts3", "2020-06-30", SOURCE_TYPE_DECISION, "dec_001"),
    ])
    period = TimePeriod("q1", "2020-01-01", "2020-03-31", PERIOD_QUARTER)
    results = idx.query_by_period(period)
    assert len(results) == 2
    ids = {s.state_id for s in results}
    assert ids == {"ts1", "ts2"}


def test_query_by_period_exclusive() -> None:
    idx = TemporalIndexer()
    idx.index_many([
        TemporalState("ts1", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-03-31", SOURCE_TYPE_ECONOMIC, "st_001"),
    ])
    period = TimePeriod(
        "q1_excl", "2020-01-01", "2020-03-31",
        inclusive_start=False, inclusive_end=False,
    )
    results = idx.query_by_period(period)
    assert len(results) == 0


def test_query_by_period_empty() -> None:
    idx = TemporalIndexer()
    period = TimePeriod("empty", "2020-01-01", "2020-03-31")
    results = idx.query_by_period(period)
    assert results == []


# ── TemporalIndexer: Rolling window ──────────────────────────────────────────

def test_rolling_window() -> None:
    idx = TemporalIndexer()
    idx.index_many([
        TemporalState("ts1", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-01-10", SOURCE_TYPE_EVIDENCE, "ev_002"),
        TemporalState("ts3", "2020-01-25", SOURCE_TYPE_EVIDENCE, "ev_003"),
        TemporalState("ts4", "2020-02-15", SOURCE_TYPE_EVIDENCE, "ev_004"),
    ])
    results = idx.rolling_window("2020-01-31", 21)
    dates = {s.date for s in results}
    assert "2020-01-10" in dates
    assert "2020-01-25" in dates
    assert "2020-01-01" not in dates
    assert "2020-02-15" not in dates


def test_rolling_window_empty() -> None:
    idx = TemporalIndexer()
    results = idx.rolling_window("2020-01-31", 20)
    assert results == []


# ── TemporalIndexer: Nearest date ────────────────────────────────────────────

def test_nearest_date_exact() -> None:
    idx = TemporalIndexer()
    idx.index_many([
        TemporalState("ts1", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-06-15", SOURCE_TYPE_EVIDENCE, "ev_002"),
    ])
    results = idx.nearest_date("2020-01-01")
    assert len(results) == 1
    assert results[0].state_id == "ts1"


def test_nearest_date_between() -> None:
    idx = TemporalIndexer()
    idx.index_many([
        TemporalState("ts1", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-12-31", SOURCE_TYPE_EVIDENCE, "ev_002"),
    ])
    results = idx.nearest_date("2020-06-15")
    assert len(results) == 1
    assert results[0].state_id == "ts1"


def test_nearest_date_before() -> None:
    idx = TemporalIndexer()
    idx.index_many([
        TemporalState("ts1", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-06-15", SOURCE_TYPE_EVIDENCE, "ev_002"),
        TemporalState("ts3", "2020-12-31", SOURCE_TYPE_EVIDENCE, "ev_003"),
    ])
    results = idx.nearest_date("2020-03-01", direction="before")
    assert len(results) == 1
    assert results[0].state_id == "ts1"


def test_nearest_date_after() -> None:
    idx = TemporalIndexer()
    idx.index_many([
        TemporalState("ts1", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-06-15", SOURCE_TYPE_EVIDENCE, "ev_002"),
    ])
    results = idx.nearest_date("2020-03-01", direction="after")
    assert len(results) == 1
    assert results[0].state_id == "ts2"


def test_nearest_date_empty() -> None:
    idx = TemporalIndexer()
    results = idx.nearest_date("2020-06-15")
    assert results == []


def test_nearest_date_tie() -> None:
    idx = TemporalIndexer()
    idx.index_many([
        TemporalState("ts1", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-12-31", SOURCE_TYPE_EVIDENCE, "ev_002"),
    ])
    results = idx.nearest_date("2020-07-01")
    assert len(results) == 1
    assert results[0].state_id in ("ts1", "ts2")


# ── TemporalIndexer: Source type counts ──────────────────────────────────────

def test_source_type_count() -> None:
    idx = TemporalIndexer()
    idx.index_many([
        TemporalState("ts1", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_002"),
        TemporalState("ts3", "2020-01-01", SOURCE_TYPE_ECONOMIC, "st_001"),
    ])
    assert idx.source_type_count(SOURCE_TYPE_EVIDENCE) == 2
    assert idx.source_type_count(SOURCE_TYPE_ECONOMIC) == 1
    assert idx.source_type_count(SOURCE_TYPE_DECISION) == 0


# ── TemporalIndexer: Clear ───────────────────────────────────────────────────

def test_indexer_clear() -> None:
    idx = TemporalIndexer()
    idx.index(TemporalState("ts1", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"))
    assert idx.entry_count() == 1
    idx.clear()
    assert idx.entry_count() == 0
    assert idx.date_range() is None


# ── TemporalIndexer: Reproducibility ─────────────────────────────────────────

def test_reproducible_query() -> None:
    idx = TemporalIndexer()
    states = [
        TemporalState("ts_b", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_002"),
        TemporalState("ts_a", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts_c", "2020-06-01", SOURCE_TYPE_ECONOMIC, "st_001"),
    ]
    idx.index_many(states)

    r1 = idx.query_by_date("2020-01-01")
    r2 = idx.query_by_date("2020-01-01")
    assert [s.state_id for s in r1] == [s.state_id for s in r2]

    p = TimePeriod("p1", "2020-01-01", "2020-12-31")
    r3 = idx.query_by_period(p)
    r4 = idx.query_by_period(p)
    assert [s.state_id for s in r3] == [s.state_id for s in r4]


# ── TemporalIndexer: Context property ────────────────────────────────────────

def test_indexer_context() -> None:
    ctx = TimeContext(timezone="US/Eastern")
    idx = TemporalIndexer(ctx)
    assert idx.context.timezone == "US/Eastern"


# ── TemporalRepository: Save/Load Index ──────────────────────────────────────

def test_repository_save_and_load_index(tmp_path: Path) -> None:
    idx = TemporalIndexer(TimeContext(timezone="US/Eastern"))
    idx.index_many([
        TemporalState("ts1", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-06-15", SOURCE_TYPE_ECONOMIC, "st_001"),
    ])
    path = tmp_path / "index.json"
    TemporalRepository().save_index(idx, path)
    assert path.exists()

    loaded = TemporalRepository().load_index(path)
    assert loaded.context.timezone == "US/Eastern"
    assert loaded.entry_count() == 2
    assert loaded.query_by_date("2020-01-01")[0].state_id == "ts1"


def test_repository_index_roundtrip_preserves_tags(tmp_path: Path) -> None:
    idx = TemporalIndexer()
    idx.index(TemporalState(
        "ts1", "2020-01-01", SOURCE_TYPE_KNOWLEDGE, "know_001",
        tags=("important", "verified"),
        metadata={"source": "test"},
    ))
    path = tmp_path / "index_tags.json"
    TemporalRepository().save_index(idx, path)
    loaded = TemporalRepository().load_index(path)
    state = loaded.query_by_date("2020-01-01")[0]
    assert state.tags == ("important", "verified")
    assert state.metadata["source"] == "test"


# ── TemporalRepository: Save/Load Period ─────────────────────────────────────

def test_repository_save_and_load_period(tmp_path: Path) -> None:
    period = TimePeriod(
        period_id="q1_2020",
        start_date="2020-01-01",
        end_date="2020-03-31",
        period_type=PERIOD_QUARTER,
        label="Q1 2020",
        metadata={"source": "calendar"},
    )
    path = tmp_path / "period.json"
    TemporalRepository().save_period(period, path)
    assert path.exists()

    loaded = TemporalRepository().load_period(path)
    assert loaded.period_id == "q1_2020"
    assert loaded.start_date == "2020-01-01"
    assert loaded.period_type == PERIOD_QUARTER
    assert loaded.metadata["source"] == "calendar"


# ── TemporalRepository: Empty Index ──────────────────────────────────────────

def test_repository_save_and_load_empty_index(tmp_path: Path) -> None:
    idx = TemporalIndexer()
    path = tmp_path / "empty_index.json"
    TemporalRepository().save_index(idx, path)
    loaded = TemporalRepository().load_index(path)
    assert loaded.entry_count() == 0


# ── TemporalEvidenceAdapter ──────────────────────────────────────────────────

def test_adapter_state_to_evidence() -> None:
    ts = TemporalState(
        "ts1", "2020-06-15", SOURCE_TYPE_ECONOMIC, "st_001",
        tags=("regime",), metadata={"inflation": 5.0},
    )
    ev = TemporalEvidenceAdapter().state_to_evidence(ts)
    assert ev.evidence_id == "tmp_ts1"
    assert ev.event_type == "TEMPORAL"
    assert ev.condition["source_type"] == SOURCE_TYPE_ECONOMIC
    assert ev.condition["date"] == "2020-06-15"
    assert ev.metadata["source_id"] == "st_001"
    assert ev.metadata["tags"] == ["regime"]


def test_adapter_indexer_to_evidence_respects_max(tmp_path: Path) -> None:
    idx = TemporalIndexer()
    for i in range(10):
        idx.index(TemporalState(
            f"ts{i}", f"2020-01-{i+1:02d}", SOURCE_TYPE_EVIDENCE, f"ev_{i:03d}",
        ))
    result = TemporalEvidenceAdapter().indexer_to_evidence(idx, max_entries=3)
    assert len(result) == 3


def test_adapter_query_to_evidence() -> None:
    states = [
        TemporalState("ts1", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-06-15", SOURCE_TYPE_ECONOMIC, "st_001"),
    ]
    result = TemporalEvidenceAdapter().query_to_evidence(states)
    assert len(result) == 2
    assert result[0].event_type == "TEMPORAL"
    assert result[1].event_type == "TEMPORAL"


def test_adapter_period_summary_evidence() -> None:
    period = TimePeriod("q1", "2020-01-01", "2020-03-31", PERIOD_QUARTER)
    states = [
        TemporalState("ts1", "2020-01-15", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-02-15", SOURCE_TYPE_ECONOMIC, "st_001"),
    ]
    ev = TemporalEvidenceAdapter.period_summary_evidence(period, states)
    assert ev.event_type == "TEMPORAL_PERIOD"
    assert ev.sample_count == 2
    assert ev.metadata["start_date"] == "2020-01-01"
    assert ev.metadata["source_type_breakdown"][SOURCE_TYPE_EVIDENCE] == 1
    assert ev.metadata["source_type_breakdown"][SOURCE_TYPE_ECONOMIC] == 1


def test_adapter_date_range_evidence_with_data() -> None:
    idx = TemporalIndexer()
    idx.index(TemporalState("ts1", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"))
    idx.index(TemporalState("ts2", "2020-12-31", SOURCE_TYPE_EVIDENCE, "ev_002"))
    ev = TemporalEvidenceAdapter.date_range_evidence(idx)
    assert ev.event_type == "TEMPORAL_RANGE"
    assert ev.metadata["earliest_date"] == "2020-01-01"
    assert ev.metadata["latest_date"] == "2020-12-31"
    assert ev.metadata["entry_count"] == 2


def test_adapter_date_range_evidence_empty() -> None:
    idx = TemporalIndexer()
    ev = TemporalEvidenceAdapter.date_range_evidence(idx)
    assert ev.evidence_id == "tmp_empty_range"
    assert ev.sample_count == 0


# ── Integration: Index + Query + Adapter ─────────────────────────────────────

def test_integration_index_query_adapter() -> None:
    idx = TemporalIndexer()
    idx.index_many([
        TemporalState("ts1", "2020-01-15", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-03-20", SOURCE_TYPE_ECONOMIC, "st_001"),
        TemporalState("ts3", "2020-06-10", SOURCE_TYPE_DECISION, "dec_001"),
    ])

    q1 = TimePeriod("q1", "2020-01-01", "2020-03-31", PERIOD_QUARTER)
    q1_states = idx.query_by_period(q1)
    assert len(q1_states) == 2

    ev_list = TemporalEvidenceAdapter().query_to_evidence(q1_states)
    assert len(ev_list) == 2

    summary = TemporalEvidenceAdapter.period_summary_evidence(q1, q1_states)
    assert summary.sample_count == 2
    assert summary.metadata["source_type_breakdown"][SOURCE_TYPE_EVIDENCE] == 1
    assert summary.metadata["source_type_breakdown"][SOURCE_TYPE_ECONOMIC] == 1


def test_integration_rolling_to_evidence() -> None:
    idx = TemporalIndexer()
    idx.index_many([
        TemporalState("ts1", "2020-01-01", SOURCE_TYPE_EVIDENCE, "ev_001"),
        TemporalState("ts2", "2020-01-10", SOURCE_TYPE_KNOWLEDGE, "know_001"),
        TemporalState("ts3", "2020-01-20", SOURCE_TYPE_ECONOMIC, "st_001"),
        TemporalState("ts4", "2020-02-15", SOURCE_TYPE_LESSON, "lesson_001"),
    ])

    window = idx.rolling_window("2020-01-25", 15)
    assert len(window) == 2

    ev_list = TemporalEvidenceAdapter().query_to_evidence(window)
    assert all(e.condition["source_type"] in (
        SOURCE_TYPE_KNOWLEDGE, SOURCE_TYPE_ECONOMIC,
    ) for e in ev_list)
