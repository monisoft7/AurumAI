# FINAL_ARCHITECTURE_GATE_001

**Subject:** Final architecture gate for leaving correction mode and entering operational validation.  
**Scope:** Read-only architecture verification, except creation of this requested audit artifact. No source, tests, configuration, documentation other than this file, or runtime artifacts were modified. No runtime was executed.  
**Date:** 2026-08-08  
**Decision:** **A) READY FOR OPERATIONAL VALIDATION**

---

## 1. Final Decision Authority

Verified production path:

`run.py -> InstitutionalOrchestrator.with_default_pipeline() -> run_all() -> institutional pipeline -> decision_engine -> finalize`

`run.py` constructs `InstitutionalOrchestrator.with_default_pipeline(...)` and executes `orch.run_all(...)`. The default DAG registers the institutional W-chain ending in `decision_engine`, and `finalize` depends on `decision_engine` plus forecast/risk side branches.

The primary institutional decision authority is `src/decision_engine/engine.py::DecisionEngine.decide()`. `finalize` emits `results["decision_engine"]` when present and falls back to the legacy decision only if the institutional decision is absent or errored.

Genuine competing/side authorities:

- `legacy_decision` from `build_legacy_pipeline`: present in `finalize`, but not authoritative when `decision_engine` succeeds.
- `risk_decision` from `risk_gate`: present in `finalize`, but not consumed by `DecisionEngine` and not an execution authority in the current institutional intelligence path.
- `bias_prevention.apply_bias_review`: a genuine institutional override only for directional decisions requiring human review; it is part of the W13 decision emission path, not an independent competing decision engine.
- `trade_recommendation`: downstream translation of the institutional decision, not a competing authority.

Conclusion: one primary institutional decision authority exists.

---

## 2. Data Flow Integrity

Verified connected production flow:

`Raw/pre-market data -> SignalAssessment -> EvidenceCollection -> EvidenceReasoning -> CounterEvidence -> ThesisConstruction/Update -> ConfidenceEngine -> ScenarioGeneration -> RiskRewardValidation -> DecisionEngine -> Finalize`

The default DAG wires each stage through explicit dependencies. The current stage functions deserialize upstream outputs into their stage contracts before invoking the next component, so the chain is not merely documentary.

Latest audited runtime facts from `runtime_20260808_195528` remain consistent with this flow:

- `pre_market_scan`: INFLATIONARY regime, confidence 0.6; ETF flow +2.26%, momentum accumulating; OI first observation `open_interest_change_pct=0.0`.
- `evidence_collection`: 4 evidence items from 11 classified observations; XAU/USD and Gold Positioning are Weak Signal, DXY and anomaly are Watch.
- `evidence_reasoning`: three evidence sets, including new `ETF_FLOW`.
- `counter_evidence`: conflict severity 0.1667, confidence penalty 0.2667, missing evidence only `CB_GOLD`.
- `confidence_engine`: final confidence 0.2494.
- `scenario_generation`: scenario confidence source is `thesis_support`, value 0.3972.
- `risk_reward_validation`: base scenario acceptable, ratio 0.9682.
- `decision_engine`: NO_TRADE from confidence 0.2494 below the 0.50 decision gate.

No material dead branch or synthetic/fallback value was found masquerading as institutional evidence in the authoritative decision path. Some heuristic/proxy values remain, but they are visible as formulas, labels, or fallback behavior and do not currently invalidate institutional analytical results.

---

## 3. Knowledge Flow

Verified structural production path:

`Knowledge Records -> Knowledge Graph -> EvidenceCollection`

`_build_legacy_pipeline` returns `knowledge_graph` from the legacy inference pipeline. `_evidence_collection` retrieves `results["build_legacy_pipeline"]["knowledge_graph"]`, constructs `EvidenceCollector(knowledge_graph=kg)`, and `EvidenceCollector._query_knowledge_records()` calls `KnowledgeGraph.filter_nodes(...)` before falling back to synthetic KR IDs.

Therefore the KG integration is structurally reachable in production. The latest runtime still used synthetic KR IDs for the specific evidence items observed, which means no matching KG node was selected for those current event types; that is not a wiring defect. The production path is live, and fallback IDs are only provenance/source identifiers, not computational evidence weights.

---

## 4. W2 Regime Flow

Verified flow:

`RegimeDiagnosis -> PreMarket -> SignalAssessment -> EvidenceCollection`

`regime_diagnosis` runs after `build_legacy_pipeline` and before `pre_market_scan`. `_pre_market_scan` reads the diagnosis regime and confidence, then passes them into `PreMarketBriefingAssembler`. `_signal_assessment` constructs the assembler with the briefing regime, and then replaces the assessment regime/confidence from `regime_diagnosis` when available. `_evidence_collection` derives `regime_weight` from `diagnosis["confidence"]`.

In `runtime_20260808_195528`, `RegimeDiagnosis.confidence=0.6`, and Evidence items carry `regime_weight=0.6`, proving the weighting derives from W2 output rather than a stale constant.

---

## 5. SignalAssessment Corrections

The three recent SignalAssessment corrections remain isolated:

- `volume_flow`: gold-class overnight instruments now pass ETF/OI positioning fields into `VolumeFlowConfirmator`; this changes criterion input wiring only.
- real OI producer: `PositioningDataFetcher._fetch_open_interest()` uses yfinance `openInterest`, persists the observed level, and returns first-observation `0.0` change without substituting traded volume.
- anomaly identity: anomaly observation IDs include a slugged description, separating different template violations on the same instrument/type.

