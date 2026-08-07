# DECISION_SENSITIVITY_ANALYSIS Audit 001

**Subject:** End-to-end sensitivity analysis of the institutional decision chain for `runtime_20260806_234356`.
**Scope:** Read-only. Every number below is computed from checkpoint artifacts and verified against source formulas. No code modified, nothing implemented.
**Date:** 2026-08-07
**Status:** FACTS ONLY. No recommendations.

---

## 0. Verified Formula Anchors

| Formula | Source | Observed result |
|---|---|---|
| `penalty = conflict_severity×0.4 + len(bias_flags)×0.1 + 0.2×regime_conflict` | analyzer.py:47-56 | `0.25×0.4 + 4×0.1 + 0.2 = 0.7` |
| `conflict_severity = cross_ratio×0.5 + avg_conflict×0.5` | analyzer.py:30-44 | `0.5×0.5 + 0.0×0.5 = 0.25` |
| `net_weight = raw×0.5 + avg_recency×0.3 + prov_ratio×0.2` | weighter.py:50 | es_usd_fx `0.18×0.5+0.5669×0.3+0.2 = 0.4601` |
| `support = avg_supporting_weight × (1 − penalty)` | builder | `0.4601×0.3 = 0.138` |
| `final = positive_score × support × (1 − penalty_score)` | computer.py:56-74 | `0.615×0.138×0.3825 = 0.0325` |
| `positive_score = 0.25·ev + 0.25·cons + 0.15·regime + 0.15·div + 0.10·kr + 0.10·rec` | computer.py:14-21 | `0.1150+0.25+0+0.05+0.1+0.1 = 0.615` |
| `penalty_score = 0.35·conflict + 0.25·missing + 0.40·internal` | computer.py:23-27 | `0.0875+0.25+0.28 = 0.6175` |
| `rr_score = mean(1 − min(ratio/10, 1))` | engine.py:193-201 | `(0.7019+0.7167+0.4992)/3 = 0.6393` |
| `composite = 0.30·conf + 0.20·rr + 0.15·ev + 0.15·(1−pen) + 0.10·p + 0.10·align` | engine.py:203-211 | `0.0097+0.1279+0.069+0.045+0.05+0.0 = 0.3016` |

Baseline: final institutional_confidence **0.0325**, composite **0.3016**, decision **NO_TRADE**.

## 1. Per-Stage Sensitivity Table

### 1.1 SignalAssessment
- **Input:** 13 raw observations (9 overnight, 3 anomalies, 1 positioning); regime INFLATIONARY.
- **Output:** 4 Watch @ confidence 0.3 (DXY + 3 anomalies), 5 Noise, 4 Ignore.
- **Confidence delta introduced:** +0.0325 vs. null (all-Neutral ⇒ 0 evidence ⇒ confidence 0.0).
- **Max improvement (ideal):** all evidence items Signal @ max classifier conf 0.95 → composite_weight 0.57 → es_usd_fx net 0.6551 → support 0.1965 → positive_score 0.6638 → final `0.6638×0.1965×0.3825 = 0.0499` (+0.0174). Composite 0.3361 (+0.0345).
- **Max degradation:** all evidence-class observations Noise ⇒ 0 evidence ⇒ final 0.0 (−0.0325).
- **Dominant bottleneck?** No (3rd of 4 positive-delta stages).

### 1.2 EvidenceCollection
- **Input:** 4 Watch observations (base_confidence 0.3).
- **Output:** 4 Evidence items, composite_weight = 0.3 × 0.6 = 0.18 (regime_weight 0.6 from regime_diagnosis confidence, stages.py:514).
- **Confidence delta introduced:** +0.0073 vs. weight-0 null (`0.5925×0.1110×0.3825 = 0.0252`).
- **Max improvement (ideal):** regime_weight 1.0 → composite 0.3 → net 0.5201 → support 0.156 → positive 0.63 → final `0.63×0.156×0.3825 = 0.0376` (+0.0051). Composite 0.3122 (+0.0106).
- **Max degradation:** regime_weight 0.0 → final 0.0252 (−0.0073).
- **Dominant bottleneck?** No (smallest positive lever).

### 1.3 EvidenceReasoning
- **Input:** 4 Evidence items (2 sets after 1 duplicate removed: es_usd_fx 1 item, es_general 2 items), all composite 0.18.
- **Output:** net weights 0.4601 (es_usd_fx) / 0.4323 (es_general), consensus 1.0, conflict 0.0.
- **Confidence delta introduced:** +0.0325 vs. net-0 null (support 0 ⇒ final 0.0).
- **Max improvement (ideal):** temporal_recency → 1.0 (max): net `0.09+0.3+0.2 = 0.59` → support 0.177 → positive 0.6475 → final `0.6475×0.177×0.3825 = 0.0438` (+0.0113). Composite 0.3245 (+0.0229).
- **Max degradation:** recency → 0.1 (floor): net `0.09+0.03+0.2 = 0.32` → support 0.096 → positive 0.58 → final `0.58×0.096×0.3825 = 0.0213` (−0.0112).
- **Dominant bottleneck?** No. (Consensus already 1.0 = max; dedupe had zero weight impact — all items 0.18.)

