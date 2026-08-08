# NEXT_BOTTLENECK_AUDIT_001

**Subject:** Which architectural bottleneck after SignalAssessment (Evidence ->
CounterEvidence -> Thesis -> Confidence -> Scenario -> RiskReward -> Decision ->
Risk/Execution) most materially limits institutional analytical quality, re-measured
on the latest post-correction runtime facts.
**Scope:** Read-only audit. No source, test, config, or capability changes.
**Reference:** docs/audit/SIGNAL_ASSESSMENT_POST_CORRECTION_AUDIT_001.md (C1-C3
verified). Re-evaluated from runtime facts, not from previous audit assumptions.
**Evidence base:** `%TEMP%\aurumai_checkpoints\runtime_20260808_195528\*.json`
(post-correction build) + current source tree.
**Date:** 2026-08-08
**Status:** VERIFIED from checkpoints and source.

---

## 1 Correction of a prior audit error (gate constant is 0.50, not 0.30)

The prior audit (SIGNAL_ASSESSMENT_POST_CORRECTION_AUDIT_001, sections 11/13)
states the institutional confidence bar as "0.30". This is wrong. The Decision
Engine gate is a hard constant `NO_TRADE_CONFIDENCE = 0.5`
(`src/decision_engine/engine.py:33`, applied at line 258: confidence < 0.5 ->
NO_TRADE). There is no 0.30 threshold anywhere in the decision chain (0.35 exists
only as `LOW_CONFIDENCE_THRESHOLD` for the low-confidence indicator, and 0.60 as
the high-confidence cap, both in `src/confidence_engine/computer.py:29-30`).

Consequence: the current NO_TRADE is not "just below the bar" (0.2494 vs a
claimed 0.30); it is **half the bar** (0.2494 vs 0.50). All decision-impact
judgments below use the correct 0.50 constant.

---

## 2 Runtime facts (single thesis th_c7d384c03b5c.v2, bullish, INFLATIONARY)

| Stage | Value |
|---|---|
| Evidence sets | es_general (support), es_etf_flow (support, new from C1), es_usd_fx (contradict) |
| W7 conflict_severity | 0.1667 (cross-set: 1 of 3 sets opposes) |
| W7 confidence_penalty | 0.2667 (0.4 x severity 0.1667 + 0.1 regime_conflict + 0.1 missing_evidence) |
| W7 missing_evidence | (CB_GOLD,) ; bias_flags: regime_conflict, missing_evidence, cross_set_conflict |
| W8/W10 institutional_support | 0.3972 = mean(net_weight x consensus) x (1 - 0.2667)  (builder.py:125-137) |
| W9 positive_score | 0.8354 (evidence_quality 0.5417, consensus 1.0, regime_alignment 1.0, source_diversity 0.6667, kr_quality 1.0, temporal_recency 1.0) |
| W9 penalty_score | 0.2484 (counter 0.35x0.1667, missing 0.25x0.3333, internal 0.40x0.2667) |
| W9 final_confidence | **0.2494** = 0.8354 x 0.3972 x 0.7516 |
| W9 caps | gs_test all_answered=True (no cap); oos_ece not passed (None) |
| W12 scenarios | confidence_source = "thesis_support" (proxy 0.3972); 3 scenarios, base p=0.5, bull 0.3147, bear 0.1853 |
| W12 RR (base) | ratio 0.9682, status **acceptable** (expected_reward 0.289, expected_risk 0.1444) |
| W13 composite | 0.5403; drivers: inst_conf 0.2494 (0.30 w), rr_quality 0.621 (0.20), evidence 0.5417 (0.15), counter_quality 0.7333 (0.15), scenario_prob 0.5 (0.10), regime_align 1.0 (0.10) |
| W13 decision | NO_TRADE, gated by confidence 0.2494 < 0.50 (NOT by RR: 0.9682 acceptable, < 2.0) |
| Bias review | critical, human_review_flag=True, findings [regime_blindness, false_precision], total_confidence_impact 0.5; applied: any directional decision would be forced to NO_TRADE (apply_bias_review, bias_prevention/contracts.py:153-191) |
| finalize | risk_decision=RiskDecision(proceed, "All risk gates pass. Full allocation advised.", score=np.float64(0.106)); forecast_validation passed=False (0 aligned pairs); legacy_decision POSITIVE conf 0.60015 |

