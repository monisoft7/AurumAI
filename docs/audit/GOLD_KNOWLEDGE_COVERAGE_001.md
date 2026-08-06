# GOLD_KNOWLEDGE_COVERAGE_001 — institutional knowledge coverage for Gold (XAU/USD)

Read-only audit. No code or test modified. Facts only; no fixes; no recommendations.

## 1. Scope

- Target: latest successful runtime `runtime_20260805_102841`
  (`outputs/2026-08-05/runtime_20260805_102841`, exit 0, 25/25 stages ok,
  `summary.json`, `stages.json`).
- Asset: XAU/USD. Event type: CPI (`summary.json:4`).
- Method: for each institutional signal category, (a) inventory the
  implementation in `src/`, (b) determine whether the signal entered this
  runtime (persisted artifacts: `finalize.json`, `artifacts/knowledge.json`,
  `artifacts/lessons.csv`, `run.log`).
- Read-only constraint: no code or test was modified.

## 2. What this runtime actually used (baseline facts)

Persisted inputs for the decision (`finalize.json`):
- Decision `NO_TRADE` (`finalize.json:24`), institutional_confidence `0.2012`
  (`finalize.json:65`), composite_score `0.4327` (`finalize.json:80`).
- Decision drivers (`finalize.json:25-62`): institutional_confidence 0.2012,
  risk_reward_quality 0.6623, evidence_quality 0.5656,
  counter_evidence_quality 0.7, scenario_probability 0.5, regime_alignment 0.0.
- Selected thesis: bearish (`finalize.json:82`), scenario bull p=0.1684
  (`finalize.json:63`).
- Knowledge records (`artifacts/knowledge.json:7`): 6 records, all
  event_type CPI, all asset XAU/USD; conditions `cpi_pressure`
  down (16 lessons) / up (111 lessons), horizons 1/5/20; confidences
  0.5208–0.6384 (`knowledge.json:10,55,95,123,140,267,404,425,543,560`).
- Lessons (`artifacts/lessons.csv`): 127 rows, event_type CPI only;
  macro_regime values LATE_CYCLE (59), RECOVERY (28), CONTRACTION (23),
  EXPANSION (17).
- Overnight fetches in `run.log`: GC=F, DX-Y.NYB, ES=F, BZ=F, EURUSD=X,
  USDJPY=X (range=10d/1d), GLD, IAUM (range=5d/1d).
- News: `news_confidence 0.0`, `news_mood null`, `recent_events []`
  (`finalize.json:15-19`); no headline text anywhere in artifacts.
