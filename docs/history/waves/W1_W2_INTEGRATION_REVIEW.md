# W1–W2 Institutional Integration Review

**Reviewer**: opencode
**Date**: 2026-07-29
**Scope**: W1 (Knowledge Record Ingestion & Encoding) and W2 (Macro Regime Diagnosis & Indicator Selection) as implemented in `src/knowledge/ingestion/` and `src/knowledge/regime/`

---

## 1. Integration Status

| Interface | Status | Description |
|-----------|--------|-------------|
| W1 → W2 (knowledge → regime) | **NOT CONNECTED** | W2 never reads the KnowledgeGraph produced by W1. The `REGIME_KR_MAP` in `indicator_hierarchy.py` is hardcoded, not derived from parsed KRs. |
| W1 → W2 (regime names) | **MISALIGNED** | Two separate regime naming conventions with no shared constant module. |
| W2 → W1 (regime activation filter) | **NOT IMPLEMENTED** | No mechanism exists to activate/deactivate KRs based on current regime. The `same_regime` graph edges exist but are never queried by W2. |
| W1 internal: parser → adapter | **CONNECTED** | `ingestion_pipeline.py` calls `create_graph_node()` per record. |
| W1 internal: adapter → graph | **CONNECTED** | `create_graph_node()` → `GraphNode`, `create_regime_relations()` → `GraphRelation`. |
| W2 internal: detector → transition | **CONNECTED** | `RegimeTransitionDetector.detect()` consumes output of `InstitutionalRegimeDetector`. |
| W2 internal: detector → hierarchy | **NOT CONNECTED** | `IndicatorHierarchyGenerator` is independent; never receives regime diagnosis output. |
| W2 internal: GRAM → detector | **CONNECTED BY CONTRACT** | `InstitutionalRegimeDetector.fit()` accepts `gram_residual_series` param. |
| W1 → W3 | **OUTPUT READY** | KnowledgeGraph with 83 nodes, 724 relations, full lineage traceability exists. |
| W2 → W3 | **OUTPUT NOT EXPOSED** | W2 outputs are in-memory DataFrames, no serialized contract or service interface. |

---

## 2. Detailed Verification

### 2.1 Knowledge Records Correctly Influence Regime-Specific Reasoning

**Finding: NOT VERIFIED -- no data path exists.**

The W1 pipeline produces a `KnowledgeGraph` with 83 nodes, each carrying `regimes` (extracted from `regime_dependence`), `mechanism`, `preconditions`, `trigger`, `failure_conditions`, etc. The graph has:
- `same_regime` edges connecting KRs that share a regime label
- `same_event_type` edges connecting KRs within the same category

However, W2's `IndicatorHierarchyGenerator` uses a **hardcoded** `REGIME_KR_MAP` that was written manually, not derived from the parsed KB:

```python
REGIME_KR_MAP = {
    "NORMAL_GROWTH": ["KR-001", "KR-005", "KR-007", "KR-008", "KR-010", "KR-019"],
    "INFLATIONARY": ["KR-003", "KR-004", "KR-012", "KR-017"],
    ...
}
```

When checked against actual KB `regime_dependence` fields:
- KR-012 regime_dependence: "Most powerful in Inflationary regime. Less powerful in Deflationary/Crisis regime." -- correct for INFLATIONARY.
- KR-017 regime_dependence: "Operates in Fiscal Dominance regime." -- Fiscal Dominance is NOT INFLATIONARY per the W2 taxonomy. This KR is misattributed.
- KR-081 regime_dependence: "Regime indicator by definition." -- generic, not specifically STRUCTURAL_REGIME_CHANGE.

This means **any reasoning that depends on "which KRs apply to which regime" will be wrong** because:
1. The mapping is a manual duplicate of the KB data, not a query.
2. It misses many KRs with relevant regime_dependence fields (e.g., KR-002 mentions Inflationary, KR-006 mentions growth-driven cuts, KR-009 mentions regimes).
3. It includes KRs whose regime_dependence doesn't match the assigned regime.

**Risk: HIGH.** All downstream workflows (W3–W17) that filter KRs by regime will operate on stale/incomplete data.

