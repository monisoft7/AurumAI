# AurumAI Institutional Validation Protocol — V1

**Program:** Institutional Validation Program
**Protocol version:** V1
**Duration:** 30 consecutive calendar days
**Proposed start:** Day 1 = 2026-08-04 (the operator may shift Day 1 to the
first calendar day on which the protocol is fully active)
**Owner:** THE BLU WALF (repository owner and escalation point)
**Scope:** validation of the daily institutional output only — observation
and review of existing artifacts. This protocol makes **no code changes, no
test changes, no algorithm, workflow, report, or architecture changes**.

## Operating assumptions

- AurumAI runs **every calendar day** via `scripts/run_daily.py`.
- Each day produces **exactly one institutional report**:
  `outputs/YYYY-MM-DD/institutional_report.md` (and `.html`).
- Each successful run appends **exactly one immutable record** to
  `runtime/run_registry.jsonl`.
- All validation activity uses artifacts that already exist; nothing in
  this protocol requires implementation work.

## Validation principles

1. **Observational only.** The program reads existing outputs; it never
   recomputes pipeline internals and never alters them.
2. **Ground truth is external.** Decisions and forecasts are compared
   against realized outcomes (gold prices, released economic data), not
   against pipeline internals.
3. **Traceable.** Every finding is recorded with the run date, run_id, and
   artifact path it refers to.
4. **No silent fixes.** Any defect discovered is escalated per Section 11;
   changes, if any, are made only after escalation resolution.

---

## 1. Daily execution schedule

| Time (ET) | Action | Tool / artifact | Max duration |
| --- | --- | --- | --- |
| 09:00 | Scheduled daily run starts | `python scripts/run_daily.py` (Task Scheduler / cron per `docs/operations/DAILY_OPERATION.md`) | — |
| 09:05 | Confirm run completed (expected total ~1–2 minutes) | Exit code printed by scheduler; `outputs/YYYY-MM-DD/summary.json` | 2 min |
| 09:10 | Daily review (Section 6) | Report + registry + `run.log` | 10 min |
| 09:20 | Record checklist results | Validation log artifact (Section 12) | 5 min |
| 09:30 | Ad-hoc escalation work, if any (Section 11) | Escalation log artifact | as needed |

The recommended daily run time is **09:00 ET** (after the 08:30 ET US
economic data release window). Days without releases still produce a run on
committed/cached data.

## 2. Data sources used

The program validates against the same sources the pipeline consumes, plus
realized outcomes:

| Source | Path / mechanism | Role in validation |
| --- | --- | --- |
| CPI series | `data/economic/CPIAUCSL.csv` | Event input for CPI runs |
| Interest rate series | `data/economic/FEDFUNDS.csv` | Event input for INTEREST_RATE runs |
| Gold price history | `data/history/gold/gold.csv` | Realized outcomes for forecast/decision comparison |
| Release calendars | `data/calendar/*.csv` | Event timing cross-check |
| Live refresh (when `.env` set) | `FRED_API_KEY` via `run.py` | Not required for validation; cached data is authoritative for the program |
| News / FOMC sentiment | nlp analyzers (when feeds available) | Context fields `news_mood`, `fomc_mood` in `finalize.json` |
| Run outputs | `outputs/YYYY-MM-DD/{config,summary,stages,finalize}.json`, `run.log`, `artifacts/` | Primary validation inputs |
| Institutional report | `outputs/YYYY-MM-DD/institutional_report.md` | The daily deliverable under review |
| Run registry | `runtime/run_registry.jsonl` | Execution history, trend metrics |
| Registry tooling | `scripts/show_run_history.py` | Weekly/monthly statistics |

## 3. Events to monitor

### 3.1 External economic events

- US CPI release (08:30 ET, ~mid-month) — focal event for CPI runs.
- FOMC / interest-rate decisions (08:30 ET or 14:00 ET, ~8×/year).
- Other 08:30 ET releases (payrolls, PCE, retail sales) and their effect on
  regime/context fields.
- Gold market moves on release days vs the run's thesis direction and
  decision.

### 3.2 Pipeline and delivery events

- Any stage status other than `ok` in `stages.json` (25 stages expected).
- `forecast_validation` reporting `sample_size = 0` / `passed = false`
  (currently expected; progress toward aligned forecast-actual pairs must
  be tracked).