---

## 3 Per-area findings (audit brief items 1-6)

### 4.1 CounterEvidence - is the corrected 0.2667 justified?

- Composition matches the documented rule (COUNTER_EVIDENCE_CORRECTION_V1):
  `severity*0.4 + 0.1*regime_conflict + 0.1*missing_evidence` (analyzer.py:47-56).
  Every term is evidence-backed: severity 0.1667 derives from a real cross-set
  contradiction (es_usd_fx vs majority, 1/3 ratio); regime_conflict flag fires
  on the real es_usd_fx bearish bias against INFLATIONARY; missing_evidence=CB_GOLD
  is a genuinely absent channel (verified in C2/C3 audits). **The 0.2667 itself
  is now justified.**
- **Remaining structural issue (duplication of the penalty downstream, W9 side,
  not W7 side):** the same penalty reaches the W9 product chain THREE layers:
  1. inside `confidence_penalty` -> `penalty_score` internal_consistency slot as
     `0.40 * 0.2667 = 0.1067`,
  2. inside `institutional_support` as the multiplier `(1 - 0.2667)` used as a
     second multiplicative factor (`builder.py:135`; `computer.py:72-73`: `final =
     positive_score * support_factor * (1 - penalty_score)`) with support_factor =
     same-derived `0.3972`,
  3. …while the counter-evidence slot also carries the *flat* `conflict_severity`
     (0.1667) at weight 0.35.
  Consequence: the effective penalty mass on the final is well above any single
  documented intent. Removing the `(1 - penalty)` from the support multiplier
  (single-counting the penalty only via penalty_score) with identical inputs:
  **0.2494 -> 0.3402 (+0.0908, +36.4%)** (verified arithmetic, section 5).