### 2.2 Regime Transitions Activate/Deactivate Relevant Knowledge Records

**Finding: NOT IMPLEMENTED.**

The `RegimeTransitionDetector` produces detailed transition metadata (date, regime, max_probability, in_transition, entropy, regime_changed, prev_regime, transition_type). But:
- There is no consumer of this output that filters the KnowledgeGraph
- No "active KR set" is derived from the current regime
- No mechanism deactivates KRs whose `failure_conditions` match the current regime state
- W2 has no concept of querying the graph for regime-filtered KRs

**Risk: MEDIUM.** W3–W6 all depend on regime-aware evidence selection. Without this bridge, every subsequent workflow must re-implement the same query logic.

### 2.3 Indicator Hierarchy References Correct Institutional Knowledge

**Finding: PARTIALLY CORRECT -- references are static, not dynamic.**

The `IndicatorHierarchyGenerator` defines indicator lists per regime that match Meth. §9 correctly. Strengths:
- Indicator names, weights, and tier assignments follow the Methodology precisely
- Trigger levels per regime are documented
- All 6 regimes are covered with appropriate dominant/secondary/weaker tiers

Weaknesses:
- `REGIME_KR_MAP` is hardcoded and does not reflect actual KB entries (see 2.1)
- The `associated_krs` field in each indicator entry is identical for all indicators within a regime (it copies the entire `REGIME_KR_MAP[regime]` list). This is technically pointless -- each indicator should reference only the KRs relevant to that specific indicator.
- No `generate()` call ever receives input from the regime detector. The hierarchy is a static lookup, not a pipeline stage.

**Risk: LOW to MEDIUM.** The indicator names/weights are correct, but the KR association is misleading. If a downstream workflow trusts `associated_krs` to be per-indicator specific, it will be wrong.

### 2.4 Confidence Propagation Is Consistent

**Finding: THREE INDEPENDENT CONFIDENCE SCHEMES, NO PROPAGATION PATH.**

| Source | Scheme | Range | Typical Values |
|--------|--------|-------|----------------|
| KB Confidence text | `_parse_confidence()` | 0.0–1.0 | 0.85 for "High", 0.15 for "Low" |
| KB Strength text | `_parse_strength()` | 0.0–1.0 | 0.95 for "Very strong", 0.50 for "Moderate" |
| W2 Regime probability | `_compute_regime_probs()` | 0.0–1.0 | 0.7 for Normal Growth at high composite |
| W2 Transition threshold | Config constant | 0.0–1.0 | 0.5 (hardcoded default) |

Issues:
- KB confidence is binary text (`"High (pre-2022). Low (post-2022)"` → matches "high" → returns 0.85 even though the text describes mixed confidence). The parser returns the **first** match, not the most relevant.
- W2 regime confidence is derived from composite score thresholds (arbitrary breakpoints at 1.0, 0.0, -1.0), not from Markov model probabilities or any calibrated ML output.
- There is no mechanism to propagate KR confidence → indicator weight → regime confidence or vice versa.
- The `transition_threshold=0.5` default is a magic number with no empirical basis.

**Risk: MEDIUM.** Confidence is stored but not propagated. W3 will need ad-hoc confidence rules.

### 2.5 Duplicated Logic

**Finding: Four instances of duplication or near-duplication.**

| # | What | Where | Duplicated In | Impact |
|---|------|-------|---------------|--------|
| 1 | Regime name constants | `adapter_dispatch.REGIME_TYPES` (human-readable) | `institutional_regime_detector` constants (UPPER_SNAKE) | No shared module → name mismatches, no single source of truth |
| 2 | Regime→KR mapping | `adapter_dispatch.create_regime_relations()` derives from actual graph edges | `indicator_hierarchy.REGIME_KR_MAP` hardcoded | Two different regime→KR associations exist; they will drift |
| 3 | Regime detection from metadata | `ingestion_pipeline.validate_kr()` checks field presence | Spec requests `EventValidator` usage | Validation logic is ad-hoc instead of reusing `EventValidator` |
| 4 | KR→Evidence conversion | `adapter_dispatch.to_evidence()` via `type()` hack | Existing `CbiEvidenceAdapter`, `CfiEvidenceAdapter`, `CaiEvidenceAdapter` | The hack bypasses actual contract objects, making conversion non-functional |

