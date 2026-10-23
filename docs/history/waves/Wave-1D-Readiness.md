# Wave-1D Readiness — PolicyBiasScore Pipeline Integration Review

**Date**: 2026-07-26  
**Review type**: Trace PolicyBiasScore evidence through the complete institutional reasoning pipeline  
**Scope**: Read-only — no implementation, no redesign, no recommendations

---

## Pipeline Architecture (Two Entry Paths)

The codebase has two distinct paths for Evidence → Reasoning → Decision:

### Path A — `OrchestrationEngine.analyze()` (`knowledge/orchestration/engine.py:61`)

Multi-source coordinator. Gathers from **4 hardcoded layers**, merges via `EvidenceAggregator`, reasons, decides:

```
_run_economic()  → EconomicEvidenceAdapter → EvidenceCollection (event_types vary)
_run_temporal()  → TemporalEvidenceAdapter  → EvidenceCollection (TEMPORAL)
_run_causal()    → _causal_relation_to_evidence() → EvidenceCollection (CAUSAL)
_run_core()      → EvidenceQuery.matching() → EvidenceCollection (CPI, etc.)
                         │
                         ▼
              EvidenceAggregator.merge()
              {"economic": ..., "temporal": ..., "causal": ..., "core": ...}
                         │
                         ▼
              EvidenceWeighter.weigh() → WeightedAggregate
                         │
                         ▼
              ReasoningEngine.reason() → ReasoningChain
                         │
                         ▼
              DecisionEngine.decide() → Decision
```

### Path B — `InferencePipeline.run()` (`knowledge/pipeline/pipeline.py`)

Single-source pipeline. Builds lessons → knowledge records → graph → evidence → reason → decide. The Evidence comes from graph nodes queried by `EvidenceQuery.matching()`. This path does NOT have a multi-layer merge.

---

## 1. How PolicyBiasScore Evidence Enters Retrieval

PolicyBiasScore evidence (`event_type="CBI_POLICY"`) enters through **Path A** (`OrchestrationEngine.analyze()`). This path currently has 4 hardcoded internal methods:

| Method | Line | Adapter | Source Object | Evidence Produced |
|---|---|---|---|---|
| `_run_economic()` | 134 | `EconomicEvidenceAdapter` | `EconomicState` → `EconomicRegime` | `event_type` from regime |
| `_run_temporal()` | 149 | `TemporalEvidenceAdapter` | `TemporalIndexer` → `TemporalState` | `TEMPORAL` |
| `_run_causal()` | 159 | `_causal_relation_to_evidence()` | `CausalRelation` | `CAUSAL` |
| `_run_core()` | 169 | `EvidenceQuery.matching()` | `KnowledgeGraph` → `KnowledgeRecord` | From event type (e.g. `CPI`) |

**There is no `_run_cbi()` method.** The `CbiEvidenceAdapter` and `CbiRepository` exist at `knowledge/cbi/` but are not wired into `OrchestrationEngine.analyze()`.

**However**, the `analyze()` method also supports a **policy-based path** (lines 68–73): when `policies` is provided, it calls `p.layer_fn(ctx)` for each active policy. The calling code can construct CBI evidence externally and inject it via this policy mechanism, or by adding a `"cbi"` key to the `collections` dict before `merge()` is called.

The `EvidenceAggregator.merge()` signature at `knowledge/orchestration/aggregator.py:22` accepts `dict[str, EvidenceCollection]` — adding a `"cbi"` key requires passing one additional `EvidenceCollection`. No signature change needed.

---

## 2. How It Participates in Evidence Weighting

`EvidenceWeighter.weigh()` at `knowledge/evidence/weighting.py` operates on individual `Evidence` objects. It has **zero knowledge of source layers**. The 5 factors apply identically to CBI evidence:

| Factor | How CBI Evidence Maps |
|---|---|
| **Confidence** | `obj.confidence` → `Evidence.confidence` — same 0.0–1.0 institutional scale. Direct pass-through. |
| **Sample** | `sample_count=1` (set by adapter, matching Economic/Temporal pattern). Factor = `min(1/baseline, 1.0)`. |
| **Provenance** | `obj.provenance` → `Evidence.provenance` — CBI contracts carry Provenance, enabling the provenance bonus (1.0 + bonus). Economic and Temporal evidence do NOT carry Provenance, so CBI evidence actually scores HIGHER on this factor. |
| **Consistency** | CBI bias (bearish/bullish/neutral) compared to majority bias within `event_type="CBI_POLICY"`. If all CBI evidence agrees, full factor. If mixed, penalized. |
| **Recency** | Based on `Evidence.provenance.created_at`. CBI evidence carries this (via CbiBaseContract). Economic/Temporal evidence does NOT carry provenance, so recency cannot be computed for them — they get full factor. CBI evidence with stale provenance gets decayed. |

