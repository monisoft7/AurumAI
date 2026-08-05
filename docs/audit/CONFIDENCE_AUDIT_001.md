# CONFIDENCE_AUDIT_001 — Institutional Confidence 0.315

Read-only audit. No code or test modified. Facts only; no fixes or recommendations.

## 1. Scope and method

- Target: latest successful runtime `runtime_20260804_230820`
  (`outputs/2026-08-04/runtime_20260804_230820`, exit code 0, 25/25 stages ok).
- Traced value: `institutional_confidence = 0.315`, from input origin through
  `ConfidenceComputer` / `ConfidenceEngine` to consumption by `DecisionEngine`.
- Read sources: the six runtime artifacts (`finalize.json`, `summary.json`,
  `stages.json`, `config.json`, `outcome.json`, `run.log`,
  `artifacts/knowledge.json`, `artifacts/lessons.csv`) and the decision-path
  source files. Decision-path code unmodified vs git commit `78c9ad4` (the
  commit recorded in `runtime/run_registry.jsonl` for this run).

## 2. Terminal value and DecisionEngine consumption

Observed in `finalize.json`:
- `decision.institutional_confidence = 0.315` (`finalize.json:65`)
- driver `institutional_confidence`: value `0.315`, weight `0.3`, score `0.0945`
  (`finalize.json:26-31`)
- `decision_drivers` composite `0.4937` includes `0.30 * 0.315 = 0.0945`
- `selected_thesis = th_5a4e06fcd3a2.v2` (bullish), 1 thesis evaluated
  (`finalize.json:63,80,86`)
- `decision = NO_TRADE` because `0.315 < NO_TRADE_CONFIDENCE` (`engine.py:258-259`)

Path of 0.315 into DecisionEngine:
1. `_confidence_engine` stage constructs `InstitutionalConfidence` via
   `ConfidenceEngine.evaluate` (`stages.py:619-656`); the single thesis is the
   updated thesis `th_5a4e06fcd3a2.v2` carried by `ThesisUpdate`
   (`stages.py:626-634`, `_construction_from_update` `stages.py:596-616`).
2. `DecisionEngine.decide` receives the `InstitutionalConfidence`
   (`engine.py:47-53`).
3. `_score_thesis` reads `tc.final_confidence` -> `0.315` (`engine.py:179`);
   contributes `0.30 * 0.315` to the composite (`engine.py:203-211`).
4. Driver emitted with value `0.315` (`engine.py:278`).
5. `_determine_decision` reads `0.315` (`engine.py:257`); `0.315 < 0.5` ->
   `NO_TRADE` (`engine.py:258-259`).

## 3. Object provenance of the assessed thesis

`finalize.json:91-134` shows the provenance chain attached to the decision
(the W12/W13 entries are appended downstream). At W9 compute time the thesis
`provenance_chain` is exactly:

- W7 CounterEvidenceAssessor (`finalize.json:93-98`) — added in
  `counter_evidence/assessor.py:55-59`
- W8 ThesisBuilder (`finalize.json:99-105`) — `thesis_construction/builder.py:48-53`
- W10 ThesisUpdater (`finalize.json:106-112`) — `thesis_update/updater.py:232-236,253`

Length 3 => `knowledge_record_quality = min(3/2, 1) = 1.0` (`computer.py:43`).

Thesis metadata at W9 compute time contains only `thesis_version` and
`previous_thesis_id` (`updater.py:237-239`); no `avg_temporal_recency`, so
`temporal_recency = 1.0` default (`computer.py:112-116`).

## 4. Origin of every input

### 4.1 W6 evidence weights (evidence_quality, consensus)
- Per-set `net_institutional_weight`, `consensus_score`, `conflict_score`
  computed by `EvidenceWeighter.weight_set` (`evidence_reasoning/weighter.py:18-35`);
  `net_weight = raw*0.5 + avg_recency*0.3 + prov_ratio*0.2`, clamped `[0,1]`
  (`weighter.py:37-51`); `consensus = supporting/n`, `conflict = conflicting/n`
  (`weighter.py:53-75`). Both validated to `[0,1]`
  (`evidence_reasoning/contracts.py:94-99`).
- `evidence_quality = avg_supporting_weight = mean(net_institutional_weight)`
  over supporting sets = **0.6094** — `thesis_construction/builder.py:107-112`
  (persisted verbatim as the decision driver, `finalize.json:39-43`).
- `evidence_consensus = avg_supporting_consensus = mean(consensus_score)` over
  supporting sets — `builder.py:113-115`. **Not persisted** (see section 8).