### 2.6 W2 Outputs Consumable by Future Workflows

**Finding: PARTIALLY -- outputs exist but lack serialization contracts.**

W2 outputs:
| Output | Format | Consumable by W3? | Issue |
|--------|--------|-------------------|-------|
| Regime classification | `pd.DataFrame` (in-memory) | Not directly | No serialization, no query interface |
| Regime probabilities | `pd.DataFrame` (in-memory) | Not directly | Same |
| Transition detection | `pd.DataFrame` (in-memory) | Not directly | Same |
| GRAM residual data | `pd.DataFrame` (in-memory) | Not directly | Same |
| GRAM current status | `dict` | Yes, but fragile | Key names are internal |
| Indicator hierarchy | `dict` | Yes | Static only, not regime-dynamic |
| Trigger levels | `dict` | Yes | Static |

Missing serialization contracts:
- No `Repository` class for W2 outputs (compare: `EvidenceRepository`, `ReasoningRepository`, `GraphRepository`)
- No `to_dict()` / `from_dict()` on any W2 class
- No `PipelineResult` integration -- W2 outputs are not part of any pipeline result type

**Risk: HIGH for W3.** W3 cannot call `regime_detector.fit()` daily -- it needs a fast `diagnose()` method that returns a typed, serializable `RegimeDiagnosis` object.

### 2.7 Missing Interfaces Before W3

**Critical missing interfaces:**

| # | Missing Interface | Why W3 Needs It | Where It Should Live |
|---|-------------------|-----------------|---------------------|
| 1 | `query_krs_by_regime(regime: str) -> list[KnowledgeRecord]` | W3 needs to know which KRs apply to today's regime | `knowledge.graph.builder` or `knowledge.graph.repository` |
| 2 | `RegimeDiagnosis` typed contract | W3 needs a stable, typed object not a raw DataFrame | `knowledge.regime.diagnosis` or `knowledge.regime.contracts` |
| 3 | `diagnose()` fast path (no re-fit) | W3 runs daily, cannot re-fit Markov every time | `InstitutionalRegimeDetector.diagnose()` |
| 4 | Regime → indicator-hierarchy dynamic query | W3 needs to know which indicators to fetch | `IndicatorHierarchyGenerator.generate(regime)` already works but needs to receive regime from detector |
| 5 | BEI data connector | W3 fetches BEI for inflation analysis | `connectors/` directory |
| 6 | Term premium data connector | W3 fetches term premium for regime context | `connectors/` directory |
| 7 | GPR data connector | W3 fetches GPR for geopolitical overlay | `connectors/` directory |
| 8 | Serialization for all W2 outputs | W3 needs to pass regime data to later workflows | Repository pattern per existing convention |

---

## 3. Risks

| # | Risk | Severity | Likelihood | Mitigation |
|---|------|----------|------------|------------|
| R1 | W1 and W2 operate in isolation with no data flow between them | **CRITICAL** | Certain | Build W1→W2 bridge before any workflow that needs regime-aware KR queries (W3, W4, W6) |
| R2 | Hardcoded REGIME_KR_MAP will drift from actual KB content | HIGH | Certain | Replace with dynamic query against KnowledgeGraph; eliminate hardcoded map |
| R3 | W2 cannot run incrementally (full Markov re-fit required) | HIGH | Certain | Add `diagnose()` method that loads cached Markov results + fast overlay |
| R4 | Regime name fragmentation leads to mismatched lookups | MEDIUM | Likely | Create `regime/constants.py` shared module |
| R5 | to_evidence() hack silently produces broken Evidence objects | MEDIUM | Likely | Remove; replace with proper adapter pattern using real contract objects |
| R6 | Confidence values are misleading (KR-001: "High (pre-2022), Low (post-2022)" → 0.85) | MEDIUM | Certain | Improve `_parse_confidence` to handle mixed confidence text |
| R7 | No cross-asset consistency checker despite W2 spec requirement | MEDIUM | Certain | Implement before W6 (Evidence Collection) |
| R8 | No data connectors for BEI, term premium, GPR (W2 spec requirement) | MEDIUM | Certain | Implement as part of connector work |

