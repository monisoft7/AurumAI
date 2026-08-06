# Audit: Top Five Missing Institutional Gold Signals

**Date:** 2026-08-05
**Reference:** extends `docs/audit/GOLD_KNOWLEDGE_COVERAGE_001.md`
**Scope:** Real Yields (DFII10), DXY Context, Breakeven Inflation (T5YIE), ETF AUM Flows, COT Positioning
**Target runtime:** `outputs/2026-08-05/runtime_20260805_102841` (NO_TRADE, institutional_confidence 0.2012, composite 0.4327)
**Mode:** read-only audit; no fixes applied

## Definitions

- **Wiring-only** — live data already fetched and/or persisted; only consumption is missing.
- **New connector** — no data source exists in the codebase; a fetcher must be created.
- **Placeholder replacement** — a stub/proxy currently occupies the slot and must be replaced with real data.

---

## 1. Real Yields (DFII10)

| Aspect | Finding |
|---|---|
| Existing code | `RealYieldFetcher` — `src/connectors/real_yield_fetcher.py:10`, `SERIES_ID="DFII10"` (`:18`), wraps `FredClient`, cache-backed, empty series on failure |
| Existing consumer | `YieldContextEnricher` (`src/knowledge/context/yields.py`) — `enrich`/`enrich_csv`, lookback 30d, low 2.0 / high 4.0, flat 10bp |
| Wiring in pipeline | `src/knowledge/pipeline/pipeline.py:89-96` — enricher call site exists, **gated by `if context.yield_data_path is not None:`** |
| Contracts | `FactorSignal` via `RealYieldAdapter` (`src/knowledge/factors/adapters/real_yield_adapter.py:25`) — reference adapter, never instantiated; rule `src/knowledge/reasoning/rules/gold_rule_001.py:95` (real yield × DXY) never invoked |
| Runtime usage | Run config had `yield_data_path: null`; gate at `pipeline.py:89` skipped; no yield context in lessons |
| Data on disk | `data/economic/DFII10.csv` (live FRED cache) |
| Disconnected at | Config value (`yield_data_path: null`), not code |
| Implementation type | **Wiring-only** |
| Complexity | **Small** — set `yield_data_path` in run config; optionally instantiate `RealYieldAdapter` + invoke `gold_rule_001` |

## 2. DXY Context

| Aspect | Finding |
|---|---|
| Existing code | `DXYFetcher` — `src/connectors/dxy_fetcher.py:7`, `TICKER="DX-Y.NYB"` (`:15`), yfinance, empty series on failure |
| Existing consumer | `DXYContextEnricher` (`src/knowledge/context/dxy.py`) — structurally mirrors yields enricher; `dxy_path`, lookback 30d, low 95 / high 105, flat 1.0 |
| Wiring in pipeline | **Not imported** — `pipeline.py:17` imports only `YieldContextEnricher`; no `dxy_path` on `PipelineContext`; enricher referenced nowhere in `src/` |
| Contracts | `DXYAdapter` (`src/knowledge/factors/adapters/dxy_adapter.py:26`) — configurable reference adapter (FactorConfig), never instantiated; `gold_rule_001` pairs DXY with real yields |
| Runtime usage | DXY price fetched for composite (`DX-Y.NYB` in fetch list) but never enters knowledge context |
| Data on disk | `data/context/dxy/dxy.csv` (82KB, live) |
| Disconnected at | Pipeline assembly — no import, no context field, no call site |
| Implementation type | **Wiring-only** (mirror the existing yields block at `pipeline.py:89-96`) |
| Complexity | **Small** — add `dxy_path` to context, import enricher, add call site mirroring yields |

## 3. Breakeven Inflation (T5YIE)

