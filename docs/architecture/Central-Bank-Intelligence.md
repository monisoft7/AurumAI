# Central Bank Intelligence

**Department Classification**: Tier-1 Intelligence Department  
**Date Established**: 2026-07-26  
**Authority**: Chief Economist Review  
**Status**: Department Charter — Approved  
**Gap Reference**: CER-009, Gap 1 (Critical, Rank 1 of 10)  

---

## 1. Mission

Central Bank Intelligence exists to monitor, analyze, and synthesize the monetary policy actions, communications, and forward guidance of the world's nine major central banks. It transforms raw central bank output — statements, minutes, speeches, press conferences, dot plots, and voting records — into structured institutional intelligence on policy bias, rate trajectories, liquidity conditions, and global monetary regime dynamics.

The department's mandate is forward-looking. It does not merely record what central banks have done. It assesses what central banks are likely to do, where market expectations diverge from probable policy paths, and what the aggregate liquidity implications are for global macro asset allocation.

Central banks are the single most powerful force in global macro markets. Gold is hypersensitive to real rate expectations and global liquidity conditions. Without comprehensive central bank intelligence, the institution is structurally late to every major macro turn.

---

## 2. Inputs

The department receives raw material from three categories of sources.

### 2.1 Primary Source Documents

| Document Type | Description | Frequency | Coverage |
|---------------|-------------|-----------|----------|
| Policy Statements | Official post-meeting communiques | Per meeting | All 9 banks |
| Meeting Minutes | Detailed deliberation records | 2-3 weeks post-meeting | Fed, ECB, BOE, BOC, RBA, RBNZ |
| Speeches | Public remarks by policymakers | Irregular, multiple per week | All 9 banks |
| Press Conferences | Post-meeting Q&A sessions | Per meeting | Fed, ECB, BOJ, BOE, SNB, BOC |
| Dot Plots | Individual rate projections | Quarterly (SEP meetings) | Fed only |
| Voting Records | Dissent patterns and vote splits | Per meeting | Fed, ECB, BOE, BOJ, RBA, BOC |
| Staff Economic Projections | Central bank staff forecasts | Quarterly | Fed (SEP), ECB, BOE (MPR), BOC (MPR), RBA (SoMP) |
| Balance Sheet Data | Holdings, purchases, maturities | Weekly/Monthly | Fed, ECB, BOJ |

### 2.2 Upstream Departmental Inputs

| Source Department | What It Provides |
|-------------------|-----------------|
| External Data Connectors | FOMC calendar, meeting schedules, raw data feeds, central bank publication calendars |
| Natural Language Processing | Sentiment scores on central bank text (FOMC RoBERTa, general FinBERT) |
| News Intelligence | Central bank-related news articles, market commentary on policy decisions |

### 2.3 Market-Derived Inputs

| Input | Purpose |
|-------|---------|
| Fed Funds Futures / OIS curves | Market-implied rate expectations for comparison against department assessment |
| Sovereign yield curves (2Y, 5Y, 10Y, 30Y) | Term premium and policy transmission signals |
| Real yield curves (TIPS) | Real rate expectations — the primary gold pricing channel |
| FX forward rates | Market-implied rate differential expectations |

---

## 3. Outputs

The department emits two categories of output: institutional products (Section 14) consumed by other departments, and internal research artifacts retained for departmental use.

All outputs carry provenance metadata: which source documents were analyzed, which analysts contributed, what confidence level applies, and what the key assumptions are. No output leaves the department without an evidence trail.

---

## 4. Internal Research Responsibilities

### 4.1 Statement Analysis

Parse and score policy statements for directional bias. Track language evolution between consecutive meetings — word additions, deletions, and substitutions are the primary signal. Maintain a canonical language change log for each central bank.

### 4.2 Minutes Analysis

Extract debate intensity, dissent arguments, and emerging minority views from meeting minutes. Minutes reveal the arguments that did not prevail — and minority arguments at one meeting frequently become majority positions two to three meetings later. Track the migration of arguments from minority to majority status.

### 4.3 Speech Tracking

Monitor individual policymaker speeches and public remarks. Maintain a per-policymaker hawk/dove score with temporal evolution. Speeches are the primary channel through which central bankers signal policy shifts before formal meetings. Weight speeches by the speaker's committee influence and voting status.

