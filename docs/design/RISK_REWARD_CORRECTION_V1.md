# RISK_REWARD_CORRECTION_V1

**Document type:** Design (Sprint 2 — no implementation)
**Status:** DESIGN ONLY
**Date:** 2026-08-07
**Source of truth (exclusive):**

1. `docs/audit/RISK_REWARD_VALIDATION_001.md` — cited as **[RV]**
2. `docs/audit/DECISION_TRACE_001.md` — cited as **[DT]**
3. `docs/audit/DECISION_SENSITIVITY_ANALYSIS_001.md` — cited as **[SA]**

> Only these three audit documents are used to derive requirements. Source-file names/line numbers quoted inside them (e.g., `generator.py:110-113`, `weighter.py:50`) are cited **as the audits recorded them**; no architectural decision in this document is derived from source code.

---

## 1. Scope

- Defines the **minimum correction** that eliminates the **fallback-derived** input flowing into RiskRewardValidation that is **not institutionally justified**, per the audit evidence.
- Covers exactly the inputs consumed by RiskRewardValidation as enumerated in [RV] §1 (trace map I1–I7).
- **In scope:** the selection of the value supplied to RiskReward as its `final_confidence` input, and the values that derive from it.
- **Explicitly non-goals** (not changed, not part of the correction):
  - Redesign of the RiskRewardValidator formulas or constants ([RV] §2).
  - Change of `expected_direction`/`alignment` mapping, `BASE_PROBABILITY`, or `time_horizon_days` — each is a documented constant, not a fallback ([RV] §1, §6).
  - Re-ordering stages; in particular **consuming the W9 institutional confidence (`0.0325`) directly into RiskReward is rejected** because the audited ordering is W12-before-W9 ([RV] §8; [DT] §6.2) — see §2 item 5.
  - Changes to the ConfidenceEngine, DecisionEngine, thresholds, contracts, or stage graph.
- Deliverable is this document only. **No code is implemented.**

---

## 2. Problem Statement (audit evidence only)

1. **The confidence input RiskReward consumes is a fallback, not an institutional value.**
   The scenarios carry `final_confidence = 0.4601` sourced as `thesis_fallback`, which equals the evidence-set net weight `avg_supporting_weight` ([RV] §1 I1, §7-1; [DT] §4.3, §6.2). The institution's own confidence for the same run is `0.0325` ([RV] §1 I1; [DT] §2; [SA] §0). The W9 confidence is **bypassed** by the fallback ([RV] §7-1).

2. **The four variables that fully determine the risk/reward ratio are all non-real.**
   "of the 4 variables that fully determine the ratio (conf, unc, alignment, probability), all 4 are non-real (synthetic/hardcoded)" ([RV] §6): `conf 0.4601` (synthetic fallback), `unc 0.5399` (= 1 − conf), `alignment 0.0` (hardcoded direction mapping), `probability 0.5` (hardcoded constant) ([RV] §6).

3. **The only fallback-injected defect among the ratio-determining quartet is the confidence value.**
   `alignment` and `probability` are documented mappings/constants, not fallbacks ([RV] §2, §6). The single input whose *value* depends on an exercised fallback is `final_confidence` ([RV] §7-1: "Confidence fallback … W9's institutional confidence 0.0325 is bypassed; the scenario used 0.4601 instead").

4. **A penalty-adjusted institutional value already exists upstream, before RiskReward runs.**
   ThesisConstruction produces `support = avg_supporting_weight × (1 − penalty) = 0.4601 × 0.3 = 0.138` ([SA] §0 anchor row; [SA] §1.5). This value is already in the same input bundle the scenario generator receives (`thesis support/confidence_inputs`, [SA] §1.7, §1.8).

5. **The audited ordering forbids feeding W9's `0.0325` into RiskReward without a reorder.**
   "The fallback conf (evidence weight) is used in place of institutional confidence (W12-before-W9 ordering)" ([RV] §8). Reordering to make W9's output available at RiskReward time is a non-goal (§1). Therefore the correction must use a penalty-informed value that is **already available before RiskReward runs** and **already in the scenario producer's input set** — the audited thesis `support` above.