- **Duplicated / heuristic / filtering-driven / structurally unsupported?**
  - duplicated (E): yes - severity enters both slots; the composite penalty enters
    twice (multiplier and slot); the doc `CONFIDENCE_PROVENANCE.md:55,79` documents
    the multiplier step but **not** the `(1 - penalty)` inside it (that factor is
    introduced in `builder.py:135` and is undocumented for W9's formula).
  - heuristic: the `missing_penalty = len(remaining_unknowns)/3` is a hardcoded
    scaling (0.3333 here, 1 unknown) - documented design (F).
  - filtering-driven: none.
  - structurally unsupported: the `(1 - penalty)` inside the support multiplier is
    unsupported by the frozen confidence formula spec.
- Re-evaluated "0.3 target": with the correct gate 0.5, the previous 0.3 was not
  meaningful; this run the corrected metric (0.3402) still sits below 0.5.

### 2. Thesis / Confidence - real institutional inputs vs fallbacks

- Real inputs: evidence_quality (net institutional weight from evidence sets,
  0.5417 verified as mean of es_general 0.4334 and es_etf_flow 0.65), consensus
  1.0, regime_alignment (deterministic from REGIME_EXPECTED_BIAS), source_diversity
  (2 supporting sets / 3 = 0.6667), knowledge_record_quality (chain length/2 - a
  **structural proxy**, value 1.0, not a reading of any record quality), missing
  panel from W7.
- **Unjustified fallback found (`D`):** `temporal_recency` defaults to **1.0**
  whenever the thesis metadata has no `avg_temporal_recency`
  (`computer.py:112-116`), and **no producer of `avg_temporal_recency` exists
  anywhere in the source tree** (searched; only the consumer exists). Every thesis
  receives the maximum 0.10-weight credit unconditionally. If that credit were
  removed, this run's final drops 0.2494 -> ~0.2194 (-0.030, -12%). Legitimate
  data exists in the same w6/w7 flow to compute it (evidence item timestamps are
  present); currently nothing does.
- No other fallback/proxy/synthetic value materially affects confidence: scenario
  probabilities inherit the same proxy (see 3), and the gs_test is fully
  satisfied (all answered True) so no cap applies.

### 3. ScenarioGeneration - conformity + dead dependency check

- The W12 generator no longer imports or calls `ConfidenceEngine` (only the static
  `ConfidenceComputer.reliability_category` helper for labels). The previous dead
  dependency on the W9 engine is **fully eliminated**: `scenario_generation`
  depends only on `thesis_construction` (orchestrator.py:307-313), and W9 consumes
  W11 (correct direction).
- `confidence_source = "thesis_support"` - a documented deterministic proxy
  (PROJECT_SCOPE_V1 sec 6.6, "W12 runs before W9"). The proxy value is
  `institutional_support = 0.3972`, the penalty-adjusted mean. BUG (minor,
  label-only): the `confidence_id` on `ScenarioGeneration` is hardcoded to
  `"cf_fallback_<construction_id>"` (generator.py:99) even when the source is
  thesis_support and no fallback happened. Cosmetic, no data impact.
- Division of labor: scenario probabilities (and therefore the RR layer) use
  `0.3972`, while the DecisionEngine gate uses W9 final `0.2494`. Two different
  confidence concepts coexist in the same decision path, labeled identically
  ("final_confidence" inside scenario confidence_inputs). See 4/5 for the seam
  this creates on RR status.

### 4. RiskRewardValidation

- Inputs are all scenario-derived synthetic scalars (no market measures); every
  input is now produced/labeled by the corrected stack: scenario
  `confidence_inputs.final_confidence = the proxy 0.3972`,
  `remaining_uncertainty = 0.6028`, regime_path, time_horizon, probability.
- `risk_reward_ratio = 0.9682 (acceptable)` on the proxy. **Fallback-derived?**
  No fallback fired: `conf_unc_rel` all present (`validator.py:100-112`); defaults
  ("very_low" 0.75) not engaged.
- **Material sensitivity discovered (dual-confidence seam):** recomputing the
  base-scenario RR with W9's confidence (0.2494) instead of the proxy (0.3972)
  flips the status:
  - proxy: upside_potential = (0.3+0.7x0.3972)x(0.4+0.6x1.0) = 0.578; expected
    reward = 0.5x0.578 = 0.289; risk_score = 0.2798; ratio = 0.9682 -> acceptable.
  - W9 value: (0.3+0.7x0.2494) = 0.4746; reward = 0.2373; risk_score = 0.305;
    ratio = 1.285 -> borderline.
  Both are eligible in the decision engine (ELIGIBLE_STATUSES includes borderline:
  `engine.py:40`), so the decision does not change, but the seam is visible and
  the "acceptable" label is a property of the proxy choice, not of W9.

### 5. DecisionEngine - what exactly drove NO_TRADE

- Exact values: `institutional_confidence = 0.2494`; gate `confidence < 0.5`
  (engine.py:258) => NO_TRADE. RR was `0.9682 (acceptable)` and << 2.0 - not a
  gate trip. The thesis is the selected (only) thesis; composite 0.5403 contains
  a healthy 0.1242 RR-quality contribution. The gate is correctly rejecting *the
  thesis given the confidence value*.
- **Is the gate "dominated by an upstream artifact"?** The 0.2494 is depressed
  by the duplicated penalty application (see 1): single-counted would be 0.3402.
  Correcting that does not flip the decision (0.3402 < 0.5). Full multiplier
  removal (0.6279, a spec redesign) WOULD flip to BUY, but even then the bias
  gate (severity-critical -> downgrade of any directional decision to NO_TRADE,
  contracts.py:174-181) would force NO_TRADE on this run's findings. So at
  current facts **no composition change can alter the emitted decision** - the
  bias gate is the binding higher constraint.
- Thresholds not changed. Verdict: rejection is structurally justified; the
  upstream decision value is systematically understated (36% of the penalty
  double-applied), but the gate outcome stands on multiple independent legs.

### 6. Execution / Risk branch - connectivity

- `decision_engine -> trade_recommendation` -> recommendation text (no order
  semantics). The execution modules (`src/execution/*`) are **not referenced by
  any pipeline job** (verified orchestrator.py job list: no execution stage).
- `risk_gate` (RiskDecision) computed in the *forecast branch* with deps
  build_context/build_legacy_pipeline/risk_measures/position_sizing, NOT from
  the institutional branch; its output is only bundled into `finalize` as
  `risk_decision`. **Nothing consumes it for allocation or veto.**
- **Synthetic input (D):** `_risk_gate` calls `UncertaintyBudget.evaluate(
  context_coherence=0.5, ...)` with the coherence hardcoded (stages.py:411) while
  the forecast's own real `context_coherence = 0.1178` (forecast_confidence).
  The RiskDecision "All risk gates pass. Full allocation advised" rests on a
  fabricated coherence value.
- Classification: this is **future execution infrastructure (G)**, not an active
  bottleneck: today it neither generates nor blocks anything authoritative. It
  BECOMES material the moment anyone wires it without first reconciling
  (it is running on hardcoded coherence and is informed of the institutional
  NO_TRADE or the bias hold).

## 4 Bottleneck quantification (candidate table)

| # | Candidate | Current | Ideal/justified (from current evidence) | Confidence impact | Decision impact | Class |
|---|---|---|---|---|---|---|
| B1 | Penalty applied twice in W9 composition (mult (1-P) inside support_factor + slot `internal_consistency` 0.40xP; severity also in counter slot) | 0.2494 | 0.3402 (single-count penalty; verified 0.8354 x 0.5417 x 0.7516) | +0.0908 (+36.4% metric) | none today (0.34 < 0.5; bias gate binds) | E (duplicated, (1-P) undocumented in the frozen formula) |
| B2 | temporal_recency default 1.0 with no producer in tree | 1.0 | unknowable; remove unsourced credit -> 0.0 | -0.030 (if 0) | none | D (fallback/proxy) |
| B3 | risk_gate uses hardcoded context_coherence=0.5 (real: 0.1178) and is disconnected from decision authority + no execution job | proceed/100% | wired consumption; coherence from forecast | none today (no consume) | none today (G) | F/G, with D input |
| B4 | Two confidence concepts in one decision path: scenario proxy 0.3972 vs W9 0.2494; RR status flips acceptable<->borderline between them; `confidence_id` always "cf_fallback_*" | 0.9682 acceptable | single consistently-sourced confidence (W9 value for both W9 and scenario/RR paths; proxy used only for ordering) | RR status flips to borderline at W9 value (ratio 1.28, > 1.00) | none (borderline still eligible: engine.py:40) | F (documented freeze) + label mislabel |
| B5 | institutional branch: single thesis, zero alternatives | n/a | multi-thesis (needs multiple thesis builders) | structural, not numerical | none now | F (architecture) |

Notes: B4's status flip is NOT a fallback defect: both status classes enter the
eligible set; no decision impact. B5 is intentionally minimal (single-thesis given
single composite signal) - listed as F, not a bottleneck today.

---

## 5 Ranked top 5 bottlenecks by actual impact

Ranking criterion: **impact on institutional decision quality measured at runtime
facts** (decision -> metric -> integration). All verified numerically above.

1. **B1 - duplicated counter-evidence penalty in the W9 composition
   (support_factor carries (1-P); penalty_score carries P and severity again).**
   - Verdict: the only *real* analytical defect of the whole chain; proves ~36%
   metric understatement. But it does not change this run's or any counterfactual
   run's decision (gate 0.5, bias gate, RR reduced by B4) -> **no material
   decision impact proven**.
2. **B3 - risk branch on fabricated inputs and disconnected from the decision
   authority (D/F/G).** Current decision impact zero (nothing executes), but it
   is the largest ready-to-fire latent contradiction: the same runtime emits
   NO_TRADE (institutional, bias-blocked) alongside "proceed / full allocation
   advised" (RiskDecision). All three voices (institutional, legacy POSITIVE
   0.6009, risk proceed) disagree with no reconciliation.
