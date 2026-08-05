# EVIDENCE_QUALITY_AUDIT_001 — evidence_quality (avg_supporting_weight) computation

Read-only audit. No code or test modified. Facts only; no fixes or recommendations.

## 1. Scope

- Target: latest successful runtime `runtime_20260804_230820`
  (`outputs/2026-08-04/runtime_20260804_230820`, exit 0, 25/25 stages ok, git
  commit `78c9ad4` per `runtime/run_registry.jsonl`).
- Traced: the complete computation of the decision driver
  `evidence_quality = 0.6094` (`finalize.json:39-43`, score `0.0914`, weight
  `0.15`) for the single assessed thesis `th_5a4e06fcd3a2.v2` (bullish), from
  raw W5 observations through W6 collection, W7 grouping/detection/weighting,
  W8/W10 confidence-input assembly, to the W13 decision engine.

## 2. The definition point (single source of truth)

`evidence_quality` is read from the thesis, not recomputed in the decision
engine:

```
src/decision_engine/engine.py:180-182  (DecisionEngine._score_thesis)
  evidence_quality = float(thesis.confidence_inputs.get("avg_supporting_weight", 0.0))
```

The value `avg_supporting_weight` is produced once in the thesis builder and
rebuilt identically by the updater:

```
src/thesis_construction/builder.py:102-122  (ThesisBuilder._build_confidence_inputs)
  avg_set_weight = round( sum(s.net_institutional_weight for s in supporting_sets) / len(supporting_sets), 4 )   # :110-112
  avg_set_consensus = round( sum(s.consensus_score for s in supporting_sets) / len(supporting_sets), 4 )        # :113-115
  return { "avg_supporting_weight": avg_set_weight, "avg_supporting_consensus": avg_set_consensus,
           "conflict_severity": ..., "confidence_penalty": ...,
           "raw_support": avg_set_weight * avg_set_consensus }                                                  # :116-122
```

I.e. `evidence_quality = mean over supporting sets of net_institutional_weight`.
Called by:
- W8 `ThesisBuilder.build_thesis` (confidence-inputs stored on the thesis;
  `builder.py:29-36+`).
- W10 `ThesisUpdater.update` — `confidence_inputs_new = ThesisBuilder._build_confidence_inputs(supporting_sets, assessment)` (`updater.py:49`), stored on the `.v2` thesis (`updater.py:250`). Same sets + same assessment ⇒ identical value.
- The `.v2` thesis is the one assessed by W9 and scored by W13 (`stages.py:596-616,626-634`; `engine.py:64-88,180`).

A second, independent consumer exists: `ConfidenceComputer.compute` reads the
same key (`computer.py:35`) into its `evidence_quality` positive contributor
with weight `0.25` (`computer.py:15`). The W13 driver weight is `0.15`
(`engine.py:28`, `finalize.json:42`). These are two different weighting
schemes for the same underlying value; the persisted `0.6094` is the shared value.

## 3. Stage-by-stage transformation register

