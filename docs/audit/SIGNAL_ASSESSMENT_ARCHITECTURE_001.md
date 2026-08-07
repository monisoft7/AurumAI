# SIGNAL_ASSESSMENT_ARCHITECTURE Audit 001

**Subject:** Complete architecture audit of SignalAssessment (Observation → Criteria → Classification), anchored on runtime `runtime_20260806_234356`.
**Scope:** Read-only. No code modified, nothing implemented.
**Date:** 2026-08-07
**Status:** FACTS ONLY. No recommendations.

---

## 1. Pipeline Topology (Observation → Criteria → Classification)

```
W3 pre_market_scan (stages.py:597)
  PreMarketBriefingAssembler.assemble (briefing_assembler.py:50)
    ├─ OvernightDataFetcher.fetch_all      → overnight_changes   (overnight_fetcher.py:139)
    ├─ OvernightNewsIngestion.ingest       → news_items          (news_ingestion.py:34)
    ├─ RiskReportGenerator.generate        → risk_snapshot       (risk_reporter.py:33)
    ├─ PositioningDataFetcher.fetch        → positioning_snapshot(positioning.py:24)
    ├─ AnomalyDetectionEngine.detect       → anomaly_flags       (anomaly_detector.py:39)
    └─ WatchlistBuilder.build              → watchlist           (watchlist_builder.py:29)
        │
        ▼
W5 signal_assessment (stages.py:436)
  SignalAssessmentAssembler.assemble (assembler.py:50)  → 4 observation branches:
    A. overnight changes (assembler.py:54-106)      → 5 criteria each
    B. positioning     (assembler.py:108-146)       → 5 criteria each
    C. anomaly flags   (assembler.py:148-175)       → 5 criteria each
    D. news items      (assembler.py:177-203)       → 5 criteria each
        │
        ▼
NoiseSignalClassifier.classify (classifier.py:30)  → label + confidence
        │
        ▼
W4 event_triage (tierer.py) → W6 evidence_collection (collector.py)
```

The 5 criteria are: **persistence, breadth, magnitude, narrative_fit, volume_flow**. Classification rule (classifier.py:51-79): Signal = ≥3 passed, or ≥2 passed with persistence; Weak Signal = ≥2 passed; Watch = 1 passed or |z|≥2.0; Noise/Ignore = 0 passed (split on |z| ≥/ < 0.5).

## 2. Data Producers Inventory (what actually exists in the codebase)

| Producer | Module | Real data source | Output |
|---|---|---|---|
| OvernightDataFetcher._compute_persistence_days | overnight_fetcher.py:124 | yfinance/FRED close series | `persistence_days` (consecutive same-sign returns) |
| OvernightDataFetcher._compute_sigma | overnight_fetcher.py:114 | yfinance/FRED close series | `change_sigma` (z-score of last return) |
| OvernightDataFetcher.fetch_overnight_changes | overnight_fetcher.py:43 | yfinance (6 tickers) + FRED (3 series) | 9 instruments |
| OvernightNewsIngestion.ingest | news_ingestion.py:34 | NewsCollector RSS feeds + NewsSentimentAnalyzer | `news_items` |
| PositioningDataFetcher._fetch_etf_flow | positioning.py:43 | yfinance GLD/IAUM Close+Volume | etf_flow_change_pct, etf_flow_momentum |
| PositioningDataFetcher._fetch_open_interest | positioning.py:72 | yfinance GC=F Volume | open_interest_change_pct |
| PositioningDataFetcher._fetch_cot | positioning.py:40 | **STUB** — hardcoded `{"z_score": 0.0, "regime": "neutral"}` | cot_z_score, cot_regime |
| PositioningDataFetcher._fetch_gofo | positioning.py:88 | **STUB** — hardcoded `{"rate": 0.0}` | gofo_rate |
| AnomalyDetectionEngine.detect (2σ/3σ) | anomaly_detector.py:49-67 | change_sigma | anomaly value = z-score |
| AnomalyDetectionEngine.detect (template/regime shift) | anomaly_detector.py:69-94 | change_pct pairs | anomaly value = **%-pt divergence** `|Δpct_left − Δpct_right|` |
| WatchlistBuilder.build | watchlist_builder.py:29 | static calendar lists | watchlist (not consumed by criteria) |

