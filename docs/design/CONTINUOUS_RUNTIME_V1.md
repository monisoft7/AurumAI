# Continuous Runtime Monitoring for XAU/USD — V1 Design

Status: Architecture only. No implementation, no code, no tests.
Scope: A minimal always-on runtime monitor that sleeps idle and wakes only on a meaningful trigger to execute the **existing, unchanged** `run.py`.

## 1. Objective

AurumAI must operate continuously and automatically execute the institutional pipeline only when a meaningful trigger occurs:

- an economic release happens,
- a scheduled time slot is reached,
- XAU/USD (or a correlated instrument) moves meaningfully,
- a relevant news item breaks.

The monitor is the smallest additive component that achieves this without modifying `run.py`, decision logic, thresholds, confidence computation, workflows, or the architecture.

## 2. Constraints (binding)

- Do NOT modify decision logic, thresholds, confidence, workflows, or architecture.
- Do NOT modify `run.py` or any existing script/module/contract.
- Reuse existing trigger sources and detection logic as-is (read-only).
- Gold (XAU/USD) is the only monitored asset in v1.
- Additive only: new monitor script + new state artifacts under `runtime/continuous_monitor/`.
- All existing market-movement thresholds are **reused, never changed** (see §4.3).

## 3. Audit of the current runtime

| Layer | Component | Behavior today |
|---|---|---|
| Runtime | `run.py` | Single-shot institutional pipeline (25 stages, ~47–55 s), writes `outputs/YYYY-MM-DD/{summary,finalize,config,stages,outcome}.json`, appends one immutable record to `runtime/run_registry.jsonl`, exits. |
| Scheduling | `scripts/run_daily.py` | Runs `run.py` once, generates the report, verifies, sends Telegram, exits. One-shot wrapper; **no daemon, no loop, no trigger awareness.** |
| Reporting | `scripts/generate_institutional_report.py` | Read-only report layer. |
| Outcome | `scripts/evaluate_outcome.py` | Post-horizon outcome evaluation (additive, reused here as-is). |
| Orchestration | `InstitutionalOrchestrator` | 25-stage checkpointed pipeline. |
| Data refresh | `scripts/download_fomc_calendar.py`, `download_dxy.py` | One-shot data pulls (FRED / yfinance). |
| State | `runtime/run_registry.jsonl` | Append-only immutable run records (`run_id`, `timestamp`, `event_type`, `decision`, `confidence`, `output_directory`). |

**There is no continuous monitor, scheduler daemon, or event loop in the project today.** `run_daily.py` is a scheduled-time wrapper invoked externally (manual/cron); nothing watches for economic releases, market moves, or news.

## 4. Available real-time trigger sources (audit result)

All of the following already exist and are reusable as-is.

### 4.1 Economic event triggers

| Source | Location | Data |
|---|---|---|
| Event registry | `src/knowledge/events/registry.py` | Registered events: `CPI, FOMC, GDP, INTEREST_RATE, NFP, PMI, PPI`. |
| CPI release calendar | `data/calendar/cpi_releases.csv` | 131 rows; `release_date`, `release_time`, `timezone=US/Eastern`, `release_timestamp` (exact release instant). |
| `ReleaseCalendar` | `src/knowledge/events/release_calendar.py` | `from_csv(...)` → records with `release_timestamp_et`; ready-made parser. |
| FOMC meeting calendar | `data/calendar/fomc_meetings.csv` | `start_date`, `end_date`, `statement_time` ("2:00 p.m."), `has_press_conference`. |
| `FOMCCalendarConnector` | `src/connectors/fomc_calendar.py` | `FOMCMeeting(start_date, end_date, minutes_release_date, ...)`; refreshed by `scripts/download_fomc_calendar.py`. |
| `StandardEventMetadata` | `src/knowledge/events/base.py` | Per-event `importance` level (1–3) available for gating. |

### 4.2 Scheduled time triggers

| Source | Location | Meaning |
|---|---|---|
| `scripts/run_daily.py` | existing daily cadence | Once-per-day institutional run. |
| Release calendar instants | §4.1 `release_timestamp` | Exact instants to wake for economic events. |
| FOMC `statement_time` | §4.1 | Scheduled statement instants. |
| `runtime_config.json` `"trigger"` | existing provenance field | Run trigger label already modeled in registry. |