### 4.4 Press Conference Analysis

Analyze post-meeting press conferences, with particular attention to Q&A responses. Prepared remarks restate the communique; Q&A responses reveal information the committee chose not to include in the statement. Track the gap between prepared remarks and Q&A tone as a forward guidance quality signal.

### 4.5 Dot Plot Analysis (Federal Reserve)

Track individual dot movements across quarterly Summary of Economic Projections releases. Monitor the median, the dispersion (standard deviation of dots), and the skew (asymmetry of dot distribution). Rising dispersion signals increasing uncertainty within the committee. Track the long-run neutral rate dot as a structural anchor signal.

### 4.6 Voting Record Analysis

Monitor dissent patterns, bloc formation, and rotation of voting members (particularly at the Fed, where regional presidents rotate annually). Dissent is a leading indicator: a single dissent today often foreshadows a policy shift in two to three meetings. Track dissent direction (hawkish vs dovish dissent) separately.

### 4.7 Forward Guidance Interpretation

Synthesize across all document types to determine what each central bank is signaling about its future policy path. Distinguish between calendar-based forward guidance ("at least through 2025"), state-contingent guidance ("until inflation sustainably reaches 2%"), and open-ended guidance ("data-dependent"). Track guidance credibility — how often has each central bank followed through on its own guidance.

### 4.8 Balance Sheet Monitoring

Track the size, composition, and pace of change in central bank balance sheets. Monitor quantitative tightening runoff caps vs actual runoff, reinvestment policy changes, and any emergency lending facility usage that signals financial stress. Balance sheet policy often diverges from rate policy — this divergence is itself an intelligence signal.

### 4.9 Policy Divergence Measurement

Measure and track the degree of policy divergence across all nine central banks. When central banks are synchronized (all tightening or all easing), the macro regime is directionally clear. When they diverge (Fed tightening while PBOC easing), the FX and capital flow implications dominate, and gold's role as a neutral reserve asset becomes more prominent.

### 4.10 Liquidity Condition Assessment

Aggregate balance sheet data, reserve changes, facility usage, and money market indicators into a composite global liquidity assessment. This is the department's highest-value synthesis task — liquidity conditions are the single strongest driver of asset allocation rotations and the primary macro factor for gold.

---

## 5. Knowledge Produced

The department produces institutional knowledge in five domains.

**Policy Direction Knowledge**: Which way is each central bank leaning? Is the bias shifting? How confident is the committee in its current path? Where is internal disagreement growing?

**Market Expectation Divergence Knowledge**: Where do market-implied rate paths diverge from the department's assessment of probable policy paths? These divergences are the primary source of macro trading opportunity — when the market is pricing something the department believes is wrong.

**Surprise Probability Knowledge**: Where are the surprises likely to come from? Which central bank's next meeting has the highest probability of delivering an outcome the market has not priced? What asymmetric risks exist in rate expectations?

**Global Liquidity Knowledge**: What is the aggregate liquidity trajectory across all nine central banks? Is global liquidity expanding or contracting? At what pace? Which central banks are the marginal contributors to liquidity change?

**Marginal Driver Knowledge**: Which central bank is the marginal driver of gold at this moment? This shifts over time — in 2022-2023 it was the Fed; in 2024-2025 it was the BOJ and PBOC. The department must identify the current marginal driver and weight its analysis accordingly.

---

## 6. Decisions This Department Never Owns

Central Bank Intelligence is an intelligence producer, not a decision-maker. The following decisions are explicitly outside its mandate:

| Decision | Owning Department |
|----------|------------------|
| Position sizing and risk allocation | Forecasting & Risk |
| Trade entry and exit timing | Execution |
| Final directional macro view | Knowledge (Decision Engine) |
| Asset selection and portfolio construction | Forecasting & Risk |
| Risk limit setting and enforcement | Forecasting & Risk |
| Data source procurement and vendor selection | External Data Connectors |
| Sentiment model architecture and training | Natural Language Processing |
| Regime classification thresholds | Knowledge (Regime Detection) |

The department provides intelligence. It does not prescribe action. Its products inform the reasoning chain — they do not bypass it.

