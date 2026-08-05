# AurumAI Post-Fix Validation Program

**Program:** 14-day observation of the institutional pipeline after Issue #001
(thesis_id mismatch fix).
**Status:** Observational only.
**Duration:** 14 consecutive calendar days.
**Owner:** THE BLU WALF (repository owner and escalation point).
**Scope:** validation of daily institutional output after the Issue #001 fix.
This program makes **no code changes, no test changes, and no threshold
changes** during the observation period.

## Operating assumption

No code is modified during the 14-day observation period. The fix shipped for
Issue #001 is treated as frozen. All validation is read-only review of the
artifacts already produced by the daily run.

## Primary artifacts per run

- `outputs/YYYY-MM-DD/summary.json` — decision label and confidence summary.
- `outputs/YYYY-MM-DD/finalize.json` — full finalize payload (decision,
  forecast confidence, context, risk, position).
- `outputs/YYYY-MM-DD/stages.json` — per-stage status records.
- Checkpoint directory `runtime_{timestamp}/` — per-stage outputs:
  `confidence_engine.json`, `scenario_generation.json`, `decision_engine.json`,
  `risk_reward_validation.json`, `bias_prevention.json`.

---

## 1. Daily execution procedure

1. Confirm the daily run completed with `success: true` and no `failed_stages`
   in `outputs/YYYY-MM-DD/summary.json`. A run that fails or errors out is
   recorded as a **broken run** and does not count toward the 14 valid days.
2. Confirm exactly one institutional decision exists in
   `outputs/YYYY-MM-DD/summary.json` under `decision`.
3. Open `outputs/YYYY-MM-DD/finalize.json` and record every metric listed in
   Section 2 into the daily validation log (one row per run).
4. Inspect the checkpoint outputs for the same run
   (`confidence_engine.json`, `decision_engine.json`,
   `risk_reward_validation.json`, `bias_prevention.json`) and copy the values
   needed for Sections 3–8.
5. Run the Section 9 anomaly checklist against the recorded values.
6. Append the run to the running 14-day log; do not edit prior entries.
7. On days 7 and 14, apply the Section 10 weekly review methodology and append
   the review record.

The validation log must contain, at minimum: run date, `pipeline_id`, and the
artifact paths referenced. Every entry is immutable; corrections are appended
as new entries.

## 2. Metrics to record after each run

Record the following per valid run (run date + `pipeline_id` in every row):

| Metric | Source artifact |
| --- | --- |
| Decision label | `summary.json` → `decision` |
| Institutional confidence | `summary.json` → `decision_confidence` (also `finalize.json` → `decision.institutional_confidence`) |
| Forecast confidence (overall) | `finalize.json` → `confidence.overall` |
| Forecast spread score | `finalize.json` → `confidence.spread_score` |
| Forecast agreement score | `finalize.json` → `confidence.agreement_score` |
| Forecast context coherence | `finalize.json` → `confidence.context_coherence` |
| Regime and regime confidence | `finalize.json` → `context.current_regime`, `context.regime_confidence` |
| Selected thesis id | `finalize.json` → `decision.selected_thesis_id` |
| Selected scenario id | `finalize.json` → `decision.selected_scenario_id` |
| Composite score | `finalize.json` → `decision.metadata.composite_score` |
| Risk/reward status | `finalize.json` → `decision.risk_reward_summary.status` |
| Risk/reward ratio | `finalize.json` → `decision.risk_reward_summary.risk_reward_ratio` |
| Bias review severity | `finalize.json` → `decision.metadata.bias_review.overall_severity` |
| Bias human review flag | `finalize.json` → `decision.metadata.bias_review.human_review_flag` |
| Bias findings | `finalize.json` → `decision.metadata.bias_review.findings` |
| Bias confidence impact | `finalize.json` → `decision.metadata.bias_review.total_confidence_impact` |
| Confidence engine final confidence | checkpoint `confidence_engine.json` → `theses_confidence[].final_confidence` |
| Confidence reliability category | checkpoint `confidence_engine.json` → `theses_confidence[].reliability_category` |
| Stage counts / errors / failed stages | `summary.json` → `stage_counts`, `errors`, `failed_stages` |
| Forecast validation result | `finalize.json` → `validation.passed`, `validation.sample_size` |

## 3. Decision distribution tracking

Track the count of each decision across the 14 valid runs:

- **BUY**
- **SELL**
- **NO_TRADE**

`HOLD` is a valid engine output (`HOLD_CONFIDENCE = 0.35`); if it appears it is
recorded in the same distribution table. Log the running totals after every
run. Report the final distribution as counts and percentages in the weekly and
final reviews.

## 4. Institutional confidence tracking

- Record `institutional_confidence` per run (Section 2).
- Compute the run-level mean, median, min, max, and share of runs at each
  reliability category (`high` / `moderate` / `low` /
  `very_low`) from `confidence_engine.json`.
- Note the decision threshold context: `NO_TRADE_CONFIDENCE = 0.5`,
  `HOLD_CONFIDENCE = 0.35`. Record whether the decision is consistent with the
  recorded confidence against these thresholds.
