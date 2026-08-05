# CONFIDENCE_COMPONENT_IMPORTANCE_001 — Contribution of every Institutional Confidence component

Read-only audit. No code or test modified. Facts only; no fixes or recommendations.

## 1. Scope and method

- Run: latest successful `runtime_20260804_230820` (`outputs/2026-08-04/runtime_20260804_230820`, exit 0, 25/25 stages ok, git commit `78c9ad4` per `runtime/run_registry.jsonl`).
- Final value measured: `institutional_confidence = 0.315` (`finalize.json:65`, driver `finalize.json:26-31`), produced by `ConfidenceComputer.compute` and adjusted by `ConfidenceEngine.evaluate`.
- Method: **sequential chain attribution** on the multiplication chain at `src/confidence_engine/computer.py:56-74`. Baseline = maximum confidence `1.0` (every positive input at 1.0, `support_factor = 1.0`, `penalty_score = 0.0`, no caps). Each factor is applied in the code's order; the reduction it causes is `value_before × (1 − factor)`. The deltas sum exactly to the total reduction:
  `1.0 − 0.315 = 0.685` (68.5% of the achievable maximum).
- Inputs that are not persisted are taken from the derived bounds in `CONFIDENCE_AUDIT_001.md` §8 and `INSTITUTIONAL_SUPPORT_AUDIT_001.md` §4: `evidence_consensus ec ∈ [0.80, 1.0]`, `source_diversity sd ∈ {0.6667, 1.0}`, `institutional_support ∈ [0.4551, 0.48752]`.

## 2. The confidence chain

`final = positive_score × support_factor × (1 − min(penalty_score, 1))`, clamped to `[0,1]` and rounded to 4 dp (`computer.py:73-74`; reason code `FORMULA_POSITIVE_PENALTY_SUPPORT`, `docs/design/CONFIDENCE_PROVENANCE.md:79`).

- `positive_score = Σ weight_i × value_i` over 6 positives (`computer.py:47-59`, weights `computer.py:14-21`).
- `penalty_score = Σ weight_i × value_i` over 3 penalties (`computer.py:61-70`, weights `computer.py:23-27`).
- `support_factor = institutional_support` when `> 0`, else `1.0` (`computer.py:72`).
- Caps applied after: GS cap (`engine.py:63-64,67-68`) and OOS cap (`engine.py:65,69-72`), then clamp/round (`engine.py:73`).

For this run: `positive_score A ∈ [0.70232, 0.75235]`, `support_factor S ∈ [0.4551, 0.48752]`, `penalty_score = 0.08` (only the internal_consistency term nonzero), hence `A × S = 0.315 / 0.92 = 0.3423913` and `A × S × 0.92 = 0.315`.

## 3. Sequential decomposition (sums exactly to 0.685)

| Step | Baseline → | After | Reduction | % of total (0.685) |
|---|---|---|---|---|
| Positive-term shortfall | 1.0 | A | `1 − A` = **[0.24765, 0.29768]** | **[36.15%, 43.46%]** |
| Support-factor multiply | A | A×S | `A×(1−S)` = **[0.3599, 0.4100]** | **[52.54%, 59.85%]** |
| Penalty-block multiply | A×S | A×S×0.92 | `A×S×0.08` = **0.0273913** | **4.00%** |
| GS cap | 0.315 | 0.315 | 0.0 | 0% |
| OOS cap | 0.315 | 0.315 | 0.0 | 0% |
| **Total** | 1.0 | **0.315** | **0.685** | 100% |

The endpoints are coupled (not independent): `A = 0.75235` only occurs with `S = 0.4551` (requires `ec = 1.0`, `sd = 1.0`); `A = 0.70235` occurs with `S = 0.48752` (either `ec = 1.0, sd = 0.6667` or `ec = 0.80, sd = 1.0`). Both endpoint pairs reproduce 0.315 exactly.

## 4. Per-component register

For each component: raw value, weight/role, raw reduction (baseline units), percentage of total confidence reduction (0.685), and source file/function/line.

