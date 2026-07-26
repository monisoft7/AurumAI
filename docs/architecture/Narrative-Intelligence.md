# Narrative Intelligence

**Department Classification**: Tier-1 Intelligence Department  
**Date Established**: 2026-07-26  
**Authority**: Chief Strategist Review  
**Status**: Department Charter — Approved  
**Gap Reference**: CER-009, Gap 5 (High, Rank 5 of 10)

---

## 1. Mission

Narrative Intelligence exists to identify, track, measure, and interpret the market narratives that drive macro asset prices across the global financial system. It transforms unstructured text — financial media, sell-side research, central bank communications, earnings calls, regulatory filings, and social discourse — into structured institutional intelligence on which stories are gaining traction, which are dying, which conflict with each other, and what the aggregate narrative structure implies about the sustainability of current market regimes.

The department's mandate is observational and interpretive. Markets move on narratives before they move on data. A recession becomes consensus through repeated storytelling well before GDP reports confirm it. A market rally exhausts itself not when fundamentals change but when the story that drove it becomes stale, disbelieved, or replaced by a more compelling alternative. The department does not create narratives. It reads the evolving story the market is telling itself — and measures how that story is being received, believed, acted upon, and eventually abandoned.

The most profitable macro trades occur at narrative inflection points. The gap between the dominant narrative and the incoming data flow is where surprise is born, positioning is caught wrong-footed, and prices adjust dramatically. The institution currently detects regime changes statistically — Markov models that confirm a regime shift only after it has appeared in price data. Narrative intelligence detects the shift four to eight weeks earlier by tracking when the conversation changes before the data confirms it.

---

## 2. Inputs

The department receives raw material from three categories of sources.

### 2.1 Primary Text Sources

| Source | Description | Frequency | Coverage |
|--------|-------------|-----------|----------|
| Financial News Wire | Real-time news articles from major financial media | Continuous | Bloomberg, Reuters, Financial Times, Wall Street Journal, CNBC, MarketWatch, Investing.com, ZeroHedge |
| Sell-Side Research | Published research notes from major investment banks | Daily | Goldman Sachs, Morgan Stanley, JPMorgan, Citigroup, Bank of America, Barclays, Deutsche Bank, UBS, Credit Suisse, Nomura, SocGen, BNP Paribas |
| Central Bank Communications | Policy statements, speeches, minutes, press conferences, interviews | Per event | All 9 Tier 1-3 central banks (Fed, ECB, BOJ, BOE, PBOC, SNB, RBA, RBNZ, BOC) |
| Earnings Call Transcripts | Management commentary on macro conditions, capital allocation, and outlook | Quarterly (concentrated in earnings seasons) | S&P 500 companies with gold sensitivity (miners, banks, consumer discretionary, energy, materials) |
| Economic Think Tank and Research Institute Publications | Independent macro research and thematic white papers | Weekly/monthly | BIS, IMF, OECD, World Bank, Peterson Institute, Council on Foreign Relations, Bruegel, CASS |
| Policy and Regulatory Documents | Government fiscal plans, legislative proposals, regulatory guidance | Event-driven | US Congress, EU Commission, PBOC, Ministry of Finance of China, US Treasury, SEC, CFTC |
| Conference Transcripts and Presentations | Investment conference remarks by prominent macro investors and policymakers | Quarterly/event-driven | Jackson Hole, Davos, IMF Spring Meetings, CFA Society events, Sohn Conference, Goldman Sachs Macro Conference |

### 2.2 Upstream Departmental Inputs

| Source Department | What It Provides |
|-------------------|-----------------|
| Natural Language Processing | Quantitative sentiment scores, entity extraction, topic classification, named entity recognition, and frequency analysis across all text sources |
| News Intelligence | Curated news flow filtered for macro relevance, geopolitical tagging, and event classification |
| Central Bank Intelligence | Policy bias scores, forward guidance interpretation, and liquidity assessments — these provide the central bank narrative layer that the department tracks as one of its most important narrative streams |
| Cross-Asset Intelligence | Correlation regime classification and rotation signals — cross-asset behavior provides market-derived validation or contradiction of narrative strength |
| Capital Flow Intelligence | Positioning data and flow momentum — extreme positioning confirms that a narrative has been acted upon; flow-absent narratives are stories without capital commitment, which have limited price impact |
| External Data Connectors | Text data feeds, research aggregator subscriptions, conference calendar data, earnings call transcript APIs |

### 2.3 Derived Inputs

| Input | Purpose |
|-------|---------|
| Rolling term frequency matrices | Baseline word and phrase counts against which current narrative intensity is measured |
| Narrative co-occurrence networks | Map of which themes appear together in the same articles — reveals narrative cluster structure |
| Sentiment time series (30-day, 90-day, 365-day) | Baseline sentiment levels for each tracked narrative theme |
| Sell-side consensus trackers | Aggregated analyst ratings, price targets, and macro forecasts — the sell-side narrative, which often lags and amplifies |
| Social media/financial forum frequency data | Retail narrative intensity and divergence from institutional narrative — divergences are reversal signals |

---

## 3. Outputs

The department emits two categories of output: institutional products (Section 14) consumed by other departments, and internal research artifacts retained for departmental use.

All outputs carry provenance metadata: which text sources were analyzed, over what observation window, what the baseline frequencies were, and what confidence level applies. No output leaves the department without an evidence trail that accounts for source selection bias — media coverage frequency is itself a function of narrative salience, and the department must distinguish between an increase in genuine narrative attention and an increase in media recycling of the same story across outlets.

---

## 4. Internal Research Responsibilities

### 4.1 Narrative Origin Identification

When a new narrative enters the market discourse, identify its origin: which speaker, institution, document, or event introduced it. Track whether the origin was a deliberate communication (a central bank governor introducing a new policy framework, a Treasury secretary announcing a fiscal initiative, a prominent investor publishing a thesis) or an emergent pattern (a phrase repeated across multiple independent sources that crystallizes into a narrative without a single identifiable author).

Narrative origin type determines the expected adoption trajectory. Deliberate, authoritative origins (central bank, Treasury, prominent institutional investor) typically follow a top-down adoption path: from the originator to sell-side analysts to media coverage to institutional positioning to retail participation. Emergent narratives typically follow a bottom-up path: from financial forums and specialized media to broader media to sell-side adoption to institutional notice. Each path has a different velocity, persistence profile, and confidence framework.

Maintain a narrative origin register: for each tracked narrative, record the date of first significant signal, the identified originator or origination event, the initial medium (central bank communication, research note, media article, social media post, earnings call remark), and the origin context (what else was happening in the market when the narrative was born).

### 4.2 Narrative Strength Quantification

Measure the intensity of each tracked narrative across multiple independent dimensions to produce a composite strength score.

**Frequency dimension**: How often is the narrative mentioned across all tracked sources? Measured as absolute mention count, share of total narrative mentions, and deviation from historical baseline frequency for comparable themes.

**Authority dimension**: Who is carrying the narrative? A narrative mentioned by a central bank governor receives higher authority weight than the same narrative mentioned in a retail forum. The authority score weights each mention by the credibility and market influence of the source — Tier 1 sources (central banks, Treasury officials, pre-eminent macro investors, IMF/BIS) receive maximum weight; Tier 2 sources (sell-side analysts, financial journalists, corporate executives) receive moderate weight; Tier 3 sources (retail-focused media, social media, financial forums) receive minimum weight.

**Sentiment intensity dimension**: How strongly is the narrative expressed? Measured by sentiment score magnitude (not direction) — an article that discusses "aggressive Fed tightening" with strong negative sentiment carries more narrative intensity than an article that mentions "the potential for rate increases" with neutral sentiment.

**Market impact dimension**: Is the narrative being reflected in price action? A narrative appearing with increasing frequency that correlates with observed price moves has higher demonstrated strength than a narrative that appears frequently but has no observable market impact.

Composite narrative strength is expressed on a scale of 0 (narrative absent) to 100 (narrative universally dominant across all dimensions).

### 4.3 Narrative Persistence Measurement

Track how long each narrative persists in the discourse and whether its persistence is structurally supported or merely habitual.

Compute narrative half-life: the time it takes for a narrative's frequency to decline by 50% from its peak. Narratives with short half-lives (under two weeks) are event-driven and typically reverse once the catalyst fades. Narratives with long half-lives (over three months) have structural support — they are being reinforced by ongoing data flow, policy evolution, or market dynamics.

Distinguish between persistent narratives and stale narratives. A persistent narrative continues to generate new mentions with fresh content — new data points, evolving arguments, updated forecasts. A stale narrative continues to generate mentions but the content is repetitive — the same arguments, same data points, same conclusions being recycled without evolution. Stale narratives are at high risk of sudden collapse when a contradictory data point or alternative narrative emerges.

Track narrative resuscitation patterns — narratives that decline, then re-emerge with renewed force when a confirming data point or event occurs. Some narratives (e.g., recession fears) have multiple waves over years, each wave triggered by fresh data. The velocity of narrative return — how quickly a narrative re-establishes peak frequency after a confirming event — measures the depth of structural belief in the narrative thesis.

### 4.4 Narrative Conflict Detection

Identify when two or more tracked narratives are in direct contradiction. Narrative conflicts are the department's highest-value signal — they indicate that the macro environment is at an inflection point and that the current price regime carries elevated uncertainty.

