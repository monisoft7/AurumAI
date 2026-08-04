# AurumAI Runtime Guide

The official runtime entry point for AurumAI. It loads configuration, validates
the environment, executes one complete institutional run through the existing
`InstitutionalOrchestrator` (25-stage DAG), persists every output under
`outputs/YYYY-MM-DD/`, and prints a concise execution summary.

The runtime layer **does not** modify any analysis algorithm, workflow, or
contract. It only wires the existing production paths.

## Requirements

- Python `>=3.10` (verified on Python 3.14.4)
- Runtime dependencies declared in `pyproject.toml`
- Working directory: repository root (`C:\AurumAI\AurumAI`)

## Files

| File | Role |
|------|------|
| `run.py` | Single executable entry point |
| `runtime_config.json` | Default runtime configuration (JSON) |
| `.env` | Environment variables (gitignored; see below) |
| `outputs/YYYY-MM-DD/` | Per-day output directory (created automatically) |

## Exact command

```powershell
python run.py
```

or, with an explicit interpreter and configuration:

```powershell
py -3 run.py
py -3 run.py --config runtime_config.json
py -3 run.py --config C:\path\to\other_config.json
```

`--config` is relative to the current working directory; the default is
`runtime_config.json` in the repository root. Paths **inside** the config file
(except `output_base_dir` and `checkpoint_dir`) are resolved against the
repository root.

## Environment variables

| Variable | Status | Behavior when missing |
|----------|--------|------------------------|
| `FRED_API_KEY` | Required (for live FRED refreshes) | Warning only — the run proceeds on the committed cached CSVs in `data/economic/`; any uncached FRED request would fail |
| `NEWS_API_KEY` | Optional | No effect; currently not consumed by the runtime |

Variables are loaded from `.env` (repo root) via `python-dotenv` before
validation. `.env` is gitignored — create it locally:

```
FRED_API_KEY=your_key_here
```

## Configuration reference (`runtime_config.json`)

| Key | Default | Description |
|-----|---------|-------------|
| `event_type` | `CPI` | Event type; must be one of: `CPI, FOMC, GDP, INTEREST_RATE, NFP, PMI, PPI` |
| `data_path` | `data/economic/CPIAUCSL.csv` | Raw event data CSV (columns `Date,Value`) |
| `gold_path` | `data/history/gold/gold.csv` | Gold price CSV (column `Close` required) |
| `gold_lessons_path` | `null` | Optional full-history gold CSV for lesson labels (used by release-by-release paths) |
| `release_calendar_path` | `data/calendar/cpi_releases.csv` | Optional release calendar CSV (canonical institutional path); `null` selects the legacy lesson builder |
| `yield_data_path` | `null` | Optional US10Y yield CSV for `YieldContextEnricher` |
| `output_base_dir` | `outputs` | Root under which `YYYY-MM-DD/` directories are created |
| `asset` | `XAU/USD` | Asset identifier passed through the pipeline |
| `horizon` | `12` | Forecast horizon (months) |
| `max_workers` | `4` | Orchestrator thread-pool size |
| `checkpoint_dir` | `null` | Optional checkpoint directory (default: temp, discarded) |
| `trigger` | `runtime` | Run trigger label recorded in the assessment |
| `query` | `""` | Query string passed to the decision context |

Missing files, unknown event types, and invalid numeric values abort the run
with exit code `2` and a descriptive error.

## Outputs — `outputs/YYYY-MM-DD/`

```
outputs/2026-08-03/
├── run.log            # Full debug-level log of the run
├── config.json        # Effective configuration used (incl. resolution notes)
├── summary.json       # Concise machine-readable execution summary
├── stages.json        # Per-stage records (stage_id, status, duration_ms, error)
├── finalize.json      # Serialized finalize stage: decision, forecast, risk
│                      #   (InstitutionalDecision, legacy Decision, RiskDecision,
│                      #    ForecastResult, ForecastConfidence,
│                      #    ForecastValidationReport, ForecastContext,
│                      #    RiskMetrics, PositionSizing, RiskBudget)
└── artifacts/
    ├── lessons.csv    # Pipeline lesson artifacts
    └── knowledge.json # Aggregated knowledge records
```

Repeated runs on the same day share one output directory; each run writes its
own `run.log` entries and overwrites the machine-readable JSONs with its own
results.

## Execution summary

The console prints, after the run:

- Pipeline ID and trigger
- Event type and stage record counts (`ok` / `failed` / `cached`)
- Errors (if any)
- Decision label and confidence
- Output directory and wall time
- Overall result (`SUCCESS` / `FAILED`)

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Run completed; all stages `ok`, no errors |
| `1` | Run completed with stage failures or errors (details in `stages.json` / `summary.json`) |
| `2` | Configuration or environment validation failed before execution |

## Notes

- Offline execution works: all inputs are committed repository CSVs; only FOMC
  calendar refresh and news RSS fetch touch the network, and both degrade
  silently (committed snapshot / empty feed).
- The orchestrator executes the full 25-stage DAG (pre-market scan → signal
  assessment → event triage → evidence collection/reasoning → thesis
  construction/update → scenario generation → confidence → risk/reward
  validation → bias prevention → decision engine → trade recommendation, plus
  legacy inference pipeline, forecasting, and risk gate). Expected runtime is
  roughly one minute per run.
- `data/economic/GDP.csv`, `data/economic/PMI.csv`, and `data/calendar/FOMC.csv`
  are synthetic (deterministic, seed 42) placeholder datasets — see
  `docs/operations/OPERATION_PLAN_V1.md` (Blocker B3).