| # | Stage | Input | Output | Weighting / normalization / aggregation | File | Function | Lines |
|---|---|---|---|---|---|---|---|
| 1 | W5 classification | per-observation Meth.§7 criteria | `obs.confidence` (base_confidence) | Signal `min(0.5+0.1·n+, 0.95)`; Weak `min(0.3+0.1·n+, 0.6)`; Watch `min(0.2+0.1·n+, 0.4)`; Noise `min(0.5+0.1·(3−n+), 0.85)`; Ignore `0.9` | `signal_assessment/classifier.py` | `NoiseSignalClassifier.classify` | 58-77 (caps 60,64,68) |
| 2 | W6 filter | `SignalAssessment.observations` | kept observations | NOISE / IGNORE discarded, never become evidence (counters incremented) | `evidence_collection/collector.py` | `EvidenceCollector.collect` | 79-92 |
| 3 | W6 evidence build | classified observation | `Evidence` item | `composite_weight = round(base_confidence × regime_weight, 4)`; `temporal_recency = min(max(1/(1+|change_sigma|), 0.1), 1.0)`; Provenance always attached; `source_kr_id = kr_ids[0]` else `kr_synthetic_<obs_id>`; bias from `INSTRUMENT_TO_REGIME_BIAS`; event_type from `INSTRUMENT_TO_EVENT_TYPE` | `evidence_collection/collector.py` | `_build_evidence`; `_query_knowledge_records`; `_resolve_bias` | 112-168 (cw 120-121; recency 160; provenance 137-141); 170-181; 184-185 |
| 4 | W7 group + dedup | evidence items | per-event_type groups, duplicate ids | same `source_kr_id` + same `event_type` ⇒ keep higher `composite_weight`, other flagged duplicate; one set per event_type | `evidence_reasoning/grouper.py` | `EvidenceGrouper.group`; `assign_set_id` | 18-43; 45-47 |
| 5 | W7 detect | group | `EvidenceSet` (bias, supporting/contradicting ids) | majority bias by count; items of opposite bias (or neutral/mixed when majority bullish/bearish) → `contradicting_evidence_ids`; all items → `evidence_ids` | `evidence_reasoning/detector.py` | `EvidenceDetector.analyze_group` | 33-73 |
| 6 | W7 weight | set + all evidence | `net_institutional_weight`, `consensus_score`, `conflict_score`, `confidence_contribution` | net weight over ALL set items (incl. contradicting): `raw = mean(composite_weight)`; `recency_boost = avg_recency × 0.3`; `prov_boost = prov_ratio × 0.2`; `net = raw×0.5 + recency_boost + prov_boost`, clamp [0,1]; `consensus = supporting/n`; `conflict = conflicting/n`; `confidence_contribution = net × consensus` | `evidence_reasoning/weighter.py` | `weight_set`; `_compute_net_weight`; `_compute_consensus_conflict` | 18-35; 37-51; 53-75 |
| 7 | W8 select supporting sets | sets + direction | `supporting_sets` | sets whose `bias == direction` (bullish); all other-directions sets + `contradicting_set_ids` become counter sets | `thesis_construction/constructor.py` | `_supporting_set_ids`; `_counter_set_ids` | 93-101; 103-116 |
| 8 | W8 / W10 aggregate | supporting sets | `avg_supporting_weight = 0.6094` | arithmetic mean of `net_institutional_weight`, round 4dp; `avg_supporting_consensus` separately (not part of this driver) | `thesis_construction/builder.py` (W8); `thesis_update/updater.py:49` (W10) | `_build_confidence_inputs` | 102-122 |
| 9 | W13 driver | thesis `confidence_inputs` | `evidence_quality` driver | read verbatim; driver `score = round(value × 0.15, 4)` | `decision_engine/engine.py` | `_score_thesis`; `_decision_drivers` | 180-182; 274-297 |

## 4. Where evidence is discarded, capped, normalized, deduped, or adjusted

Discarded (never enter evidence):
- NOISE and IGNORE observations are dropped before evidence construction (`collector.py:79-92`; counters `filtered_noise`/`filtered_ignore`).
- No KG match ⇒ synthetic provenance source id `kr_synthetic_<obs_id>` (`collector.py:124-125`), still full provenance object.

Capped:
- `base_confidence` caps by label: Signal ≤ 0.95, Weak ≤ 0.6, Watch ≤ 0.4 (`classifier.py:60,64,68`).
- `composite_weight = round(base_confidence × regime_weight, 4)` (`collector.py:121`); `regime_weight` default `0.8` (`collector.py:70`, stage `params.get("regime_weight", 0.8)` `orchestration/stages.py:465`; no override in `runtime_config.json`).
- `temporal_recency` clamp `[0.1, 1.0]` (`collector.py:160`).
- `net_institutional_weight` clamp `[0,1]` (`weighter.py:51`); contract validates `[0,1]` (`evidence_reasoning/contracts.py`; pinned by `tests/test_evidence_reasoning.py:133-137` for 1.5 → error).
- `composite_weight` identity is contract-validated (`evidence_collection/contracts.py:99-102`) and documented (`INSTITUTIONAL_CONTRACTS.md:280-281,298,309`).

Normalized:
- `consensus = supporting/n` and `conflict = conflicting/n` (`weighter.py:73-74`).
- Averages over sets divide by `len(supporting_sets)` (`builder.py:110-115`).

Duplicate removal:
- Same `source_kr_id` + same `event_type` → keep the higher `composite_weight`, other marked duplicate (`grouper.py:29-38`). Dedup can only raise or keep the set's mean composite weight, never lower it.

Contradicting-evidence handling:
- Within a set, opposite-bias (or neutral/mixed vs bullish/bearish majority) items are flagged `contradicting_evidence_ids` (`detector.py:50-57`) and lower `consensus_score` only.
- They still enter `net_institutional_weight` because the group is all `evidence_ids` (`weighter.py:20`), so their own `composite_weight`/recency are averaged in — but there is no explicit per-item contradiction penalty on net weight.
- Explicit contradiction penalty (`confidence_penalty`, this run 0.2) is applied later to `institutional_support = raw×(1−penalty)` (`builder.py:124-137`), NOT to the `evidence_quality` driver.

## 5. Why evidence_quality = 0.6094 and not ≈ 1.0

Two layered causes: a structural (design) ceiling below 1.0, and run-specific
evidence below that ceiling.

Structural ceiling (applies to every run, regardless of evidence quality):