No classifier scoring constants, DecisionEngine thresholds, or W13 behavior were altered by these corrections.

---

## 6. CounterEvidence

Current penalty is justified by actual evidence:

- `conflict_severity=0.1667` reflects a real cross-set contradiction.
- `regime_conflict` reflects bearish USD_FX evidence opposing the INFLATIONARY expected bias.
- `missing_evidence=CB_GOLD` reflects a genuinely unavailable channel under current producers.

The previous duplicate-charge issue is materially reduced: `compute_confidence_penalty()` now charges only `conflict_severity * 0.4`, plus `0.1` for `regime_conflict`, plus `0.1` for `missing_evidence`. It does not add separate mass for `cross_set_conflict`, `no_dissent`, or a duplicate regime-conflict boolean. No remaining obvious duplicate charge makes the current decision materially misleading.

---

## 7. Confidence

Material confidence inputs are upstream-derived:

- evidence quality: evidence-set weights from W6/W6 reasoning.
- consensus/source diversity: evidence-set composition.
- regime alignment: derived from thesis direction and W2 regime.
- counter/missing/internal penalties: W7 assessment and thesis unknowns.
- thesis support: penalty-adjusted W8/W10 support.

Remaining fallback/proxy values:

- `temporal_recency` defaults to 1.0 when thesis metadata lacks `avg_temporal_recency`; this has computational weight but was previously quantified as decision-neutral at current facts.
- `knowledge_record_quality` is a provenance-chain proxy, not a measured KR-quality score.
- scenario `confidence_id` still uses a `cf_fallback_*` label, but this is cosmetic and does not affect computation.
- OOS ECE is absent and therefore no OOS cap is applied; this is visible in confidence metadata and not a fabricated pass.

None of these fallback/proxy values currently invalidates the institutional result.

---

## 8. RiskReward

The previous fallback-derived confidence path has been removed/replaced for the current production path. ScenarioGeneration first uses `thesis.institutional_support`; raw `avg_supporting_weight` is used only if penalty-adjusted support is absent.

Current RiskReward inputs are institutionally defensible within the frozen W12 ordering:

- `final_confidence=0.3972` comes from penalty-adjusted thesis support.
- `remaining_uncertainty=0.6028` is the deterministic complement of that scenario confidence.
- reliability is derived from the same scenario confidence.
- expected direction, time horizon, scenario probabilities, and regime path come from the generated thesis scenarios.

These are scenario-model quantities, not direct market measurements, but they no longer depend on the previously audited raw evidence-weight fallback.

---

## 9. Decision

The latest institutional NO_TRADE is explainable from actual upstream values:

- selected thesis: bullish `th_c7d384c03b5c.v2`.
- selected scenario: base scenario, probability 0.5.
- institutional confidence: 0.2494.
- confidence gate: `NO_TRADE_CONFIDENCE = 0.5`.
- risk/reward: acceptable, ratio 0.9682, not the blocking gate.
- composite: 0.5403.
- bias review: critical/human-review flag recorded; since the decision was already NO_TRADE, it annotated rather than changed the decision.

The emitted decision is not caused by a disconnected or fabricated gate. It is a conservative decision from connected upstream evidence and a live confidence threshold.

---

## 10. Execution / Risk Branch

The known RiskDecision/execution disconnection is classified as:

**future execution integration**

Reason: `risk_gate` is computed on the forecast/risk branch and is bundled into `finalize` as `risk_decision`, but it is not consumed by the institutional `DecisionEngine`, does not veto or override the institutional decision, and no execution stage consumes it for live allocation. The latest runtime can therefore show `risk_decision=proceed` beside institutional `NO_TRADE` without materially invalidating institutional intelligence validation.

This should not be corrected merely because it exists. It becomes material only when execution integration is commissioned or when `risk_decision` is promoted to an authoritative trade/allocation gate.

---

## Final Gate

**A) READY FOR OPERATIONAL VALIDATION**

Operational metrics to monitor during the next runtimes:

1. OI second-observation behavior: `open_interest_change_pct` should move from first-capture `0.0` to a real interval-derived value once a prior yfinance `openInterest` state exists.
2. Evidence-set composition: count and event types, especially `ETF_FLOW`, `USD_FX`, `GENERAL`, and any admitted `REAL_YIELD`/`INFLATION` evidence that survives SignalAssessment filtering.
3. CounterEvidence decomposition: `conflict_severity`, `confidence_penalty`, `missing_evidence`, and `bias_flags`, watching for duplicate penalty reappearance.
4. Institutional confidence drivers: final confidence, support factor, temporal_recency default exposure, and regime_alignment.
5. Decision reconciliation fields: institutional decision vs legacy decision vs risk_decision, ensuring only `decision_engine` remains authoritative.

First runtime observation to check:

- Confirm OI second-observation behavior in `pre_market_scan.positioning_snapshot.open_interest_change_pct` and downstream `SignalAssessment`/`EvidenceCollection` volume-flow effects for XAU/USD and Gold Positioning.

No further broad architecture audit is justified at this stage. The next appropriate phase is operational validation with targeted metric monitoring, not another correction-mode architecture sweep.
