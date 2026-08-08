# SIGNAL_ASSESSMENT_CORRECTION_AUDIT 001

**Subject:** Why SignalAssessment has ~63.1% producer coverage, which missing/disconnected
criteria materially reduce institutional evidence quality, and what the smallest
correction boundary is. Follow-up to `SIGNAL_ASSESSMENT_ARCHITECTURE_001`.
**Scope:** Read-only audit + design. No source, config, or test changes.
**Date:** 2026-08-08
**Status:** VERIFIED AGAINST CURRENT TREE. Each finding cites the code location it
was verified at. Runtime facts are cited from the persisted checkpoints of
`runtime_20260806_234356` (`%TEMP%\aurumai_checkpoints\...\pre_market_scan.json`,
`signal_assessment.json`, `evidence_collection.json`, `event_triage.json`,
`evidence_reasoning.json`, `finalize.json`).

---

## §1 Executive finding

The 63.1% producer-coverage figure (41 of 65 criterion slots in the audited run) is
arithmetically correct and reproducibly so: 9 overnight observations × 5 criteria +
3 anomaly × 5 + 1 positioning × 5 = 65 slots, of which exactly 41 are fed by a
connected, data-producing source. Verification below re-derives all counts from the
persisted checkpoints.

The 63.1% does **not** mean the classifier is broken. The classifier decision rules
(`classifier.py:51-79`) and all 5 criterion scorers are correct, and the four corrections designed in
`docs/design/EVIDENCE_FILTERING_V2.md` (C1–C4) are **already implemented in the
current tree** and verified as wired (overnight z-scores with a 10-bar window,
data-driven positioning breadth, real persistence with per-instrument types,
corrected USD/JPY bias). The remaining gap decomposes exactly as:

| Uncovered-slots cause | Slots (of 65) | Category (§4) | Justification |
|---|---|---|---|
| Overnight branch `volume_flow` never receives volume/OI/ETF inputs | 9 | A — implemented but not wired | **unjustified loss; correction candidate #1** |
| Anomaly `persistence` hardcoded True, `breadth`/`narrative_fit`/`volume_flow` hardcoded False | 12 | D — intentionally unavailable | anomalies carry no extra data; `persistence=True` is a deliberate minimum floor |
| Positioning `persistence`/`magnitude` on COT stub (always z=0) | 2 | B placeholder / C dependent | genuine COT data absent from repo; No TRADE-impacting this run |
| Positioning `narrative_fit` hardcoded False | 1 | D — no producer for event | acceptable by design (no "narrative" input plausibly related) |
| News branch criteria unused (branch unused this run) | 0 active slots | D / runtime-availability | news_items=() at runtime; connected producers exist inline |

So of the 24 uncovered slots, roughly **9 are objectively unjustified
institutional-information loss** (the overnight volume_flow disconnect), ~12 are
intentional constants with no available data (anomaly slots), ~2 more wait for a real
COT producer, and the remainder are by-design-only (news text criteria, positioning
narrative). The breadth table gap (7 instruments forced 0.0 by missing
`EXPECTED_RELATIONSHIPS` entries) is a **config table gap**, not a data-producer gap:
the producer (changes_dict feed) is connected; what is missing is relationship
definitions. It raises breadth only for XAU/USD and DXY-adjacent instruments.

Correcting the overnight volume_flow wiring raises producer coverage from
41/65 (63.1%) to 50/65 (76.9%) and, in the audited run, restores a real volume/flow
criterion only for gold-type instruments — no evidence weighting, thesis, confidence,
or decision arithmetic is touched.

---

## §2 Current SignalAssessment execution path (verified)

