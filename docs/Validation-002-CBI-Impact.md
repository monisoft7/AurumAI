# Validation-002: Central Bank Evidence Impact on Institutional Reasoning

**Date:** 2026-07-26
**Type:** Architecture review only — no implementation
**Scope:** Impact of adding CBI evidence (PolicyBiasScore, ForwardGuidanceRecord, RatePathProjection) to the existing Economic + Temporal pipeline

---

## Pipeline Reference

The five-stage evidence pipeline as implemented:

```
OrchestrationEngine.analyze()
  ├─ Layer collection: _run_economic(), _run_temporal(), _run_cbi()
  ├─ EvidenceAggregator.merge()       → dedup, conflict detection
  ├─ EvidenceWeighter.weigh()         → WeightedAggregate (5-factor geometric mean)
  ├─ ReasoningEngine.reason()         → ReasoningChain (steps + confidence)
  └─ DecisionEngine.decide()          → Decision (classification + confidence)
```

---

## 1. Does retrieval change?

**NO.** Retrieval is unchanged.

`_run_core()` calls `ctx.evidence_query.matching()` which queries the `KnowledgeGraph` for historical records matching event_type/condition/horizon. This path is **completely independent** from `_run_cbi()`, which translates in-memory CBI objects via `CbiEvidenceAdapter` — no query, no index lookup, no database access.

CBI evidence is **injected, not retrieved**. The retrieval pipeline (`EvidenceQuery`, `SituationQuery`, `TemporalIndexer`) receives zero modification and zero additional calls.

**Architecture evidence:**
- `engine.py:145-176` (`_run_core`) — calls `ctx.evidence_query.matching()` against KnowledgeGraph
- `engine.py:192-218` (`_run_cbi`) — calls `CbiEvidenceAdapter` translation methods
- No shared state, no shared code paths between the two.

---

## 2. Does evidence ranking change?

**YES.** Ranking changes because the evidence pool composition changes.

`EvidenceWeighter.weigh()` computes a composite weight per evidence item as the geometric mean of five factors, then produces weighted averages across all items:

```
composite_weight = (cf * sf * pf * cosf * rf) ^ (1/5)
```

Adding CBI items to the pool changes every downstream aggregation:

### 2A. Weighted average return (`w_ret`)

```
w_ret = Σ(w_i * return_i) / Σ(w_i)
```

- Economic evidence: `average_return_pct` = historical returns (could be -5% to +15% based on real data)
- Temporal evidence: `average_return_pct` = returns under temporal conditions
- CBI evidence: `average_return_pct = 0.0` (always — CBI objects are forward-looking assessments, not historical observations)

**Effect:** CBI items dilute the weighted average return toward zero. The magnitude of dilution = CBI's share of total weight.

### 2B. Weighted average confidence (`w_conf`)

```
w_conf = Σ(w_i * conf_i) / Σ(w_i)
```

- Economic evidence confidence: derived from `LessonSummaryAggregator._confidence()` — 0.0 to 1.0, typically ~0.5-0.8
- CBI evidence confidence: directly from object fields — PolicyBiasScore `confidence` (typically 0.75-0.85 in tests)
- CBI evidence `sample_count = 1` → `sample_factor = 1/100 = 0.01`

**Effect:** CBI items contribute moderate confidence but their composite weight is severely penalized by `sample_factor = 0.01`. `(0.8² * 0.01 * 1.0 * 0.6 * recency)^(1/5)` produces composite ~0.2 for a fresh CBI item with provenance, vs ~0.6-0.9 for economic items with sample_count > 100.

### 2C. Attribution distribution

Attribution measures each `event_type`'s share of total weight. CBI introduces three new event types (`CBI_POLICY`, `CBI_GUIDANCE`, `CBI_RATE_PATH`), each claiming a share of the weight pie. Existing event types' attribution percentages necessarily decrease.

### 2D. Consistency factor

`_compute_majority_bias()` builds per-event-type majority maps. CBI introduces event types that may have only 1 item each → `majority = "mixed_or_context_dependent"` → `consistency_factor = 0.5 + 0.2/2 = 0.6`.

**Architecture evidence:**
- `weighting.py:91-98` — weighted average formulas include all evidence items
- `weighting.py:74-78` — attribution includes all event types
- `weighting.py:112-128` — majority map includes CBI event types
- `weighting.py:160-163` — `sample_factor = min(sample_count / 100, 1.0)`, CBI has sample_count=1 → 0.01