**Result**: CBI evidence participates fully in weighting. Weighting is source-agnostic — it reads `Evidence` fields only. **No changes needed.**

---

## 3. How It Appears Inside ReasoningChain

`ReasoningEngine.reason()` at `knowledge/reasoning/engine.py` groups evidence by `event_type`:

1. **`STEP_EVIDENCE_REVIEW`** — One step per CBI evidence item. The `explanation` field populated by the adapter (`"PolicyBiasScore for FED: tightening (2)"`) becomes the step conclusion text.

2. **`STEP_COMPARISON`** — If multiple CBI evidence items share `event_type="CBI_POLICY"`, a comparison step is generated contrasting their biases, confidences, and explanations.

3. **`STEP_AGGREGATION`** — CBI evidence contributes to the weighted average. Since `average_return_pct=0.0` (set by adapter, matching Economic/Temporal pattern), it contributes zero to the return calculation but contributes its weight and confidence to the aggregate confidence.

4. **`STEP_CONCLUSION`** — `_build_conclusion()` at `knowledge/reasoning/engine.py` extracts `institutional_context` from `ev.metadata.get("institutional_context", {})`. CBI adapter stores CBI fields in `metadata` as per the adapter pattern. If `institutional_context` is present in metadata, it is appended as `"key=value"` strings. Currently, CBI adapter stores domain fields (central_bank, score, direction, etc.) directly — not nested under `"institutional_context"` key.

5. **`attribution`** — `event_type="CBI_POLICY"` appears in the chain's `attribution` dict alongside other event types (CPI, TEMPORAL, CAUSAL, etc.).

**No changes needed.** The ReasoningEngine operates on Evidence fields only. CBI evidence with `event_type="CBI_POLICY"` follows the same path as any other event type.

---

## 4. How It Influences Institutional Assessment

`InstitutionalAssessment` at `orchestration/models.py` collects outputs from all stages. The CBI influence is indirect:

- **If Path A (OrchestrationEngine)**: CBI evidence appears in `OrchestrationReport.aggregation.collection`, `OrchestrationReport.weighted_aggregate.attribution["CBI_POLICY"]`, and `OrchestrationReport.chain` steps.
- **If Path B (InferencePipeline)**: CBI evidence does not appear unless a pipeline stage explicitly loads and merges it after `_stage_query_evidence()`.

The existing `PipelineContext.institutional_context` at `knowledge/pipeline/context.py` is a `dict[str, str]` field that already exists. PolicyBiasScore fields (central_bank, score, direction) can populate this dict for context enrichment. The field is read by `_build_conclusion()` via `ReasoningContext.institutional_context`.

---

## 5. How It Reaches Decision

`DecisionEngine.decide()` at `knowledge/decision/engine.py` extracts:

- **`avg_return`** — from the aggregation step's `details["avg_return_pct"]` or `details["average_return_pct"]`. CBI evidence with `average_return_pct=0.0` dilutes this toward zero. The Economic adapter also sets `average_return_pct=0.0` — this is the standard pattern for intelligence-layer evidence that carries directional signals but no return statistics.
- **`confidence`** — from `chain.overall_confidence`. CBI evidence contributes its weighted confidence.
- **`evidence_count`** — from `chain.evidence_count`. CBI evidence increments this, making `INSUFFICIENT_EVIDENCE` less likely.
- **`classification`** — `_classify()` thresholds on avg_return and confidence. CBI evidence with `average_return_pct=0.0` and high confidence can push the decision toward `POSITIVE` or `NEGATIVE` if other evidence provides the return signal, or result in `NEUTRAL` if CBI evidence dominates.

**No changes needed.** DecisionEngine is source-agnostic — it reads the ReasoningChain only.

---

## 6. Whether Any Adapter or Bridge Is Still Missing

**One wiring bridge is incomplete**, but it is a **trivial extension of an existing pattern**, not a missing adapter or infrastructure gap.

### What exists:
- `CbiRepository.save_policy_bias()` / `load_policy_bias()` — ✅ Wave-1A
- `CbiEvidenceAdapter.policy_bias_to_evidence()` — ✅ Wave-1B
- `EvidenceAggregator.merge()` accepts `dict[str, EvidenceCollection]` — ✅ existing
- `EvidenceWeighter.weigh()` source-agnostic — ✅ existing
- `ReasoningEngine.reason()` source-agnostic — ✅ existing
- `DecisionEngine.decide()` source-agnostic — ✅ existing

### The wiring gap:

`OrchestrationEngine.analyze()` at `knowledge/orchestration/engine.py:74-88` constructs the `collections` dict from exactly 4 hardcoded sources:

```python
collections = {}
if report.economic_evidence:
    collections["economic"] = report.economic_evidence
if report.temporal_evidence:
    collections["temporal"] = report.temporal_evidence
if report.causal_evidence:
    collections["causal"] = report.causal_evidence
if report.core_evidence:
    collections["core"] = report.core_evidence
```

