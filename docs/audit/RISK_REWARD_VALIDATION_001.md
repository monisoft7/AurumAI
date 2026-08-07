# RISK_REWARD_VALIDATION Audit 001

**Subject:** Full trace of `risk_reward_ratio = 2.9807` (base scenario `sc_230407aba79a`) in `runtime_20260806_234356`.
**Scope:** Read-only. Every number verified against `risk_reward_validation.json`, `scenario_generation.json`, `evidence_reasoning.json`, `evidence_collection.json`, `signal_assessment.json`, `pre_market_scan.json` and source (`src/risk_reward_validation/validator.py`, `src/scenario_generation/generator.py`, `src/confidence_engine/computer.py`, `src/evidence_reasoning/weighter.py`). No code modified, nothing implemented.
**Date:** 2026-08-07
**Status:** FACTS ONLY. No recommendations.

---

## 1. Trace Map (value → producer)

| # | Input | Value | Producer | Classification |
|---|---|---|---|---|
| I1 | final_confidence | 0.4601 | `scenario_generation.json` confidence_inputs — `generator._fallback_confidence` (generator.py:110-113) = thesis `avg_supporting_weight` = es_usd_fx net weight (weighter.py:50) | **Estimated/synthetic** (evidence-set weight, NOT W9 confidence 0.0325) |
| I2 | remaining_uncertainty | 0.5399 | `generator._build_scenario` (generator.py:168) = 1 − 0.4601 | **Hardcoded complement** (derived, not measured) |
| I3 | reliability_category | "low" | `ConfidenceComputer.reliability_category(0.4601)` (computer.py:119-126, band 0.30–0.49) | **Derived from synthetic conf** |
| I4 | expected_direction | "bearish" | thesis `th_dc596931c303.v2` direction (thesis_construction) | **Deterministic mapping** |
| I5 | probability | 0.5 | `BASE_PROBABILITY` constant (generator.py:38) | **Hardcoded constant** |
| I6 | time_horizon_days | 90 | thesis field (thesis_construction, hardcoded at construction) | **Hardcoded constant** |
| I7 | regime_path | ("INFLATIONARY",) | scenario `_regime_path` (generator.py:180-187) ← pre_market_scan regime | **Real regime** (estimated by InstitutionalRegimeDetector on composite_score) |

Supporting data underlying I1: es_usd_fx net 0.4601 = `0.18×0.5 + 0.5669×0.3 + 1.0×0.2` where 0.18 = composite_weight = classifier Watch confidence 0.3 × regime_weight 0.6 (real regime_confidence, stages.py:514); 0.5669 = temporal_recency `1/(1+|0.7639|)` from real change_sigma (overnight_fetcher.py:114-121, yfinance data).

## 2. Constants (validator.py)

| Constant | Value | Line |
|---|---|---|
| RELIABILITY_PENALTY | high 0.0 / moderate 0.25 / low 0.5 / very_low 0.75 | 18-23 |
| MAX_RISK_REWARD_RATIO | 10.0 | 25 |
| ACCEPTABLE_RATIO_THRESHOLD | 1.0 | 26 |
| REJECT_RATIO_THRESHOLD | 3.0 | 27 |
| ACCEPTABLE_MIN_REWARD | 0.15 | 28 |
| REJECT_MAX_REWARD | 0.05 | 29 |
| upside formula | (0.3 + 0.7×conf) × (0.4 + 0.6×alignment) | 81-83 |
| downside formula | (0.3 + 0.7×unc) × (0.4 + 0.6×(1−alignment)) | 84-86 |
| reward/risk multiplier | × scenario.probability | 90-91 |
| tail_risk | 0.5×unc + 0.5×penalty | 93 |
| liquidity_risk | min(horizon/365, 1)×0.5 + penalty×0.5 | 94-98 |
| risk_score weights | 0.5·expected_risk + 0.2·tail + 0.2·regime + 0.1·liquidity | 102-108 |
| alignment mapping | bullish 1.0 / bearish 0.0 / neutral 0.5 | 160-166 |
| regime_risk | single-path 0.3 / same-path 0.4 / different-path 0.75 | 168-178 |

## 3. Intermediate Calculations (base scenario, verified)

