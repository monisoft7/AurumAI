# COUNTER_EVIDENCE_VALIDATION_001

**Subject:** Complete audit of every penalty applied by W7 CounterEvidenceAssessor in `runtime_20260806_234356` (assessment `cea_98a910c7a650`).
**Scope:** Read-only. All values verified against checkpoints (`counter_evidence.json`, `evidence_reasoning.json`, `evidence_collection.json`, `thesis_update.json`, `confidence_engine.json`, `pre_market_scan.json`, `forecast_validation.json`, `scenario_generation.json`) and source (`src/counter_evidence/assessor.py`, `detector.py`, `analyzer.py`, `src/thesis_construction/builder.py`, `src/confidence_engine/computer.py`, `engine.py`, `src/orchestration/stages.py`). No code modified, nothing implemented.
**Date:** 2026-08-07
**Status:** FACTS ONLY. No recommendations.

---

## 1. What W7 Produced

```
confidence_penalty = 0.7
conflict_severity  = 0.25
bias_flags         = (no_dissent, regime_conflict, missing_evidence, cross_set_conflict)
regime_conflict    = True
supporting_sets    = (es_usd_fx,)        # DXY, bias=bearish
contradicting_sets = (es_general,)       # XAU/USD anomalies, bias=bullish
missing_evidence   = (CB_GOLD, INFLATION, REAL_YIELD)
```

## 2. W7 Inputs (the only data W7 can see)

`_counter_evidence` (stages.py:643-658) passes **only** `EvidenceReasoning` into the assessor. No risk measures, no forecast/calibration data, no event-tiering information, no thesis state.

EvidenceReasoning (evidence_reasoning.json, 21:46:30.954):

| Set | Event type | Bias | Items | consensus | conflict_score | net weight |
|---|---|---|---|---|---|---|
| es_usd_fx | USD_FX | bearish | 1 (DXY synthetic obs) | 1.0 | 0.0 | 0.4601 |
| es_general | GENERAL | bullish | 2 (XAU anomaly obs; 1 duplicate removed) | 1.0 | 0.0 | 0.4323 |

Regime passed: `INFLATIONARY`.

## 3. The Exact 0.7 Decomposition

`compute_confidence_penalty` (analyzer.py:47-56):

```
penalty = conflict_severity × 0.4          = 0.25 × 0.4 = 0.10
        + len(bias_flags) × 0.1            = 4 × 0.1    = 0.40
        + 0.2 if regime_conflict           =              0.20
        = 0.70
```

`compute_conflict_severity` (analyzer.py:30-44): `cross_ratio(1/2) × 0.5 + avg_conflict(0.0) × 0.5 = 0.25`.

Six additive 0.1-units, traceable to **four distinct facts**:

| Unit | Source | Value |
|---|---|---|
| U1 | severity term (conflict_severity×0.4) | 0.10 |
| U2 | bias_flag `cross_set_conflict` | 0.10 |
| U3 | bias_flag `regime_conflict` | 0.10 |
| U4 | bias_flag `no_dissent` | 0.10 |
| U5 | bias_flag `missing_evidence` | 0.10 |
| U6 | regime_conflict boolean | 0.20 |
| | **Total** | **0.70** |

## 4. Per-Penalty Traces

### 4.1 cross-set conflict — severity term (U1, 0.10)

1. **Originating observation:** es_usd_fx (DXY, bearish) vs es_general (XAU/USD anomalies, bullish).
2. **Evidence supporting:** Real market data in this run: DXY +0.2658% (σ 0.7639); XAU/USD +1.2459% (σ 0.7594) with anomaly flags template_violation 0.9801 and correlation_regime_shift 1.4782. Both instruments moved **in the same direction** — an anomalous configuration — mapped to opposing biases (DXY up → gold bearish via "USD inverse correlation" mechanism; XAU up → gold bullish direct).
3. **Evidence quality:** real (prices), **inferred** (bias sign assignment), **synthetic** (anomaly items carry change_pct=0.0 placeholders instead of the real +1.2459% move). Bias assignments are heuristics.
4. **Exact formula:** severity = round(0.5 × (1 contra / 2 sets) + 0.5 × (0.0 avg conflict), 4) = 0.25; unit = 0.25 × 0.4 = 0.10.
5. **Weight:** 0.10 (of the 0.7); W9 also charges 0.25 × 0.35 = 0.0875 in penalty_score.
6. **Contribution to confidence loss:** ≈ −0.0142 final confidence (marginal at P=0.7; via internal_consistency channel), plus −0.0074 via the W9 counter_evidence channel.
7. **Avoidable using runtime info:** No — the contradiction is real market data. (Its duplicate, U2, is avoidable — see 4.2.)
8. **Cause:** real contradictory evidence.