- Non-convergence or `ValueWarning`/`ConvergenceWarning` entries in
  `run.log`.
- Regime label changes (`context.current_regime`) between consecutive days.
- Decision type changes (e.g., repeated `NO_TRADE` → directional) and
  confidence movements of material size between days.
- `bias_review` findings and `human_review_flag = true` in
  `decision.metadata`.
- Registry append failures; Telegram delivery failures
  (`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` configured or not).

## 4. Validation methodology

### 4.1 Daily verification (execution layer)

For every day the program is active, confirm the scheduler's three
verification gates all passed:

1. Pipeline exit code `0`.
2. `institutional_report.md` exists and is non-empty.
3. Exactly one new registry record was appended with
   `output_directory` = `outputs/YYYY-MM-DD`.

Source: the scheduler summary (`scripts/run_daily.py`) and
`runtime/run_registry.jsonl`.

### 4.2 Daily report verification (output layer)

- All 14 report sections are present (Executive Summary → Provenance
  Summary).
- Every figure in the report matches the corresponding field in
  `summary.json`, `finalize.json`, and the registry record for the same
  run (report numbers are transformed, not invented; spot-check the
  decision, confidence, regime, and risk metrics).
- `decision` and `decision_confidence` in the registry match the report's
  Executive Summary.

### 4.3 Rolling outcome validation (ground-truth layer)

As realized data becomes available after each run:

- **Decision direction check.** Compare the thesis direction
  (`selected_thesis_direction`) and decision (`BUY`/`SELL`/`HOLD`/
  `NO_TRADE`) against subsequent gold price movement from
  `data/history/gold/gold.csv` over the report's horizon.