```
I3 → penalty = RELIABILITY_PENALTY["low"] = 0.5
I4 → alignment = _alignment("bearish") = 0.0

upside_potential  = (0.3 + 0.7×0.4601) × (0.4 + 0.6×0.0) = 0.62207 × 0.4 = 0.2488
downside_potential= (0.3 + 0.7×0.5399) × (0.4 + 0.6×1.0) = 0.67793 × 1.0 = 0.6779

expected_upside   = 0.2488
maximum_downside  = 0.6779

expected_reward   = 0.5 × 0.2488 = 0.1244
expected_risk     = 0.5 × 0.6779 = 0.3389   (float: 0.3389499…)

tail_risk         = 0.5×0.5399 + 0.5×0.5 = 0.52
liquidity_risk    = min(90/365,1)×0.5 + 0.5×0.5 = 0.12329 + 0.25 = 0.3733
regime_risk       = 0.3   (single-path INFLATIONARY)
volatility_impact = 0.5×0.5399 + 0.5×0.3 = 0.42

risk_score        = 0.5×0.3389 + 0.2×0.52 + 0.2×0.3 + 0.1×0.3733
                  = 0.16945 + 0.104 + 0.06 + 0.03733
                  = 0.3708

risk_reward_ratio = min(round(0.3708 / 0.1244, 4), 10.0)
                  = min(2.980707…, 10.0)
                  = 2.9807
```

Status classification (validator.py:181-189): ratio 2.9807 < 3.0 (not reject by ratio), reward 0.1244 ≥ 0.05 (not reject by reward), ratio > 1.0 (not acceptable) → **borderline**. Matches `validation_status='borderline'` in checkpoint.

## 4. Contribution Breakdown of the Ratio

`ratio = risk_score / expected_reward = 0.3708 / 0.1244`

Numerator (risk_score 0.3708):

| Component | Value | Share | Driver |
|---|---|---|---|
| 0.5 × expected_risk | 0.16945 | 45.7% | downside_potential 0.6779 × p 0.5 — **alignment=0 (bearish) sets downside factor to 1.0**; unc 0.5399 drives the 0.3+0.7×unc base |
| 0.2 × tail_risk | 0.104 | 28.0% | unc 0.5399 + reliability penalty 0.5 |
| 0.2 × regime_risk | 0.06 | 16.2% | hardcoded single-path 0.3 |
| 0.1 × liquidity_risk | 0.03733 | 10.1% | horizon 90d + penalty 0.5 |

Denominator (expected_reward 0.1244): p 0.5 (fixed) × upside_potential 0.2488 — **alignment=0 (bearish) floors upside factor at 0.4**; conf 0.4601 (synthetic fallback) governs 0.3+0.7×conf.

## 5. Why Did the Ratio Become 2.9807?

- The bearish direction (alignment 0.0) is the single dominant driver: it **caps** upside_potential at its 0.4 floor (reward 0.2488) while **liberating** downside_potential to its 1.0 full weight (risk 0.6779) — an asymmetric 1.25× amplification per the `(0.4+0.6×a)` vs `(0.4+0.6×(1−a))` pair.
- The numerator also carries a large fixed load: tail 0.104 (28%) + regime 0.06 (16%) + liquidity 0.037 (10%) — 54% of risk_score is **independent of the scenario's reward**.
- The denominator (0.1244) is 50% smaller than the numerator's expected_risk term (0.16945) alone, because p=0.5 applies equally to both but downside base (0.6779) is 2.7× the upside base (0.2488).
- Net: ratio = 2.9807, inside the "reject" neighbor band (≥3.0) but classified borderline.

## 6. Which Components Are Based on Real Runtime Data?

| Component | Real? | Basis |
|---|---|---|
| regime (INFLATIONARY), regime_confidence 0.6 | Real (estimated) | InstitutionalRegimeDetector on composite_score; consumed as regime_weight 0.6 in I1 chain |
| change_sigma 0.7639 (DXY) | Real | yfinance close series, overnight_fetcher.py:114 |
| temporal_recency 0.5669 | Real (derived) | 1/(1+|sigma|) of real sigma |
| conf 0.4601 (I1) | **Not real** | synthetic fallback: classifier Watch constant (0.3) × regime_weight, boosted by recency/provenance factors (0.5/0.3/0.2 constants) |
| unc 0.5399 (I2) | **Not real** | 1 − synthetic conf |
| reliability penalty 0.5 (I3) | **Not real** | band mapping of synthetic conf |
| probability 0.5 (I5) | **Not real** | hardcoded BASE_PROBABILITY |
| alignment 0.0 (I4) | **Not real** | hardcoded direction mapping |
| time_horizon 90 (I6) | **Not real** | hardcoded thesis constant |
| regime_risk 0.3 | **Not real** | hardcoded single-path constant |
| tail/volatility/liquidity | Mixed | unc/penalty-derived + horizon constant |

