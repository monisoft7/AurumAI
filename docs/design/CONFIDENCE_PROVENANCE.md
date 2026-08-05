# Confidence Provenance Layer — Design

Status: Architecture only. No implementation, no code, no tests.
Scope: A provenance layer that produces a complete, machine-readable explanation for every institutional confidence value emitted by the pipeline.

## 1. Objective

For every institutional confidence value produced by W9, produce an explanation that answers, per value:

1. Raw confidence from ConfidenceComputer.
2. Every adjustment applied.
3. Every cap applied.
4. Every penalty applied.
5. Final confidence.
6. The reason for every change.
7. The source component responsible for every change.

The explanation must become part of the runtime artifacts (per-run, alongside `summary.json` / `finalize.json` and the stage checkpoints).

## 2. Constraints

This design is strictly additive and observational:

- **No algorithm changes** — the confidence formula in `ConfidenceComputer.compute()` is untouched.
- **No threshold changes** — all boundaries are read from existing constants and only recorded.
- **No contract changes** — `ThesisConfidence` / `InstitutionalConfidence` / `Provenance` are not extended.
- **No workflow changes** — the W9 stage executes exactly as today; provenance is assembled after `evaluate()` returns.
- **No decision logic changes** — `DecisionEngine`, `BiasPrevention`, and `ScenarioGeneration` consumption behavior is unchanged.

Design consequence: because all information required for the full explanation already exists in the current W9 outputs, the provenance layer is a **pure assembly / serialization concern** — it recomputes nothing and mutates nothing.

## 3. Scope — what is "every institutional confidence value"

One provenance record is produced for each value emitted by W9, i.e. one record per `(confidence_id, thesis_id)` pair, where the value is `ThesisConfidence.final_confidence`.

The value is *consumed unchanged* downstream:

- `DecisionEngine` reads `selected[tc].final_confidence` as `institutional_confidence`.
- `BiasPrevention` records `total_confidence_impact` as decision metadata (a gate note) but never mutates the confidence value.
- `ScenarioGeneration` keys scenarios off the same thesis/confidence value.

Therefore the provenance of the *value* is fully bounded by the W9 step trace; downstream components only consume it. The design records downstream consumers explicitly (see §6, `propagation`), but the value trace itself ends at W9 output.

## 4. Provenance model — the ordered step trace

Every explanation is an **ordered trace** of steps. Applying the steps in order to the raw value must reproduce `final_confidence` within rounding tolerance (self-verifying invariant).

### 4.1 Step taxonomy

Each trace is a sequence of steps drawn from this fixed taxonomy. Steps not triggered in a run are recorded with `active: false` so the explanation is complete regardless of which optional inputs were consumed.

| Step type | What it is | Source component |
|---|---|---|
| `raw_compute` | Raw value from `ConfidenceComputer.compute()` including its internal formula, plus every positive/penalty input used | `ConfidenceComputer.compute` (`src/confidence_engine/computer.py:32-100`) |
| `adjustment_support` | Multiplicative `support_factor` (institutional support, or 1.0 when ≤ 0) | `ConfidenceComputer.compute` (`computer.py:72`, recorded in `metadata.support_factor`) |
| `penalty_factor` | One entry per applied penalty factor: name, value, weight, penalty impact (`value × weight`), and marginal impact on the final value | `ConfidenceComputer.compute` (`computer.py:67-70,90-93`) |
| `cap_gs` | GS 3-question test cap at `HIGH_CONFIDENCE_THRESHOLD` when `generation` is present and the test is not fully answered | `ConfidenceEngine.evaluate` (`src/confidence_engine/engine.py:64,67-68`) |
| `cap_oos` | OOS calibration cap: `ECE > 0.25` → `LOW_CONFIDENCE_THRESHOLD`; `ECE > 0.15` → `HIGH_CONFIDENCE_THRESHOLD` | `ConfidenceEngine._oos_cap` (`engine.py:65,69-72,165-173`) |
| `clamp_round` | Domain clamp to `[0,1]` and 4-decimal rounding | `ConfidenceEngine.evaluate` (`engine.py:73`) |