### 4.3 Market movement triggers (XAU/USD)

| Source | Location | Behavior |
|---|---|---|
| `OvernightDataFetcher` | `src/pre_market/overnight_fetcher.py` | Live yfinance pull for `XAU/USD → GC=F` (plus DXY, S&P futures, EUR/USD, USD/JPY); computes `change_pct` and `change_sigma` (vs trailing-return sigma). |
| `OvernightPriceChange` | `src/pre_market/contracts.py:11` | `instrument, previous_close, current_price, change_pct, change_sigma, session`. |
| `AnomalyDetectionEngine` | `src/pre_market/anomaly_detector.py` | **Already detects meaningful moves:** `SIGMA_THRESHOLD = 2.0`, `HIGH_SIGMA_THRESHOLD = 3.0` → `two_sigma_move` / `high_sigma_move`; plus template violations and correlation shifts. This is the v1 market-movement predicate — reused unchanged. |
| `DXYFetcher` | `src/connectors/dxy_fetcher.py` | Correlation instrument. |
| `data/history/gold/gold.csv` | committed history | NOT a live source; used for outcome evaluation, not triggers. |

### 4.4 News triggers

| Source | Location | Behavior |
|---|---|---|
| `NewsCollector` | `src/news/news_collector.py` | RSS aggregation (feedparser) with dedup + sort; topic-based. |
| `NewsIngestion` | `src/pre_market/news_ingestion.py` | Topics: `gold, inflation, fed, interest_rates, usd, ...`; produces `NewsItem(headline, source, published, sentiment_label, sentiment_confidence, relevance_score)`. |
| `NEWS_API_KEY` | `run.py` `_validate_env` (NOTICE) | News capability present but not wired into the institutional pipeline today. |

### 4.5 Classification

| Trigger class | Sources (reused) | Fires when |
|---|---|---|
| **Economic event** | CPI calendar, FOMC meetings, `EventRegistry` | `now` reaches an unconsumed `release_timestamp` (within execution window). |
| **Scheduled time** | daily slot, calendar instants, FOMC `statement_time` | Wall-clock reaches the configured slot / instant. |
| **Market movement** | `OvernightDataFetcher` + `AnomalyDetectionEngine` | XAU/USD `change_sigma` ≥ 2σ (or ≥ 3σ for high severity) within cooldown. |
| **News** | `NewsCollector` + `NewsIngestion` | A relevant article (`relevance_score` ≥ gate) published since the last check. |

## 5. Architecture

### 5.1 New component (additive, sole new owner)

`scripts/continuous_monitor.py` — a long-running daemon.

```
┌─────────────────────────────── continuous_monitor.py ───────────────────────────────┐
│  LOOP (state machine §7)                                                             │
│   ┌──────────────┐   compute_next_deadline()   ┌──────────────┐                       │
│   │  SLEEPING    │ ──────────────────────────► │  POLLING     │                       │
│   │  (sleep idle)│ ◄────────────────────────── │  (evaluate)  │                       │
│   └──────────────┘         no trigger          └──────┬───────┘                       │
│                                                        │ trigger                     │
│                                          ┌─────────────▼─────────────┐                │
│                                          │  FIRING  (subprocess run.py│                │
│                                          │  unchanged, run_daily-style)│               │
│                                          └─────────────┬─────────────┘                │
│                                                        │ exit                        │
│                                           COOLDOWN / FAILED (§7)                      │
└───────────────────────────────────────────────────────────────────────────────────────┘
        │ reads                          │ writes                     │ runs
        ▼                                ▼                            ▼
 trigger sources (existing)      state + ledger (new)          run.py (UNCHANGED)
  ReleaseCalendar/EventRegistry  runtime/continuous_monitor/    subprocess, cwd=ROOT
  OvernightDataFetcher           {state.json, ledger.jsonl,     (same invocation as
  AnomalyDetectionEngine         monitor.log}                    run_daily._run_pipeline)
  NewsCollector/NewsIngestion
```

Ownership:
- **Monitor loop** — owns wake/sleep scheduling, state transitions, subprocess execution.
- **Trigger adapters** — thin read-only wrappers over existing sources that emit `TriggerCandidate{source, event_key, effective_time, severity, payload}`. No detection logic is re-implemented.
- **Ledger** — durable acknowledgement store; owns duplicate protection.
- **run.py** — executes unchanged; the monitor never imports it, only subprocesses it.