| Aspect | Finding |
|---|---|
| Existing code | `data/economic/T5YIE.csv` on disk; `FredClient.get_series` accepts arbitrary series IDs; `overnight_fetcher.py:24` lists T5YIE in overnight FRED set |
| Existing consumer | **None** — no adapter, no enricher, no lesson integration; `EconomicDataFetcher._INDICATORS` (`src/connectors/fred_client.py:106-116`) omits T5YIE |
| Wiring in pipeline | None |
| Contracts | None (no `FactorSignal` path for breakeven) |
| Runtime usage | T5YIE value never reaches artifacts (runtime shows no inflation-expectations evidence) |
| Data on disk | `data/economic/T5YIE.csv` (live FRED cache) |
| Disconnected at | Consumption layer — data and fetch capability exist, zero consumers |
| Implementation type | **New connector (minor) + wiring** — data layer already works; needs adapter/enricher + pipeline call site |
| Complexity | **Medium** — new adapter + enricher + wiring; no new fetch infrastructure |

## 4. ETF AUM Flows

| Aspect | Finding |
|---|---|
| Existing code | `PositioningDataFetcher._fetch_etf_flow` — `src/pre_market/positioning.py:43-70`: **GLD/IAUM 5-day close-price proxy**, not AUM |
| Existing consumer | `ETFFlowMonitor` contract — `src/knowledge/cfi/contracts.py:62-72`; CFI adapter exists (`src/knowledge/cfi/adapter.py`); `GoldPositioningDashboard.etf_flow` (`contracts.py:100`) frozen-empty |
| Contracts | `PositioningSnapshot.etf_flow_momentum` / `etf_flow_change_pct` populated from price proxy only |
| Runtime usage | Proxy-derived flow momentum only; true AUM absent |
| Data on disk | None for AUM |
| Disconnected at | Data source — price movement is a proxy for shares-outstanding flows |
| Implementation type | **Placeholder replacement + new connector** (AUM feed, e.g. shares outstanding × NAV) |
| Complexity | **Medium–Large** — new AUM connector + adapter swap + contract population |

## 5. COT Positioning

| Aspect | Finding |
|---|---|
| Existing code | `_fetch_cot` stub — `src/pre_market/positioning.py:40-41`: hardcoded `{"z_score": 0.0, "regime": "neutral"}` |
| Existing consumer | `GoldPositioningDashboard.cot_net_non_commercial` (`contracts.py:99`) frozen-empty; `PositioningSnapshot.cot_z_score`/`cot_regime` always neutral |
| Wiring in pipeline | None |
| Contracts | Contract exists, never populated |
| Runtime usage | No COT evidence in any artifact (verified in runtime) |
| Data on disk | None |
| Disconnected at | Data source — no CFTC connector anywhere in `src/` |
| Implementation type | **Placeholder replacement + new connector** (CFTC weekly reports) |
| Complexity | **Large** — new CFTC connector + parsing + adapter + contract population |

---

## Ranking A — Highest Impact (from GOLD_KNOWLEDGE_COVERAGE_001 register)

1. **Real Yields (DFII10)** — #1 in missing-capability register; opportunity-cost mechanism fully coded but disabled by config
2. **DXY Context** — #3; inverse USD mechanism + `gold_rule_001` already written, unwired
3. **ETF AUM Flows** — #4; distinguishes price moves from investor flows
4. **COT Positioning** — #5; only true speculator-positioning signal, entirely stubbed
5. **Breakeven Inflation (T5YIE)** — #6; complements real yields in the inflation-expectations cluster

## Ranking B — Lowest Implementation Cost

1. **Real Yields (DFII10)** — Small, wiring-only (config value + optional adapter/rule hookup)
2. **DXY Context** — Small, wiring-only (mirror yields block, `pipeline.py:89-96`)
3. **Breakeven Inflation (T5YIE)** — Medium, data layer already live; new adapter + enricher
4. **ETF AUM Flows** — Medium–Large, new connector replaces price proxy
5. **COT Positioning** — Large, new CFTC connector + full replacement

## Conclusion

Two of the five signals (Real Yields, DXY) are **code-complete but config/assembly-disconnected** — both rank top-3 in impact and bottom-2 in cost, making them the clear first moves. Breakeven sits between (data layer ready, consumer missing). ETF AUM and COT require genuine new data infrastructure.