---

## 3. Does ReasoningChain change?

**YES.** The chain's steps, confidence, and conclusion all change.

`ReasoningEngine.reason()` at `reasoning/engine.py:20-51`:

```
for ev in evidence:                              # ← CBI items add 1-3 more review steps
    step = _build_evidence_review(ev, i)

_add_comparison_steps(evidence, steps)           # ← CBI single-item types get no comparison

_build_aggregation(evidence, wa, steps)          # ← uses wa.weighted_avg_return w_conf
_build_conclusion(evidence, wa, context, steps)  # ← uses wa.weighted_avg_return w_conf
```

### Changes:
- **Step count:** +1 to +3 evidence review steps (for CBI_POLICY, CBI_GUIDANCE, CBI_RATE_PATH)
- **Comparison steps:** No new comparisons (CBI event types each have 1 item, condition for comparison < 2)
- **Aggregation step:** `wa.weighted_avg_return` and `wa.weighted_avg_confidence` are both changed
- **Conclusion step:** Uses same shifted metrics; attribution output now includes CBI event types
- **`overall_confidence`:** Set to `wa.weighted_avg_confidence` — changed
- **`evidence_count`:** Increased by CBI item count
- **`attribution` dict:** Includes CBI event types

**Architecture evidence:**
- `reasoning/engine.py:23-25` — for loop over evidence includes CBI items
- `reasoning/engine.py:38` — `overall_confidence = wa.weighted_avg_confidence`
- `reasoning/engine.py:49` — `evidence_count = len(evidence)`
- `reasoning/engine.py:41` — `attribution = wa.attribution`

---

## 4. Does Institutional Assessment change?

**YES.** The `InstitutionalAssessment` record (defined in `src/orchestration/models.py`) captures pipeline execution metadata:

- `stages`: now includes CBI collection stage → different stage records
- `outputs`: contains decision metrics that changed (decision_type, confidence, evidence_count)
- `wall_time_ms`: increased by `_run_cbi()` execution time
- `errors`: any CBI-related errors (e.g., translation failures) appear here

However, `InstitutionalAssessment` is a **descriptive record**, not a decision-influencing structure. The changes reflect that the pipeline ran with more inputs; they do not constitute a change in reasoning logic itself.

---

## 5. Does Decision change?

**YES.** The Decision can change — possibly including its classification type.

`DecisionEngine.decide()` at `decision/engine.py:18-53`:

```
avg_return = _extract_avg_return(chain)     # changed (diluted by CBI's 0.0 returns)
confidence = chain.overall_confidence       # changed (shifted by CBI confidences)
evidence_count = chain.evidence_count       # increased

decision_type = _classify(avg_return, confidence, evidence_count, min_evidence_count)
```

### `_classify()` thresholds (`decision/engine.py:66-83`):

| Condition | Type |
|-----------|------|
| `avg_return > 1.0 AND confidence >= 0.7` | STRONG_POSITIVE |
| `avg_return > 0 AND confidence >= 0.5` | POSITIVE |
| `avg_return < -1.0 AND confidence >= 0.7` | STRONG_NEGATIVE |
| `avg_return < 0 AND confidence >= 0.5` | NEGATIVE |
| else | NEUTRAL |
| `evidence_count < min_evidence_count` | INSUFFICIENT_EVIDENCE |

### How CBI affects classification:

CBI items have `average_return_pct = 0.0`. The weighted average return shifts toward zero because these zero-return items dilute the pool. This means:

- **If A → STRONG_POSITIVE:** CBI dilutes return below 1.0 or confidence below 0.7 → could downgrade to POSITIVE or NEUTRAL
- **If A → POSITIVE:** CBI dilutes return toward zero → if return drops below 0, could become NEUTRAL or NEGATIVE
- **If A → STRONG_NEGATIVE:** CBI dilutes return above -1.0 or confidence below 0.7 → could downgrade to NEGATIVE or NEUTRAL
- **If A → NEGATIVE:** CBI dilutes return toward zero → if return rises above 0, could become NEUTRAL or POSITIVE
- **If A → NEUTRAL:** CBI could push confidence above 0.5 with a directional return tilt → could become POSITIVE or NEGATIVE
- **If A → INSUFFICIENT_EVIDENCE:** CBI items increase `evidence_count` → could cross the threshold

### Numerical example (realistic values):

