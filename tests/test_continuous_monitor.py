# tests/test_continuous_monitor.py

from __future__ import annotations

import datetime
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from pre_market.contracts import OvernightPriceChange


def _load_monitor():
    import sys

    spec = importlib.util.spec_from_file_location(
        "continuous_monitor",
        Path(__file__).resolve().parents[1] / "scripts" / "continuous_monitor.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MON = _load_monitor()

NOW = datetime.datetime(2026, 8, 4, 12, 35, tzinfo=datetime.timezone.utc)


def _now() -> datetime.datetime:
    return NOW


def _write_calendar(path: Path, rows: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "reference_period,release_date,release_time,timezone,release_timestamp\n"
    )
    path.write_text(header + "".join(rows), encoding="utf-8")
    return path


def _release_source(tmp_path: Path, timestamp: str) -> MON.ReleaseCalendarSource:
    csv = _write_calendar(
        tmp_path / "cpi.csv",
        [
            f"2026-08-01,{timestamp.split(' ')[0]},{timestamp.split(' ')[1]},"
            f"US/Eastern,{timestamp}\n",
        ],
    )
    return MON.ReleaseCalendarSource("CPI", csv)


def _market_source(fetcher, bucket_seconds: int = 3600) -> MON.MarketMovementSource:
    return MON.MarketMovementSource(
        instrument="XAU/USD", bucket_seconds=bucket_seconds, fetcher=fetcher
    )


def _news_article(title: str, url: str = "https://news.example/a") -> SimpleNamespace:
    return SimpleNamespace(
        title=title,
        url=url,
        published="2026-08-04T12:00:00+00:00",
        topics=(),
    )


class _FakeRunner:
    def __init__(self, returncode: int = 0, dry_run: bool = False) -> None:
        self.calls: list[str] = []
        self.returncode = returncode
        self._dry_run = dry_run

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    def run(self, trigger_label: str) -> tuple[int, None]:
        self.calls.append(trigger_label)
        return self.returncode, None


def _monitor(tmp_path: Path, sources, runner=None, config=None) -> MON.ContinuousMonitor:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    ledger = MON.Ledger(state_dir / "ledger.jsonl")
    state = MON.StateStore(state_dir / "state.json")
    cfg = dict(MON.DEFAULT_CONFIG)
    if config:
        cfg.update(config)
    return MON.ContinuousMonitor(
        config=cfg,
        sources=sources,
        runner=runner or _FakeRunner(),
        ledger=ledger,
        state=state,
        now_fn=_now,
        sleep_fn=lambda seconds: None,
        log_fn=lambda message: None,
    )


# ===========================================================================
# Configuration
# ===========================================================================


class TestLoadConfig:
    def test_merges_defaults_with_overrides(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"poll_interval_seconds": 5}), encoding="utf-8")
        config = MON.load_config(path)
        assert config["poll_interval_seconds"] == 5
        assert config["execution_window_minutes"] == 30
        assert config["asset"] == "XAU/USD"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            MON.load_config(tmp_path / "missing.json")


# ===========================================================================
# Ledger & state
# ===========================================================================


class TestLedger:
    def test_append_and_read_round_trip(self, tmp_path: Path) -> None:
        ledger = MON.Ledger(tmp_path / "ledger.jsonl")
        ledger.append({"key": "a", "status": "fired", "at": "t"})
        ledger.append({"key": "b", "status": "coalesced", "coalesced_into": "a"})
        entries = ledger.read()
        assert [e["key"] for e in entries] == ["a", "b"]

    def test_corrupt_lines_skipped(self, tmp_path: Path) -> None:
        ledger = MON.Ledger(tmp_path / "ledger.jsonl")
        ledger.path.write_text(
            "not json\n{\"key\": \"ok\", \"status\": \"fired\"}\n", encoding="utf-8"
        )
        assert len(ledger.read()) == 1

    def test_has_consumed_statuses_only(self, tmp_path: Path) -> None:
        ledger = MON.Ledger(tmp_path / "ledger.jsonl")
        assert ledger.has("a") is False
        ledger.append({"key": "a", "status": "failed"})
        assert ledger.has("a") is False
        ledger.append({"key": "a", "status": "fired"})
        assert ledger.has("a") is True

    def test_last_status(self, tmp_path: Path) -> None:
        ledger = MON.Ledger(tmp_path / "ledger.jsonl")
        ledger.append({"key": "a", "status": "failed"})
        ledger.append({"key": "a", "status": "fired"})
        assert ledger.last_status("a") == "fired"