---

## 7. Downstream Consumers

The following existing AurumAI departments consume Central Bank Intelligence output.

### 7.1 Institutional Knowledge Department

**Primary consumer.** Central bank intelligence enters the Knowledge Department as evidence within the reasoning chain. Policy bias scores, rate path assessments, and liquidity outlooks become evidence items weighted by the Evidence Weighter and consumed by the Reasoning Engine. This is the canonical path through which central bank intelligence influences institutional decisions.

Specific consumption points:
- Evidence Repository receives policy bias and rate path assessments as new evidence classes
- Feature Extraction consumes structured central bank features for lesson-building
- Regime Detection receives global monetary regime signals as regime classification inputs
- Context Enrichment receives central bank context for cross-referencing against market data context

### 7.2 Forecasting & Risk Department

Rate path projections and liquidity outlooks directly inform time-series forecasting models. The Forecasting Department uses central bank intelligence to condition its macro forecasts — a rate path shift changes the distribution of expected outcomes for gold, yields, and currencies. Risk models consume policy surprise probability for tail-risk calibration.

### 7.3 Natural Language Processing Department

Coordination relationship. NLP provides sentiment scores to Central Bank Intelligence; Central Bank Intelligence provides domain-specific labeling, calibration feedback, and new document types for sentiment model coverage expansion. The two departments co-evolve: as Central Bank Intelligence coverage expands to new banks, NLP expands its model coverage accordingly.

### 7.4 Simulation & Validation Department

Historical central bank intelligence products provide ground-truth labels for simulation replay. When Simulation replays a historical period, it needs the department's reconstructed assessment of what was known at each point in time — not the actual outcome, but the contemporaneous intelligence estimate.

---

## 8. Upstream Providers

The following existing AurumAI departments provide input to Central Bank Intelligence.

### 8.1 External Data Connectors Department

Provides meeting calendars, publication schedules, and raw data feeds. The FOMC Calendar Connector is the existing foundation — this expands to cover all nine central banks' meeting schedules and publication calendars.

### 8.2 Natural Language Processing Department

Provides quantitative sentiment scores on central bank text. The FOMC Sentiment Analyzer (RoBERTa-based) is the existing capability. Central Bank Intelligence consumes these scores as one input among many — sentiment scores alone are insufficient for policy bias assessment, but they provide a quantitative anchor.

### 8.3 News Intelligence Department

Provides macro-relevant news articles tagged with central bank relevance. Market commentary, analyst reactions, and journalistic interpretation of central bank communications provide context that raw source documents do not contain — particularly regarding market consensus interpretation.

---

## 9. Daily Workflow

The daily workflow runs every trading day, regardless of whether any central bank has a scheduled event.

| Time (UTC) | Activity | Purpose |
|------------|----------|---------|
| 06:00 | Overnight communication scan | Capture BOJ, PBOC, RBA, RBNZ actions from Asian session; BOE, ECB, SNB from early European session |
| 06:30 | Speaker log update | Record any overnight policymaker remarks; update individual hawk/dove scores if warranted |
| 07:00 | Market-implied rate check | Compare current OIS/futures-implied paths against department's standing assessments; flag any divergence exceeding 1 standard deviation |
| 12:00 | Midday scan | Capture any European-session speeches or ECB/BOE publications |
| 15:00 | Fed communication window | Monitor any Federal Reserve speeches, Fed research publications, or regional Fed bank commentary |
| 17:00 | Daily intelligence summary | Produce a brief daily note: any material changes to any central bank's assessed bias, any notable market-implied rate moves, any upcoming events for the next 48 hours |

**On meeting days**, the workflow expands to include real-time statement parsing, immediate bias score update, and press conference analysis (when applicable). Meeting-day output is elevated to an event-driven intelligence product with same-day dissemination.

**On minutes release days**, the workflow includes a full minutes analysis with comparison against the original statement, extraction of dissent arguments, and update to forward guidance interpretation.

---

## 10. Weekly Workflow

The weekly workflow runs every Friday, synthesizing the week's intelligence into standing assessments.

