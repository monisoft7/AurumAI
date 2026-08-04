# AurumAI Operation Plan V1

**Objective:** Bring AurumAI to its first successful real execution — running the
production code paths against real, committed repository data and producing real
outputs. This document is an inventory and a blocker ledger only. **No fixes, no
features, no redesigns were performed.**

**Verification basis:** All "VERIFIED" statements below were empirically executed
on 2026-08-03 on this machine (Windows, Python 3.14.4) from the repository root
(`C:\AurumAI\AurumAI`) using the repository's own data files. Both primary
execution paths ran to completion with zero stage errors.

---

## 1. Exact command required to execute AurumAI end-to-end

There is **no packaged CLI**. `pyproject.toml` defines no `[project.scripts]`,
there is no `__main__` entry, and the README documents only the test command.
The exact verified commands are below. All commands run from the repository root
in PowerShell and assume `src/` is on `sys.path` (the commands do this
explicitly, matching `tests/conftest.py`).

### Command A — Canonical inference pipeline (real CPI data) — **VERIFIED COMPLETE**

```powershell
py -3 -c "import sys; sys.path.insert(0, 'src'); from pathlib import Path; from knowledge.events.cpi import CPIEvent; from knowledge.pipeline.context import PipelineContext; from knowledge.pipeline.pipeline import InferencePipeline; ctx = PipelineContext(event=CPIEvent(), event_data_path=Path('data/economic/CPIAUCSL.csv'), gold_path=Path('data/gold.csv'), output_dir=Path('data/output/ops_run_v1'), knowledge_prefix='cpi_gold_summary_v1', condition_columns=('cpi_pressure',), asset='XAU/USD', query='gold outlook after CPI', release_calendar_path=Path('data/calendar/cpi_releases.csv')); r = InferencePipeline().run(ctx); print(r.decision)"
```

Result: completes all 7 stages (`build_lessons`, `build_knowledge`,
`build_graph`, `query_evidence`, `reason`, `decide`); prints a Decision object.
Writes `data/output/ops_run_v1/lessons.csv` and `data/output/ops_run_v1/knowledge.json`.

### Command B — Full institutional orchestrator (25-stage DAG, real data) — **VERIFIED COMPLETE (~57 s)**

```powershell
py -3 -c "import sys, tempfile; sys.path.insert(0, 'src'); from orchestration.orchestrator import InstitutionalOrchestrator; a = InstitutionalOrchestrator.with_default_pipeline().run_all(trigger='manual', force=True, event_type='INTEREST_RATE', data_path='data/economic/FEDFUNDS.csv', gold_path='data/history/gold/gold.csv', output_dir=tempfile.mkdtemp(prefix='aurumai_ops_'), asset='XAU/USD', horizon=12); print('errors:', a.errors); print('decision:', a.outputs['finalize']['decision'])"
```

Result: 25/25 stages status `ok`, zero errors. Final output is an
`InstitutionalAssessment` whose `outputs["finalize"]` contains
`InstitutionalDecision`, `Decision` (legacy), `RiskDecision`,
`ForecastResult`, `ForecastConfidence`, `ForecastValidationReport`,
`ForecastContext`, `RiskMetrics`, `PositionSizing`, `RiskBudget`.

### Command C — Full 7-event-type historical replay (documented "primary production path") — **NOT VERIFIED TO COMPLETE ON REAL DATA**

```powershell
py -3 -c "import sys; sys.path.insert(0, 'src'); from simulation.historical_replay import run_simulation; print(run_simulation().to_dict())"
```

`HistoricalReplayEngine.run_all()` / `run_simulation()` is described as the
primary production path in `docs/CER-006-runtime-architecture-trace.md` (§1) and
`docs/architecture/PROJECT_BLUEPRINT.md`. It replays CPI, NFP, GDP,
INTEREST_RATE, PMI, PPI, FOMC through the orchestrator. Estimated runtime
2.5–3+ hours (130 CPI releases × ~57 s per full orchestrator run; see Blocker B5).
**Not run in this session.**

### Command D — Acceptance gate (documented command, `README.md` line 33) — **COLLECTION VERIFIED**

```powershell
py -3 -m pytest -q
```

