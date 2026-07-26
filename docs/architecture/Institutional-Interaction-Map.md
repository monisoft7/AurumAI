# Institutional Interaction Map — Architecture Checkpoint 001

**Checkpoint Classification**: Architecture Verification  
**Date**: 2026-07-26  
**Scope**: Central Bank Intelligence, Cross-Asset Intelligence, Capital Flow Intelligence, Narrative Intelligence  
**Objective**: Verify that the four Tier-1 intelligence departments can operate together as one coherent institutional research organization

---

## 1. Department Profiles

### 1.1 Central Bank Intelligence (CBI)

**Inputs**: Policy statements, meeting minutes, speeches, press conferences, dot plots, voting records, staff economic projections, balance sheet data — from 9 central banks (Fed, ECB, BOJ, BOE, PBOC, SNB, RBA, RBNZ, BOC).  

**Upstream providers**: External Data Connectors (schedules, raw feeds), Natural Language Processing (sentiment scores), News Intelligence (central bank-related articles).  

**Outputs**: Policy Bias Score, Policy Path Assessment, Forward Guidance Tracker, Liquidity Outlook, Rate Path Projection, Balance Sheet Outlook, Policy Divergence Matrix, Hawk/Dove Scorecard, Global Monetary Regime Assessment, Central Bank Surprise Index.  

**Downstream consumers** (as documented): Knowledge Department, Forecasting & Risk, NLP (coordination), Simulation.  

**Intelligence type**: Fundamental policy intelligence — what central banks are doing and why.

### 1.2 Cross-Asset Intelligence (CAI)

**Inputs**: Continuous price feeds across gold, DXY, Treasury yields, real yields, equities, FX pairs, commodities, volatility indices.  

**Upstream providers**: External Data Connectors (price feeds), Central Bank Intelligence (policy context), Natural Language Processing (sentiment), News Intelligence (event flow).  

**Outputs**: Cross Asset Strength Matrix, Correlation Stability Index, Divergence Alerts, Liquidity Rotation Map, Safe Haven Rotation Index, Inflation Transmission Report, Yield Transmission Report, Dollar Pressure Index, Cross Asset Regime Assessment, Institutional Confirmation Matrix.  

**Downstream consumers** (as documented): Knowledge Department, Forecasting & Risk, Central Bank Intelligence (coordination), Simulation.  

**Intelligence type**: Relational market intelligence — how assets behave relative to one another.

### 1.3 Capital Flow Intelligence (CFI)

**Inputs**: ETF flow data, CFTC COT reports, options positioning, TIC data, central bank reserve data, fund flow data, SWF/pension disclosures, 13F filings, dealer positioning data.  

**Upstream providers**: External Data Connectors (data feeds), Central Bank Intelligence (policy context for official flows), Cross-Asset Intelligence (correlation and regime context), Natural Language Processing (institutional communication sentiment), News Intelligence (event flow).  

**Outputs**: Gold Positioning Dashboard, COT Positioning Report, ETF Flow Monitor, Central Bank Reserve Flow Report, Market Structure and Gamma Profile, Safe-Haven Flow Index, De-Dollarization Flow Index, Speculative Flow Asymmetry Assessment, Institutional Accumulation Signal, Liquidity Migration Map.  

**Downstream consumers** (as documented): Knowledge Department, Forecasting & Risk, Central Bank Intelligence (coordination), Cross-Asset Intelligence (coordination), Simulation.  

**Intelligence type**: Flow and positioning intelligence — where capital has gone, who sent it, and how extreme it is.

### 1.4 Narrative Intelligence (NI)

**Inputs**: Financial news wires, sell-side research, central bank communications, earnings call transcripts, think tank publications, policy documents, conference transcripts.  

**Upstream providers**: Natural Language Processing (sentiment, topic, entity extraction), News Intelligence (curated news), External Data Connectors (text data feeds), Central Bank Intelligence (policy narrative layer), Cross-Asset Intelligence (market-derived narrative validation), Capital Flow Intelligence (positioning validation layer).  

**Outputs**: Narrative Strength Dashboard, Narrative Conflict Matrix, Narrative Positioning Gap Report, Narrative Regime Assessment, Narrative Data Gap Alert, Narrative Collapse Warning, Sell-Side Consensus Index, Narrative Impact Decomposition, Cross-Department Narrative Coherence Score, Narrative Catalyst Calendar.  

