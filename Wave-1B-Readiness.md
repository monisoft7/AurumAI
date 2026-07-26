# Wave-1B Readiness — CbiEvidenceAdapter Architecture Review

**Date**: 2026-07-26  
**Review type**: Architecture comparison against existing adapters  
**Target**: `knowledge/cbi/adapter.py`

---

## 1. Ownership

| Dimension | EconomicEvidenceAdapter | TemporalEvidenceAdapter | CbiEvidenceAdapter (proposed) |
|---|---|---|---|
| File | `knowledge/economics/adapter.py` | `knowledge/temporal/adapter.py` | `knowledge/cbi/adapter.py` |
| Class | `EconomicEvidenceAdapter` | `TemporalEvidenceAdapter` | `CbiEvidenceAdapter` |
| Package | `knowledge.economics` | `knowledge.temporal` | `knowledge.cbi` |
| Source objects | `EconomicRegime`, `EconomicState` | `TemporalState`, `TimePeriod`, `TemporalIndexer` | `PolicyBiasScore`, `RatePathProjection`, `ForwardGuidanceRecord`, `LiquidityOutlook`, `GlobalMonetaryRegime` |

**Consistent**: Every knowledge sub-package owns its adapter. CBI adapter belongs in `knowledge/cbi/adapter.py`.

---

## 2. Inputs

| Adapter | Input type | Frozen? | Package |
|---|---|---|---|
| Economic | `EconomicRegime` | `@dataclass(frozen=True)` | `knowledge.economics.regime` |
| Temporal | `TemporalState`, `TimePeriod` | `@dataclass(frozen=True)` | `knowledge.temporal` |
| CBI | 5 CBI contract types | `@dataclass(frozen=True)` (extends `CbiBaseContract`) | `knowledge.cbi.contracts` |

**Consistent**: All adapters receive pre-constructed frozen dataclasses from their own package.

---

## 3. Outputs

All three adapters output `Evidence` (frozen dataclass from `knowledge.evidence.evidence`, 12 fields + provenance + metadata).

No adapter outputs `KnowledgeRecord`, `EvidenceCollection`, or any other type. `Evidence` is the canonical pipeline entry point.

---

## 4. Evidence Produced — Field-by-Field Comparison

| Evidence field | Economic | Temporal | CBI (proposed) |
|---|---|---|---|
| `evidence_id` | `f"econ_{regime.regime_id}"` | `f"tmp_{state.state_id}"` | `f"cbi_{type}_{central_bank}"` |
| `source_node_id` | `f"econ_regime_{regime.regime_type}"` | `f"temporal_{source_type}_{source_id}"` | `f"cbi_{central_bank}"` |
| `event_type` | `"ECONOMIC"` | `"TEMPORAL"`, `"TEMPORAL_PERIOD"`, `"TEMPORAL_RANGE"` | `"CBI_POLICY"`, `"CBI_RATE_PATH"`, `"CBI_GUIDANCE"`, `"CBI_LIQUIDITY"`, `"CBI_REGIME"` |
| `condition` | `{"regime": regime_type}` | `{"source_type": ..., "date": ...}` | `{"central_bank": ..., "type": ...}` |
| `horizon_days` | `0` | `0` | `0` |
| `sample_count` | `1` | `1` | `1` |
| `average_return_pct` | `0.0` | `0.0` | `0.0` |
| `confidence` | `regime.confidence` | `1.0` | `obj.confidence` |
| `bias` | `"neutral"` | `"neutral"` | Mapped from direction/classification |
| `explanation` | Constructed from regime fields | Constructed from state fields | Constructed from CBI domain fields |
| `provenance` | not set (None) | not set (None) | `obj.provenance` (pass-through, enabled by CBI contracts) |
| `metadata` | regime_id, type, dates, indicators | state_id, date, source, tags | CBI-specific domain fields |

**Key observation**: The CBI adapter maps `bias` directionally (tightening→bearish, easing→bullish) where Economic and Temporal always use `"neutral"`. This is architecturally valid — the `bias` field on `Evidence` is `str` with no enum constraint. CBI is the first department whose knowledge objects inherently carry directional policy signals. EvidenceAggregator.merge() already detects bias conflicts across layers, so directional bias is an intended consumer of this field.

---

## 5. Mapping to KnowledgeRecord

**None of the three adapters produce KnowledgeRecord.**

`KnowledgeRecord` is a historical aggregated statistics object (from the learning engine). It is populated by a separate pipeline path (`LessonBuilder` → `LearningEngine`) and is not a target of the adapter layer.