| Activity | Output | Distribution |
|----------|--------|-------------|
| Policy Bias refresh | Updated Policy Bias Score for any central bank where new information was received during the week | Knowledge Department, Forecasting & Risk |
| Forward Guidance Tracker update | Updated guidance interpretation for any central bank with new communications | Knowledge Department |
| Policy Divergence Matrix update | Refreshed cross-bank divergence scoring | Knowledge Department, Forecasting & Risk |
| Speaker calendar review | Flag key speeches and events for the coming week; pre-position analysis resources | Internal departmental use |
| Market expectation divergence review | Identify any widening gaps between department assessment and market-implied pricing | Knowledge Department |
| Weekly intelligence brief | 1-2 page synthesis of the week's central bank developments and their macro implications | All consuming departments |

---

## 11. Monthly Workflow

The monthly workflow runs on the last business day of each month, producing the department's most comprehensive assessments.

| Activity | Output | Distribution |
|----------|--------|-------------|
| Full Policy Path Assessment | Complete rate path projection for all nine central banks, 12-month horizon | Knowledge Department, Forecasting & Risk, Simulation |
| Balance Sheet Outlook refresh | Updated QE/QT trajectory for Fed, ECB, and BOJ; balance sheet size projections | Knowledge Department, Forecasting & Risk |
| Global Monetary Regime Assessment | Composite assessment of global monetary stance: synchronized easing/tightening, divergence degree, liquidity trajectory | Knowledge Department, Forecasting & Risk |
| Liquidity Outlook update | 3-month forward liquidity conditions assessment incorporating balance sheet flows, reserve changes, and facility usage | Knowledge Department, Forecasting & Risk |
| Hawk/Dove Scorecard full refresh | Complete per-policymaker scoring for all voting members across all nine central banks | Internal departmental use, Knowledge Department |
| Forecast accuracy review | Compare prior month's department assessments against actual outcomes; calibrate confidence levels | Internal departmental use |
| Central Bank Surprise Index recalibration | Update the surprise probability model based on the month's actual vs expected outcomes | Knowledge Department |

---

## 12. Central Bank Coverage

The department maintains analytical coverage of nine central banks representing approximately 85% of global reserve currency GDP and the overwhelming majority of global monetary policy influence on macro asset allocation.

### 12.1 Federal Reserve (Fed)

**Coverage tier**: Tier 1 — Maximum depth  
**Jurisdiction**: United States  
**Meeting frequency**: 8 scheduled meetings per year (FOMC)  
**Key officers tracked**: Chair, Vice Chair, Vice Chair for Supervision, all Board Governors, all 12 regional presidents (5 voting at any time)  
**Unique intelligence**: Dot plot (quarterly SEP), Beige Book (8x/year), Financial Stability Report (2x/year), H.4.1 balance sheet data (weekly), Fed speaker volume is highest of any central bank  
**Significance to gold**: Primary — Fed policy sets the global risk-free rate, the USD, and the opportunity cost of holding gold. The Fed is the default marginal driver unless conditions elevate another bank.

### 12.2 European Central Bank (ECB)

**Coverage tier**: Tier 1 — Maximum depth  
**Jurisdiction**: Euro Area (20 member states)  
**Meeting frequency**: 6 interest rate meetings + 4 non-monetary policy meetings per year  
**Key officers tracked**: President, Vice President, Chief Economist, all Executive Board members, all national central bank governors (rotating voting)  
**Unique intelligence**: Staff macroeconomic projections (quarterly), Account of the monetary policy meeting (equivalent to minutes), fragmentation risk monitoring (TPI instrument), APP/PEPP reinvestment policy  
**Significance to gold**: High — EUR/USD is the largest component of DXY; ECB-Fed divergence is a primary driver of dollar strength/weakness and therefore gold.

### 12.3 Bank of Japan (BOJ)

**Coverage tier**: Tier 1 — Maximum depth  
**Jurisdiction**: Japan  
**Meeting frequency**: 8 scheduled meetings per year  
**Key officers tracked**: Governor, 2 Deputy Governors, 6 Policy Board members  
**Unique intelligence**: Yield Curve Control parameters (target rate, tolerance band), JGB purchase operations (daily), Outlook for Economic Activity and Prices (quarterly), BOJ's balance sheet is the largest relative to GDP of any major central bank  
**Significance to gold**: High — JPY is a global funding currency; BOJ policy shifts (as in 2024) cause massive global capital flow reallocation. BOJ normalization is a structural gold headwind through yen strengthening; BOJ easing supports gold through global liquidity expansion.