**Downstream consumers** (as documented): Knowledge Department, Forecasting & Risk, Central Bank Intelligence (coordination), Cross-Asset Intelligence (coordination), Capital Flow Intelligence (coordination), Simulation.  

**Intelligence type**: Discourse intelligence — what the market is saying, which stories are winning, and how much life they have left.

---

## 2. Dependency Graph

```
FUNDAMENTAL LAYER
  Central Bank Intelligence
  → produces: policy bias, rate paths, liquidity outlook, forward guidance, balance sheet outlook
  → consumed by: Knowledge, Forecasting & Risk, Cross-Asset Intelligence, Capital Flow Intelligence, Narrative Intelligence, Simulation
  → contributes to: fundamental context for all cross-asset, flow, and narrative analysis

RELATIONAL LAYER
  Cross-Asset Intelligence
  → produces: correlation regime, divergence alerts, rotation map, safe-haven ranking, confirmation matrix
  → consumed by: Knowledge, Forecasting & Risk, Central Bank Intelligence (co-validation), Capital Flow Intelligence, Narrative Intelligence, Simulation
  → contributes to: market-derived validation layer for flow and narrative interpretation

FLOW LAYER
  Capital Flow Intelligence
  → produces: gold positioning, COT extremes, ETF momentum, central bank reserve flows, gamma profile, de-dollarization index, liquidity migration
  → consumed by: Knowledge, Forecasting & Risk, Central Bank Intelligence (co-validation), Cross-Asset Intelligence (co-validation), Narrative Intelligence, Simulation
  → contributes to: positioning validation layer for narrative lifecycle assessment

DISCOURSE LAYER
  Narrative Intelligence
  → produces: narrative strength, conflict matrix, positioning gap, regime assessment, collapse warnings, coherence score, catalyst calendar
  → consumed by: Knowledge, Forecasting & Risk, Central Bank Intelligence (co-validation), Cross-Asset Intelligence (co-validation), Capital Flow Intelligence (co-validation), Simulation
  → contributes to: conviction calibration and data-gap identification for all departments
```

### Graphical Flow

```
External Data Connectors  ─┬─→  CBI  ──→  Knowledge Department
                           ├─→  CAI  ─┤           ↑
                           ├─→  CFI  ─┤           │
                           └─→  NI   ─┤           │
                                      │           │
Natural Language Processing ─┬─→  CBI ─┤           │
                             ├─→  CAI ─┤           │
                             ├─→  CFI ─┤           │
                             └─→  NI  ─┤           │
                                      │           │
News Intelligence ────────────┬─→  CBI │           │
                             ├─→  CAI │           │
                             ├─→  CFI │           │
                             └─→  NI  │           │
                                      │           │
           ┌──────────────────────────┘           │
           ▼                                      │
    ┌──────────────┐     ┌──────────────┐         │
    │      CBI     │────→│     CAI      │         │
    └──────────────┘     └──────┬───────┘         │
           │                    │                 │
           │                    ▼                 │
           │            ┌──────────────┐         │
           ├───────────→│     CFI      │         │
           │            └──────┬───────┘         │
           │                    │                 │
           │                    ▼                 │
           │            ┌──────────────┐         │
           ├───────────→│      NI      │         │
           │            └──────┬───────┘         │
           │                    │                 │
           │                    ▼                 │
           │           [[Knowledge Department]]   │
           │                    ↑                 │
           └────────────────────┘                 │
                                                  │
     Forecasting & Risk ←── CBI, CAI, CFI, NI ──┘
     Simulation          ←── CBI, CAI, CFI, NI
```

The dependency graph is a directed acyclic graph (DAG). No circular dependencies exist. The intelligence flow is strictly hierarchical: fundamental policy (CBI) → relational market structure (CAI) → flow and positioning confirmation (CFI) → narrative discourse integration (NI). Each layer consumes from all prior layers and adds its distinct analytical value.

---

## 3. Analysis Findings

### 3.1 Duplicated Responsibilities

**Finding: No genuine duplication exists. Three areas of intentional multi-department coverage are designed correctly.**

