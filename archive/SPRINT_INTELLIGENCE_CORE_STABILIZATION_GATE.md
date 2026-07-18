# Sprint: Intelligence Core Stabilization Gate

Status: In Progress

Start date: 2026-07-16

Authority: `docs/PROJECT_CONSTITUTION.md` and
`docs/adr/ADR-0004-canonical-inference-path.md`.

## Objective

Turn the working Intelligence Core into one semantically correct, traceable,
versioned, and reproducible canonical path before expanding macro context.

## Scope

### Gate 1 — Canonical architecture

- [x] Adopt `InferencePipeline` as the canonical intelligence path.
- [x] Classify `EconomicBrain` and rule fallback as legacy compatibility code.
- [x] Keep current package locations during stabilization.

### Gate 2 — Evidence and decision integrity

- [ ] Filter evidence by event type, condition, and requested horizon.
- [ ] Configure and enforce a minimum evidence-item count.
- [ ] Emit `INSUFFICIENT_EVIDENCE` when evidence is absent or below threshold.
- [ ] Keep true neutral evidence distinct from missing evidence.
- [ ] Validate the optional `compare_context` stage in the correct order.
- [ ] Cover all semantics with deterministic tests.

### Gate 3 — Lineage and immutable artifacts

- [ ] Add source lesson IDs to every knowledge record.
- [ ] Add source artifact paths and SHA-256 checksums.
- [ ] Write lessons and knowledge atomically.
- [ ] Preserve immutable content-addressed versions without breaking current
      compatibility paths.
- [ ] Prove lineage and versioning behavior with deterministic tests.

### Gate 4 — Real-history CPI/US10Y evaluation

- [ ] Use only local repository datasets; no live network dependency.
- [ ] Use expanding-window, chronological evaluation with no future leakage.
- [ ] Compare CPI-only and CPI+US10Y evidence on held-out events.
- [ ] Report directional accuracy, coverage, sample fragmentation, and
      confidence behavior.
- [ ] Record an Accept / Conditional / Reject decision for US10Y.

### Gate 5 — Clean execution and quality

- [ ] Make the documented pytest command reliable without a repository-local
      locked temp directory.
- [ ] Remove runtime path modification from the canonical entry point.
- [ ] Add CI for the supported Python version and the full test suite.
- [ ] Keep all existing tests passing and add regression tests for the gates.

## Out of scope

- DXY and new macro factors.
- Agents and execution.
- Backtesting and paper trading.
- Graph-backend migration.
- Broad package relocation or deletion of legacy functionality.

## Definition of done

The sprint is complete only when every gate above is checked, the full test
suite passes through the documented command, real-history evaluation artifacts
are reproducible, and an independent review finds no conflict with the project
constitution.