**Conflict types**:
- Direct factual contradiction: "Inflation is transitory" vs "Inflation is persistent." Both narratives cannot be correct. The resolution of this conflict (one narrative winning decisively) typically produces a significant market move.
- Competing priority: "The Fed will prioritize inflation fighting" vs "The Fed will prioritize financial stability." Both may co-exist; the conflict is over which concern dominates, and the resolution determines the policy path.
- Temporal conflict: "Soft landing in H2 2025" vs "Hard landing in H2 2025." Both reference the same timeframe; the resolution comes with data releases that confirm one and refute the other.
- Regime conflict: "Risk-on reflation" vs "Risk-off defensive positioning." These are not factual contradictions but contradictory market behaviors that cannot persist indefinitely — eventually the market chooses one regime.

For each detected conflict, the department measures: (1) the strength balance — which narrative is currently winning, and by what margin, (2) the conflict intensity — how frequently both narratives appear in the same articles or presentations, and with what tone (acknowledged as a known tension vs asserted without acknowledging the alternative), (3) the resolution catalyst — what event or data release is most likely to resolve the conflict, and (4) the expected price impact of resolution in each direction.

### 4.5 Narrative Confirmation Analysis

Track whether each narrative is being confirmed or contradicted by incoming data, policy developments, and market behavior. A narrative that is strengthening in media frequency while being contradicted by data has reached peak narrative power — the gap between story and reality is at its widest, and reversal risk is highest. A narrative that is strengthening while being confirmed by data remains in its healthy adoption phase.