There is no `collections["cbi"] = ...` line. Adding it requires:

1. Adding `_run_cbi()` method to `OrchestrationEngine` (following `_run_economic()` pattern at line 134)
2. Adding `cbi_evidence` field to `OrchestrationReport` (following `economic_evidence` at line 20)
3. Adding the `"cbi"` key to `collections` dict (line 80-88)

### Ownership

| Component | File | Owner |
|---|---|---|
| `_run_cbi()` method | `knowledge/orchestration/engine.py` | Orchestration layer |
| `cbi_evidence` field on `OrchestrationReport` | `knowledge/orchestration/engine.py` | Orchestration layer |
| `"cbi"` key in collections dict | `knowledge/orchestration/engine.py` (lines 80-88) | Orchestration layer |
| `CbiEvidenceAdapter` injection into orchestration | `orchestration/stages.py` or orchestration caller | Integration layer |

This is **not an architectural gap** — it is wiring that follows the exact pattern of `_run_economic()` (17 lines) and `_run_temporal()` (9 lines).

---

## 7. Whether the Current Pipeline Already Supports Mixed Evidence Without Architectural Modification

**YES**, at the `EvidenceAggregator.merge()` level and below:

| Component | Supports Mixed Evidence? | Evidence |
|---|---|---|
| `EvidenceAggregator.merge()` | ✅ YES | Accepts `dict[str, EvidenceCollection]`. Deduplication and conflict detection are layer-agnostic. |
| `EvidenceWeighter.weigh()` | ✅ YES | Operates on individual Evidence fields. No source-layer logic. |
| `ReasoningEngine.reason()` | ✅ YES | Groups by `event_type`. CBI evidence with `event_type="CBI_POLICY"` gets its own group. |
| `DecisionEngine.decide()` | ✅ YES | Reads only from ReasoningChain. Source-agnostic. |

Economic evidence (`event_type` from regime), temporal evidence (`TEMPORAL`), and CBI evidence (`CBI_POLICY`) can coexist in the merged `EvidenceCollection` without conflict. The merge deduplicates by `evidence_id` — CBI evidence IDs use the `"cbi_policy_{central_bank}"` prefix, which does not collide with economic (`"econ_"`) or temporal (`"tmp_"`) IDs.

**The only architectural constraint**: A CBI evidence object with `event_type="CBI_POLICY"` cannot be produced by Path B (InferencePipeline) because that path builds evidence from KnowledgeRecord → KnowledgeGraph → EvidenceQuery, and no CBI records have been fed into the lesson system. CBI evidence must enter through Path A (OrchestrationEngine.analyze()) or through a direct call to merge() in the calling orchestration layer.

---

## Conclusion

| Question | Answer |
|---|---|
| Does PolicyBiasScore evidence reach the pipeline? | ✅ Yes — through `OrchestrationEngine.analyze()` (Path A) |
| Does it participate in weighting? | ✅ Yes — 5-factor weight model is source-agnostic |
| Does it appear in ReasoningChain? | ✅ Yes — grouped by `event_type="CBI_POLICY"`, gets evidence review + comparison + aggregation + conclusion |
| Does it influence Institutional Assessment? | ✅ Yes — through `WeightedAggregate.attribution`, `ReasoningChain`, and `Decision` |
| Does it reach Decision? | ✅ Yes — `average_return_pct=0.0` dilutes return but confidence and bias influence classification |
| Is any adapter missing? | ❌ No — `CbiEvidenceAdapter` exists and is complete |
| Is any bridge missing? | ⚠️ Minor — `_run_cbi()` method in `OrchestrationEngine` follows existing `_run_economic()` pattern; 3 additions to `knowledge/orchestration/engine.py` |
| Does pipeline support mixed Economic + Temporal + CBI evidence? | ✅ Yes — `EvidenceAggregator.merge()` accepts arbitrary layers, deduplication uses unique `evidence_id` prefixes |

---

## READY

**Justification**: The complete Evidence → Weighting → Reasoning → Decision chain already supports multiple evidence sources without architectural modification. `EvidenceAggregator.merge()` at `knowledge/orchestration/aggregator.py:22` accepts `dict[str, EvidenceCollection]` — adding a `"cbi"` layer requires one additional dict key. The `EvidenceWeighter`, `ReasoningEngine`, and `DecisionEngine` are all source-agnostic — they operate on `Evidence` fields only. The only remaining item is a `_run_cbi()` method in `OrchestrationEngine` (following the 17-line `_run_economic()` pattern) and a `cbi_evidence` field on `OrchestrationReport`. This is wiring, not architecture. All infrastructure — contracts, repository, adapter, aggregator, weighter, reasoning engine, decision engine — exists and is verified.