### 12.4 Bank of England (BOE)

**Coverage tier**: Tier 2 — High depth  
**Jurisdiction**: United Kingdom  
**Meeting frequency**: 8 scheduled meetings per year (MPC)  
**Key officers tracked**: Governor, 4 Deputy Governors, Chief Economist, 4 external MPC members  
**Unique intelligence**: Monetary Policy Report (quarterly, with fan charts), MPC minutes published simultaneously with decision, voting record transparency is highest among major central banks, Financial Policy Committee interactions  
**Significance to gold**: Moderate-High — GBP is a meaningful DXY component; UK inflation dynamics often lead or lag other developed markets, providing a preview of policy trajectory.

### 12.5 People's Bank of China (PBOC)

**Coverage tier**: Tier 2 — High depth  
**Jurisdiction**: China  
**Meeting frequency**: No fixed schedule; policy changes announced via State Council or PBOC directly  
**Key officers tracked**: Governor, Deputy Governors, Monetary Policy Committee members  
**Unique intelligence**: Medium-Term Lending Facility (MLF) rate, Loan Prime Rate (LPR), Required Reserve Ratio (RRR), FX reserve data (monthly), capital account management signals, PBOC gold purchases (reported monthly with lag)  
**Significance to gold**: Critical for structural demand — PBOC gold reserve accumulation (2022-2025) created a structural bid. PBOC easing/tightening signals are also a proxy for China growth outlook, which drives industrial commodity demand and global growth sentiment.

### 12.6 Swiss National Bank (SNB)

**Coverage tier**: Tier 2 — High depth  
**Jurisdiction**: Switzerland  
**Meeting frequency**: 4 scheduled meetings per year  
**Key officers tracked**: Chairman, Vice Chairman, all Governing Board members  
**Unique intelligence**: FX intervention policy (SNB has historically intervened aggressively), sight deposit data (proxy for intervention), one of the largest gold reserves per capita, Swiss franc as safe-haven currency  
**Significance to gold**: Moderate — CHF is a competing safe-haven asset; SNB FX policy affects EUR/CHF and broader risk sentiment. SNB's own gold holdings and reserve management decisions are directly relevant.

### 12.7 Reserve Bank of Australia (RBA)

**Coverage tier**: Tier 3 — Standard depth  
**Jurisdiction**: Australia  
**Meeting frequency**: 8 scheduled meetings per year  
**Key officers tracked**: Governor, Deputy Governor, all Board members  
**Unique intelligence**: Statement on Monetary Policy (SoMP, quarterly), Board minutes (2 weeks post-meeting), Australia as a commodity currency proxy — AUD/USD often leads commodity sentiment  
**Significance to gold**: Moderate — AUD is a gold-correlated currency; RBA policy reflects commodity cycle dynamics and Asian demand conditions that directly affect gold.

### 12.8 Reserve Bank of New Zealand (RBNZ)

**Coverage tier**: Tier 3 — Standard depth  
**Jurisdiction**: New Zealand  
**Meeting frequency**: 7 scheduled meetings per year  
**Key officers tracked**: Governor, Deputy Governor, Monetary Policy Committee members  
**Unique intelligence**: Monetary Policy Statement (quarterly, with published interest rate track — one of the few central banks that explicitly publishes its expected rate path), RBNZ often leads the global hiking/cutting cycle — it raised rates before the Fed in 2021 and cut before the Fed  
**Significance to gold**: Moderate — RBNZ is a leading indicator central bank. Its policy moves often foreshadow what larger central banks will do 3-6 months later. The published rate track provides a unique comparison point against market-implied paths.

### 12.9 Bank of Canada (BOC)