class TestStateStore:
    def test_round_trip(self, tmp_path: Path) -> None:
        store = MON.StateStore(tmp_path / "state.json")
        store.save({"status": "firing", "pid": 1})
        assert store.load() == {"status": "firing", "pid": 1}

    def test_missing_returns_empty(self, tmp_path: Path) -> None:
        assert MON.StateStore(tmp_path / "nope.json").load() == {}


# ===========================================================================
# Time parsing
# ===========================================================================


class TestParse12h:
    @pytest.mark.parametrize("value,expected", [
        ("2:00 p.m.", (14, 0)),
        ("2:00 PM", (14, 0)),
        ("2:00 p.m", (14, 0)),
        ("10:30 a.m.", (10, 30)),
        ("12:00 p.m.", (12, 0)),
        ("12:30 a.m.", (0, 30)),
    ])
    def test_parses(self, value: str, expected: tuple[int, int]) -> None:
        assert MON._parse_12h_to_24h(value) == expected

    def test_invalid(self) -> None:
        assert MON._parse_12h_to_24h("") is None
        assert MON._parse_12h_to_24h("garbage") is None
        assert MON._parse_12h_to_24h("25:00 p.m.") is None


# ===========================================================================
# Trigger sources
# ===========================================================================


class TestReleaseCalendarSource:
    def test_candidate_from_release_timestamp(self, tmp_path: Path) -> None:
        source = _release_source(tmp_path, "2026-08-04 08:30:00")
        candidates = source.candidates(NOW)
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.source == "economic"
        assert candidate.event_key == "CPI|2026-08-04T08:30:00"
        # 08:30 US/Eastern on 2026-08-04 (EDT, UTC-4) == 12:30 UTC
        assert candidate.effective_time == datetime.datetime(
            2026, 8, 4, 12, 30, tzinfo=datetime.timezone.utc
        )


class TestFOMCSource:
    def test_candidate_from_statement_time(self, tmp_path: Path) -> None:
        csv = tmp_path / "fomc.csv"
        csv.write_text(
            "start_date,end_date,event_type,meeting_type,is_two_day,"
            "has_press_conference,statement_time,year,month\n"
            "2024-07-31,2024-07-31,FOMC,scheduled,0,1,2:00 p.m.,2024,2024-07\n",
            encoding="utf-8",
        )
        source = MON.FOMCSource(csv)
        candidates = source.candidates(NOW)
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.event_key == "FOMC|2024-07-31|14:00"
        # 14:00 EDT (UTC-4) on 2024-07-31 == 18:00 UTC
        assert candidate.effective_time == datetime.datetime(
            2024, 7, 31, 18, 0, tzinfo=datetime.timezone.utc
        )


class TestScheduledSlotSource:
    def test_slot_within_window_is_fireable(self, tmp_path: Path) -> None:
        source = MON.ScheduledSlotSource(["08:30"], 30)
        source._local_tz = lambda: ZoneInfo("US/Eastern")  # type: ignore[assignment]
        candidates = source.candidates(NOW)  # 12:35 UTC == 08:35 EDT
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.source == "scheduled"
        assert candidate.effective_time == datetime.datetime(
            2026, 8, 4, 12, 30, tzinfo=datetime.timezone.utc
        )
        assert candidate.payload.get("expired") is False

    def test_slot_past_window_is_expired(self) -> None:
        source = MON.ScheduledSlotSource(["08:30"], 30)
        source._local_tz = lambda: ZoneInfo("US/Eastern")  # type: ignore[assignment]
        late = datetime.datetime(2026, 8, 4, 13, 30, tzinfo=datetime.timezone.utc)
        candidates = source.candidates(late)  # 09:30 EDT, past window
        assert candidates[0].payload.get("expired") is True


