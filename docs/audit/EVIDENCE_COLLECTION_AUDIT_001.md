# EVIDENCE_COLLECTION_AUDIT_001 — evidence items in the latest successful run

Read-only audit. No code or test modified. Facts only; no fixes or recommendations.

## 1. Scope

- Target: latest successful runtime `runtime_20260804_230820`
  (`outputs/2026-08-04/runtime_20260804_230820`, exit 0, 25/25 stages ok, git
  commit `78c9ad4` per `runtime/run_registry.jsonl`; `stages.json`
  `evidence_collection` ok 13.4ms, `evidence_reasoning` ok 12.3ms,
  `counter_evidence` ok 10.0ms).
- Audited: every evidence item produced by W6 `EvidenceCollector` for the run's
  single thesis `th_5a4e06fcd3a2.v2` (bullish): source, timestamp, confidence,
  relevance, recency, provenance, and final weight; classification of each item
  (High/Medium/Low/Noise); and the duplicate / stale / contradictory / missing /
  weak-dominating relations among them.
- Persisted anchors: `evidence_quality = avg_supporting_weight = 0.6094`
  (`finalize.json:39-43`), `counter_evidence_quality = 0.8`
  (`finalize.json:44-49`).

## 2. Method and observability (facts)

The W6 stage returns an in-memory `EvidenceCollection` that is never
serialized for this run. Search of `outputs/2026-08-04/runtime_20260804_230820`
found only `stages.json`, `summary.json`, `run.log`, `outcome.json`,
`finalize.json`, `config.json`, `artifacts/knowledge.json`,
`artifacts/lessons.csv`; no per-item evidence, no W5/W6/W7 JSON. No cache or
checkpoint files persist W5/W6 objects (`src/orchestration/cache.py`,
temp checkpoints; none present).

Consequently every per-item value below is DERIVED from three sources:
(a) the W4 inputs persisted to disk (price caches, `run.log` fetch traces);
(b) the deterministic W5/W6/W7 transformation code; (c) the persisted
aggregates that over-constrain the composition. Facts from (c) are:
- `avg_supporting_weight = 0.6094 = mean(set.net_institutional_weight)` over
  the bullish thesis' supporting sets (`builder.py:110-112`; consumed
  verbatim at `engine.py:180-182`).
- `counter_evidence_quality = 0.8 = 1 − confidence_penalty`
  (`engine.py:207`), so `confidence_penalty = 0.2`; with formula
  `penalty = conflict_severity×0.4 + len(bias_flags)×0.1 (+0.2 if
  regime_conflict)` (`counter_evidence/analyzer.py:47-56`), this requires
  `conflict_severity = 0`, `regime_conflict = False`, exactly 2 bias flags.
  The 2 flags are `confirmation_bias` (all sets share one bias,
  `analyzer.py:14-20`) and `no_dissent` (`conflict_score = 0` in every set,
  `analyzer.py:22-27`).
- No `cross_set_conflict` flag ⇒ no contradicting evidence ids, no bearish /
  neutral / mixed sets ⇒ **no contradictory evidence existed in this run** and
  no counter set was assessed.
- `finalize.json:89` precondition "Gold ETF flow momentum ... Multi-factor
  cross-asset transmission ..." ⇒ supporting sets' event types ⊆
  `{ETF_FLOW, GENERAL}` (asserted already in `EVIDENCE_QUALITY_AUDIT_001` §6).

## 3. Deterministic item-space constraints from source

Every observation path in this run is bound by verified code constants:

1. W4 overnight `change_sigma` for all 6 yfinance instruments is 0.0: the
   fetched 5-day window in `run.log:69` is `2026-07-30 04:00 → 2026-08-04 04:00`
   (4 daily bars, 3 returns) and `src/pre_market/overnight_fetcher.py` returns
   0.0 when `len(returns) < 4`. FRED `change_sigma = abs(pct_change)/0.5`
   (overnight_fetcher.py FRED path) is far below 0.5 against cached values
   (DFII10 daily ~0.05%).