**Consequence of the defect:** RiskReward evaluates against a confidence that is systematically more optimistic than the institutional estimate (`0.4601` vs penalty-adjusted `0.138`). Per the audited formulas ([RV] §2), a higher conf raises the reward term `(0.3 + 0.7×conf)` and lowers the risk/complement terms built on `unc = 1 − conf` — i.e. the risk/reward ratio is understated relative to the institutional posture.

---

## 3. Inventory of RiskReward Inputs

Classification vocabulary (consistent with [RV] §1, §6): **Real** / **Derived** / **Fallback** / **Synthetic**.

| # | Input (consumed by RiskReward) | Producer | Current source | Classification | Audit evidence |
|---|---|---|---|---|---|
| I1 | `final_confidence` | scenario generator (fallback path `_fallback_confidence`) | thesis `avg_supporting_weight` = evidence-set net weight `0.4601` (bypasses institutional `0.0325`) | **Fallback** | [RV] §1 I1, §6, §7-1; [DT] §4.3, §6.2; [SA] §1.8 "fallback proxy = avg_supporting_weight 0.4601" |
| I2 | `remaining_uncertainty` | scenario generator | `1 − final_confidence` = `0.5399` (complement, no independent measure) | **Derived** | [RV] §1 I2 "hardcoded complement", §8 "uncertainty = 1 − conf"; [SA] §1.9 carries `unc = 0.5399` |
| I3 | `reliability_category` → penalty | ConfidenceComputer `reliability_category` band mapping | `0.4601` → band 0.30–0.49 → `"low"` → penalty `0.5` | **Derived** | [RV] §1 I3, §3, §8 (bands); §6 "band mapping of synthetic conf"; penalty set [RV] §2 |
| I4 | `expected_direction` → `alignment` | thesis construction (direction `"bearish"`) | mapping bearish → `0.0` | **Synthetic** (deterministic mapping) | [RV] §1 I4, §2 alignment mapping, §6; [DT] §2 selected thesis bearish |
| I5 | `probability` | scenario generator (`BASE_PROBABILITY`) | `0.5` base (fixed); bull `0.179` / bear `0.321` allocation | **Synthetic** (hardcoded constant) | [RV] §1 I5, §3, §8 "Base probability fixed at 0.5"; [SA] §1.8 |
| I6 | `time_horizon_days` | thesis construction | `90` (fixed at construction) | **Synthetic** (hardcoded constant) | [RV] §1 I6, §6 |
| I7 | `regime_path` | scenario generator from pre-market regime | `("INFLATIONARY",)` | **Real** (estimated by InstitutionalRegimeDetector) | [RV] §1 I7, §6 "Real (estimated)" |

Context inputs (not producer inputs to RiskReward; listed for completeness — **unchanged**):

| Constant | Value | Audit evidence |
|---|---|---|
| Validator formulas & constants | upside/downside pair, tail, liquidity, alignment map, regime_risk, ratio/reward thresholds | [RV] §2; [SA] §1.9 |
| DecisionEngine gates | NO_TRADE when `confidence < 0.5` **or** `ratio > 2.0` | [SA] §3 "NO_TRADE fires when confidence < 0.5 or ratio > 2.0"; [DT] §2 "no thesis clears institutional confidence and risk/reward thresholds" |
| Thesis `support` (institutional, penalty-adjusted; available but not currently sourced into I1) | `0.138 = avg_supporting_weight × (1 − penalty)` | [SA] §0; [SA] §1.5 |

**Audit confirmation of the gap:** the only ratio-driving input carrying a *fallback* is I1; I4/I5/I6 are documented constants, I2/I3 are straight derivations of I1, I7 is real ([RV] §6, §7).

---

## 4. Correction Matrix

Exactly one action per input.

