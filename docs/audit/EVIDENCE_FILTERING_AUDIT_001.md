# EVIDENCE_FILTERING_AUDIT_001 — why high-value evidence did not enter the pipeline

Read-only audit. No code or test modified. Facts only; no fixes or recommendations.

## 1. Scope

- Target: latest successful runtime `runtime_20260804_230820`
  (`outputs/2026-08-04/runtime_20260804_230820`, exit 0, 25/25 stages ok, git
  `78c9ad4`; `evidence_collection` 13.4ms, `evidence_reasoning` 12.3ms,
  `counter_evidence` 10.0ms, `stages.json`).
- Traced: the complete lifecycle of every evidence item from W4 briefing
  through W5 collection/classification, W6 filtering, W7 weighting/evidence
  sets/reasoning, W8/W10 supporting-set selection, to the W13 decision engine.
- Persisted anchors: `evidence_quality = avg_supporting_weight = 0.6094`
  (`finalize.json:39-43`), `counter_evidence_quality = 0.8`
  (`finalize.json:44-49`), precondition at `finalize.json:89`.
- Read-only constraint: no code or test was modified.

## 2. Lifecycle map

```
W4 PreMarketBriefing (briefing_assembler.py:50-94)
  9 overnight changes (6 yfinance + 3 FRED, overnight_fetcher.py:12-25)
  1 positioning snapshot (positioning.py:24-38)                    -> stub-heavy
  news_items = [] (finalize.json:17 news_confidence 0.0)
  anomaly_flags >= 1 (derived; AnomalyDetectionEngine, briefing_assembler.py:80)
     |
     v
W5 SignalAssessment (assembler.py:38-195; invoked stages.py:403-422)
  10 + n classified observations (9 overnight + 1 positioning + n anomaly + 0 news)
  per-observation 5-criteria evaluation -> NoiseSignalClassifier.classify
     |
     v
W6 EvidenceCollection (collector.py:67-110; invoked stages.py:444-481)
  drops NOISE + IGNORE; keeps SIGNAL / WEAK_SIGNAL / WATCH
  -> 2-3 evidence items, all WATCH
     |
     v
W7 EvidenceReasoning (reasoner.py:27-62)
  grouper (grouper.py:18-43) -> detector (detector.py:19-73) -> weighter (weighter.py:18-51)
  -> 2 EvidenceSets {ETF_FLOW, GENERAL}, both bullish, conflict 0
     |
     v
W8 ThesisBuilder (constructor.py:93-101 _supporting_set_ids) -> 2 supporting sets
W10 ThesisUpdater (updater.py:49) -> avg_supporting_weight = 0.6094
W13 DecisionEngine (engine.py:180-182, 207) -> evidence_quality 0.6094, counter 0.8
```

## 3. Filtering-step register

Each step: input count / output count / discarded / reason / file / function /
line. Stage counts are DERIVED (per-item output is not persisted, §8).

### R0 — W4 instrument fetch (data gate)
- Input: 9 configured instruments (`OVERNIGHT_TICKERS` 6, `overnight_fetcher.py:12-19`; `OVERNIGHT_FRED_SERIES` 3, `:21-25`).
- Output: 9 `OvernightPriceChange`. Fetches confirmed in `run.log:50,81,112,143,174,205` (all six `range=5d`, HTTP 200) and FRED cached series (`DFII10/DGS10/T5YIE` exist in `data/economic/`).
- Discarded: 0.
- Discard reason: n/a (fetch failures silently return `[]`, `overnight_fetcher.py:54-55,76-77`; none failed this run).

### R1 — W4 anomaly generation gate
- Input: 9 overnight changes.
- Output: ≥1 template-violation flag (derived; see §7 constraint identity).
- Discarded (no flag): instruments with `|z| < 2.0` that do not match a template. `GC=F/DX-Y.NYB/ES=F/BZ=F` have z = 0.0 (`overnight_fetcher.py:113-114`); `EURUSD/USDJPY` real z-scores are < 2.0 (forced: a ≥2σ move would create an anomaly → WEAK_SIGNAL → USD_FX counter-set → cross-set contradiction, absent, §7).
- File/function/line: `src/pre_market/anomaly_detector.py` `AnomalyDetectionEngine.detect` `:39-96` (2σ `:59-67`, 3σ `:49-58`, templates `:69-94`); pairing table `:7-26`.

### R2 — W4 positioning snapshot gate (stub injection)
- Input: 1 call, `positioning.py:24-38`.
- Output: 1 `PositioningSnapshot` in which `cot_z_score = 0.0`, `cot_regime = "neutral"` (hard-coded stub, `positioning.py:40-41`), `gofo_rate = 0.0` (stub, `positioning.py:87-89`). Only `etf_flow_*` is live (GLD/IAUM, `run.log:234-292`), plus OI from GC Volume (`positioning.py:72-85`).