2. W5 criteria per normal observation: `persistence` `passed = False` for all
   overnight instruments (`deviation_days = 1` ≤ noise thresholds,
   `persistence.py:54-59`; score 1.0 for ETF/DXY/gold_real_yield 1-day, 0.14
   for COMEX); `magnitude` `passed = False` (`abs(z) < 2`, `classifier.py:55`);
   `narrative_fit` `passed = False` (`finalize.json:17` `news_confidence` 0.0,
   `fomc_confidence` 0.0, `recent_events` `[]`); `volume_flow` `passed = False`
   (no volume data, z = 0.0 → `XDMA`/`etf` paths return 0.0, `volume.py`).
   Therefore the only feasible passing criterion on a normal observation is
   `breadth`, and `breadth` is hard-coded `passed = True` for the
   `Gold Positioning` snapshot (`assembler.py:112`), while FRED instruments
   (`US10Y Real Yield`, `US10Y Nominal Yield`, `Breakeven Inflation`) have no
   entry in `EXPECTED_RELATIONSHIPS` ⇒ breadth `score 0, passed False`.
3. W5 classification outcome for a normal observation is therefore IGNORE
   (0 positive criteria and `|z| < 0.5`, `classifier.py:70-73`) or WATCH
   (exactly 1 positive = breadth, confidence `min(0.2+0.1×1, 0.4) = 0.3`,
   `classifier.py:66-69`). **WEAK_SIGNAL (0.5) and SIGNAL (0.95) are
   unreachable on normal observations in this run** because persistence never
   passes and only breadth may pass.
4. W6 filter: NOISE and IGNORE are dropped (`collector.py:79-92`); only
   SIGNAL / WEAK_SIGNAL / WATCH become evidence. Per item:
   `composite_weight = round(confidence × 0.8, 4)` (`regime_weight` default
   0.8; `stages.py:465`, `run.py` never overrides it), `temporal_recency =
   min(max(1/(1+|change_sigma|), 0.1), 1.0)` (`collector.py:160`), Provenance
   always attached (`collector.py:137-141`), `source_kr_id =
   kr_synthetic_<obs_id>` because `knowledge_graph = None` in the runtime path
   (`stages.py:463` reads `params["knowledge_graph"]`; `run.py` never sets it;
   `collector.py:170-181` returns `[], []`). So all items have provenanced
   synthetic ids and never link to a knowledge record.
5. W7 set weights for WATCH-only items (`cw 0.24`, `recency 1.0`, prov_ratio
   1.0) are exactly `0.5×0.24 + 0.3×1.0 + 0.2 = 0.62` per set, regardless of
   item count (`weighter.py:37-51`). The observed mean 0.6094 < 0.62 therefore
   proves at least one collected item had `temporal_recency < 1.0`, i.e.
   `change_sigma > 0`. The only collected-reachable observation with
   `change_sigma > 0` is an **anomaly-derived observation**: W4 anomaly flags
   (`gold_dxy_co_move`, `gold_real_yield_divergence`,
   `gold_equity_correlation_shift`, `detector.py:69-94`) carry
   `change_sigma = flag.value = |Δgold − Δdxy|` (or `|Δgold − ΔS&P|`,
   `assembler.py:156`) and classify WATCH (persistence `passed = True` is the
   single positive; `assembler.py:132`). Instrument of every template flag is
   `XAU/USD` ⇒ anomaly evidence lands in event_type `GENERAL`
   (`collector.py:25,38`).
6. Dedup: duplicate detection keys on `(source_kr_id, event_type)`
   (`grouper.py:29-38`); with KG = None every `source_kr_id` is unique per
   observation ⇒ **the duplicate detector is inert in the runtime path; no
   duplicate evidence was detected and none can be detected**; but also by this
   mechanism there is no same-key pair, so no duplicate evidence existed in
   this run.

## 4. Evidence item register (reconstructed; derived)

Identity anchor: `0.6094 = mean_cw×0.5 + avg_recency×0.3 + 0.2`. With every
Watch item at `cw = 0.24`, `0.6094` requires `avg_recency = 0.9647` (over all
supporting-set items). The unique minimal self-consistent composition
(2 supporting sets, both bullish, 1 item each):