### 4.2 Step record fields

Every step carries the same shape so traces are uniform and machine-parsable:

- `step`: step type (taxonomy above).
- `component`: source component, e.g. `ConfidenceComputer.compute`, `ConfidenceEngine.evaluate`, `ConfidenceEngine._oos_cap`.
- `reason_code`: stable machine-readable reason identifier.
- `reason`: human-readable reason, citing the contract rule it enforces.
- `condition`: the evaluated condition that triggered (or did not trigger) the step.
- `value_before` / `value_after`: value entering and leaving the step (absent for pure-recording steps).
- `delta`: `value_after − value_before` (positive/negative/none).
- `boundary`: the threshold that governs the step, where applicable (read from existing constants).
- `active`: `true` if the step changed (or could change) the value in this run; `false` if it was skipped.

Reason codes are anchored to the existing computation so that every `reason` traces back to a specific code location:

| `reason_code` | Meaning | Authority |
|---|---|---|
| `FORMULA_POSITIVE_PENALTY_SUPPORT` | raw = positive_score × support_factor × (1 − min(penalty_score, 1)) | `computer.py:73` |
| `ADJUST_SUPPORT_FACTOR` | institutional support applied multiplicatively (identity when ≤ 0) | `computer.py:72` |
| `PENALTY_WEIGHTED_CONTRIBUTION` | penalty contribution = value × PENALTY_WEIGHTS[name] | `computer.py:90-93` |
| `CAP_GS_NOT_FULLY_ANSWERED` | GS 3-question test incomplete caps at Medium | `engine.py:64,67-68` (W9 processing stage 2) |
| `CAP_OOS_HIGH_ECE` | OOS ECE > 0.25 caps at Low | `engine.py:69-70` (W9 processing stage 5) |
| `CAP_OOS_MEDIUM_ECE` | OOS ECE > 0.15 caps at Medium | `engine.py:71-72` (W9 processing stage 5) |
| `CLAMP_DOMAIN` | clamp value to [0, 1] | `engine.py:73` |
| `ROUND_4DP` | 4-decimal rounding | `engine.py:73` |

## 5. Artifact format

### 5.1 Artifact identity

- **Filename:** `confidence_provenance.json`
- **Location:** the same per-run output directory as `summary.json` / `finalize.json` (e.g. `outputs/2026-08-04/confidence_provenance.json`), and mirrored into the W9 stage checkpoint (see §8).
- **Versioning:** `schema_version` field at the record root; schema changes bump it.
- **Encoding:** UTF-8 JSON; keys sorted; values are plain JSON types (no dataclass reprs).

### 5.2 Record structure (schema, version 1)

```json
{
  "schema_version": "1.0",
  "artifact": "confidence_provenance",
  "generated_at": "<UTC ISO-8601>",
  "pipeline_id": "<run id>",
  "confidence_id": "<cf_...>",
  "construction_id": "<...>",
  "provenance": [
    {
      "thesis_id": "<th_...>",
      "final_confidence": 0.0,
      "reliability_category": "low",
      "remaining_uncertainty": 0.0,
      "steps": [
        {
          "step": "raw_compute",
          "component": "ConfidenceComputer.compute",
          "reason_code": "FORMULA_POSITIVE_PENALTY_SUPPORT",
          "reason": "raw = positive_score x support_factor x (1 - min(penalty_score, 1))",
          "condition": "always",
          "value_before": null,
          "value_after": 0.0,
          "delta": null,
          "boundary": null,
          "active": true
        },
        {
          "step": "cap_gs",
          "component": "ConfidenceEngine.evaluate",
          "reason_code": "CAP_GS_NOT_FULLY_ANSWERED",
          "reason": "GS 3-question test not fully answered; cap at HIGH_CONFIDENCE_THRESHOLD",
          "condition": {"generation_consumed": false, "all_answered": false},
          "value_before": 0.0,
          "value_after": 0.0,
          "delta": 0.0,
          "boundary": 0.60,
          "active": false
        }
      ],
      "inputs": {
        "positive_score": 0.0,
        "penalty_score": 0.0,
        "support_factor": 1.0,
        "positives": [],
        "penalties": [
          {"name": "counter_evidence", "value": 0.0, "weight": 0.35, "penalty": 0.0, "marginal_delta": 0.0}
        ],
        "gs_test": null,
        "oos_calibration": null,
        "w6_evidence": null
      },
      "propagation": {
        "consumed_unchanged_by": ["scenario_generation", "decision_engine"],
        "gate_only": ["bias_review"]
      }
    }
  ]
}
```