- Anomaly flags: none in artifacts.
- The only named evidence set in `finalize.json` is `es_usd_fx`, appearing
  only in `invalidation_conditions` ("Counter-evidence from sets es_usd_fx
  strengthens", `finalize.json:67`).

## 3. Category register

Status legend: implemented / partially implemented / placeholder / missing.
For each implemented or partial item: used-in-this-runtime = yes/no + why not.

### 3.1 Inflation — partially implemented (used: yes, CPI only)

Implemented:
- CPI/PPI FRED series (`src/connectors/fred_client.py:107-108`), cached CSVs
  `data/economic/CPIAUCSL.csv`, `PPIACO.csv`; composite score
  (`src/knowledge/regime/composite_score.py:21-35`) runs in
  `src/orchestration/stages.py:32` (`CompositeScoreBuilder().build()`).
- CPI/PPI lesson builders registered (`src/knowledge/events/__init__.py:43-49`)
  and executed via `_ingest_event` (`stages.py:40-53`).
- Breakeven inflation T5YIE configured in overnight fetch
  (`src/pre_market/overnight_fetcher.py:24`) and in regime indicator weights
  (`indicator_hierarchy.py:37,55`).

Used in this runtime: yes — CPI is the configured event; 6 CPI knowledge
records fed the thesis (see §2). PPI, composite CPI input to regime detection
(`stages.py:32-33`).
Not used in this runtime: breakeven inflation (T5YIE) — no T5YIE value
appears in `finalize.json`, `knowledge.json`, or `lessons.csv`; regime
detection consumed the 5-series composite, not BEI.

### 3.2 Interest Rates — partially implemented (used: yes, indirect only)

Implemented:
- FEDFUNDS/DFF/DGS10 in `fred_client.py:112-114`; DGS10 (US10Y Nominal
  Yield) in overnight fetch (`overnight_fetcher.py:23`).
- FOMC + INTEREST_RATE event classes registered
  (`events/__init__.py:43-49`); FOMC calendar connector exists
  (`src/connectors/fomc_calendar.py:47`).
- SOFR/LIBOR: zero hits in `src/`.

Used in this runtime: no direct value. No DGS10/FEDFUNDS/DFF value appears in
any artifact. The `_ingest_news` stage's FOMC fetch is dead:
`fomc.fetch()` does not exist on `FOMCCalendarConnector` — AttributeError
swallowed (`stages.py:71-77`), so `fomc_events` is always `[]`.
Why not: `_ingest_event` loads only the configured CPI event; the FOMC
calendar call is broken; `fomc_confidence 0.0` (`finalize.json:15`).

### 3.3 Real Yields — partially implemented (not used in runtime)

Implemented:
- DFII10 (US10Y Real Yield) in overnight fetch (`overnight_fetcher.py:22`);
  `RealYieldFetcher` (`src/connectors/real_yield_fetcher.py:10`);
  `RealYieldAdapter` (`src/knowledge/factors/adapters/real_yield_adapter.py:25`);
  `gold_rule_001.apply(real_yield, dxy)` (`src/knowledge/reasoning/rules/gold_rule_001.py`).
- Not wired: `RealYieldFetcher` is referenced only in its own file and a
  docstring in `dxy_fetcher.py:12`; `RealYieldAdapter` and `gold_rule_001`
  are never instantiated/called anywhere in `src/`.

Used in this runtime: no. No DFII10 value in any artifact; `yield_data_path:
null` in `config.json` (run config). Why not: real-yield consumers are not
invoked from the pipeline; the config passes no yield data path.

### 3.4 USD — partially implemented (used: yes, pre-market only)

Implemented:
- DXY fetched live via yfinance DX-Y.NYB (`overnight_fetcher.py:14`);
  committed DXY history `data/context/dxy/dxy.csv`; gold–DXY co-move anomaly
  template (`src/pre_market/anomaly_detector.py:9-13`); DXY news topic
  (`src/news/models.py:14,42-44`).
- Not wired: `DXYFetcher` (`dxy_fetcher.py:7` — imported unused at
  `overnight_fetcher.py:8`); `DXYContextEnricher` (`src/knowledge/context/dxy.py:18`)
  not imported by `src/knowledge/pipeline/pipeline.py` (only
  `YieldContextEnricher` at `pipeline.py:17`).

Used in this runtime: partial. DX-Y.NYB fetched (`run.log`), and `es_usd_fx`
appears as a counter-evidence invalidation set (`finalize.json:67`). No DXY
value is persisted in `knowledge.json`/`lessons.csv`; the DXY context
enricher (which would make DXY an explicit knowledge input) does not run.

### 3.5 ETF Flows — partially implemented (used: yes, pre-market only)

Implemented:
- GLD/IAUM close-price 5-day change as flow proxy
  (`src/pre_market/positioning.py:43-70`), consumed in
  `signal_assessment/assembler.py` breadth and `volume.py:50-59`.
- `ETFFlowMonitor` contract (`src/knowledge/cfi/contracts.py:62-72`) +
  adapter (`cfi/adapter.py:10-31`); consumed only if
  `OrchestrationContext.cfi_etf_flows` is populated — nothing populates it.

Used in this runtime: partial. GLD + IAUM fetched (`run.log`); the ETF-flow
proxy feeds positioning breadth in signal assessment. No ETF flow value is
persisted in `knowledge.json`/`lessons.csv`; the CFI contract path never runs.

### 3.6 COT Positioning — placeholder (not used in runtime)

Implemented:
- `_fetch_cot()` returns hard-coded `{"z_score": 0.0, "regime": "neutral"}`
  (`positioning.py:40-41`). No CFTC commitments-of-traders fetch exists
  anywhere in `src/`.
- `open_interest_change_pct` always 0.0: `_fetch_open_interest` returns
  `{"change_pct": 0.0}` before computing OI (`positioning.py:77-79`);
  `_compute_sigma`-style OI lines are dead code.
- `comex_managed_money_zscore` appears only as indicator names/weights in
  `indicator_hierarchy.py:24,49,66,82`.

Used in this runtime: no — the stub value `cot_z_score = 0.0` was consumed by
the positioning persistence/magnitude criteria (`assembler.py` positioning
block), i.e. a constant placeholder, not data.

### 3.7 Central Banks — placeholder (not used in runtime)

Implemented:
- `CBGoldReserveFetcher` (`src/connectors/cb_gold_fetcher.py:25`):
  `get_us_holdings` via FRED series `GOLDUS` (non-standard series; returns
  None on failure, `cb_gold_fetcher.py:44-50`); `get_known_top_holders` is a
  hard-coded 15-country table (`:52-74`); `aggregate_central_bank_demand` is
  a hard-coded tonnes dict (`:76-91`).
- `CentralBankReserveFlowReport` contract (`cfi/contracts.py:76-94`) and CBI
  contracts (`src/knowledge/cbi/contracts.py:85-130`) exist with no producer.

Used in this runtime: no. `CBGoldReserveFetcher` is never imported or
instantiated anywhere in `src/` (only self-file reference). No central-bank
value appears in any artifact; `_CACHE_PATH` target
`data/central_bank_gold.csv` does not exist.

### 3.8 Options — missing (not used in runtime)

- Only a contract: `GoldPositioningDashboard.options_put_call_ratio` and
  `dealer_gamma_profile` (`cfi/contracts.py:101-102`), never populated.
- No put/call, options open interest, or dealer gamma data source exists in
  `src/`.

Used in this runtime: no — no options data or code path executed.

### 3.9 Volatility — partially implemented (used: yes, derived metrics only)

Implemented:
- Realized-vol z-scores (`overnight_fetcher.py:113-121`); VaR/CVaR and tail
  risk (`src/forecasting/risk_measures.py`) used in pre-market risk report
  and position sizing; `VolatilityTargetSizer`
  (`src/forecasting/position_sizing.py`).
- VIX: no VIX fetcher/data exists in `src/`; `"vix"` appears only as an
  indicator name/weight (`indicator_hierarchy.py:71`). No GARCH/implied-vol.

Used in this runtime: partial — computed risk metrics from price history
(volatility_impact 0.7172, tail_risk 0.3422, liquidity_risk 0.2483,
`finalize.json:135-146`; `position_sizing.current_vol 0.003246`,
`finalize.json:254`). Market volatility indices (VIX) not used.

### 3.10 Geopolitics — missing (not used in runtime)

Implemented:
- News keyword handling only: GEOPOLITICS RSS topic
  (`news/models.py:16,48-50`), narrative keyword scoring
  (`signal_assessment/narrative.py:12,93`), triage keywords
  (`src/event_triage/tierer.py:32,46-47`).
- GPR index: appears only as indicator names/weights
  (`indicator_hierarchy.py:31,56,74,87`) and as an optional
  `gpr_series` parameter of `InstitutionalRegimeDetector.fit`
  (`institutional_regime_detector.py:62,90-95`); no GPR series is ever
  loaded. `InstitutionalRegimeDetector` is never instantiated in the runtime
  (only `MacroRegimeDetector`, `stages.py:33`).

Used in this runtime: no. No GPR value in artifacts; no news headlines to
score (news_confidence 0.0).

### 3.11 Liquidity — missing (not used in runtime)

Implemented:
- GOFO: `_fetch_gofo()` returns hard-coded `{"rate": 0.0}`
  (`positioning.py:87-89`).
- `usd_liquidity_measures`, `gold_forward_rate`, `term_premium` appear only
  as indicator names/weights (`indicator_hierarchy.py:44,72-73,107`).
- `LiquidityOutlook` contract (`cbi/contracts.py:115-121`) with no producer.
- No SOFR/LIBOR/FRA-OIS/swap-spread/Fed-balance-sheet fetchers in `src/`.

Used in this runtime: no market liquidity data. The `liquidity_risk` value
in `finalize.json:140` is derived from confidence inputs
(`risk_reward_validation/validator.py:94`), not from liquidity data.

### 3.12 Risk Sentiment — partially implemented (used: no market sentiment)

Implemented:
- `NewsSentimentAnalyzer` (ModernFinBERT, `src/nlp/news_sentiment.py:19`)
  wired into `OvernightNewsIngestion` (`pre_market/news_ingestion.py:31`) and
  `ForecastContextBuilder` (`forecasting/context.py:99`).
- `FOMCSentimentAnalyzer` (FOMC-RoBERTa, `src/nlp/fomc_sentiment.py:25`)
  wired only via `ForecastContextBuilder._resolve_fomc_sentiment`
  (`context.py:166-183`).
- S&P 500 futures (ES=F) fetched as a risk-appetite instrument
  (`overnight_fetcher.py:15`).

Used in this runtime: no market-sentiment signal. News ingestion produced no
items (news_mood null, fomc_mood null, news_confidence 0.0,
`finalize.json:15-19`); the live `_build_context`/`_forecast_confidence`
stages construct the builder with no news/fomc texts, so news/fomc mood are
None in live runs. ES=F price was fetched but no ES=F value persists in
`knowledge.json`/`lessons.csv`.

### 3.13 Physical Demand — missing (not used in runtime)

- `fabrication_demand` appears only as an indicator name/weight
  (`indicator_hierarchy.py:28`); `MECHANISM_JEWELLERY_DEMAND` constant
  (`src/knowledge/factors/contracts.py:113`); triage keyword "SUPPLY/COSTS"
  (`tierer.py:37`).
- No jewelry/coin/bar/retail-demand data source exists in `src/`.

Used in this runtime: no.

### 3.14 Mining Supply — missing (not used in runtime)

- `gold_mining_supply` appears only as an indicator name/weight
  (`indicator_hierarchy.py:27`); `MECHANISM_SUPPLY_CONSTRAINT` constant
  (`factors/contracts.py:116`).
- No mining/production/supply data source exists in `src/`.

Used in this runtime: no.

### 3.15 News — partially implemented (used: no)

Implemented:
- RSS feeds: `NewsCollector` (`src/news/news_collector.py:16`) with
  `DEFAULT_RSS_FEEDS` (`news/models.py:29-51`); `OvernightNewsIngestion`
  wired into the briefing (`briefing_assembler.py:70`).
- Broken duplicate path: `_ingest_news` imports `news.collector` which does
  not exist (module is `news/news_collector.py`); ImportError swallowed
  (`stages.py:63-69`) — the institutional `ingest_news` stage always yields
  `[]` (ran "ok" in 3.49 ms, `stages.json`).

Used in this runtime: no. `news_confidence 0.0`, `news_mood null`,
`recent_events []` (`finalize.json:15-19`); no headline text in any artifact.
Why not: the stage-level ingestion path is broken (wrong import name); the
pre-market news ingestion produced no items in this run.

## 4. Signals the system SHOULD know for XAU/USD but did not use

Cross-category register of missing/absent institutional inputs in this
runtime (all values absent from `finalize.json`, `artifacts/knowledge.json`,
`artifacts/lessons.csv`):

- Real yields (10Y TIPS) — live-capable via FRED DFII10; no value reached the
  decision (config `yield_data_path: null`; real-yield consumers unwired).
- Nominal yields / policy rates — DGS10, FEDFUNDS, DFF available in FRED
  client; not invoked (CPI-only event run; FOMC calendar fetch broken).
- Breakeven inflation — T5YIE fetched-capable; not used.
- COT managed-money positioning — hard-coded stub 0.0 (no CFTC feed).
- ETF AUM flows — price-change proxy only (GLD/IAUM closes); no AUM/flow
  data; CFI contract never populated.
- Central bank net purchases / reserves — hard-coded table, never wired.
- Options (put/call ratio, dealer gamma) — contract only, no data.
- VIX / implied volatility — no data source.
- Geopolitical Risk Index (GPR) — config names only; no series loaded.
- GOFO / gold forward rate — hard-coded stub 0.0.
- USD liquidity (SOFR, LIBOR, FRA-OIS, swap spreads, Fed balance sheet) —
  no data source.
- Physical demand (jewelry, coins, bars, fabrication) — no data source.
- Mining supply (production, supply constraint) — no data source.
- News headlines / sentiment / FOMC sentiment — none ingested (stage import
  broken; pre-market ingestion empty).

## 5. Dead or unwired institutional code (facts)

- `CBGoldReserveFetcher` — never imported/instantiated in `src/`
  (only `cb_gold_fetcher.py:25`).
- `RealYieldFetcher` — referenced only in its own file and a docstring
  (`dxy_fetcher.py:12`).
- `RealYieldAdapter`, `DXYAdapter` — never instantiated
  (`factors/adapters/real_yield_adapter.py:25`, `dxy_adapter.py:26`).
- `DXYContextEnricher` — defined (`context/dxy.py:18`), not wired into
  `knowledge/pipeline/pipeline.py`.
- `gold_rule_001` (real yield × DXY rule) — never invoked
  (`rules/gold_rule_001.py:95`).
- `InstitutionalRegimeDetector` — never instantiated in runtime
  (`stages.py:33` uses `MacroRegimeDetector` only).
- `_ingest_news` FOMC branch — calls non-existent `fomc.fetch()`, error
  swallowed (`stages.py:71-77`).
- CFI contracts (`ETFFlowMonitor`, `CentralBankReserveFlowReport`,
  `GoldPositioningDashboard`) and CBI contracts — no producer populates
  them; `OrchestrationContext.cfi_*`/`cbi_*` never set in the runtime.

## 6. Observability notes (facts)

- The 6 knowledge records and 127 lessons are CPI-only; no other event type
  was present in this run's artifacts.
- No per-observation or per-evidence item is persisted; only driver
  aggregates (evidence_quality 0.5656, counter_evidence_quality 0.7) reach
  `finalize.json:39-49`. The single named evidence set `es_usd_fx` appears
  only in `invalidation_conditions` (`finalize.json:67`).
- `events/__init__.py:32,36,38` lists enum values UNEMPLOYMENT, DXY, YIELD10
  for which no event classes exist.
- Runtime regime values LATE_CYCLE/RECOVERY/CONTRACTION/EXPANSION (from
  `lessons.csv`) are produced by `MacroRegimeDetector`
  (`stages.py:33`); the `REGIME_INDICATORS` hierarchy
  (`indicator_hierarchy.py:7-148`) names 6 canonical regimes
  (NORMAL_GROWTH, INFLATIONARY, STAGFLATIONARY, DEFLATIONARY_CRISIS,
  GEOPOLITICAL_STRESS, STRUCTURAL_REGIME_CHANGE) with 22 institutional
  indicator weights; `IndicatorHierarchyGenerator` is not invoked by the
  runtime stages.
