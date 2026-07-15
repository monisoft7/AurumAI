# AurumAI

AurumAI is a Market Intelligence Operating System for gold and macro markets.

It is not a trading bot. Its goal is to collect market and economic data,
convert that data into historical lessons, reason over current context, and only
then produce explainable decisions.

The project builds the connective intelligence between mature open-source tools
instead of rebuilding indicators, backtesters, news APIs, broker wrappers,
sentiment models, RAG frameworks, or vector databases.

Current stage: Data Engine stabilization and Knowledge Engine start.

Current working pipeline:

1. Build CPI/gold lessons.
2. Aggregate lessons into knowledge records.
3. Ingest knowledge into memory.
4. Query the Brain for evidence-backed market understanding.

```powershell
py -3 src\teacher\build_lessons.py
py -3 src\knowledge\build_knowledge.py
py -3 src\knowledge\brain.py
py -3 -m pytest -q
```

See [PROJECT_IDENTITY.md](PROJECT_IDENTITY.md) for the operating doctrine.