Maintain a confirmation matrix for each narrative, comparing the narrative's claims against: (1) economic data releases (are actual data points consistent with the narrative's implied trajectory?), (2) central bank actions (are policy decisions consistent with the narrative's policy assumptions?), (3) corporate behavior (are earnings, guidance, and capital allocation decisions consistent with the narrative?), (4) market pricing (are asset prices consistent with the narrative's implied valuation framework?), and (5) flow data (are capital flows consistent with the narrative's positioning thesis?).

The confirmation score per narrative is expressed as a percentage — the proportion of tracked confirmation signals that support versus contradict the narrative. A confirmation score above 80% indicates a fully data-supported narrative. A confirmation score below 40% indicates a narrative at high risk of collapse.

### 4.6 Narrative Decay and Collapse Monitoring

Monitor narratives for signs of exhaustion and imminent collapse. Narrative collapse is the fastest price-relevant event in macro markets — a story that took months to build can be destroyed in a single data release or policy decision.

**Decay indicators**:
- Frequency decline with no new confirming data
- Repetition without evolution (the same arguments recycled without new evidence)
- Authority decline (the narrative moving from Tier 1 sources to Tier 3 sources — from central banks to retail forums)
- Increasing caveats and conditionality in how the narrative is expressed ("if inflation persists, the Fed may..." — hedging language signals weakening conviction)
- Emergence of a competing narrative that directly contradicts the decaying narrative
- Confirming data flow slowing or reversing while the narrative remains unchanged

**Collapse detection triggers**:
- A single data release that directly contradicts a core narrative claim
- A policy decision that reframes the macro environment in a way that makes the narrative irrelevant
- A prominent authority figure explicitly rejecting the narrative (a central banker dismissing a recession narrative, a prominent investor calling a market peak)
- Price action that breaks the narrative's implied price trajectory — a narrative that said gold would fall on higher rates collapsing when gold rallies on a rate hike

When collapse is detected or imminent, the department issues a narrative collapse alert specifying the decaying narrative, the collapse trigger (if already materialized), the velocity of expected dissipation, and the most probable successor narrative.

### 4.7 Narrative Transition Detection

Identify the moments when the dominant market narrative shifts from one story to another. Narrative transitions are the highest-value events in macro market analysis — they represent the moment when the market's collective framework for interpreting the world changes, and every asset priced under the old framework must be re-evaluated.

**Transition archetypes**:
- Gradual displacement: The old narrative fades slowly over weeks as a new narrative gains incremental traction. Typical of structural shifts (e.g., the gradual transition from "inflation is transitory" to "inflation is persistent" over mid-2021 through late-2021).
- Catalyst-driven replacement: A single event destroys the old narrative and establishes the new narrative in a compressed timeframe. Typical of policy-driven shifts (e.g., the Fed pivot in December 2023 replacing "higher for longer" with "rate cuts coming").
- Coexistence and bifurcation: Two narratives both survive, each dominating different asset classes or timeframes. Typical of genuinely uncertain environments where more than one outcome is plausible.
- False transition and reversal: The narrative appears to shift, but the new narrative fails to gain traction and the old narrative reasserts itself. Typical of bear market rallies within a dominant bear narrative, or corrections within a dominant bull narrative.

For each detected transition, the department measures: the transition type (which archetype), the transition velocity (how quickly the old narrative's share declined and the new narrative's share rose), the transition completeness (what share of tracked sources have adopted the new narrative), and the stability assessment (is the new narrative self-reinforcing or vulnerable to reversal by the next data point?).

### 4.8 Narrative Theme Tracking — Institutional

Maintain continuous tracking of the institutional narrative themes listed in Section 12. For each theme, the department produces a structured analytical file containing: the theme definition and key claims, the current strength score and 30-day trend, the authority-weighted mention frequency, the persistent half-life, the confirmation score, the active conflicts with other themes, the current lifecycle phase (below), and the key catalysts that would accelerate or reverse the theme.

**Narrative lifecycle phases**:
- **Emergence**: The narrative first appears in the discourse. Frequency is low but growing. Authority distribution is concentrated (one or two prominent sources). Confirmation with data is untested. Market impact is minimal.
- **Adoption**: Frequency is growing rapidly across multiple source types. Authority distribution is broadening. Data confirmation is mixed but the narrative is gaining adherents. Market impact is moderate and strengthening.
- **Consensus**: Frequency is at or near peak. Authority distribution is broad (all source tiers carrying the narrative). Data confirmation is widely accepted. Market impact is high — positioning reflects the narrative. This is the most fragile phase, as the narrative is fully discounted in prices.
- **Exhaustion**: Frequency is declining or plateauing. Authority distribution is contracting toward lower-tier sources. Data confirmation is deteriorating or the narrative claims are no longer being challenged. Market impact is declining as the narrative becomes background noise.
- **Collapse or Persistence**: The narrative either collapses under contradictory evidence (fast, price-violent) or transitions to a background assumption that no longer drives price action (slow, benign fade).

### 4.9 Sell-Side Consensus Tracking

Monitor the evolution of sell-side analyst consensus on gold, macro conditions, and Fed policy. Sell-side consensus is a lagging indicator that amplifies existing narratives and typically peaks at narrative extremes — when 90% of sell-side analysts recommend buying gold, the gold narrative is at consensus and vulnerable to reversal.

Track: (1) analyst ratings distribution for gold miners and gold ETFs — the ratio of buy/hold/sell ratings, (2) gold price target consensus and dispersion — tight consensus near current price signals narrative exhaustion; wide dispersion signals active debate, (3) macro house view distribution — are sell-side strategists bullish, bearish, or neutral on gold, and how has the distribution shifted over the trailing month?, (4) sell-side narrative phrase frequency — which phrases appear most frequently in sell-side gold research ("structural bid," "real yield sensitivity," "central bank buying," "safe haven premium"), and (5) sell-side narrative innovation rate — are analysts introducing new arguments or recycling established ones.

Sell-side consensus provides a valuable contrarian indicator at extremes but should not be dismissed as always wrong. The department distinguishes between sell-side consensus that is data-supported and sell-side consensus that has become a herding behavior disconnected from fundamentals.

### 4.10 Cross-Department Narrative Reconciliation

Synthesize narrative intelligence across all upstream departmental inputs to produce a unified institutional narrative assessment. Central Bank Intelligence identifies policy narratives. Capital Flow Intelligence identifies positioning narratives. Cross-Asset Intelligence identifies regime narratives. Narrative Intelligence integrates all of these into a composite picture: is the dominant market narrative consistent across policy, positioning, and price behavior? If policy is saying one thing, positioning is implying another, and prices are reflecting a third, the narrative structure is fractured — a precursor to significant price adjustment.

Produce a weekly cross-departmental narrative coherence score: a measure of how closely aligned the narratives carried by each upstream department are with the overall market narrative. High coherence means all departments see the same story. Low coherence means a significant story gap exists — an opportunity or risk that the unified institutional view has not yet incorporated.

---

## 5. Knowledge Produced

The department produces institutional knowledge in five domains.

**Narrative Regime Knowledge**: What is the current dominant market narrative? What is its lifecycle phase, strength, and persistence? Is it confirmed or contradicted by incoming data? What would a regime change look like — what catalyst would overthrow the current narrative, and what successor narrative is most likely? The narrative regime is the institution's most comprehensive answer to the question "what story is the market telling itself right now?"

**Narrative Conflict Knowledge**: Where are the active contradictions in market discourse? Which narratives cannot both be correct, and what is the balance of evidence for each? Narrative conflicts define the uncertainty regime — the higher the conflict intensity, the more cautious the institution should be about high-conviction directional positions. Conflicts that are approaching resolution (one narrative clearly winning) flag approaching opportunity.

**Narrative Positioning Knowledge**: Is the dominant narrative being acted upon or merely discussed? A narrative that appears in the discourse without corresponding flow and positioning data is cheap talk — interesting but not market-moving. A narrative that is confirmed by extreme positioning and confirmed by flow data has been fully adopted and is at risk of reversal. The gap between narrative frequency and narrative positioning is the department's highest-conviction tactical signal.

**Narrative Data Gap Knowledge**: Where is the dominant narrative making claims that incoming data is likely to contradict? The gap between the narrative's implied trajectory and the probable data path defines the surprise potential. A narrative that claims "inflation is resurging" entering a period where base effects and lagged shelter costs are likely to produce benign CPI prints is a narrative about to collide with reality. The department identifies these upcoming collisions and assesses their probable market impact.

**Narrative Exhaustion Knowledge**: Which narratives are nearing the end of their lifecycle? Which are becoming stale (repetitive content, declining authority, plateaued frequency)? Which are most vulnerable to collapse? Narrative exhaustion intelligence allows the Knowledge Department to begin formulating successor theses before the current narrative collapses — enabling a proactive rather than reactive institutional response to narrative regime change.

---

## 6. Decisions This Department Never Owns

Narrative Intelligence is an intelligence producer, not a decision-maker. The following decisions are explicitly outside its mandate:

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
| Central bank policy bias assessment | Central Bank Intelligence |
| Cross-asset relationship classification | Cross-Asset Intelligence |
| Flow source classification | Capital Flow Intelligence |
| Price target determination | Forecasting & Risk |

The department provides intelligence about what the market is saying, who is saying it, and whether the story is supported by fact and action. It does not prescribe action. Its products inform the reasoning chain — they do not bypass it. A narrative in the consensus phase is not a sell signal. A narrative in the emergence phase is not a buy signal. The department describes the narrative structure the market is operating within — the Knowledge Department decides what to do about it.

---

## 7. Downstream Consumers

The following existing AurumAI departments consume Narrative Intelligence output.

### 7.1 Institutional Knowledge Department

**Primary consumer.** Narrative intelligence enters the Knowledge Department as evidence within the reasoning chain. Narrative regime assessments, conflict scores, positioning-gap analysis, and exhaustion warnings become evidence items weighted by the Evidence Weighter and consumed by the Reasoning Engine. Narrative intelligence provides a critical conviction calibrator — a fundamentally-supported gold thesis that aligns with an emerging narrative that has not yet reached consensus carries different conviction than the same thesis supported by a narrative that is already exhausted and priced in.

Specific consumption points:
- Evidence Repository receives narrative strength scores, narrative conflict alerts, and narrative positioning-gap assessments as distinct evidence classes
- Feature Extraction consumes structured narrative features (narrative lifecycle phase, confirmation score, conflict intensity) for lesson-building — the lifecycle phase of the dominant gold narrative is a meaningful feature for interpreting gold-specific evidence
- Context Enrichment receives narrative context for cross-referencing against fundamental data and central bank context — when fundamental data supports a directional view but the dominant narrative contradicts it, the cross-reference produces a nuanced evidence picture that is more valuable than either input alone
- Reasoning Engine receives narrative conviction calibration — the gap between narrative strength and positioning is a direct input to conviction scoring

### 7.2 Forecasting & Risk Department

Narrative regime assessments inform forecast confidence intervals. When narrative conflicts are elevated, the Forecasting Department widens confidence intervals across all macro variables — the existence of contradictory narratives means the market is uncertain about which regime will prevail, and forecasts should reflect that uncertainty. When a narrative is approaching consensus with data confirmation, forecasts can carry tighter confidence bands. Narrative transition velocity estimates inform expected volatility regime — the faster a transition is occurring, the higher the expected near-term volatility.

### 7.3 Central Bank Intelligence Department

Coordination relationship. Central Bank Intelligence provides the authoritative central bank narrative layer: what central banks are saying about their own policy intentions. Narrative Intelligence provides the market narrative layer: how the market is interpreting, amplifying, or distorting central bank communications. When Central Bank Intelligence assesses a dovish policy bias but the market narrative is hawkish (the market does not believe the central bank), a significant narrative gap exists that the two departments must jointly analyze. The gap between communicated intent and market interpretation is one of the highest-value cross-departmental signals.

### 7.4 Cross-Asset Intelligence Department

Coordination relationship. Narrative Intelligence identifies the story the market is telling itself. Cross-Asset Intelligence validates or contradicts that story through price action and relationship behavior. A narrative that claims "risk-on reflation" should be confirmed by rising equities, rising commodities, falling dollar, and rising breakevens — if the narrative is present in the discourse but cross-asset behavior contradicts it, the narrative is either early (about to be validated by price) or false (price will not follow). The two departments co-validate through continuous cross-reference.

### 7.5 Capital Flow Intelligence Department

Coordination relationship. Narrative Intelligence measures what is being said. Capital Flow Intelligence measures what is being done. A narrative that is gaining frequency without corresponding flow patterns is still in the adoption phase — opinions are forming but capital has not yet committed. A narrative that is declining in frequency but still supported by extreme positioning is a zombie narrative — the story is dead but the positioning has not yet unwound. The gap between narrative lifecycle and flow lifecycle is one of the department's most predictive cross-references.

### 7.6 Simulation & Validation Department

Historical narrative regime data is essential for realistic backtesting. A simulation that replays a historical gold rally without incorporating the narrative context of the time — the "transitory inflation" narrative of 2021, the "aggressive tightening" narrative of 2022, the "central bank buying" narrative of 2023-2025 — produces a structurally incomplete representation of the market environment. Narrative-aware simulation enables the institution to test whether a given strategy would have been adopted given the contemporaneous narrative environment, rather than evaluating strategy performance with the benefit of narrative hindsight.

---

## 8. Upstream Providers

The following existing AurumAI departments provide input to Narrative Intelligence.

### 8.1 Natural Language Processing Department

Provides the quantitative foundation for all narrative analysis: sentiment scoring across multiple models (FOMC RoBERTa for central bank text, FinBERT for financial news), topic classification and entity extraction, named entity recognition, frequency analysis, and co-occurrence matrices. NLP processes the raw text; Narrative Intelligence interprets the patterns. The two departments co-evolve — as Narrative Intelligence identifies new narrative themes requiring tracking, NLP expands its model coverage and classification taxonomy accordingly.

### 8.2 News Intelligence Department

Provides the curated news flow that constitutes a primary narrative source: macro-relevant article selection, geopolitical tagging, event classification, and source tier assignment. The News Intelligence Department filters the global flow of financial and economic news to a manageable, relevant feed. Narrative Intelligence analyzes patterns across this feed. The two departments are tightly integrated — News Intelligence defines what constitutes a narrative-relevant source; Narrative Intelligence defines what constitutes a narrative signal within that source.

### 8.3 External Data Connectors Department

Provides access to all text data feeds: financial news wire subscriptions, sell-side research aggregator access, earnings call transcript APIs, central bank document publication calendars, conference schedule data, and regulatory filing databases. Data access breadth and depth directly determine the department's maximum possible intelligence coverage — a narrative that appears only in a source the department does not monitor is a narrative the department cannot detect.

### 8.4 Central Bank Intelligence Department

Provides the central bank narrative layer as a structured input. Policy bias scores, forward guidance interpretations, liquidity assessments, and dot plot analyses are not raw text but already-processed intelligence that Narrative Intelligence consumes as a high-authority narrative source. Central Bank Intelligence's outputs inform the authority weighting of central bank-adjacent narrative signals.

### 8.5 Cross-Asset Intelligence Department

Provides the market-derived narrative validation layer. The Cross-Asset Regime Assessment, Correlation Stability Index, and rotation signals provide quantitative cross-reference against which narrative strength claims are validated or contradicted. A narrative gaining frequency while cross-asset behavior confirms it is self-reinforcing. A narrative gaining frequency while cross-asset behavior contradicts it is approaching a breaking point.

### 8.6 Capital Flow Intelligence Department

Provides the positioning validation layer. COT positioning extremes, ETF flow momentum, and the Speculative Flow Asymmetry Assessment provide the quantitative answer to the question "is this narrative being acted upon?" A consensus-phase narrative with extreme positioning and decelerating flow momentum is a narrative ready to collapse. An emergence-phase narrative with steady accumulation and room for additional positioning is a narrative with runway.

---

## 9. Daily Workflow

The daily workflow runs every trading day. Narrative analysis is continuous — the narrative environment can shift within a single trading session on a single data release or policy remark.

| Time (UTC) | Activity | Purpose |
|------------|----------|---------|
| 06:00 | Overnight narrative scan | Capture Asian and early European session narrative developments — any new themes emerging in Asian financial media, overnight sell-side research notes from Asian and European desks, any overnight central bank remarks or data releases that shift narrative context |
| 06:30 | Topical frequency update | Update narrative mention frequencies across all tracked themes based on overnight text flow; flag any theme whose frequency increased by more than 1 standard deviation from its trailing 30-day average |
| 07:00 | Narrative strength recalibration | Recalculate composite narrative strength scores for Themes 1-15 based on overnight frequency, authority, and sentiment signals; flag any theme that changed strength score by more than 5 points |
| 08:00 | European open narrative read | Analyze narrative tone at European open — are European commentators framing the narrative environment differently from their Asian counterparts? Narrative divergence across regions signals that regional-specific factors are overriding the global narrative |
| 12:00 | Midday conflict scan | Run narrative conflict detection across all theme pairs; flag any conflict that has intensified or weakened significantly since the previous scan; update the Narrative Conflict Matrix |
| 15:00 | US session narrative integration | Integrate US market open developments — US data releases, Fed communications, US sell-side research notes, US financial media coverage — into the global narrative assessment |
| 17:00 | Daily narrative intelligence summary | Produce a brief daily note: the current dominant narrative and its lifecycle phase, any new narratives detected, any narrative conflicts that intensified, the day's most significant narrative-frequency changes, and any approaching catalysts that could shift the narrative regime in the next 48 hours |

**On major data release days** (NFP, CPI, FOMC, GDP), the workflow expands to include real-time narrative shift monitoring — how does the commentary change in the first hour after the release? Which narratives gain immediate traction? Which are abandoned? The first 60 minutes of post-release narrative formation is the highest-density signal window of the month.

**On earnings season peak days**, the workflow expands to include earnings call transcript narrative extraction — management commentary on macro conditions provides a ground-level view of whether the official narrative matches corporate experience.

---

## 10. Weekly Workflow

The weekly workflow runs every Friday, synthesizing the week's intelligence into standing assessments.

| Activity | Output | Distribution |
|----------|--------|-------------|
| Narrative strength score full review | Updated strength scores for all 15 tracked themes; 1-week, 4-week, and 13-week frequency and strength trends; any theme that crossed a lifecycle phase boundary | Knowledge Department, All Intelligence Departments |
| Narrative conflict matrix refresh | Complete conflict matrix — all tracked theme pairs, conflict intensity scores, conflict trend (intensifying/stable/resolving), most probable resolution catalysts | Knowledge Department, Forecasting & Risk |
| Sell-side consensus update | Updated analyst rating distribution, price target consensus and dispersion, macro house view distribution for gold | Knowledge Department |
| Narrative positioning gap analysis | Compare narrative strength scores against capital flow data for each theme; identify themes where narrative has run ahead of positioning (risk of reversal) and themes where positioning has run ahead of narrative (room for narrative to catch up) | Knowledge Department, Capital Flow Intelligence |
| Cross-department narrative coherence assessment | Calculate and distribute the narrative coherence score — how closely aligned are the policy narrative, positioning narrative, price narrative, and market narrative? Flag any material divergence for joint departmental review | All Intelligence Departments |
| Weekly narrative intelligence brief | 2-3 page synthesis of the week's narrative environment: dominant narrative assessment, narrative conflicts requiring attention, narrative regime change warnings, approaching catalysts, and cross-departmental coherence status | All consuming departments |

---

## 11. Monthly Workflow

The monthly workflow runs on the last business day of each month, producing the department's most comprehensive assessments.

| Activity | Output | Distribution |
|----------|--------|-------------|
| Full narrative regime assessment | Comprehensive analysis of the current dominant narrative, its lifecycle phase, strength trajectory, confirmation status, and expected persistence horizon; identification of the most probable successor narrative if the current regime is nearing exhaustion | Knowledge Department, All Intelligence Departments, Forecasting & Risk |
| Narrative transition velocity report | Quantitative analysis of narrative transition speeds over the trailing month and trailing 12 months; comparison of current transition velocity against historical norms; identification of whether narrative transitions are accelerating or decelerating (acceleration signals increasing macro uncertainty) | Knowledge Department, Forecasting & Risk |
| Narrative data gap analysis | Forward-looking identification of the most significant gaps between dominant narrative claims and expected incoming data flow; ranked by expected market impact of resolution | Knowledge Department |
| Narrative origin register update | New narratives detected during the month cataloged with origin, initial adoption velocity, and early lifecycle phase classification | Internal departmental use |
| Narrative decay watch list refresh | Updated assessment of narratives approaching exhaustion or collapse; ranked by collapse probability and expected market impact | Knowledge Department |
| Sell-side consensus deep dive | Quarterly comprehensive sell-side consensus report: analyst rating trends, thesis evolution, new arguments introduced vs old arguments retired, consensus quality assessment (is consensus data-supported or herding-driven?) | Knowledge Department, Forecasting & Risk |
| Lifecycle recalibration | Recalibrate lifecycle phase transition thresholds based on trailing 12 months of narrative data; update half-life baselines, frequency extreme thresholds, and authority weight parameters | Internal departmental use |
| Forecast accuracy review | Compare prior month's narrative assessments (strength scores, lifecycle phase classifications, transition predictions, collapse warnings) against actual narrative developments; calibrate confidence levels | Internal departmental use |

---

## 12. Narratives Tracked

The department maintains analytical coverage of fifteen institutional narratives. Each narrative represents a distinct thematic structure that can drive macro asset prices, particularly gold, for sustained periods.

### 12.1 Inflation Narrative

**Coverage tier**: Tier 1 — Maximum depth  
**Theme type**: Directional macro  
**Core claim**: Inflation is currently rising/falling/staying elevated and will drive central bank policy responses that affect asset prices  
**Sub-narratives tracked**: Transitory inflation, persistent inflation, structural inflation (demographic, deglobalization, energy transition drivers), inflation peak / inflation trough, wage-price spiral, shelter inflation stickiness, goods vs services inflation divergence  
**Gold relevance**: Direct and primary. Inflation narrative directly drives gold through the inflation expectation channel and the real yield channel. Gold is the ultimate inflation hedge asset; when inflation narrative is dominant, gold is structurally supported. The specific sub-narrative determines gold sensitivity — persistent inflation (strong gold support), transitory inflation (weak gold support), inflation peaking (gold headwind)  
**Lifecycle sensitivity**: Most dangerous for gold during consensus phase — inflation as consensus trade is vulnerable to a cooling CPI print that causes narrative collapse and gold liquidation

### 12.2 Recession Narrative

**Coverage tier**: Tier 1 — Maximum depth  
**Theme type**: Directional macro  
**Core claim**: The economy is entering a recession that will force central bank easing and drive safe-haven asset demand  
**Sub-narratives tracked**: Soft landing (growth slows but recession avoided), hard landing (recession confirmed), rolling recession (sectors recessing sequentially, no aggregate recession), technical recession (two quarters negative GDP, mild), financial crisis recession (systemic event), consumer strain narrative, housing recession, manufacturing recession  
**Gold relevance**: High but conditional. A recession narrative supported gold through two channels: (1) expected central bank easing — lower rates reduce gold opportunity cost, and (2) safe-haven demand — recession triggers defensive portfolio rotation. However, a liquidity crisis recession (all assets sold for cash) is gold-negative. The specific recession sub-narrative determines which channel dominates  
**Lifecycle sensitivity**: Emergence phase is the most profitable for gold — recession fears long before recession data generates the most powerful gold bid. Consensus phase for recession is typically when gold begins to peak, as recession positioning is fully priced and the narrative has stopped surprising

### 12.3 Soft Landing Narrative

**Coverage tier**: Tier 1 — Maximum depth  
**Theme type**: Conditional macro  
**Core claim**: The economy will slow sufficiently to bring inflation to target without a significant increase in unemployment or a recession  
**Sub-narratives tracked**: Goldilocks (perfect soft landing — below-trend growth, inflation at target), bumpy landing (periodic growth scares but no recession), immaculate disinflation (inflation falls without growth cost), immaculate recovery (recession fears that never materialize)  
**Gold relevance**: Moderately negative. Soft landing is the most gold-negative macro narrative — it implies no recession (no safe-haven demand), no aggressive easing (no opportunity cost relief), and contained inflation (no inflation hedge demand). A gold market that rallies during a soft landing narrative requires structural demand factors (central bank buying) to overcome the narrative headwind  
**Lifecycle sensitivity**: The narrative switch from soft landing to hard landing (or vice versa) is among the highest-impact narrative transitions for gold. The 2023-2024 soft landing narrative was the primary headwind preventing gold from rallying despite elevated geopolitical risk

### 12.4 Hard Landing Narrative

**Coverage tier**: Tier 1 — Maximum depth  
**Theme type**: Directional macro  
**Core claim**: The economy will enter a significant recession with rising unemployment, falling corporate profits, and systemic stress  
**Sub-narratives tracked**: Classic cyclical recession, credit crunch recession (banking system-led), policy error recession (Fed overtightens), external shock recession (geopolitical, commodity price shock), balance sheet recession (household/corporate debt overhang)  
**Gold relevance**: Strongly positive in the emergence and adoption phases. Hard landing narrative drives aggressive central bank easing expectations (gold-positive) and intense safe-haven demand (gold-positive). The critical threshold is whether the hard landing narrative escalates to a liquidity crisis narrative — at which point gold may be temporarily sold alongside all other assets to meet margin calls and redemptions  
**Lifecycle sensitivity**: The transition from soft landing to hard landing narrative is the single most powerful narrative gold catalyst. It triggers simultaneous repricing of rate expectations, safe-haven allocations, and portfolio defense. The transition typically unfolds over two to six weeks and coincides with the most rapid gold price appreciation periods

### 12.5 Higher for Longer Narrative

**Coverage tier**: Tier 1 — Maximum depth  
**Theme type**: Central bank policy  
**Core claim**: Central banks — particularly the Federal Reserve — will maintain elevated policy rates for an extended period regardless of economic growth concerns, because inflation is proving persistent  
**Sub-narratives tracked**: Structural higher for longer (neutral rate has structurally increased), cyclical higher for longer (temporary but extended hold), forced higher for longer (fiscal dominance, inflation persistence force rates up), patient Fed (will wait for definitive evidence before cutting)  
**Gold relevance**: Negative. Higher for longer directly pressures gold through elevated real yields (higher opportunity cost) and a stronger dollar (higher rate differentials). The gold-negative impact is partially offset if higher-for-longer increases recession risk (through restrictive policy) — in that case, gold faces a tug-of-war between opportunity cost headwind and safe-haven tailwind  
**Lifecycle sensitivity**: This narrative is most potent for gold during adoption phase (when markets are raising terminal rate expectations). It becomes less relevant for gold during consensus phase (gold adjusts, structural demand factors reassert). The collapse of higher for longer in favor of a rate-cutting narrative is a powerful gold catalyst

### 12.6 De-Dollarization Narrative

**Coverage tier**: Tier 1 — Maximum depth  
**Theme type**: Structural macro  
**Core claim**: The US dollar's role as the world's primary reserve currency is declining as central banks and sovereign wealth funds diversify reserves into gold, other currencies, and alternative assets  
**Sub-narratives tracked**: Reserve diversification (central banks rebalancing to reduce USD dependence), sanctions avoidance (petrostates and targeted nations seeking alternatives to USD settlement), BRICS+ reserve currency initiative, China-driven de-dollarization, US fiscal credibility decline (debt and deficit concerns driving reserve diversification), incremental de-dollarization (slow, steady, multi-decade)  
**Gold relevance**: This is the single most structurally bullish narrative for gold tracked by the department. De-dollarization implies sustained central bank gold demand, reduced USD-denominated asset demand, and a structural shift in gold's reserve asset role. The narrative, if sustained, provides a structural bid under gold that operates independently of the cyclical macro environment — it is the narrative equivalent of the central bank reserve flow data tracked by Capital Flow Intelligence  
**Lifecycle sensitivity**: Persistence phase (structural). De-dollarization is a multi-year or multi-decade narrative that does not follow the standard emergence-adoption-consensus-exhaustion lifecycle. It persists as a background structural assumption that occasionally moves to the foreground during specific catalysts (BRICS summits, US fiscal events, sanctions escalations). The department tracks de-dollarization not for tactical timing but for structural gold conviction calibration

### 12.7 Safe-Haven Narrative

**Coverage tier**: Tier 1 — Maximum depth  
**Theme type**: Defensive/event-driven  
**Core claim**: Geopolitical, financial, or economic uncertainty is driving investors to seek safe-haven assets, with gold as the primary beneficiary  
**Sub-narratives tracked**: Geopolitical safe-haven (war, conflict, sanctions), financial safe-haven (banking crisis, credit event, market crash), dollar safe-haven question (is the dollar still the safe-haven of last resort?), inflation safe-haven (gold as purchasing power protection), sovereign debt safe-haven (gold as alternative to government bonds), debasement safe-haven (gold as hedge against currency devaluation via fiscal expansion or money printing)  
**Gold relevance**: The safe-haven narrative is gold's natural habitat. Gold is the original and most universally recognized safe-haven asset. The strength and persistence of the safe-haven narrative determines the magnitude of gold's premium above what fundamental models (real yields, dollar, etc.) would predict  
**Lifecycle sensitivity**: Event-driven, typically following a shock-and-decay pattern: a trigger event produces a spike in safe-haven narrative frequency, which gradually decays over two to six weeks as the shock is absorbed. The department's most valuable safe-haven narrative product is distinguishing between safe-haven spikes that will fully decay (return to pre-event gold fair value) and safe-haven spikes that establish a new, higher baseline (the event has permanently increased the gold risk premium)

### 12.8 AI Investment Cycle Narrative

**Coverage tier**: Tier 2 — High depth  
**Theme type**: Sectoral/cyclical  
**Core claim**: The emergence of generative artificial intelligence is driving a multi-year investment cycle in data centers, semiconductor manufacturing, energy infrastructure, and electrical grid upgrades, with macro implications for growth, inflation, and asset allocation  
**Sub-narratives tracked**: AI productivity boom (AI drives structural productivity growth that is disinflationary), AI capex cycle (AI investment drives growth and capex demand, is inflationary for specific sectors), AI energy demand (AI data center power demand drives energy investment and commodity demand), AI race (US-China AI competition drives national security-focused industrial policy and supply chain reconfiguration)  
**Gold relevance**: Indirect but growing. Gold's primary exposure to the AI narrative is through: (1) energy demand — AI-driven electricity demand drives natural gas, nuclear, and renewable investment which affects energy inflation and commodity demand, (2) electronics demand — gold is used in semiconductor manufacturing and electronics; AI data center buildout drives server demand, which drives electronics component demand, (3) macro growth — AI productivity gains affect growth/inflation/revenue trajectories that influence central bank policy and macro cycles, (4) equity flow competition — AI narrative attracts significant equity capital that competes with gold allocation in multi-asset portfolios  
**Lifecycle sensitivity**: Early adoption phase. The AI narrative has been a dominant force in equity markets since 2023 but is still in early adoption for gold-specific implications. The department expects increasing integration of AI narrative into gold analysis as AI energy demand and semiconductor growth effects become more material

### 12.9 Energy Transition Narrative

**Coverage tier**: Tier 2 — High depth  
**Theme type**: Structural/sectoral  
**Core claim**: The global transition from fossil fuels to renewable and low-carbon energy sources is driving structural changes in energy markets, commodity demand, capital allocation, inflation, and industrial policy  
**Sub-narratives tracked**: Green capex supercycle (renewable energy investment drives commodity demand — copper, lithium, silver, rare earths), energy inflation (transition creates cost-push inflation through carbon pricing, stranded assets, and energy system reconfiguration), transition realism (recognition that transition is slower, more expensive, and more complex than initially assumed), critical mineral supply chain (energy transition creates new strategic dependencies and supply chain vulnerabilities)  
**Gold relevance**: Moderate and strengthening. Direct channels: (1) silver demand — energy transition (solar panels) significantly expands industrial silver demand, affecting the gold/silver relationship, (2) inflation channel — transition-driven energy inflation affects central bank policy and gold's inflation hedge role, (3) fiscal channel — government spending on transition (subsidies, infrastructure, industrial policy) adds to fiscal expansion that structurally supports gold through the sovereign credit/debasement channel, (4) capital allocation — energy transition-themed funds and ESG mandates affect commodity flows  
**Lifecycle sensitivity**: Persistence phase (structural). Like de-dollarization, the energy transition is a multi-decade structural narrative that operates at a background level. It is elevated to active monitoring during specific catalyst events (COP conferences, major policy announcements, energy price shocks)

### 12.10 Fiscal Expansion Narrative

**Coverage tier**: Tier 2 — High depth  
**Theme type**: Structural/policy  
**Core claim**: Sustained government deficit spending — driven by demographics, defense, industrial policy, entitlement programs, and debt service costs — is creating a structural fiscal expansion that drives bond supply, crowds out private investment, and ultimately constrains central bank independence  
**Sub-narratives tracked**: Fiscal dominance (fiscal needs overriding monetary policy independence — central banks cannot tighten sufficiently because high rates would make government debt service unmanageable), US debt trajectory (debt/GDP ratio on unsustainable path, driving structural Treasury yield premium), industrial policy spending (CHIPS Act, IRA, infrastructure spending as ongoing fiscal impulse), defense spending cycle (NATO commitments, great power competition driving sustained defense expenditure increases), entitlement demographic (aging populations in developed markets driving structural social security and healthcare spending increases)  
**Gold relevance**: Structurally positive. Fiscal expansion supports gold through three channels: (1) sovereign credit concern — persistent large deficits raise sovereign default risk premium on government bonds, making gold an increasingly attractive alternative store of value, (2) fiscal dominance — if fiscal needs prevent central banks from tightening rates, real yields remain suppressed even during inflationary periods, removing gold's primary headwind, (3) debasement expectation — persistent deficit spending without corresponding growth creates currency debasement expectations that drive structural gold demand  
**Lifecycle sensitivity**: Persistence phase (structural) with episodic activation. The fiscal expansion narrative is a permanent background condition in developed markets post-2020, but it intensifies during specific episodes — debt ceiling crises, credit rating downgrades, budget negotiations, and sovereign credit events at the periphery that demonstrate the risks of fiscal excess

### 12.11 Credit Tightening Narrative

**Coverage tier**: Tier 2 — High depth  
**Theme type**: Cyclical/financial conditions  
**Core claim**: Banks are tightening lending standards, reducing credit availability, and constraining economic activity through the credit channel — functioning as a de facto monetary policy tightening that supplements or replaces central bank rate actions  
**Sub-narratives tracked**: Bank lending standards tightening (quarterly SLOOS data — the most authoritative credit tightening signal), regional bank stress (deposit flight, commercial real estate exposure, unrealized bond losses constraining regional bank lending), credit crunch (credit availability contraction significant enough to choke off economic growth), shadow bank tightening (private credit, fintech lenders, and non-bank financial intermediaries reducing credit supply), corporate debt maturity wall (upcoming refinancing needs at higher rates creating credit stress)  
**Gold relevance**: Mixed with positive bias. Credit tightening supports gold through the easing expectation channel — tighter credit conditions substitute for rate hikes and increase the probability of future rate cuts. However, credit tightening that escalates to a credit crunch can trigger a liquidity crisis that temporarily pressures gold. The net gold impact depends on whether the credit tightening is orderly (moderate, gradual, policy-responsive — gold-positive) or disorderly (sudden, systemic, confidence-shattering — gold-negative in near term, gold-positive in medium term as central banks respond aggressively)  
**Lifecycle sensitivity**: Narrative adoption phase typically aligns with gold's transition from cyclical headwind to safe-haven support. The narrative becomes most market-relevant during SLOIS release weeks, bank earnings seasons, and regional bank stress episodes

### 12.12 Global Growth Narrative

**Coverage tier**: Tier 2 — High depth  
**Theme type**: Directional macro  
**Core claim**: Global economic growth is accelerating, decelerating, or following a specific trajectory that determines commodity demand, trade flows, capital flows, and central bank policy direction  
**Sub-narratives tracked**: Global growth synchrony (all major economies expanding/contracting simultaneously — high macro conviction), growth divergence (US outperforming, Europe/China underperforming — more complex macro picture), China growth narrative (recovery, stagnation, property crisis, stimulus-driven reacceleration), Europe growth narrative (energy crisis hangover, competitiveness concerns, fiscal integration progress), EM growth narrative (demographic dividend, manufacturing relocation, NEarshoring beneficiaries)  
**Gold relevance**: Indirect through multiple channels. Strong global growth is moderately gold-negative (risk-on flows favor equities and credit over gold, higher real yields from growth-driven demand). Weak global growth is gold-positive through safe-haven demand and rate-cut expectations. However, the growth narrative interacts with all other narratives — a global growth slowdown combined with inflation (stagflation narrative) is gold's strongest environment; a global growth boom with contained inflation is gold's weakest  
**Lifecycle sensitivity**: The global growth narrative evolves slowly (multi-month to multi-year) and rarely produces sudden narrative transitions. Its most valuable gold signal is at inflection points — the narrative shift from "global growth acceleration" to "global growth peaking" or from "growth slowdown" to "growth stabilization"

### 12.13 Supply Chain Disruption Narrative

**Coverage tier**: Tier 2 — High depth  
**Theme type**: Structural/event-driven  
**Core claim**: Global supply chains are persistently disrupted by geopolitical conflict, trade fragmentation, industrial policy, natural disasters, or pandemic after-effects, causing goods inflation, delivery delays, inventory costs, and production constraints  
**Sub-narratives tracked**: COVID-era supply chain crisis (post-pandemic reopening bottlenecks — 2021-2022), deglobalization supply chain restructuring (friendshoring, near-shoring, China+1, Taiwan contingency planning), shipping disruption (Red Sea, Suez Canal, Panama Canal, container shipping cost volatility), critical mineral supply risk (rare earths, lithium, copper supply concentration concerns), semiconductor supply chain (Taiwan dependency, CHIPS Act/European Chips Act diversification)  
**Gold relevance**: Moderate. Supply chain disruption supports gold through the inflation channel — disrupted supply chains create goods inflation pressure that keeps headline inflation elevated, supports the inflation narrative, and sustains gold's inflation hedge demand. Specific supply chain events (shipping route disruption, critical mineral supply threats) can trigger gold safe-haven spikes. The broader deglobalization supply chain sub-narrative is a structural gold positive — it implies permanently higher inflation volatility and increased geopolitical risk premium in gold  
**Lifecycle sensitivity**: Event-driven with structural background. The narrative intensifies during specific disruption events (Houthi Red Sea attacks, Taiwan drills, port strikes, natural disasters) and fades during calm periods. The department distinguishes between disruption spikes that decay (temporary event effects) and disruption shifts that persist (structural deglobalization effects)

### 12.14 Commodity Supercycle Narrative

**Coverage tier**: Tier 2 — High depth  
**Theme type**: Structural/sectoral  
**Core claim**: We are in or approaching a multi-year period of sustained commodity price appreciation driven by structural demand (population growth, urbanization, energy transition, reindustrialization) constrained by structural supply limitations (underinvestment, ESG constraints, geological depletion, geopolitical concentration)  
**Sub-narratives tracked**: Energy transition commodity demand (copper, lithium, silver, rare earths demand from green infrastructure), underinvestment supercycle (decade of commodity underinvestment creating supply constraints across oil, copper, uranium, agriculture), geopolitical supply risk (concentrated commodity production in geopolitically risky jurisdictions), China commodity demand (property sector decline vs manufacturing/export strength), commodity capex cycle (rising commodity prices eventually generating supply response, ending the supercycle)  
**Gold relevance**: Gold is a unique case within the commodity supercycle narrative. It is not consumed like industrial commodities, so the standard supply/demand supercycle framework does not apply directly. However, gold benefits from the commodity supercycle narrative through: (1) commodity allocation — investors rotating from equities/bonds to commodities allocate a share to gold, (2) inflation channel — broad commodity price appreciation drives inflation, supporting gold's inflation hedge role, (3) real asset preference — commodity supercycle narrative emphasizes real assets over financial assets, and gold is the most established real asset, (4) central bank behavior — commodity-exporting central banks accumulate gold as commodity revenues increase reserve accumulation capacity  
**Lifecycle sensitivity**: Persistence phase (structural) with episodic intensification. Like de-dollarization and the energy transition, the commodity supercycle is a multi-year structural narrative that functions as a background condition until a specific catalyst (commodity price spike, supply disruption, major policy announcement) elevates it to active market relevance

### 12.15 Risk-On / Risk-Off Narrative

**Coverage tier**: Tier 1 — Maximum depth  
**Theme type**: Regime/classification  
**Core claim**: The market is in a risk-seeking (risk-on) or risk-averse (risk-off) regime that determines which assets are favored and which are avoided  
**Sub-narratives tracked**: Risk-on (equities favored, credit tight spreads, commodities rally, dollar weak, gold moderate), risk-off (Treasuries and gold favored, equities fall, credit spreads widen, dollar strong), risk-on within risk-off (quality risk-on — large-cap tech rallies while small caps and credit decline), risk-off within risk-on (sectoral defensive rotation within an overall risk-on market), regime transition (narrative explicitly discussing whether a risk-on or risk-off regime change is approaching)  
**Gold relevance**: Gold is one of the few assets that benefits from both risk-on and risk-off regimes, which is a unique feature that the department monitors closely. In risk-off, gold is a safe haven. In risk-on, gold benefits from commodity demand, dollar weakness, and liquidity expansion. The specific sub-narrative determines gold's behavior: risk-off driven by geopolitics (strong gold rally), risk-off driven by liquidity crisis (initial gold selloff, subsequent safe-haven bid), risk-on driven by growth (moderate gold headwind), risk-on driven by liquidity expansion (gold rally alongside all assets)  
**Lifecycle sensitivity**: The risk-on/risk-off narrative is the most frequently shifting of all tracked narratives and the most integrative — it is typically a function of the interaction between all other narratives. The department generates its most valuable risk-on/risk-off intelligence not by tracking the narrative itself but by tracking the narrative contradictions that precede a regime change — when risk-off narrative is dominant but gold is selling off, or when risk-on narrative is dominant but gold is rallying

---

## 13. Intelligence Dimensions

The department produces intelligence across the following dimensions. Each dimension represents a distinct analytical perspective that requires different data sources, analytical methods, and temporal horizons.

### 13.1 Narrative Origin

**Definition**: The source and circumstances of a narrative's first emergence in the tracked discourse.

**Analytical output**: Originator identification (individual, institution, event, or emergent pattern), origination date and context, initial medium, initial authority tier, initial adoption velocity (how quickly did the narrative spread from its origin to Tier 2 and Tier 3 sources?), origin type classification (deliberate communication, data-driven emergence, event-driven emergence, market behavior pattern).

**Temporal signature**: Origin analysis is retrospective and archival — it is most valuable for understanding the nature of a narrative, not for predicting its trajectory. However, narratives with deliberate, high-authority origins tend to have faster adoption curves and longer half-lives than emergent narratives. The department maintains origin records for all tracked narratives and uses origin type as an input to persistence forecasting.

### 13.2 Narrative Strength

**Definition**: A composite measure of narrative intensity across frequency, authority, sentiment, and market impact dimensions.

**Primary indicators**: Frequency z-score (deviation from trailing mean), authority-weighted frequency, sentiment intensity score, market impact correlation, narrative force (frequency multiplied by authority multiplied by sentiment intensity).

**Analytical output**: Composite Strength Score (0-100), strength breakdown by dimension (which dimensions are driving the current strength level — is this a broad-based strong narrative or one that appears strong only because of high low-authority frequency?), strength trajectory (strengthening/stable/weakening), strength acceleration (rate of change in strength score over 1-week and 4-week windows).

**Temporal signature**: Strength is the department's most dynamic dimension — it can shift from neutral to extreme within a single trading session (post-data release) or build gradually over weeks. Strength trajectory (direction of travel) is more predictive than absolute strength level for near-term narrative evolution.

### 13.3 Narrative Persistence

**Definition**: The duration and structural support of a narrative's presence in market discourse.

**Primary indicators**: Narrative half-life (days from peak frequency to 50% decline), residence time (days above 75% of peak frequency), evolution score (rate of new argument introduction — evolving narratives persist longer than static narratives), reinforcement density (how many confirming independent data points or events have occurred during the narrative's lifetime), resuscitation count (how many times has the narrative declined and re-emerged with renewed force).

**Analytical output**: Persistence classification (short-lived under 2 weeks, moderate 2-8 weeks, sustained 8-26 weeks, structural over 26 weeks), structural support assessment (is the narrative being reinforced by ongoing fundamentals or sustained only by repetition?), vulnerability score (how exposed is the narrative to a single contradictory catalyst given its current persistence profile?).

**Temporal signature**: Persistence analysis is most informative once a narrative has been active for at least three weeks — before that, it is too early to distinguish an emerging narrative from a noise event. The department's persistence intelligence is a medium- to long-horizon product that informs institutional assessment of whether a narrative is likely to still be relevant in 3, 6, or 12 months.

### 13.4 Narrative Conflicts

**Definition**: The degree and nature of contradiction between two or more active narratives.

**Primary indicators**: Frequency co-occurrence (how often contradictory narratives appear in the same articles or time windows), conflict intensity (strength of direct contradiction — are the narratives mutually exclusive or merely tension-filled?), balance score (which narrative is currently leading in the conflict?), resolution proximity assessment (how close is the conflict to resolution based on upcoming catalysts?), historical analogue similarity (how similar is this conflict pattern to previous conflicts and their resolutions?).

**Analytical output**: Conflict Matrix (NxN table of all tracked narrative pairs with conflict intensity scores), Conflict Type classification per pair (direct factual contradiction, competing priority, temporal conflict, regime conflict), Conflict Resolution Forecast (expected resolution pathway, trigger catalyst, timeline, and price impact estimate for each resolution direction).

**Temporal signature**: Narrative conflicts are most intense and most predictive during regime transition periods. A high-conflict environment (many narrative pairs with elevated conflict intensity) is the department's strongest signal of approaching macro regime change. Conflicts typically resolve within two to twelve weeks of their peak intensity — the rate of resolution is proportional to the calendar density of data releases and policy events.

### 13.5 Narrative Confirmation

**Definition**: The degree to which a narrative's core claims are supported by incoming economic data, policy decisions, corporate behavior, and market pricing.

**Primary indicators**: Data confirmation rate (percentage of economic data releases in the trailing month consistent with narrative claims), policy consistency score (are policy actions aligned with narrative guidance?), corporate alignment score (are earnings and guidance consistent with narrative assumptions?), market pricing consistency (are asset prices trading consistent with the narrative's valuation framework?), flow alignment score (are capital flows consistent with the narrative's positioning implications?).

**Analytical output**: Composite Confirmation Score (0-100%), per-channel confirmation breakdown (which channels confirm and which contradict), confirmation trajectory (is the narrative gaining or losing empirical support?), confirmation gap score (the difference between narrative strength and confirmation score — a large positive gap means the story is running ahead of the facts, a large negative gap means the facts are ahead of the story).

**Temporal signature**: The confirmation gap is the department's most predictive near-term dimension. A narrative with high strength and low confirmation (story running ahead of facts) has elevated collapse risk and typically converges within two to eight weeks. A narrative with low strength and high confirmation (facts ahead of story) has adoption runway — it will likely strengthen as the market catches up to the data.

### 13.6 Narrative Decay

**Definition**: The indicators that a narrative is approaching exhaustion or collapse.

**Primary indicators**: Frequency trend (declining from peak), authority distribution shift (migration from high-tier to low-tier sources), evolution decay (declining rate of new argument introduction), hedging increase (rising proportion of conditional language — "if," "perhaps," "could"), confirmation deterioration (declining confirmation score over trailing 4-weeks), competing narrative emergence (a contradictory narrative gaining strength), positioning exhaustion (extreme positioning confirming that the narrative has been fully acted upon).

**Analytical output**: Decay Score (0 — no decay indicators triggered, to 100 — all indicators triggered and narrative collapse imminent), dominant decay type (frequency decay, authority decay, confirmation decay, or positioning decay — each has different collapse dynamics), decay velocity (how fast is the narrative deteriorating?), collapse probability estimate (what is the probability that a single catalyst would trigger complete collapse?), collapse trigger identification (what specific data release or event would most likely trigger the collapse?).

**Temporal signature**: Narrative decay is the department's early warning system for narrative collapse. Decay indicators typically appear two to six weeks before the narrative collapses in the discourse and one to four weeks before the positioning adjusts. The longer a narrative has been in consensus phase without showing decay indicators, the more vulnerable it is to a sudden, violent collapse when decay finally sets in.

### 13.7 Narrative Transition

**Definition**: The process by which one dominant narrative is replaced by another.

**Primary indicators**: Incumbent narrative strength trend (is it declining?), challenger narrative strength trend (is it rising?), conflict resolution progress (is the conflict between incumbent and challenger resolving?), narrative substitution rate (for every 100 mentions of the incumbent narrative, how many mentions of the challenger are there?), authority migration (are high-tier sources beginning to adopt the challenger narrative?), catalyst proximity (is the next potential transition-triggering event approaching?).

**Analytical output**: Transition Probability (0-100% probability that a transition from the current dominant narrative to the identified challenger will occur within the next 4 weeks), Transition Archetype classification (gradual displacement, catalyst-driven replacement, coexistence and bifurcation, or false transition and reversal), Transition Velocity Forecast (if transition occurs, how fast will it unfold?), Transition Completeness Forecast (what share of the current narrative's positioning will unwind vs persist as a background assumption?), Post-Transition Regime Assessment (what is the expected narrative environment after the transition stabilizes?).

**Temporal signature**: Narrative transition analysis is the department's highest-value dimension. The transition itself — not the destination — is typically where the greatest market volatility and opportunity reside. The department's transition intelligence is most actionable when the transition probability is between 30% and 70% — below 30%, the transition is too speculative to drive institutional action; above 70%, the transition is already priced in and the opportunity has passed.

---

## 14. Institutional Products

The department emits the following standing institutional products. Each product has a defined format, update cadence, and confidence framework.

### 14.1 Narrative Strength Dashboard

**Definition**: A comprehensive daily dashboard showing the current strength score, lifecycle phase, and 30-day trajectory for each of the fifteen tracked narratives.

**Format**: Single-page visual dashboard with: for each narrative — Composite Strength Score (0-100) with direction-of-trend arrow, current lifecycle phase (Emergence, Adoption, Consensus, Exhaustion, Persistence), 1-week and 4-week strength change, Confirmation Score, and Conflict Flag (if narrative is in active conflict with any other narrative). Gold-relevant narratives are highlighted. The dashboard includes a "Narrative Landscape Summary" — a one-sentence characterization of the current narrative environment (e.g., "Soft landing narrative dominant, challenged by persistent inflation narrative; de-dollarization background structural support for gold").

**Update cadence**: Daily.

**Differentiation from raw data**: The dashboard integrates frequency, authority, sentiment, and market impact data into a single composite assessment per narrative. Raw frequency data is noise; the composite score, lifecycle classification, and trajectory trend are the signal.

**Consumers**: Knowledge Department, All Intelligence Departments.

### 14.2 Narrative Conflict Matrix

**Definition**: A structured matrix showing the active conflicts between all pairs of tracked narratives, with conflict intensity scores and resolution assessments.

**Format**: 15x15 visually coded matrix. Each cell shows the conflict intensity between narrative row and narrative column (0 = no conflict, 10 = direct factual contradiction). The diagonal is intentionally blank (a narrative cannot conflict with itself). A summary row beneath the matrix shows the Aggregate Conflict Index — the average conflict intensity across all active pairs — with a trailing 30-day trend. A "Most Intense Conflicts" callout box lists the top three active conflicts with resolution assessments.

**Update cadence**: Weekly, with interim updates when any conflict changes by more than 1 point.

**Significance**: The Narrative Conflict Matrix is the department's highest-level synthesis product. It provides the entire institution with an immediate answer to "how much narrative uncertainty exists in the current environment?" A high Aggregate Conflict Index signals elevated macro uncertainty and suggests that the current price regime is fragile. A declining Aggregate Conflict Index signals narrative consolidation and improving conviction.

**Consumers**: Knowledge Department, Forecasting & Risk.

### 14.3 Narrative Positioning Gap Report

**Definition**: A weekly product comparing narrative strength against positioning data to identify where the story has run ahead of the capital or vice versa.

**Format**: For each tracked narrative, compare Narrative Strength Score (0-100) against a Positioning Implementation Score (0-100) derived from Capital Flow Intelligence flow and positioning data for assets associated with that narrative. Display as a scatter plot with four quadrants: (1) High Narrative, High Positioning — consensus, fully priced, vulnerable, (2) High Narrative, Low Positioning — narrative in adoption phase, room for capital to flow, (3) Low Narrative, High Positioning — zombie narrative, positioning will eventually unwind, (4) Low Narrative, Low Positioning — irrelevant, no action required.

**Update cadence**: Weekly.

**Significance**: The narrative-positioning gap is the department's most actionable tactical product. The High Narrative / Low Positioning quadrant identifies narratives that have institutional attention but have not yet been fully capitalized — the highest-opportunity quadrant for macro conviction. The High Narrative / High Positioning quadrant identifies narratives that are fully discounted and vulnerable to reversal — the highest-risk quadrant.

**Consumers**: Knowledge Department, Capital Flow Intelligence.

### 14.4 Narrative Regime Assessment

**Definition**: A comprehensive monthly assessment of the current narrative regime, including the dominant narrative, its lifecycle position, active conflicts, and the most probable transition scenarios.

**Format**: Structured report with: Dominant Narrative Identification (which narrative currently has the highest composite strength score and why), Narrative Regime Characterization (coherent single story, fragmented competing stories, unstable transition, structural acceptance), Lifecycle Phase Assessment (where each tracked narrative sits in its lifecycle and how much runway remains), Conflict Landscape Summary (active conflicts, resolution progress, and expected resolution catalysts), Transition Scenarios (ranked by probability: the three most likely narrative regime transitions over the next 1-3 months, with trigger catalysts and expected asset price implications), Cross-Departmental Coherence Section (how well do the policy, positioning, price, and market narratives align? flag any significant divergences).

**Update cadence**: Monthly.

**Significance**: The Narrative Regime Assessment is the department's flagship product. It provides the Knowledge Department and all downstream consumers with the institutional institution's authoritative view of what story the market is telling itself, how much life that story has left, and what story will likely replace it.

**Consumers**: Knowledge Department, All Intelligence Departments, Forecasting & Risk.

### 14.5 Narrative Data Gap Alert

**Definition**: An event-driven product issued when a tracked narrative makes claims that are about to be tested by incoming data.

**Trigger criteria**: (1) A tracked narrative has a Confirmation Score below 50%, (2) an incoming data release or policy event within the next 7-14 days directly addresses one of the narrative's core claims, and (3) the expected data outcome has a materially different implied narrative implication than the narrative currently asserts.

**Alert contents**: Which narrative is at risk, which data release or event will test it, the narrative's current claim, the department's expected data outcome based on objective indicators, the market implication if data confirms the narrative (no change, continuity), the market implication if data contradicts the narrative (potential narrative collapse, repricing), and the estimated magnitude of gold price impact for each scenario.

**Update cadence**: Event-driven — issued 7-14 days before the relevant data release or event.

**Significance**: Narrative data gap alerts are the department's most directly actionable product for the Knowledge Department. They identify upcoming collisions between narrative and reality before the collision occurs — enabling the institution to position proactively for the resolution rather than reactively after the data release.

**Consumers**: Knowledge Department, Forecasting & Risk.

### 14.6 Narrative Collapse Warning

**Definition**: An urgent product issued when a tracked narrative is approaching or undergoing collapse.

**Trigger criteria**: (1) Narrative Decay Score exceeds 70, (2) a contradictory data release or policy event has occurred within the past 48 hours, or (3) a high-authority source has explicitly contradicted the narrative's core claim.

**Alert contents**: Collapsing narrative identification and current Decay Score, collapse trigger (if a trigger event has occurred, describe it; if pre-emptive, identify the most probable trigger), collapse velocity estimate (how quickly the narrative will unwind — hours, days, or weeks), positioning vulnerability estimate (how much capital is positioned around this narrative and how much is at risk of forced unwinding), successor narrative assessment (which narrative is most likely to replace the collapsing narrative), gold implication assessment (what does the collapse mean for gold — positive, negative, or neutral given gold's positioning and fundamental context?).

**Update cadence**: Event-driven — issued immediately when trigger criteria are met, with daily updates until the collapse stabilizes or the warning is withdrawn.

**Significance**: Narrative collapse warnings are the department's most time-sensitive product. Narrative collapse is the fastest price-relevant event in macro markets — asset prices can adjust within hours to days as the old story is abandoned. An early collapse warning, even by 24-48 hours, provides significant institutional advantage.

**Consumers**: Knowledge Department (as high-priority evidence), Forecasting & Risk.

### 14.7 Sell-Side Consensus Index

**Definition**: A weekly composite index tracking the evolution of sell-side analyst consensus on gold and macro conditions.

**Format**: Three component indices — Gold Analyst Consensus (buy/hold/sell ratio for gold-equity analysts, converted to a 0-100 consensus scale where 100 = all analysts rate gold a buy), Gold Target Consensus (dispersion of gold price targets — low dispersion = high agreement, high dispersion = active debate; expressed as a 0-100 dispersion scale), Macro House Consensus (share of major sell-side strategists with bullish/neutral/bearish gold views). Composite Sell-Side Consensus Score is the average of the three components. A Consensus-Confirmation comparison: compare sell-side consensus (as a lagging indicator) against the department's own narrative strength assessment to identify gaps.

**Update cadence**: Weekly.

**Significance**: Sell-side consensus is a useful contrarian indicator at extremes and a useful confirmation indicator during narrative adoption phases. The most valuable signal is a divergence between sell-side consensus and the department's own narrative strength assessment — if sell-side consensus is rising toward extreme bullish while the department's narrative strength is declining (late consensus phase), that divergence signals peak narrative risk.

**Consumers**: Knowledge Department (Evidence Repository), Capital Flow Intelligence.

### 14.8 Narrative Impact Decomposition

**Definition**: A monthly product that decomposes gold price movement into the portion attributable to narrative factors vs fundamental factors.

**Methodology**: Using a multi-factor framework, estimate the contribution of each tracked narrative (as measured by narrative strength score) to gold's monthly return, controlling for fundamental macro variables (real yields, DXY, inflation data) and positioning variables (COT, ETF flows). The residual (unexplained by fundamentals and positioning) is the pure narrative premium — the portion of gold's price that is being driven by narrative factors independent of the underlying data.

**Format**: Monthly decomposition chart showing: Actual Gold Return, Contribution from Fundamentals (real yields, DXY, CPI, PCE — the standard macro model), Contribution from Positioning (COT extreme, ETF flow momentum), Contribution from Narratives (aggregate narrative strength leading gold), Unexplained Residual. For each contributing narrative, display its estimated contribution in basis points.

**Update cadence**: Monthly.

**Significance**: Narrative Impact Decomposition provides the Knowledge Department with an objective measure of how much of gold's current price is "story" vs "substance." A gold price move that is predominantly narrative-driven is more vulnerable to reversal when the narrative inevitably shifts. A gold price move that is predominantly fundamental-driven has stronger support. The decomposition also tests the department's own thesis — if a narrative that the department rates as strong is not appearing in the decomposition's narrative contribution, the narrative may be present in the discourse but not yet market-relevant.

**Consumers**: Knowledge Department, Forecasting & Risk.

### 14.9 Cross-Department Narrative Coherence Score

**Definition**: A weekly composite score measuring how closely aligned the narrative assessments are across all Tier-1 Intelligence Departments.

**Methodology**: Compare the dominant narrative as assessed by each intelligence department — Central Bank Intelligence (policy narrative), Capital Flow Intelligence (positioning narrative), Cross-Asset Intelligence (price narrative), and Narrative Intelligence (discourse narrative). Score coherence on a 0-100 scale: 100 = all departments identify the same dominant narrative and it is consistent across all evidence types; 0 = each department identifies a different dominant narrative, implying a fractured market environment where policy, positioning, price, and discourse are telling different stories.

**Format**: Single numeric score (0-100) with per-department narrative comparison table. When coherence is below 40, include a "Narrative Fracture Analysis" section describing where the fractures are and what they imply for institutional conviction.

**Update cadence**: Weekly.

**Significance**: This is the department's integrative product — it fulfills the coordination function described in Section 4.10. A declining coherence score is the institution's earliest warning that the market environment is becoming fragmented across narrative dimensions. Low coherence periods historically precede significant macro volatility and trend changes. High coherence periods are associated with strong trending markets where conviction can be high.

**Consumers**: All Intelligence Departments, Knowledge Department.

### 14.10 Narrative Catalyst Calendar

**Definition**: A forward-looking calendar identifying upcoming data releases, policy events, and scheduled communications that are most likely to affect each tracked narrative.

**Format**: 4-week forward calendar with events color-coded by narrative relevance. For each event, show: event name and date, narratives affected (which tracked narratives' confirmation scores will be updated by this event), current narrative claim vs expected outcome (the gap the event will resolve), expected market impact if data confirms current narrative, expected market impact if data contradicts current narrative, and the department's probability-weighted expected narrative outcome.

**Update cadence**: Weekly, reviewed daily for updates and additions.

**Significance**: The Narrative Catalyst Calendar provides the Knowledge Department and Forecasting & Risk with a forward-looking map of the upcoming narrative risk events. It is the operational product that answers "what should we be watching this week?"

**Consumers**: Knowledge Department, Forecasting & Risk, All Intelligence Departments.

---

## 15. Coverage Tier Framework

The department operates a three-tier coverage framework to allocate analytical resources proportional to each narrative's current market impact, gold relevance, and lifecycle phase intensity.

| Tier | Narratives | Coverage Standard | Resource Allocation |
|------|-----------|-------------------|-------------------|
| Tier 1 — Maximum Depth | Inflation, Recession, Soft Landing, Hard Landing, Higher for Longer, De-Dollarization, Safe Haven, Risk-On/Risk-Off | Continuous narrative strength tracking; same-day alerts on frequency, authority, or lifecycle phase changes; weekly deep analysis reports; full conflict detection against all other Tier 1 and Tier 2 narratives; dedicated data-gap analysis and risk-calendar integration | 60% of departmental capacity |
| Tier 2 — High Depth | AI Investment Cycle, Energy Transition, Fiscal Expansion, Credit Tightening, Global Growth, Supply Chain Disruption, Commodity Supercycle | Daily narrative strength tracking; next-business-day alerts on significant changes; weekly summary reports; conflict detection against Tier 1 narratives; monthly deep analysis; data-gap analysis for narrative-specific catalysts | 25% of departmental capacity |
| Tier 3 — Standard Depth | Narrative-specific sub-narratives as identified (e.g., specific commodity supercycle sub-narratives, sectoral AI effects, regional growth divergence variants) | Weekly strength check; monthly summary; included in composite intelligence products (Narrative Regime Assessment, Narrative Impact Decomposition) but not independently reported; coverage elevated on event-driven basis when a sub-narrative becomes market-dominant | 15% of departmental capacity |

Tier assignments are reviewed monthly. A narrative may be temporarily elevated — for example, if the Credit Tightening narrative intensifies during a regional bank stress episode, it moves from Tier 2 to Tier 1 monitoring for the duration of the stress. A narrative in the Exhaustion lifecycle phase may be temporarily downgraded to free analytical capacity for emerging narratives in the Emergence phase.

The tier structure is designed around current market relevance, not intrinsic narrative importance. A narrative that is structurally significant (like de-dollarization) but currently in Persistence phase with stable, predictable dynamics receives Tier 1 coverage at standard depth rather than crisis monitoring. A narrative that is cyclically less important (like credit tightening) but currently experiencing a surge in frequency, authority, and market impact receives elevated coverage until the cycle passes.

---

*Narrative Intelligence — Department Charter*  
*AurumAI Institutional Architecture*