| Component | Value | Weight/role | Raw reduction | % of total reduction | File | Function | Line |
|---|---|---|---|---|---|---|---|
| evidence_quality | 0.6094 | positive, 0.25 | 0.09765 (=0.25×(1−0.6094)) | **14.26%** | `src/confidence_engine/computer.py`; produced `src/thesis_construction/builder.py` | `ConfidenceComputer.compute`; `ThesisBuilder.build_thesis` | computer.py:35,48,56 (weight :15); builder.py:110-112 |
| counter_evidence_quality | 0.8 (= 1 − 0.2) | decision driver; **not a direct chain input** | 0.0 direct (effect fully inside institutional_support and internal_consistency) | 0% direct | `src/decision_engine/engine.py` | `DecisionEngine._build_drivers` | engine.py:282-284 (reads penalty computer.py:38; driver formula engine.py:207) |
| institutional_support | [0.4551, 0.48752] | multiplicative `support_factor` | [0.3599, 0.4100] | **[52.54%, 59.85%]** | `src/thesis_construction/builder.py`; `src/confidence_engine/computer.py` | `ThesisBuilder._compute_institutional_support`; `ConfidenceComputer.compute` | builder.py:124-137; computer.py:39,72-73 |
| regime_alignment | 0.0 | positive, 0.15 | 0.15 (=0.15×(1−0)) | **21.90%** | `src/confidence_engine/computer.py` | `ConfidenceComputer.compute` / `ConfidenceComputer._regime_alignment` | computer.py:41,56; :103-109 |
| internal_consistency | 0.2 (confidence_penalty) | penalty, 0.40 | 0.0273913 (=A×S×0.40×0.2) | **4.00%** | `src/confidence_engine/computer.py` | `ConfidenceComputer.compute` | computer.py:38,64,67-70 (weight :26) |
| consensus_score (evidence_consensus) | [0.80, 1.0] | positive, 0.25 | [0, 0.05] (=0.25×(1−ec)) | [0%, 7.30%] | `src/confidence_engine/computer.py`; produced `src/thesis_construction/builder.py` | `ConfidenceComputer.compute`; `ThesisBuilder.build_thesis` | computer.py:36,56 (weight :16); builder.py:113-115 |
| confidence_penalty | 0.2 | root value of internal_consistency and of the support multiplier | 0.0273913 exclusively via internal_consistency (already counted above); also inside institutional_support's (1−0.2)=0.8 multiplier | 4.00% exclusive | `src/counter_evidence/analyzer.py`; `src/counter_evidence/assessor.py`; applied `builder.py` / `computer.py` | `BiasAnalyzer.compute_confidence_penalty`; `CounterEvidenceAssessor.assess`; `ConfidenceComputer.compute` | analyzer.py:47-56; assessor.py:49-53; builder.py:134-135; computer.py:38,64 |
| GS cap | not triggered (0.315 < 0.60) | cap at HIGH_CONFIDENCE_THRESHOLD=0.60 | 0.0 | 0% | `src/confidence_engine/engine.py` | `ConfidenceEngine.evaluate` / `_gs_test` | engine.py:63-64,67-68; :137-163 |
| OOS calibration | `oos_ece` absent → `None` | cap at 0.35/0.60 | 0.0 | 0% | `src/confidence_engine/engine.py`; `src/orchestration/stages.py` | `ConfidenceEngine.evaluate` / `_oos_cap`; `_confidence_engine` | engine.py:65,69-72,165-173; stages.py:645-647 |

Chain components present but not in the requested list (included for a complete sum to 68.5%):

| Component | Value | Weight | Raw reduction | % of total | File:Function:Line |
|---|---|---|---|---|---|
| source_diversity | 0.6667 or 1.0 | positive, 0.15 | [0, 0.05] | [0%, 7.30%] | computer.py:42,56; thesis_construction/constructor.py:93-101 |
| knowledge_record_quality | 1.0 | positive, 0.10 | 0.0 | 0% | computer.py:43,56 (chain length 3, updater.py:253) |
| temporal_recency | 1.0 | positive, 0.10 | 0.0 | 0% | computer.py:44,56; :112-116 (no metadata key, updater.py:237-239) |
| counter_evidence penalty | conflict_severity = 0.0 | penalty, 0.35 | 0.0 | 0% | computer.py:37,62,67-70; analyzer.py:30-44 |
| missing_evidence penalty | 0.0 (LATE_CYCLE not in `REGIME_EXPECTED_EVENT_TYPES`) | penalty, 0.25 | 0.0 | 0% | computer.py:45,63,67-70; counter_evidence/detector.py:9-16,108-114 |

