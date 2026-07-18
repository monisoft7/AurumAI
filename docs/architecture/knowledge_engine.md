# Knowledge Engine

Status: Active — Intelligence Core Stabilization

## Canonical flow

Economic events + asset history + optional macro context

↓

Feature extraction

↓

Immutable, versioned lessons

↓

Knowledge records with source-lesson lineage

↓

Knowledge graph

↓

Evidence filtered by event, condition, and horizon

↓

Reasoning chain

↓

Advisory decision or explicit insufficient evidence

`knowledge.pipeline.InferencePipeline` is the canonical entry point for this
flow. See [ADR-0004](../adr/ADR-0004-canonical-inference-path.md) for the full
architectural decision and stabilization gate status.

Architecture principles and layer definitions are governed by the
[Project Constitution](../PROJECT_CONSTITUTION.md), Section 9 (Architecture
Principles) and Section 16 (Feature Extraction Layer).

## Compatibility layer

`EconomicBrain`, flat `Memory`, and `RULES` are legacy compatibility
components. They remain available during migration but do not define new
Intelligence Core behavior and are not evidence sources for the canonical path.

## Current boundaries

Reasoning, decision, and learning remain under `src/knowledge/` during this
stabilization sprint. Their physical relocation is deferred to avoid import
churn. Learning, temporal, economic, and causal primitives are not considered
part of the end-to-end canonical flow until explicitly wired and gated.
