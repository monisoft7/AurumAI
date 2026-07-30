# Gold Influence Map v1

**Document ID:** GIM-v1  
**Classification:** Internal — Institutional Research  
**Date:** 2026-07-28  
**Author:** Chief Research Engineer, AurumAI  
**Status:** Living Document — v1 Freeze  

---

## Table of Contents

1. Executive Summary  
2. Research Methodology & Authoritative Sources  
3. Complete Gold Influence Map (60+ Factors)  
4. Influence Hierarchy  
5. Dependency Graph  
6. High-Priority Factors (Influence Score ≥ 8)  
7. Low-Priority Factors (Influence Score ≤ 3)  
8. Missing Free Data  
9. Existing OSS Ecosystem  
10. Final Recommendations for AurumAI Architecture  

---

## 1. Executive Summary

Gold is not like other assets. It has no coupon, no dividend, no earnings, and no default risk. Its price is determined by the equilibrium between five demand categories (jewellery, investment, central banks, technology, OTC) and two supply categories (mine production, recycling). Unlike equities or bonds, where valuation is anchored to discounted cash flows, gold valuation is a system of competing narratives about store-of-value, monetary stability, geopolitical risk, and real returns.

**The core finding of this research is that gold price factors decompose into a clear hierarchy:**

| Layer | Time Horizon | Primary Factors | Share of Explanatory Power |
|-------|-------------|-----------------|---------------------------|
| **Long-term (>5 years)** | Secular | Global nominal GDP growth, global portfolio capitalisation (GLTER model) | ~60-70% |
| **Medium-term (1-5 years)** | Cyclical | Real yields, US dollar, central bank reserves, monetary policy regime | ~20-25% |
| **Short-term (<1 year)** | Tactical | ETF flows, COT positioning, momentum, geopolitical risk, seasonality | ~10-15% |

*Source: World Gold Council GRAM model, Federal Reserve Bank of Chicago CFL No. 464, Gold Long-Term Expected Return (GLTER) model.*

**Critical structural shift (2022–2026):** The pre-2024 framework — where gold was best explained by real yields (inverse correlation ~-0.85), the trade-weighted dollar, and managed-money positioning — has structurally broken. Central bank buying (>1,000t annually 2022–2024) has introduced a structural buyer invisible to the COT report and partially decoupled from real yields. The April 2026 configuration (gold at $4,637 with moderate managed-money positioning at 175-225k contracts vs. 290k at the 2011 peak) is the visible signature of this shift.

*Sources: Convex Research April 2026, ECB IRE Box June 2025, IMF WP/23/008, Federal Reserve IFDP 1420.*

---

## 2. Research Methodology & Authoritative Sources

### Priority-ordered source list used in this research:

| Rank | Source | Data/Material Used |
|------|--------|--------------------|
| 1 | World Gold Council | GRAM model, GLTER model, Qaurum GVF, Gold Demand Trends (Q1 2025, FY 2024, Q1 2026, FY 2025), Central Bank Surveys 2024/2025, ETF flow data, Gold Return Attribution Model |
| 2 | LBMA | Gold Price PM Fix (1971–present), trading volume data |
| 3 | CME Group | COMEX gold futures open interest, options data |
| 4 | Federal Reserve | Chicago Fed Letter No. 464 (Barsky et al. 2021), IFDP 1420 (Weiss 2024), FRED API |
| 5 | FRED | 800,000+ economic time series (CPIAUCSL, DGS10, DFF, FEDFUNDS, T10YIE, etc.) |
| 6 | BIS | Working Paper No. 906 (gold in FX reserves), Triennial Survey |
| 7 | IMF | WP/23/008 (Arslanalp, Eichengreen, Simpson-Bell 2023), IFS gold reserve data, Global Financial Stability Reports |
| 8 | ECB | International Role of the Euro June 2025 (gold demand & geopolitics box), Financial Stability Review May 2025 |
| 9 | CFTC | Disaggregated Commitments of Traders reports (gold, weekly) |
| 10 | NBER | Working Paper 17894 (Aizenman & Inoue), various gold papers |
| 11 | SSRN | Changani (2024), Erb & Harvey (2024), Baur (2013 seasonality), Gülseven (2020), multiple gold factor papers |
| 12 | OECD | Economic outlook data |
| 13 | Academic | Journal of International Money & Finance, Resources Policy, International Review of Financial Analysis, Energy Economics, PLOS ONE |

---

## 3. Complete Gold Influence Map

### 3.1 MONETARY POLICY

#### 3.1.1 Federal Funds Rate

| Field | Value |
|-------|-------|
| **Category** | Monetary Policy |
| **Why it affects Gold** | The fed funds rate is the base price of money. It determines short-term opportunity cost of holding non-yielding gold and sets the tone for global monetary conditions through dollar funding channels. |
| **Direct / Indirect** | Indirect — transmits through real yields, USD, and dollar funding conditions |
| **Relationship** | Negative — rate hikes suppress gold (higher opportunity cost); rate cuts support gold |
| **Time Horizon** | Short-term (policy decisions, FOMC meetings) to medium-term (rate cycle) |
| **Historical Importance** | Very high. Wang & Chueh (2013) demonstrate dynamic transmission: FFR → USD → gold. Herley, Orłowski & Ritter (2024) show gold-USD elasticity is state-dependent across FFR zones (low: weak, intermediate: stronger, high: very pronounced). |
| **Influence Score** | 8/10 |
| **Interaction** | Interacts with real yields, USD, inflation expectations, central bank reserves. At zero-lower-bound periods, the relationship weakens as QE replaces rate policy. |
| **Can conflicts occur?** | Yes — during "higher-for-longer" vs. recession-cut expectations. The market trades forward guidance, not the current rate. |
| **Typical market behaviour** | Gold rallies in anticipation of rate cuts; sells off when cuts are delayed. FOMC dates see elevated gold volatility. |
| **Required data source** | FRED (DFF, FEDFUNDS), CME FedWatch Tool |
| **Free data availability** | Full — FRED API (fredapi, free key), CME FedWatch (free) |
| **Existing open-source projects** | `fredapi` (Mortada), `fredq` (typed library), `pandas-datareader` |
| **Existing APIs** | FRED API v2, CME FedWatch Tool |
| **Recommended integration** | **Reuse** — `fredapi` adapter. Already in `.env` (`FRED_API_KEY`). Replace static CSV approach. |

#### 3.1.2 Quantitative Easing / Tightening (Central Bank Balance Sheets)

| Field | Value |
|-------|-------|
| **Category** | Monetary Policy |
| **Why it affects Gold** | QE expands central bank balance sheets, increases money supply, weakens currency, lowers real yields, and creates demand for alternative safe assets. Balance sheet runoff reverses this. |
| **Direct / Indirect** | Indirect — through global liquidity, real yields, and dollar funding |
| **Relationship** | Positive for QE (gold ↑), negative for QT (gold ↓) |
| **Time Horizon** | Medium-term (policy cycle) to long-term (structural) |
| **Historical Importance** | Very high. BIS Working Paper No. 906 shows QE → increased EMDE gold reserves. G4 central bank assets growth correlates with gold reserve accumulation. Post-GFC QE triggered structural shift in EMDE gold buying. |
| **Influence Score** | 8/10 |
| **Interaction** | Interacts with global liquidity, money supply (M2), real yields, and currency reserves. The Fed, ECB, BOJ, and PBOC balance sheets combined drive global dollar/euro/yuan liquidity. |
| **Can conflicts occur?** | Yes — simultaneous QE by multiple central banks amplifies gold impact. Divergent monetary policy complicates net effect. |
| **Required data source** | FRED (WALCL — Fed balance sheet), ECB, BOJ, PBOC balance sheet data |
| **Free data availability** | Full for Fed, ECB, BOJ. PBOC data is partial/lower frequency. |
| **Existing open-source projects** | `fredapi`, `pandas-datareader` |
| **Existing APIs** | FRED API, ECB SDW API |
| **Recommended integration** | **Reuse** — wrap `fredapi` for Fed balance sheet data. Add ECB/BOJ adapters. |

#### 3.1.3 US Dollar (DXY / Broad Dollar Index)

| Field | Value |
|-------|-------|
| **Category** | Monetary Policy / Currency |
| **Why it affects Gold** | Gold is priced in USD. A weaker dollar makes gold cheaper for non-USD buyers (pricing channel). Dollar also embeds monetary policy expectations and global liquidity conditions (dollar-channel proxy). |
| **Direct / Indirect** | Direct — pricing channel; Indirect — opportunity cost and global liquidity channels |
| **Relationship** | Negative — strong inverse correlation. MDPI study (2026) finds DXY coefficient of −2.24 on gold returns. Persistent across all data frequencies. |
| **Time Horizon** | All horizons — strongest factor in short-to-medium term |
| **Historical Importance** | Highest among individual factors. Reboredo (2013), Wang & Chueh (2013), Herley et al. (2024). The MDPI (2026) study using Lasso + post-Lasso estimation confirms DXY has the most robust incremental predictive power for gold returns among all macro factors. |
| **Influence Score** | 9/10 |
| **Interaction** | Interacts with every other factor. Real yields → USD → gold. Risk sentiment → USD → gold. Inflation → Fed policy → USD → gold. The DXY is the reduced-form channel for the entire macro-financial transmission mechanism. |
| **Can conflicts occur?** | Yes — in crisis periods (2008, 2020) both gold and USD can rally simultaneously (complementarity, not substitution). This is the safe-haven "both bid" phenomenon documented by Herley et al. (2024) using Markov switching. |
| **Typical market behaviour** | During normal periods: USD up → gold down (substitution effect). During crisis (flight-to-safety): USD up AND gold up (both are safe havens). |
| **Required data source** | FRED (DTWEXBGS, DTWEXAFEGS), ICE (DXY) |
| **Free data availability** | Full — FRED API (DTWEXBGS is the broad trade-weighted USD index, free) |
| **Existing open-source projects** | `fredapi`, `yfinance` (DXY=DX-Y.NYB) |
| **Existing APIs** | FRED API, Yahoo Finance |
| **Recommended integration** | **Reuse** — `fredapi` adapter replacing static CSV. Already partially used in `scripts/download_dxy.py`. Wire into production pipeline. |

