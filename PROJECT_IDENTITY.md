# AurumAI Project Identity

Status: Historical record. Superseded in authority by
[PROJECT_NORTH_STAR.md](PROJECT_NORTH_STAR.md) (highest engineering authority).
[docs/PROJECT_CONSTITUTION.md](docs/PROJECT_CONSTITUTION.md) governs
constitutional rules. This file is kept as the original CTO decision record;
where it conflicts with PROJECT_NORTH_STAR.md or the constitution, those
documents govern.

## CTO Decision

AurumAI is not a trading bot.

AurumAI is a Market Intelligence Operating System.

Trading execution is only the final downstream result of a system that first
collects data, converts it into knowledge, reasons over market context, and
produces explainable decisions.

## Mission

Build the strongest possible Market Intelligence Engine for gold and macro
markets. The system should explain what it has learned from history before it
recommends any action.

Example target output:

> Found 47 similar historical cases since 1980. Gold rose within one week in
> 81% of them with an average move of 2.4%. When the dollar was in a strong
> uptrend, the success rate dropped to 54%.

## Golden Rule

If a mature open-source project already solves a problem well, AurumAI does not
rebuild it.

AurumAI may:

- integrate it
- build on top of it
- adapt it behind a stable internal interface

AurumAI should only build the connective intelligence that turns data, tools,
and research into explainable market understanding.

## What AurumAI Does Not Rebuild

- Technical indicators such as EMA, RSI, MACD
- Generic backtesting engines
- News APIs
- MT5 wrappers
- Sentiment models such as FinBERT
- RAG frameworks
- Vector databases

## What AurumAI Builds

AurumAI builds the brain between existing components:

1. Data Sources
2. Data Engine
3. Knowledge Engine
4. Brain
5. Reasoning Engine
6. Decision Engine
7. Execution Engine

## Layer Responsibilities

### Data Sources

External providers and mature libraries:

- Yahoo Finance
- FRED
- TradingEconomics
- NewsAPI
- MT5
- AlphaVantage
- Polygon
- Binance
- Reddit
- X

### Data Engine

Collects, cleans, normalizes, validates, and stores data.

It does not analyze or decide.

### Knowledge Engine

Transforms historical data into lessons.

Example:

`CPI event -> gold response -> historical outcome -> lesson`

Thousands of lessons become the knowledge base.

### Brain

Understands relationships, not trade signals.

Example:

Higher rates can pressure gold, but the effect changes when the dollar is weak,
liquidity is stressed, or inflation expectations shift.

### Reasoning Engine

Combines macro, price, news, liquidity, and historical lessons into a confidence
assessment.

### Decision Engine

Produces explainable decisions only after reasoning is complete.

### Execution Engine

The last layer. It may connect to MT5, Binance, or another broker only after
backtesting and paper trading are successful.

## AI Agent Roles

### ChatGPT / Codex

Acts as CTO:

- project management
- architecture
- technical decisions
- code review
- priorities
- protecting project direction

### DeepSeek

Acts as Python Engineer:

- algorithms
- utilities
- mathematical functions
- focused implementation tasks

DeepSeek does not own the full project architecture.

### Kimi

Acts as Research Engineer:

- papers
- GitHub research
- APIs
- books
- articles

### Groq

Acts as Reviewer:

- comparisons
- measurement
- improvement suggestions

## Non-Negotiable Rules

1. Do not build what already exists as a mature open-source solution.
2. Every module must be independent.
3. Every decision must be explainable.
4. No real trading before successful backtesting and paper trading.
5. Every sprint must produce a working artifact.
6. Do not move to the next phase until the current phase passes its gates.
7. Fix root causes, not symptoms.
8. Build for a ten-year system, not a one-day bot.

## Current Strategic Position

AurumAI is in Institutional Readiness. The core intelligence pipeline is
frozen at v1.0, Production Hardening is complete, Lineage is active in
production, and reproducibility is proven (A — Fully deterministic).

The next priority is Out-of-Sample Validation (ADR-0004 Gate 6): prove
measurable predictive value on unseen historical data before adding any
new intelligence capability.

## Related ADRs

- [ADR-0004](docs/adr/ADR-0004-canonical-inference-path.md) — Canonical
  Intelligence Inference Path. Defines the `InferencePipeline` as the canonical
  entry point and establishes stabilization gates for the current Intelligence
  Core.
