# AurumAI

AurumAI is a Market Intelligence Operating System for gold and macro markets.

It is not a trading bot. Its goal is to collect market and economic data,
convert that data into historical lessons, reason over current context, and only
then produce explainable decisions.

The project builds the connective intelligence between mature open-source tools
instead of rebuilding indicators, backtesters, news APIs, broker wrappers,
sentiment models, RAG frameworks, or vector databases.

Current stage: Intelligence Core stabilization.

Current working pipeline:

1. Build CPI/gold lessons.
2. Aggregate lessons into knowledge records.
3. Build a NetworkX knowledge graph.
4. Query evidence from the graph.
5. Build an explainable reasoning chain.
6. Produce an advisory, evidence-backed decision.

The pipeline can optionally enrich lessons with US10Y yield context before
knowledge aggregation, enabling multi-factor records such as CPI pressure plus
yield trend.

The inference pipeline can persist a context comparison report that compares
single-factor knowledge against context-conditioned knowledge before the project
accepts more macro context.

```powershell
py -3 -m pytest -q
```

See [docs/PROJECT_CONSTITUTION.md](docs/PROJECT_CONSTITUTION.md) for the
operating doctrine. [PROJECT_IDENTITY.md](PROJECT_IDENTITY.md) remains as a
historical CTO decision record and defers to the constitution wherever the
two differ.

The full test suite is configured to use a repository-local pytest temp
directory so it remains runnable on locked-down Windows environments.
