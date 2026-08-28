# AurumAI Daily Operations (Cloud)

Scheduled cloud execution of the existing daily workflow
(`python scripts/run_daily.py`) via GitHub Actions. The workflow changes no
production semantics — it runs the same entry point as the local path.

Workflow file: `.github/workflows/aurumai-daily.yml`

## Manual trigger

1. Open the repository on GitHub → **Actions** → **AurumAI Daily Operations**.
2. Select **Run workflow** → choose the `funding-preparation` (or `main`)
   branch → **Run workflow**.
3. Or via CLI:

   ```sh
   gh workflow run aurumai-daily.yml --ref funding-preparation
   gh run watch
   ```

Note: scheduled (cron) triggers only fire from the workflow file present on
the **default branch** (`main`). Until the workflow is merged to `main`, use
manual `workflow_dispatch` runs.

## Required GitHub Secrets

Set under Settings → Secrets and variables → Actions:

| Secret                | Required | Effect when missing                                    |
|-----------------------|----------|--------------------------------------------------------|
| `FRED_API_KEY`        | soft     | Warns; falls back to committed CSV data caches          |
| `TELEGRAM_BOT_TOKEN`  | optional | Telegram steps report "not configured"; run succeeds    |
| `TELEGRAM_CHAT_ID`    | optional | (as above)                                              |

`NEWS_API_KEY` is **not** consumed by the runtime and must not be added.
Secrets are injected as environment variables only; they are never echoed,
logged, or committed.

## Schedule

- Cron `0 22 * * 1-5` — **22:00 UTC, Monday–Friday**.
- After the US gold session close (daily bar final) and before 24:00 UTC so
  the UTC runner's `date.today()` matches the trading date measured.
- Weekdays only: gold market data does not advance on weekends.

## Where outputs appear

Each run uploads an artifact `aurumai-outputs-<run_id>` containing
`outputs/<date>/<run_id>/`:

- `outcome.json`, `outcome.evaluated.json` (when the horizon elapsed)
- `daily_operational_summary.json`
- `finalize.json`, `summary.json`, `stages.json`
- `institutional_report.md/.html`, `run.log`
- `artifacts/` (technical assessment, trade recommendation, …)

Retention is 30 days (configurable via the `ARTIFACT_RETENTION_DAYS` env in
the workflow).

## Failure interpretation

- The job fails if `run_daily.py` exits non-zero (pipeline, report, or
  registry verification failed). The run outputs are still uploaded
  (`if: always()`) — inspect `run.log` and `stages.json` for the failing
  stage.
- Data refresh failures (FRED / yfinance) are fail-safe inside the pipeline:
  the run proceeds on committed caches and degrades rather than crashes.
- Telegram failures never fail the run (output channel only).
- Re-running a failed job is safe; the state cache prevents duplicate
  registry records from being misread (one append per successful run).

## State persistence (calibration / outcomes / registry)

Mutable state is carried between runs with a rolling `actions/cache` entry:

- `runtime/run_registry.jsonl`
- `runtime/calibration.json`
- `outputs/**/outcome.json` (pending decisions awaiting their horizon)
- `outputs/**/outcome.evaluated.json` (scored history)

Safety properties (from the existing contracts):

- `outcome.evaluated.json` records are immutable once written.
- `runtime/calibration.json` is fully recomputed from evaluated outcome
  records (deduplicated by `decision_id`), so a restored cache cannot corrupt
  calibration mathematics.
- No generated runtime/output/data files are committed back to Git.

If the cache is ever lost, the system degrades safely: calibration returns
`oos_ece: None` (pre-hardening behaviour) until ≥10 scored samples re-accrue,
and the registry readers treat missing history as empty.

### Deterministic state recovery

The cache rolls state forward correctly, but its failures are silent (an
evicted or failed snapshot makes the next run restore an older one, and >7
days without a run evicts CI-side state). Therefore every run also uploads
an immutable backup artifact `aurumai-state-backup-<run_id>` (90-day
retention) containing:

- `runtime/run_registry.jsonl`
- `runtime/calibration.json`
- `outputs/**/outcome.json`
- `outputs/**/outcome.evaluated.json`

To recover deterministically after cache loss:

1. Download the newest `aurumai-state-backup-*` artifact from the Actions
   tab (or `gh run download <run-id> -n aurumai-state-backup-<run-id>`).
2. Unpack it over the repository checkout before the next run — restoring
   is lossless because evaluated outcome records are immutable and
   deduplicated by `decision_id`, and calibration is recomputed from them.

## Concurrency

The `aurumai-daily-operations` concurrency group queues overlapping runs
(`cancel-in-progress: false`), guaranteeing at most one daily run writes the
registry/calibration state at a time.
