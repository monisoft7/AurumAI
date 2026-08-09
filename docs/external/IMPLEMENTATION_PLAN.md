# AurumAI — Funding Preparation Implementation Plan

## A — Documentation

Create and maintain this package on `funding-preparation`. No core code changes are required for the funding-preparation package itself.

## B — Evidence cleanup

Before final external submission:

1. reconcile historical test-count discrepancies;
2. reconcile old/new phase labels;
3. distinguish OOS infrastructure from demonstrated predictive value;
4. label superseded snapshots;
5. make every external metric reference a dated reproducible artifact.

These activities improve the credibility and reproducibility of the external package without changing the core architecture.

## C — Validation correction

Address only the decision-material Knowledge → Evidence finding identified by Operational Validation Run 002.

First establish the exact causal boundary from runtime evidence. Then apply the smallest correct fix. No broad architectural redesign is implied.

## D — Targeted validation

After the correction, verify:

- KnowledgeRecord identity;
- evidence producer;
- `source_kr_id` lineage;
- evidence-class compatibility;
- duplicate handling;
- downstream thesis contribution;
- deterministic reproducibility.

The acceptance criterion is an artifact-backed validation result, not an architectural claim.

## E — Institutional validation package

Produce a dated validation package containing:

- source commit;
- data snapshot;
- execution command;
- environment information;
- test results;
- OOS metrics;
- experiment IDs;
- validation artifacts;
- limitations;
- unresolved findings.

This package establishes the evidence required to evaluate institutional release readiness.

## F — External funding package

The external funding package may be presented during active validation. It does not require C/D to be completed first.

Its purpose is to explain:

- what AurumAI already contains;
- what remains unvalidated;
- why external API/compute/data funding is required;
- what funded work packages will be executed;
- what measurable acceptance criteria will determine success.

The final institutional release package is separate and will only be produced after the relevant validation findings have been resolved and independently reproducible evidence has been recorded.

Funding preparation is not live-trading preparation.