| Phenomenon | CBI Lens | CAI Lens | CFI Lens | NI Lens | Verdict |
|-----------|----------|----------|----------|---------|---------|
| Safe-haven dynamics | Not covered | Safe Haven Rotation Index — price performance ranking | Safe-Haven Flow Index — flow destination and composition | Safe Haven Narrative — discourse lifecycle | Three independent perspectives on the same phenomenon. When they align, conviction is high. When they diverge, the divergence is itself intelligence. **Not duplication — intentional layered analysis.** |
| De-dollarization | Reserve diversification analysis within central bank coverage | Not covered | De-Dollarization Flow Index — quantitative flow measurement | De-Dollarization Narrative — discourse tracking | Two independent perspectives (CBI context + CFI measurement, NI overlays both). CBI provides the policy explanation for the flow data CFI measures. **Not duplication — complementary causal and measurement layers.** |
| Liquidity cycle | Liquidity Outlook — central bank policy-driven liquidity | Liquidity Rotation Map — capital rotation via price action | Liquidity Migration Map — capital migration via flow data | Liquidity narrative tracking within multiple themes | Three perspectives from policy (CBI), market (CAI), and flow (CFI). NI tracks the discourse about liquidity. **Not duplication — three distinct analytical lenses on the same macro driver.** |

### 3.2 Ownership Conflicts

**Finding: No ownership conflicts exist. The "Decisions This Department Never Owns" sections are mutually consistent across all four departments.**

Every department explicitly defers to the same owning departments for:
- Position sizing / risk allocation → Forecasting & Risk
- Trade execution → Execution
- Final directional macro view → Knowledge (Decision Engine)
- Asset selection / portfolio construction → Forecasting & Risk
- Risk limit setting and enforcement → Forecasting & Risk
- Data source procurement → External Data Connectors
- Sentiment model training → Natural Language Processing
- Regime classification thresholds → Knowledge (Regime Detection)
- Price target determination → Forecasting & Risk

Each department also explicitly disclaims ownership of the other three departments' core domains:
- CAI disclaims → central bank policy bias assessment (CBI)
- CFI disclaims → central bank policy bias assessment (CBI), cross-asset relationship classification (CAI)
- NI disclaims → central bank policy bias assessment (CBI), cross-asset relationship classification (CAI), flow source classification (CFI)

The ownership boundaries form a clean partition with no gaps or overlaps.

### 3.3 Circular Dependencies

**Finding: No circular dependencies exist. The dependency graph is a directed acyclic graph.**

The flow of hierarchical intelligence is:
```
CBI → CAI:   policy context enables cross-asset interpretation
CBI → CFI:   policy context enables official-sector flow interpretation
CBI → NI:    central bank communications are a primary narrative source
  
CAI → CFI:   correlation regime supplies context for flow interpretation
CAI → NI:    cross-asset regime validates or contradicts narratives

CFI → NI:    positioning data validates whether narratives are acted upon
```

No department depends on a downstream department for its core analytical function. The "coordination relationships" described in Section 7 of each charter represent feedback and co-validation, not structural dependencies — none of the four departments would fail to function if the feedback loop were severed, though institutional intelligence quality would be lower.

### 3.4 Missing Information Flows

**Finding: The actual information flows are correctly designed, but the upstream departments' consumer listings are incomplete in three places.**

| Missing Consumer | Document | Should List |
|-----------------|----------|-------------|
| Cross-Asset Intelligence | CBI Section 7 | CAI is a downstream consumer of CBI's policy context, liquidity outlook, and policy divergence matrix |
| Capital Flow Intelligence | CBI Section 7 | CFI is a downstream consumer of CBI's policy context for official-sector flow interpretation |
| Narrative Intelligence | CBI Section 7 | NI is a downstream consumer of CBI's policy bias scores and forward guidance interpretation |
| Capital Flow Intelligence | CAI Section 7 | CFI is a downstream consumer of CAI's correlation regime, safe-haven hierarchy, and rotation signals |
| Narrative Intelligence | CAI Section 7 | NI is a downstream consumer of CAI's cross-asset regime assessment and correlation stability index |
| Narrative Intelligence | CFI Section 7 | NI is a downstream consumer of CFI's COT extremes, ETF flow momentum, and asymmetry assessment |