---

### 3.2 INTEREST RATES & REAL YIELDS

#### 3.2.1 Real Yields (10-Year TIPS)

| Field | Value |
|-------|-------|
| **Category** | Interest Rates / Real Yields |
| **Why it affects Gold** | The opportunity cost of holding non-yielding gold. When real yields rise, bonds become more attractive relative to gold. This is the most theoretically grounded relationship in gold economics. |
| **Direct / Indirect** | Direct — standard asset substitution channel. "Given that gold is a long-duration durable asset with a relatively stable dividend yield, its price is expected to have a strong inverse relationship with the long-term real interest rate." (Chicago Fed, 2021) |
| **Relationship** | Negative — pre-2024: −0.85 correlation. Each 100bp move in 10Y TIPS → ~$200-300 move in gold (inverse). Post-2024: correlation partially broken due to central bank buying. |
| **Time Horizon** | Medium-term (cycle) to long-term (structural) |
| **Historical Importance** | Highest among macro factors for 2001–2022 period. Chicago Fed regression: 1pp rise in 10Y real rate → −13.1% gold price. Pre-COVID, this was the dominant factor. Post-COVID: diminished explanatory power (Demajo, 2025; University of Malta). |
| **Influence Score** | 9/10 (pre-2022) → 7/10 (current, partially decoupled) |
| **Interaction** | Interacts with Fed policy, inflation expectations, nominal yields, US dollar. The real yield is itself a composite of nominal yield minus inflation expectations. |
| **Can conflicts occur?** | Yes — 2024-2026 regime: real yields remained at 1.80-2.20% while gold doubled from $2,000 to $4,746. The structural break is the central-bank buying channel. ECB IRE (June 2025) confirms the gold-real yield correlation broke down post-Russia-Ukraine invasion. |
| **Typical market behaviour** | Historically: TIPS yields down → gold up, with 2-4 week lag. Current: relationship is state-dependent and weakened. |
| **Required data source** | FRED (DFII10 — 10-Year TIPS yield, DGS10 — 10-Year Nominal, T10YIE — Breakeven inflation) |
| **Free data availability** | Full — FRED API |
| **Existing open-source projects** | `fredapi` |
| **Existing APIs** | FRED API |
| **Recommended integration** | **Reuse** — `fredapi` adapter. Must account for regime-dependent break. Do NOT assume constant inverse correlation. Track rolling correlation window. |

#### 3.2.2 Nominal Yields (10-Year Treasury)

| Field | Value |
|-------|-------|
| **Category** | Interest Rates |
| **Why it affects Gold** | Embeds both real yield and inflation expectations. Drives global fixed-income portfolio allocation. |
| **Direct / Indirect** | Indirect — decomposes into real yield + inflation expectation (see Real Yields) |
| **Relationship** | Negative (typically, via real yield component) |
| **Time Horizon** | Medium-term |
| **Historical Importance** | High — the DGS10 is the most-watched global interest rate benchmark |
| **Influence Score** | 7/10 |
| **Interaction** | Interacts with real yields, term premium, Fed policy. The difference DGS10 − DFII10 = breakeven inflation rate. |
| **Required data source** | FRED (DGS10, T10Y2M — yield curve) |
| **Free data availability** | Full |
| **Existing open-source projects** | `fredapi` |
| **Existing APIs** | FRED API |
| **Recommended integration** | **Reuse** — `fredapi`. Already used in AurumAI's `YieldContextEnricher` with CSV data. Replace CSV with live FRED. |

#### 3.2.3 Yield Curve (2s10s Spread)

| Field | Value |
|-------|-------|
| **Category** | Interest Rates / Recession Indicator |
| **Why it affects Gold** | Inverted yield curve signals expected recession, which historically boosts gold via safe-haven demand and expected rate cuts. |
| **Direct / Indirect** | Indirect — recession expectations channel |
| **Relationship** | Negative spread (inversion) → eventually positive for gold (with 6-18 month lag to recession) |
| **Time Horizon** | Medium-term (6-18 month leading indicator) |
| **Historical Importance** | High — inverted curve preceded every US recession since 1970. Gold rallies in rate-cutting cycles that follow inversions. |
| **Influence Score** | 6/10 |
| **Interaction** | Interacts with recession risk, Fed policy expectations, equity volatility. |
| **Required data source** | FRED (T10Y2Y) |
| **Free data availability** | Full |
| **Existing open-source projects** | `fredapi` |
| **Existing APIs** | FRED API |
| **Recommended integration** | **Reuse** — `fredapi` adapter. Compute as derived series. |

---

### 3.3 INFLATION

#### 3.3.1 Headline CPI / Inflation Expectations

| Field | Value |
|-------|-------|
| **Category** | Inflation |
| **Why it affects Gold** | Gold is the classical inflation hedge. Chicago Fed (2021): "Given the long-term real interest rate, an extra percentage point of ten-year expected inflation raises the real gold price by a hefty 37%." |
| **Direct / Indirect** | Direct — as an inflation hedge narrative. Also indirect via real yields channel. |
| **Relationship** | Positive — gold ↑ when inflation ↑ (hedge demand) |
| **Time Horizon** | Pre-2000: dominant long-term factor. Post-2000: diminished but re-emerged 2021-2023. |
| **Historical Importance** | Very high. 1971-2000: inflation was the single most important driver. 2000-2020: diminished (inflation anchored at ~2%). 2021-2023: re-emerged with post-COVID inflation spike. |
| **Influence Score** | 8/10 (regime-dependent: high in high-inflation regimes) |
| **Interaction** | Interacts with real yields (inflation component), Fed policy (reaction function), commodity complex (oil → CPI via energy). The relationship is non-linear: gold responds more to unexpected inflation than to expected inflation. |
| **Can conflicts occur?** | Yes — during "good disinflation" (disinflation from supply-side recovery) gold may fall despite falling inflation. During "bad stagflation" (high inflation + low growth) gold can rally strongly. |
| **Typical market behaviour** | CPI releases see 0.5-1.5% gold price moves. Higher-than-expected CPI → gold rallies. |
| **Required data source** | FRED (CPIAUCSL, PCEPILFE — Core PCE, T5YIE, T10YIE — breakeven inflation rates) |
| **Free data availability** | Full — FRED API (CPIAUCSL, PCE, breakeven rates all free) |
| **Existing open-source projects** | `fredapi`, `pandas-datareader` |
| **Existing APIs** | FRED API, BLS API |
| **Recommended integration** | **Reuse** — `fredapi` adapter. Already uses `data/economic/CPIAUCSL.csv` — replace with live FRED. |

#### 3.3.2 Core Inflation (Core CPI / Core PCE)

| Field | Value |
|-------|-------|
| **Category** | Inflation |
| **Why it affects Gold** | Core inflation (ex-food & energy) is the Fed's preferred metric. It drives Fed policy more directly than headline CPI. |
| **Direct / Indirect** | Indirect — via Fed policy expectations |
| **Relationship** | Positive (same as headline, but policy-sensitive) |
| **Time Horizon** | Medium-term |
| **Historical Importance** | High — since 2000, Core PCE is the Fed's target. Gold responds more to core surprises than headline. |
| **Influence Score** | 7/10 |
| **Interaction** | Interacts with Fed funds rate expectations, real yields, and the USD |
| **Required data source** | FRED (PCEPILFE — Core PCE, CPILFESL — Core CPI) |
| **Free data availability** | Full |
| **Existing open-source projects** | `fredapi` |
| **Existing APIs** | FRED API |
| **Recommended integration** | **Reuse** — `fredapi` |

---

### 3.4 CENTRAL BANK GOLD RESERVES

#### 3.4.1 Central Bank Net Purchases

| Field | Value |
|-------|-------|
| **Category** | Central Banks / Official Sector |
| **Why it affects Gold** | Central banks are structural, non-commercial buyers who take physical delivery. Their purchases remove gold from the float permanently (or for decades). At >1,000t/year (2022-2024), they represent ~20% of global demand vs. ~10% average in 2010s. |
| **Direct / Indirect** | Direct — physical demand channel |
| **Relationship** | Positive — CB buying supports gold price floor and provides structural upward bias |
| **Time Horizon** | Medium-term (quarterly data) to long-term (structural) |
| **Historical Importance** | **Transformative** — the 2022-2026 cycle is historic. Since Q2 2009, central banks have been net buyers every quarter. The post-Russia-Ukraine acceleration (>1,000t/year 2022-2024) is the dominant new factor. IMF WP/23/008 identifies 14 "active diversifiers" (exclusively EM). ECB IRE (June 2025): "Gold demand for monetary reserves surged sharply in the wake of Russia's full-scale invasion of Ukraine." |
| **Influence Score** | 10/10 (current regime-defining factor) |
| **Interaction** | Interacts with geopolitical risk (sanctions), de-dollarization, USD reserve share, financial sanctions. Weiss (Federal Reserve IFDP 1420): sanctions are associated with increased gold reserve share. |
| **Can conflicts occur?** | Yes — CB buying happens at the same time as Western ETF outflows (2023-2024), creating a "West sells, East buys" divergence. CB buying is price-insensitive in the short term. |
| **Typical market behaviour** | Structural support, not a short-term price driver. However, monthly CB purchase announcements (e.g., China, Poland, Turkey) can trigger 1-3% rallies. |
| **Required data source** | World Gold Council (quarterly), IMF IFS (monthly), individual central bank disclosures |
| **Free data availability** | Yes — WGC publishes quarterly CB data free. IMF IFS data available but requires navigation. |
| **Existing open-source projects** | None specialized for CB gold data |
| **Existing APIs** | WGC Goldhub data API (free registration), IMF Data Portal |
| **Recommended integration** | **Adapt** — build an `CBGoldReserveFetcher` adapter that pulls from WGC Goldhub API and IMF IFS. This is currently a gap in AurumAI. |

#### 3.4.2 Central Bank Gold Reserve Share (%)