## 3. Criterion-by-Criterion Analysis

### 3.1 persistence

1. **Why it exists:** Gold-specific noise filters per Meth. §7 — COMEX 1w=noise/3w=signal, ETF 1d/2w, DXY 0.5%+5bp, etc. (persistence.py:5-10). Prevents single-day blips from acting as signals.
2. **Real data feed:** `OvernightPriceChange.persistence_days` from OvernightDataFetcher._compute_persistence_days (real yfinance/FRED data). Anomaly branch: **no feed** — hardcoded `CriterionScore(1.0, 0.5, True)` (assembler.py:150). Positioning branch: COT stub (always 0.0). News branch: hardcoded 0.0 (assembler.py:179).
3. **Can it become True at runtime?** Overnight: yes. Pass points (interpolated, persistence.py:48-67): DXY ≥ 2.5d; ETF-type instruments ≥ 10d; gold_real_yield ≥ 18d; XAU/USD (COMEX) ≥ 15d. Anomaly: always True by construction (can never be False). Positioning: no (COT stub).
4. **Expected frequency (derived from thresholds, not measured):** requires N consecutive same-sign daily returns ending on the last bar. DXY (~1 session in several), XAU/USD ≥15d (rare), yields/breakeven ≥18d (very rare). Observed in run: DXY 1d (False), XAU 3d (False), others 1-4d (all False).
5. **Runtime-limited or structurally unreachable?** Overnight: runtime-limited. Anomaly: structurally hardcoded True. Positioning: structurally unreachable (stub producer). News: structurally hardcoded False.
6. **% hardcoded:** 3/13 observations (anomalies — hardcoded True), 1/13 positioning (score constant 0.5 with stub-dependent pass), 0/13 news (branch unused). ≈ 31% of persistence slots non-data-driven in this run.
7. **Defaults to False with no producer?** News branch (0.0 hardcoded). Positioning (stub → effectively False).
8. **Producer exists but disconnected?** No — COT producer exists but is a stub (returns constants), not disconnected.

### 3.2 breadth

1. **Why it exists:** Requires confirmation by correlated instruments before a move is meaningful (Meth. §7 criterion 2; breadth.py:16-20).
2. **Real data feed:** `changes_dict` of all overnight change_pcts (assembler.py:55) → BreadthChecker.evaluate. **EXPECTED_RELATIONSHIPS defined only for XAU/USD and DXY** (breadth.py:5-8). Positioning: ETF flow change_pct (real). Anomaly: hardcoded 0.0 (assembler.py:152). News: hardcoded 0.0 (assembler.py:181).
3. **Can it become True at runtime?** Overnight: yes for XAU/USD (threshold 0.6) and DXY (0.5). **No for the other 7 instruments** — no relationship definitions → always "no correlated instruments available" → 0.0. Positioning: yes if |etf_flow_change_pct| > 1.0. Anomaly/news: never.
4. **Expected frequency:** for XAU/USD — all 3 expected relations must confirm at ≥60%; for DXY — ≥2 of 3 at ≥50%. In the observed run, XAU/USD breadth was 0/3 (all disconfirmed: gold co-moved with DXY and real yields, S&P fell) and DXY was 2/3 (True). Positioning: needs >1% daily ETF flow.
5. **Runtime-limited or structurally unreachable?** Structurally unreachable for 7/9 overnight instruments (no relationships defined). Anomaly: structurally hardcoded False. Positioning: runtime-limited.
6. **% hardcoded:** anomaly 3/13, news 0/13 (unused), positioning real. Structural (table gap) for 7/9 overnight.
7. **Defaults to False with no producer?** Anomaly branch (3), news branch (0 unused). Plus 7/9 overnight slots forced 0 by missing relationship entries (producer exists but no data definition).
8. **Producer exists but disconnected?** No.