### R3 — W5 per-criterion evaluation (5 gates per observation)
- Input: 9 overnight + 1 positioning + n anomaly observations.
- Per-observation gates (`assembler.py`): persistence `:44-48`, breadth `:49-53`, magnitude `:54-60`, narrative `:61-65`, volume `:66-68`; positioning `:96-128`; anomaly `:130-157`.
- Resulting pass pattern for this run (each non-anomaly observation's only possible pass is breadth; all other gates structurally closed — §5.3):
  - `persistence` passed=False for every normal observation: hard-coded `deviation_days=1.0, instrument_type="ETF"` at `assembler.py:44-47`; ETF noise threshold 1d ⇒ 1 ≤ 1 ⇒ `passed=False` (`persistence.py:54-59`). For positioning `passed=|cot_z_score|≥1.0` = False (`assembler.py:102`). For anomaly observations `passed=True` (`assembler.py:132`).
  - `magnitude` passed=False for all: requires `|change_sigma| ≥ 2.0` (`assembler.py:58,113,133`; `classifier.py:55`). GC/DX/ES/BZ z=0.0; EURUSD/USDJPY |z|<2 (R1); anomaly |value|<2 (R1-derived).
  - `narrative_fit` passed=False for all: `news_items` empty ⇒ `"no news headlines available"` (`narrative.py:34-41`).
  - `volume_flow` passed=False for all normal observations: called with only `change_sigma`, no volume/OI/ETF args ⇒ `"no volume/flow data available"` (`volume.py:62-69`, `assembler.py:66-68`); positioning volume only if |GLD+IAUM 5-d change| > 1.0% (`volume.py:49-56`, unknown, primary composition assumes not).
  - `breadth` the only variable gate: passes if confirmed (score ≥ threshold) against `EXPECTED_RELATIONSHIPS` (`breadth.py:5-8` — keys exist ONLY for `XAU/USD` and `DXY`), or if the instrument itself moved < 0.01% (`breadth.py:42-49` skip → passed=True). All other instruments have no relationships ⇒ `score 0, passed=False` (`breadth.py:74-77`).
- Output: 5 `CriterionScore` per observation with the pass pattern above.

### R4 — W5 classification gate
- Input: 10 + n observations (`n ≥ 1` anomaly).
- Output labels: 8-9 IGNORE/NOISE, 2-3 WATCH (primary composition, §4).
- Logic: `positive_count = #{passed}` (`classifier.py:51`); SIGNAL if `≥3` or (`≥2` and persistence) `:58`; WEAK_SIGNAL if `≥2` `:62`; WATCH if `==1` or magnitude `:66`; IGNORE if `0` and `|z|<0.5` `:70`; else NOISE `:75`.
- Confidence caps: SIGNAL `0.95` `:60`, WEAK `0.6` `:64`, WATCH `min(0.2+0.1n, 0.4)` → `0.3` for n=1 `:68`, IGNORE `0.9` `:72`, NOISE `:76`.
- File/function/line: `src/signal_assessment/classifier.py` `NoiseSignalClassifier.classify` `:30-79`.

### R5 — W6 filter (the only place evidence is actually dropped)
- Input: 10 + n classified observations.
- Output: 2-3 evidence items (primary: 2 — positioning + anomaly; alternative: 3 with a breadth-passed XAU/USD or S&P item).
- Discarded: 8-9 observations.
- Discard reason: `obs.classification == NOISE` → `filtered_noise += 1; continue` (`collector.py:80-82`); `obs.classification == IGNORE` → `filtered_ignore += 1; continue` (`collector.py:83-85`).
- File/function/line: `src/evidence_collection/collector.py` `EvidenceCollector.collect` `:67-110` (counters `:73-77`, kept counters `:87-92`, item build `:94`).

### R6 — W6 confidence transform
- Applied to kept items only: `composite_weight = round(confidence × regime_weight, 4)` with `regime_weight = 0.8` (default `collector.py:70`; stage `params.get("regime_weight", 0.8)` `stages.py:465`, no override in `runtime_config.json`). WATCH 0.3 × 0.8 = `0.24` (`collector.py:120-121`).
- `temporal_recency = min(max(1/(1+|change_sigma|), 0.1), 1.0)` (`collector.py:160`); Provenance always attached (`:137-141`); `source_kr_id = kr_synthetic_<obs_id>` because `knowledge_graph = None` (`stages.py:463`; `collector.py:124,170-181`).

### R7 — W7 dedup gate
- Input: 2-3 items; Output: 2-3 items; discarded 0.
- Reason: dedup keys on `(source_kr_id, event_type)` (`grouper.py:29-38`); under KG=None every `source_kr_id` is unique ⇒ no same-key pair exists; `duplicates_removed = 0` (`reasoner.py:56`).

### R8 — W7 bias split (set membership gate)
- Input: 2 groups (`ETF_FLOW` from `Gold Positioning`; `GENERAL` from XAU/USD/anomaly/S&P). Output: 2 `EvidenceSet`, majority bias `bullish` (`detector.py:33-34`). All items land in `supporting_evidence_ids` (`detector.py:50-51`); `contradicting_evidence_ids` empty. Discarded: 0 items, 0 counter-members.

### R9 — W7 weight gate
- `net_institutional_weight = mean(composite_weight)×0.5 + mean(recency)×0.3 + prov_ratio×0.2`, clamp [0,1] (`weighter.py:37-51`). WATCH-only composition ⇒ ≈0.62 per set (exact split in §7). `consensus = supporting/n` (`weighter.py:73`), `conflict = conflicting/n` (`:74`).

### R10 — W7 reasoning assembly
- `reasoner.py:27-62`: groups `:35`, sets `:38-44`, totals `:46,54-55`, duplicates `:56`. Output: `EvidenceReasoning` with 2 sets, 2-3 items.

### R11 — W8 supporting-set gate (the only set-level filter)
- Input: 2 sets (both bullish). Output: 2 `supporting_sets`; 0 counter sets.
- Reason: `_supporting_set_ids` selects `es.bias == direction` (`constructor.py:93-101`); bearish/neutral/mixed sets would be excluded here and become counter sets via `_counter_set_ids` (`:103-116`).

### R12 — W8/W10/W13 aggregation
- `avg_supporting_weight = mean(set.net_institutional_weight)` (`builder.py:110-112`; recomputed identical at `updater.py:49`); read by the engine verbatim `engine.py:180-182`; `counter_evidence_quality = 1 − confidence_penalty` `engine.py:207`.

## 4. Per-observation register (W5 classification → W6 fate; derived)

| Observation | change_sigma | breadth | persistence | magnitude | narrative | volume | positive | Label (conf) | W6 fate |
|---|---|---|---|---|---|---|---|---|---|
| XAU/USD (GC=F) | 0.0 (4 bars) | FAIL — gold–DXY co-move (anomaly fired) | False | False | False | False | 0 | IGNORE (0.9) | dropped |
| DXY (DX-Y.NYB) | 0.0 | FAIL — score < 0.5 (required, §7) | False | False | False | False | 0 | IGNORE (0.9) | dropped |
| S&P 500 Futures (ES=F) | 0.0 | FAIL — no relationships, |move|≥0.01 | False | False | False | False | 0 | IGNORE (0.9) | dropped |
| Brent Crude (BZ=F) | 0.0 | FAIL — no relationships | False | False | False | False | 0 | IGNORE (0.9) | dropped |
| EUR/USD (EURUSD=X) | real, <2.0 | FAIL — no relationships (|move|≥0.01) | False | False | False | False | 0 | IGNORE or NOISE | dropped |
| USD/JPY (USDJPY=X) | real, <2.0 | FAIL — no relationships | False | False | False | False | 0 | IGNORE or NOISE | dropped |
| US10Y Real Yield (DFII10) | tiny | FAIL — no relationships | False | False | False | False | 0 | IGNORE (0.9) | dropped |
| US10Y Nominal Yield (DGS10) | tiny | FAIL — no relationships | False | False | False | False | 0 | IGNORE (0.9) | dropped |
| Breakeven Inflation (T5YIE) | tiny | FAIL — no relationships | False | False | False | False | 0 | IGNORE (0.9) | dropped |
| Gold Positioning | 0.0 | PASS — hard-coded True (`assembler.py:112`) | False (|cot_z|=0) | False | False | False | **1** | **WATCH (0.3)** | **kept → ETF_FLOW** |
| Anomaly: XAU/USD template | value ≥ 0.076 | hard-coded False (`assembler.py:134`) | **True** (`:132`) | False (|value|<2) | False | False | **1** | **WATCH (0.3)** | **kept → GENERAL** |

All kept items: `base_confidence 0.3`, `composite_weight 0.24`, Provenance attached, `kr_synthetic_<id>`.

## 5. The four required explanations

### 5.1 Why the +0.64% XAU/USD move was discarded
Ground fact: the daily gold change was `(4109.6 − 4083.4)/4083.4 = +0.6416%` (gold.csv rows 2026-08-03/2026-08-04; the GC=F 5-d window also closes on 4109.6/4083.4, `run.log:69`). It was discarded by sequential independent gates:

1. **z-score zeroed (magnitude gate):** the GC=F 5-d fetch returned 4 bars (`run.log:69` `2026-07-30 → 2026-08-04`); `_compute_sigma` returns `0.0` when `len(series) < 5` (`overnight_fetcher.py:113-114`). The +0.64% move cannot express itself: `change_sigma = 0.0`, magnitude `passed=False` (`assembler.py:58`).
2. **Persistence gate:** duration hard-coded to 1 day with ETF thresholds (`assembler.py:44-47`); 1 ≤ ETF noise 1 ⇒ `passed=False`, score 1.0 (`persistence.py:54-59`). A same-day move cannot be "persistent".
3. **Breadth gate disconfirmed:** co-move with DXY (see §7) ⇒ the gold–DXY expected-inverse relationship is disconfirmed (`breadth.py:65-72`), so breadth does not pass.
4. **Narrative/volume gates closed:** no news (`narrative.py:34-41`) and no volume data (`volume.py:62-69`).
5. **Classification:** 0 positive criteria and `|z|=0 < 0.5` ⇒ `IGNORE` (`classifier.py:70-73`), confidence 0.9.
6. **W6 drop:** `obs.classification == IGNORE` ⇒ `continue` (`collector.py:83-85`).

A +0.64% daily move is therefore structurally capped at **IGNORE** (or, if breadth had confirmed, at **WATCH 0.3**) by gate 1+2 regardless of its size, because the sigma is computed on a <5-bar window and persistence uses a hard-coded 1-day duration.

### 5.2 Why stub evidence survived
The `Gold Positioning` evidence's decisive attribute — a passing breadth criterion — is **hard-coded** `CriterionScore("breadth", 0.5, 0.5, True, "positioning snapshot")` (`assembler.py:112`), independent of data quality. Even though `cot_z_score`, `cot_regime`, and `gofo_rate` are stubs (`positioning.py:40-41,87-89`) and persistence fails (|cot_z|=0), the hard-coded breadth yields exactly 1 positive ⇒ WATCH (`classifier.py:66-69`) ⇒ kept (`collector.py:87-92`). The stub hence bypasses every data-dependent gate that killed the live price move.

### 5.3 Why SIGNAL / WEAK_SIGNAL were unreachable
SIGNAL requires `positive_count ≥ 3` or `(≥2 and persistence_passed)` (`classifier.py:58`); WEAK_SIGNAL requires `≥2` (`:62`). For normal observations:
- `persistence_passed` is structurally False (hard-coded `deviation_days=1.0` / ETF 1-day noise, `assembler.py:44-47`, `persistence.py:54-59`);
- `narrative_passed` requires headlines — none exist (`narrative.py:34-41`);
- `volume_passed` requires volume/flow args — never provided for overnight instruments (`volume.py:62-69`);
- `magnitude_passed` requires `|z| ≥ 2.0` — impossible for the four 4-bar instruments (z=0.0) and < 2.0 for FX (R1);
- so only `breadth` can pass ⇒ `positive_count ≤ 1` ⇒ the only non-IGNORE/NOISE outcome is **WATCH**.

For anomaly observations: persistence is True but breadth/narrative/volume are hard-coded False (`assembler.py:134-136`) ⇒ `positive_count = 1 + (magnitude|value|≥2)` ⇒ at most 2, which is WEAK_SIGNAL (0.5); this run |value| < 2 ⇒ WATCH.

For positioning: persistence |cot_z|≥1 is False, magnitude |cot_z|≥2 is False, narrative False; only hard-coded breadth passes ⇒ WATCH.

SIGNAL is therefore unreachable for every observation class in this run; WEAK_SIGNAL is reachable only syntactically (anomaly with |value|≥2, or positioning with issuing live ETF flow >1%). Neither occurred in this run's derived composition.

### 5.4 Why only WATCH reached the reasoning engine
Every surviving item is WATCH: the classification rules (`classifier.py:66-69`) and W6's keep-set (`collector.py:79-92`) combined mean "kept" is equivalent to "WATCH" whenever SIGNAL/WEAK_SIGNAL are unreachable. Consequences through the chain:
- all kept items carry `base_confidence 0.3`, `composite_weight 0.24` (`collector.py:120-121`);
- all sets are formed from WATCH items (`reasoner.py:35-44`); all items are bullish ⇒ `consensus 1.0`, `conflict 0.0` (`weighter.py:73-74`; `no_dissent` flag);
- `avg_supporting_weight = 0.6094` and `counter_evidence_quality = 0.8` are therefore built exclusively from WATCH-grade evidence (`builder.py:110-112`; `engine.py:180-182,207`).
- The reasoning engine thus received 2 evidence sets, 2-3 items, all WATCH (R10); no SIGNAL or WEAK_SIGNAL item ever reached W7.

## 6. Count summary (primary composition)

| Gate | In | Out | Discarded | Discard reason |
|---|---|---|---|---|
| R0 W4 fetch | 9 configured | 9 | 0 | — |
| R1 W4 anomaly | 9 | ≥1 flag | — (not evidence) | not a ≥2σ or template pair |
| R3/R4 W5 criteria+classify | 11 | 2 WATCH | 9 | ≤1 positive; IGNORE/NOISE rules |
| R5 W6 filter | 11 | 2 | 9 (8 IGNORE + 1 NOISE*) | `collector.py:80-85` |
| R7 W7 dedup | 2 | 2 | 0 | no same (source_kr_id, event_type) pair |
| R8 W7 bias split | 2 | 2 | 0 | no opposite-bias items |
| R11 W8 supporting filter | 2 | 2 | 0 | both bullish |
| R12 aggregate | 2 sets | 1 value 0.6094 | — | mean of 2 set weights |

*Primary: IGNORE = 9 overnights (XAU/USD … Breakeven), NOISE = 0; alternative compositions move 1-2 to NOISE (`|z|≥0.5` FX) or add a breadth-passed WATCH. Counters `signals_count/weak_signals_count/watch_count/filtered_noise_count/filtered_ignore_count` (`collector.py:104-109`) are not persisted; counts here are derived (§8).

## 7. Persisted-value consistency (constraints on the derived composition)

- `0.6094 = mean(net_institutional_weight)` over 2 supporting sets (`builder.py:110-112`), each `= mean_cw×0.5 + mean_recency×0.3 + 0.2` (`weighter.py:37-51`). All-WATCH ⇒ per-set `0.62` exactly; the observed total `1.2188` means ≥1 item had `temporal_recency < 1.0` ⇒ `change_sigma > 0` on a collected item. The only collected-reachable path is a W4 anomaly observation (`change_sigma = flag.value = |Δgold − Δdxy|`, `assembler.py:156`; XAU/USD template pairs `anomaly_detector.py:7-26`). Primary: single anomaly item, `|Δgold−Δdxy| ≈ 0.076` ⇒ `ΔDXY ≈ +0.57%` (co-move with gold); alternative: anomaly + breadth-passed normal, `|Δgold−Δdxy| ≈ 0.165`.
- Same-direction gold/DXY is precisely the `gold_dxy_co_move` template violation (`anomaly_detector.py:9-13`) ⇒ XAU/USD's and DXY's own divergence breadths are disconfirmed ⇒ both IGNORE, consistent with R4/R5 and with the absence of any `USD_FX` counter-set.
- `counter_evidence_quality = 0.8 = 1 − 0.2`; `0.2 = len(bias_flags)×0.1` with exactly 2 flags — `confirmation_bias` + `no_dissent` (`counter_evidence/analyzer.py:47-56`, flags `:14-27`); `conflict_severity 0` and no `cross_set_conflict`/`regime_conflict` ⇒ no contradictory or counter-set evidence existed.
- Supporting event types ⊆ `{ETF_FLOW, GENERAL}` per the thesis precondition (`finalize.json:89`); `ETF_FLOW` = Gold Positioning, `GENERAL` = XAU/USD (+anomaly) and/or S&P 500 Futures (`collector.py:12-50`).

## 8. Observability notes (facts)

- No per-item or per-stage evidence is serialized for this run; W6 counters (`collector.py:104-109`), set weights, consensus, and observation labels exist only in memory. All counts in this document are derived from code constants + persisted aggregates (§7), not read from artifacts.
- `finalize.json:245-246` `evidence_count: 3` is the legacy forecast path (`reason_CPI_inflation_pressure_down`, avg return +0.905964%), not the W6 items.
- The persisted provenance chain (`finalize.json:91-134`) begins at W7; no W4/W5/W6 provenance propagates.
- `USD/JPY` bias map misspelling `"bulllish"` (`collector.py:46`) is present but unused this run (no USD/JPY item reached W6).
- `persistence.py` `NOISE_FILTERS`/`PERSISTENCE_THRESHOLDS` COMEX/DXY/CB keys are dead in this runtime path: `assembler.py:44-47` hard-codes `instrument_type="ETF"` and `deviation_days=1.0` for every overnight observation.