```
max base_confidence (Signal)   = 0.95        classifier.py:60
max composite_weight           = 0.95 × 0.8  = 0.76   collector.py:120-121, stages.py:465
net = raw×0.5 + recency×0.3 + prov×0.2                weighter.py:50
max net (raw=0.76, recency=1.0, prov=1.0) = 0.76×0.5 + 0.3 + 0.2 = 0.88
```

- No `EvidenceSet` can reach `net_institutional_weight = 1.0`; the ceiling is
  `0.88` under default `regime_weight = 0.8`. Even if `regime_weight` were
  raised to 1.0 the ceiling is `0.95×0.5 + 0.3 + 0.2 = 0.975`, and it cannot be
  exceeded because the Signal confidence cap is 0.95 and the composite factor
  contributes at only 0.5.
- Therefore `avg_supporting_weight` (= `evidence_quality`) is structurally
  capped well below 1.0. The observed `0.6094` is inside this ceiling.

Run-specific arithmetic (`prov_ratio = 1.0` always, since every item receives a
Provenance object `collector.py:137-141`):

```
0.6094 = mean_cw × 0.5 + avg_recency × 0.3 + 0.2
      ⇒ mean_cw × 0.5 + avg_recency × 0.3 = 0.4094
```

Given `avg_recency ∈ [0.1, 1.0]` (`collector.py:160`):
- `mean_cw ∈ [0.2188, 0.7588]` ⇒ per-item `base_confidence ∈ [0.27, 0.95]` at `regime_weight = 0.8`.

The exact value is set by the observations' `base_confidence` (Signal cap 0.95,
Weak 0.6, Watch 0.4) and their `change_sigma`-derived recency. Per-item values
are not persisted (see §7), so only this constraint identity can be stated from
code + persisted aggregate.

What does NOT explain 0.6094 (precision guardrails):
- It is not reduced by `confidence_penalty` (0.2) — that applies to
  `institutional_support` (`builder.py:135`), not to this driver.
- It is not reduced by `consensus_score` — consensus is a separate driver
  (`avg_supporting_consensus`), and `raw_support = avg_weight × avg_consensus`
  (`builder.py:121`) is a third stored field.
- It is not lowered by deduplication — dedup keeps the higher composite weight.
- Contradicting items only drag net weight through their own composite
  weight/recency; the primary contradiction handling (consensus + penalty)
  affects other values.

## 6. Consistency with persisted run values

- Driver score `0.0914 = round(0.6094 × 0.15, 4)` (`engine.py:294`; matches `finalize.json:40-42`).
- `ConfidenceComputer` contribution would be `0.6094 × 0.25 = 0.15235` (`computer.py:15,56-59`); not persisted separately.
- Supporting sets for the bullish thesis: event types `{ETF_FLOW, GENERAL}`, n ≥ 2 (derived in `INSTITUTIONAL_SUPPORT_AUDIT_001` §3; mechanism `finalize.json:89`). `ETF_FLOW` arises from the `Gold Positioning` instrument (`collector.py:34`, bias bullish `collector.py:47`); `GENERAL` from `XAU/USD` (`collector.py:25,38`) and/or `S&P 500 Futures` (`collector.py:30,43`). Reconstruction only; set contents not persisted.
- `avg_supporting_consensus` is not persisted; derived to lie in `[0.9335, 1.0]` from the `institutional_support ∈ [0.4551, 0.48752]` interval (`INSTITUTIONAL_SUPPORT_AUDIT_001` §4-6).

## 7. Observability notes (facts)

- `evidence_quality = 0.6094` is the only value of this chain persisted in run
  artifacts (as the W13 driver `finalize.json:39-43`). The per-set
  `net_institutional_weight`/`consensus_score`, per-item
  `base_confidence`/`composite_weight`/`temporal_recency`, the W6 counts
  (`signals_count`/`weak_signals_count`/`watch_count`/`filtered_noise_count`/
  `filtered_ignore_count`, `collector.py:104-109`), and `avg_supporting_consensus`
  are not serialized for this run. `stages.json` stores only stage
  id/status/duration; `run.log` contains no evidence/weight/set lines.
- `finalize.json:245-246` `evidence_count: 3` and the
  `reason_CPI_inflation_pressure_down` chain belong to the legacy forecast path
  (`legacy_decision`), not the W6/W7 institutional evidence items; do not conflate.
- Incidental implementation fact (not causal for this run): `INSTRUMENT_TO_REGIME_BIAS`
  contains the misspelled value `"USD/JPY": "bulllish"` (`collector.py:46`), which
  would classify a USD/JPY observation as `bulllish` (no matching `OPPOSITE_BIAS`
  key) rather than `bullish`.