- Flag any run where a non-zero confidence engine output exists for the
  selected thesis but the recorded `institutional_confidence` is `0.0`
  (regression of Issue #001 — see Section 9).

## 5. Forecast confidence tracking

- Record `forecast confidence (overall)` per run from `finalize.json` →
  `confidence.overall`.
- Also record the component scores: `spread_score`, `agreement_score`,
  `context_coherence`.
- Track the per-run mean, median, min, and max across the 14 days.
- Track the realized validation signal where available:
  `finalize.json` → `validation.passed` and `validation.sample_size`.

## 6. Difference between forecast confidence and institutional confidence

- Compute per run: `Δ = forecast confidence (overall) − institutional confidence`.
- Record `Δ` per run; track mean, median, min, max, and sign distribution
  (positive / negative / zero) across the 14 days.
- A persistent, one-sided `Δ` (e.g., forecast systematically far above
  institutional confidence) is recorded for the Section 12 calibration
  assessment. No threshold is changed during the observation window.

## 7. Bias findings frequency

- For each run, record `overall_severity` and the full `findings` list from
  `decision.metadata.bias_review`.
- Track the per-finding count over 14 runs (e.g., `confirmation_bias`,
  `anchoring`, `groupthink`, `false_precision`, and any others emitted).
- Track how often `human_review_flag` is `true` and the per-run
  `total_confidence_impact`.
- Report the most and least frequent findings and whether findings correlate
  with NO_TRADE outcomes in the weekly reviews.

## 8. Risk/reward status frequency

- For each run, record `decision.risk_reward_summary.status`
  (`acceptable` / `borderline` / `reject`) and `risk_reward_ratio`.
- Count each status over the 14 runs and report percentages.
- Track the count of runs whose selected scenario was accepted
  (`ELIGIBLE_STATUSES = {acceptable, borderline}`) versus rejected.
- Report whether the risk/reward status distribution changed materially across
  the first and second 7-day halves in the final review.

## 9. Daily anomaly checklist

After recording metrics, confirm all of the following. Any failure is an
**anomaly** and must be logged with the run date and `pipeline_id`:

1. Run completed: `success: true`, no `failed_stages`, `errors` empty.
2. Decision present and one of BUY / SELL / NO_TRADE (or HOLD).
3. `selected_thesis_id` in the decision matches a thesis in the
   `confidence_engine.json` output (no thesis_id mismatch).
4. `institutional_confidence` equals the selected thesis `final_confidence`
   from `confidence_engine.json` (within rounding) and is not `0.0` when the
   engine produced a non-zero value.
5. `scenario_generation.json` scenarios carry the same thesis_id as the
   selected thesis.
6. Bias review metadata present on the decision (`metadata.bias_review`) with
   a valid `overall_severity`.
7. `risk_reward_summary.status` present and one of the valid statuses.
8. Confidence is in `[0.0, 1.0]`; forecast confidence is in `[0.0, 1.0]`.
9. No unexpected `0.0` institutional confidence where a thesis was selected.
10. No cache-hit-only or replayed outputs where the run should be fresh
    (`cache_hits` consistent with a fresh run).

Anomalies are logged daily and aggregated in the weekly review. No code change
is made during the 14-day window; anomalies feed Section 12 only.

## 10. Weekly review methodology

On day 7 and day 14, produce a weekly review covering the runs since the last
review:

1. Aggregate all Section 2 metrics and the Section 3–8 distributions.
2. Confirm the Issue #001 fix held: every valid run satisfies checklist items
   3–5 (thesis_id alignment, non-zero propagated confidence, scenario keying).
3. Compare the first-half and second-half decision distributions
   (BUY / SELL / NO_TRADE / HOLD) for material drift.
4. Compare institutional confidence vs forecast confidence distributions and
   the `Δ` sign/magnitude between halves.
5. Review bias finding frequencies and `human_review_flag` share.
6. Review risk/reward status frequencies and the share of `acceptable`
   statuses.
7. List all anomalies recorded since the last review and their disposition
   (observed only — no code changes).
8. Append the review record to the validation log.

## 11. Success criteria

The 14-day program is a success when all of the following hold:

1. At least 14 valid daily runs (broken runs excluded, with reason logged).
2. Checklist items 3–5 (Issue #001 regression checks) pass on every valid run —
   no thesis_id mismatch, no unexplained `0.0` institutional confidence.
3. Every valid run produced exactly one decision with a non-empty
   `decision_explanation`.
4. No run exceeded a reasonable anomaly count, and every anomaly was logged
   with run date and `pipeline_id`.
5. Decision distribution is stable between the first and second 7-day halves
   (no material drift in BUY / SELL / NO_TRADE shares).
6. Institutional confidence and forecast confidence are each within
   `[0.0, 1.0]` on every run and the recorded `Δ` is bounded (no runaway gap).

## 12. Conditions that justify calibration work

The following observations — after the 14-day window — justify proposing
calibration work (to be implemented only after this observation period, per the
no-code-change assumption):

1. Systematic under- or over-confidence: realized outcomes are consistently
   outside the forecast bands, or forecast/institutional confidence is
   consistently misaligned with realized accuracy.
2. Persistent one-sided `Δ` (forecast confidence − institutional confidence)
   across a majority of runs.
3. Concentration of NO_TRADE caused by confidence just below
   `NO_TRADE_CONFIDENCE` with otherwise favorable risk/reward, indicating a
   threshold or weight calibration question.
4. Systematic bias findings (the same finding on a majority of runs) with
   material `total_confidence_impact`.
5. A stable bias review `human_review_flag = true` share that indicates
   over-flagging or under-flagging.
6. Recurring anomalies in the Section 9 checklist that trace to pipeline
   behavior rather than external data.

Calibration work is out of scope for this document; this section only defines
when it is justified to propose it.