### 4.2 cross-set conflict — flag (U2, 0.10)

1. **Originating observation:** same as 4.1. Flag fired because es_general bias=bullish ≠ majority bias=bearish (detector.py:34-69).
2. **Evidence supporting:** identical to 4.1. **The flag and the severity term are computed from the same single fact.**
3. **Evidence quality:** real (duplicate).
4. **Exact formula:** `cross_set_conflict` appended when contradicting_ids non-empty (assessor.py:46-47); unit = 1 flag × 0.1.
5. **Weight:** 0.10.
6. **Contribution to confidence loss:** ≈ −0.0142.
7. **Avoidable:** Yes — the information is already fully counted by U1. Removing U2 loses no information (contradicting_ids still produce severity; labels remain in the assessment).
8. **Cause:** heuristic (structural double-count of the same fact).

**Tie-break artifact (same fact):** with 2 sets at 1v1, `bias_counts.most_common(1)` returns the first set in tuple order (bearish) as "majority" (detector.py:52). If es_general were first, es_usd_fx would be the contradicting set and labels would flip. The penalty value (0.7) is invariant to this; only supporting/contradicting labels are order-dependent.

### 4.3 regime_conflict — flag (U3, 0.10)

1. **Originating observation:** es_usd_fx bias=bearish in regime INFLATIONARY.
2. **Evidence supporting:** regime INFLATIONARY (real, detected at 21:46:10, regime_confidence 0.6); es_usd_fx bearish (real evidence). The link between them is the **hardcoded table** `REGIME_EXPECTED_BIAS = {INFLATIONARY: "bullish"}` (detector.py:19-26): bearish = OPPOSITE_BIAS["bullish"] → flag fires.
3. **Evidence quality:** regime real; bias real (inferred sign); the INFLATIONARY→bullish mapping is **synthetic** (static assumption, not derived from runtime data).
4. **Exact formula:** `regime_conflict(sets, regime)` returns True if any set bias == OPPOSITE_BIAS[REGIME_EXPECTED_BIAS[regime]] (detector.py:71-83); unit = 0.1.
5. **Weight:** 0.10 (as a flag) — plus U6 (0.20, same detector call, assessor.py:50).
6. **Contribution to confidence loss:** ≈ −0.0142 (flag) and −0.0284 (bool); the same fact is also penalized a third time inside W9 as `regime_alignment = 0.0` (positive contributor weight 0.15 yields 0.000 instead of 0.150 when aligned — computer.py:41, 102-109).
7. **Avoidable:** No, given the mapping — the mismatch (bearish evidence in a bullish-expected regime) is real. The magnitude rests on the hardcoded mapping, not on runtime evidence.
8. **Cause:** heuristic (hardcoded regime→bias table) over real regime + real evidence.

### 4.4 regime_conflict — boolean (U6, 0.20)

1. **Originating observation:** same as 4.3.
2. **Evidence supporting:** same fact as U3; no additional evidence.
3. **Evidence quality:** real (duplicate of U3).
4. **Exact formula:** assessor.py:50 `regime_conflict_flag = self._detector.regime_conflict(...)`; analyzer.py:54-55 `penalty += 0.2 if regime_conflict`. **The same boolean call that produced U3 is charged a second time at double rate.**
5. **Weight:** 0.20.
6. **Contribution to confidence loss:** ≈ −0.0284.
7. **Avoidable:** Yes — structurally redundant with U3 (same detector invocation); the fact is already counted in U3 and in W9's regime_alignment.
8. **Cause:** heuristic (structural double-count, one fact charged 0.30 across U3+U6, plus a third charge in W9).

### 4.5 no_dissent (U4, 0.10)

1. **Originating observation:** both evidence sets report conflict_score = 0.0.
2. **Evidence supporting:** real: es_usd_fx consensus 1.0 (1/1 item uniform), es_general consensus 1.0 (2/2 uniform) → conflict_score 0.0 in both.
3. **Evidence quality:** real (within-set unanimity) — but the flag's definition (analyzer.py:23-27: all conflict_scores == 0.0) ignores cross-set dissent. The run simultaneously flags `cross_set_conflict` — i.e., dissent exists while the flag claims there is none.
4. **Exact formula:** `no_dissent = all(es.conflict_score == 0.0)` → True; unit = 0.1.
5. **Weight:** 0.10.
6. **Contribution to confidence loss:** ≈ −0.0142.
7. **Avoidable:** Yes — the dissent information it is meant to detect is already available in contradicting_ids (U1/U2). The flag is a mislabeled heuristic whose trigger condition (within-set unanimity) is not the concept it names (absence of dissent).
8. **Cause:** heuristic (mislabeled definition).

### 4.6 missing_evidence (U5, 0.10)