---

## 4. Required Contracts

The following contracts must exist before W3 can safely begin:

```python
# Contract 1: DiagnosedRegime -- W2 output that W3+ can consume
@dataclass(frozen=True)
class DiagnosedRegime:
    regime: str                    # NORMAL_GROWTH | INFLATIONARY | ...
    label: str                     # Human-readable label
    confidence: float              # 0.0–1.0
    probabilities: dict[str, float]  # All 6 regime probabilities
    in_transition: bool
    transition_type: str           # "deterioration" | "improvement" | "none" | "regime_break"
    transition_confidence: float   # 0.0–1.0
    gram_residual: float
    gram_trend: str                # "growing" | "shrinking" | "stable"
    indicator_hierarchy: list[dict]  # Dominant → secondary → weaker indicators
    timestamp: str

# Contract 2: KRQuery -- W1 output accessible to W2+
@dataclass(frozen=True)
class KRQuery:
    @staticmethod
    def by_regime(graph: KnowledgeGraph, regime: str) -> list[GraphNode]: ...
    @staticmethod
    def by_event_type(graph: KnowledgeGraph, event_type: str) -> list[GraphNode]: ...
    @staticmethod
    def by_condition(graph: KnowledgeGraph, condition: dict) -> list[GraphNode]: ...

# Contract 3: RegimeIndicator -- typed indicator entry
@dataclass(frozen=True)
class RegimeIndicator:
    indicator: str
    weight: float
    description: str
    tier: str                    # "dominant" | "secondary" | "weaker"
    associated_krs: tuple[str, ...]
```

---

## 5. Recommended Adjustments (No Code Changes -- Design Only)

### A. Create Shared Regime Constants Module
Merge the regime taxonomy into a single source of truth at `knowledge/regime/constants.py`:
- Define all 6 canonical regimes with consistent keys
- Include the human-readable labels, Meth. §9 descriptions, and threshold defaults
- Both `adapter_dispatch.py` and `indicator_hierarchy.py` should import from this module

### B. Replace Hardcoded REGIME_KR_MAP with Dynamic Graph Query
The `IndicatorHierarchyGenerator` should accept a `KnowledgeGraph` reference and query `get_neighbors()` via `same_regime` edges to find KRs associated with each regime. This:
- Eliminates drift between the KB and the code
- Automatically updates when new KRs are added to the KB
- Preserves the correct regime-to-KR associations per the actual `regime_dependence` field

### C. Add RegimeDiagnosis Typed Output
Wrap all W2 outputs into a single `DiagnosedRegime` frozen dataclass that can be serialized, stored in a `RegimeRepository`, and consumed by any downstream workflow.

### D. Add Fast Diagnose Path
Add a `diagnose(gpr_value, gram_residual_value, composite_score)` method to `InstitutionalRegimeDetector` that skips the full Markov re-fit and applies the overlay logic only. The Markov fit should be cached and refreshed on a configurable cadence (daily or weekly), not on every call.

### E. Fix Regime Name Extraction in adapter_dispatch.py
The `_extract_regimes()` function uses substring matching which produces false positives and misses valid regimes. The fix should:
- Use word-boundary matching or a known-regime set
- Handle "Deflationary / Crisis" and "DEFLATIONARY_CRISIS" consistently
- Not return raw text when no regime is matched (currently returns `[regime_dependence]` as fallback)

### F. Remove Dead Code in regime_transition.py
The unused `regime_break` set comprehension in `_classify_transition()` should be removed. The `if current == "STRUCTURAL_REGIME_CHANGE"` check directly handles this case.

### G. Plan for to_evidence() Replacement
The `type()` hack in `adapter_dispatch.to_evidence()` should be replaced with proper calls to `CbiEvidenceAdapter`, `CfiEvidenceAdapter`, or `CaiEvidenceAdapter` using real contract objects. Document which KR categories map to which adapter.