Result: 2575 tests collected cleanly with no collection errors
(`tests/test_dummy_event.py` and `tests/test_test_event_event.py` referenced in
`CURRENT_STATE.md` §10 no longer exist). Full-suite pass/fail status was not
re-run in this session.

---

## 2. Required configuration files

| File | Status | Purpose |
|------|--------|---------|
| `pyproject.toml` | Committed | Package layout (`src/`), 10 runtime dependencies, pytest testpaths |
| `.env` | **Gitignored, NOT committed** | `FRED_API_KEY`, `NEWS_API_KEY`; loaded by `src/connectors/fred_client.py:8-11` (`load_dotenv()`) |
| `tests/conftest.py` | Committed | Puts `src/` on `sys.path` for pytest; clears global feature extractors per test |
| Runtime config file (YAML/JSON/Toml consumed at startup) | **Does not exist** | All pipeline configuration is code-level (`PipelineContext`, orchestrator `params` dict) |

There is no scheduler, no service config, no DB config.

---

## 3. Required environment variables

| Variable | Required? | Source | Used by |
|----------|-----------|--------|---------|
| `FRED_API_KEY` | **Yes, if any FRED series is not already cached** | `.env` (gitignored; present on this machine) | `src/connectors/fred_client.py` (fredapi `Fred(api_key=...)`); `FredClient.get_series` reads cache-first from `data/economic/<SERIES>.csv`, falls back to live FRED API |
| `NEWS_API_KEY` | No — declared but **never read by any code** | `.env` (empty) | Nothing (grep across `src/` finds no usage) |
| `PYTHONPATH` | No — commands inject `sys.path.insert(0, 'src')`; pytest uses `conftest.py` | — | — |

---

## 4. Required external services / APIs

| Service | Package/URL | Blocker if down? | Failure mode |
|---------|-------------|------------------|--------------|
| FRED API (fredapi) | `fredapi`, `api.stlouisfed.org` | Only when cache-miss (uncached series or `use_cache=False`) | Raises (no graceful fallback) |
| Federal Reserve FOMC calendar JSON | `https://www.federalreserve.gov/json/calendar.json` (`src/connectors/fomc_calendar.py:12`) | No — committed snapshot `data/calendar/fomc_meetings.csv` fallback (`fomc_calendar.py:68-74`) | Silent fallback to CSV |
| News RSS feeds (feedparser, `src/news/news_collector.py:41-51`) | Public RSS URLs (`src/news/models.py`) | No — `feedparser.parse` returns empty on failure | Silent: zero articles, no exception |
| Yahoo Finance (yfinance) | `yfinance` for DXY (`src/connectors/dxy_fetcher.py`) | Not used by core pipeline | Only used by DXY scripts/adapters |
| HuggingFace `transformers` | NOT installed on this machine | Not used by core path | `src/nlp/fomc_sentiment.py`, `src/nlp/news_sentiment.py` import lazily (inside methods); would `ImportError` only if the never-injected analyzers were invoked (see Blocker B6) |

No broker, no trading API, no LLM API is used. Network is not required for
Commands A and B (all inputs are committed CSVs).

---

## 5. Required input datasets (all committed in git, except where noted)

**Gold**
- `data/gold.csv` — 1566 rows, 2019-01-01 → 2024-12-31, columns `Date, Close` (used by Command A and experiment scripts)
- `data/history/gold/gold.csv` — 2765 rows, 2015-01-02 → 2025-12-31, columns `Date, Open, High, Low, Close, Volume` (used by Command B/C default)

**Event/economic data (`data/economic/`, FRED-cached format `Date,Value`)**
- `CPIAUCSL.csv` (CPI), `PAYEMS.csv` (NFP), `PPIACO.csv` (PPI), `FEDFUNDS.csv` (INTEREST_RATE) — real FRED data
- `DFF.csv`, `DGS10.csv`, `DFII10.csv`, `T5YIE.csv`, `UNRATE.csv` — real FRED data (context/regime inputs; `CompositeScoreBuilder` builds 1386×2 from these — verified)
- **`GDP.csv` (26 rows), `PMI.csv` (36 rows) — SYNTHETIC**, generated by `HistoricalReplayEngine._ensure_synthetic_csvs()` with `numpy.random.default_rng(42)` (`src/simulation/historical_replay.py:480-531`)