| Field | Value |
|-------|-------|
| **Category** | Central Banks / Official Sector |
| **Why it affects Gold** | The share of gold in total FX reserves signals central bank portfolio preferences. Rising share = ongoing diversification out of FX into gold. From 10% of reserves (2019) to >22% (Aug 2025) per IMF. |
| **Direct / Indirect** | Indirect — signals structural regime shift |
| **Relationship** | Positive — rising share supports gold, but with self-limiting mechanics (BIS WP No. 906) |
| **Time Horizon** | Long-term (structural, multi-year) |
| **Historical Importance** | High — the doubling of gold's reserve share in 6 years is unprecedented |
| **Influence Score** | 8/10 |
| **Interaction** | Interacts with de-dollarization, sanctions risk, geopolitical alignment |
| **Required data source** | IMF IFS, WGC Central Bank Surveys |
| **Free data availability** | Yes — WGC annual survey, IMF data |
| **Recommended integration** | **Build** — specialized contract `CentralBankReserveDiversification` in CBI package |

---

### 3.5 ETF FLOWS

#### 3.5.1 Global Gold ETF Holdings & Flows

| Field | Value |
|-------|-------|
| **Category** | Investment Demand |
| **Why it affects Gold** | Gold ETFs bridge physical and paper gold. ETF flows represent investable demand from institutional and retail investors. In 2025, global gold ETFs added 801t — the second strongest year on record. |
| **Direct / Indirect** | Direct — ETFs buy/sell physical gold to back shares. Every tonne of ETF inflow = ~$86M of physical demand at $2,700/oz. |
| **Relationship** | Positive — inflows support gold, outflows pressure gold |
| **Time Horizon** | Short-to-medium term (weeks to months) |
| **Historical Importance** | Very high. GRAM model identifies ETF flows as a momentum driver. 2024 marked the first year since 2020 with essentially unchanged holdings (vs. heavy prior outflows). 2025 was a record inflow year (801t). Q1 2026: 226.5t inflows in January alone. |
| **Influence Score** | 8/10 |
| **Interaction** | Interacts with gold price momentum (positive feedback loop: rising gold → ETF inflows → more gold buying), real yields (Western investors switch between TIPS and gold ETFs based on real yield), geopolitical risk. |
| **Can conflicts occur?** | Yes — "West sells, East buys" divergence (2022-2024: Western ETFs sold while Asian central banks bought). ETF outflows can coexist with rising gold prices. |
| **Typical market behaviour** | Strong ETF inflows amplify gold rallies. Sustained outflows accelerate corrections. Mutual reinforcing: ETF holdings at all-time highs amplify momentum. |
| **Required data source** | World Gold Council (weekly/monthly), Bloomberg (company filings) |
| **Free data availability** | WGC publishes gold ETF data free on Goldhub with registration |
| **Existing open-source projects** | None specialized |
| **Existing APIs** | WGC Goldhub API |
| **Recommended integration** | **Adapt** — build `ETFFlowMonitor` adapter per existing contract in `docs/architecture/Institutional-Knowledge-Contracts.md`. This is a documented gap. |

---

### 3.6 FUTURES POSITIONING & COT

#### 3.6.1 Managed Money Net Positioning (COMEX Gold)

| Field | Value |
|-------|-------|
| **Category** | Speculative Positioning |
| **Why it affects Gold** | Managed money (hedge funds, CTAs) are the marginal price setter in the short term. Their net long/short position measures how crowded the gold trade is. Extreme positioning historically precedes reversals. |
| **Direct / Indirect** | Direct — positioning extremes signal fuel for reversal |
| **Relationship** | Correlated in trend, contrarian at extremes. Rising net longs → gold ↑ (trend). Extreme net longs + falling open interest → vulnerable (contrarian). |
| **Time Horizon** | Short-term (weeks to months) |
| **Historical Importance** | Very high. 2011 peak: 290k net long contract at $1,920 top. 2015 trough: −35k net short at $1,053 bottom. 2020: extreme built and reversed. Current (2026): 175-225k — moderate relative to gold price. |
| **Influence Score** | 7/10 |
| **Interaction** | Interacts with swap dealer positioning (the other side), DXY, real yields. Crowded long + turning dollar = vulnerable. COTInsight: "Gold positioning does not exist in a vacuum. A crowded managed-money long is far more fragile when the dollar is turning up or real yields are rising." |
| **Can conflicts occur?** | Yes — 2024-2026: gold at all-time highs with moderate positioning. The decoupling is the signature of central bank buying as a structural buyer invisible to COT. |
| **Typical market behaviour** | Extreme z-score (+2.0) + falling OI = caution. Extreme + rising OI = trend can continue. Positioning + price divergence (bullish positioning with falling price) = vulnerable. |
| **Required data source** | CFTC Disaggregated COT Report (weekly, free), CME |
| **Free data availability** | Full — CFTC publishes weekly COT data free on website and via bulk download |
| **Existing open-source projects** | `cot-report` (various), `cftc-data` scrapers |
| **Existing APIs** | CFTC public data, CME COT tool |
| **Recommended integration** | **Adapt** — build `COTPositioningReport` adapter per existing contract. This is a documented gap in AurumAI. CFTC data is free and machine-parseable. |

#### 3.6.2 Swap Dealer Positioning

| Field | Value |
|-------|-------|
| **Category** | Dealer/Intermediary Positioning |
| **Why it affects Gold** | Swap dealers intermediate OTC gold market on COMEX. Their net short position is the other side of speculative length. Extreme swap dealer shorts signal potential short-squeeze fuel. |
| **Direct / Indirect** | Indirect — measures market structure imbalance |
| **Relationship** | Large swap dealer net short = normal (197k-ish contracts in 2026). Change in position signals important flows. |
| **Time Horizon** | Short-to-medium term |
| **Historical Importance** | High — swap dealer short covering was a key feature of gold's 2024-2026 rally |
| **Influence Score** | 6/10 |
| **Interaction** | Mirrors managed money positioning. Large-scale short covering by swap dealers reduces hedging pressure and supports prices. |
| **Required data source** | CFTC COT Disaggregated | |
| **Free data availability** | Full |
| **Recommended integration** | **Adapt** — include in COT adapter |

---

### 3.7 GEOPOLITICAL RISK & SAFE HAVEN

#### 3.7.1 Geopolitical Risk Index (GPR)

| Field | Value |
|-------|-------|
| **Category** | Geopolitical Risk |
| **Why it affects Gold** | Gold is the primary safe-haven asset during geopolitical crises. The WGC GRAM model uses the GPR Index (Caldara & Iacoviello, 2022) as a direct risk/uncertainty driver. |
| **Direct / Indirect** | Direct — safe-haven demand channel |
| **Relationship** | Positive — GPR spikes → gold rallies |
| **Time Horizon** | Short-term (crisis onset) to medium-term (persistent elevated tension) |
| **Historical Importance** | Very high — Ukraine/Russia sanctions (2022), US-Iran (2026), US-China trade tensions. GPR peaks align with gold price bubble formations (Zhou & Liang, 2025). ECB (2025): sanctions → gold reserve share increases. |
| **Influence Score** | 9/10 (in current elevated regime) |
| **Interaction** | Interacts with central bank gold buying (sanctions drive reserve diversification), VIX, USD (both safe havens can rally together), oil prices |
| **Can conflicts occur?** | Yes — "this time is different" risk. Each geopolitical crisis has unique characteristics. The 2020 COVID crisis saw gold initially sell off (cash-for-margin) before rallying. |
| **Typical market behaviour** | Initial spike (24-48h), then consolidation. If conflict persists, gold maintains elevated level. Resolution → gold gives back 12-17% (WGC Mid-Year 2025). |
| **Required data source** | GPR Index (Caldara & Iacoviello, Fed Board), WGC |
| **Free data availability** | Full — GPR Index downloadable free from Matteo Iacoviello's Fed Board page |
| **Existing open-source projects** | `geopolitical-risk-index` scrapers |
| **Existing APIs** | None standardized. Manual download required. |
| **Recommended integration** | **Build** — periodic downloader for GPR Index. It's a simple CSV. |

#### 3.7.2 Financial Sanctions

| Field | Value |
|-------|-------|
| **Category** | Geopolitical Risk |
| **Why it affects Gold** | Sanctions (especially on Russia 2022, Iran) demonstrated that USD/EUR reserves can be frozen. This drove central banks globally to diversify into gold. |
| **Direct / Indirect** | Indirect — drives CB demand, de-dollarization |
| **Relationship** | Positive — sanctions → gold reserve accumulation → higher gold prices |
| **Time Horizon** | Long-term (structural, persistent) |
| **Historical Importance** | Transformative. The freezing of Russia's $300B+ reserves in 2022 is arguably the single most important structural event for gold since the end of Bretton Woods. Arslanalp et al. (IMF WP/23/008): "Imposition of financial sanctions by the United States, UK, EU, and Japan is associated with an increase in the share of central bank reserves held in gold." |
| **Influence Score** | 9/10 (structural regime shift) |
| **Interaction** | Interacts with CB reserve management, de-dollarization, geopolitical alignment |
| **Required data source** | Global Sanctions Database (GSDB), Federal Register, EU sanctions lists |
| **Free data availability** | GSDB is free for academic use |
| **Recommended integration** | **Build** — include as a regime state variable (sanctions regime on/off). Not a continuous data feed. |

#### 3.7.3 Wars & Military Conflicts

| Field | Value |
|-------|-------|
| **Category** | Geopolitical Risk |
| **Why it affects Gold** | Wars trigger flight-to-safety, disrupt supply chains, create uncertainty about economic outlook, and often lead to expansionary fiscal/monetary policy. |
| **Direct / Indirect** | Direct (safe-haven) and Indirect (economic disruption) |
| **Relationship** | Positive — conflicts → gold ↑ |
| **Time Horizon** | Short-term (acute) to medium-term (protracted) |
| **Historical Importance** | Very high — Gulf War (1990), Iraq War (2003), Russia-Ukraine (2022-), Israel-Hamas (2023-), US-Iran (2026). Gold volatility spikes during these events. |
| **Influence Score** | 8/10 (during active conflicts) |
| **Interaction** | Interacts with oil prices (Persian Gulf conflicts spike oil), VIX, USD, central bank behavior |
| **Required data source** | GPR Index (sub-indices: GPRA = acts, GPRT = threats) |
| **Free data availability** | Included in GPR Index |
| **Recommended integration** | **Reuse** — GPR Index sub-components |

---