**Coverage tier**: Tier 3 — Standard depth  
**Jurisdiction**: Canada  
**Meeting frequency**: 8 fixed announcement dates per year  
**Key officers tracked**: Governor, Senior Deputy Governor, all Deputy Governors, all Governing Council members  
**Unique intelligence**: Monetary Policy Report (quarterly), Business Outlook Survey (quarterly), Canadian economy as a commodity-sensitive, US-correlated proxy — BOC policy often mirrors Fed with a lag, but divergences are informative  
**Significance to gold**: Moderate — CAD is a commodity currency; BOC-Fed divergence signals are useful for gauging whether Fed policy is too tight or too loose relative to fundamentals in a closely correlated economy.

---

## 13. Document Types Analyzed

### 13.1 Statements

The post-meeting policy statement is the most market-sensitive central bank document. It is carefully drafted by committee and every word change is deliberate.

**Analysis method**: Line-by-line comparison with prior statement. Language additions, deletions, and substitutions are cataloged. Directional bias scoring weights the magnitude and location of changes. Opening paragraph changes (economic assessment) are distinguished from closing paragraph changes (forward guidance) — they carry different information content.

**Coverage**: All 9 central banks.

### 13.2 Minutes

Meeting minutes reveal the arguments behind the decision — including arguments that lost. They are the primary source for identifying emerging dissent and shifting internal dynamics.

**Analysis method**: Extraction of distinct argument threads. Classification of arguments as hawkish, dovish, or neutral. Identification of new arguments not present in prior minutes (novel concerns). Assessment of debate intensity through language markers ("a few members" vs "several members" vs "most members").

**Coverage**: Fed, ECB, BOE, BOC, RBA, RBNZ. BOJ publishes a summary but not full minutes. PBOC and SNB do not publish minutes.

### 13.3 Speeches

Policymaker speeches are the primary channel for signaling between meetings. They are less constrained than committee-drafted statements and often reveal individual positioning.

**Analysis method**: Per-speaker hawk/dove scoring with temporal tracking. Speeches are weighted by the speaker's role (Chair/Governor speeches carry higher weight than regional/external members), timing relative to the next meeting (speeches closer to the meeting are more indicative of the upcoming decision), and whether the speaker is a current voting member.

**Coverage**: All 9 central banks. Volume varies significantly — Fed speakers generate 10-15 speeches per week; SNB generates 2-3 per month.

### 13.4 Press Conferences

Post-meeting press conferences — particularly the Q&A portion — often contain more information than the prepared statement. Journalists probe areas where the committee's communication is deliberately ambiguous.

