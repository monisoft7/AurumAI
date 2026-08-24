# Institutional Outcome Validation — Design

Status: Architecture only. No implementation, no code, no tests.
Scope: A v1 additive capability that lets AurumAI evaluate whether an institutional decision was correct once the real market outcome (gold movement) becomes known, after each completed run.

## 1. Objective

After each institutional run completes and the evaluation horizon elapses, produce an outcome record that answers, per run:

- What decision was made and with what institutional confidence.
- What the realized gold (XAU/USD) return actually was over the horizon.
- Whether the decision was correct (or was an unscored abstention).

## 2. Constraints and principles

1. **Reuse, do not duplicate.** All outcome math is delegated to the existing simulation correctness engine in `src/simulation/historical_replay.py`. No logic is copied or re-implemented.
2. **Gold (XAU/USD) is the only supported asset in v1.** The outcome evaluation reads the run's `gold_path` (default `data/history/gold/gold.csv`) exclusively.
3. **Additive only.** No existing workflow, decision logic, threshold, or contract is modified.
4. **Runtime artifacts remain immutable.** `summary.json` / `finalize.json` / stage checkpoints are never rewritten after the run. Outcome evaluation produces a separate artifact.

## 2.1 Reused APIs (single source of truth)

| API | Signature | Location | Role |
|---|---|---|---|
| `_compute_gold_return` | `(gold: DataFrame, entry_date: datetime, horizon_days: int = 5) -> float \| None` | `src/simulation/historical_replay.py:170` | Post-event gold return %: nearest price at-or-before `entry_date` → nearest price at-or-after `entry_date + horizon`. |
| `_classify_actual_direction` | `(actual_return_pct: float, dead_zone: float = 0.10) -> "UP" \| "DOWN" \| "FLAT"` | `historical_replay.py:133` | Classifies the realized return. |
| `_decision_is_correct` | `(decision: str, actual_direction: str) -> bool \| None` | `historical_replay.py:147` | BUY→UP, SELL→DOWN, HOLD→FLAT; `NO_TRADE` / `INSUFFICIENT_EVIDENCE` → `None` (abstention, not scored). Compatible with the institutional vocabulary `BUY/SELL/HOLD/NO_TRADE` (`src/decision_engine/contracts.py:15`). |

These three functions already define the exact post-event computation used by the simulation subsystem (`historical_replay.py:788-797`, `1605-1612`) and are imported as-is by the outcome evaluator. No new math exists anywhere in the design.

## 3. Lifecycle

Three phases; each phase is a separate, non-mutating step.

### 3.1 Phase A — Run completion (emits the pending outcome record)

At the end of a successful institutional run, at the existing artifact-writer site (`run.py:376-399`, where `summary.json` / `finalize.json` are written), an **additive outcome writer** emits a pending record. This is attach-only:

- It writes a new file `outputs/<date>/outcome.json`.
- It does not modify `summary.json`, `finalize.json`, stage checkpoints, or any stage output.
- It captures only fields already computed by the run (no recomputation, no new stages).

Record written in Phase A:
- `run_id`, `decision`, `institutional_confidence`, `event_type`, `horizon_days` — populated.
- `realized_gold_return`, `decision_correct`, `evaluation_timestamp` — `null` (pending).
- `status: "pending"`.

### 3.2 Phase B — Horizon elapsed (independent evaluator fills the record)

An **outcome evaluator** (a standalone tool invoked by an operator or the reporting pipeline after the horizon, e.g. alongside `scripts/generate_institutional_report.py`) processes a pending record:

1. Loads the run's `gold_path` CSV (Date/Close schema, the same file format `historical_replay._load_gold_data` consumes).
2. Determines `entry_date` from the run (run date / event release context).
3. Calls `_compute_gold_return(gold, entry_date, horizon_days)` using the run's configured `horizon` (`runtime_config.json:10`, e.g. 12).
4. If a return is produced, calls `_classify_actual_direction(return)` then `_decision_is_correct(decision, direction)`.
5. Writes an **evaluated record** (see §5 for immutable-pairing semantics) with `evaluation_timestamp` set and `status: "evaluated"`.

The run-time artifact (`outputs/<date>/outcome.json`, pending) is never modified; the evaluated record is written as a sibling. See §5.2.

### 3.3 Phase C — Consumption

Downstream consumers (reporting, the 14-day validation program in `docs/validation/POST_FIX_VALIDATION.md`, knowledge lessons) read evaluated records. Correctness aggregation for institutional runs may reuse the same aggregation contracts the simulation subsystem already defines (`OOSSummary` / `EconomicSummary` in `src/simulation/models.py`) if needed; this design only mandates the per-run record.