### 1.4 CounterEvidence
- **Input:** 2 evidence sets (1 supporting bearish, 1 contradicting bullish); regime INFLATIONARY (expected bias bullish, detector.py:19-26).
- **Output:** conflict_severity 0.25, bias_flags [no_dissent, regime_conflict, missing_evidence, cross_set_conflict], confidence_penalty **0.7**, regime_conflict=True.
- **Confidence delta introduced:** **−0.1797** vs. penalty-0 null (`0.615×0.4601×0.75 = 0.2122`). This is the only stage whose output removes confidence relative to its null.
- **Max improvement (ideal):** penalty → 0.0 → support 0.4601, penalty_score 0.25 (missing channels unchanged) → final **0.2122** (+0.1797). Composite 0.4605 (+0.1589). Note: this requires conflict_severity 0, zero bias flags, no regime conflict — i.e., upstream regime/direction alignment.
- **Max degradation:** penalty → 1.0 → support 0.0 → final 0.0 (−0.0325).
- **Dominant bottleneck?** **YES.** Largest confidence lever by 10× (0.1797 vs next 0.0174).

### 1.5 ThesisConstruction
- **Input:** sets 0.4601/0.4323, penalty 0.7.
- **Output:** 3 theses; bearish `th_dc596931c303` support 0.138 (0.4601×0.3), bullish 0.1297, neutral 0.0.
- **Confidence delta introduced:** +0.0325 vs. no-thesis null (0.0).
- **Max improvement (ideal):** support already equals the theoretical max for the given inputs (0.4601×0.3 = 0.138); source_diversity 1/3 is bounded by the number of upstream sets. Improvement 0.0000. Composite unchanged 0.3016.
- **Max degradation:** neutral thesis (support 0.0) → final 0.0 (−0.0325).
- **Dominant bottleneck?** No (zero gap to ideal given upstream).

### 1.6 ThesisUpdate
- **Input:** thesis v1 support 0.138, trigger periodic.
- **Output:** v2 support 0.138, action no_change, confidence_delta 0.0.
- **Confidence delta introduced:** 0.0 (output equals input).
- **Max improvement:** 0.0 (no change performed). **Max degradation:** 0.0.
- **Dominant bottleneck?** No — neutral stage.

### 1.7 ConfidenceEngine
- **Input:** thesis support 0.138, confidence_inputs (avg_supporting_weight 0.4601, consensus 1.0, conflict_severity 0.25, penalty 0.7).
- **Output:** final_confidence **0.0325**, reliability very_low, remaining_uncertainty 0.9675.
- **Confidence delta introduced:** +0.0325 vs. zero-input null (deterministic composition).
- **Max improvement:** 0.0 — deterministic given inputs; all input values already consumed at their observed levels. **Max degradation:** 0.0.
- **Dominant bottleneck?** No — pass-through; it can only mirror upstream losses.

### 1.8 ScenarioGeneration
- **Input:** thesis support/confidence_inputs (fallback proxy = avg_supporting_weight 0.4601, generator.py:110-113).
- **Output:** base p=0.5 (fixed, generator.py:38), bull 0.179, bear 0.321; confidence_inputs carry 0.4601 (NOT the W9 0.0325).
- **Confidence delta introduced:** 0.0 on W9 confidence (scenarios do not feed it). Composite contribution +0.05 (max_probability 0.5 × 0.1).
- **Max improvement:** max_probability is capped at base 0.5 (bull max = 0.5×(0.45−0.2×conf) < 0.5) → improvement 0.0 on composite driver. **Max degradation:** probability → 0 → composite −0.05 (0.2516).
- **Dominant bottleneck?** No.

### 1.9 RiskRewardValidation
- **Input:** 3 scenarios (conf 0.4601 fallback, unc 0.5399, reliability low → penalty 0.5).
- **Output:** base borderline ratio 2.9807, bull borderline 2.833, bear reject 5.0075; summary acceptable 0 / borderline 2 / reject 1.
- **Confidence delta introduced:** 0.0 on W9 confidence. Composite contribution +0.1279 (rr_score 0.6393 × 0.2).
- **Max improvement (ideal):** all ratios → 0 ⇒ rr_score 1.0 → composite +0.0721 (0.3737). Confidence unchanged 0.0325.
- **Max degradation:** rr_score 0.0 → composite 0.1737 (−0.1279).
- **Dominant bottleneck?** No for confidence; second-largest composite lever (0.0721).

### 1.10 BiasPrevention
- **Input:** updated thesis, CounterEvidenceAssessment, InstitutionalConfidence.
- **Output:** 4 findings (narrative_bias, single_source_bias, regime_blindness critical, false_precision), overall critical, human_review_flag True, total_confidence_impact 0.8.
- **Confidence delta introduced:** **0.0** — findings are appended to the decision explanation only (stages.py:795 `apply_bias_review`); total_confidence_impact is informational, not applied to institutional_confidence or composite.
- **Max improvement:** 0.0. **Max degradation:** 0.0 (numeric). Human-review gate: flag True (no numeric effect on the recorded decision).
- **Dominant bottleneck?** No (numeric).