## 5. Ranking — largest to smallest confidence reduction

Primary ranking (each unit of the 68.5% attributed exactly once):

1. **institutional_support** — [0.3599, 0.4100] — **[52.54%, 59.85%]** — builder.py:124-137; computer.py:39,72-73
2. **regime_alignment** — 0.15 — **21.90%** — computer.py:41,103-109
3. **evidence_quality** — 0.09765 — **14.26%** — computer.py:35,48,56; builder.py:110-112
4. **internal_consistency** — 0.0273913 — **4.00%** — computer.py:38,64,67-70
5. **consensus_score** — [0, 0.05] — **[0%, 7.30%]** — computer.py:36,56; builder.py:113-115
6. **knowledge_record_quality / temporal_recency / counter_evidence penalty / missing_evidence penalty** — 0.0 — 0% each
7. **GS cap** — 0.0 — 0% — engine.py:63-64,67-68
8. **OOS calibration** — 0.0 — 0% — engine.py:65,69-72,165-173; stages.py:645-647

Mapping of the two requested components that are derived views of the same penalty (not additive to the above; their effect is contained in ranks 1 and 4):

- **confidence_penalty (0.2)**: root cause of rank 4 (internal_consistency `0.40×0.2 = 0.08` of penalty_score → 0.0273913, 4.00%) and of the `(1 − 0.2) = 0.8` multiplier inside rank 1 (`institutional_support = mean(w·c) × (1 − confidence_penalty)`, builder.py:135). Exclusive direct chain effect: **4.00%**.
- **counter_evidence_quality (0.8)**: the decision-driver form of the same value (`1 − confidence_penalty`, engine.py:282-284; composite weight 0.15 at engine.py:29,207). It is not read by `ConfidenceComputer`; it has no independent reduction inside the confidence chain. Direct effect: **0%**.

## 6. Verbatim reconstruction checks

- Max-reduction end (`ec=1.0, sd=1.0`, `S=0.4551`): positive shortfall `0.09765+0+0.15+0 = 0.24765`; support `0.4100`; penalty `0.02739`; total `0.685`; `A×S×0.92 = 0.75235×0.4551×0.92 = 0.315`.
- Min-reduction end (`S=0.48752`): `A = 0.70235`; support `0.3599`; penalty `0.02739`; positive shortfall `0.29765`; total `0.685`; `0.70235×0.48752×0.92 = 0.315`.
- Penalty-block delta independent of `S`: `0.315/0.92 × 0.08 = 0.0273913` (4.00%).

## 7. Observability limitations (facts)

- `confidence_breakdown`, `positive_contributors`, `negative_contributors`, `confidence_penalties`, and `metadata.support_factor` are constructed in memory (`computer.py:76-99`, `engine.py:88-100`) and are **not serialized** in the runtime artifacts. Only `final_confidence = 0.315` reaches `finalize.json` (via DecisionEngine driver, `finalize.json:26-31`).
- `evidence_consensus`, `source_diversity`, `conflict_severity`, `institutional_support`, and the exact supporting-set count are therefore derived, not observed; the bounds used here come from `CONFIDENCE_AUDIT_001.md` §8 and `INSTITUTIONAL_SUPPORT_AUDIT_001.md` §4.
- The `finalize.json` top-level `confidence` object (`overall 0.7169`, `finalize.json:2-7`) is the **forecast** confidence (`src/forecasting/confidence.py`), not the institutional confidence; it is not part of this chain.
- GS test outcome (`all_answered`) is not persisted for this run; whether or not it fired, the cap is a no-op because `0.315 < HIGH_CONFIDENCE_THRESHOLD = 0.60` (`engine.py:67-68`).