### 3.3 magnitude

1. **Why it exists:** A move must exceed 2σ of its own recent return distribution to be material (assembler.py:66-72; classifier.py:55).
2. **Real data feed:** `change_sigma` from OvernightDataFetcher._compute_sigma (real). Anomaly: flag value (real, but %-pt divergence scale — see below). Positioning: COT z-score (stub 0.0). News: hardcoded 0.0 (assembler.py:182).
3. **Can it become True at runtime?** Overnight: yes, |z| ≥ 2.0. Anomaly: theoretically yes if divergence value ≥ 2.0 — **but the value is a %-pt divergence fed to a z-score threshold** (assembler.py:151); correlation-type values are typically small. Positioning: no (COT stub).
4. **Expected frequency:** threshold is 2σ; under a normal-return assumption ≈ 4.6% of sessions (2-sided). Observed: 0/9 overnight (max z=0.98), 0/3 anomalies (max 1.4782).
5. **Runtime-limited or structurally unreachable?** Overnight: runtime-limited. Anomaly: runtime-limited with scale mismatch (%-pt vs z-threshold). Positioning: structurally unreachable (stub).
6. **% hardcoded:** positioning 1/13 (stub). Anomaly values are real (detector) but mismatched scale.
7. **Defaults to False with no producer?** News branch (0.0 hardcoded), positioning (stub).
8. **Producer exists but disconnected?** No.

### 3.4 narrative_fit

1. **Why it exists:** A credible news narrative must explain the move (Meth. §7 criterion 4; narrative.py:21-25).
2. **Real data feed:** `news_headlines` from `briefing.news_items` (assembler.py:52,73-77) — produced by OvernightNewsIngestion/NewsCollector (RSS). In the observed run `news_items=()` → every narrative_fit = 0.0. Anomaly: hardcoded 0.0 (assembler.py:153). Positioning: hardcoded 0.0 (assembler.py:132). News branch: `relevance_score` (real, from sentiment analyzer).
3. **Can it become True at runtime?** Overnight: yes, if news exists with matching keywords (score ≥ 0.3; negligible moves < 0.1% auto-pass at 0.5). News branch: yes (relevance ≥ 0.3). Anomaly/positioning: never.
4. **Expected frequency:** whenever RSS news collection returns articles containing gold/inflation/fed/dxy/yield keywords. Producer connected but returned nothing in this run (empty `news_items`).
5. **Runtime-limited or structurally unreachable?** Overnight: runtime-limited (producer connected, empty this run). Anomaly/positioning: structurally hardcoded False.
6. **% hardcoded:** anomaly 3/13, positioning 1/13. ≈ 31% of slots in this run.
7. **Defaults to False with no producer?** Anomaly branch (3), positioning branch (1).
8. **Producer exists but disconnected?** No — news producer is wired into the overnight branch (assembler.py:73); it simply produced zero items in this run.

### 3.5 volume_flow