**Result: of the 4 variables that fully determine the ratio (conf, unc, alignment, probability), all 4 are non-real (synthetic/hardcoded). The only real-data influence is indirect — via the regime label and DXY's real σ inside recency.**

## 7. Fallbacks Exercised in This Run

1. **Confidence fallback**: scenario confidence_inputs use `thesis_fallback` (generator.py:101, 110-113) — W9's institutional confidence 0.0325 is **bypassed**; the scenario used 0.4601 instead.
2. **Reliability fallback**: `reliability_category` derived from fallback conf via computer.py bands; `RELIABILITY_PENALTY.get(reliability, 0.75)` default for unknown labels (validator.py:78).
3. **Ratio cap**: `min(ratio, 10.0)` (validator.py:110-115); bear scenario exercised the reject path via ratio 5.0075.
4. **Regime fallback**: `_regime_risk` returns 1.0 if path empty or regime not in INSTITUTIONAL_REGIMES (validator.py:170-173) — not exercised.
5. **Single-path regime_risk 0.3** — the base scenario's path length 1 constant (validator.py:174-175).

## 8. Assumptions (code-embedded, not data-verified)

- Downside factor = 1.0 for bearish, upside factor = 1.0 for bullish, neutral = 0.5 (validator.py:160-166).
- 90-day horizon normalized over 365 days for liquidity.
- Base probability fixed at 0.5 regardless of evidence (generator.py:38).
- uncertainty = 1 − conf (no independent measure).
- Reliability bands: <0.30 very_low, 0.30–0.49 low, 0.50–0.69 moderate, ≥0.70 high (computer.py:119-126).
- The fallback conf (evidence weight) is used in place of institutional confidence (W12-before-W9 ordering, generator.py:47-53).

## 9. Answers to the Objective Questions

**• Why did the ratio become 2.9807?**
The ratio is `0.3708 / 0.1244`. The numerator is dominated by the downside term (0.16945, 45.7%) — a 0.6779 downside base inflated to full weight by bearish alignment 0.0 — plus fixed tail/regime/liquidity load (54%). The denominator is the 0.4-floored upside base (0.2488) × the fixed 0.5 probability, i.e., a bearish-direction scenario whose asymmetry (downside ×1.0 vs upside ×0.4) is compounded by synthetic uncertainty 0.5399.

**• Which components contributed most?**
1) alignment=0 (bearish) — drives both the upside floor (0.4) and the downside full-weight (1.0); 2) unc 0.5399 — drives expected_risk (0.16945) and tail (0.104); 3) reliability penalty 0.5 — tail +0.10, liquidity +0.25; 4) probability 0.5 — halves the denominator; 5) regime_risk 0.3 — fixed +0.06. Ranked: alignment ≈ uncertainty > reliability penalty > probability > regime constant.

**• Is every component based on real runtime data?**
No. Four variables fully determine the ratio — conf (0.4601), unc (0.5399), alignment (0.0), probability (0.5) — and **all four are synthetic or hardcoded**. Real runtime data enters only indirectly (regime label; DXY real σ in temporal_recency). The W9 institutional confidence (0.0325) is not consumed at all (fallback exercised).

**• Could the same runtime ever produce a ratio below 2.0 without changing upstream data?**
No. With inputs frozen (conf 0.4601, unc 0.5399, penalty 0.5, alignment 0.0, p 0.5, horizon 90, path INFLATIONARY), the validator is a pure deterministic function → ratio = 2.9807 on every re-run, with zero variance (no randomness, no data re-read inside the validator). The only degrees of freedom (conf/probability) are upstream outputs; e.g., ratio < 2.0 would require conf near 1.0 (algebraically, conf → 1.0, unc → 0, reliability high → ratio ≈ 0.74) — unreachable with this run's evidence chain (max achievable es_usd_fx net with all-ideal upstream ≈ 0.975 → ratio ≈ 2.6). Additionally, the ratio cap (10.0) and reject band (≥3.0) are structural, not runtime-dependent.