1. **Originating observation:** no evidence items with event_type in {CB_GOLD, INFLATION, REAL_YIELD}.
2. **Evidence supporting:** `REGIME_EXPECTED_EVENT_TYPES["INFLATIONARY"] = {INFLATION, REAL_YIELD, USD_FX, CB_GOLD}` (detector.py:9-16, hardcoded); present = {USD_FX, GENERAL} → missing = {CB_GOLD, INFLATION, REAL_YIELD} (detector.py:107-114).
3. **Evidence quality:** **mixed**:
   - CB_GOLD: **missing** — no central-bank gold data source exists anywhere in the scan universe (pre_market_scan.json contains no CB gold observation).
   - INFLATION: **available but excluded** — pre_market_scan.json (21:46:30.890) contains `obs_Breakeven Inflation` (change_pct −0.9174) with **change_sigma = nan**.
   - REAL_YIELD: **available but excluded** — pre_market_scan.json contains `obs_US10Y Real Yield` (change_pct +0.4115) with **change_sigma = nan**.
   - Both NaN-σ observations were tiered Tier 4 (signal_assessment.json 21:46:30.915 / event_triage.json 21:46:30.927: filtered_noise_count=5) and never reached evidence collection (21:46:30.939). All of this existed in the runtime **before** W7 ran (21:46:30.966).
4. **Exact formula:** sorted(expected − present); flag appended if non-empty; unit = 0.1. Downstream, the 3 channels become thesis `remaining_unknowns` → W9 `missing_penalty = min(3/3, 1.0) = 1.0` (computer.py:45) charged at weight 0.25.
5. **Weight:** 0.10 (flag) + 0.25 in W9 penalty_score (via remaining_unknowns).
6. **Contribution to confidence loss:** ≈ −0.0142 (flag) plus −0.0212 (W9 missing_evidence channel 0.25×0.25... computed counterfactual).
7. **Avoidable:** Partially — for 2 of the 3 channels (INFLATION, REAL_YIELD) the observations were present in the runtime but excluded by the sigma-based tiering (NaN σ → noise). Had they been admitted, the flag (and the remaining_unknowns penalty) would shrink. CB_GOLD is not avoidable (no producer).
8. **Cause:** missing producer (CB_GOLD) + disconnected producer (tiering/filtering excluded available INFLATION and REAL_YIELD observations).

## 5. Downstream Confidence Loss (how the 0.7 hits final numbers)

The 0.7 is consumed **twice multiplicatively**:

1. **Thesis support** (builder.py:125-137): `institutional_support = raw × (1 − confidence_penalty) = 0.4601 × 0.3 = 0.138` (thesis_update.json: new_support 0.138).
2. **W9 internal_consistency** (computer.py:23-27, 61-70): thesis.confidence_inputs["confidence_penalty"] = 0.7 → penalty 0.7 × 0.4 = 0.28 in penalty_score.

Full W9 chain (confidence_engine.json, verified): `final = positive_score(0.61502) × support_factor(0.138) × (1 − penalty_score(0.6175)) = 0.0325`.

```
positive_score = 0.4601×0.25 + 1.0×0.25 + 0.0×0.15 + 0.3333×0.15 + 1.0×0.1 + 1.0×0.1 = 0.61502
penalty_score  = 0.0875 (counter_evidence: 0.25×0.35)
               + 0.25   (missing_evidence: 1.0×0.25)
               + 0.28   (internal_consistency: 0.7×0.4)
               = 0.6175
```

Confidence-loss attribution (counterfactuals against final 0.0325; no-W7 baseline = 0.2830 → W7 total loss 0.2505):

| Channel | Counterfactual final | Loss vs 0.0325 |
|---|---|---|
| Remove internal_consistency (0.28) | 0.0562 | 0.0237 |
| Remove missing_evidence ps (0.25) | 0.0537 | 0.0212 |
| Remove counter_evidence ps (0.0875) | 0.0399 | 0.0074 |
| Remove support-factor dampening (0.138 → 0.4601) | 0.1082 | 0.0757 |
| **Remove the 0.7 entirely (support 0.4601, internal 0)** | **0.1875** | **0.1550** |

Per-penalty-unit marginal at P=0.7: d(final)/d(unit) ≈ −0.0142 per 0.1 unit (0.1 → ≈−0.014; 0.2 → ≈−0.028).

The penalty also reaches risk/reward validation: scenario confidence_inputs inherit `institutional_support = 0.138` (generator.py:169), feeding `maximum_downside = uncertainty(0.5399) + support(0.138) = 0.6779` (risk_reward_validation.json) — i.e., the 0.7 indirectly raised the base-scenario risk_reward_ratio driver in the no-trade decision chain.