**Analysis method**: Separate analysis of prepared remarks (which largely restate the statement) and Q&A responses. Q&A analysis focuses on: topics the chair deflected (what they don't want to address), precision of language (hedged vs definitive), and any deviation in tone from the written statement. Press conference tone that is more hawkish or dovish than the statement itself is a strong signal.

**Coverage**: Fed, ECB, BOJ, BOE, SNB, BOC. RBA and RBNZ rely on statements and minutes. PBOC does not hold regular post-decision press conferences.

### 13.5 Dot Plots

The Federal Reserve's Summary of Economic Projections dot plot is a unique instrument that publishes individual (anonymous) rate projections from all FOMC participants.

**Analysis method**: Track median dot, mean dot, dispersion (standard deviation), skew, and range across quarterly releases. Monitor dot migration — how many dots moved up vs down between releases. The long-run dot (neutral rate estimate) is tracked separately as a structural anchor. Compare the dot median to the Fed Funds futures curve — divergences signal either that the market doesn't believe the Fed, or that the Fed is behind the market.

**Coverage**: Federal Reserve only (quarterly, at March, June, September, and December FOMC meetings).

### 13.6 Voting Records

How each committee member voted — and particularly who dissented and in which direction — is a direct measure of internal policy tension.

**Analysis method**: Track dissent frequency, dissent direction (hawkish vs dovish), and dissenter identity over time. Rising dissent is a leading indicator of policy inflection. Track voting bloc formation — when the same members consistently dissent together, it signals an organized minority view gaining coherence. Monitor the relationship between dissent and subsequent policy changes (historically, the direction of dissent predicts the direction of the next policy move with significant accuracy).

**Coverage**: Fed (full roll call), ECB (vote count, not individual attribution), BOE (full roll call with individual attribution), BOJ (full roll call), BOC (consensus-based, dissent is rare but notable when it occurs), RBA (consensus-based). PBOC and SNB do not publish voting records.

---

## 14. Institutional Products

The department emits the following standing institutional products. Each product has a defined format, update cadence, and confidence framework.

### 14.1 Policy Bias Score

**Definition**: A per-central-bank directional assessment of the current monetary policy stance on a standardized scale.

**Scale**: -5 (aggressively dovish / emergency easing) to +5 (aggressively hawkish / emergency tightening), with 0 representing assessed neutrality.

**Update cadence**: After every meeting, speech, or minutes release that warrants a reassessment. Minimum weekly for Tier 1 banks.

**Components**: Assessed from statement language, recent speeches, voting patterns, and forward guidance. Each component contributes to the composite score with defined weights.

**Consumers**: Knowledge Department (Evidence Repository), Forecasting & Risk.

### 14.2 Policy Path Assessment

**Definition**: A 12-month forward projection of each central bank's expected policy rate trajectory, expressed as a base case with probability-weighted alternative scenarios.

**Format**: Base case rate path (most likely), hawkish scenario (with probability), dovish scenario (with probability), key contingencies that would trigger scenario switching.

**Update cadence**: Monthly (full refresh), with interim updates after any meeting that materially changes the assessment.

**Differentiation from market-implied paths**: This product explicitly diverges from market pricing where the department's assessment differs. The gap between the department's path and the market-implied path is itself a primary intelligence product.

**Consumers**: Knowledge Department, Forecasting & Risk, Simulation.

### 14.3 Forward Guidance Tracker

**Definition**: A structured record of each central bank's current forward guidance, classified by type and assessed for credibility.

**Guidance types tracked**: Calendar-based ("until at least Q3 2026"), state-contingent ("until inflation sustainably returns to target"), open-ended ("data-dependent, meeting by meeting"), quantitative ("balance sheet reduction of $60B/month").

**Credibility score**: Based on each central bank's historical follow-through on its own guidance. Central banks that frequently abandon guidance receive lower credibility scores, which propagate as lower confidence weights in downstream evidence consumption.

**Update cadence**: After every meeting or communication that modifies guidance. Weekly integrity check.

**Consumers**: Knowledge Department (Evidence Repository, Reasoning Engine).

### 14.4 Liquidity Outlook

**Definition**: A 3-month forward assessment of global liquidity conditions, aggregating balance sheet flows, reserve changes, and money market indicators across all major central banks.

**Components**: Aggregate G4 balance sheet change trajectory, reserve accumulation/drawdown trends, money market stress indicators (SOFR, repo rates, FRA-OIS spreads), fiscal liquidity effects (TGA balance, RRP facility for the US).

**Classification**: Expanding / Stable / Contracting, with pace qualifier (rapidly, gradually, marginally).

**Update cadence**: Monthly, with interim alerts for any abrupt liquidity event.

**Significance**: This is the department's highest-value synthesis product. Global liquidity is the single strongest driver of macro asset allocation and the primary macro factor for gold. Liquidity expansion is structurally gold-positive; contraction is structurally gold-negative.

**Consumers**: Knowledge Department, Forecasting & Risk.

### 14.5 Rate Path Projection

**Definition**: A quantitative projection of the most likely policy rate for each central bank at each of the next 8 scheduled meetings, with confidence intervals.

**Format**: Point estimate per meeting + 80% confidence interval. Expressed in basis points of change from current rate.

**Differentiation from Policy Path Assessment**: The Rate Path Projection is quantitative and short-horizon (next 8 meetings). The Policy Path Assessment (14.2) is qualitative and long-horizon (12 months). They complement rather than duplicate.

**Update cadence**: After every meeting. Continuous refinement as new data arrives.

**Consumers**: Forecasting & Risk (direct input to rate-sensitive models).

### 14.6 Balance Sheet Outlook

**Definition**: A forward projection of central bank balance sheet size and composition for the Fed, ECB, and BOJ — the three central banks whose balance sheet policies have the most significant global liquidity impact.

**Components**: Total balance sheet size trajectory, government bond holdings trajectory, pace of QT/QE (actual vs announced), reinvestment policy, emergency facility usage trends.

**Update cadence**: Monthly.

**Consumers**: Knowledge Department, Forecasting & Risk (as input to liquidity-sensitive models).

### 14.7 Policy Divergence Matrix

**Definition**: A cross-bank comparison matrix measuring the degree and direction of policy divergence between all pairs of covered central banks.

**Format**: 9x9 matrix of divergence scores, with color-coded directional indicators. Aggregate divergence index (high divergence vs low divergence across the global system).

**Significance**: High policy divergence drives FX volatility and capital flow reallocation. Maximum divergence periods historically correlate with elevated gold volatility and trend acceleration. When all central banks converge on the same policy direction, macro conviction trades are higher confidence but lower magnitude.

**Update cadence**: Weekly.

**Consumers**: Knowledge Department (Regime Detection), Forecasting & Risk.

### 14.8 Hawk/Dove Scorecard

**Definition**: A per-policymaker assessment of each voting member's current policy lean, tracked over time.

**Scale**: -3 (consistent dove) to +3 (consistent hawk), with temporal weighting favoring recent communications.

**Coverage**: All current voting members of all 9 central banks. Historical scoring maintained for non-voting members who will rotate into voting positions.

**Significance**: Committee composition changes (member rotation, new appointments) can shift the balance of power without any change in economic conditions. The scorecard enables the department to anticipate how composition changes will affect policy outcomes.

**Update cadence**: After every speech or public appearance by a tracked policymaker. Full refresh monthly.

**Consumers**: Internal departmental use (feeds into Policy Bias Score calculation), Knowledge Department.

### 14.9 Global Monetary Regime Assessment

**Definition**: A composite assessment of the global monetary regime — the aggregate stance, direction, and synchronization of monetary policy across the world's major central banks.

**Regime classifications**:
- Synchronized Easing (all major banks easing — gold structurally bullish)
- Synchronized Tightening (all major banks tightening — gold structurally bearish)
- Divergent (mixed policy stances — gold driven by relative rates and capital flows)
- Transition (regime is shifting — highest uncertainty, elevated volatility)
- Emergency (one or more banks in crisis-response mode — gold safe-haven bid activated)

**Update cadence**: Monthly, with interim alerts on regime transition signals.

**Consumers**: Knowledge Department (Regime Detection — as a global overlay to the US-centric Markov regime framework), Forecasting & Risk.

### 14.10 Central Bank Surprise Index

**Definition**: A per-central-bank measure of how frequently and by how much each bank's actual decisions have surprised market expectations over trailing 12-month and 24-month windows.

**Components**: Decision surprise (actual vs consensus), communication surprise (guidance shifts without data justification), balance sheet surprise (actual vs announced pace).

**Significance**: Central banks with high surprise indices require wider confidence intervals in rate path projections. Low-surprise banks (those that reliably telegraph their moves) can be projected with higher confidence, freeing analytical attention for higher-surprise banks.

**Update cadence**: After every meeting. Trailing recalculation monthly.

**Consumers**: Knowledge Department (Evidence Weighter — surprise index informs confidence weighting), Forecasting & Risk.

---

## 15. Coverage Tier Framework

The department operates a three-tier coverage framework to allocate analytical resources proportional to each central bank's impact on the institution's primary mission.

| Tier | Banks | Coverage Standard | Resource Allocation |
|------|-------|-------------------|-------------------|
| Tier 1 — Maximum Depth | Fed, ECB, BOJ | All 6 document types analyzed in full; real-time monitoring; same-day product updates on meeting days; full balance sheet tracking; individual policymaker scoring for all committee members | 60% of departmental capacity |
| Tier 2 — High Depth | BOE, PBOC, SNB | All available document types analyzed; next-business-day product updates; balance sheet monitoring where published; individual policymaker scoring for key officers | 25% of departmental capacity |
| Tier 3 — Standard Depth | RBA, RBNZ, BOC | Statements, minutes, and key speeches analyzed; weekly product updates; policymaker scoring for Governor and Deputy Governor only | 15% of departmental capacity |

Tier assignments are reviewed quarterly. A central bank may be temporarily elevated (e.g., if RBNZ is the first to cut in a global easing cycle, it moves to Tier 2 monitoring for the duration of its leading-indicator relevance).

---

*Central Bank Intelligence — Department Charter*  
*AurumAI Institutional Architecture*
