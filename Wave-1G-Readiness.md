# Wave-1G Readiness — Minimum Institutional Capability Assessment

**Date**: 2026-07-26  
**Review type**: Institutional capability evaluation  
**Implemented objects**: PolicyBiasScore · ForwardGuidanceRecord · RatePathProjection  
**Not implemented**: LiquidityOutlook · BalanceSheetOutlook · PolicyDivergenceMatrix · HawkDoveScore · GlobalMonetaryRegime · CentralBankSurpriseIndex · PolicyPathAssessment

---

## 1. Can These Three Objects Be Combined Into a Single Institutional Policy Assessment?

**Yes.** The three implemented objects form a coherent policy assessment triad covering the three essential questions about any central bank's monetary policy stance:

| Question | Object | Output |
|---|---|---|
| **What do they think?** | `PolicyBiasScore` | Directional stance (tightening/easing/neutral) with conviction score (-5 to +5), confidence weight, and component breakdown |
| **What are they saying?** | `ForwardGuidanceRecord` | Canonical guidance text, guidance type (calendar/state-contingent/open/quantitative), language drift (delta from prior), and credibility score |
| **What will they do?** | `RatePathProjection` | Quantitative path over next 8 meetings, confidence interval width, and current policy rate baseline |

These are different representations of the same underlying assessment:

- PolicyBiasScore provides the **direction and magnitude** of the stance
- ForwardGuidanceRecord provides the **narrative justification and credibility**
- RatePathProjection provides the **quantitative expression** (expected rates)

Combined, they answer: *"Central bank X has a Y bias (score Z) with W% confidence, justified by guidance '...' (credibility: Q), projecting rates to reach R bps over N meetings (CI: ±C bps)."*

This is a complete policy assessment for any individual central bank. The objects share a common `central_bank` identifier and `cross_references` field, enabling explicit linking.

---

## 2. Is Any Essential Knowledge Still Missing Before a Coherent Assessment Can Exist?

**No.** The following unimplemented CBI objects serve distinct purposes that are **additive, not foundational**:

| Missing Object | Purpose | Relevance to Policy Assessment |
|---|---|---|
| `LiquidityOutlook` | G4 aggregate balance sheet trajectory, money market stress | **Orthogonal** — systemic liquidity conditions, not individual central bank policy stance |
| `BalanceSheetOutlook` | Single-CB balance sheet trajectory (QE/QT pace) | **Supplementary** — clarifies policy implementation tool, not stance direction |
| `HawkDoveScore` | Individual committee member leaning | **Granular** — feeds PolicyBiasScore but is not required to produce it |
| `PolicyDivergenceMatrix` | Cross-bank divergence measurement | **Comparative** — requires multiple PolicyBiasScores; the inputs exist, only the cross-product is missing |
| `GlobalMonetaryRegime` | Aggregate regime classification | **Synthetic** — derived from individual PolicyBiasScores; the inputs exist, only the aggregation is missing |
| `CentralBankSurpriseIndex` | Historical surprise track record | **Historical** — weights CBI evidence confidence, not required for current assessment |
| `PolicyPathAssessment` | Composite path with market comparison, scenarios | **Synthetic** — requires RatePathProjection + external market data + PolicyBiasScore scenario input |

The three implemented objects cover **primary data collection** (reading central bank communications, interpreting stance, projecting rates). The missing objects cover **secondary synthesis** (cross-bank comparisons, historical analysis, composite assessments) and **orthogonal domains** (liquidity, balance sheet).

---

## 3. Can the Department Produce a Stable Institutional View Without LiquidityOutlook and BalanceSheetOutlook?

**Yes.** LiquidityOutlook and BalanceSheetOutlook address a fundamentally different dimension of central bank intelligence:

| Dimension | Coverage | Implemented? |
|---|---|---|
| **Policy stance** | Direction, guidance, rate path | ✅ Full (3 objects) |
| **Liquidity conditions** | G4 balance sheets, money markets, reserves | ❌ LiquidityOutlook |
| **QE/QT trajectory** | Single-CB asset holdings, runoff pace | ❌ BalanceSheetOutlook |

These dimensions are independent:
- A central bank can have a clear tightening bias (PolicyBiasScore=+3) while liquidity simultaneously contracts (LiquidityOutlook=Contracting). The policy stance assessment is coherent without knowing whether liquidity is expanding or contracting.
- A central bank can issue forward guidance (ForwardGuidanceRecord) without simultaneously adjusting its balance sheet (BalanceSheetOutlook). The two are separate policy tools.

The policy triad (bias + guidance + path) provides a **stable institutional view of central bank intent**. Liquidity and balance sheet data provide **context about central bank implementation** — important for comprehensive intelligence but not required for a coherent policy assessment.

---

## 4. Is PolicyPathAssessment Derivable from the Three Implemented Objects?

**Partially.** PolicyPathAssessment (Section 1.10) requires:

| Required Field | Source | Available? |
|---|---|---|
| `base_case_path` (quarterly, 12-month) | RatePathProjection.base_path (8-meeting horizon) → extrapolated | ✅ Partially — shorter horizon, needs quarterly conversion |
| `hawkish_scenario.path` | Not in any implemented object | ❌ — requires scenario-aware projection logic |
| `hawkish_scenario.trigger_conditions` | ForwardGuidanceRecord.language_delta may contain trigger references | ⚠️ — inferable but not structured |
| `dovish_scenario.path` | Not in any implemented object | ❌ — requires scenario-aware projection logic |
| `dovish_scenario.trigger_conditions` | ForwardGuidanceRecord.language_delta | ⚠️ — inferable but not structured |
| `market_implied_path_delta` | External market data (OTS, Fed Funds futures) | ❌ — requires market data ingestion |
| `scenario_analysis` (optional) | RatePathProjection.scenario_analysis | ✅ — structured scenario field exists on all CBI contracts |