Note: W9's negative contributor is labeled `internal_consistency` (value 0.7) although the value is W7's composite `confidence_penalty` — a naming mismatch between producer field and consumer label.

## 6. Mitigation Channels Available at W9 Time (facts)

- **W12 downside case (gs_test):** consumed (engine.py:63-64, 137-163) — all_answered=True → gs_cap="none". The 3-question test is structurally always answered: `why_not_priced_in = bool(supporting_set_ids)`, `downside_case = bool(bear.invalidation_conditions)` — both trivially true. The cap never fired and could not modulate the 0.7.
- **OOS ECE (oos_ece):** not consumed (metadata `oos_ece_consumed: False`; stages.py:766-768). At the time of W9 there was no ECE to consume: forecast_validation.json (21:45:40, before the W-chain) reports `sample_size=0`, `passed=False`, "No aligned forecast-actual pairs available for validation". The producer ran but produced nothing — not a wiring gap.
- **Risk measures (VaR/cVaR/tail_index, risk_measures.json 21:45:40):** not inputs to W7 or W9; the W-chain does not read them.

## 7. Final Table

| Penalty | Weight | Evidence | Confidence loss | Evidence quality | Structural / Runtime |
|---|---|---|---|---|---|
| conflict_severity term (U1) | 0.10 | es_usd_fx bearish vs es_general bullish (real opposing market moves) | ≈ −0.014 final; +0.0875 in W9 ps | real (prices); severity formula heuristic | runtime (real contradiction) |
| cross_set_conflict flag (U2) | 0.10 | same fact as U1 | ≈ −0.014 final | real, duplicate | structural (double-count of U1) |
| regime_conflict flag (U3) | 0.10 | bearish set vs hardcoded INFLATIONARY→bullish mapping | ≈ −0.014 final | regime real; mapping synthetic | structural (hardcoded table) |
| regime_conflict bool (U6) | 0.20 | same fact as U3 | ≈ −0.028 final | real, duplicate | structural (flag+bool double-charge; same fact also in W9 regime_alignment) |
| no_dissent flag (U4) | 0.10 | both sets conflict_score 0.0 (within-set unanimity) | ≈ −0.014 final | real fact; flag mislabeled (cross-set dissent exists) | structural (heuristic definition) |
| missing_evidence flag (U5) | 0.10 | CB_GOLD/INFLATION/REAL_YIELD absent from sets | ≈ −0.014 final; +0.25 in W9 ps (remaining_unknowns 3/3) | CB_GOLD truly missing; INFLATION/REAL_YIELD available-but-filtered (NaN σ → Tier 4) | structural (missing producer) + runtime (filtering disconnected available data) |
| **Total** | **0.70** | 4 distinct facts, 6 charge units | **0.1550 (0.7 channels) of W7 total 0.2505; final 0.0325 vs no-W7 0.2830** | mixed | 3 units duplicate (U2, U4, U6), 1 unit partly avoidable (U5) |

## 8. Answers

**Is the 0.7 CounterEvidence penalty fully justified by the available runtime evidence?**

**No.** Directionally, the penalty rests on real runtime facts: a genuine directional contradiction between real market data (DXY +0.27% vs XAU +1.25%, both up — an anomalous same-direction move), a real bearish-vs-INFLATIONARY regime mismatch, real within-set unanimity, and a real absence of the CB_GOLD channel. But the exact magnitude 0.7 is not derivable from the evidence:

- 3 of 6 charge units (0.30) are duplicate charges of two facts already counted: U2 duplicates U1 (same cross-set fact), U6 duplicates U3 (same regime fact, at double rate — and the same fact is charged a third time in W9's regime_alignment).
- U4 (no_dissent) is a mislabeled heuristic: its trigger condition (within-set conflict 0.0) is true, but the run simultaneously flags cross-set dissent, which is the opposite of "no dissent"; the dissent information is already penalized via U1/U2.
- U5 (missing_evidence) is fully justified for CB_GOLD only. For INFLATION and REAL_YIELD, the observations existed in the runtime (pre_market_scan, before W7) and were excluded by the sigma-based tiering (change_sigma = NaN → Tier 4 noise) — the penalty for those channels charges the runtime for data it had but discarded.
- The regime channel's magnitude rests entirely on the hardcoded INFLATIONARY→bullish table, not on runtime evidence.
- Net: unique fact content ≈ 0.35–0.40 (cross-set ~0.10–0.20, regime ~0.10–0.20, unanimity ~0, missing ~0.05–0.10); the remaining ~0.3 is structural duplication and filtering-driven charges. The confidence outcome itself (0.0325, very_low, no-trade chain) is additionally driven by the 0.7 being consumed twice (support ×0.3 and internal ×0.4) plus W9's own regime_alignment 0.0.