**Impact assessment**: These are documentation gaps in the producing departments' charters, not design flaws. The consuming departments correctly identify their upstream providers in Sections 8. The intelligence flows are operational. The fix is to add the missing consumers to each department's Section 7 listing.

**Risk**: Low. No intelligence flow is actually missing — each consuming department correctly identifies where its inputs come from. The documentation asymmetry creates a minor risk that someone reading only one department's charter might underestimate its reach, but this does not affect institutional operation.

### 3.5 Opportunities for Evidence Sharing

**Finding: Three evidence sharing opportunities exist that would increase institutional intelligence without creating duplication.**

**Opportunity 1 — Safe-Haven Integrated Product**: CAI (Safe Haven Rotation Index — price), CFI (Safe-Haven Flow Index — flow), and NI (Safe Haven Narrative — discourse) each produce a safe-haven product independently. These three products reach the Knowledge Department as separate evidence classes. The departments could jointly produce a Safe-Haven Composite Assessment that integrates all three dimensions into a single read — reducing cognitive load on the Knowledge Department while preserving the independent analytical perspectives that make the three products individually valuable.

**Opportunity 2 — Liquidity Cycle Cross-Reference**: CBI (central bank balance sheet liquidity), CAI (price-based rotation), and CFI (flow-based migration) each maintain a liquidity assessment. Currently these are not cross-referenced in any standing product. A quarterly Liquidity Cycle Reconciliation meeting or cross-reference note would ensure the three perspectives are consistent — and if they are not, the divergence is itself an intelligence signal.

**Opportunity 3 — Gold Positioning Composite**: CFI's Gold Positioning Dashboard (Product 14.1) currently integrates multiple positioning data sources. It could optionally incorporate CAI's cross-asset confirmation score and NI's narrative lifecycle phase as overlay layers, producing a more comprehensive composite without requiring a new product. The current arrangement (separate products from CFI, CAI, NI that the Knowledge Department reconciles) is functionally correct but adds reconciliation overhead.

### 3.6 Opportunities for Common Institutional Products

**Finding: Three product consolidation opportunities exist. None are required for coherence, but all would improve institutional efficiency.**

**Opportunity 1 — Weekly Institutional Intelligence Brief**: All four departments produce a weekly intelligence brief (CBI Section 10, CAI Section 10, CFI Section 10, NI Section 10). These are currently four separate documents. A single Weekly Institutional Intelligence Brief with departmental sections would provide the Knowledge Department with a unified weekly view, reduce formatting redundancy, and ensure all four departments' weekly assessments reach consumers together.

**Opportunity 2 — Monthly Institutional Intelligence Review**: All four departments produce comprehensive monthly assessments (CBI Section 11, CAI Section 11, CFI Section 11, NI Section 11). These could be coordinated around a shared monthly calendar and issued as a coherent Monthly Institutional Intelligence Review package, with cross-references between departmental sections indicated.

**Opportunity 3 — Shared Institutional Catalyst Calendar**: NI's Narrative Catalyst Calendar (Product 14.10) is a forward-looking calendar of upcoming events affecting narratives. However, CBI, CAI, and CFI each also track upcoming events relevant to their domains (CBI: central bank meeting calendar; CAI: data releases affecting correlation structure; CFI: flow data release calendar). A shared institutional catalyst calendar that NI maintains but all departments contribute to would reduce calendar maintenance duplication.

### 3.7 Work Belonging Elsewhere

**Finding: No department owns work that structurally belongs to another department.**

Each department's core analytical domain is clearly bounded:
- CBI: central bank communications and policy analysis only
- CAI: cross-asset price relationships and correlation structure only
- CFI: flow and positioning data only
- NI: market discourse, narrative lifecycle, and thematic analysis only

The multi-department coverage of safe-haven, liquidity, and de-dollarization (noted in 3.1) is not ownership overlap — it is layered analysis of the same phenomenon from different data domains. Each department analyzes these phenomena using its own data sources (price, flow, policy, discourse), producing independent perspectives that together are more valuable than any single perspective.

The only finding approaching a concern is that CBI's reserve diversification analysis and CFI's Central Bank Reserve Flow Report cover adjacent territory. CBI provides the policy motivation for central bank reserve decisions (why the PBOC is buying gold). CFI measures the actual reserve flow data (how much the PBOC bought). These are complementary analytical roles. The boundary is clean: CBI owns the policy interpretation; CFI owns the flow measurement and extreme detection. No overlap.