### 3.8 MACROECONOMIC CONDITIONS

#### 3.8.1 Global GDP / Economic Growth

| Field | Value |
|-------|-------|
| **Category** | Macroeconomic |
| **Why it affects Gold** | Long-term, gold's return is driven by global nominal GDP growth. The GLTER model (World Gold Council, 2025) shows GDP is the primary driver of gold price in the long run, with coefficient 2.8 (1% GDP growth → 2.8% gold return). |
| **Direct / Indirect** | Direct — economic component of gold demand (wealth, income, savings accumulate into gold) |
| **Relationship** | Positive — GDP growth → gold ↑ (long-run). Contradicts the "recession is good for gold" myth. The short-term is different. |
| **Time Horizon** | Long-term (5+ years) |
| **Historical Importance** | Highest for long-term returns. GLTER model predicts 8.6% annual avg return (1971-2024) vs. actual 8%. Gold has significantly outperformed both inflation (4%) and T-bills (4.4%) over 50+ years. |
| **Influence Score** | 9/10 (long-term), 3/10 (short-term) |
| **Interaction** | Interacts with global portfolio capitalisation (GLTER financial component). The joint model of GDP + global portfolio explains gold's long-run price path with cointegration. |
| **Can conflicts occur?** | Yes — short-term: recession fears → gold rallies (safe-haven). Long-term: GDP growth → gold rallies (wealth accumulation). The short-term safe-haven effect and the long-term growth effect can conflict cyclically. |
| **Typical market behaviour** | Short-term: recession scare → gold rallies. Long-term: sustained growth → gold appreciates as wealth accumulates into gold (jewellery, investment, CB reserves). |
| **Required data source** | World Bank (world GDP), FRED (US GDP: GDPC1), OECD |
| **Free data availability** | World Bank API (free), FRED API, OECD API |
| **Existing open-source projects** | `wbdata` (World Bank API), `fredapi`, `pandas-datareader` |
| **Existing APIs** | World Bank API v2, FRED API, OECD API |
| **Recommended integration** | **Reuse** — `wbdata` or `fredapi` for global GDP. This is a long-run model, not a daily input. |

#### 3.8.2 Recession Risk

| Field | Value |
|-------|-------|
| **Category** | Macroeconomic |
| **Why it affects Gold** | Gold historically performs during recessions (safe-haven, monetary easing expectations). Chicago Fed: "pessimism about future economic activity" is a key gold driver. A one standard deviation increase in pessimistic expectations (Michigan survey) raises gold 9.7%. |
| **Direct / Indirect** | Direct — safe-haven demand |
| **Relationship** | Positive — recession risk ↑ → gold ↑ (in the short/medium term) |
| **Time Horizon** | Short-to-medium term (6-24 months) |
| **Historical Importance** | High — 2008 GFC: gold initially sold off (liquidation) then rallied to $1,920. 2020 COVID: gold sold off in March then rallied to $2,070. |
| **Influence Score** | 7/10 |
| **Interaction** | Interacts with yield curve (inversion precedes recession), Fed policy (rate cuts), equity selloff (safe-haven), VIX. |
| **Required data source** | FRED (T10Y2Y yield curve), NBER recession dates (USREC), Michigan Consumer Sentiment |
| **Free data availability** | Full — FRED (USREC, UMCSENT) |
| **Existing open-source projects** | `fredapi` |
| **Existing APIs** | FRED API |
| **Recommended integration** | **Reuse** — `fredapi` for yield curve + recession indicators |

#### 3.8.3 Employment (Non-Farm Payrolls / Unemployment)

| Field | Value |
|-------|-------|
| **Category** | Macroeconomic / Labour Market |
| **Why it affects Gold** | NFP is the single most market-moving US data point. It drives Fed policy expectations, USD, and real yields. |
| **Direct / Indirect** | Indirect — via Fed policy, USD, real yields |
| **Relationship** | NFP beat → USD up, yields up → gold down. NFP miss → opposite. |
| **Time Horizon** | Short-term (intraday to weekly) |
| **Historical Importance** | Very high for short-term gold volatility. First Friday of every month is a gold event. |
| **Influence Score** | 6/10 |
| **Interaction** | Interacts with Fed policy expectations, wage data (average hourly earnings), participation rate |
| **Required data source** | FRED (PAYEMS — Nonfarm payrolls, UNRATE — Unemployment rate), BLS |
| **Free data availability** | Full — FRED API, BLS API |
| **Existing open-source projects** | `fredapi` |
| **Existing APIs** | FRED API |
| **Recommended integration** | **Reuse** — `fredapi`. Already in AurumAI as CSV. Replace with live. |

#### 3.8.4 Consumer Confidence / Sentiment

| Field | Value |
|-------|-------|
| **Category** | Macroeconomic / Sentiment |
| **Why it affects Gold** | Consumer pessimism drives safe-haven gold demand. Chicago Fed regression: Michigan Survey pessimistic expectations is a statistically significant gold driver. |
| **Direct / Indirect** | Indirect — safe-haven signal |
| **Relationship** | Negative — confidence ↓ → gold ↑ |
| **Time Horizon** | Medium-term |
| **Historical Importance** | Medium — Michigan Consumer Sentiment has predictive power for gold at medium frequencies |
| **Influence Score** | 5/10 |
| **Required data source** | FRED (UMCSENT), Conference Board |
| **Free data availability** | Full |
| **Recommended integration** | **Reuse** — `fredapi` |

---

### 3.9 COMMODITIES

#### 3.9.1 Crude Oil

