# Wave-1G: Pipeline Activation — Complete

**Date:** 2026-07-26
**Status:** ACTIVATED

## Summary

Central Bank Intelligence is now wired into the `OrchestrationEngine` as a first-class evidence department, following the same `_run_layer()` pattern as Economic, Temporal, Causal, and Core.

## Changes (2 files, +43 lines)

### `src/knowledge/orchestration/context.py` (+11 lines)
- Import: `PolicyBiasScore`, `ForwardGuidanceRecord`, `RatePathProjection` from `knowledge.cbi.contracts`
- Import: `CbiEvidenceAdapter` from `knowledge.cbi.adapter`
- New fields: `cbi_bias_scores`, `cbi_guidance_records`, `cbi_rate_paths`, `cbi_adapter`

### `src/knowledge/orchestration/engine.py` (+32 lines)
- Import: `CbiEvidenceAdapter` from `knowledge.cbi.adapter`
- Report field: `cbi_evidence: EvidenceCollection` on `OrchestrationReport`
- Wiring in `analyze()`: `report.cbi_evidence = self._run_cbi(ctx)` + `collections["cbi"]`
- New method: `_run_cbi(self, ctx) -> EvidenceCollection` — translates all three CBI object types through `CbiEvidenceAdapter`, tags with `_source_layer: "cbi"`

## Test Results

```
243 passed in 2.19s
```

### Breakdown
| Suite | Tests |
|-------|-------|
| `test_cbi_policy_bias.py` | 25 |
| `test_cbi_forward_guidance.py` | 30 |
| `test_cbi_rate_path.py` | 27 |
| Regression (compat, integrity, economic, orchestration) | 161 |
| **Total** | **243** |

## Evidence Adapter Architecture

All five CBI→Evidence translation methods are unchanged:
- `policy_bias_to_evidence()` — PolicyBiasScore → Evidence (event_type=CBI_POLICY)
- `forward_guidance_to_evidence()` — ForwardGuidanceRecord → Evidence (event_type=CBI_GUIDANCE)
- `rate_path_to_evidence()` — RatePathProjection → Evidence (event_type=CBI_RATE_PATH)
- `liquidity_to_evidence()` — stub (Future)
- `regime_to_evidence()` — stub (Future)

## End-to-End Flow

```
OrchestrationEngine.analyze(ctx)
  └─ ctx.cbi_bias_scores ──→ _run_cbi() ──→ CbiEvidenceAdapter ──→ Evidence[] ──→ cbi_evidence
  └─ ctx.cbi_guidance_records ─┘                         ↑                          ↓
  └─ ctx.cbi_rate_paths ───────┘                    Pure translation          collections["cbi"]
                                                                                    ↓
                                                                          EvidenceAggregator.merge()
                                                                                    ↓
                                                                          WeightedAggregate
```

## Files Touched (cumulative since Wave-1A)

| File | Lines |
|------|-------|
| `knowledge/cbi/__init__.py` | 106 |
| `knowledge/cbi/contracts.py` | 130 |
| `knowledge/cbi/repository.py` | 210 |
| `knowledge/cbi/adapter.py` | 205 |
| `tests/test_cbi_policy_bias.py` | 500 |
| `tests/test_cbi_forward_guidance.py` | 640 |
| `tests/test_cbi_rate_path.py` | 572 |
| `knowledge/orchestration/context.py` | +11 |
| `knowledge/orchestration/engine.py` | +32 |
| **Total CBI** | **~2406** |

## Next

Wave-2 would extend to LiquidityIndicator and MonetaryRegime objects, plus their translation methods in CbiEvidenceAdapter.
