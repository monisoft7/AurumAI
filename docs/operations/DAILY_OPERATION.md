# AurumAI Daily Operation

This document describes how to operate the daily institutional run through
the scheduler `scripts/run_daily.py`, schedule it with Windows Task Scheduler
or Linux cron, choose an execution time, and understand failure behavior.

## Overview

`scripts/run_daily.py` runs the complete daily workflow:

1. Executes `run.py` (the runtime entry point) and waits for completion.
2. Generates the Institutional Daily Report
   (`outputs/YYYY-MM-DD/institutional_report.md` and `.html`) from the fresh
   run outputs.
3. Verifies the run:
   - pipeline exit code is `0`
   - `institutional_report.md` exists and is non-empty
   - exactly one new immutable record was appended to
     `runtime/run_registry.jsonl` for this run directory
4. Prints a concise execution summary and exits with a proper exit code.

Manual invocation:

```
python scripts/run_daily.py
```

## Recommended execution time

The pipeline analyzes economic data releases (e.g., CPI, interest rates).
Most US economic data releases at 08:30 ET should be reflected in the run,
so the recommended execution time is:

- **09:00 ET, daily** — after the 08:30 ET data release window and before
  the US market open. On days without releases the run simply uses the
  latest committed/cached data.
- Runs take roughly **50-60 seconds**, so a 09:00 start finishes well before
  any market-open dependency.
- The run uses committed data files under `data/` (plus `.env` credentials
  for live refreshes when set); it does not depend on market hours.

## Windows Task Scheduler

### Option A: `schtasks` (command line)

Run PowerShell as Administrator:

```powershell
schtasks /Create /TN "AurumAI Daily Run" /TR "cmd /c cd /d C:\AurumAI\AurumAI && C:\Python314\python.exe scripts\run_daily.py" /SC DAILY /ST 09:00
```

Notes:

- Replace `C:\AurumAI\AurumAI` with the repository path and
  `C:\Python314\python.exe` with the interpreter that has the project
  dependencies installed.
- The `cmd /c cd /d ... && ...` wrapper fixes the working directory, which
  `run_daily.py` requires (paths are resolved relative to the repo root).
- Verify: `schtasks /Query /TN "AurumAI Daily Run"` and run once manually
  with `schtasks /Run /TN "AurumAI Daily Run"`.
- Remove when needed: `schtasks /Delete /TN "AurumAI Daily Run" /F`.

### Option B: Task Scheduler GUI

1. Open **Task Scheduler** → **Create Basic Task**.
2. Name: `AurumAI Daily Run` → **Daily**.
3. Start time: `09:00` (see recommended execution time).
4. Action: **Start a program**.
   - Program/script: `C:\Python314\python.exe`
   - Arguments: `scripts\run_daily.py`
   - Start in: `C:\AurumAI\AurumAI`
5. Finish. Optionally check the task's history or run it with **Run** to
   confirm success.

## cron (Linux)

Add a crontab entry (server local time):

```cron
30 8 * * * cd /opt/AurumAI && /usr/bin/python3 scripts/run_daily.py >> /var/log/aurumai_daily.log 2>&1
```

Notes:

- Adjust the path (`/opt/AurumAI`) and interpreter (`/usr/bin/python3`) to
  the environment.
- cron uses the **server's local time**; adjust the hour so the run starts
  after the 08:30 ET data release window in the server timezone.
- Install with `crontab -e`; view with `crontab -l`.
- Redirect `stdout`/`stderr` to a log file as shown; `run_daily.py` prints
  the daily summary there too.

## Failure behavior

| Scenario | Behavior |
| --- | --- |
| Pipeline fails (`run.py` exit code non-zero) | Report generation and registry verification are skipped; scheduler exits `1`. |
| Report generation fails | Scheduler exits `1`; the registry still holds the pipeline record (the run itself succeeded). |
| Registry record missing | Scheduler exits `1`; the pipeline record is appended only by a successful `run.py`, so investigate `run.log`/registry before rerunning. |
| Precondition error (missing `run.py` or report script) | Scheduler exits `2` without executing anything. |
| Success | Scheduler exits `0`; one immutable record is appended to `runtime/run_registry.jsonl`. |

Exit codes used by the scheduler:

- `0` — daily run completed and verified
- `1` — pipeline failed or verification failed
- `2` — scheduler precondition error

Recovery:

- Re-run manually with `python scripts/run_daily.py` (idempotent: each run
  appends its own record and overwrites the same day's output directory).
- Inspect the run log: `outputs/YYYY-MM-DD/run.log`.
- Inspect run history: `python scripts/show_run_history.py`.
- Prerequisites: `.env` with `FRED_API_KEY` (optional for cached data),
  committed data files under `data/`, and dependencies installed in the
  interpreter used by the scheduled task.