### 5.3 Worked example (real run)

Grounded in `runtime_20260804_182103`, `cf_50cde3058011`, thesis `th_dd0c1d7a8e0a.v2`, `final_confidence = 0.3139`.

Intermediate values used by the trace (all derived from the recorded `confidence_breakdown`, `confidence_penalties`, and `metadata` — no recomputation at serialize time):

- positive_score = 0.6077×0.25 + 1.0×0.25 + 0.0×0.15 + 0.6667×0.15 + 1.0×0.10 + 1.0×0.10 = **0.70193**
- penalty_score = 0.0×0.35 + 0.0×0.25 + 0.2×0.40 = **0.08**
- support_factor = **0.4861** (institutional_support)
- raw = 0.70193 × 0.4861 × (1 − 0.08) = **0.3139** (rounded)

Trace steps (order matters):

| # | step | component | value_before | value_after | delta | boundary | active | reason_code |
|---|---|---|---|---|---|---|---|---|
| 1 | `raw_compute` | `ConfidenceComputer.compute` | — | 0.3139 | — | — | true | `FORMULA_POSITIVE_PENALTY_SUPPORT` |
| 2 | `penalty_factor` (internal_consistency) | `ConfidenceComputer.compute` | 0.3412* | 0.3139 | −0.0273 | 0.40 | true | `PENALTY_WEIGHTED_CONTRIBUTION` |
| 3 | `adjustment_support` | `ConfidenceComputer.compute` | 0.6458** | 0.3139 | −0.3319 | — | true | `ADJUST_SUPPORT_FACTOR` |
| 4 | `cap_gs` | `ConfidenceEngine.evaluate` | 0.3139 | 0.3139 | 0.0 | 0.60 | false | `CAP_GS_NOT_FULLY_ANSWERED` |
| 5 | `cap_oos` | `ConfidenceEngine._oos_cap` | 0.3139 | 0.3139 | 0.0 | 0.35 / 0.60 | false | `CAP_OOS_HIGH_ECE` / `CAP_OOS_MEDIUM_ECE` |
| 6 | `clamp_round` | `ConfidenceEngine.evaluate` | 0.3139 | 0.3139 | 0.0 | [0, 1] / 4dp | true | `CLAMP_DOMAIN` / `ROUND_4DP` |

\* counterfactual: raw with penalty_score = 0 → 0.70193 × 0.4861 = 0.3412 (marginal impact of penalties).
\*\* counterfactual: raw with support_factor = 1.0 → 0.70193 × 0.92 = 0.6458 (marginal impact of support).

In this run the GS cap is inactive (`gs_cap = "none"`, `all_answered = true`) and no OOS ECE was consumed (`oos_ece_consumed = false`); both are recorded as explicit inactive steps so the trace is complete. The `clamp_round` step is active-but-identity.

Reconstruction invariant: 0.70193 × 0.4861 × 0.92 = 0.3139 = `final_confidence`. Any run whose trace does not reproduce the recorded `final_confidence` fails validation.

### 5.4 Completeness rules