1. **Why it exists:** Price moves should be confirmed by volume spike, open-interest change, or ETF flows (Meth. §7 criterion 5; volume.py:9-14).
2. **Real data feed:** **For overnight observations: NONE.** The assembler calls `self._volume.evaluate(change_sigma=change.change_sigma)` passing **only change_sigma** (assembler.py:78-80) — no `volume_change_pct`, `open_interest_change_pct`, `etf_flow_change_pct`, or `etf_flow_momentum` → scorer returns 0.0 / "no volume/flow data available" (volume.py:62-69). Positioning: real ETF flow/OI/momentum passed (assembler.py:117-120). Anomaly: hardcoded 0.0 (assembler.py:154). News: `sentiment_confidence` as proxy (assembler.py:183).
3. **Can it become True at runtime?** Overnight: **NO — structurally impossible.** The producer data exists (PositioningDataFetcher._fetch_etf_flow, _fetch_open_interest) but is never passed into this branch. Positioning: yes (ETF flow >1%, OI >5%, or momentum accumulating/distributing — real yfinance data). Observed: etf_flow_change_pct=0.01% → False.
4. **Expected frequency:** positioning-only, whenever daily ETF flow exceeds 1%.
5. **Runtime-limited or structurally unreachable?** Overnight: **structurally unreachable (disconnected).** Anomaly: structurally hardcoded False. Positioning: runtime-limited.
6. **% hardcoded:** anomaly 3/13; overnight 9/13 forced default by disconnection (not hardcoded constants, but constant output).
7. **Defaults to False with no producer?** Anomaly branch (3). Overnight branch (9) — producer **exists** but is disconnected.
8. **Producer exists but disconnected?** **YES — the primary disconnect in the architecture:** `PositioningDataFetcher._fetch_etf_flow` (positioning.py:43) and `_fetch_open_interest` (positioning.py:72) produce ETF flow and OI data, but only the positioning branch consumes them; the 9 overnight observations never receive volume/OI/ETF arguments.

## 4. Hardcoded-Value Inventory (assembler.py constants)

| Location | Criterion | Fixed value | Branch |
|---|---|---|---|
| assembler.py:150 | persistence | 1.0 / passed=True | anomaly (all) |
| assembler.py:152 | breadth | 0.0 / passed=False | anomaly (all) |
| assembler.py:153 | narrative_fit | 0.0 / passed=False | anomaly (all) |
| assembler.py:154 | volume_flow | 0.0 / passed=False | anomaly (all) |
| assembler.py:179 | persistence | 0.0 / passed=False | news (all) |
| assembler.py:181 | breadth | 0.0 / passed=False | news (all) |
| assembler.py:182 | magnitude | 0.0 / passed=False | news (all) |
| assembler.py:110-116 | persistence score | 0.5 constant; pass = \|COT z\| ≥ 1.0 | positioning (stub feed) |
| assembler.py:132 | narrative_fit | 0.0 / passed=False | positioning |

Hardcoded slots in the observed run (13 observations × 5 = 65 criterion slots): anomaly 4×3=12, positioning narrative 1, positioning persistence (constant score, stub pass) 1 → **13-14 of 65 ≈ 20-22%** depend on hardcoded constants. Adding the disconnected overnight volume_flow (9 slots) and the breadth relationship-table gap (7 overnight instruments forced 0): **≈ 29 of 65 ≈ 45%** of scored criteria in this run cannot produce a data-driven True.

## 5. Criteria That Default to False Because No Producer Exists

| Criterion | Branch | Where forced |
|---|---|---|
| breadth | anomaly | assembler.py:152 (constant) |
| narrative_fit | anomaly | assembler.py:153 (constant) |
| volume_flow | anomaly | assembler.py:154 (constant) |
| narrative_fit | positioning | assembler.py:132 (constant) |
| persistence | news | assembler.py:179 (constant; branch unused this run) |
| breadth | news | assembler.py:181 (constant; branch unused) |
| magnitude | news | assembler.py:182 (constant; branch unused) |
| persistence | positioning | stub COT producer returns 0.0 (positioning.py:40-41) |
| magnitude | positioning | stub COT producer returns 0.0 |
| breadth | overnight (7/9 instruments) | missing EXPECTED_RELATIONSHIPS entries (breadth.py:5-8) |

## 6. Producers That Exist But Are Disconnected

| Producer | Data | Wired into | Not wired into |
|---|---|---|---|
| PositioningDataFetcher._fetch_etf_flow (positioning.py:43) | ETF flow % | positioning branch (assembler.py:117-120) | **overnight branch volume_flow (assembler.py:78-80)** |
| PositioningDataFetcher._fetch_open_interest (positioning.py:72) | OI % | positioning branch | **overnight branch volume_flow** |
| PositioningDataFetcher._fetch_cot (positioning.py:40) | COT z | positioning persistence/magnitude | **stub — no real data ever** |
| AnomalyDetectionEngine 2σ/3σ flags (anomaly_detector.py:49-67) | z-score anomalies | anomaly branch (would carry real z) | none (fires only when |z|≥2.0) |

