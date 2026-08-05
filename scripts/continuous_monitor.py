"""AurumAI continuous runtime monitor.

A long-running daemon that sleeps idle and wakes only on a meaningful
trigger to execute the existing ``run.py`` unchanged. Trigger classes:

  - economic   (CPI / FOMC release-calendar instants)
  - scheduled  (daily wall-clock slots)
  - market     (XAU/USD sigma move, via OvernightDataFetcher +
                AnomalyDetectionEngine)
  - news       (relevant headline, via NewsCollector)

This file is the runtime/trigger layer only. It does not modify any
workflow, algorithm, contract, threshold, or ``run.py`` behavior.

State artifacts (all under ``runtime/continuous_monitor/``):
  config.json    monitor configuration (merged over defaults)
  state.json     last-known monitor state (persisted per transition)
  ledger.jsonl   append-only trigger ledger (duplicate protection)
  monitor.log    structured monitor log

Usage:
    python scripts/continuous_monitor.py                 # daemon
    python scripts/continuous_monitor.py --once          # single pass
    python scripts/continuous_monitor.py --once --dry-run

Exit codes:
    0  clean shutdown / successful single pass
    1  configuration error
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, MutableSet

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from runtime_registry.outputs import latest_run_dir  # noqa: E402

EXIT_OK = 0
EXIT_CONFIG_ERROR = 1

DEFAULT_STATE_DIR = ROOT / "runtime" / "continuous_monitor"

DEFAULT_CONFIG: dict[str, Any] = {
    "poll_interval_seconds": 60,
    "execution_window_minutes": 30,
    "merge_window_minutes": 5,
    "market_cooldown_minutes": 60,
    "news_cooldown_minutes": 120,
    "recovery_lookback_minutes": 1440,
    "scheduled_slots": ["09:30"],
    "event_types": ["CPI", "FOMC"],
    "release_calendar_path": "data/calendar/cpi_releases.csv",
    "fomc_calendar_path": "data/calendar/fomc_meetings.csv",
    "news_min_relevance": 0.7,
    "backoff_seconds": [300, 900, 1800],
    "max_run_seconds": 180,
    "pipeline_config": "runtime_config.json",
    "asset": "XAU/USD",
}

SOURCE_PRIORITY: dict[str, int] = {
    "economic": 1,
    "scheduled": 2,
    "market": 3,
    "news": 4,
}

# Ledger statuses that permanently consume a trigger key.
CONSUMED = frozenset({"fired", "coalesced", "expired"})


def _utc_now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _iso(dt: _dt.datetime) -> str:
    return dt.isoformat()


def _parse_12h_to_24h(value: str) -> tuple[int, int] | None:
    """Parse '2:00 p.m.' / '2:00 PM' into (14, 0)."""
    text = value.strip().lower()
    if not text:
        return None
    pm = "p.m." in text or "p.m" in text or text.endswith("pm")
    cleaned = text.replace("a.m.", "").replace("p.m.", "").replace(" am", "").replace(" pm", "")
    try:
        hour_str, minute_str = cleaned.split(":")
    except ValueError:
        return None
    try:
        hour = int(hour_str)
        minute = int(minute_str.split()[0])
    except (ValueError, IndexError):
        return None
    if pm and hour != 12:
        hour += 12
    elif not pm and hour == 12:
        hour = 0
    if not (0 <= hour < 24 and 0 <= minute < 60):
        return None
    return hour, minute


# ---------------------------------------------------------------------------
# Trigger model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TriggerCandidate:
    source: str
    event_key: str
    effective_time: _dt.datetime
    severity: str
    window_minutes: int
    payload: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Durable state
# ---------------------------------------------------------------------------


class Ledger:
    """Append-only JSONL store of trigger events (duplicate protection)."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        entries: list[dict[str, Any]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict):
                entries.append(entry)
        return entries

    def has(self, event_key: str) -> bool:
        return any(
            e.get("key") == event_key and e.get("status") in CONSUMED
            for e in self.read()
        )

    def append(self, entry: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()

    def last_status(self, event_key: str) -> str | None:
        for e in reversed(self.read()):
            if e.get("key") == event_key:
                return str(e.get("status"))
        return None


class StateStore:
    """Small persisted JSON store for the monitor's runtime state."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def save(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)


# ---------------------------------------------------------------------------
# Trigger sources
# ---------------------------------------------------------------------------


class ReleaseCalendarSource:
    """Economic releases from a committed release calendar (CPI)."""

    def __init__(self, event_type: str, calendar_path: Path) -> None:
        from knowledge.events.release_calendar import ReleaseCalendar

        self._event_type = event_type
        self._path = calendar_path
        self._cal = ReleaseCalendar.from_csv(str(calendar_path))

    @property
    def event_type(self) -> str:
        return self._event_type

    def candidates(self, now: _dt.datetime) -> list[TriggerCandidate]:
        from zoneinfo import ZoneInfo

        result: list[TriggerCandidate] = []
        for record in self._cal.records:
            try:
                tz = ZoneInfo(record.timezone)
            except Exception:
                tz = ZoneInfo("US/Eastern")
            naive = _dt.datetime.strptime(record.release_timestamp_et, "%Y-%m-%dT%H:%M:%S")
            effective = naive.replace(tzinfo=tz).astimezone(_dt.timezone.utc)
            result.append(TriggerCandidate(
                source="economic",
                event_key=f"{self._event_type}|{record.release_timestamp_et}",
                effective_time=effective,
                severity="high",
                window_minutes=int(DEFAULT_CONFIG["execution_window_minutes"]),
                payload={
                    "event_type": self._event_type,
                    "reference_period": record.reference_period,
                },
            ))
        return result


class FOMCSource:
    """FOMC statement instants from the committed meeting calendar."""

    def __init__(self, calendar_path: Path) -> None:
        from connectors.fomc_calendar import FOMCCalendarConnector

        self._path = calendar_path
        self._connector = FOMCCalendarConnector(path=calendar_path, auto_refresh=False)

    def candidates(self, now: _dt.datetime) -> list[TriggerCandidate]:
        from zoneinfo import ZoneInfo

        df = self._connector.df
        tz = ZoneInfo("US/Eastern")
        result: list[TriggerCandidate] = []
        for _, row in df.iterrows():
            start = row["start_date"]
            statement = _parse_12h_to_24h(str(row.get("statement_time", "")))
            if statement is None:
                continue
            hour, minute = statement
            effective = _dt.datetime(
                start.year, start.month, start.day, hour, minute, tzinfo=tz
            ).astimezone(_dt.timezone.utc)
            result.append(TriggerCandidate(
                source="economic",
                event_key=f"FOMC|{start.isoformat()}|{hour:02d}:{minute:02d}",
                effective_time=effective,
                severity="high",
                window_minutes=int(DEFAULT_CONFIG["execution_window_minutes"]),
                payload={"event_type": "FOMC", "meeting_date": start.isoformat()},
            ))
        return result


class ScheduledSlotSource:
    """Daily wall-clock slots interpreted in the server's local timezone."""

    def __init__(self, slots: list[str], window_minutes: int) -> None:
        self._slots = list(slots)
        self._window_minutes = window_minutes

    def _local_tz(self) -> Any:
        return _dt.datetime.now().astimezone().tzinfo

    def candidates(self, now: _dt.datetime) -> list[TriggerCandidate]:
        tz = self._local_tz()
        local_now = now.astimezone(tz)
        result: list[TriggerCandidate] = []
        for slot in self._slots:
            try:
                hour, minute = (int(p) for p in slot.split(":"))
            except (ValueError, AttributeError):
                continue
            slot_dt = _dt.datetime(
                local_now.year, local_now.month, local_now.day, hour, minute, tzinfo=tz
            ).astimezone(_dt.timezone.utc)
            expired = slot_dt + _dt.timedelta(minutes=self._window_minutes) < now
            result.append(TriggerCandidate(
                source="scheduled",
                event_key=f"daily|{local_now.date().isoformat()}",
                effective_time=slot_dt,
                severity="medium",
                window_minutes=self._window_minutes,
                payload={"slot": slot, "expired": expired},
            ))
        return result


class MarketMovementSource:
    """XAU/USD sigma move via the existing overnight fetcher + detector."""

    SIGMA_ANOMALY_TYPES = ("high_sigma_move", "two_sigma_move")

    def __init__(
        self,
        instrument: str,
        bucket_seconds: int,
        fetcher: Callable[[], list[Any]] | None = None,
        detector: Any = None,
    ) -> None:
        from pre_market.anomaly_detector import AnomalyDetectionEngine

        self._instrument = instrument
        self._bucket_seconds = int(bucket_seconds)
        self._fetcher = fetcher
        self._detector = detector or AnomalyDetectionEngine()

    def _default_fetch(self) -> list[Any]:
        from pre_market.overnight_fetcher import OvernightDataFetcher

        return OvernightDataFetcher().fetch_overnight_changes()

    def candidates(self, now: _dt.datetime) -> list[TriggerCandidate]:
        if self._fetcher is None:
            changes = self._default_fetch()
        else:
            changes = self._fetcher()
        if not changes:
            return []
        flags = self._detector.detect(changes)
        qualifying = [
            f for f in flags
            if f.anomaly_type in self.SIGMA_ANOMALY_TYPES
            and f.instrument == self._instrument
        ]
        if not qualifying:
            return []
        bucket = int(now.timestamp() // self._bucket_seconds) * self._bucket_seconds
        bucket_start = _dt.datetime.fromtimestamp(bucket, tz=_dt.timezone.utc)
        worst = max(qualifying, key=lambda f: abs(f.value))
        return [TriggerCandidate(
            source="market",
            event_key=f"market|{self._instrument}|{bucket_start.isoformat()}",
            effective_time=now,
            severity=worst.severity,
            window_minutes=int(DEFAULT_CONFIG["execution_window_minutes"]),
            payload={
                "instrument": self._instrument,
                "change_sigma": float(worst.value),
                "anomaly_type": worst.anomaly_type,
            },
        )]


class NewsSource:
    """Relevant headline trigger via the existing NewsCollector.

    Candidate generation is pure. Article keys are reported through the
    candidate payload so the monitor can mark them as seen after it has
    processed the trigger pass (``consume_news_keys``).
    """

    def __init__(
        self,
        min_relevance: float,
        bucket_seconds: int,
        collector: Any = None,
        relevance_fn: Callable[[Any], float] | None = None,
        seen: MutableSet[str] | None = None,
    ) -> None:
        self._min_relevance = float(min_relevance)
        self._bucket_seconds = int(bucket_seconds)
        self._collector = collector
        self._relevance_fn = relevance_fn
        self.seen = seen if seen is not None else set()

    def _default_collect(self) -> list[Any]:
        from news.news_collector import NewsCollector

        return NewsCollector().collect()

    def _default_relevance(self, article: Any) -> float:
        from pre_market.news_ingestion import OvernightNewsIngestion

        return OvernightNewsIngestion._default_relevance(
            article, OvernightNewsIngestion.W3_TOPICS
        )

    @staticmethod
    def _article_key(article: Any) -> str:
        raw = f"{getattr(article, 'url', '')}|{getattr(article, 'published', '')}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def candidates(self, now: _dt.datetime) -> list[TriggerCandidate]:
        if self._collector is None:
            articles = self._default_collect()
        else:
            articles = self._collector()
        if not articles:
            return []
        relevance_fn = self._relevance_fn or self._default_relevance
        unseen = [a for a in articles if self._article_key(a) not in self.seen]
        if not unseen:
            return []
        relevant = [a for a in unseen if relevance_fn(a) >= self._min_relevance]
        if not relevant:
            return []
        bucket = int(now.timestamp() // self._bucket_seconds) * self._bucket_seconds
        bucket_start = _dt.datetime.fromtimestamp(bucket, tz=_dt.timezone.utc)
        return [TriggerCandidate(
            source="news",
            event_key=f"news|{bucket_start.isoformat()}",
            effective_time=now,
            severity="medium",
            window_minutes=int(DEFAULT_CONFIG["execution_window_minutes"]),
            payload={
                "headline": getattr(relevant[0], "title", ""),
                "count": len(relevant),
                "article_keys": [self._article_key(a) for a in relevant],
            },
        )]

    def consume_news_keys(self, candidates: list[TriggerCandidate]) -> None:
        for candidate in candidates:
            if candidate.source != "news":
                continue
            for key in candidate.payload.get("article_keys", []):
                self.seen.add(str(key))


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------


class PipelineRunner:
    """Executes the existing ``run.py`` unchanged as a subprocess."""

    def __init__(
        self,
        root: Path = ROOT,
        state_dir: Path = DEFAULT_STATE_DIR,
        python: str | None = None,
        dry_run: bool = False,
    ) -> None:
        self._root = root
        self._state_dir = state_dir
        self._python = python or sys.executable
        self._dry_run = dry_run

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    def _override_config(self, trigger_label: str, base_config: dict[str, Any]) -> Path:
        override = dict(base_config)
        override["trigger"] = trigger_label
        path = self._state_dir / "pipeline_config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(override, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    def run(self, trigger_label: str) -> tuple[int, Path | None]:
        run_date = _dt.date.today().isoformat()
        outputs_base = self._root / "outputs"
        date_dir = outputs_base / run_date
        if self._dry_run:
            return 0, date_dir
        self._refresh_gold()
        pipeline_script = self._root / "run.py"
        base = self._root / "runtime_config.json"
        if base.exists():
            try:
                base_config = json.loads(base.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                base_config = {}
        else:
            base_config = {}
        config_path = self._override_config(trigger_label, base_config)
        command = [
            self._python, str(pipeline_script), "--config", str(config_path),
            "--no-refresh",
        ]
        returncode = subprocess.run(
            command,
            cwd=str(self._root),
            timeout=3600,
        ).returncode
        run_dir = latest_run_dir(outputs_base, run_date) or date_dir
        if returncode == 0 and run_dir != date_dir:
            report_script = self._root / "scripts" / "generate_institutional_report.py"
            subprocess.run(
                [self._python, str(report_script), "--output-dir", str(run_dir)],
                cwd=str(self._root),
                timeout=600,
            )
        return returncode, run_dir

    def _refresh_gold(self) -> None:
        """Refresh local gold history before a triggered run (fail-safe)."""
        try:
            from connectors.gold_data_provider import GoldDataProvider

            report = GoldDataProvider().refresh()
            print(
                f"continuous_monitor: gold refresh {report.status} "
                f"(rows {report.rows_before} -> {report.rows_after}, "
                f"last {report.last_date_before} -> {report.last_date_after})",
                flush=True,
            )
            if report.status != "ok":
                print(
                    f"continuous_monitor: gold refresh incomplete "
                    f"({report.message}); proceeding with existing dataset",
                    file=sys.stderr,
                    flush=True,
                )
        except Exception as exc:  # pragma: no cover - defensive
            print(
                f"continuous_monitor: gold refresh failed ({exc}); "
                "proceeding with existing dataset",
                file=sys.stderr,
                flush=True,
            )


def _load_pipeline_run_id(run_dir: Path | None) -> str | None:
    if run_dir is None:
        return None
    path = run_dir / "summary.json"
    if not path.exists():
        return None
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(summary, dict):
        return summary.get("pipeline_id")
    return None


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------


class ContinuousMonitor:
    """State machine: INIT -> SLEEPING -> POLLING -> FIRING/COOLDOWN -> ..."""

    def __init__(
        self,
        config: dict[str, Any],
        sources: list[Any],
        runner: PipelineRunner,
        ledger: Ledger,
        state: StateStore,
        now_fn: Callable[[], _dt.datetime] = _utc_now,
        sleep_fn: Callable[[float], None] = time.sleep,
        log_fn: Callable[[str], None] | None = None,
    ) -> None:
        self._config = config
        self._sources = list(sources)
        self._runner = runner
        self._ledger = ledger
        self._state = state
        self._now_fn = now_fn
        self._sleep_fn = sleep_fn
        self._log_fn = log_fn or (lambda msg: print(msg, flush=True))
        self._stopped = False

    def _log(self, message: str) -> None:
        self._log_fn(message)

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    @property
    def ledger(self) -> Ledger:
        return self._ledger

    @property
    def state(self) -> StateStore:
        return self._state

    def _window_minutes(self) -> int:
        return int(self._config.get("execution_window_minutes", 30))

    def _merge_window(self) -> int:
        return int(self._config.get("merge_window_minutes", 5))

    def _backoff_step(self, consecutive_failures: int) -> int:
        ladder = list(self._config.get("backoff_seconds", [300, 900, 1800]))
        if not ladder:
            return 300
        return int(ladder[min(consecutive_failures, len(ladder) - 1)])

    # -- state transitions -------------------------------------------------

    def _set_status(self, status: str, **extra: Any) -> None:
        data = self._state.load()
        data.update({"status": status, "last_updated": _iso(self._now_fn())})
        data.update(extra)
        self._state.save(data)

    def _pid_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except (OSError, ProcessLookupError):
            return False
        except Exception:
            return True
        return True

    def recover(self) -> None:
        """Resolve stale in-flight state after a restart."""
        data = self._state.load()
        if data.get("status") == "firing":
            pid = data.get("pid")
            key = data.get("trigger_key")
            alive = bool(pid) and self._pid_alive(int(pid))
            if not alive:
                self._ledger.append({
                    "key": key,
                    "source": data.get("trigger_source"),
                    "status": "interrupted",
                    "at": _iso(self._now_fn()),
                    "pid": pid,
                    "notes": "interrupted on restart; retry if window open",
                })
                self._log(f"recovered stale firing state for {key} (pid={pid})")
        self._set_status("sleeping")

    def _candidates(self, now: _dt.datetime) -> list[TriggerCandidate]:
        candidates: list[TriggerCandidate] = []
        for source in self._sources:
            try:
                candidates.extend(source.candidates(now))
            except Exception as exc:  # pragma: no cover - defensive
                self._log(f"source {source!r} failed: {exc}")
        return candidates

    @staticmethod
    def _expired_keys(
        candidates: list[TriggerCandidate], now: _dt.datetime, lookback_minutes: int,
    ) -> list[TriggerCandidate]:
        result: list[TriggerCandidate] = []
        lookback = _dt.timedelta(minutes=lookback_minutes)
        for candidate in candidates:
            expiry = candidate.effective_time + _dt.timedelta(
                minutes=candidate.window_minutes
            )
            if expiry < now and candidate.effective_time >= now - lookback:
                result.append(candidate)
        return result

    @staticmethod
    def _fireable(
        candidates: list[TriggerCandidate], now: _dt.datetime,
    ) -> list[TriggerCandidate]:
        result: list[TriggerCandidate] = []
        for candidate in candidates:
            if candidate.payload.get("expired"):
                continue
            expiry = candidate.effective_time + _dt.timedelta(
                minutes=candidate.window_minutes
            )
            if candidate.effective_time <= now <= expiry:
                result.append(candidate)
        result.sort(key=lambda c: (
            SOURCE_PRIORITY.get(c.source, 9),
            c.effective_time,
        ))
        return result

    def next_deadline(self, now: _dt.datetime) -> _dt.datetime:
        deadlines = [
            now + _dt.timedelta(seconds=int(self._config.get("poll_interval_seconds", 60))),
        ]
        for candidate in self._candidates(now):
            if candidate.effective_time > now and not self._ledger.has(candidate.event_key):
                deadlines.append(candidate.effective_time)
        failures = int(self._state.load().get("consecutive_failures", 0))
        if failures > 0:
            deadlines.append(now + _dt.timedelta(seconds=self._backoff_step(failures)))
        return min(deadlines)

    def tick(self, now: _dt.datetime | None = None) -> str:
        """Run one monitor iteration; returns the outcome label."""
        now = now or self._now_fn()
        self.recover()

        candidates = self._candidates(now)

        for expired in self._expired_keys(
            candidates, now,
            int(self._config.get("recovery_lookback_minutes", 1440)),
        ):
            if self._ledger.has(expired.event_key):
                continue
            self._ledger.append({
                "key": expired.event_key,
                "source": expired.source,
                "status": "expired",
                "at": _iso(now),
                "payload": expired.payload,
                "notes": "execution window elapsed",
            })
            self._log(f"expired {expired.source} {expired.event_key}")

        for source in self._sources:
            if hasattr(source, "consume_news_keys"):
                source.consume_news_keys(candidates)

        fireable = [
            c for c in self._fireable(candidates, now)
            if not self._ledger.has(c.event_key)
        ]
        if not fireable:
            self._set_status("sleeping")
            return "idle"

        winner = fireable[0]
        if self._runner.dry_run:
            self._log(
                f"[dry-run] would fire {winner.source} {winner.event_key} "
                f"(severity={winner.severity})"
            )
            self._set_status("sleeping")
            return f"dry-run:{winner.event_key}"

        self._set_status("firing", pid=os.getpid(), trigger_key=winner.event_key,
                         trigger_source=winner.source)
        self._log(f"firing {winner.source} trigger {winner.event_key}")

        try:
            returncode, run_dir = self._runner.run(winner.source)
        except Exception as exc:  # pragma: no cover - defensive
            returncode = -1
            run_dir = None
            self._log(f"runner raised: {exc}")

        run_id = _load_pipeline_run_id(run_dir)
        if returncode == 0:
            self._ledger.append({
                "key": winner.event_key,
                "source": winner.source,
                "status": "fired",
                "at": _iso(now),
                "run_id": run_id,
                "severity": winner.severity,
                "payload": winner.payload,
            })
            self._state.save(self._state.load() | {"consecutive_failures": 0})
            self._set_status("cooldown")
            self._log(f"fired ok {winner.event_key} run_id={run_id}")

            merge = self._merge_window()
            for other in fireable[1:]:
                delta = abs((other.effective_time - winner.effective_time).total_seconds())
                if delta <= merge * 60:
                    self._ledger.append({
                        "key": other.event_key,
                        "source": other.source,
                        "status": "coalesced",
                        "coalesced_into": winner.event_key,
                        "at": _iso(now),
                    })
                    self._log(f"coalesced {other.source} {other.event_key} into {winner.event_key}")
            return f"fired:{winner.event_key}"
        else:
            self._ledger.append({
                "key": winner.event_key,
                "source": winner.source,
                "status": "failed",
                "at": _iso(now),
                "returncode": returncode,
                "severity": winner.severity,
                "payload": winner.payload,
            })
            failures = int(self._state.load().get("consecutive_failures", 0)) + 1
            self._state.save(self._state.load() | {"consecutive_failures": failures})
            self._set_status("sleeping", consecutive_failures=failures)
            self._log(f"firing failed {winner.event_key} returncode={returncode}")
            return f"failed:{winner.event_key}"

    def run_forever(self) -> int:
        self._log("continuous monitor starting")
        self._set_status("sleeping")

        def _handle_signal(signum: int, frame: Any) -> None:  # noqa: ARG001
            self._stopped = True

        try:
            signal.signal(signal.SIGINT, _handle_signal)
            signal.signal(signal.SIGTERM, _handle_signal)
        except (ValueError, OSError):  # pragma: no cover - non-main thread
            pass

        while not self._stopped:
            now = self._now_fn()
            outcome = self.tick(now)
            self._log(f"tick: {outcome}")
            if outcome.startswith("failed"):
                deadline = now + _dt.timedelta(
                    seconds=self._backoff_step(
                        int(self._state.load().get("consecutive_failures", 0))
                    )
                )
            else:
                deadline = self.next_deadline(now)
            sleep_seconds = max(0.0, (deadline - self._now_fn()).total_seconds())
            if sleep_seconds > 0:
                self._set_status("sleeping", next_wake=_iso(deadline))
                self._log(f"sleeping {sleep_seconds:.0f}s until {deadline.isoformat()}")
                try:
                    self._sleep_fn(sleep_seconds)
                except KeyboardInterrupt:
                    self._stopped = True

        self._set_status("shutdown")
        self._log("continuous monitor shutdown")
        return EXIT_OK


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def load_config(path: Path) -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    if not path.exists():
        raise FileNotFoundError(f"monitor config not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"failed to parse monitor config {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"monitor config {path} must be a JSON object")
    config.update(raw)
    return config


def build_sources(config: dict[str, Any], state: StateStore) -> list[Any]:
    sources: list[Any] = []
    window = int(config.get("execution_window_minutes", 30))
    event_types = list(config.get("event_types", ["CPI", "FOMC"]))

    if "CPI" in event_types:
        cal_path = ROOT / str(config["release_calendar_path"])
        if cal_path.exists():
            try:
                sources.append(ReleaseCalendarSource("CPI", cal_path))
            except Exception as exc:  # pragma: no cover - defensive
                print(f"monitor: CPI calendar load failed: {exc}", file=sys.stderr)
        else:
            print(f"monitor: CPI calendar not found: {cal_path}", file=sys.stderr)

    if "FOMC" in event_types:
        fomc_path = ROOT / str(config["fomc_calendar_path"])
        if fomc_path.exists():
            try:
                sources.append(FOMCSource(fomc_path))
            except Exception as exc:  # pragma: no cover - defensive
                print(f"monitor: FOMC calendar load failed: {exc}", file=sys.stderr)
        else:
            print(f"monitor: FOMC calendar not found: {fomc_path}", file=sys.stderr)

    slots = list(config.get("scheduled_slots", []))
    if slots:
        sources.append(ScheduledSlotSource(slots, window))

    sources.append(MarketMovementSource(
        instrument=str(config.get("asset", "XAU/USD")),
        bucket_seconds=int(config.get("market_cooldown_minutes", 60)) * 60,
    ))

    seen: MutableSet[str] = set(state.load().get("news_seen", []))
    sources.append(NewsSource(
        min_relevance=float(config.get("news_min_relevance", 0.7)),
        bucket_seconds=int(config.get("news_cooldown_minutes", 120)) * 60,
        seen=seen,
    ))
    return sources


def persist_news_seen(sources: list[Any], state: StateStore) -> None:
    for source in sources:
        if isinstance(source, NewsSource):
            state.save(state.load() | {"news_seen": sorted(source.seen)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/continuous_monitor.py",
        description="AurumAI continuous runtime monitor.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_STATE_DIR / "config.json"),
        help="Path to the monitor configuration JSON.",
    )
    parser.add_argument(
        "--state-dir",
        default=str(DEFAULT_STATE_DIR),
        help="Directory for monitor state artifacts.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single pass and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect triggers but never execute the pipeline.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=None,
        help="Override the poll interval for this invocation.",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(Path(args.config))
    except (FileNotFoundError, ValueError) as exc:
        print(f"continuous_monitor: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    if args.sleep_seconds is not None:
        config["poll_interval_seconds"] = args.sleep_seconds

    state_dir = Path(args.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(state_dir / "ledger.jsonl")
    state = StateStore(state_dir / "state.json")
    sources = build_sources(config, state)
    runner = PipelineRunner(root=ROOT, state_dir=state_dir, dry_run=args.dry_run)

    monitor = ContinuousMonitor(
        config=config,
        sources=sources,
        runner=runner,
        ledger=ledger,
        state=state,
        sleep_fn=time.sleep,
    )

    if args.once:
        outcome = monitor.tick()
        persist_news_seen(sources, state)
        print(f"continuous_monitor: once -> {outcome}")
        return EXIT_OK

    try:
        code = monitor.run_forever()
    except KeyboardInterrupt:
        code = EXIT_OK
    finally:
        persist_news_seen(sources, state)
    return code


if __name__ == "__main__":
    sys.exit(main())