3. **B4 - dual-source confidence (scenario proxy 0.3972 vs W9 0.2494) with
   RR-status hinge and the permanent "cf_fallback_" label.** Visible seam; flips
   RR label; does not flip eligibility; non-material today, but hard-wired
   design that any future consumer will misread.
4. **B2 - unsourced temporal_recency full credit (0.10 weight awarded to
   everything).** Undue in every run; magnitude per run ~0.03; decision-neutral
   but systematically inflates.
5. **B5 - absence of a second/third thesis (single-thesis pipeline).** F.
   A future alternative-selection capability, not a defect at single-candidate
   scale.

No candidate passes the test "currently and materially affects the final
institutional decision": B1 changes the metric by 36% but never the decision
(both counterfactuals verified); B2-B5 are small or inactive today; the bias
gate currently overrides any hypothetical correction-driven directional change.
(If a later run sits within ~0.1 of the 0.5 gate with a clean bias review, B1
becomes the justified single correction - see section 6.)

---

## 6 Executable-spec one-liner

If later evidence (e.g., a run where the thesis sits within 0.1 of the 0.5 gate
and the bias review is clean) proves a *decision-relevant* downstream dependency,
the single justified correction is: **remove the `(1 - confidence_penalty)`
factor from the theses `institutional_support` multiplier (`builder.py:135`),
keeping the quantified W9 penalty_score as the single penalty application** -
this returns 0.2494 to 0.3402 with existing constants. Not recommended today
(no decision impact proven; spec freeze documented).