- **Forecast accuracy check.** When aligned forecast–actual pairs exist
  (the pipeline's `validation` block reports `sample_size`), record
  `rmse`, `mae`, `mape`, `coverage`, `directional_accuracy` from
  `finalize.json`.
- **Confidence calibration check.** Track whether higher-confidence
  decisions were directionally right more often than lower-confidence
  ones (compare `institutional_confidence` vs realized direction).
- **Risk measure stability.** Record `var_95`, `var_99`, `cvar_95`,
  `tail_index` from `finalize.json.risk_metrics`; flag jumps that exceed
  prior-day values by a large multiple without a market event.

### 4.4 Trend validation (registry layer)

Weekly and monthly, run `python scripts/show_run_history.py` and validate:

- Success rate (successful runs / total runs).
- Average, min, max execution duration.
- Decision distribution and event-type distribution.
- Registry immutability: line count equals number of successful runs; each
  line is valid JSON; no record rewritten (no duplicate `run_id`).

### 4.5 Non-goals

This program does **not**: tune algorithms, change workflows, edit the
report generator, edit the registry schema, or redesign architecture —
even when findings suggest improvements. Suggested changes are recorded in
the escalation log for resolution after the 30-day window.

## 5. Metrics to collect

| Metric | Source field / artifact | Collection point |
| --- | --- | --- |
| Exit code | registry `exit_code` | daily |
| Pipeline status | registry `pipeline_status` | daily |
| Stage ok count / failures | `outputs/YYYY-MM-DD/stages.json`, `summary.json.stage_counts` | daily |
| Wall time (s) | registry `execution_duration_seconds` | daily |
| Decision | registry `institutional_decision` | daily |
| Confidence | registry `confidence`; `finalize.json.decision.institutional_confidence` | daily |
| Composite score | `finalize.json.decision.metadata.composite_score` | daily |
| Risk/reward ratio | decision explanation (`risk_reward_ratio`) | daily |
| Regime + confidence | `finalize.json.context.current_regime` / `regime_confidence` | daily |
| Forecast model + metadata | `finalize.json.forecast_result.model_name` / `.metadata` | daily |
| Validation metrics | `finalize.json.validation` (`sample_size`, `passed`, `metrics.*`) | daily |
| Risk measures | `finalize.json.risk_metrics` (`var_95`, `var_99`, `cvar_95`, `tail_index`) | daily |
| Bias review | `finalize.json.decision.metadata.bias_review` | daily |
| Report completeness | report section count (14) | daily |
| Report→registry consistency | Executive Summary vs registry record | daily |
| Telegram delivery | scheduler summary (`Telegram:` line) | daily |
| Registry size / integrity | `runtime/run_registry.jsonl` | weekly |
| Success rate | registry statistics | weekly |
| Avg / min / max runtime | registry statistics | weekly |
| Decision distribution | registry statistics | weekly |
| Forecast accuracy | `finalize.json.validation.metrics` as pairs accumulate | monthly |
| Confidence calibration | decision vs realized direction | monthly |
| Registry immutability | line count vs run count, duplicate `run_id` scan | monthly |

## 6. Daily review checklist

Recorded in the validation log for each active day (all items must be
`PASS`/`FAIL`/`N/A` with a one-line note on non-PASS):

1. [ ] Scheduler exit code `0` and `Result: SUCCESS`.
2. [ ] Pipeline exit code `0` recorded in registry for today's `run_id`.
3. [ ] `institutional_report.md` exists, non-empty, with all 14 sections.
4. [ ] Registry record for today exists; `output_directory` matches
       `outputs/YYYY-MM-DD`; one new record appended.
5. [ ] Report Executive Summary decision/confidence match registry.
6. [ ] `stages.json` shows all 25 stages `ok`; no `failed_stages`.
7. [ ] No new errors in `run.log` beyond known warnings
       (convergence/ValueWarnings are noted, not failed).
8. [ ] `finalize.json.validation` notes read; `sample_size` trend noted.
9. [ ] Regime, decision, confidence compared with prior day; material
       changes noted.
10. [ ] `bias_review` findings reviewed; `human_review_flag` noted if true.
11. [ ] Telegram status line reviewed (`sent` / `not configured`).
12. [ ] Any anomaly copied to the escalation log with run date + `run_id`.

## 7. Weekly review checklist

Performed every 7th day (and at Day 30), in addition to the daily items:

1. [ ] `python scripts/show_run_history.py` run; statistics recorded.
2. [ ] Success rate ≥ 98% for the week (tolerance per Section 9).
3. [ ] Decision distribution reviewed; streaks (e.g., 5+ identical
       decisions) noted.
4. [ ] Week's forecasts compared with realized gold movements; direction
       hits/misses tallied per event.
5. [ ] Confidence calibration reviewed (were confident calls right?).
6. [ ] Bias findings and `human_review_flag` occurrences summarized.
7. [ ] Data completeness: every calendar day has outputs + registry record.
8. [ ] Registry integrity: line count = successful run count; no malformed
       lines; no duplicate `run_id`.
9. [ ] Escalation log reviewed; open items still open after 3 days are
       re-escalated (Section 11).
10. [ ] Weekly summary appended to the validation log.

## 8. Monthly review checklist

Performed at Day 30 (program close-out):

1. [ ] Cumulative statistics: runs, success rate, avg/min/max runtime,
       decision and event-type distributions.
2. [ ] Forecast accuracy summary across all realized pairs; report
       `directional_accuracy`, `rmse`, `mape`, `coverage` and sample size.
3. [ ] Confidence calibration verdict (directional decisions only).
4. [ ] Regime distribution and regime-transition log across the window.
5. [ ] Registry immutability audit (all 30 days).
6. [ ] Escalation log: every entry resolved or carried with owner.
7. [ ] Success criteria (Section 9) evaluated line by line.
8. [ ] Failure criteria (Section 10) checked; any triggered criterion
       documented.
9. [ ] Protocol effectiveness assessment (what was easy/hard to validate).
10. [ ] Go / no-go recommendation for the next program cycle and any
       proposed (post-window) changes, recorded in the escalation log.

## 9. Success criteria

The 30-day program is **successful** when **all** of the following hold:

| # | Criterion | Threshold |
| --- | --- | --- |
| S1 | Daily execution reliability | ≥ 90% of active days produce a verified run (exit 0, report exists, registry record appended) |
| S2 | Report completeness | 100% of produced reports contain all 14 sections |
| S3 | Registry integrity | 100% of successful runs have exactly one record; zero malformed lines; zero duplicate `run_id` |
| S4 | Report–registry consistency | 100% of daily spot-checks show matching decision/confidence |
| S5 | Stage health | No unexplained stage failures on 2+ consecutive days |
| S6 | Forecast accuracy | Whenever ≥ 10 aligned forecast–actual pairs exist: `directional_accuracy ≥ 50%` (better than random) and `coverage` within the stated confidence band |
| S7 | Confidence calibration | For directional decisions, average confidence of correct calls ≥ average confidence of incorrect calls |
| S8 | Delivery | Telegram sends (when configured) succeed on ≥ 95% of days, with no silent failures |
| S9 | Escalation discipline | Every escalation entry resolved within 3 working days |
| S10 | Change discipline | Zero unapproved code/algorithm/workflow/report changes during the window |

## 10. Failure criteria

The program **fails** (or must halt) when **any** of the following holds.
Each is recorded in the escalation log with evidence:

| # | Criterion | Severity |
| --- | --- | --- |
| F1 | 3 consecutive failed runs (non-zero exit) without a documented cause and response | High |
| F2 | Reports missing on 2+ consecutive days | High |
| F3 | Registry corruption: malformed lines, missing records, rewritten or duplicate `run_id` | High |
| F4 | Report–registry disagreement on decision/confidence for 2+ consecutive days | High |
| F5 | Unapproved change to code/algorithms/workflows/reports/registry during the window | High |
| F6 | Persistent zero-sample forecast validation with no progress toward aligned pairs at Day 30 | Medium (records a validation gap, not a run failure) |
| F7 | Telegram silently failing (no send, no error surfaced) on 3+ configured days | Medium |
| F8 | Unexplained decision flips or confidence anomalies across 2+ consecutive reports | Medium |
| F9 | Protocol itself not executed (daily checklist missed) on 3+ days | Medium |

Any High-severity criterion halts the daily schedule until resolved
(Section 11, T1).

## 11. Escalation rules

### 11.1 Severity tiers

| Tier | Definition | Response |
| --- | --- | --- |
| T3 — Observe | Minor anomaly, no impact on the daily deliverable | Log it; review at next weekly review |
| T2 — Investigate | Deliverable still produced but with a defect or anomaly (e.g., report inconsistency, stage hiccup, Telegram failure, suspicious metric jump) | Investigate the same day; fix or record resolution within 2 working days |
| T1 — Halt | Deliverable missing/corrupt, registry damaged, suspected data integrity issue, or any High-severity failure criterion | Halt the daily schedule; escalate to THE BLU WALF immediately; resume only after resolution is recorded |

### 11.2 Escalation path

1. Operator records the finding in the escalation log (date, `run_id`,
   artifact path, observation, tier).
2. T2/T1 findings are communicated to **THE BLU WALF** (repository owner)
   via the configured channel (e.g., Telegram) with the escalation log
   reference.
3. Resolution is appended to the escalation log: root cause, action taken
   (or explicit "no action, recorded for post-window"), and whether the
   daily schedule resumes.
4. Open items older than 3 working days are automatically re-escalated at
   the next weekly review.

### 11.3 Halting rules

- A T1 finding halts `scripts/run_daily.py` scheduling until the
  resolution is recorded.
- Restart requires: resolution note in the escalation log, one successful
  manual daily run, and all three verification gates passing.
- During a halt, no protocol sections are skipped retroactively; missed
  days are recorded as `HALTED` in the validation log and counted against
  the execution-reliability criterion S1.

## 12. Required artifacts

| Artifact | Path | Purpose |
| --- | --- | --- |
| Daily report (markdown) | `outputs/YYYY-MM-DD/institutional_report.md` | The daily deliverable under validation |
| Daily report (HTML) | `outputs/YYYY-MM-DD/institutional_report.html` | Reviewable rendering |
| Run summary | `outputs/YYYY-MM-DD/summary.json` | Execution verification |
| Stage records | `outputs/YYYY-MM-DD/stages.json` | Stage health |
| Finalized outputs | `outputs/YYYY-MM-DD/finalize.json` | Metrics + decision evidence |
| Run log | `outputs/YYYY-MM-DD/run.log` | Warning/error review |
| Artifacts dir | `outputs/YYYY-MM-DD/artifacts/` | Knowledge/lessons evidence |
| Run registry | `runtime/run_registry.jsonl` | Immutable execution history |
| Protocol document | `docs/validation/VALIDATION_PROTOCOL_V1.md` | This document (pinned to a git commit at Day 1) |
| Validation log | `docs/validation/VALIDATION_LOG_V1.md` | Daily/weekly checklist results (opened on Day 1 by the operator) |
| Escalation log | `docs/validation/ESCALATION_LOG_V1.md` | Every T2/T1 finding + resolution (opened on Day 1) |

The validation log and escalation log are opened on Day 1, maintained by
the operator throughout the window, and summarized in the Day-30 monthly
review.