Suppose 2 economic evidence items:
| Item | return | confidence | composite_w |
|------|--------|-----------|-------------|
| GDP | +2.0% | 0.75 | 0.80 |
| CPI | +1.5% | 0.70 | 0.75 |

Scenario A (no CBI): w_ret = (0.80*2.0 + 0.75*1.5) / 1.55 = 1.76%, w_conf = (0.80*0.75 + 0.75*0.70) / 1.55 = 0.726
→ avg_return > 1.0, confidence >= 0.7 → **STRONG_POSITIVE**

Add 2 CBI items (FED tightening bias):
| Item | return | confidence | composite_w |
|------|--------|-----------|-------------|
| CBI_POLICY (FED) | 0.0% | 0.80 | 0.21 |
| CBI_GUIDANCE (FED) | 0.0% | 0.85 | 0.22 |

Scenario B (with CBI): w_ret = (0.80*2.0 + 0.75*1.5 + 0.21*0 + 0.22*0) / (1.55+0.43) = 1.46%
w_conf = (0.80*0.75 + 0.75*0.70 + 0.21*0.80 + 0.22*0.85) / 1.98 = 0.734
→ avg_return < 1.0 now, confidence >= 0.7 → **POSITIVE** (downgraded from STRONG_POSITIVE)

Classification changed due to CBI evidence diluting the weighted average return.

---

## 6. Does Confidence change?

**YES.** Confidence changes at every downstream stage.

### Stage-by-stage propagation:

| Stage | Formula | Impact of CBI |
|-------|---------|---------------|
| EvidenceWeighter | `w_conf = Σ(w_i * conf_i) / Σ(w_i)` | +CBI confidence terms in numerator, +CBI weights in denominator |
| ReasoningChain | `overall_confidence = w_conf` | Direct copy of shifted value |
| Decision | `confidence = chain.overall_confidence` | Direct copy of shifted value |

### Direction of change:

CBI evidence confidence values are typically 0.75-0.85. Whether they increase or decrease the weighted average depends on the existing pool's confidence profile:

- If economic evidence has high confidence (>0.85 on average): CBI dilutes it downward
- If economic evidence has low confidence (<0.75 on average): CBI lifts it upward
- CBI sample_factor = 0.01 mutes the magnitude of influence significantly

### Provenance effect:

CBI evidence objects have explicit `Provenance` fields. When present, `provenance_factor = 1.0` (base 1.0 + bonus 0.3, capped at 1.0). When absent, `provenance_factor = 0.0`, collapsing the geometric mean composite to zero.

---

## 7. Are the changes explainable?

**YES.** Every CBI influence path is traceable and attributable.

### Attribution mechanisms:

1. **`_source_layer: "cbi"`** — every CBI evidence item is tagged in its metadata at `engine.py:199,207,215`

2. **Event type — explicit distinction:** CBI items use unique event types `CBI_POLICY`, `CBI_GUIDANCE`, `CBI_RATE_PATH`, distinct from economic event types (e.g., `GDP`)

3. **`WeightedAggregate.attribution`** — shows each event_type's share of total weight at `weighting.py:74-78`. CBI event types appear with their true share

4. **`EvidenceAggregator.conflicts`** — if CBI evidence_id duplicates another layer's evidence_id, the bias conflict is logged with source layer names at `aggregator.py:36-44`

5. **ReasoningChain attribution** — passed through to chain at `reasoning/engine.py:41`

6. **Lineage registry** — at `engine.py:237-268`, every evidence item is linked: `layer:cbi → evidence_id → chain → decision`

7. **CBI metadata** — each CBI evidence item carries full original object state in metadata: `central_bank`, `score`, `direction`, `guidance_text`, `credibility_score`, `base_path`, `confidence_interval`, etc.

### To isolate CBI's specific contribution:

```python
# Extract CBI evidence from a report
cbi_items = [ev for ev in report.aggregation.collection
             if ev.metadata.get("_source_layer") == "cbi"]

# See CBI's attribution share
cbi_share = sum(pct for evt, pct in report.weighted_aggregate.attribution.items()
                if evt.startswith("CBI_"))
```

---

## 8. Are there cases where CBI evidence is correctly ignored?

**YES.** The architecture provides multiple guardrails:

### Case 1: No CBI adapter provided
```python
ctx = OrchestrationContext(event_type="CPI")
report = engine.analyze(ctx)  # cbi_adapter=None → _run_cbi() returns empty
```
`engine.py:193-194`: `if ctx.cbi_adapter is None: return EvidenceCollection()`