All documented candidates are non-material at current facts by the audit's own
accuracy criterion.

---

## 7 Files consulted (read-only)

- `src/counter_evidence/analyzer.py`, `detector.py`, `assessor.py`
- `src/confidence_engine/computer.py`, `engine.py`, `contracts.py`
- `src/thesis_construction/builder.py` (W8/W10 support computation)
- `src/thesis_update/updater.py`
- `src/scenario_generation/generator.py`, `contracts.py`
- `src/risk_reward_validation/validator.py`, `contracts.py`
- `src/decision_engine/engine.py`, `contracts.py`
- `src/bias_prevention/detector.py`, `contracts.py`
- `src/orchestration/stages.py`, `orchestrator.py`
- runtime checkpoints `%TEMP%\aurumai_checkpoints\runtime_20260808_195528\*.json`
- docs: CONFIDENCE_PROVENANCE.md (formula spec), COUNTER_EVIDENCE_CORRECTION_V1.md,
  prior audits (composition numbers verified against runtime, atomic).

---

## Conclusion

The institutional decision path after the corrections runs on honest,
connected inputs; the only structural number-level defect found (duplicated
penalty applied twice to one confidence metric) is decision-neutral at current
runtime facts (verified 0.2494 ---> 0.3402, still below the 0.50 gate; flip of
any non-NO_TRADE outcome is additionally blocked by the critical bias review).
No candidate materially changes the institutional decision today; the
highest-value action is operational validation (second real observation of OI,
watch for a two-template-violation night to exercise the C3 dedup fix in
production), and the next material candidates (risk-branch reconciliation,
recency-sourced recency, the permanent false "cf_fallback_" label, dual-source
confidence reconciliation) are all F/G/D-class items that do not meet the
"materially affects institutional decision quality" bar with current evidence.

**Stop corrections and continue operational validation**