### 5.2 Configuration (new, additive)

`runtime/continuous_monitor/config.json` (defaults shown):

| Key | Default | Meaning |
|---|---|---|
| `poll_interval_seconds` | 60 | Wake cadence when no nearer deadline exists. |
| `execution_window_minutes` | 30 | Window after a release instant during which a run may fire. |
| `market_cooldown_minutes` | 60 | Minimum gap between market-triggered runs per instrument. |
| `news_cooldown_minutes` | 120 | Minimum gap between news-triggered runs. |
| `scheduled_slots` | `["09:30"]` (local) | Daily wall-clock slots. |
| `event_types` | `["CPI", "FOMC"]` | Economic events with a committed calendar (v1). |
| `news_min_relevance` | 0.7 | `NewsItem.relevance_score` gate. |
| `backoff_seconds` | `[300, 900, 1800]` | Retry backoff after a failed run. |
| `max_run_seconds` | 180 | Timeout guard for the subprocess. |

These are monitor-level cadence knobs only; they do not touch any existing threshold, decision, or confidence constant.

## 6. Trigger lifecycle

Every trigger passes five phases; the ledger is the durable trace of phases 3–5.

1. **Registered** — an adapter derives a `TriggerCandidate` with a stable `event_key` and `effective_time` (e.g. `("cpi", "2015-03-11T08:30:00-05:00")`, `("daily", "2026-08-04")`, `("market", "XAU/USD")`, `("news", "<article-url-hash>")`).
2. **Armed** — the monitor computes `next_deadline = min(effective_time)` across candidates and sleeps until then (never busy-waits).
3. **Fired** — at `effective_time` (within the execution window) the monitor records `{"key": ..., "status": "fired", "at": ..., "run_id": ...}` in the ledger and starts `run.py`.
4. **Acknowledged** — on success, the ledger entry is updated with `run_id` + `result: "ok"`; the key is now consumed and will never re-fire.
5. **Expired / orphaned** — after restart or window expiry, an unconsumed key is either backfilled (window still open) or marked `expired` with a note (§9).

## 7. State machine

| State | Meaning | Transition on |
|---|---|---|
| `INIT` | Load ledger + `state.json`; reconcile (§9). | reconciliation done → `SLEEPING` |
| `SLEEPING` | Idle. Sleeps until `next_deadline` (min of poll interval / nearest trigger). | deadline reached → `POLLING`; SIGINT/SIGTERM → `SHUTDOWN` |
| `POLLING` | Evaluate adapters against ledger; dedupe. | no trigger → `SLEEPING`; trigger → `FIRING` |
| `FIRING` | Subprocess `run.py` (unchanged); write `state.json` in-flight marker (`pid`, `trigger_key`, `started_at`). | exit 0 → `COOLDOWN`; nonzero/exception → `FAILED` |
| `COOLDOWN` | Post-fire guard for market/news; also the dedupe backstop. | cooldown elapsed → `SLEEPING` |
| `FAILED` | Record failure in ledger + log; apply backoff. | backoff elapsed → `POLLING` (retry same key if window open) |
| `SHUTDOWN` | Persist state, close ledger, exit cleanly (exit code 0). | always terminal |

The in-flight marker in `state.json` makes a crash mid-`run.py` recoverable (§9).

## 8. Duplicate protection

Single mechanism: the **append-only ledger** `runtime/continuous_monitor/ledger.jsonl`, one line per fired key.

- **Economic** — `event_key = (event_type, release_timestamp)`. Consumed keys never re-fire; the calendar is processed strictly forward from the last consumed timestamp.
- **Scheduled** — `event_key = (slot_id, local_date)`. One execution per slot per day.
- **Market** — not a discrete event; dedupe by `market_cooldown_minutes` window: a market trigger fires at most once per cooldown per instrument. The ledger stores the last-fired timestamp per `(market, instrument)`; candidates inside the window are suppressed. `state.json` also remembers the last observed `change_sigma` peak so a sustained move does not re-trigger on every poll.
- **News** — `event_key = sha256(article_url + published)`. One execution per distinct article; multiple co-timed articles coalesce into a single run (a run is per-trigger-instance, not per-article).
- **Cross-class dedupe** — an economic release and a coincident market move within a `merge_window` (e.g. 5 minutes) produce **one** run: the earliest trigger fires, the other is coalesced (ledger records `coalesced_into`).

