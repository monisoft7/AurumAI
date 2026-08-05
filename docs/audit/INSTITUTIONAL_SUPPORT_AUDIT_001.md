# INSTITUTIONAL_SUPPORT_AUDIT_001 — institutional_support computation

Read-only audit. No code or test modified. Facts only; no fixes or recommendations.

## 1. Scope

- Target: latest successful runtime `runtime_20260804_230820`
  (`outputs/2026-08-04/runtime_20260804_230820`, exit 0, 25/25 stages ok, git
  commit `78c9ad4` per `runtime/run_registry.jsonl`).
- Traced: the complete computation of `institutional_support` for the single
  assessed thesis `th_5a4e06fcd3a2.v2` (bullish), which becomes the
  `support_factor` consumed by `ConfidenceComputer` and the `0.315` institutional
  confidence.

## 2. The formula (single definition point)

`src/thesis_construction/builder.py:124-137` — `ThesisBuilder._compute_institutional_support`:

```
raw     = sum(s.net_institutional_weight * s.consensus_score for s in supporting_sets) / len(supporting_sets)   # builder.py:131-133
penalty = assessment.confidence_penalty                                                                            # builder.py:134
support = raw * (1.0 - penalty)                                                                                    # builder.py:135
return  max(0.0, min(round(support, 4), 1.0))                                                                      # builder.py:136
```

i.e. `institutional_support = mean(net_institutional_weight × consensus_score) × (1 − confidence_penalty)`, clamped to `[0,1]`.

Called by:
- W8 `ThesisBuilder.build_thesis` — `support = self._compute_institutional_support(...)` (`builder.py:43`), stored `institutional_support=support` (`builder.py:68`).
- W10 `ThesisUpdater.update` — `support_new = ThesisBuilder._compute_institutional_support(supporting_sets, assessment)` (`updater.py:48`), stored `institutional_support=support_new` on the `.v2` thesis (`updater.py:251`). Same sets + same assessment ⇒ W8 and W10 produce the same value.
- The `.v2` thesis is the one assessed by W9 (`stages.py:626-634`, `_construction_from_update` `stages.py:596-616`).

## 3. Input register

| # | Input | Value in this run | Weight/role | Source | File | Function | Line |
|---|---|---|---|---|---|---|---|
| 1 | supporting_set_ids (which sets enter the mean) | bullish sets, n ≥ 2, event types {ETF_FLOW, GENERAL} (mechanism `finalize.json:89`) | selection (denominator n) | `thesis_construction/constructor.py` | `_supporting_set_ids` | 93-101 |
| 2 | net_institutional_weight w_i per supporting set | mean w = 0.6094 (= evidence_quality, `finalize.json:41`) | factor inside `mean(w·c)` | `evidence_reasoning/weighter.py` | `EvidenceWeighter.weight_set` / `_compute_net_weight` | 18-35, 37-51 |
| 2a | composite_weight (per item) | evidence-determined | 0.5 × raw | `evidence_collection/collector.py` | `_build_evidence` (`cw = base_confidence × regime_weight`) | 120-121 |
| 2b | temporal_recency (per item) | evidence-determined | 0.3 × avg_recency | `evidence_collection/collector.py` | `_build_evidence` (`min(max(1/(1+abs(change_sigma)),0.1),1.0)`) | 160 |
| 2c | provenance presence (per item) | always present (W6 EvidenceCollector) | 0.2 × prov_ratio | `evidence_collection/collector.py` | `_build_evidence` (Provenance) | 137-141 |
| 3 | consensus_score c_i per supporting set | mean c (avg_supporting_consensus) derived ∈ [0.80, 1.0] (not persisted) | factor inside `mean(w·c)` | `evidence_reasoning/weighter.py` | `_compute_consensus_conflict` (`consensus = supporting/n`) | 53-75 |
| 4 | product mean(w·c) | derived ∈ [0.5689, 0.6094] | arithmetic mean, weight 1/n per set | `thesis_construction/builder.py` | `_compute_institutional_support` | 131-133 |
| 5 | confidence_penalty | 0.2 (⇒ multiplier 0.8) | multiplier `(1 − penalty)` | `counter_evidence/assessor.py` + `counter_evidence/analyzer.py` | `assess` / `compute_confidence_penalty` | assessor.py:49-53; analyzer.py:47-56 |
| 6 | clamp/round | 0.4551–0.48752 (derived) | domain [0,1], 4 dp | `thesis_construction/builder.py` | `_compute_institutional_support` | 136 |