- Every value emitted by W9 has exactly one trace entry.
- Inactive steps are still emitted (`active: false`) — absence of an input is part of the explanation.
- Optional-input provenance is preserved: `gs_test`/`gs_cap` only exist when `generation` was consumed; `oos_calibration` only when `oos_ece` was provided; `w6_evidence` only when reasoning was provided.

## 6. Ownership

| Role | Owner | Responsibility |
|---|---|---|
| Raw value producer | `ConfidenceComputer.compute` (W9) | Emits the raw value and its full factor breakdown; unchanged. |
| Adjustment / cap executor | `ConfidenceEngine.evaluate` (W9) | Applies GS/OOS caps and final clamp; unchanged. |
| Input providers | W6 `EvidenceReasoning`, W12 `ScenarioGeneration`, OOS-ECE supplier | Supply the optional inputs that condition caps and metadata; unchanged. |
| **Provenance serializer** | W9-adjacent, additive component | Assembles the ordered trace from the already-computed `InstitutionalConfidence`; computes deltas and counterfactuals from recorded fields; writes the artifact. This is the only new owner and it neither computes confidence nor changes any value. |
| Consumers (no write) | `DecisionEngine`, `ScenarioGeneration`, `BiasPrevention`, validation/reporting | Read `final_confidence`; read the trace for explanation. |
| Non-owner | `BiasPrevention` | Records `total_confidence_impact` as a gate note; it is deliberately **excluded** from the value trace because it never changes the value. |

No component outside W9 writes the value trace.

## 7. Lifecycle

1. **Creation** — during W9 stage execution, immediately after `evaluate()` returns, before the stage emits its checkpoint. The serializer reads the in-memory `InstitutionalConfidence` (no recomputation, no re-execution of stages).
2. **Persistence** — the artifact is written (a) as the W9 stage checkpoint companion and (b) into the run's output directory next to `summary.json` / `finalize.json`, under the same run-identity naming conventions. One write per run; values are frozen at write time.
3. **Propagation** — downstream stages and reports reference the trace by `(confidence_id, thesis_id)`; the value itself continues to flow unchanged.
4. **Validation** — covered by the existing 14-day observational program in `docs/validation/POST_FIX_VALIDATION.md`: each run's traces are checked for the reconstruction invariant and for agreement with `finalize.json`.
5. **Rotation** — follows existing runtime-artifact rotation; the artifact carries `schema_version` and `generated_at` for independent verification.

## 8. Integration point

The single integration seam is the **W9 orchestration stage boundary** in `src/orchestration/stages.py` (the `confidence_engine` job): the serializer hooks at the point where `ConfidenceEngine.evaluate()` output is already the authoritative per-run value, and writes into the two existing artifact channels (per-job checkpoints + `outputs/<date>/`). 

Integration is deliberately non-invasive:

- No change to `compute()`, `evaluate()`, or the ranker.
- No change to `ThesisConfidence` / `InstitutionalConfidence` contracts.
- No change to stage ordering, thresholds, or decision logic.
- Header consistency with the existing provenance convention (`created_at`, `created_by`, `entity_version` from `knowledge/integrity/provenance.py`) so the artifact joins the established provenance-chain family.

Because every field the trace needs already exists in today's W9 output (`confidence_breakdown`, `confidence_penalties`, `metadata.support_factor`, `metadata.gs_test`/`gs_cap`, `metadata.oos_calibration`, `metadata.w6_evidence`, `provenance_chain`), the integration is additive assembly only — the design goal of zero behavioral risk.

## 9. Acceptance criteria (design-level)

1. Every W9 value maps to exactly one ordered trace with all seven required elements (§1).
2. Reconstructing the value from the trace reproduces `final_confidence` (rounding tolerance).
3. Every step names its source component and reason code.
4. Inactive steps and absent optional inputs are recorded, not omitted.
5. No algorithm, threshold, contract, workflow, or decision logic changes are required.
6. The artifact is written per run alongside existing runtime artifacts.