### 4.2 W7 counter evidence (penalty, severity, flags, missing)
`CounterEvidenceAssessor.assess` (`counter_evidence/assessor.py:25-87`):
- `confidence_penalty = 0.2` — persisted via decision driver
  `counter_evidence_quality = 1 - 0.2 = 0.8` (`finalize.json:44-49`,
  `engine.py:283`). Formula `conflict_severity*0.4 + len(bias_flags)*0.1 +
  0.2*regime_conflict` (`analyzer.py:47-56`).
- `conflict_severity = cross_ratio*0.5 + avg_conflict*0.5`
  (`analyzer.py:30-44`).
- `bias_flags`, `missing_evidence`, `regime_conflict`, `contradicting_set_ids`
  — **not persisted** (section 8 derives them).
- Deterministic facts from code + observed regime `LATE_CYCLE`
  (`finalize.json:10`):
  - `missing_evidence = []` because `REGIME_EXPECTED_EVENT_TYPES` has no
    `LATE_CYCLE` key -> `missing_event_types = expected - present = {}`
    (`detector.py:9-16`, `detector.py:108-114`, `assessor.py:42-44`). Hence
    `missing_penalty = min(len(remaining_unknowns)/3, 1) = 0.0`
    (`computer.py:45`, `builder.py:41`, `updater.py:249`).
  - `regime_conflict = False` because `REGIME_EXPECTED_BIAS` has no
    `LATE_CYCLE` key -> expected `"neutral"` -> `opposite = ""` -> no set can
    match the opposite (`detector.py:19-26`, `detector.py:76-83`,
    `assessor.py:50,80`). Consistent with the thesis invalidating conditions
    carrying no "Current regime conflicts with thesis direction"
    (`builder.py:93-94`; decision output `finalize.json:66-68`).
  - `contradicting_set_ids = []` (`detector.py:33-69`); consistent with no
    "Counter-evidence from sets ..." invalidating condition
    (`builder.py:91-92`; `finalize.json:66-68`).

### 4.3 W8/W10 institutional_support (support factor)
`ThesisBuilder._compute_institutional_support` (`builder.py:124-137`):
`institutional_support = mean(net_institutional_weight * consensus_score) *
(1 - confidence_penalty)`, clamped `[0,1]`. With `confidence_penalty = 0.2`:
`support = 0.8 * mean(w*c)`. Recomputed identically by W10
(`updater.py:48-49`). **Not persisted** (section 8 bounds it).

### 4.4 Other compute() inputs
- `supporting_set_ids` -> `source_diversity = min(n/3, 1)`
  (`computer.py:42`). Supporting sets are those with `bias == "bullish"`
  (`thesis_construction/constructor.py:93-101`). Their event types are
  `{ETF_FLOW, GENERAL}` (mechanism string, `finalize.json:89`; derived at
  `builder.py:74-82`) => at least 2 supporting sets => `source_diversity` is
  `0.6667` (n=2) or `1.0` (n>=3). Exact n **not persisted**.
- `regime_alignment = 0.0` (`computer.py:41,103-109`; persisted as driver
  value, `finalize.json:56-61`): `LATE_CYCLE` not in `REGIME_EXPECTED_BIAS` ->
  expected `"neutral"` (`detector.py:19-26`); direction `bullish` != `neutral`
  -> `0.0` (`computer.py:107-109`).
- `internal_penalty` (confidence_penalty) = `0.2` (`computer.py:38`).

## 5. ConfidenceComputer.compute — full transformation chain
`src/confidence_engine/computer.py:32-100`

### 5.1 Positives (`computer.py:47-59`, weights `computer.py:14-21`)
- evidence_quality: `0.25 * 0.6094 = 0.15235`
- evidence_consensus: `0.25 * ec` (ec not persisted)
- regime_alignment: `0.15 * 0.0 = 0.0`
- source_diversity: `0.15 * sd`, sd in `{0.6667, 1.0}`
- knowledge_record_quality: `0.10 * 1.0 = 0.10`
- temporal_recency: `0.10 * 1.0 = 0.10`

`positive_score = 0.35235 + 0.25*ec + 0.15*sd` (`computer.py:56-59`).

### 5.2 Penalties (`computer.py:61-70`, weights `computer.py:23-27`)
- counter_evidence: `0.35 * conflict_severity`
- missing_evidence: `0.25 * 0.0 = 0.0`
- internal_consistency: `0.40 * 0.2 = 0.08`

`penalty_score = 0.35*conflict_severity + 0.08` (`computer.py:67-70`).

### 5.3 Combine (`computer.py:72-74`)
- `support_factor = institutional_support` (since `institutional_support > 0`,
  branch `computer.py:72`)
- `final = positive_score * support_factor * (1 - min(penalty_score, 1))`
  (`computer.py:73`)
- `final = round(clamp(0.315, 0, 1), 4) = 0.315` (`computer.py:74`)