Idempotence guarantee: replaying the ledger never re-fires a consumed key; `run.py` itself is also inherently re-runnable (writes a fresh `pipeline_id` and appends a fresh registry record), but the monitor never double-fires for the same economic release or slot.

## 9. Recovery after restart

Recovery is driven by the durable `state.json` + ledger; no in-memory state is trusted.

1. **Reload** — load ledger and `state.json`. Recompute armed candidates from sources.
2. **Stale in-flight** — if `state.json` shows `status: firing` and the recorded `pid` is dead, treat the previous run as interrupted: mark the ledger entry `interrupted` with a note; if the trigger's execution window is still open, allow a retry (subject to backoff), else mark `expired`.
3. **Forward scan** — process calendars forward from the last consumed `release_timestamp`; any release whose window is still open is fired, any that lapsed while down is marked `expired` (one log line each).
4. **Resume** — recompute `next_deadline`, enter `SLEEPING`. No trigger is lost or double-fired because every key is ledger-authoritative.

## 10. Logging

- **Monitor log** — `runtime/continuous_monitor/monitor.log`, structured one-line entries: `ts level source event_key state run_id duration notes`.
- **Run logs** — unchanged; produced by `run.py` at `outputs/<date>/run.log`.
- **Registry** — unchanged; the monitor relies on `run_registry.jsonl` records for post-hoc verification of every triggered run.
- **Ledger** — doubles as the audit trace: every fire/ack/expire/interrupt is a line.
- No log file from the monitor is ever parsed by `run.py`.

## 11. Failure handling

| Failure | Behavior |
|---|---|
| Trigger-source poll error (network/API) | Treat as "no trigger" for that cycle, log, keep sleeping on remaining sources; never crash the loop. |
| `run.py` subprocess non-zero exit | Record `failed` in ledger; apply backoff ladder; retry same key if window open; continue daemon. |
| `run.py` subprocess exception / timeout (`max_run_seconds`) | Same as non-zero exit; kill the subprocess. |
| Calendar/ledger file corrupt or missing | Recreate the ledger with a `rebuilt` note (duplicate risk limited to a re-fire guarded by `run_registry` timestamps); calendars are committed data. |
| Missing optional sources (no news key, no network gold feed) | Degrade gracefully: only the available source classes are armed; the monitor continues on the rest. |
| Clock skew | Economic triggers are keyed to UTC-normalized `release_timestamp`; wall-clock sleeps tolerate sub-minute skew. |
| Crash anywhere | `state.json` + ledger persist; restart recovery (§9). |

Design rule: **the monitor must never terminate because a single trigger source or a single run failed.** Failures degrade to log + ledger + backoff.

## 12. Integration with the existing runtime (no changes)

- The monitor invokes `python run.py` exactly as `scripts/run_daily.py:72-76` does (subprocess, `cwd=ROOT`), passing through the same config file. No argument, env, or behavior change to `run.py`.
- After a successful run, the monitor may invoke the **existing** `scripts/generate_institutional_report.py` and `scripts/evaluate_outcome.py` as-is (optional post-steps, mirroring `run_daily`).
- The run registry (`runtime/run_registry.jsonl`) already records `trigger` provenance implicitly via `run_id`/timestamps; the monitor's ledger adds explicit trigger-source provenance without touching the registry contract.

## 13. Acceptance criteria (design-level)

1. A single daemon process sleeps idle and executes `run.py` **unchanged** on: economic release instant, daily slot, ≥2σ XAU/USD move, relevant news.
2. Each economic release and daily slot triggers at most one run (ledger-enforced), including across restarts.
3. Market and news triggers respect their cooldowns; coalesced coincident triggers produce one run.
4. Restart recovery re-arms all unconsumed triggers and never double-fires a consumed key.
5. No existing file, contract, threshold, workflow, or decision logic is modified.
6. All failures degrade to log + ledger + backoff; the daemon never exits on a single-source failure.