class TestMarketMovementSource:
    def test_high_sigma_emits_candidate(self) -> None:
        fetcher = lambda: [OvernightPriceChange(  # noqa: E731
            instrument="XAU/USD", previous_close=100.0, current_price=101.0,
            change_pct=1.0, change_sigma=3.4, session="APAC",
        )]
        source = _market_source(fetcher)
        candidates = source.candidates(NOW)
        assert len(candidates) == 1
        assert candidates[0].source == "market"
        assert candidates[0].severity == "high"
        assert candidates[0].event_key.startswith("market|XAU/USD|")

    def test_two_sigma_emits_medium_candidate(self) -> None:
        fetcher = lambda: [OvernightPriceChange(  # noqa: E731
            instrument="XAU/USD", previous_close=100.0, current_price=101.0,
            change_pct=1.0, change_sigma=2.1, session="APAC",
        )]
        source = _market_source(fetcher)
        candidates = source.candidates(NOW)
        assert len(candidates) == 1
        assert candidates[0].severity == "medium"

    def test_below_threshold_no_candidate(self) -> None:
        fetcher = lambda: [OvernightPriceChange(  # noqa: E731
            instrument="XAU/USD", previous_close=100.0, current_price=101.0,
            change_pct=1.0, change_sigma=0.5, session="APAC",
        )]
        assert _market_source(fetcher).candidates(NOW) == []

    def test_other_instrument_ignored(self) -> None:
        fetcher = lambda: [OvernightPriceChange(  # noqa: E731
            instrument="DXY", previous_close=100.0, current_price=101.0,
            change_pct=1.0, change_sigma=3.4, session="APAC",
        )]
        assert _market_source(fetcher).candidates(NOW) == []


class TestNewsSource:
    def test_relevant_article_emits_candidate_and_marks_seen(self) -> None:
        source = MON.NewsSource(
            min_relevance=0.7,
            bucket_seconds=7200,
            collector=lambda: [_news_article("gold prices surge")],
            relevance_fn=lambda article: 0.9,
        )
        candidates = source.candidates(NOW)
        assert len(candidates) == 1
        assert candidates[0].source == "news"
        source.consume_news_keys(candidates)
        assert len(source.seen) == 1
        assert source.candidates(NOW) == []

    def test_low_relevance_no_candidate(self) -> None:
        source = MON.NewsSource(
            min_relevance=0.7,
            bucket_seconds=7200,
            collector=lambda: [_news_article("recipe for bread")],
            relevance_fn=lambda article: 0.1,
        )
        assert source.candidates(NOW) == []


# ===========================================================================
# Monitor behavior
# ===========================================================================


class TestTick:
    def test_economic_release_fires_once(self, tmp_path: Path) -> None:
        source = _release_source(tmp_path, "2026-08-04 08:30:00")
        runner = _FakeRunner()
        monitor = _monitor(tmp_path, [source], runner=runner)
        outcome = monitor.tick(NOW)
        assert outcome == "fired:CPI|2026-08-04T08:30:00"
        assert runner.calls == ["economic"]
        entries = monitor.ledger.read()
        fired = [e for e in entries if e["status"] == "fired"]
        assert fired[0]["key"] == "CPI|2026-08-04T08:30:00"
        assert monitor.state.load()["status"] == "cooldown"

        second = monitor.tick(NOW)
        assert second == "idle"

    def test_past_window_release_marked_expired(self, tmp_path: Path) -> None:
        source = _release_source(tmp_path, "2026-08-04 08:30:00")
        runner = _FakeRunner()
        monitor = _monitor(tmp_path, [source], runner=runner)
        late = NOW + datetime.timedelta(hours=4)
        outcome = monitor.tick(late)
        assert outcome == "idle"
        assert runner.calls == []
        statuses = {e["status"] for e in monitor.ledger.read()}
        assert "expired" in statuses

    def test_ancient_release_not_recorded(self, tmp_path: Path) -> None:
        source = _release_source(tmp_path, "2025-01-15 08:30:00")
        monitor = _monitor(tmp_path, [source])
        monitor.tick(NOW)
        assert monitor.ledger.read() == []

    def test_dry_run_does_not_record(self, tmp_path: Path) -> None:
        source = _release_source(tmp_path, "2026-08-04 08:30:00")
        runner = _FakeRunner(dry_run=True)
        monitor = _monitor(tmp_path, [source], runner=runner)
        outcome = monitor.tick(NOW)
        assert outcome.startswith("dry-run:")
        assert runner.calls == []
        assert monitor.ledger.read() == []

    def test_failed_run_is_retryable(self, tmp_path: Path) -> None:
        source = _release_source(tmp_path, "2026-08-04 08:30:00")
        runner = _FakeRunner(returncode=1)
        monitor = _monitor(tmp_path, [source], runner=runner)
        outcome = monitor.tick(NOW)
        assert outcome.startswith("failed:")
        assert monitor.state.load()["consecutive_failures"] == 1

        runner.returncode = 0
        retry = monitor.tick(NOW)
        assert retry.startswith("fired:")
        assert runner.calls == ["economic", "economic"]

    def test_market_move_coalesces_into_economic(self, tmp_path: Path) -> None:
        economic = _release_source(tmp_path, "2026-08-04 08:30:00")
        now = NOW - datetime.timedelta(minutes=3)
        fetcher = lambda: [OvernightPriceChange(  # noqa: E731
            instrument="XAU/USD", previous_close=100.0, current_price=101.0,
            change_pct=1.0, change_sigma=3.4, session="APAC",
        )]
        market = _market_source(fetcher)
        runner = _FakeRunner()
        monitor = _monitor(tmp_path, [economic, market], runner=runner)

        outcome = monitor.tick(now)
        assert outcome.startswith("fired:")
        assert runner.calls == ["economic"]
        entries = {e["status"] for e in monitor.ledger.read()}
        assert "fired" in entries
        assert "coalesced" in entries

    def test_market_only_fires_when_no_calendar(self, tmp_path: Path) -> None:
        fetcher = lambda: [OvernightPriceChange(  # noqa: E731
            instrument="XAU/USD", previous_close=100.0, current_price=101.0,
            change_pct=1.0, change_sigma=3.4, session="APAC",
        )]
        market = _market_source(fetcher)
        runner = _FakeRunner()
        monitor = _monitor(tmp_path, [market], runner=runner)
        outcome = monitor.tick(NOW)
        assert outcome.startswith("fired:")
        assert runner.calls == ["market"]

    def test_cooldown_bucket_suppresses_repeat(self, tmp_path: Path) -> None:
        fetcher = lambda: [OvernightPriceChange(  # noqa: E731
            instrument="XAU/USD", previous_close=100.0, current_price=101.0,
            change_pct=1.0, change_sigma=3.4, session="APAC",
        )]
        market = _market_source(fetcher)
        runner = _FakeRunner()
        monitor = _monitor(tmp_path, [market], runner=runner)
        assert monitor.tick(NOW).startswith("fired:")
        # Same cooldown bucket (60 min) -> suppressed
        later = NOW + datetime.timedelta(minutes=10)
        assert monitor.tick(later) == "idle"