## 6. ConfidenceEngine.evaluate — caps (all no-ops)
`src/confidence_engine/engine.py:60-73`
- `gs_cap = "medium"` only if generation present and `not all_answered`
  (`engine.py:64`); even if triggered, `min(0.315, HIGH_CONFIDENCE_THRESHOLD=0.60)`
  (`engine.py:68`, threshold `computer.py:30`) = `0.315` -> delta 0.
- `oos_cap`: `oos_ece` absent from config (`config.json:1-18`) -> `None` at
  `stages.py:645-647` -> no cap (`engine.py:65,166-173`). Delta 0.
- Final re-round `0.315` (`engine.py:73`); stored on `ThesisConfidence`
  (`engine.py:88-100`).

## 7. Contributor register

| Contributor | Value | Weight | Contribution | Status | Source |
|---|---|---|---|---|---|
| evidence_quality (avg_supporting_weight) | 0.6094 | 0.25 | +0.15235 | observed | computer.py:35,14-21; builder.py:110-112; finalize.json:41 |
| evidence_consensus (avg_supporting_consensus) | in [0.80, 1.0] | 0.25 | +0.25*ec | derived (not persisted) | computer.py:36; builder.py:113-115 |
| regime_alignment | 0.0 | 0.15 | +0.0 (max 0.15 lost) | observed | computer.py:41,103-109; finalize.json:58 |
| source_diversity | 0.6667 or 1.0 | 0.15 | +0.15*sd | derived (n not persisted) | computer.py:42; constructor.py:93-101 |
| knowledge_record_quality | 1.0 | 0.10 | +0.10 | proven (chain len 3) | computer.py:43; updater.py:253; finalize.json:91-112 |
| temporal_recency | 1.0 | 0.10 | +0.10 | proven (no meta key) | computer.py:44,112-116; updater.py:237-239 |
| counter_evidence penalty | conflict_severity = 0.0 | 0.35 | -0.0 | derived | computer.py:37,61-70; analyzer.py:30-44,47-56 |
| missing_evidence penalty | 0.0 | 0.25 | -0.0 | proven (LATE_CYCLE) | computer.py:45; detector.py:9-16,108-114 |
| internal_consistency penalty | confidence_penalty = 0.2 | 0.40 | -0.08 | observed (0.8 quality) | computer.py:38,61-70; finalize.json:47; engine.py:283 |
| support factor (institutional_support) | in [0.4551, 0.48752] | multiplicative | x0.4551..x0.48752 | derived | computer.py:39,72-73; builder.py:124-137 |
| GS cap (Goldman 3-question) | medium only, threshold 0.60 | cap | x1.0 (no-op) | proven (0.315 < 0.60) | engine.py:64,68,137-163 |
| OOS calibration cap | not applied (oos_ece None) | cap | x1.0 (no-op) | proven | engine.py:65,166-173; stages.py:645-647; config.json |

## 8. Derived facts (constraint solving, not directly persisted)

Given `final = positive_score * support_factor * (1 - penalty_score) = 0.315`,
with `support <= 0.8 * 0.6094 = 0.48752` (since `mean(w*c) <= mean(w) = 0.6094`
because `c <= 1`, contracts.py:96-97) and `positive_score <= 0.75235`:

- `support_factor = institutional_support in [0.4551, 0.48752]`
  (lower bound from `0.315 / (0.75235 * 0.92)`; upper bound from the
  `mean(w*c) <= mean(w)` cap). Reduction factor `0.5125..0.5449`
  (51.25%..54.49% reduction). Deterministic.
- `positive_score in [0.7023, 0.75235]`.
- `conflict_severity = 0.0` — the only feasible value. `cs = 0.25` or `0.5`
  would require `support_factor >= 0.503` or `0.562`, exceeding the hard cap
  `0.48752`. (Verified numerically.)
- Consequently `bias_flags = {confirmation_bias, no_dissent}` exactly
  (length 2 is required by `0.2 = 0*0.4 + k*0.1 + 0.2*False`), and all
  evidence sets share one bias with `conflict_score = 0.0`
  (`analyzer.py:15-27,47-56`).
- `avg_supporting_consensus = ec in [0.80, 1.0]` (from `positive_score >= 0.7023`).

These derived facts follow from the code formulas plus the observed
`0.6094 / 0.8 / 0.0 / 0.315 / LATE_CYCLE / bullish`; they are not serialized
in the runtime artifacts.

## 9. Transformation table