**Calendar (`data/calendar/`)**
- `cpi_releases.csv` — 130 releases, 2015-02-01 → 2025-11-01 reference periods (only event type with a release calendar; mapping in `historical_replay.py:558-565`)
- `fomc_meetings.csv` — real FOMC meeting schedule snapshot
- **`FOMC.csv` (66 rows) — SYNTHETIC** (same rng-42 generation)

**Context**
- `data/context/dxy/dxy.csv` — DXY history (used only by standalone scripts/adapters, not the core pipeline)

All datasets are tracked in git (`git ls-files data` → 99 files).

---

## 6. Expected outputs

**Command A** (`data/output/ops_run_v1/`):
- `lessons.csv` (event × horizon lessons), `knowledge.json` (aggregated knowledge records)
- Console: `Decision` object (verified: `POSITIVE` with default horizons; `STRONG_POSITIVE` with `horizons=(5, 20)` — deterministic given identical inputs)

**Command B** (console `InstitutionalAssessment`):
- `outputs["finalize"]` with: `InstitutionalDecision`, legacy `Decision`, `RiskDecision`, `ForecastResult`, `ForecastConfidence`, `ForecastValidationReport`, `ForecastContext`, `RiskMetrics`, `PositionSizing`, `RiskBudget`
- Per-stage `StageRecord` list — verified 25/25 `ok`

**Command C** (`SimulationReport.to_dict()`):
- Per-event `EventRunResult` (7 event types) with decision, forecast confidence, validation, risk metrics, OOS correctness fields; aggregated `OOSSummary`, `ForecastAccuracySummary`, `RiskSummary`
- Side effect: `data/economic/GDP.csv`, `data/economic/PMI.csv`, `data/calendar/FOMC.csv` are (re)created with synthetic rng-42 data if absent (`_ensure_synthetic_csvs`)

**Command D**: pytest summary — 2575 collected (verified); full-suite result not re-verified this session (historical claims in `docs/Wave-2D-Completion.md` cite 1990 passed + 3 pre-existing failures; those 3 files have since changed — `test_release_calendar` collection is clean now).

---

## 7. Expected execution order

1. **Prepare environment** — create `.env` with `FRED_API_KEY` (not in git); install dependencies per `pyproject.toml` (`pip install -e .` or `pip install` of the 10 listed packages; verified working set on Python 3.14.4: pandas 2.3.3, numpy 2.4.4, networkx 3.6.1, statsmodels 0.14.6, statsforecast 2.1.1, feedparser 6.0.12, fredapi 0.5.2, python-dotenv 1.2.2, requests 2.34.2, yfinance 1.5.1).
2. **Acceptance gate** — Command D (`py -3 -m pytest -q`).
3. **Canonical pipeline** — Command A (fast, produces the first real knowledge artifacts).
4. **Full institutional orchestrator** — Command B (~1 min, single event type).
5. **Full historical replay** — Command C (hours; see Blocker B5). Run after B succeeds so the heavy loop starts from a proven base.
6. **Optional data refresh** (network required): `scripts/download_fomc_calendar.py`, `scripts/download_dxy.py`; FRED refresh via `EconomicDataFetcher.refresh_cache()`.

---

## 8. Blockers preventing the first successful real execution

### B1 — No executable entry point / no defined run command — **MISSING CONFIGURATION**
- Evidence: `pyproject.toml` has no `[project.scripts]`; no `__main__.py` anywhere (`src/` has a single top-level `__init__.py`); README documents only `py -3 -m pytest -q`; every prior "run" is a test, an experiment script with synthetic data, or an ad-hoc invocation.
- Impact: the operator cannot execute AurumAI end-to-end without hand-assembling a driver; Commands A/B in §1 are the only verified exact commands, and neither is packaged or documented in-repo.
- Location: `pyproject.toml:1-33`, `README.md:32-34`.

### B2 — `.env` is gitignored; `FRED_API_KEY` absent on any fresh machine — **MISSING CONFIGURATION**
- Evidence: `.gitignore` excludes `.env`; `.env` is not in `git ls-files`. `FredClient` passes the key to `Fred()` (fredapi raises without one) whenever a FRED series is not already cached (`src/connectors/fred_client.py:28,54-63`).
- Impact: any execution that triggers a FRED cache-miss (uncached series, `refresh_cache()`, or an empty `data/economic/`) fails immediately. Commands A/B currently pass only because cached CSVs are committed.
- Location: `.gitignore`, `src/connectors/fred_client.py:8-11,23-65`.