### H. Improve Confidence Parsing
`_parse_confidence()` currently matches the first keyword (e.g., "High" in "High (pre-2022). Low (post-2022)."). For mixed-confidence KRs, consider returning a tuple `(confidence, secondary_confidence)` or parsing the most pessimistic value for safety.

---

## 6. W1 Completion Criteria Audit

| Completion Criterion | Status | Notes |
|----------------------|--------|-------|
| All 207+ KRs parsed and encoded | **PARTIAL** | 83 KRs parsed (document contains 83, not 207+). The spec references "19 categories, ~207+ records" but only 6 categories exist in the KB. |
| All KR fields populated | **PASS** | Validation confirms 0 missing field errors across all 83 KRs. |
| Graph edges have causal direction, confidence, regime-dependence | **PARTIAL** | Regime dependence is present. Causal direction is always `"undirected"`, confidence is always `0.5`. |
| CausalGraph validates acyclic | **NOT IMPLEMENTED** | No `CausalGraph` is produced. The existing `CausalGraph` module in `knowledge/causal/` is not used. |
| Lineage traceable | **PASS** | 83 lineage records registered via `LineageRegistry`. |
| Existing benchmarks pass | **PASS** | 1976 tests pass, 0 regressions. |

## 7. W2 Completion Criteria Audit

| Completion Criterion | Status | Notes |
|----------------------|--------|-------|
| 6-regime classifier outputs labels matching Meth. §9 | **PASS** | InstitutionalRegimeDetector produces all 6 regimes. |
| Indicator hierarchy matches Meth. §9 per regime | **PASS** | Indicator lists are correct per Meth. §9. |
| Regime transition detection within 2σ of expert classification | **NOT TESTABLE** | No historical expert classification dataset exists. Requires retrospective validation. |
| GRAM residual flags 2022 regime break within 3 months | **NOT TESTABLE** | Requires live FRED data feed. Architecture supports it (rolling window) but hasn't been tested on real 2022 data. |
| Cross-asset consistency checker | **NOT IMPLEMENTED** | Missing from W2 spec's "Missing Capabilities" list but listed as a completion criterion. |
| Wired into InstitutionalOrchestrator | **NOT IMPLEMENTED** | No integration with `InstitutionalOrchestrator`. |
| All tests pass | **PASS** | 1976 pass, 0 regressions. |

---

## 8. GO / NO-GO Recommendation for W3

### NO-GO — Do NOT begin W3 until the following conditions are met:

**BLOCKING (must fix before W3):**
1. **Regime→KR query interface** — W3 needs to know which KRs apply to today's regime. Without this, W3 cannot connect overnight signals to institutional knowledge. Create `KRQuery.by_regime()` as a graph query.
2. **DiagnosedRegime contract** — W3 needs a typed, serializable regime diagnosis, not raw DataFrames. Create the contract and a `diagnose()` fast path.
3. **Indicator hierarchy fed by regime detector** — W3 needs to know which indicators to fetch. The `IndicatorHierarchyGenerator` must receive the current regime diagnosis, not be called independently.

**RECOMMENDED (fix before W3 to avoid rework):**
4. **Shared regime constants module** — Prevents name fragmentation across W1, W2, W3.
5. **Regime name extraction fix** — Without this, `_extract_regimes()` produces regime labels that don't match the W2 taxonomy, making the `same_regime` graph edges unreliable.
6. **Confidence parsing improvement** — Without this, KR-001 reports 0.85 confidence when the text clearly describes a breakdown in the relationship.

**DEFERRED (can fix during or after W3):**
7. Cross-asset consistency checker (W2 completion criterion, not critical for W3)
8. Data connectors for BEI/term premium/GPR (needed by W3's data fetching stage but can be stubbed)
9. CausalGraph output (W1 completion criterion, needed by W11)
10. `to_evidence()` replacement (needed by W6 Evidence Collection, not W3)

**Recommended action**: Create the three blocking contracts, then proceed to W3. Estimated effort: 1–2 hours for contracts, shared constants, and query interface. No ML or data work required.