```
raw observation (run edition: 9 OvernightPriceChange, 3 AnomalyFlag, 1 PositioningSnapshot, 0 NewsItem)
  └─ PreMarketBriefingAssembler.assemble (pre-mkt/briefing_assembler.py:50-94)
        ├─ OvernightDataFetcher.fetch_all   (overnight_fetcher.py:139-142; lookback_days=10 verified)
        ├─ OvernightNewsIngestion.ingest    (news_ingestion.py:34-60) → () this run
        ├─ RiskReportGenerator.generate     (risk_reporter.py)
        ├─ PositioningDataFetcher.fetch     (positioning.py:24-38) → COT 0.0/neutral, GLD+IAUM "flow" 0.01,
        │                                    OI 0.0, GOFO 0.0 (verified pre_market_scan.json)
        ├─ AnomalyDetectionEngine.detect    (anomaly_detector.py:39-96) → 3 flags (2 template + 1 correlation)
        └─ WatchlistBuilder.build           (watchlist_builder.py)
  ──► SignalAssessmentAssembler.assemble (signal_assessment/assembler.py:50-213)
        ├─ Branch A: 9 overnight obs × 5 criteria (assembler.py:53-106)  [persistence real, breadth table, magnitude real, narrative connected-empty, volume disconnected]
        ├─ Branch B: 1 positioning obs × 5 (assembler.py:110-146)         [persistence COT stub, breadth data-driven, magnitude COT stub, narrative constant, volume ETF close-proxy]
        ├─ Branch C: 3 anomaly obs × 5 (assembler.py:148-175)             [persistence const True; breadth/narrative/volume const False; magnitude from flag value]
        └─ Branch D: news obs × 5 (assembler.py:177-203)                 [not instantiated this run; persistence/breadth/magnitude const 0, narrative relevance, volume sentiment proxy]
  └─► NoiseSignalClassifier.classify (classifier.py:30-79) → largest-grade DXY Watch, 3 anomalies Watch, 8 overnight Noise/Ignore, positioning Ignored
  └─► W4 event_triage (tierer.py:85-139): DXY→Tier 1 via regime_relevance>0.8 → monitoring continuous
  └─► W6 EvidenceCollector (evidence_collection/collector.py:76-177): 4 items kept (Watch only), 3 after dedup; composite = 0.3×0.6=0.18
  └─► EvidenceReasoner (reasoner/grouper/weighter): es_usd_fx net_weight 0.4601, es_general 0.4323 (duplicates_removed=1)
  └─► W7 CounterEvidence → W8 Thesis → W9 Confidence (0.0325) → W12 Risk/Reward → W13/DecisionEngine: NO_TRADE composite 0.3016
  (trace numbers verified against evidence_reasoning.json/finalize.json)

## §3. Complete 5-criterion inventory (per branch with current input)

Legend: input = value actually passed into the scorer; class =
Real | Derived | Fallback | Synthetic/Hardcoded | Proxy.

### 3.1 persistence (producers @ overnight_fetcher.py:123-137 → assembler.py:56-60; scorer persistence.py)

| Branch | Producer | Consumer | Current input | Class | True-in-prod? | Disconnected? | Runtime-limited? |
|---|---|---|---|---|---|---|---|
| overnight ×9 | `_compute_persistence_days` (real yfinance/FRED series) | PersistenceTracker | `persistence_days`, instrument type via `PERSISTENCE_TYPE_BY_INSTRUMENT` (assembler.py:15-24) | Real | Yes (DXY needs ≥2.5d, COMEX ≥15d, yield ≥18d; observed max 4d) | No | Yes |
| positioning ×1 | `_fetch_cot` stub returns 0.0 (positioning.py:40-41) | assembler.py:110-115 | `abs(cot_z_score)>=1.0` → 0.0 (always) | Synthetic (stub) | **No** | N/A (stub producer) | Irrelevant — producer placeholder |
| anomaly ×3 | — | assembler.py:150 | const `(1.0, 0.5, True)` | Hardcoded | Trivially True always | N/A | Constant |
| news ×0 (unused) | — | assembler.py:179 | const `(0.0, 0.5, False)` | Hardcoded | No (impossible for text) | N/A | Constant |

### 3.2 breadth (producers @ BreadthChecker; assembler.py:61-65)

| Branch | Producer | Consumer | Current input | Class | True-in-prod? | Disconnected? | Runtime-limited? |
|---|---|---|---|---|---|---|---|
| overnight ×9 | `changes_dict` (real) → EXPECTED_RELATIONSHIPS (breadth.py:5-8) | BreadthChecker.evaluate | changes_map | Real | Only XAU/USD (threshold 0.6) and DXY (0.5). For the other 7 instruments `relationships={}` → "no correlated instruments available" → 0.0 (verified in run for S&P 500 Futures) | Table gap (config), not data disconnect | For the 2 defined instruments: runtime-limited |
| positioning ×1 | PositioningDataFetcher._fetch_etf_flow (positioning.py:43-70) | assembler.py:124-130 | `abs(etf_flow_change_pct)>1.0` (observed 0.01 → False) | Derived (close-price proxy × ETF sum) | possible >1%/day flow | No | Yes |
| anomaly/news | — | assembler.py:152,181 | 0.0 const | Hardcoded | No | N/A (constants) | Always False |

### 3.3 magnitude (producers: change_sigma, COT stub, anomaly flag value)

| Branch | Producer | Consumer | Input | Class | True-in-prod? | Structural note |
|---|---|---|---|---|---|---|
| overnight ×9 | `_compute_sigma` (real; lookback 10d) | assembler.py:66-72 | `abs(z)>=2.0` real z | Real | Yes (observed max 0.9846 — none passed) |
| positioning | COT stub | assembler.py:131 | `abs(cot_z)>=2.0` → 0.0 | Synthetic | No (stub) | same stub |
| anomaly ×3 | detector values: z ≥2 flags; template/correlation divergence (percentage-point) | assembler.py:151 | `abs(value)>=2.0`; observed 0.98/0.83/1.48 → all False | Real | Yes for z-flags (true z ≥2) | **scale mismatch**: template/correlation flags feed a %-pt divergence into a z-threshold — passable only if divergence ≥ 2.0 pp (rare) |
| news ×1 | — | assembler.py:182 | 0.0 const | Hardcoded | No | text item — no move data |

### 3.4 narrative_fit

| Branch | Producer | Consumer | Input | Class | True? | Notes |
|---|---|---|---|---|---|---|
| overnight ×9 | OvernightNewsIngestion/NewsCollector (news_ingestion.py:34-60; real RSS) | assembler.py:73-77 | `news_headlines` — empty this run → "no news headlines available" | Real / connected | Yes when news present (0.3 threshold), incl. negligible-move auto-pass (narrative.py:43-50) | Runtime-limited |
| anomaly/positioning ×3/×1 | — | assembler.py:132,152 | const 0.0 | Hardcoded | No | No suitable input channel |
| news | `relevance_score` (from sentiment analyzer, real) | assembler.py:180 | `relevance_score>=0.3` | Real | Yes | branch unused this run |

### 3.5 volume_flow

| Branch | Producer | Input | Class | True? | Notes |
|---|---|---|---|---|---|
| overnight ×9 | **PositioningDataFetcher._fetch_etf_flow / _fetch_open_interest** (real yfinance data exists) | assembler.py:78-80 passes **only `change_sigma`** → scorer volume.py:62-69 → "no volume/flow data available" | Fallback (0.0) | **No — structurally disconnected** | **THE primary actionable gap** |
| positioning ×1 | `_fetch_etf_flow` (proxy close change) + `_fetch_open_interest` (broken, always 0) | assembler.py:117-120: passes etf_flow change/momentum; OI never passed | Real (proxy) / Broken OI | possible via ETF flow >1% & accumulating; observed 0.01 → False | `momentum="stable"` this run |
| anomaly ×3 | — | assembler.py:154 | 0.0 const | Hardcoded | No | Constant |
| news ×1 | sentiment_confidence (real sentiment) | assembler.py:183 | `sentiment_confidence>=0.5` | **Proxy** (not volume/flow — semi-derived) | branch unused | semantic mismatch — sentiment as volume |

## §4. Producer / connectivity classification (A/B/C/D)

| Item | Evidence | Would fix which loss | Category |
|---|---|---|---|
| ETF flow + OI producer data exists (positioning.py:43-70, :72-89) but is only ever passed to one branch | assembler.py:78 call site; run volume_flow 0.0 "no volume/flow data available" | overnight ×9 volume slots — objective loss | **A — implemented but not wired** |
| OI producer broken by dead code (`prev_oi`/`curr_oi` assigned only inside the `len<2` early-return path → NameError for `len>=2`; positioning.py:78-83) | always returns 0.0; verified in run (`open_interest_change_pct=0.0`) | positioning volume confirmation | **B — placeholder/broken** |
| COT stub (positioning.py:40-41) — real COT data is NOT in the repo (no connector, no file, no CFTC source under src/, data/, scripts/) | grep over repo; only CFI knowledge contracts mention COT fields (knowledge/cfi/contracts.py) | positioning persistence+magnitude | **C — genuinely missing new data producer** |
| GOFO stub (positioning.py:87-89) | **no consumer**: assembler never reads `gofo_rate` (verified) | none | **D — intentionally inert; zero consumers; keep** |
| Exchange volume column present in yfinance fetches but dropped | overnight_fetcher.py:93-97 uses only Close; run.log shows OHLCV fetched | overnight volume (alternative to A) | **A** variant — fetch-internal data not exposed (needs a contract field) → medium cost; keep boundary |
| Breadth relationships table incomplete (breadth.py:5-8 only XAU/USD, DXY) | run shows "no correlated instruments available" for the other 7 | breadth for 7 overnight instruments | **A — data-table gap (config, not producer)** |
| Anomaly criteria constants and magnitude scale mismatch | assembler.py:148-175 | — | **D (design)**, noted §5 |
| News criteria constants | assembler.py:177-203 | news text dummies | **D — text items; by-design; leave** |

## §5 Structural vs data-availability gaps

| Gap | Structural or data-availability? |
|---|---|
| Overnight `volume_flow` 0.0 | **Structural** (wiring absent; no data could reach the scorer) |
| ETF/OI not connected to overnight branch (positioning-only) | Structural wiring |
| OI producer returns 0 always | **Structural bug** (dead code), not absence of data — fixable without new data |
| COT persistence/magnitude | **Structural placeholder** (C: no real producer in repo) |
| Breadth relationships for the 7 non-defined instruments | **Structural table gap** (data definitions, not data feed) |
| Anomaly `breadth`/`narrative`/`volume` = 0 | Structural by design (no compatible event-data exists); D, not A/B/C |
| Overnight `narrative_fit` = 0.0 | **Data-availability** — producer path (RSS) connected; zero items at runtime |
| News branch unused | **Data-availability** only (producer connected; empty RSS that night) |

## §6 Downstream decision impact

Complete chain (cite collector.py:88-104 → evidence_reasoning/weighter.py:37-51 →
thesis_construction/builder.py:41-99 → confidence_engine — verified values in §2
above):

For each *institutionally unjustified* gap:

1. **Overnight volume_flow (9 slots):** on days where gold surges and ETF flow/OI
   would confirm the move, `volume_flow` cannot pass — for XAU/USD this reduces
   `positive_count` by 1, moving boundaries: SIGNAL (≥3 or ≥2+persistence) becomes
   one criterion harder, WEAK_SIGNAL (≥2) becomes WATCH, WATCH (1) becomes
   NOISE/IGNORE. This is equivalent to knowingly discarding an existing, fetched,
   real-flow confirmation channel. It had no effect on this run's outcome (observed
   flow 0.01%, below the 1% threshold anyway), but it reliably degrades institutional
   evidence quality on genuine flow days.
2. **Breadth table gap (7 instruments):** "no correlated instruments available" is an
   accurate non-verdict; the cost is that those instruments' breadth can never
   confirm, so e.g. EUR/USD can never contribute breadth to its own or a gold
   observation via defined relationships. Minor, config-only.
3. **COT stub:** positioning can only reach WATCH via breadth+volume; persistence and
   magnitude are structurally unreachable. In this run the positioning observation
   was IGNORE (0 positives) — a correct withholding given the stub data, not a loss.
   Real COT would be the single largest institutional enhancement (category C) but
   requires a producer that does not exist in the repo.
4. **Duplicate anomaly evidence:** two distinct template violations (gold-DXY,
   gold-real-yield) collide on `observation_id` (`obs_anomaly_XAU/USD_template_violation`),
   hence produce the same `evidence_id`, hence 1 is deduped — the *distinct
   institutional fact* "gold/real-yield co-move" never reaches any reasoning channel.
   Small but **objective and cheap to fix** (identity key should include the paired
   instrument / description, e.g. the template pair).
5. **Not a loss — anomaly magnitude scale:** feeding %-pt divergence into a z-threshold
   makes template anomalies structurally unable to pass magnitude, capping them at
   WATCH vs possible SIGNAL on ≥2.0 %-pt divergence. Design decision, no information
   lost (the anomaly fact still reaches the pipeline as WATCH). Leave under D.

Impact ladder (this audit run): Watch-only collection → base_confidence 0.3,
composite 0.18 × regime 0.6 → net set weights 0.4601/0.4323 → thesis support
0.138 → confidence 0.0325 → NO_TRADE. None of these arithmetic steps is defective;
they inherit the restricted criterion pool above. Any correction changes only
inputs; the formulas downstream never change.

## §7 Tests & regression coverage

Tests that protect correct behavior:
- `test_persistence_uses_real_days`, `test_signal_reachable_with_persistent_move`,
  `test_one_day_noise_remains_watch` — pin C3 (real persistence days,
  per-instrument types) in test_signal_assessment.py.
- `test_positioning_genuine_etf_flow_not_ignored` and
  `test_positioning_stub_classified_ignore` — pin C2 (data-driven positioning
  breadth; stub data → IGNORE, real flow → survives).
- `TestBreadthChecker` (confirm / violation / no-correlated-instruments),
  `TestNarrativeFitScorer` (matches / no match / no headlines / negligible move),
  `TestVolumeFlowConfirmator` (notably `test_no_data_returns_not_passed` — the 0.0
  fallback when no data is passed is the correct, intended behavior),
  `TestNoiseSignalClassifier` (full 5-rule decision matrix),
  `test_w3_to_w4_integration`, `test_w4_to_w5_integration` (test_evidence_collection.py),
  `test_w5_no_noise_in_evidence` — protect the W6 keep/drop boundary
  (Signal/Weak/Watch kept; Noise/Ignore dropped).

Gaps: no test currently encodes the anomaly constants or the overnight volume
disconnect as intentional, which is precisely why the disconnect shipped unnoticed —
the suite tests scorer contracts, not branch wiring. Missing regression tests
(design list for any eventual correction):
- T1 Overnight branch volume_flow wiring: assert `VolumeFlowConfirmator` receives
  `etf_flow_change_pct` / `open_interest_change_pct` / momentum for gold-class
  instruments (currently untested → disconnect invisible).
- T2 OI producer returns nonzero when volume data is present (unit, mocked yfinance).
- T3 Breadth for non-XAU/DXY instruments (e.g. EUR/USD↔DXY relationship once defined).
- T4 Template violations get distinct observation_ids (identity fix guard).
- T5 Anomaly magnitude scale: %-pt divergence vs z-score flag semantics marker.

## §8 Ranked correction candidates (impact × implementation cost)

Rank = products of institutional relevance (see §6) and elapsed cost within existing
architecture:

| # | Candidate | Category (§4) | Expected impact | Cost | Risk |
|---|---|---|---|---|---|
| 1 | Wire existing ETF/OI data into the overnight `volume_flow` call for gold-class instruments (reuse `VolumeFlowConfirmator.evaluate(...)` args; strictly additive, no contract change) | A | +9 slots covered (63.1%→76.9%); restores the real confirmation channel; enables an additional positive for XAU/USD SIGNAL paths | very low (1 call site) | minimal; note the ETF input itself is currently a close-price proxy (see #6) |
| 2 | Repair `_fetch_open_interest` dead code so OI reaches the evaluator (positioning branch) | B | positioning volume_flow can confirm via real OI | low (1 block) | low |
| 3 | Extend `EXPECTED_RELATIONSHIPS` for the 7 bare instruments (only relationships derivable from the existing methodology text and the XAU/USD/DXY table, e.g. EUR/USD↔DXY inverse) | A | breadth becomes meaningful for those instruments | low (config/table data) | low (data only); must not invent relationships beyond documented reasoning |
| 4 | Fix anomaly observation identity (include the paired instrument / template key in `observation_id`) | A | prevents loss of a distinct fact when two template violations fire the same night | very low | low |
| 5 | Real COT persistence/magnitude (new CFTC data source + fetcher; NOT in repo) | C | largest prospective upgrade (positioning weight path) | **high** (new external producer) | medium — out of scope for a "smallest correction" pass unless commissioned |
| 6 | Honest ETF flow (GLD+IAUM "close-sum" → real flow/shares-based) | B | makes "ETF flow" semantically honest | medium (different data source) | — |

Non-considered: anomaly + news criteria constants (D), GOFO (D, zero consumers),
COT exists (C — needs a new producer, see #5).

The minimal, justified, architecture-locked bundle for a "smallest correction" is
**items 1+2+4**, optionally 3 — all reuse data already fetched each run; none grows
the 5-criterion model, classifier, thresholds, Evidence/Thesis/Confidence/Decision,
KnowledgeGraph, or W4/W6 logic.

## §9 Smallest correction boundary

Given the frozen architecture (no W5, W6 redesign; no KG responsibilities; no
changes to DecisionEngine/ConfidenceEngine, or contract semantics):

- Allowed: pass data already on the *existing* `PositioningSnapshot` (already inside
  `PreMarketBriefing.positioning_snapshot`) and/or already-fetched yfinance rows into
  the **existing `VolumeFlowConfirmator.evaluate()` arguments**; such calls are
  wiring, not a behavior change to the scorer.
- Allowed: make `_fetch_open_interest` not return 0 from dead logic (code repair,
  same signature/contract — `{change_pct}`).
- Allowed: additive rows in `breadth.py:EXPECTED_RELATIONSHIPS` (+ optional
  `BREADTH_THRESHOLDS`) — table data, not classification logic.
- Allowed: change `observation_id` construction for the anomaly branch (identity fix;
  no observation/class semantics change).
- Allowed: test additions (T1-T5) as regression guards when corrections land.
- NOT allowed: any change to `classifier.py` rules/thresholds, `CriterionScore`
  semantics, `Evidence`/`composite_weight` formula, `EvidenceSet` weights, thesis/
  confidence/decision driver weights, regime handling in the assembler, W3 briefing
  topology, KnowledgeGraph responsibilities, and — repeated — no new data producer
  classes unless the repository already contains them.

## §10 Explicit non-goals

1. Increase Signal/Watch counts for their own sake. The objective is classification
   quality: every correction here *reconnects existing data into an existing scorer*,
   not a "produce more signals" capability.
2. Rebalance the Meth. §7 noise/signal day thresholds (COMEX 7/21, ETF 1/14, DXY 1/5,
   gold_real_yield 1/30) — frozen filters.
3. Move KnowledgeGraph responsibilities (CFI contracts — `GoldPositioningDashboard`,
   `ETFFlowMonitor` — and their adapters) into SignalAssessment: they are
   knowledge-layer contracts, not data producers; no new wiring to CFI.
4. Adjust DecisionEngine / ConfidenceEngine / RiskReward validation or their
   thresholds and weighting formulas.
5. Fix the anomaly/news criterion constants (field types without meaningful data;
   D-classified).
6. Invent data sources: no new sources unless the repository already contains them
   (candidate #5, real COT, is therefore a proposal, not a "smallest correction").
7. Re-plumb the news pipeline: any news-branch improvement would be additive wiring
   of the existing feed + narrative intent, *if ever required* — not part of this
   minimal set.

---

### Appendix: Coverage math re-derivation (verified)

- Overnight (9 obs × 5 = 45 slots): persistence 9 (real), breadth 9 (producer
  connected; 7 table-gapped to 0.0), magnitude 9 (real), narrative 9 (connected,
  empty this run), volume 0 (never called) → **36**.
- Anomaly (3 obs × 5 = 15 slots): magnitude 3 (real flag values; scale caveat aside);
  the other 12 are constants → **3**.
- Positioning (1 obs × 5 = 5 slots): breadth 1 (real but close-price proxy) +
  volume 1 (same) → **2**.
- News: branch uninstantiated this run → 0.
- **Total = 41 / 65 = 63.1%.** Stricter variant — producers that can actually
  produce a True (excluding the breadth table-gap instruments and the
  empty-but-connected narrative): **34 / 65 = 52.3%** (per
  SIGNAL_ASSESSMENT_ARCHITECTURE_001 §8, re-derived and confirmed).