| # | Item | Source | Timestamp* | Confidence (base) | Composite weight | Recency | Relevance | Provenance | Final set weight | Set |
|---|---|---|---|---|---|---|---|---|---|---|
| E1 | `Gold Positioning` snapshot (COF/ETF `positioning_snapshot`, instrument "Gold Positioning") | W4 `PositioningDataFetcher` — COT stub (z=0.0, neutral), ETF flow from GLD/IAUM, GOFO stub defaults | 2026-08-04T21:10:47Z (W6 build time, `provenance.created_at`) | WATCH, 0.3 | 0.24 | 1.0 (`change_sigma` 0.0) | HIGH — ETF-flow precondition, `finalize.json:89`; instrument bias bullish (`collector.py:47`) | always attached; `kr_synthetic_<obs>`, no KG link | **0.62** (exact) | ETF_FLOW |
| E2 | Anomaly evidence for `XAU/USD` (template violation and/or correlation shift flagged at W4; `obs_anomaly_XAU/USD_*`, source `anomaly_flag`) | W4 `AnomalyDetectionEngine` on overnight changes; value `|Δgold − Δdxy| ∈ {≈0.076, ≈0.165}` (see §5) | 2026-08-04T21:10:47Z (W6 build time) | WATCH, 0.3 | 0.24 | `1/(1+value) ∈ {0.929, 0.859}` | MEDIUM — indirect gold-signal (derived from a co-move flag, not the price move itself) | always attached; `kr_synthetic_<obs>`, no KG link | **0.5988** or **0.62** per §4 alternatives | GENERAL |

Notes: (a) WATCH confidence is exactly 0.3 for both (`classifier.py:66-69`), so
both have `cw = 0.24`. (b) The `Evidence` contract has no source-data timestamp
field; the only timestamp is W6 `provenance.created_at` (same second as W6
run, `finalize.json` provenance chain 21:10:47). Underlying price bar for any
XAU/USD item would be `2026-08-04 04:00` UTC close; the positioning snapshot's
own timestamp is set to run time (z-score 0.0 stub).

Alternative compositions consistent with the same persisted aggregate
(non-unique; item-level truth is not recoverable — §7):
- GENERAL with 2 items (XAU/USD normal WATCH `r=1.0` + anomaly WATCH
  `value = 0.165`, `r = 0.859`): `0.12 + 0.15×(1.0+0.859) + 0.2 = 0.5988`,
  identical set weight; ETF_FLOW 0.62. Total `1.2188`, mean `0.6094`.
- 3 supporting sets with distributed recency are arithmetically possible but
  require an extra event-type set with no contradicting bias and no
  `cross_set_conflict` flag; no evidence forces or excludes this.

In every case: **exactly 2-3 evidence items, all WATCH-grade, all bullish,
all provenanced, all synthetic-id, all with `recency ≥ 0.859`, in 2 supporting
sets `{ETF_FLOW, GENERAL}`**. All other observations from the run's 10-11
(9 overnight/FRED + 1 positioning + ≥1 anomaly-derived) were classified
IGNORE/NOISE and filtered by W6, or Watch-filtered-normal as above.

## 5. Classification of every evidence item

