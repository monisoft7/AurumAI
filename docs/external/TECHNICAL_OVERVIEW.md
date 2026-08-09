# AurumAI — Technical Overview

## Product

AurumAI is an institutional financial-intelligence platform. Its intended output is an explainable investment assessment derived from historical and current evidence.

## Canonical path

```text
Raw Data → Events → Feature Extraction → Lessons → Knowledge Records
→ Knowledge Graph → Evidence Retrieval/Ranking → Reasoning → Decision
→ Institutional Assessment → Paper Execution → Live Adapter (future)
```

## Architectural properties

- **Deterministic:** same inputs are intended to produce the same outputs.
- **Explainable:** decisions are traceable through Source Data → Lessons → Knowledge → Evidence → Reasoning → Decision.
- **Versioned / traceable:** provenance and lineage components preserve source-to-decision relationships.
- **Frozen core:** inference, reasoning, decision, evidence, knowledge-graph contracts, and core entity contracts are protected from unnecessary redesign.

## Recorded capabilities

Project documentation records macro-event processing, feature extraction, knowledge aggregation, NetworkX graph construction, evidence retrieval, reasoning, decision, economic/temporal/causal intelligence, forecasting, risk intelligence, paper execution, lineage activation, chronological OOS infrastructure, institutional experiments, and an experiment registry.

## Critical distinction

Implemented infrastructure does not by itself prove predictive value. Institutional readiness requires empirical validation on unseen historical data and operational evidence integrity.