## 2. Stage Ranking — Contribution to Final Confidence Loss (vs. stage-ideal)

| Rank | Stage | Confidence loss vs ideal | Composite loss vs ideal |
|---|---|---|---|
| 1 | CounterEvidence | **0.1797** | **0.1589** |
| 2 | SignalAssessment | 0.0174 | 0.0345 |
| 3 | EvidenceReasoning | 0.0113 | 0.0229 |
| 4 | EvidenceCollection | 0.0051 | 0.0106 |
| 5 | ConfidenceEngine | 0.0000 (deterministic) | 0.0000 |
| 6 | ScenarioGeneration | 0.0000 | 0.0000 |
| 7 | RiskRewardValidation | 0.0000 | 0.0721 |
| 8 | ThesisConstruction | 0.0000 (max given inputs) | 0.0000 |
| 9 | ThesisUpdate | 0.0000 (no_change) | 0.0000 |
| 10 | BiasPrevention | 0.0000 (informational) | 0.0000 |

## 3. Top 10 Bottlenecks — Ordered by Actual Quantitative Impact on the Final Recommendation

Decision gates (engine.py:257-268): NO_TRADE fires when confidence < 0.5 **or** ratio > 2.0. Both gates fail independently: confidence 0.0325 vs 0.5 (gap 0.4675); ratio 2.9807 vs 2.0.

| # | Bottleneck | Mechanism | Quantified impact on final recommendation |
|---|---|---|---|
| 1 | CounterEvidence 0.7 penalty | Penalty formula `0.25×0.4 + 4×0.1 + 0.2`: severity 0.25 + 4 bias flags + regime conflict. Cuts support 0.4601→0.138 and internal-consistency penalty 0.28. | Confidence 0.0325 vs 0.2122 potential (−0.1797, 85% of all recoverable confidence); composite −0.1589 |
| 2 | RiskRewardValidation gate | Selected base ratio 2.9807 > NO_TRADE_RR_RATIO 2.0; bear scenario reject (5.0075). rr_score 0.6393 vs 1.0. | Independent hard gate: SELL impossible at ratio > 2.0 even with confidence ≥ 0.5; composite −0.0721 |
| 3 | SignalAssessment Watch ceiling | All 4 evidence items at classifier Watch conf 0.3 (cap 0.4); max possible conf per item 0.95. | Composite weight 0.18 vs ≥0.57 potential; confidence −0.0174; composite −0.0345 |
| 4 | EvidenceReasoning recency weighting | net = raw×0.5 + recency×0.3 + prov×0.2; observed avg recency 0.5669/0.4743 vs max 1.0. | Confidence −0.0113; composite −0.0229 |
| 5 | EvidenceCollection regime_weight 0.6 | composite_weight = 0.3 × 0.6 = 0.18 (regime_diagnosis confidence 0.6). | Confidence −0.0051; composite −0.0106 |
| 6 | ScenarioGeneration fallback confidence | Scenarios carry 0.4601 (thesis_fallback) not W9 0.0325; base p fixed 0.5. | No confidence effect; composite driver maxed (0.05) — neutral |
| 7 | ConfidenceEngine reliability | very_low (0.0325) propagates via support_factor 0.138 and penalty_score 0.6175. | Pass-through of items 1,3,4,5 — no independent loss (0.0000) |
| 8 | ThesisConstruction single supporting set | source_diversity 1/3 (min(1 set / 3)); bounded by upstream set count. | Zero gap vs ideal given inputs (0.0000) |
| 9 | ThesisUpdate no_change action | action=no_change, confidence_delta 0.0 despite regime_conflict=True. | 0.0000 numeric (feeds bias finding #10 only) |
| 10 | BiasPrevention human-review flag | overall_severity critical, human_review_flag True, impact 0.8 informational. | 0.0000 numeric on recorded decision (flag only) |

**Decisive facts:**
- 84% of the recoverable confidence gap (0.1797 of 0.2135 summed delta) is attributable to a single stage: CounterEvidence.
- NO_TRADE is over-determined: even with the #1 bottleneck at its ideal (penalty 0), confidence would be 0.2122 — still below the 0.5 trade gate; the risk/reward gate (ratio ≤ 2.0) additionally fails independently at 2.9807.
- Single-stage ideal deltas are NOT additive (the chain is multiplicative). Combined cumulative scenario — SignalAssessment ideal (item conf 0.95) × EvidenceCollection ideal (regime_weight 1.0 → composite_weight 0.95) × EvidenceReasoning ideal (recency 1.0 → net `0.95×0.5+0.3+0.2 = 0.975`) × CounterEvidence ideal (penalty 0 → support 0.975, penalty_score 0.25) — computes to `0.7438 × 0.975 × 0.75 = 0.5439`, which **passes the 0.5 confidence gate** (regime_alignment stays 0.0).
- Even in the full cumulative ideal, the final decision remains **NO_TRADE**: the risk/reward gate is independent — selected base ratio 2.9807 > 2.0 (engine.py:260-261) is untouched by any upstream stage. No scenario reachable in this run's structure (single thesis, fixed probabilities, fixed ratios) can clear both gates.