## 4. Artifact schema

### 4.1 `outputs/<date>/outcome.json` (pending, written at Phase A)

```json
{
  "schema_version": "1.0",
  "artifact": "decision_outcome",
  "status": "pending",
  "run_id": "runtime_20260804_182103",
  "decision": "NO_TRADE",
  "institutional_confidence": 0.3139,
  "event_type": "CPI",
  "asset": "XAU/USD",
  "horizon_days": 12,
  "gold_path": "data/history/gold/gold.csv",
  "entry_date": "2026-08-04",
  "realized_gold_return": null,
  "decision_correct": null,
  "evaluation_timestamp": null,
  "decision_id": "dec_0f5f745cf534"
}
```

Field notes:
- `run_id` ← `summary.json` `pipeline_id`.
- `decision` ← `finalize.json` `decision.decision` (extraction per the existing `_extract_decision` pattern at `historical_replay.py:981`).
- `institutional_confidence` ← `finalize.json` `decision.institutional_confidence` (equals `summary.json` `decision_confidence`).
- `event_type` ← `summary.json` `event_type`.
- `horizon_days` ← run config `horizon`.
- `entry_date` ← run date (event release / run timestamp). `null` handling defined in §6.
- `asset` is fixed `XAU/USD` in v1; the schema is forward-compatible.
- `decision_id` is an optional cross-reference for traceability; `null` if absent.

Correction 055-A (`schema_version` bumped to `1.1`; all prior fields preserved):
`decision_snapshot` freezes decision-time facts already contained in
`finalize["decision"]`, verbatim, so later evaluation never recomputes or
reinterprets them:
- `best_rejected` — `{thesis_id, direction, composite_score}` of the best
  forgone candidate: for abstentions the selected-but-gated thesis takes
  precedence, otherwise the top composite-sorted `rejected_alternatives` entry;
  `null` when none exists.
- `gate_reasons` — `{conviction_gate_pass, rr_gate_pass, risk_reward_ratio,
  bias_review_blocked}` using the existing W13 constants
  (`NO_TRADE_CONFIDENCE=0.5`, `NO_TRADE_RR_RATIO=2.0`); `rr_gate_pass=null`
  is the deterministic signature of the no-eligible-thesis path.
- `evidence_snapshot` — `{evidence_quality, counter_evidence_quality,
  scenario_probability_max, total_theses_evaluated}` read from the recorded
  decision drivers and metadata.

### 4.2 Evaluated record `outputs/<date>/outcome.evaluated.json`

Identical schema with `status: "evaluated"` and the three outcome fields populated:

```json
{
  "schema_version": "1.0",
  "artifact": "decision_outcome",
  "status": "evaluated",
  "run_id": "runtime_20260804_182103",
  "decision": "BUY",
  "institutional_confidence": 0.62,
  "event_type": "CPI",
  "asset": "XAU/USD",
  "horizon_days": 12,
  "gold_path": "data/history/gold/gold.csv",
  "entry_date": "2026-08-04",
  "realized_gold_return": 1.25,
  "decision_correct": true,
  "evaluation_timestamp": "2026-08-16T12:00:00+00:00",
  "decision_id": "dec_0f5f745cf534"
}
```

Semantics:
- `realized_gold_return` — percent change from `_compute_gold_return` (e.g. +1.25%). `null` if gold data or horizon is unavailable.
- `decision_correct` — `true`/`false` from `_decision_is_correct`; **`null` for `NO_TRADE` (abstention is not scored)**, matching existing replay semantics (`historical_replay.py:147-167`).
- `evaluation_timestamp` — UTC ISO-8601 when the evaluated record was written.

Trace 054 additive fields (evaluated-artifact schema bumped to `1.1`; the
pending decision-time artifact remains schema `1.0`):

- `gold_source_sha256` — SHA-256 hex digest of the exact gold CSV bytes consulted for this evaluation (`null` when the file is missing/unreadable). Enables reproducibility checks for later re-evaluation without a data-vintage system.
- `abstention_evaluable` — `true` iff the decision is an abstention (`NO_TRADE` / `INSUFFICIENT_EVIDENCE`).
- `abstention_verdict` — Correction 055-A taxonomy: `justified_abstention` (no meaningful positive forgone return beyond the existing ±0.10% dead zone), `missed_opportunity` (a named forgone directional candidate would have won beyond the dead zone), `unresolvable` (no eligible directional thesis existed; structural, outcome-independent), `unevaluable` (horizon/gold/integrity failure), or `unscored` (run predates `decision_snapshot`). `null` for non-abstentions.
- `abstention_basis` — decision-time bases restated verbatim (`bias_review`, `low_conviction`, `rr_asymmetry`, `no_eligible_thesis`); they never override the outcome verdict.
- `decision_snapshot` — passthrough of the frozen decision-time snapshot.
- `abstention_return` — the realized return for abstentions (information, not a score); `null` otherwise.