| # | Input | **Action** | Specification | Justification (audit source) |
|---|---|---|---|---|
| I1 | `final_confidence` | **Replace** | Source becomes the institutional penalty-adjusted value `thesis.support = avg_supporting_weight × (1 − penalty)` (audited `0.138`) instead of the raw `avg_supporting_weight` (`0.4601`) used today. Selection remains **conditional**: the penalty-adjusted value is used whenever it is present in the scenario input bundle; the raw fallback is preserved only if that value is absent (not the case in the audited run, where `support = 0.138` is always present). | Fallback bypass documented: [RV] §1 I1, §7-1. Corrected value produced upstream and already in scenario inputs: [SA] §0, §1.5, §1.7, §1.8. Reordering rejected: §1; [RV] §1, §8. |
| I2 | `remaining_uncertainty` | **Remain** | Stays the mathematical complement `1 − I1`; recomputes from the corrected I1 with the same formula. | [RV] §1 I2, §8 "uncertainty = 1 − conf". |
| I3 | `reliability_category` | **Remain** | Stays the band mapping of the confidence value with unchanged bands and penalties; recomputes from the corrected I1. | [RV] §1 I3, §8 (band constants), §2 (penalty set). |
| I4 | `expected_direction` → `alignment` | **Remain** | Deterministic thesis-direction mapping; not a fallback. | [RV] §1 I4, §2 alignment mapping. |
| I5 | `probability` | **Remain** | Documented hardcoded constant; not fallback-derived. | [RV] §1 I5, §8; [SA] §1.8. |
| I6 | `time_horizon_days` | **Remain** | Documented thesis constant. | [RV] §1 I6, §6. |
| I7 | `regime_path` | **Remain** | Real estimated regime; no fallback in the audited run. | [RV] §1 I7, §6; [DT] §4.3. |

**Rationale (why only I1 is touched):** of the ratio-determining quartet (conf, unc, alignment, probability), only I1 is fallback-injected ([RV] §7); I2 and I3 are derived directly from I1 and correct themselves once I1's source is replaced ([RV] §2, §3, §8); I4–I6 are documented constants, and I7 is real ([RV] §6).

---

## 5. Expected Downstream Effect

Only statements derivable from the audits appear here; **no speculative corrected ratio is asserted**, since the audits publish no recomputed run.

1. **Value replaced.** In the audited run, the confidence input moves from `0.4601` (fallback) to the audited institutional support `0.138` ([SA] §0: `0.4601 × 0.3 = 0.138`).
2. **Derived consequences (formulas and constants all audit-sourced).**
   - `remaining_uncertainty = 1 − 0.138 = 0.862` (formula: complement `1 − conf`, [RV] §1 I2).
   - `reliability_category`: `0.138 < 0.30`, which maps to **`very_low`** per the audited bands ([RV] §8 "<0.30 very_low"), therefore the reliability penalty term rises from `0.5` (low) to `0.75` (very_low) ([RV] §2 penalty set).
3. **Directional (monotonic) effect on the score terms.** With alignment `0.0` and base probability `0.5` fixed ([RV] §2), lowering conf:
   - lowers the reward base `(0.3 + 0.7×conf)`;
   - raises the complement `unc`, hence the risk base `(0.3 + 0.7×unc)`;
   - raises `tail_risk` and `liquidity_risk` (both carry `+0.5×unc` and `+0.5×penalty` terms, [RV] §2).
   Since `risk_score` is a fixed weighted sum of these positive terms ([RV] §2 risk_score weights), the risk/reward ratio for the same scenario **moves strictly higher** than the audited `2.9807`. No exact corrected ratio is asserted (audits publish none).
4. **Decision outcome is provably invariant (over-determined).**
   NO_TRADE fires when `confidence < 0.5` **or** `ratio > 2.0` ([SA] §3). The ratio gate already fails independently at `2.9807` ([SA] §3; [DT] §4.4, §2), and "Even in the full cumulative ideal, the final decision remains NO_TRADE: the risk/reward gate is independent" ([SA] §3). A higher corrected ratio cannot clear that gate; the decision remains **NO_TRADE** ([DT] §2).