## 7. Final Matrix

| Criterion | Producer | Runtime reachable | Structurally reachable | Current runtime value | Consumers |
|---|---|---|---|---|---|
| persistence | OvernightDataFetcher (real); COT stub (positioning); none (anomaly/news) | Yes (overnight: DXY ≥2.5d, COMEX ≥15d); No (positioning stub); anomaly always True | Yes (overnight); No (positioning); hardcoded True (anomaly) | overnight 0.13-1.0 (all False); anomaly 1.0/True; positioning 0.5/False | classifier (Signal branch: ≥2 + persistence), collector supporting ids |
| breadth | BreadthChecker over overnight changes (real); ETF flow (positioning, real); none (anomaly/news) | Yes for XAU/USD & DXY only; No for 7 instruments; No (anomaly/news) | Yes (2/9 overnight); No (7/9, table gap); hardcoded False (anomaly) | DXY 0.6667/True; XAU 0.0; others 0.0; positioning 0.0 | classifier positive_count, collector supporting ids |
| magnitude | change_sigma (real); anomaly flag value (real, %-pt vs z-threshold); COT stub (positioning); none (news) | Yes (overnight \|z\|≥2.0); theoretical (anomaly ≥2.0 %-pt); No (positioning) | Yes (overnight); Yes-in-principle (anomaly, scale mismatch); No (positioning) | overnight 0.067-0.328 (all False); anomaly 0.28-0.49 (all False); positioning 0.0 | classifier positive_count + Watch via magnitude_passed, tierer price_impact/trigger, collector ids |
| narrative_fit | OvernightNewsIngestion→NewsCollector (real, connected); relevance_score (news branch, real); none (anomaly/positioning) | Yes if news present (empty this run); No (anomaly/positioning) | Yes (overnight, news); hardcoded False (anomaly/positioning) | 0.0 everywhere (news_items=()) | classifier positive_count, collector ids |
| volume_flow | PositioningDataFetcher ETF/OI (real) — **disconnected from overnight branch**; sentiment_confidence proxy (news); none (anomaly) | Yes (positioning only); **No (overnight — never receives args)**; No (anomaly) | Yes (positioning); **No (overnight — structural)**; hardcoded False (anomaly) | 0.0 everywhere (overnight "no volume/flow data available"; ETF flow 0.01% < 1%) | classifier positive_count, collector ids |

## 8. Coverage Calculation

**Definition:** Coverage % = (criterion slots with a real producer feeding data) / (total criterion slots), for the observed run (13 observations × 5 criteria = 65 slots).

- Overnight (9 obs × 5 = 45 slots): persistence 9 (real), breadth 9 (real feed, 7 structurally zeroed by table gap), magnitude 9 (real), narrative 9 (connected, empty this run), volume 0 (disconnected) → **36**
- Anomaly (3 obs × 5 = 15 slots): magnitude 3 (real flag values) → **3** (persistence/breadth/narrative/volume hardcoded)
- Positioning (1 obs × 5 = 5 slots): breadth 1 (ETF flow), volume 1 (ETF flow/OI) → **2** (persistence/magnitude on COT stub, narrative hardcoded)
- News: branch unused in this run (0 observations)

**Coverage = 41 / 65 = 63.1%** (producers exist and are connected).

Stricter variant — producers that can actually produce a True (excluding breadth table-gap instruments and empty-but-connected narrative): **34 / 65 = 52.3%**.

Per-criterion coverage (producer connected): persistence 9/13 = 69.2%; breadth 10/13 = 76.9%; magnitude 12/13 = 92.3%; narrative 9/13 = 69.2%; volume_flow 2/13 = **15.4%** (lowest — overnight branch never receives volume data).
