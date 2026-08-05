# Gold Data Provider V1 (Design)

Status: Proposed. Design only — no implementation, no code.

## 0. Audit summary (what already exists)

Findings from the codebase audit (baseline git HEAD `78c9ad4`):

1. **No production connector maintains gold OHLCV history.** `data/history/gold/gold.csv`
   (2765 rows, 2015-01-02 → 2025-12-31, schema `Date,Close,High,Low,Open,Volume`) is
   static. No code in `src/` or `scripts/` writes it. The only writers of gold CSVs are
   simulation scratch files under temp dirs (`src/simulation/historical_replay.py:723-725`,
   `1555-1556`).
2. **A real market-data layer already exists for other instruments:**
   - `src/connectors/dxy_fetcher.py` — yfinance (`DX-Y.NYB`) daily close series.
   - `src/connectors/fred_client.py` — FRED series with local CSV cache (`fred_client.py:63`).
   - `src/connectors/real_yield_fetcher.py` — yfinance/FRED yield series.
   - `src/connectors/fomc_calendar.py` — FOMC calendar with CSV cache (`fomc_calendar.py:157`).
   - `src/pre_market/overnight_fetcher.py` — yfinance batch incl. gold ticker `GC=F`
     (`OVERNIGHT_TICKERS`, `overnight_fetcher.py:13`).
   - `src/pre_market/positioning.py` — yfinance short-window calls for `GC=F`, `GLD`, `IAUM`.
   - `src/connectors/cb_gold_fetcher.py` — **central-bank gold holdings**, not price history.
   - `scripts/download_dxy.py` — one-shot yfinance→CSV download for DXY (closest precedent;
     no lifecycle, no merge, no validation).
3. **`yfinance` is the established market-data dependency** (declared in
   `pyproject.toml:16`), is already used for gold ticker `GC=F`, and the existing
   `gold.csv` values carry yfinance float artifacts (e.g. `1203.9000244140625`),
   indicating the same origin.
4. **Consumers of `gold.csv` (unchanged interface):**
   - `src/orchestration/stages.py:165` (`_forecast`, `parse_dates=["Date"]`, `y=Close`),
     `:196` (`_forecast_confidence`), `:241` (`_forecast_validation`), `:258` (`_build_context`).
   - `src/simulation/historical_replay.py:51,67` (default `data/history/gold/gold.csv`).
   - `src/knowledge/builders/lesson_builder.py:19` (default path).
   - Scripts: `scripts/dxy_capability.py:32`, `scripts/gate6_validation.py:16`,
     `scripts/run_experiment_002.py:63`.
5. **Conclusion:** no gold-history connector exists (requirement 4 not satisfied), so the
   smallest additive **Gold Data Provider** is designed (requirement 5). It reuses the
   existing data-source layer (`yfinance` + ticker `GC=F`) rather than introducing a new
   library or API.

## 1. Data source

| Item | Choice | Rationale |
|---|---|---|
| Instrument | COMEX gold futures front month `GC=F` | Already the codebase's gold ticker (`overnight_fetcher.py:13`, `positioning.py:21`); matches existing `gold.csv` provenance. |
| Vendor/library | `yfinance` | Declared dependency (`pyproject.toml:16`); used by `dxy_fetcher.py`, `overnight_fetcher.py`, `positioning.py`, `scripts/download_dxy.py`. No API key required. |
| Fields | Daily OHLCV: `Date, Open, High, Low, Close, Volume` | Superset of the required schema; mapped to `gold.csv` column order `Date,Close,High,Low,Open,Volume` (unchanged). |
| Granularity | Daily bars (timezone-naive trading dates) | Matches existing rows (business days). |
| Coverage | Full history from `period="max"` (or explicit start = earliest local date) | Enables forward-only merge with the existing file. |

Design note: reusing `GC=F`/`yfinance` does not duplicate functionality — no existing
code fetches full OHLCV gold history; the provider adds only the missing
download→merge→validate→commit lifecycle.

## 2. Update lifecycle

Runs before every production run, as a standalone step (see §5). Sequence:

1. **Load local history** — read `data/history/gold/gold.csv` if present. Missing file is
   allowed (bootstrap case).
2. **Fetch remote** — request `GC=F` daily bars from yfinance (full history). Empty/failed
   response short-circuits to the failure policy (§4).
3. **Normalize** — map remote frame to the existing schema
   `Date,Close,High,Low,Open,Volume`; dates normalized to `YYYY-MM-DD` strings; numeric
   fields coerced to `float`.
4. **Merge (forward-only append)**:
   - Keep every existing local row unchanged.
   - Append only remote rows whose date is strictly greater than the local max date.
   - Backfill an internal local gap (date present remotely, absent locally) **only** when
     it does not replace an existing local row.
   - Never reorder, drop, or overwrite existing local rows.
5. **Validate** the merged frame (§3).
6. **Commit atomically** — write to a sibling temp file, then `os.replace` onto
   `gold.csv` (same filesystem → atomic). No commit on validation failure.