The CBI adapter follows the same boundary: domain object → Evidence only. KnowledgeRecord population, if ever needed, would be a separate concern.

---

## 6. Mapping to Evidence — Translation Pattern

All three adapters follow the identical construction pattern:

```
1. Construct evidence_id from domain identifiers
2. Set source_node_id to domain path
3. Set event_type to domain-specific constant
4. Extract identifying fields into condition dict
5. Set horizon_days=0, sample_count=1, average_return_pct=0.0 (defaults)
6. Copy confidence directly (0.0–1.0, same scale)
7. Set bias (CBI maps directionally, others use "neutral")
8. Build explanation from domain fields
9. Attach provenance if available (CBI has it, others don't)
10. Pack remaining domain fields into metadata dict
```

The CBI adapter follows steps 1–10 exactly. Step 9 (provenance pass-through) is additive — enabled by the CBI contracts carrying Provenance via CbiBaseContract. Evidence.provenance already exists as `Provenance | None`. No schema modification needed.

---

## 7. Mapping to Provenance

| Adapter | Domain object carries Provenance? | Evidence.provenance set? |
|---|---|---|
| Economic | No (EconomicRegime has no provenance field) | No (None) |
| Temporal | No (TemporalState has no provenance field) | No (None) |
| CBI | **Yes** — CbiBaseContract has `provenance: Provenance \| None` | **Yes** — pass-through (when not None) |

**CBI adapter improvement**: The CBI contracts were designed with provenance from the start (per Section 0.4 of the knowledge contract framework). The adapter passes `obj.provenance` directly to `Evidence.provenance`. This is backward-compatible — Evidence.provenance is `Provenance | None` and `None` is valid when no provenance exists.

---

## 8. Mapping to Institutional Context

**None of the three adapters map to institutional context.**

Institutional context enrichment is handled by `PipelineContext.institutional_context` (existing field, populated by the orchestration layer, not by adapters). The CBI adapter stays within the adapter responsibility boundary.

---

## 9. Repository Interaction

| Adapter | Reads from repository? | Receives pre-built objects? |
|---|---|---|
| Economic | No | Yes — `regime_to_evidence(regime)` receives pre-built EconomicRegime |
| Temporal | No | Yes — methods receive pre-built TemporalState / TimePeriod / TemporalIndexer |
| CBI | No | Yes — methods receive pre-built CBI contract objects |

**Repository interaction is zero in all three adapters.** The caller (orchestration layer) is responsible for loading objects via the repository and passing them to the adapter. This separation of concerns is consistent.

---

## 10. Pipeline Interaction

| Adapter | Calls pipeline? | Registers stages? | Modifies context? |
|---|---|---|---|
| Economic | No | No | No |
| Temporal | No | No | No |
| CBI | No | No | No |

All three adapters are pure translation layers. Pipeline interaction is the orchestration layer's responsibility.

---

## Verification Against Constraints

| Constraint | Verdict | Evidence |
|---|---|---|
| No Frozen Core modification required | YES | Adapter only reads from CBI contracts (new) and creates Evidence (existing frozen). No existing file modified. |
| No new pipeline stage required | YES | EvidenceAggregator.merge() at `knowledge/orchestration/aggregator.py:22` accepts dict[str, EvidenceCollection]. The adapter produces Evidence[] which feeds into this existing merge point. |
| No orchestration change required | YES | The existing `merge(collections)` signature, `AggregationResult` output, and `EvidenceCollection` input all remain unchanged. |
| No adapter-specific special case introduced | YES | The adapter follows the identical static-method-per-domain-object pattern as both existing adapters. The only difference (provenance pass-through) is a previously-unavailable capability enabled by the CBI contracts, not a special case. |

---

## Final Answer

**YES**.

**Architectural justification**: The CbiEvidenceAdapter is a pure translation layer that maps frozen dataclass domain objects (CBI contracts) to frozen dataclass Evidence objects, following the identical pattern established by EconomicEvidenceAdapter (79 lines) and TemporalEvidenceAdapter (128 lines). The mapping is entirely field-to-field with no side effects, no repository calls, no pipeline interaction, and no infrastructure modification. The adapter creates `Evidence` instances using only the existing 12-field constructor, with `provenance` pass-through enabled by the CBI contracts carrying Provenance (a capability the earlier adapters lacked because their domain objects lacked provenance, not because of any architectural limitation). EvidenceAggregator.merge() at `knowledge/orchestration/aggregator.py:22` already accepts the output collection via `dict[str, EvidenceCollection]`. Zero existing files require modification. The adapter is structurally identical to its predecessors.