- **E1 `Gold Positioning` → Medium.** Real position data exists (ETF-flow
  fetcher), but every quantitative field is a stub default (`z=0.0` COT
  neutral, GOFO defaults, `positioning.py`), so its 0.3 WATCH confidence
  reflects "snapshot present" only. Recency maximal; relevance high (it is the
  thesis' ETF-flow precondition). Not Noise only because breadth is
  hard-coded passed; its informative content is threshold.
- **E2 `XAU/USD` anomaly → Low.** The item's entire basis is a co-move flag
  (`value ≈ 0.08-0.17`) rather than a directional price observation; the
  actual XAU/USD overnight move (+0.64% in the run window) was downgraded to
  IGNORE by W5 (persistence `passed=False`, magnitude `|z|<2`, no news). The
  evidence preserved is the vestigial flag, not the price move.
- **Filtered observations (DXY, S&P 500 Futures, Brent, EUR/USD, USD/JPY,
  US10Y Real/Nominal Yield, Breakeven Inflation) → Noise.** All nine were
  fetched, all classified IGNORE or NOISE, all dropped before evidence. Their
  collected information content for this run is zero.
- **No item is High value.** No SIGNAL or WEAK_SIGNAL item exists this run
  (constraint §3.3: unreachable given the data state).

## 6. Issue register (facts; findings are not recommendations)

**Duplicated evidence:** none existed, and none can be detected in the runtime
path: dedup keys on `(source_kr_id, event_type)` and KG=None makes every
`source_kr_id` unique (`grouper.py:29-38`, `collector.py:124`).
`duplicates_removed` is unconditionally 0 under KG=None.

**Stale evidence:** the FRED series used at W4 are cache-stale relative to the
run date (2026-08-04): `data/economic/DFII10.csv` last row 2026-07-27,
`DGS10.csv` 2026-07-10, `T5YIE.csv` 2026-07-28; `FredClient.get_series`
defaults to `use_cache=True`. No real-yield/inflation evidence existed in the
run (all three Ignored, `data_date_range` capped 2026-08-04 in
`finalize.json:11-14` despite caches ending earlier). The one live-ish price
path (gold.csv) ends on the run date.

**Contradictory evidence:** none. All items bullish; `conflict_score = 0` in
every set; zero contradicting evidence ids; `no_dissent` flagged. The driver
`counter_evidence_quality = 0.8` is `1 − penalty` where the 0.2 penalty comes
from the two bias flags (`confirmation_bias`, `no_dissent`) — i.e. the 0.8
reports an empty-but-agreeing evidence base, not the presence of refuting
evidence. It cannot read below 0.8 when sets merely agree. (Also see: the
`INSTRUMENT_TO_REGIME_BIAS["USD/JPY"] = "bulllish"` misspelling
`collector.py:46` would make any USD/JPY item neither supporting nor
contradicting vs a bullish/bearish majority — it did not occur this run.)

**Missing expected evidence:** the run fetched USD_FX instruments (DXY,
EUR/USD, USD/JPY), real yields, and breakevens yet produced zero
`USD_FX` / `REAL_YIELD` / `INFLATION` evidence — the USD and rates channels are
absent from the thesis' supporting base. Additionally the missing-evidence
check is a structural no-op for this run's regime: `REGIME_EXPECTED_EVENT_TYPES`
(`counter_evidence/detector.py:9-16`) has no `LATE_CYCLE` key, so
`missing_event_types()` returns nothing and `missing_evidence` cannot be
flagged in regime LATE_CYCLE. News/FOMC observations also absent
(`news_confidence 0.0`).

**Weak evidence dominating stronger evidence:** every surviving item is the
lowest-grade class (WATCH, base confidence 0.3, `cw 0.24`), and the two
constant terms of `weighter._compute_net_weight` (recency×0.3 + provenance×0.2)
supply 0.5 of the 0.62 set weight (~81%) while actual confidence content
(`raw×0.5 = 0.12`) supplies ~19%. The strongest observed market fact — the
XAU/USD overnight move (~+0.64% in the run window) — was filtered by W5 and
enters no set; the surviving GENERAL evidence is an anomaly tag. The two sets
contribute near-identically (0.62 vs 0.5988) despite E1 resting on stub data
and E2 on a residual flag, i.e. no set has higher-grade evidence to dominate.

## 7. Observability notes (facts)

- Per-item fields are not persisted; reconstruction per §2-§5 is consistent
  with all persisted aggregates and all source constants, but is not unique at
  item level (alternative GENERAL 2-item split in §4 has identical weight).
- `finalize.json:245-246` `evidence_count: 3` is the legacy forecast path
  (`reason_CPI_inflation_pressure_down`, avg return +0.905964%, confidence
  0.600), NOT the W6 evidence items; do not conflate.
- The W7 provenance chain persisted in `finalize.json:91-134` starts at
  W7 CounterEvidenceAssessor — no W4/W5/W6 provenance propagates to
  finalize.json.