**Verdict**: The three implemented objects provide **the CBI-side inputs** for PolicyPathAssessment (base rate path, policy bias direction for scenario probabilities, guidance text for trigger conditions) but PolicyPathAssessment also requires **market data** (market-implied rates) and **business logic** (scenario projection, quarterly conversion, delta computation). PolicyPathAssessment is a **synthetic product** that depends on these three objects plus external data — not derivable from CBI objects alone, but the CBI contribution is complete.

---

## 5. If Activated Today, Would the Department Provide Meaningful Evidence to AurumAI?

**Yes.** The evidence produced by these three objects enters the existing pipeline through the verified `CbiEvidenceAdapter` → `EvidenceAggregator.merge()` path (verified in Waves 1B, 1D) and provides:

### What AurumAI would receive:

| Evidence Type | Directional Signal | Confidence | Temporal | Cross-References |
|---|---|---|---|---|
| `CBI_POLICY` | bearish/bullish/neutral | 0.0–1.0 | valid_from → valid_until | To CAI, CFI objects |
| `CBI_GUIDANCE` | neutral | 0.0–1.0 | valid_from → valid_until | To PolicyBiasScore |
| `CBI_RATE_PATH` | neutral | 0.0–1.0 | valid_from → next meeting | To ForwardGuidanceRecord |

### How it integrates:

1. **EvidenceWeighter** — CBI evidence participates in the 5-factor weight model. CBI evidence carries `Provenance` (unlike Economic/Temporal evidence), receiving the provenance bonus factor.

2. **ReasoningEngine** — CBI evidence with `event_type="CBI_POLICY"` provides directional bias (bearish/bullish) that influences majority-bias calculations across the merged evidence collection. No other evidence source in the current pipeline provides central bank directional signals.

3. **DecisionEngine** — CBI evidence increments `evidence_count` (reducing `INSUFFICIENT_EVIDENCE` risk) and contributes its confidence to `overall_confidence`. The `CBI_POLICY` bias influences the conclusion's directional classification.

4. **InstitutionalAssessment** — CBI attribution appears in `WeightedAggregate.attribution` alongside CPI, TEMPORAL, ECONOMIC, CAUSAL. CBI evidence is tracked in `OrchestrationReport.layer_counts["cbi"]`.

### What makes activation meaningful now:

- **Directional gap filled**: The existing pipeline has Economic evidence (neutral bias), Temporal evidence (neutral bias), Causal evidence (neutral bias), and Core evidence (bias from historical returns). CBI_POLICY is the **only source providing forward-looking directional policy bias** from institutional analysis rather than historical statistics.

- **Confidence fidelity**: CBI confidence represents analyst conviction about policy stance interpretation — a fundamentally different signal from historical return-based confidence. The two are complementary.

- **Temporal precision**: CBI evidence carries `valid_until` — automatic expiry at the next policy meeting. This enables time-aware evidence weighting that no other source currently provides (Economic/Temporal evidence have no validity semantics).

- **Provenance chain**: CBI evidence carries full provenance (analyst identity, version, timestamp), enabling audit, lineage tracing, and recency weighting. Economic and Temporal evidence do not carry provenance.

---

## Minimum Institutional Capability Conclusion

The three implemented objects satisfy the core CBI mission defined in the department charter:

> *"Central Bank Intelligence produces assessments of central bank policy stance, forward guidance, and rate trajectory for the nine covered central banks."*

The policy triad covers:
- **Stance assessment** (What do they think?) — PolicyBiasScore
- **Guidance interpretation** (What are they saying?) — ForwardGuidanceRecord
- **Rate trajectory** (What will they do?) — RatePathProjection

All three are verified through the complete lifecycle (contract → repository → adapter → aggregator → reasoning → decision). The adapter integration is verified, the aggregator merge is verified, the evidence fields are populated correctly, and confidence/provenance/validity are preserved unchanged through the pipeline.

The unimplemented objects (LiquidityOutlook, BalanceSheetOutlook, GlobalMonetaryRegime, HawkDoveScore, CentralBankSurpriseIndex, PolicyDivergenceMatrix, PolicyPathAssessment) are either orthogonal dimensions or synthetic products derived from the core triad. They expand departmental capability but are not prerequisites for it.

The only remaining infrastructure item is the `_run_cbi()` wiring in `OrchestrationEngine` (identified in Wave-1D) — a 17-line method following the `_run_economic()` pattern.

---

## READY FOR ACTIVATION

**Justification**: The three implemented knowledge objects (PolicyBiasScore, ForwardGuidanceRecord, RatePathProjection) form a complete policy assessment triad covering stance direction, narrative justification, and quantitative rate trajectory for any individual central bank. All three are verified through the complete lifecycle: frozen contract → deterministic repository persistence → pure adapter translation → EvidenceAggregator merge → EvidenceWeighter participation → ReasoningChain inclusion → Decision influence. The evidence they produce (CBI_POLICY, CBI_GUIDANCE, CBI_RATE_PATH) fills a gap no existing evidence source covers — forward-looking institutional directional bias with provenance, temporal validity, and confidence fidelity. The unimplemented objects are supplementary (liquidity, balance sheet, cross-bank analysis) or synthetic (regime classification, composite path assessment) — they expand departmental scope but are not prerequisites for meaningful institutional intelligence output.