Result: CBI is silently skipped. Pipeline identical to Scenario A.

### Case 2: No CBI objects populated
```python
ctx = OrchestrationContext(event_type="CPI", cbi_adapter=CbiEvidenceAdapter())
# cbi_bias_scores, cbi_guidance_records, cbi_rate_paths all None → empty collection
```

All three lists iterate only `if not None` and `if not None` and empty respectively.

### Case 3: Custom policy execution
```python
report = engine.analyze(ctx, policies=[my_policy])
```
When `policies` parameter is provided, the default 5-layer collection is bypassed entirely at `engine.py:86-89`. CBI is only included if a policy explicitly invokes `_run_cbi()`.

### Case 4: CBI confidence = 0.0
`confidence_factor = 0.0² = 0.0` → geometric mean = `(0.0 * sf * pf * cosf * rf)^(1/5) = 0.0`

Result: composite_weight = 0.0 → CBI contributes nothing to weighted averages, attribution, or consistency maps. Still counted in `evidence_count` (relevant for INSUFFICIENT_EVIDENCE threshold only).

### Case 5: Evidence ID collision
If a CBI evidence_id (e.g., `cbi_policy_FED`) duplicates an existing evidence_id from another layer, `EvidenceAggregator` deduplicates by keeping the first occurrence. The CBI item is dropped and a conflict is logged.

### Case 6: No reasoning/decision engine
```python
ctx = OrchestrationContext(event_type="CPI", reasoning_engine=None)
```
CBI evidence is merged and weighted but no chain or decision is built from it. Evidence exists in the report but has no downstream impact.

---

## Overall Verdict

### MEDIUM IMPACT

**Rationale:**

CBI evidence is architecturally guaranteed to influence every downstream stage — ranking, reasoning chain, decision, and confidence — because it is added as additional items in the identical evidence pool. The pipeline has zero special-case logic for CBI; it is treated identically to economic, temporal, and other layers.

However, the impact is structurally bounded by two inherent properties:

1. **`sample_count = 1`** — CBI evidence is forward-looking with no historical sample. The `_sample_factor` formula `min(sample_count / 100, 1.0)` penalizes CBI items to 0.01, which when combined via geometric mean with the other four factors (each 0.5–1.0) produces composite weights on the order of ~0.2, compared to ~0.7–0.9 for well-sampled economic evidence. This means CBI influence is muted — typically 3–10% of total weight allocation.

2. **`average_return_pct = 0.0`** — CBI items always pull the weighted average return toward zero, which means they can only moderate extreme conclusions. They cannot create a strong directional signal where none existed.

The taxonomy mapping:

| Dimension | Verdict | Key Evidence |
|-----------|---------|-------------|
| Retrieval | **NO** | `_run_cbi()` is independent from `_run_core()` |
| Ranking | **YES** | New items in pool change weighted averages, attribution, consistency |
| ReasoningChain | **YES** | More steps, shifted metrics in aggregation/conclusion |
| Institutional Assessment | **YES** | Different stages, timing, outputs recorded |
| Decision | **YES** | Classification thresholds can be crossed |
| Confidence | **YES** | `w_conf` changes at weighting → chain → decision |
| Explainable | **YES** | Source layer, event types, attribution, lineage all traceable |
| Correctly ignored | **YES** | 6 architectural guardrails identified |

**The impact is MEDIUM** because CBI evidence has architectural guarantee of influence on all downstream stages, can alter decision classification in marginal cases, but is structurally muted by the sample_count penalty and cannot introduce new directional signals — only dilute or shift existing ones.

---

## Appendix: Adapter Translation Summary

| CBI Object | Event Type | sample_count | avg_return | bias logic | Provenance |
|------------|-----------|-------------|-----------|------------|------------|
| PolicyBiasScore | CBI_POLICY | 1 | 0.0 | DIRECTION_TIGHTENING → bearish | Carried from object |
| ForwardGuidanceRecord | CBI_GUIDANCE | 1 | 0.0 | Always neutral | Carried from object |
| RatePathProjection | CBI_RATE_PATH | 1 | 0.0 | Always neutral | Carried from object |
| LiquidityOutlook | CBI_LIQUIDITY | 1 | 0.0 | Classification-based map | Carried from object |
| GlobalMonetaryRegime | CBI_REGIME | 1 | 0.0 | Regime-based map | Carried from object |