Sub-weights inside `net_institutional_weight` (`weighter.py:37-51`):
- `raw = mean(composite_weight)` weight **0.5** (`weighter.py:41,50`)
- `recency_boost = avg_recency × 0.3` weight **0.3** (`weighter.py:43-44,50`)
- `prov_boost = prov_ratio × 0.2` weight **0.2** (`weighter.py:46-48,50`)
- `adjusted = raw*0.5 + recency_boost + prov_boost`, clamped [0,1] (`weighter.py:50-51`)

`confidence_penalty` formula (`analyzer.py:47-56`):
`conflict_severity×0.4 + len(bias_flags)×0.1 + 0.2×regime_conflict`, clamped [0,1].
For this run: `conflict_severity = 0.0`, `bias_flags = {confirmation_bias, no_dissent}` (length 2), `regime_conflict = False` (all derived in `CONFIDENCE_AUDIT_001` §8) ⇒ `penalty = 0.0×0.4 + 2×0.1 + 0 = 0.2`, so the multiplier is `(1 − 0.2) = 0.8`.

Downstream use of the value: `ConfidenceComputer.compute` reads `thesis.institutional_support` (`computer.py:39`), uses it as `support_factor` when `> 0` (`computer.py:72`), and multiplies `final = positive_score × support_factor × (1 − penalty_score)` (`computer.py:73`). The value is also copied into scenario `confidence_inputs` (`generator.py:207`) — not persisted in this run's artifacts.

## 4. Why the latest run produced institutional_support ≈ 0.455–0.488

The value is not serialized in the runtime artifacts; it is determined to lie in
`[0.4551, 0.48752]` by two independent constraints:

Upper bound (0.48752) — cap from evidence quality × penalty factor:
- `consensus_score ≤ 1` (validated, `evidence_reasoning/contracts.py:96-97`) ⇒
  `mean(w·c) ≤ mean(w) = 0.6094` (each c_i ≤ 1, each w_i ≥ 0).
- `support ≤ 0.6094 × (1 − 0.2) = 0.48752`.
- Equality requires every supporting set to have `consensus_score = 1.0`.

Lower bound (0.4551) — floor forced by the observed confidence output:
- `final = positive_score × support_factor × (1 − penalty_score) = 0.315`
  (`computer.py:73`).
- `positive_score = 0.25×0.6094 + 0.25×ec + 0.15×0 + 0.15×sd + 0.10×1 + 0.10×1
  ≤ 0.25×0.6094 + 0.25 + 0.15 + 0.10 + 0.10 = 0.75235`
  (`computer.py:14-21,56-59`).
- `penalty_score = 0.35×0.0 + 0.25×0.0 + 0.40×0.2 = 0.08`
  (`computer.py:23-27,67-70`).
- ⇒ `support ≥ 0.315 / (0.75235 × 0.92) = 0.4551`.

Therefore: `institutional_support ∈ [0.4551, 0.48752]`, equivalently
`mean(w·c) ∈ [0.5689, 0.6094]`, i.e. supporting-set consensus must have been
near-saturated (`mean(w·c)/mean(w) ≥ 0.9335` under equal per-set weights).
The interval reported by the user (0.455–0.488) matches these bounds.

## 5. Classification of the 0.8 multiplier