Step | Before | After | Delta | Reason
|---|---|---|---|---|
| evidence_quality term | 0.0000 | +0.15235 | +0.15235 | 0.25 x 0.6094 (computer.py:56) |
| evidence_consensus term | 0.15235 | +0.25*ec | +0.25*ec (ec in [0.80,1.0]) | 0.25 x avg_supporting_consensus (computer.py:56) |
| regime_alignment term | +0.25*ec | +0.25*ec | +0.0 (max +0.15 lost) | LATE_CYCLE -> expected "neutral", bullish mismatch -> 0.0 (computer.py:41,103-109; detector.py:19-26) |
| source_diversity term | +0.25*ec | +0.25*ec+0.15*sd | +0.10 or +0.15 | min(n/3,1), n>=2 supporting sets (computer.py:42; constructor.py:93-101) |
| knowledge_record_quality term | prior | +0.10 | +0.10 | min(len(chain)/2,1), chain len 3 (computer.py:43) |
| temporal_recency term | prior | +0.10 | +0.10 | default 1.0, no avg_temporal_recency (computer.py:44,112-116) |
| positive_score total | 0 | P in [0.7023, 0.75235] | +0.7023..+0.75235 | sum of weighted positives (computer.py:56-59) |
| counter_evidence penalty | P | P - 0.0 | -0.0 | 0.35 x conflict_severity, cs = 0.0 (derived; computer.py:67) |
| missing_evidence penalty | P | P - 0.0 | -0.0 | 0.25 x 0.0, LATE_CYCLE has no expected types (computer.py:67; detector.py:9-16) |
| internal_consistency penalty | P | P - 0.08 | -0.08 | 0.40 x confidence_penalty 0.2 (computer.py:67) |
| penalty_score total | 0 | 0.08 | +0.08 | cs=0, mp=0, ip=0.2 (computer.py:67-70) |
| **support factor multiply** | P | P x S, S in [0.4551, 0.48752] | **-51.25%..-54.49%** | final x institutional_support; support = 0.8 x mean(w*c) <= 0.48752 (computer.py:72-73; builder.py:124-137) |
| penalty block multiply | P x S | P x S x 0.92 | -8.0% | (1 - penalty_score) = 1 - 0.08 (computer.py:73) |
| clamp + round | 0.3150.. | 0.315 | -0.0001 (round) | computer.py:74 |
| GS cap | 0.315 | 0.315 | -0.0 | min(0.315, 0.60) no-op (engine.py:64,68) |
| OOS cap | 0.315 | 0.315 | -0.0 | oos_ece None, no cap (engine.py:65; stages.py:645-647) |
| DecisionEngine gate | 0.315 | NO_TRADE | 0.315 < 0.5 | engine.py:257-259; NO_TRADE_CONFIDENCE=0.5 engine.py:33 |

## 10. Answer

Which single transformation reduces confidence the most?

**The support factor multiplication in `ConfidenceComputer.compute`
(`computer.py:72-73`): `final = positive_score * support_factor * (1 - penalty_score)`
with `support_factor = institutional_support in [0.4551, 0.48752]`.**

It is a multiplicative reduction of at least 51.25% (up to 54.49%) of the
entire confidence mass, and it is the dominant term:
- regime_alignment zeroing removes at most `0.15` absolute on a
  `positive_score` of ~0.70-0.75 (relative ~20%);
- internal_consistency penalty removes `0.08` absolute (~8% multiplicative);
- evidence_quality shortfall is `0.09765` absolute;
- missing_evidence and the counter_evidence penalty (cs = 0.0) remove nothing;
- GS cap and OOS cap remove nothing.

The support factor is bounded above by `0.8 * 0.6094 = 0.48752` because
`institutional_support = mean(net_institutional_weight * consensus_score) *
(1 - confidence_penalty)` (`builder.py:131-136`) and
`mean(w*c) <= mean(w) = evidence_quality = 0.6094` (consensus <= 1). Every
other positive contributor is capped regardless, so the support factor alone
removes more than half of the achievable confidence before the
`NO_TRADE_CONFIDENCE = 0.5` gate is evaluated.

## 11. Observability limitations (facts)

- W9's per-thesis `confidence_breakdown`, `positive_contributors`,
  `negative_contributors`, `confidence_penalties`, and `metadata.support_factor`
  are constructed in memory (`computer.py:76-99`, `engine.py:88-100`) and are
  **not serialized** in the runtime artifacts. Only the aggregate
  `final_confidence = 0.315` reaches `finalize.json` (via DecisionEngine).
- Consequently `avg_supporting_consensus`, `conflict_severity`,
  `bias_flags`, `institutional_support`, and the exact supporting-set count
  are not directly observable; their values in this document are derived from
  the code formulas and the persisted values `0.6094 / 0.8 / 0.0 / 0.315` plus
  the observed regime `LATE_CYCLE` and direction `bullish`.
- `conflict_severity = 0.0` and `bias_flags = {confirmation_bias, no_dissent}`
  are the only assignments consistent with `confidence_penalty = 0.2`,
  `support_factor <= 0.48752`, and `final = 0.315`; any nonzero
  `conflict_severity` would require `support_factor > 0.48752`.