5. **Nothing outside RiskReward reads this value.** Scenarios do not feed the institutional (W9) confidence ([SA] §1.8 "0.0 on W9 confidence (scenarios do not feed it)"), so W9 final `0.0325` and the composite `0.3016` are unaffected by this correction ([DT] §2, §4).

**Net effect:** RiskReward no longer under-states institutional risk via a fallback-inflated confidence; the shift is more conservative (higher ratio, unchanged gate), and the audited decision outcome (NO_TRADE) does not change.

---

## 6. Architectural Preservation Proof

| Requirement | Proof (traceable to audits) |
|---|---|
| **Architecture / layers preserved** | No stage added or removed; the corrected value is produced by an existing upstream producer (Thesis Construction) and is already in the scenario generator's input bundle ([SA] §0, §1.5, §1.7, §1.8). Stage structure unchanged: 26/26 `ok` ([DT] §1). |
| **Contracts preserved** | RiskReward input keys (`final_confidence`, `remaining_uncertainty`, `reliability_category`, `expected_direction`, `probability`, `time_horizon_days`, `regime_path`) stay identical with the same meaning; only the *value source* of one key changes ([RV] §1). The `confidence_source` metadata label changes value with the selection but the contract remains ([DT] §4.3, §6.2). |
| **Pipeline ordering preserved** | Stages run in the recorded order ([DT] §1, §3); the design adds no read of any later stage and does not attempt to use W9's `0.0325` (forbidden by the W12-before-W9 ordering, [RV] §1, §8). The corrected source `support` is produced by Thesis Construction, which precedes Scenario Generation in the audited order ([DT] §1, stage 7 vs stage 11). |
| **DecisionEngine preserved** | Composite equation ([SA] §0 `composite = 0.30·conf + 0.20·rr + …`) and gates (`confidence < 0.5` **or** `ratio > 2.0`, [SA] §3) are untouched. The only effect arrives through the numeric value of one upstream scenario input — exactly the intended "improved upstream inputs" behavior ([SA] §1.9). |
| **ConfidenceEngine preserved** | ConfidenceEngine formula (`final = positive_score × support × (1 − penalty_score)`) and its inputs are unchanged ([SA] §0). The correction does not alter what the ConfidenceEngine receives; it mirrors upstream inputs deterministically ([SA] §1.7). |
| **RiskRewardValidator & thresholds preserved** | Validator formulas and constants (upside/downside pair, tail, liquidity, alignment map, regime_risk, `MAX_RISK_REWARD_RATIO 10.0`, thresholds `1.0/3.0`, min/max reward `0.15/0.05`, reliability penalties) remain as recorded ([RV] §2, §3). |
| **No new coupling** | The corrected source (`support`) is already present in the scenario generator's input bundle (`thesis support/confidence_inputs`, [SA] §1.7, §1.8). No new cross-stage read, no new dependency, no new import or artifact. |

---

## 7. Traceability Index (statement → audit)

| Key statement | Source |
|---|---|
| conf fallback `0.4601` vs institutional `0.0325` | [RV] §1‑§7; [DT] §2, §6.2; [SA] §1.8 |
| four ratio-determining drivers all non-real | [RV] §6 |
| only conf is a fallback; I2/I3 derived; I4–I6 constants; I7 real | [RV] §1, §6, §7 |
| institutional support value `0.138` exists upstream | [SA] §0, §1.5, §1.7 |
| substitution needs no W9 and no reorder | [RV] §1, §8; [SA] §1.8 |
| outcome over-determined, NO_TRADE final | [SA] §3; [DT] §2, §4 |
| reliability bands and penalty constants | [RV] §2, §8 |
| decision gates `0.5` / `2.0` | [SA] §3; [DT] §4.1 |
| composite / formula untouched | [SA] §0; [DT] §1 |
| stage order / count unchanged | [DT] §1, §3 |

*End of design. Design only — nothing implemented.*