`decision_correct` stays `null` for abstentions: verdicts assess abstention
quality only. Any binary abstention scoring policy remains DEFERRED. HOLD is
a scored flat decision class and never enters the abstention taxonomy.

### 4.3 Immutability pairing

- The pending artifact is **write-once** at Phase A.
- The evaluated artifact is **write-once** at Phase B (re-evaluation writes a new file, never edits the previous one).
- Neither artifact, once written, is modified in place. Runtime artifacts remain immutable.

## 5. Integration points

| Point | Where | What happens | Additive? |
|---|---|---|---|
| P1 — Pending emit | `run.py` artifact-writer block (`run.py:376-399`), beside `summary.json`/`finalize.json` writes | Writes `outcome.json` from already-computed run values | Yes — new file, new call; no existing line altered |
| P2 — Evaluation | New standalone evaluator tool (co-located with `scripts/generate_institutional_report.py`) | Loads pending record + gold CSV, calls the three reused functions, writes `outcome.evaluated.json` | Yes — new tool; `historical_replay.py` and contracts untouched |
| P2b — Automatic evaluation (Trace 054) | `scripts/run_daily.py` invokes `scripts/evaluate_outcome.py --all-pending` after report generation and verification | Sweeps every run under the outputs base whose horizon has elapsed and evaluates it idempotently; evaluated runs are skipped; failures never affect the daily result or exit code | Yes — additive scheduling step; no decision-time artifact is touched |
| P3 — Consumption | Reporting / validation / lessons | Reads evaluated records | Yes — read-only |

No orchestration stage is added or modified. The run workflow, decision logic, thresholds, and all contracts (`decision_engine`, `simulation.models`, `InstitutionalDecision`, etc.) are unchanged.

## 6. Failure handling

| Condition | Detection | Behavior |
|---|---|---|
| Gold file missing / unreadable | `_compute_gold_return` returns `None` (no rows at-or-before entry) | Evaluated record written with `status: "evaluated"`, `realized_gold_return: null`, `decision_correct: null`, plus a `notes` entry describing the failure; no exception propagates |
| Horizon not yet elapsed (no price at-or-after entry+horizon) | `_compute_gold_return` returns `None` (empty future rows) | Record remains `pending`; evaluator exits silently (retry later). Distinct from true failure |
| Entry date resolution failure (no event date) | `entry_date` unavailable | Record remains `pending` with a `notes` marker; no scoring attempted |
| Decision extraction failure | `finalize.json` decision field missing/foreign | `decision: null`; `decision_correct: null`; flagged in `notes`; never crashes the run |
| `NO_TRADE` decision | `_decision_is_correct` returns `None` by design | `decision_correct: null`, `realized_gold_return` still recorded (it is information, not a score) |
| Malformed prior artifact | Parser error on `outcome.json` | Evaluator aborts that run's evaluation, logs, continues others (fail-one-isolated) |
| Re-evaluation attempt | Detected status / duplicate `run_id` | No overwrite; new evaluation file written (versioned sibling) |

Design rule: **outcome evaluation never causes the run to fail and never blocks run completion.** All outcomes degrade to `null` + `notes`.

## 7. Acceptance criteria

1. Every completed run emits exactly one pending `outcome.json`; no run-artifact modification.
2. After the horizon, an evaluated record exists with `realized_gold_return`, `decision_correct`, and `evaluation_timestamp` populated (or explicit `null` + `notes` for `NO_TRADE` / data failure).
3. `realized_gold_return` is produced **only** by `_compute_gold_return`; `decision_correct` only by `_decision_is_correct(_classify_actual_direction(...))` — no duplicated math anywhere.
4. Gold (XAU/USD) is the sole asset referenced; asset field is constant in v1.
5. `summary.json` / `finalize.json` / stage checkpoints are byte-identical before and after evaluation (immutability preserved).
6. A `NO_TRADE` run scores `decision_correct: null` (abstention), with realized return still recorded.
7. Failure conditions in §6 produce `null` + `notes` and never fail or block the run.
8. No workflow, decision-logic, threshold, or contract change is required by the design.