7. **Report** status: `{status, rows_added, last_date, source, timestamp}` to the run log
   (and the run manifest if the caller persists it).

Idempotency: a refresh with no new remote rows yields a no-op commit and `rows_added=0`.

## 3. Validation rules

All must pass before commit; a failure routes to §4.

1. **Schema** — columns exactly `Date,Close,High,Low,Open,Volume`; `Date` non-empty strings.
2. **Chronology** — strictly increasing dates; no duplicates; no out-of-order rows.
3. **Completeness** — no empty/missing `Close`; `Open/High/Low/Close` non-null and finite.
4. **Price sanity** — all four prices `> 0`; `High >= max(Open, Close)`;
   `Low <= min(Open, Close)`.
5. **Non-shrink** — merged row count `>=` previous local row count, and previous local max
   date must still be present. Never overwrite valid history with a shorter dataset.
6. **Continuity** — merged first date equals prior first date (or is set on bootstrap);
   merged last date `>=` prior last date.

## 4. Failure policy

- **Fetch fails (network/API/library error or empty payload):** log a warning; leave
  `gold.csv` untouched; return `status="skipped"`. The production run proceeds on the
  existing dataset (fail-open for data freshness; forecast may be stale but the pipeline
  is never blocked or corrupted).
- **Validation fails (chronology, prices, shrink, schema):** abort commit; delete the
  temp file; leave `gold.csv` untouched; return `status="failed"`. A pre-commit copy of
  the previous file is retained as `gold.csv.bak` from the last successful refresh (if
  one exists) for manual inspection.
- **Atomic-write failure:** the temp file is removed; the existing file is untouched
  (guaranteed by `os.replace` semantics); run proceeds.
- **Offline mode:** explicit `--no-refresh`/`no_refresh` flag skips the step entirely and
  runs on the existing file (still successful).

The invariant in every failure path: **the previous valid dataset is always preserved and
readable.**

## 5. Integration point

- **Invocation:** at the start of a production run, before the pipeline executes
  (`orch.run_all`), in the run entry points that currently launch the pipeline
  (`run.py` around the config load / `run_all` call at `run.py:382-413`, and
  `scripts/run_daily.py`). A `--no-refresh` flag disables it.
- **Not a DAG stage:** explicitly NOT a new `PipelineJob` — orchestration
  (`src/orchestration/orchestrator.py`, `stages.py`) is out of scope and must not change.
  The provider is a pre-run step that maintains the same file the stages already read.
- **Module placement:** `src/connectors/gold_data_provider.py` (consistent with
  `dxy_fetcher.py`, `fred_client.py`, `real_yield_fetcher.py`), exposing
  `refresh() -> Report` and importing `yfinance` the same way existing connectors do.
- **Interface contract:** file path `data/history/gold/gold.csv` and schema
  `Date,Close,High,Low,Open,Volume` are unchanged, so all consumers listed in §0 (4)
  work with zero code changes.

## 6. Acceptance criteria

1. **Freshness:** after an online refresh, `gold.csv` max date equals the most recent
   `GC=F` trading date available from yfinance at that moment.
2. **Preservation:** every pre-existing row is byte-identical after refresh; row count is
   monotonically non-decreasing.
3. **Chronology:** merged file passes §3 rules (strictly increasing dates, no dupes).
4. **Non-shrink:** a simulated shorter remote dataset (or truncation) does not reduce row
   count and never removes the prior max date.
5. **Fail-safe:** simulated fetch failure (network error, empty payload) and validation
   failure both leave `gold.csv` untouched and the run still completes (status
   `skipped`/`failed` recorded, not `ok`).
6. **Idempotency:** two consecutive refreshes with no new data produce identical file
   state and `rows_added=0`.
7. **Bootstrap:** with `gold.csv` absent, an online refresh creates a valid file
   satisfying §3; an offline run with no file fails with a clear message (no
   semi-written file left).
8. **No regressions:** `_forecast`, `forecast_confidence`, `forecast_validation`,
   `build_context`, `historical_replay`, and `lesson_builder` consume the refreshed file
   with zero code changes; forecast/decision/confidence/threshold/orchestration files are
   unmodified.

## 7. Method and sources

- Connector inventory: `src/connectors/*.py`, `src/pre_market/overnight_fetcher.py`,
  `src/pre_market/positioning.py`, `scripts/download_dxy.py`.
- Consumer inventory: `src/orchestration/stages.py:165,196,241,258`,
  `src/simulation/historical_replay.py:51,67`, `src/knowledge/builders/lesson_builder.py:19`,
  scripts referenced in §0 (4).
- Dependency evidence: `pyproject.toml:16`.
- Data evidence: `data/history/gold/gold.csv` (schema, range, yfinance float artifacts).
- Prior audit: `docs/audit/FORECAST_PIPELINE_AUDIT_001.md` (stale-gold findings),
  `docs/audit/POSITION_SIZING_AUDIT_001.md`, `docs/audit/RUNTIME_TRACE_AUDIT_001.md`.