class TestNextDeadline:
    def test_returns_earliest_future_calendar(self, tmp_path: Path) -> None:
        source = _release_source(tmp_path, "2026-08-05 08:30:00")
        monitor = _monitor(
            tmp_path, [source], config={"poll_interval_seconds": 999999999}
        )
        early = datetime.datetime(2026, 8, 4, 0, 0, tzinfo=datetime.timezone.utc)
        deadline = monitor.next_deadline(early)
        assert deadline == datetime.datetime(
            2026, 8, 5, 12, 30, tzinfo=datetime.timezone.utc
        )

    def test_poll_interval_wins_when_sooner(self, tmp_path: Path) -> None:
        source = _release_source(tmp_path, "2026-08-05 08:30:00")
        monitor = _monitor(tmp_path, [source])
        early = datetime.datetime(2026, 8, 4, 0, 0, tzinfo=datetime.timezone.utc)
        deadline = monitor.next_deadline(early)
        assert deadline == early + datetime.timedelta(seconds=60)


class TestRecovery:
    def test_stale_firing_state_is_interrupted(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        ledger = MON.Ledger(state_dir / "ledger.jsonl")
        state = MON.StateStore(state_dir / "state.json")
        state.save({
            "status": "firing", "pid": 2 ** 31 - 1,
            "trigger_key": "CPI|2026-08-04T08:30:00", "trigger_source": "economic",
        })
        monitor = MON.ContinuousMonitor(
            config=dict(MON.DEFAULT_CONFIG),
            sources=[],
            runner=_FakeRunner(),
            ledger=ledger,
            state=state,
            now_fn=_now,
            sleep_fn=lambda seconds: None,
            log_fn=lambda message: None,
        )
        monitor.recover()
        assert state.load()["status"] == "sleeping"
        statuses = {e["status"] for e in ledger.read()}
        assert "interrupted" in statuses


# ===========================================================================
# Source assembly
# ===========================================================================


class TestBuildSources:
    def test_default_assembly(self, tmp_path: Path) -> None:
        state = MON.StateStore(tmp_path / "state.json")
        config = dict(MON.DEFAULT_CONFIG)
        config["event_types"] = ["CPI"]
        sources = MON.build_sources(config, state)
        kinds = {type(s).__name__ for s in sources}
        assert "ReleaseCalendarSource" in kinds
        assert "MarketMovementSource" in kinds
        assert "NewsSource" in kinds
        assert "FOMCSource" not in kinds