The 0.8 is not a literal constant in code; it is `(1.0 − penalty)`
(`builder.py:135`) with `penalty = assessment.confidence_penalty` = 0.2 for
this run.

- **Mathematically required?** No. Nothing forces support to be scaled by
  `(1 − confidence_penalty)`; it is a chosen composition. The only property
  used is that the factor is in `[0,1]` because `confidence_penalty ∈ [0,1]`
  (`counter_evidence/contracts.py:98-99`).
- **Contract-defined?** No. Contracts define the field ranges only:
  `InvestmentThesis.institutional_support: float ∈ [0,1]`
  (`thesis_construction/contracts.py:26,83-84`) and
  `CounterEvidenceAssessment.confidence_penalty: float ∈ [0,1]`
  (`counter_evidence/contracts.py:35,98-99`). No formula appears in contracts.
- **Architecture-defined?** No. The design doc `docs/design/CONFIDENCE_PROVENANCE.md`
  documents the downstream *application* of the support factor as the
  `adjustment_support` step (`support_factor`, identity when ≤ 0;
  `CONFIDENCE_PROVENANCE.md:55,80`, anchored to `computer.py:72`) but does not
  specify the formula that *produces* `institutional_support`. `ADR-0010`
  documents a different (legacy) weighting module, not this formula.
- **Hardcoded implementation choice?** Yes. The formula
  `support = raw * (1.0 - penalty)` is an implementation literal
  (`builder.py:135`), with `penalty` itself produced by the hardcoded
  `BiasAnalyzer.compute_confidence_penalty` formula (`analyzer.py:47-56`). The
  behavior is pinned by tests: `test_thesis_update.py:261` asserts
  `updated.institutional_support == 0.72` for `weight=0.8, consensus=0.9,
  penalty=0` (0.8×0.9×1.0 = 0.72); `test_thesis_construction.py:308-322`
  asserts penalty 0.5 keeps support in `(0,1]`.

## 6. Limited by design or by available evidence?

Both, at different layers:

- **Design-limited components:**
  - the multiplicative `(1 − confidence_penalty)` factor ⇒ for this run
    `support ≤ 1 − 0.2 = 0.8` regardless of evidence;
  - the `consensus_score ≤ 1` structure ⇒ `mean(w·c) ≤ mean(w)`;
  - the clamp to `[0,1]` (`builder.py:136`).
- **Evidence-limited component:**
  - `mean(w) = 0.6094` (the observed net institutional weight of the supporting
    sets), determined by the collected observations (`composite_weight =
    base_confidence × regime_weight` from `collector.py:120-121`,
    `temporal_recency` from `|change_sigma|` at `collector.py:160`,
    provenance always present `collector.py:137-141`). This is below 1.0, so it
    tightens the design cap of 0.8 down to `0.6094 × 0.8 = 0.48752`.
- **Conclusion for this run:** the interval `[0.4551, 0.48752]` is bounded
  above by the product of evidence quality (`0.6094`) and the design penalty
  factor (`0.8`). Even with perfect consensus, support could not exceed
  `0.48752`; reaching the lower part of the interval additionally requires
  maximum positive contributors (`ec=1`, `sd=1`, i.e. ≥ 3 supporting sets).
  The value is therefore limited by design (penalty multiplier, consensus
  bound) and by available evidence (mean net weight) jointly.

## 7. Observability notes (facts)

- `institutional_support` is not persisted in the runtime artifacts
  (`finalize.json`, `summary.json`, `stages.json`, `outcome.json`, `run.log`,
  `artifacts/`). It is copied into scenario `confidence_inputs`
  (`generator.py:207`) but scenario details beyond the selected scenario are
  not written for this run.
- The interval `[0.4551, 0.48752]` and the inputs in §3 marked "derived" follow
  from the code formulas plus the persisted values `0.6094 / 0.8 / 0.0 / 0.315`
  and the observed `LATE_CYCLE` regime and `bullish` direction; they are not
  directly serialized.
