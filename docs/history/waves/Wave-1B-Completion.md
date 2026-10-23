# Wave-1B Completion — CbiEvidenceAdapter

**Date**: 2026-07-26  
**Files created**: 1 (`knowledge/cbi/adapter.py`)  
**Lines of code**: 133  
**Existing files modified**: 1 (`knowledge/cbi/__init__.py` — added import + export)  
**Regression tests**: 142 passed (unchanged)

---

## Deliverable

### `knowledge/cbi/adapter.py` (133 lines)

`CbiEvidenceAdapter` — 5 translation methods, each taking a CBI frozen dataclass and returning `Evidence`:

| Method | Input | Output | event_type | Bias Logic |
|--------|-------|--------|-----------|------------|
| `policy_bias_to_evidence` | `PolicyBiasScore` | `Evidence` | `CBI_POLICY` | tightening→bearish, easing→bullish, neutral→neutral |
| `rate_path_to_evidence` | `RatePathProjection` | `Evidence` | `CBI_RATE_PATH` | neutral |
| `forward_guidance_to_evidence` | `ForwardGuidanceRecord` | `Evidence` | `CBI_GUIDANCE` | neutral |
| `liquidity_to_evidence` | `LiquidityOutlook` | `Evidence` | `CBI_LIQUIDITY` | expanding→bullish, stable→neutral, contracting→bearish |
| `regime_to_evidence` | `GlobalMonetaryRegime` | `Evidence` | `CBI_REGIME` | synchronized_easing→bullish, synchronized_tightening→bearish, divergent→neutral, transition→neutral, emergency→bearish |

---

## Field Mapping Verification

| Constraint | Result | Evidence |
|---|---|---|
| Preserve Provenance unchanged | ✅ | `obj.provenance` → `Evidence.provenance` (direct pass-through, `Provenance \| None`) |
| Preserve Confidence unchanged | ✅ | `obj.confidence` → `Evidence.confidence` (1:1, same 0.0–1.0 scale) |
| Preserve Evidence references unchanged | ✅ | `obj.evidence_references` stored in `Evidence.metadata["evidence_references"]` |
| Preserve Validity information unchanged | ✅ | `valid_from`, `valid_until`, `time_horizon` all stored in `Evidence.metadata` |
| Pure translation layer | ✅ | No repository calls, no pipeline interaction, no side effects |
| No Frozen Core modification | ✅ | Uses only existing `Evidence` constructor — no existing file modified (beyond `__init__.py` export) |
| No infrastructure change | ✅ | `EvidenceAggregator.merge()` accepts the output via `EvidenceCollection` |

---

## Verification Summary

- **10 assertions** covering all 5 adapter methods
- **EvidenceAggregator.merge()** compatibility confirmed (6-item merged collection, 2 layers, 0 conflicts)
- **All 5 repository roundtrips** preserved (regression check)
- **Bias mapping** verified for all 3 policy directions, 3 liquidity classifications, and 3 regime orientations
- **142 regression tests** pass unchanged

---

## Status: Ready for Wave-1C

Wave-1B complete. Next step per Implementation-Wave-1-Readiness.md:

**Wave-1C**: Pipeline integration — populate `PipelineContext.institutional_context` with CBI context and call `EvidenceAggregator.merge()` with CBI-derived evidence from the adapter.