| Field | Value |
|-------|-------|
| **Category** | Commodities |
| **Why it affects Gold** | Oil affects gold through three channels: (1) inflation channel — oil → CPI → gold hedge demand; (2) cost channel — mining/transportation costs; (3) portfolio channel — commodity substitution. |
| **Direct / Indirect** | Indirect (inflation) and Direct (mining cost) |
| **Relationship** | Historically positive. Wang & Chueh (2013): short-term bidirectional causality. |
| **Time Horizon** | Short-to-medium term |
| **Historical Importance** | Moderate-to-high. Gradient boosting study (Xiong & Zhang, 2024) found oil was the single most important factor in their gold price model (feature importance #1, R²=0.89 with oil+rates+DXY+GDP). However, MDPI (2026) using Lasso found oil's marginal contribution disappears once DXY is included. |
| **Influence Score** | 6/10 (debated — depends on methodology) |
| **Interaction** | Interacts with inflation, USD (both are dollar-denominated commodities), geopolitical risk (both respond to Middle East tensions). Oil-USD relationship complicates the gold-oil relationship. |
| **Can conflicts occur?** | Yes — oil supply shock (e.g., Iran conflict): oil spikes, but the effect on gold is ambiguous (inflation supports, recession risk also supports, but initial liquidation can hurt). |
| **Required data source** | FRED (WTI: WTI, or CL=F via Yahoo), EIA |
| **Free data availability** | Full — FRED (WTI series), Yahoo Finance |
| **Existing open-source projects** | `yfinance`, `fredapi` |
| **Existing APIs** | FRED API, Yahoo Finance, EIA API |
| **Recommended integration** | **Reuse** — `yfinance` for WTI futures or `fredapi` for WTI spot |

#### 3.9.2 Silver

| Field | Value |
|-------|-------|
| **Category** | Commodities / Precious Metals |
| **Why it affects Gold** | Gold-silver ratio is a widely watched indicator. Silver is both a precious metal (monetary/industrial dual nature). Silver extremes often lead gold extremes (silver is a "canary in the coal mine"). |
| **Direct / Indirect** | Indirect — portfolio substitution, sentiment signal |
| **Relationship** | Positive (co-movement) but with divergences at extremes. Gold/silver ratio compresses in bull markets. |
| **Time Horizon** | Short-to-medium term |
| **Historical Importance** | Moderate — gold-silver ratio signals sentiment extremes for the precious metals complex |
| **Influence Score** | 4/10 |
| **Interaction** | Interacts with industrial demand (silver's industrial uses create divergence from gold), speculative positioning |
| **Required data source** | LBMA silver price, COMEX silver futures |
| **Free data availability** | Full — Yahoo Finance (SI=F), LBMA |
| **Existing open-source projects** | `yfinance` |
| **Existing APIs** | Yahoo Finance |
| **Recommended integration** | **Reuse** — `yfinance` as derived indicator (gold/silver ratio) |

#### 3.9.3 Copper / Industrial Metals

| Field | Value |
|-------|-------|
| **Category** | Commodities / Industrial |
| **Why it affects Gold** | Copper is "Dr. Copper" — a leading indicator of global economic health. Rising copper → strong growth → mixed for gold (higher rates vs. higher wealth). Falling copper → recession fears → supports gold. |
| **Direct / Indirect** | Indirect — economic activity proxy |
| **Relationship** | Complex — higher copper can hurt gold (via rates expectations) or help (via wealth/inflation). |
| **Time Horizon** | Medium-term |
| **Historical Importance** | Low-moderate. Used more as a regime indicator than a direct gold driver. |
| **Influence Score** | 3/10 |
| **Interaction** | Interacts with global GDP, China demand, industrial cycle |
| **Required data source** | LME copper price, FRED (PCOPPUSDM) |
| **Free data availability** | Full |
| **Recommended integration** | **Reuse** — `fredapi` as regime indicator |

---

### 3.10 SUPPLY SIDE

#### 3.10.1 Mine Production

| Field | Value |
|-------|-------|
| **Category** | Supply |
| **Why it affects Gold** | Mine supply is the primary source of new gold. Supply is relatively inelastic (mine development takes 5-10 years). |
| **Direct / Indirect** | Direct — supply |
| **Relationship** | Usually negative (more supply = lower price) but very weak due to inelasticity |
| **Time Horizon** | Long-term (decades) |
| **Historical Importance** | Low in short-term. Mine supply grew only 1% in 2025 to 3,672t — muted response to 44% price increase. |
| **Influence Score** | 3/10 |
| **Interaction** | Interacts with gold price (lagged 5-10 years via mine capex decisions), energy costs (mining is energy-intensive) |
| **Required data source** | WGC Demand Trends (quarterly), Metals Focus |
| **Free data availability** | WGC publishes annual mine production data free |
| **Recommended integration** | **Build** — periodic download from WGC. Low frequency (annual/quarterly). |

#### 3.10.2 Recycled / Scrap Gold Supply

| Field | Value |
|-------|-------|
| **Category** | Supply |
| **Why it affects Gold** | Recycling provides ~30% of total supply. It acts as a natural price stabilizer: high prices incentivize scrap sales, capping rallies. |
| **Direct / Indirect** | Direct — supply |
| **Relationship** | Positive — price ↑ → recycling ↑ (muted in current cycle: +3% in 2025 vs. 67% price increase) |
| **Time Horizon** | Short-to-medium term (quick response to price) |
| **Historical Importance** | Moderate — typically provides elastic supply response, but the current cycle is unprecedented in its muted response (WGC Q1 2026: recycling +5% vs. 70% price increase). |
| **Influence Score** | 4/10 |
| **Interaction** | Interacts with price level, jewellery demand (old-gold exchange), economic distress selling |
| **Required data source** | WGC Demand Trends |
| **Free data availability** | Yes — WGC quarterly |
| **Recommended integration** | **Build** — periodic download. Not real-time. |

---

### 3.11 DEMAND SECTORS

#### 3.11.1 Jewellery Demand

| Field | Value |
|-------|-------|
| **Category** | Demand — Consumer |
| **Why it affects Gold** | Jewellery is the largest single demand category historically (~50% of total). It is price-sensitive and income-sensitive. |
| **Direct / Indirect** | Direct — physical demand |
| **Relationship** | Negative — price ↑ → jewellery volume ↓ (but value ↑). In 2024: volumes −11%, spend +9%. In 2025: volumes −19% to 1,542t, spend +18% to $172bn. |
| **Time Horizon** | Medium-term (quarterly, seasonal) |
| **Historical Importance** | Very high for long-term equilibrium. However, investment demand has now structurally overtaken jewellery as the marginal price setter. |
| **Influence Score** | 5/10 (declining as share of demand shifts toward investment) |
| **Interaction** | Interacts with GDP (income), price level, seasonality (Indian wedding season, Chinese New Year, Diwali, Akshaya Tritiya), gold-as-investment substitution |
| **Required data source** | WGC Demand Trends (country-level), Metals Focus |
| **Free data availability** | Yes — WGC quarterly data free |
| **Recommended integration** | **Build** — periodic download from WGC. Quarterly frequency. |

#### 3.11.2 Bar & Coin Investment

| Field | Value |
|-------|-------|
| **Category** | Demand — Investment |
| **Why it affects Gold** | Bar and coin demand represents retail investor flows into physical gold. At 1,374t in 2025 (12-year high), it is the second-largest demand category. |
| **Direct / Indirect** | Direct — physical demand |
| **Relationship** | Positive — bar/coin demand supports gold price |
| **Time Horizon** | Medium-term (reacts to price with 1-2 month lag) |
| **Historical Importance** | High — 2025 was a record year for bar/coin demand in many markets. China: 67% y/y growth to a record 207t in Q1 2026. India: 34% y/y growth. |
| **Influence Score** | 5/10 |
| **Interaction** | Interacts with price momentum (dip-buying behavior), geopolitical risk, currency weakness, negative real deposit rates |
| **Required data source** | WGC Demand Trends (country-level) |
| **Free data availability** | Yes — WGC quarterly |
| **Recommended integration** | **Build** — periodic download |

#### 3.11.3 Technology / Industrial Demand

| Field | Value |
|-------|-------|
| **Category** | Demand — Industrial |
| **Why it affects Gold** | Gold is used in electronics (connectors, bonding wires), AI chips (2024-2026 growth driver), and other industrial applications. |
| **Direct / Indirect** | Direct — industrial demand |
| **Relationship** | Positive — industrial demand ↑ → gold supported |
| **Time Horizon** | Medium-term (tied to global tech cycle) |
| **Historical Importance** | Moderate but growing. Technology demand reached 322.8t in 2025 (+7% y/y), driven by AI adoption. |
| **Influence Score** | 3/10 |
| **Interaction** | Interacts with global tech cycle, AI investment, consumer electronics |
| **Required data source** | WGC Demand Trends |
| **Free data availability** | Yes |
| **Recommended integration** | **Build** — periodic download |

---

### 3.12 CHINA

#### 3.12.1 Chinese Gold Demand (Jewellery + Investment)

| Field | Value |
|-------|-------|
| **Category** | Country-Specific |
| **Why it affects Gold** | China is the world's largest gold consumer and the dominant marginal buyer. Chinese bar/coin demand hit a record 207t in Q1 2026 (+67% y/y). The PBOC was a major gold buyer. |
| **Direct / Indirect** | Direct — physical demand, also indirect via PBOC reserves |
| **Relationship** | Positive — Chinese buying supports gold |
| **Time Horizon** | All horizons |
| **Historical Importance** | Very high — China's gold market liberalization (2002), the rise of the Shanghai Gold Exchange, and the PBOC's sustained gold purchases have been transformative. |
| **Influence Score** | 7/10 |
| **Interaction** | Interacts with Chinese GDP growth, RMB exchange rate, Chinese real estate market (gold as alternative investment), Chinese equity market, PBOC reserve policy |
| **Required data source** | WGC China demand data, SGE withdrawal data, PBoC reserve data |
| **Free data availability** | WGC data free. SGE data partially available. |
| **Recommended integration** | **Build** — China-specific demand data from WGC. High priority given China's outsize role. |

#### 3.12.2 PBOC Gold Purchases

| Field | Value |
|-------|-------|
| **Category** | Central Banks / Country-Specific |
| **Why it affects Gold** | The PBOC is among the largest central bank buyers, and its purchases are closely watched as a signal of RMB internationalization and reserve diversification. |
| **Direct / Indirect** | Direct — CB demand |
| **Relationship** | Positive |
| **Time Horizon** | Medium-term (monthly reserve data) |
| **Historical Importance** | Very high — China and Russia are the two largest central bank gold accumulators (Weiss, Fed IFDP 1420) |
| **Influence Score** | 7/10 |
| **Required data source** | PBOC, WGC |
| **Free data availability** | PBOC publishes monthly reserve data |
| **Recommended integration** | **Build** — PBOC data scraper. Included in CBI package. |

#### 3.12.3 Shanghai Gold Exchange (SGE) Premium

| Field | Value |
|-------|-------|
| **Category** | Country-Specific / Market Structure |
| **Why it affects Gold** | The SGE premium/discount over LBMA indicates Chinese physical demand pressure. Large premiums signal aggressive buying. |
| **Direct / Indirect** | Indirect — signal of Chinese demand intensity |
| **Relationship** | Premium ↑ → strong Chinese demand → bullish for gold |
| **Time Horizon** | Short-to-medium term |
| **Historical Importance** | Moderate — periods of large SGE premiums (2013, 2020) coincided with strong Chinese buying |
| **Influence Score** | 4/10 |
| **Required data source** | SGE, Bloomberg, WGC |
| **Free data availability** | Limited — some data from WGC |
| **Recommended integration** | **Build** — derive from LBMA vs. SGE pricing data |

---

### 3.13 INDIA

#### 3.13.1 Indian Gold Demand (Jewellery + Investment)

| Field | Value |
|-------|-------|
| **Category** | Country-Specific |
| **Why it affects Gold** | India is the second-largest gold consumer. Cultural factors (wedding season, Akshaya Tritiya, Dhanteras, Diwali) create predictable seasonal demand. Investment demand structurally rose to 70% of total in Q1 2026. |
| **Direct / Indirect** | Direct — physical demand |
| **Relationship** | Positive |
| **Time Horizon** | Medium-term (seasonal) to long-term (structural income growth) |
| **Historical Importance** | Very high. India gold demand was 151t in Q1 2026. A structural shift is underway: investment now dominates jewellery. A 9% import duty hike in May 2026 impacted demand. |
| **Influence Score** | 6/10 |
| **Interaction** | Interacts with INR/USD exchange rate, Indian monsoon (rural income), import duties, gold price level (price elasticity of jewellery demand) |
| **Required data source** | WGC India gold demand data, India Ministry of Commerce (import data), MCX gold price |
| **Free data availability** | WGC data free. Indian government data is public. |
| **Recommended integration** | **Build** — WGC data downloader + India import/export monitor |

---

### 3.14 LIQUIDITY & MONEY

#### 3.14.1 Global Money Supply (M2)

| Field | Value |
|-------|-------|
| **Category** | Monetary / Liquidity |
| **Why it affects Gold** | Money supply expansion = more currency chasing the same real assets = gold should appreciate. M2 growth correlates with gold over long horizons. |
| **Direct / Indirect** | Indirect — monetary debasement channel |
| **Relationship** | Positive — M2 growth → gold ↑ (over long cycles) |
| **Time Horizon** | Long-term |
| **Historical Importance** | Moderate — M2 growth explains some of gold's long-run appreciation |
| **Influence Score** | 5/10 |
| **Interaction** | Interacts with QE, fiscal deficits, velocity of money |
| **Required data source** | FRED (M2SL, M2NS) |
| **Free data availability** | Full |
| **Recommended integration** | **Reuse** — `fredapi` |

#### 3.14.2 Global Liquidity (G4 Central Bank Balance Sheets)

| Field | Value |
|-------|-------|
| **Category** | Monetary / Liquidity |
| **Why it affects Gold** | Combined balance sheets of the Fed, ECB, BOJ, and PBOC drive global liquidity conditions. Expansion supports gold via lower real yields, weaker USD, and safe-asset demand. |
| **Direct / Indirect** | Indirect — comprehensive liquidity channel |
| **Relationship** | Positive |
| **Time Horizon** | Medium-to-long term |
| **Historical Importance** | High — post-GFC QE strongly correlated with EMDE central bank gold buying (BIS WP 906) |
| **Influence Score** | 7/10 |
| **Required data source** | FRED (WALCL), ECB, BOJ, PBOC balance sheets |
| **Free data availability** | Full for Fed, ECB, BOJ. Partial for PBOC. |
| **Recommended integration** | **Adapt** — combine individual CB balance sheet adapters into a composite index |

---

### 3.15 MARKETS & VOLATILITY

#### 3.15.1 VIX (CBOE Volatility Index)

| Field | Value |
|-------|-------|
| **Category** | Market / Volatility |
| **Why it affects Gold** | VIX = investor fear gauge. Rising VIX → flight-to-safety → gold benefits. However, extreme VIX spikes (2008, 2020 March) can trigger forced liquidation of gold as investors sell everything for cash. |
| **Direct / Indirect** | Direct — safe-haven demand. But asymmetric: positive VIX shocks → gold up (safe-haven). |
| **Relationship** | Asymmetric positive — Löwen et al. (2021): "positive shocks in VIX cause positive shocks in GVZ." Hood & Malik (2013): VIX is a superior hedge to gold. |
| **Time Horizon** | Short-term (days to weeks) |
| **Historical Importance** | High. VIX is the most-watched risk indicator. Gold-VIX relationship is state-dependent: moderate VIX spikes → gold rallies; extreme VIX (80+) → gold sells off initially (cash-for-margin). |
| **Influence Score** | 6/10 |
| **Interaction** | Interacts with equity selloffs, USD (both safe havens can rally), geopolitical risk |
| **Can conflicts occur?** | Yes — during liquidity crises (March 2020), gold sold off with equities (everything dollar sold). Gold is a safe haven for value, not for liquidity. |
| **Typical market behaviour** | VIX 15-25: gold stable. VIX 25-40: gold rallies (flight to safety). VIX 40+: gold may sell off initially, then recover. |
| **Required data source** | CBOE, Yahoo Finance (^VIX) |
| **Free data availability** | Full — Yahoo Finance |
| **Existing open-source projects** | `yfinance` |
| **Existing APIs** | Yahoo Finance |
| **Recommended integration** | **Reuse** — `yfinance` for VIX |

#### 3.15.2 GVZ (Gold Volatility Index)

| Field | Value |
|-------|-------|
| **Category** | Market / Volatility |
| **Why it affects Gold** | GVZ is the implied volatility of gold options (CBOE Gold ETF Volatility Index). It measures fear in the gold market itself. |
| **Direct / Indirect** | Direct — gold-specific fear gauge |
| **Relationship** | GVZ ↑ during gold selloffs and gold rallies (both directions create volatility) |
| **Time Horizon** | Short-term |
| **Historical Importance** | Moderate — less liquid than VIX but gold-specific |
| **Influence Score** | 4/10 |
| **Required data source** | CBOE, Yahoo Finance (^GVZ) |
| **Free data availability** | Full |
| **Recommended integration** | **Reuse** — `yfinance` |

#### 3.15.3 Equity Market (S&P 500 / Global Equities)

| Field | Value |
|-------|-------|
| **Category** | Market / Cross-Asset |
| **Why it affects Gold** | Gold competes with equities for portfolio allocation. During risk-off, investors rotate from stocks to gold. The correlation is time-varying — typically negative during crises, weakly positive during normal periods. |
| **Direct / Indirect** | Indirect — portfolio allocation channel |
| **Relationship** | Typically negative during crises. MDPI (2026) uses Dow Jones as "asset substitution and risk-on/risk-off sentiment" proxy. |
| **Time Horizon** | Short-to-medium term |
| **Historical Importance** | Moderate. Gold's correlation with equities was positive in the 1990s (gold as commodity), turned negative in the 2000s (gold as anti-dollar), and has been state-dependent since. |
| **Influence Score** | 5/10 |
| **Interaction** | Interacts with VIX, recession risk, risk appetite, Fed policy |
| **Required data source** | Yahoo Finance (^GSPC), FRED (SP500) |
| **Free data availability** | Full |
| **Existing open-source projects** | `yfinance`, `fredapi` |
| **Existing APIs** | Yahoo Finance, FRED API |
| **Recommended integration** | **Reuse** — `yfinance` |

#### 3.15.4 Options Market (Gold Put/Call Ratio, Skew)

| Field | Value |
|-------|-------|
| **Category** | Market / Derivatives |
| **Why it affects Gold** | Gold options market sentiment (put/call ratio, 25-delta skew) signals positioning and hedging demand among sophisticated investors. |
| **Direct / Indirect** | Indirect — sentiment signal |
| **Relationship** | Extreme put buying → bearish sentiment (contrarian bullish for gold). |
| **Time Horizon** | Short-term |
| **Historical Importance** | Low-moderate for gold compared to equities |
| **Influence Score** | 3/10 |
| **Required data source** | CME (gold options OI and volume data), Bloomberg |
| **Free data availability** | Limited — CME provides some volume data free |
| **Recommended integration** | **Build** — requires CME data. Lower priority. |

---

### 3.16 SEASONALITY

#### 3.16.1 Calendar Seasonality (Monthly Patterns)

| Field | Value |
|-------|-------|
| **Category** | Seasonality |
| **Why it affects Gold** | Gold exhibits statistically significant seasonal patterns driven by cultural factors (Indian weddings, Chinese New Year, Diwali), fiscal calendars, and portfolio rebalancing. |
| **Direct / Indirect** | Direct — predictable physical demand cycles |
| **Relationship** | January: strongest month (+2.8% avg, p=0.047). June/July: weakest (−1.2% to −2%). August: strong (+1.8%). Q1: +4.0% average. May-June: −1.0%. |
| **Time Horizon** | Seasonal (annual cycle) |
| **Historical Importance** | Moderate. Baur (2013) found an "autumn effect" (September, November). Gülseven (2020) found a stronger "winter effect" (January, February). January seasonality is the most statistically robust (p<0.05 per bootstrap analysis). Seasonality360: Jan 5-Mar 10 long strategy: 75% win rate, +4.2% avg return, 2.1 profit factor (20-year data). |
| **Influence Score** | 4/10 (reliable but modest magnitude) |
| **Interaction** | Interacts with Indian festival calendar, Chinese New Year, Western fiscal year-end, portfolio rebalancing |
| **Can conflicts occur?** | Yes — macro shocks can completely override seasonality |
| **Required data source** | LBMA Gold Price (1971-present), WGC |
| **Free data availability** | WGC historical gold price data free |
| **Existing open-source projects** | Various seasonality analysis notebooks on GitHub |
| **Existing APIs** | WGC Goldhub |
| **Recommended integration** | **Build** — calendar seasonality module. Empirical data from LBMA, recompute annually. |

#### 3.16.2 East-West Divergence (Overnight vs. Intraday Returns)

| Field | Value |
|-------|-------|
| **Category** | Market Microstructure |
| **Why it affects Gold** | A persistent anomaly: nearly all of gold's long-term appreciation occurs during overnight hours (Asian/early European session). Intraday (European/US session) shows cumulative losses. |
| **Direct / Indirect** | Indirect — market structure signal |
| **Relationship** | Overnight CAGR: +13.83% (1968-2024). Intraday CAGR: −4.73%. The divergence reveals different buyer/seller bases geographically. |
| **Time Horizon** | Long-term structural pattern |
| **Historical Importance** | Discovered by Haupt (2025) on GitHub using LBMA AM/PM fix data. Reproducible across gold, platinum, palladium. |
| **Influence Score** | 3/10 (more a diagnostic than a predictor) |
| **Required data source** | LBMA AM and PM fixes |
| **Free data availability** | LBMA fix data — historically free, but IBA licensing changes in 2025 restrict historical LBMA data |
| **Existing open-source projects** | `Robin-Haupt-1/lbma-east-west-divergence` (GitHub, MIT) |
| **Recommended integration** | **Reuse** — adopt the existing open-source analysis from `lbma-east-west-divergence` as a diagnostic module |

---

### 3.17 MACRO REGIMES

#### 3.17.1 Macroeconomic Regime (Stagflation / Goldilocks / Reflation / Disinflation)

| Field | Value |
|-------|-------|
| **Category** | Macro Regime |
| **Why it affects Gold** | Gold performs differently in each macro regime. Stagflation (low growth + high inflation) is gold's best regime. Goldilocks (moderate growth + moderate inflation) is weakest. |
| **Direct / Indirect** | Indirect — regime context modulates all other factors |
| **Relationship** | Stagflation → strongest gold. Disinflation → neutral/mixed. Deflation → initially positive then negative. |
| **Time Horizon** | Medium-term (6-24 months) |
| **Historical Importance** | High. The macro regime determines which factors dominate. In the 1970s, inflation drove gold. In 2001-2012, real yields drove gold. In 2022-2026, central bank buying and geopolitics drove gold. |
| **Influence Score** | 8/10 (as a context modulator) |
| **Interaction** | Interacts with ALL factors. Regime determines factor sensitivities. Example: in a high-inflation regime, CPI data is the dominant gold driver. In a low-inflation regime, real yields dominate. |
| **Required data source** | Composite: CPI (CPIAUCSL), GDP (GDPC1), Unemployment (UNRATE) from FRED |
| **Free data availability** | Full |
| **Existing open-source projects** | `fredapi` |
| **Existing APIs** | FRED API |
| **Recommended integration** | **Reuse** — AurumAI's `CompositeScoreBuilder` + `MacroRegimeDetector` already implements this. Currently dormant — must be activated and wired into production. |

---

### 3.18 MARKET MOMENTUM & TECHNICAL

#### 3.18.1 Trend / Momentum

| Field | Value |
|-------|-------|
| **Category** | Technical / Behavioral |
| **Why it affects Gold** | The GRAM model includes "Momentum & Trends" as one of four thematic driver categories. Gold exhibits time-series momentum — past returns predict future returns (Moskowitz, Ooi, Pedersen 2012). |
| **Direct / Indirect** | Direct — autocorrelation in gold returns |
| **Relationship** | Positive — gold trends persist (1-12 month horizons) |
| **Time Horizon** | Short-to-medium term (1-12 months) |
| **Historical Importance** | High. WGC GRAM: momentum accounting for ~4% of monthly return in May 2021. The ~2-year trend in gold from $2,000 (early 2024) to $4,746 (April 2026) is partly momentum-driven. |
| **Influence Score** | 6/10 |
| **Interaction** | Interacts with ETF flows (positive feedback loop), COT positioning (trend-following specs), positioning extremes |
| **Required data source** | Gold price history. Derived metric. |
| **Free data availability** | WGC, LBMA, Yahoo Finance all free |
| **Recommended integration** | **Build** — momentum/trend is a derived metric. Simple computation from LBMA gold price. Already partially implemented in the existing codebase via technical indicators. |

---

## 4. Influence Hierarchy

### Tier 1: Regime-Defining Factors (Structural)
*These factors determine the macro environment in which all other factors operate.*

| Factor | Score | Why Tier 1 |
|--------|-------|------------|
| Central Bank Net Purchases | 10/10 | Structural buyer, >1,000t/year, price-insensitive |
| US Dollar (DXY) | 9/10 | Transmits macro through pricing, opportunity cost, and liquidity channels |
| Real Yields (10Y TIPS) | 9→7/10 | Historically dominant, partially broken post-2022 but still essential |
| Geopolitical Risk / Sanctions | 9/10 | Driving CB buying, safe-haven demand, and the structural regime shift |
| Global GDP (Long-term) | 9/10 | Primary long-run gold return driver (GLTER model) |

### Tier 2: Cyclical Factors (Market-Cycle)
*These factors drive gold within the structural regime.*

| Factor | Score |
|--------|-------|
| Inflation (CPI/Core PCE) | 8/10 |
| QE / Central Bank Balance Sheets | 8/10 |
| Federal Funds Rate | 8/10 |
| Gold ETF Holdings & Flows | 8/10 |
| Macroeconomic Regime | 8/10 |
| Global Liquidity (G4 Balance Sheets) | 7/10 |
| Nominal Yields (10Y) | 7/10 |
| Managed Money COT Positioning | 7/10 |
| China Gold Demand | 7/10 |
| PBOC Gold Purchases | 7/10 |
| Recession Risk | 7/10 |

### Tier 3: Tactical Factors (Short-Term)
*These factors drive short-term deviations from equilibrium.*

| Factor | Score |
|--------|-------|
| Crude Oil | 6/10 |
| India Gold Demand | 6/10 |
| VIX | 6/10 |
| Momentum / Trend | 6/10 |
| Yield Curve (2s10s) | 6/10 |
| Employment (NFP) | 6/10 |
| Swap Dealer Positioning | 6/10 |
| Consumer Confidence | 5/10 |
| Global M2 Money Supply | 5/10 |
| Equity Market (S&P 500) | 5/10 |
| Jewellery Demand | 5/10 |
| Bar & Coin Demand | 5/10 |

### Tier 4: Supplementary Factors
*These provide marginal insight or context.*

| Factor | Score |
|--------|-------|
| SGE Premium | 4/10 |
| GVZ (Gold Volatility) | 4/10 |
| Silver / Gold Ratio | 4/10 |
| Seasonality | 4/10 |
| Recycling Supply | 4/10 |
| Mine Production | 3/10 |
| Technology Demand | 3/10 |
| Copper / Industrial Metals | 3/10 |
| Options Market (Put/Call) | 3/10 |
| East-West Divergence | 3/10 |

---

## 5. Dependency Graph

```
                        ┌──────────────────────────────────────────┐
                        │           GEOPOLITICAL RISK              │
                        │  (Sanctions, Wars, GPR Index, US-Iran)   │
                        └────────────┬─────────────────────────────┘
                                     │
                                     ▼
              ┌─────────────────────────────────────────────┐
              │         CENTRAL BANK GOLD RESERVES          │
              │  (Structural Buyer: 1,000t+ / year 2022-24) │
              └────────────────────┬────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        FEDERAL RESERVE POLICY                         │
│  (Fed Funds Rate → QE/QT → Forward Guidance → Balance Sheet Policy)  │
└────┬─────────────┬──────────────┬──────────────┬─────────────────────┘
     │             │              │              │
     ▼             ▼              ▼              ▼
┌─────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐
│  USD    │ │  REAL    │ │ INFLATION  │ │  GLOBAL      │
│ (DXY)   │ │ YIELDS   │ │ (CPI/PCE)  │ │  LIQUIDITY   │
│         │ │ (TIPS)   │ │            │ │  (G4 CBs)    │
└────┬────┘ └────┬─────┘ └──────┬─────┘ └──────┬───────┘
     │          │              │              │
     ▼          ▼              ▼              ▼
┌────────────────────────────────────────────────────────────────────┐
│                         GOLD PRICE                                   │
│  Determined by equilibrium of:                                       │
│    • Investment Demand (ETF + Bar/Coin + OTC)                        │
│    • Central Bank Demand                                             │
│    • Jewellery Demand                                                │
│    • Technology Demand                                               │
│    • Mine Supply + Recycling                                         │
└────┬────────────────────────────────────────────────────────────────┘
     │                          │
     ▼                          ▼
┌──────────┐           ┌───────────────┐
│ SPECUL.  │           │ PHYSICAL      │
│ POSITION │           │ SUPPLY/DEMAND │
│ (COT)    │           │               │
└──────────┘           └───────────────┘
     │
     ▼
┌──────────┐
│ MOMENTUM │
│ (ETF Flo │
│  + COT)  │
└──────────┘
```

**Key feedback loops:**
1. **ETF Flow → Momentum → ETF Flow:** Rising gold → ETF inflows → more gold buying → higher gold.
2. **Central Bank Buying → Price Support → CB Confidence:** Lower price risk → more CB accumulation.
3. **Dollar Weak → Gold Strong → Dollar Weaker:** Gold appreciation signals dollar debasement, reinforcing the narrative.
4. **COT Extreme → Reversal:** Crowded positioning creates the fuel for the next correction.

---

## 6. High-Priority Factors (Influence Score ≥ 8)

These factors should be the core of AurumAI's gold intelligence system:

| Rank | Factor | Score | AurumAI Status | Action Required |
|------|--------|-------|----------------|-----------------|
| 1 | Central Bank Net Purchases | 10 | **Gap** — contract exists in docs, no implementation | **Build** `CBIAdapter` for WGC/IMF CB gold data |
| 2 | US Dollar (DXY) | 9 | Partial — `DXYContextEnricher` uses static CSV | **Replace** CSV with live FRED API |
| 3 | Geopolitical Risk / Sanctions | 9 | **Gap** — no implementation | **Build** GPR Index downloader + sanctions regime classifier |
| 4 | Global GDP (GLTER) | 9 | **Gap** — no integration | **Build** GLTER model for long-run equilibrium anchor |
| 5 | Real Yields (10Y TIPS) | 9→7 | Partial — `YieldContextEnricher` uses static CSV | **Replace** CSV with live FRED API; add regime-aware correlation |
| 6 | Inflation (CPI/Expectations) | 8 | Partial — `CompositeScoreBuilder` uses static CSV | **Replace** CSV with live FRED API |
| 7 | QE / Central Bank Balance Sheets | 8 | **Gap** | **Build** composite G4 liquidty index from individual CB data |
| 8 | Federal Funds Rate | 8 | Partial — Fed data available via `data/economic/DFF.csv` | **Replace** CSV with live FRED API |
| 9 | Gold ETF Holdings & Flows | 8 | **Gap** — contract `ETFFlowMonitor` exists in docs, no implementation | **Build** `ETFFlowMonitor` adapter from WGC Goldhub |
| 10 | Macroeconomic Regime | 8 | Implemented but **dormant** — `MacroRegimeDetector` not wired into production | **Activate** — wire `CompositeScoreBuilder` + `MacroRegimeDetector` into production pipeline |

---

## 7. Low-Priority Factors (Influence Score ≤ 3)

These factors should NOT be implemented in the initial phase:

| Factor | Score | Reason |
|--------|-------|--------|
| Mine Production | 3 | Supply response is inelastic and slow. Annual data suffices. |
| Technology Demand | 3 | Small share (~6%) of total demand, stable growth. |
| Copper / Industrial Metals | 3 | Weak direct relationship, redundant with GDP and PMI. |
| Options Market (Put/Call) | 3 | Low predictive power for gold, data cost/availability issues. |
| East-West Divergence | 3 | Diagnostic/analytical tool, not a predictive factor. |
| Recycling Supply | 4 | Muted response in current cycle reduces its importance. |
| SGE Premium | 4 | Useful signal but data availability is limited. |

---

## 8. Missing Free Data

The following critical data sources are available for free but not currently integrated into AurumAI:

| Data Series | Provider | Free? | Integration |
|-------------|----------|-------|-------------|
| US Treasury yields (DGS10, DGS2, DFF) | FRED API | Yes | `fredapi` |
| TIPS yields (DFII10) | FRED API | Yes | `fredapi` |
| Breakeven inflation (T10YIE) | FRED API | Yes | `fredapi` |
| CPI / Core CPI (CPIAUCSL, CPILFESL) | FRED API | Yes | `fredapi` |
| Core PCE (PCEPILFE) | FRED API | Yes | `fredapi` |
| GDP / GDPC1 | FRED API | Yes | `fredapi` |
| NFP / Unemployment (PAYEMS, UNRATE) | FRED API | Yes | `fredapi` |
| Fed Balance Sheet (WALCL) | FRED API | Yes | `fredapi` |
| M2 Money Supply (M2SL) | FRED API | Yes | `fredapi` |
| Broad USD Index (DTWEXBGS) | FRED API | Yes | `fredapi` |
| VIX | Yahoo Finance | Yes | `yfinance` |
| S&P 500 | Yahoo Finance | Yes | `yfinance` |
| WTI Oil | Yahoo Finance/FRED | Yes | `yfinance` / `fredapi` |
| Gold ETF Holdings & Flows | WGC Goldhub | Yes (registration) | WGC Goldhub API |
| Central Bank Gold Reserves | WGC / IMF IFS | Yes | WGC quarterly data |
| COT Report (COMEX Gold) | CFTC Website | Yes | CFTC bulk data |
| GPR Geopolitical Risk Index | Fed Board (Iacoviello) | Yes | CSV download |
| World GDP | World Bank API | Yes | `wbdata` / World Bank API |
| NBER Recession Dates | FRED (USREC) | Yes | `fredapi` |
| Consumer Sentiment (UMCSENT) | FRED API | Yes | `fredapi` |
| Yield Curve (T10Y2Y) | FRED API | Yes | Derived from DGS10/DGS2 |
| LBMA Gold Price (daily/weekly) | WGC / IBA | Historically free; IBA restrictions may apply | WGC Goldhub |

---

## 9. Existing OSS Ecosystem

### 9.1 Data Access Libraries

| Project | License | Stars | Description | Reuse? |
|---------|---------|-------|-------------|--------|
| `fredapi` (mortada) | Apache 2.0 | 800+ | Python FRED API wrapper | **Yes** — core data layer |
| `fredq` | MIT | New | Typed FRED client with pydantic, CLI | Consider |
| `yfinance` | Apache 2.0 | 14k+ | Yahoo Finance data | **Yes** — VIX, DXY, gold futures, oil |
| `pandas-datareader` | BSD | 3k+ | Multi-source reader | Consider |
| `wbdata` | MIT | 200+ | World Bank API | **Yes** — global GDP |
| `exchange_calendars` | MIT | 400+ | Exchange calendars | Consider for event dates |
| `cot-report` (various) | Mixed | Various | CFTC COT scrapers | **Adapt** — use as reference |
| `geopolitical-risk-index` | Various | Various | GPR scrapers | Reference for implementation |

### 9.2 Gold-Specific Projects

| Project | Description | Reuse? |
|---------|-------------|--------|
| `JasonBuildAI/GoldMind` (62★) | LangChain multi-agent gold analysis with GLM-4 + DeepSeek | Reference only — LLM-driven, opposite architecture |
| `Kishore-a77/Project-GOLD` (CN) | Production-grade ensemble (Chronos-T5 + N-HiTS) | Reference — reuse the Chronos-T5 model approach if needed |
| `ASAPUI/MARGINS` | Monte Carlo gold simulation, 6 stochastic models, walk-forward backtest | Reference — backtest methodology |
| `RuthvikDacha/Gold-Price-Prediction` | ML pipeline: RF + XGBoost + SHAP + PSI drift + MLflow | Reference — feature engineering |
| `sohithchanumolu/goldpluse-ai` | AI-powered gold intelligence pipeline | Reference |
| `MubashirShafique/Gold-Trend-Predictor` | XGBoost, DVC, FastAPI, Flutter app | Reference |
| `Robin-Haupt-1/lbma-east-west-divergence` | LBMA AM/PM fix divergence analysis | **Reuse** — analytical methodology |
| `shahram8708/Gold-Price-Analysis-and-Forecasting` | Comprehensive gold analysis notebooks | Reference |
| `ta-lib` (BSD) | Industry standard technical indicators, C-optimized | **Reuse** — replace AurumAI's custom indicator code |

### 9.3 Risk & Portfolio Libraries

| Project | License | Description | Reuse? |
|---------|---------|-------------|--------|
| `pyextremes` | MIT | Extreme value theory for tail risk | **Yes** — replace TailRiskDetector |
| `riskfolio-lib` | MIT | 8+ portfolio optimization methods | **Yes** — replace RiskParitySizer |
| `empyrical` | Apache 2.0 | 40+ risk metrics | **Yes** — replace VaR/CVaR if desired |
| `pyportfolioopt` | MIT | Mean-variance, risk parity, CLA | Consider |

---

## 10. Final Recommendations for AurumAI Architecture

### 10.1 Immediate (Wave 1 — Data Modernization)

Replace all static CSV file sources with live API adapters. This is the single highest-leverage change:

| Current | Replace With | Effort | Impact |
|---------|-------------|--------|--------|
| `data/economic/CPIAUCSL.csv` | `fredapi.get_series('CPIAUCSL')` | 2h | Eliminates stale data, enables auto-update |
| `data/economic/DFF.csv` | `fredapi.get_series('DFF')` | 1h | Same |
| `data/economic/DGS10.csv` | `fredapi.get_series('DGS10')` | 1h | Same |
| `data/economic/GDP.csv` | `fredapi.get_series('GDPC1')` | 1h | Same |
| `data/economic/PAYEMS.csv` | `fredapi.get_series('PAYEMS')` | 1h | Same |
| `data/economic/PMI.csv` | `fredapi.get_series('NAPM')` | 1h | Same |
| `data/economic/PPIACO.csv` | `fredapi.get_series('PPIACO')` | 1h | Same |
| `data/economic/UNRATE.csv` | `fredapi.get_series('UNRATE')` | 1h | Same |
| `data/context/dxy/dxy.csv` | `fredapi.get_series('DTWEXBGS')` | 1h | Same |
| `data/calendar/fomc_meetings.csv` | FRED + Fed API | 4h | Eliminates manual calendar updates |
| `data/calendar/CPI_releases.csv` | BLS release calendar | 2h | Same |

**Est. effort: ~16h for complete data modernization.**

### 10.2 Short-Term (Wave 2 — Fill Critical Gaps)

| Capability | Build / Adapt | Priority |
|-----------|---------------|----------|
| **CB Gold Reserve Adapter** | **Build** — `CBIAdapter` for WGC/IMF data | **Critical** — Tier-1 factor, documented contract exists |
| **ETF Flow Adapter** | **Build** — `ETFFlowMonitor` from WGC Goldhub | **Critical** — Tier-2 factor, contract exists |
| **COT Report Adapter** | **Adapt** — CFTC bulk data parser | **High** — Tier-2 factor, contract exists |
| **GPR Index Adapter** | **Build** — periodic download from Iacoviello page | **High** — Tier-1 factor |
| **GLTER Model** | **Build** — long-run equilibrium anchor | **High** — provides fair-value context |

### 10.3 Medium-Term (Wave 3 — Activate & Enhance)

| Capability | Action | Priority |
|-----------|--------|----------|
| **MacroRegimeDetector Activation** | Wire into production pipeline | **High** — already built, currently dormant |
| **CompositeScoreBuilder Activation** | Wire into production | **High** — feeds regime detector |
| **TA-Lib Migration** | Replace custom indicators | **Medium** — reduces maintenance, improves accuracy |
| **pyextremes Migration** | Replace TailRiskDetector | **Medium** — more robust EVT |
| **riskfolio-lib Migration** | Replace RiskParitySizer | **Low** — current implementation works |
| **Seasonality Module** | Build empirical calendar | **Low** — marginal predictive value |
| **East-West Divergence Module** | Adopt existing OSS | **Low** — diagnostic tool |

### 10.4 Architecture Principles Moving Forward

1. **Every external data source must be accessed through an adapter**, never as a committed CSV file.
2. **All adapters implement a `DataProvider` protocol** so they can be swapped, cached, and tested with deterministic fixtures.
3. **The regime detector must be the first stage** of every pipeline execution — factor sensitivities are regime-dependent.
4. **Positioning data (COT, ETF flows) must be read in context** — extremes alone mean nothing without the macro backdrop (DXY, real yields).
5. **The long-run GLTER model provides the anchor** — short-term deviations from the GDP+portfolio equilibrium signal potential reversals.
6. **Central bank buying is the new structural floor** — the 2022-2026 regime shift means pre-2024 models and correlations cannot be relied upon.

---

## References

1. World Gold Council. (2025). *Gold Long-Term Expected Return (GLTER)*. SUERF Policy Brief No. 1119.
2. World Gold Council. (2025). *Gold Mid-Year Outlook 2025*.
3. World Gold Council. (2026). *Gold Demand Trends: Full Year 2025*.
4. World Gold Council. (2026). *Gold Demand Trends: Q1 2026*.
5. World Gold Council. (2021). *Short-term gold performance model*. Gold Focus.
6. Barsky, R., Epstein, C., Lafont-Mueller, A., & Yoo, Y. (2021). *What Drives Gold Prices?* Chicago Fed Letter No. 464.
7. Herley, M.D., Orłowski, L.T., & Ritter, M.A. (2024). *US Dollar Exchange Rate Elasticity of Gold Returns at Different Federal Fund Rate Zones*. Economies, 12(9), 229.
8. MDPI. (2026). *The U.S. Dollar as a Dollar-Channel Proxy in Gold Return Dynamics: Evidence from 2000–2025*. Economies, 14(3), 79.
9. Arslanalp, S., Eichengreen, B., & Simpson-Bell, C. (2023). *Gold as International Reserves: A Barbarous Relic No More?* IMF WP/23/008.
10. Weiss, C. (2024). *De-Dollarization? Diversification? Exploring Central Bank Gold Purchases and the Dollar's Role in International Reserves*. Federal Reserve IFDP 1420.
11. ECB. (2025). *Gold demand: the role of the official sector and geopolitics*. International Role of the Euro, June 2025.
12. BIS. (2021). *What share for gold? On the interaction of gold with FX reserve portfolios*. BIS Working Paper No. 906.
13. Aizenman, J. & Inoue, K. (2012). *Central Banks and Gold Puzzles*. NBER WP 17894.
14. Baur, D.G. (2013). *The Seasonality of Gold: The Autumn Effect*. SSRN.
15. Gülseven, O. (2020). *Turn-of-the-Year Effect in Gold Prices: Decomposition Analysis*. arXiv.
16. Löwen, C., Kchouri, B., & Lehnert, T. (2021). *Is this time really different? Flight-to-safety and the COVID-19 crisis*. PLOS ONE.
17. Hood, M. & Malik, F. (2013). *Is gold the best hedge and a safe haven under changing stock market volatility?* Review of Financial Economics.
18. Wang, Y.S. & Chueh, Y.L. (2013). *Dynamic transmission effects between the interest rate, the US dollar, and gold and crude oil prices*. Economic Modelling, 30.
19. Reboredo, J.C. (2013). *Is gold a safe haven or a hedge for the US dollar?* International Review of Financial Analysis.
20. Demajo, N. (2025). *An analysis of the relationship between real yields and gold prices: a pre and post Covid analysis*. University of Malta.
21. Zhou, H. & Liang, C. (2025). *Geopolitical risk and gold price bubbles*. Review of Accounting and Finance.
22. Changani, J.G. (2024). *Factors Influencing Gold Price Movements: A Time Series Analysis Perspective*. SSRN.
23. Xiong, H. & Zhang, W. (2024). *How the US Macroeconomic Factors Affect the Gold Price?* Advances in Economics, Management and Political Sciences.
24. Erb, C. & Harvey, C. (2024). *Is There Still a Golden Dilemma?* SSRN. NBER.
25. IMF. (2026). *Gold in Central Bank Reserves: Strategic Considerations, Market*.