### B3 — GDP, PMI, FOMC input datasets are synthetic, not real — **MISSING DATA**
- Evidence: `data/economic/GDP.csv` (26 rows), `data/economic/PMI.csv` (36 rows), `data/calendar/FOMC.csv` (66 rows) are rng-42-generated fillers written by `HistoricalReplayEngine._ensure_synthetic_csvs()` (`src/simulation/historical_replay.py:100-125,480-531`); the engine **actively overwrites** the repo `data/` tree with synthetic files when real files are absent. Only CPI has a release calendar (`_release_calendar_path_for` maps CPI only).
- Impact: 3 of 7 event types in Command C are replayed against fabricated data; a "real" execution does not exist for these events.
- Location: `src/simulation/historical_replay.py:100-125,480-531,558-565`; `data/economic/GDP.csv`, `data/economic/PMI.csv`, `data/calendar/FOMC.csv`.

### B4 — DXY context enrichment is not wired into the pipeline — **MISSING CONNECTOR**
- Evidence: `PipelineContext` (`src/knowledge/pipeline/context.py:10-36`) has `yield_data_path` but no `dxy_data_path`; `DXYContextEnricher` (`src/knowledge/context/dxy.py`) is reachable only from standalone scripts (`scripts/dxy_capability.py`, `scripts/download_dxy.py`). Confirmed independently by `docs/CER-006-runtime-architecture-trace.md` §8.11.
- Impact: any end-to-end definition that includes DXY context cannot run through the canonical path (Command A/B); DXY is limited to script-only runs with hardcoded configs (duplicate-knowledge risk, CER-006 §6.2).

### B5 — Primary production path (Command C, `run_simulation`) is unverified on real data and impractical at full scope — **PRODUCTION BUG**
- Evidence: (a) no completion artifact exists in-repo — `data/output/` contains only `gate6/` and `dxy_capability/` results, never a replay/SimulationReport output; (b) measured single-orchestrator cost ≈ 57 s (verified) × 130 CPI releases ≈ 2+ hours for CPI alone, ~2.5–3+ h total; (c) the replay passes `force=True` and builds a fresh orchestrator per release (`src/simulation/historical_replay.py:727-749`), disabling the cache/checkpoint machinery (`src/orchestration/orchestrator.py:161-188`) that exists specifically to reuse work; (d) it silently injects synthetic files into the committed `data/` tree (see B3).
- Impact: the documented primary production path has never produced a first successful real execution; nothing in the repo proves it terminates on real data.

### B6 — `transformers` runtime dependency missing for optional NLP capabilities — **MISSING RUNTIME DEPENDENCY**
- Evidence: `pip show transformers` → not installed; `src/nlp/fomc_sentiment.py:7-8,38-39` and `src/nlp/news_sentiment.py:7-8,38-39` import it lazily (TYPE_CHECKING / inside methods). `pyproject.toml` does not list it.
- Impact: non-blocking for Commands A–D (verified imports succeed, analyzers never injected); any future wiring of `FOMCSentimentAnalyzer`/`NewsSentimentAnalyzer` fails at call time with `ImportError`.

### B7 — Declared-but-unused `NEWS_API_KEY`; no NewsAPI-style connector — **MISSING CONNECTOR** (non-blocking)
- Evidence: `.env` declares `NEWS_API_KEY=` (empty); no code reads it. News ingestion is RSS-only (`src/news/news_collector.py:41-51`) and degrades silently to zero articles offline.
- Impact: none on Commands A–D; flagged because the `.env` contract implies an API-keyed news connector that does not exist.

---

**Not blockers (verified working):**
- Python 3.14.4 + statsforecast 2.1.1 (no numba wheel needed) — imports and forecast stages run.
- `CompositeScoreBuilder`/macro-regime initialization — builds 1386×2 from committed CSVs.
- Offline execution of Commands A/B — all inputs are committed files; only FOMC refresh and RSS are network-dependent, both degrade safely.
- 2575-test collection — clean (the `--ignore` flags mandated by `CURRENT_STATE.md` §10 for removed legacy test files are no longer needed).