---

## 4. Coordination Relationship Verification

Each department documents coordination relationships in its Downstream Consumers section. The following table verifies that all documented relationships are mutual (present in both departments' charters) or asymmetrical (present in only one but correctly designed as a one-way flow).

| Relationship | In CBI | In CAI | In CFI | In NI | Status |
|-------------|--------|--------|--------|-------|--------|
| CBI ↔ CAI (policy context for cross-asset) | Not listed as consumer of CAI | CAI 7.3: co-validation with CBI | N/A | N/A | **Asymmetrical.** CAI documents receiving from CBI and providing feedback. CBI does not list CAI as upstream or downstream. CBI provides policy context to CAI; CAI's feedback is informal co-validation. No structural dependency. Acceptable. |
| CBI ↔ CFI (policy context for official flows) | Not listed as consumer of CFI | N/A | CFI 7.3: co-validation with CBI | N/A | **Asymmetrical.** Same pattern as above. CFI receives CBI's policy context as a formal upstream input and describes co-validation as a coordination relationship. CBI does not list CFI. Acceptable. |
| CBI ↔ NI (policy narrative layer for discourse) | Not listed as consumer of NI | N/A | N/A | NI 7.3: co-validation with CBI | **Asymmetrical.** Same pattern. NI receives CBI policy narratives as a formal upstream input. CBI does not list NI. Acceptable. |
| CAI ↔ CFI (cross-asset context for flow) | N/A | Not listed as consumer of CFI | CFI 7.4: co-validation with CAI | N/A | **Asymmetrical.** CFI receives CAI's correlation and regime context as a formal upstream input. CAI does not list CFI. Acceptable. |
| CAI ↔ NI (cross-asset for narrative validation) | N/A | Not listed as consumer of NI | N/A | NI 7.4: co-validation with CAI | **Asymmetrical.** NI receives CAI's regime assessment as a formal upstream input. CAI does not list NI. Acceptable. |
| CFI ↔ NI (positioning for narrative validation) | N/A | N/A | Not listed as consumer of NI | NI 7.5: co-validation with CFI | **Asymmetrical.** NI receives CFI's positioning data as a formal upstream input. CFI does not list NI. Acceptable. |

**Summary**: All coordination relationships follow a consistent pattern — the consuming department (CAI, CFI, or NI) correctly identifies its upstream provider and describes a co-validation feedback loop. The upstream provider's charter does not always list the consuming department as a downstream consumer. This is a documentation asymmetry, not a design flaw, because the intelligence flows are unidirectional (upstream → downstream) and the feedback loops are informal coordination, not structural dependencies.

---

## 5. Institutional Coherence Assessment

### 5.1 Coverage Completeness

The four departments together cover the complete set of intelligence domains required for world-class macro decision-making:

| Intelligence Domain | Primary Department | Supporting Departments |
|--------------------|-------------------|----------------------|
| What central banks are doing and why | CBI | NI (narrative layer) |
| How assets relate to each other | CAI | CBI (policy context), CFI (positioning context) |
| Where capital has gone and who sent it | CFI | CBI (policy context), CAI (regime context) |
| What the market is saying and believing | NI | CBI, CAI, CFI (validation) |

No intelligence domain is uncovered. The four layers (fundamental, relational, flow, discourse) form a complete stack that transforms raw data into structured institutional intelligence.

### 5.2 Data Domain Separation

Each department analyzes a distinct data domain:

| Department | Primary Data Domain | Analytical Method |
|------------|-------------------|------------------|
| CBI | Central bank communications (text + policy data) | Fundamental interpretation, document comparison |
| CAI | Market prices (time series) | Statistical correlation, relative strength, lead/lag |
| CFI | Flow and positioning data (tabular + regulatory filings) | Extreme detection, momentum, compositional analysis |
| NI | Market discourse (text) | Frequency analysis, lifecycle tracking, conflict detection |

The data domains do not overlap. Multi-department coverage of safe-haven, liquidity, and de-dollarization (identified in 3.1) uses different data within each department's domain. No two departments analyze the same raw data.

### 5.3 Consumer Consistency

All four departments identify the same primary consumers:
- Knowledge Department — primary consumer for all four (evidence, reasoning, conviction calibration)
- Forecasting & Risk — secondary consumer for all four (model inputs, confidence calibration, risk assessment)
- Simulation & Validation — tertiary consumer for all four (historical context for backtesting)

This consistency confirms that the four departments are designed as intelligence producers feeding the same downstream decision infrastructure.

### 5.4 Temporal Coverage

The four departments together provide intelligence across all relevant time horizons:

| Horizon | Leading Department | Supporting |
|---------|-------------------|------------|
| Intraday to 1 week | NI (narrative collapse, catalyst calendar), CFI (flow momentum) | CAI (divergence alerts) |
| 1 week to 1 month | CFI (positioning extremes, ETF momentum), CAI (correlation stability) | NI (narrative positioning gap) |
| 1 month to 3 months | CAI (regime assessment), NI (transition detection) | CBI (rate path), CFI (structural demand) |
| 3 months to 12 months | CBI (policy path assessment, balance sheet outlook) | CFI (structural demand shift), NI (narrative persistence) |
| Structural (1+ years) | CBI (de-dollarization, global liquidity), CFI (reserve flows) | NI (structural narrative tracking) |

No temporal gap exists.

---

## 6. Architecture Checkpoint Conclusion

### 6.1 Issues Requiring Action

| Issue | Severity | Action Required |
|-------|----------|----------------|
| CBI Section 7 (Downstream Consumers) does not list CAI, CFI, or NI | Low — documentation gap | Add missing consumers to CBI Section 7 |
| CAI Section 7 (Downstream Consumers) does not list CFI or NI | Low — documentation gap | Add missing consumers to CAI Section 7 |
| CFI Section 7 (Downstream Consumers) does not list NI | Low — documentation gap | Add missing consumer to CFI Section 7 |

### 6.2 Issues Not Requiring Action

| Issue | Reasoning |
|-------|-----------|
| Multi-department coverage of safe-haven, liquidity, and de-dollarization | Intentional layered analysis using different data domains within each department's charter |
| Coordination relationships asymmetrically documented | Feedback loops are informal co-validation, not structural dependencies. The consuming departments correctly identify their upstream providers. |
| Product naming similarity (Liquidity Outlook, Liquidity Rotation Map, Liquidity Migration Map) | Products are differentiated by data domain (CBI: policy, CAI: price, CFI: flow). Consumers familiar with each department's role will not confuse them. |

### 6.3 Optional Improvements

| Improvement | Expected Benefit |
|-------------|-----------------|
| Joint Safe-Haven Composite Assessment | Reduces Knowledge Department reconciliation overhead |
| Single Weekly Institutional Intelligence Brief | Ensures all four weekly assessments reach consumers together |
| Shared Institutional Catalyst Calendar | Eliminates calendar maintenance duplication across four departments |
| Quarterly Liquidity Cycle Reconciliation | Ensures three independent liquidity assessments remain consistent |

### 6.4 Final Verdict

**The four departments are architecturally coherent and ready to become permanent Tier-1 departments.**

No duplicated responsibilities exist — the three areas of multi-department coverage (safe-haven, liquidity, de-dollarization) are intentional layered analysis from distinct data domains.

No ownership conflicts exist — the "Decisions This Department Never Owns" sections form a consistent, mutually-reinforcing partition of institutional responsibilities.

No circular dependencies exist — the dependency graph (CBI → CAI → CFI → NI) is a strict directed acyclic graph with no cycles.

No department owns work that belongs elsewhere — each department's analytical domain is clearly bounded and uses distinct data sources.

The three documentation gaps identified in 6.1 are minor consumer-listing omissions in the producing departments' charters. They do not affect operational intelligence flow, as each consuming department correctly identifies its upstream providers. The recommendation is to correct these listings at the next charter update cycle. The optional improvements in 6.3 would increase institutional efficiency but are not required for architectural coherence.

The four departments together form a complete intelligence organization covering fundamental policy analysis (CBI), relational market structure (CAI), flow and positioning confirmation (CFI), and narrative discourse integration (NI) — delivering intelligence across all relevant time horizons from intraday to structural years, feeding a consistent set of downstream consumers through clearly bounded ownership domains.

---

*Institutional Interaction Map — Architecture Checkpoint 001*  
*AurumAI Institutional Architecture*
