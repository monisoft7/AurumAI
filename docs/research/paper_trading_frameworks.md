# Phase 21 — Paper Trading Research Report

**Date:** 2026-07-19
**Scope:** Evaluate mature open-source paper trading / backtesting frameworks, then propose AurumAI's minimal Paper Trading architecture.

---

## 1. Evaluation Summary

### Framework Comparison Matrix

| Criterion | Backtrader | VectorBT (OS) | Zipline-Reloaded | Nautilus Trader | QuantConnect LEAN |
|----------|-----------|--------------|-----------------|----------------|-------------------|
| **License** | GPL-3.0 | Apache 2.0 + Commons Clause | Apache 2.0 | LGPL-3.0 | Apache 2.0 |
| **Language** | Python | Python (+Numba/Rust) | Python (+Cython) | Rust core, Python API | C# core, Python API |
| **GitHub Stars** | ~22,400 | ~5,500 | ~4,200 | ~7,000 | ~20,500 |
| **Maintenance (2026)** | Stagnant (last meaningful release ~2021; unofficial forks active) | OS stalled at v0.28.1; PRO is active (paid, ~$150/mo) | Community-maintained; active as of 3.1.1 (Jul 2025) | Very active; nightly releases; 16k+ commits in 2026 | Very active; 13k+ commits; QuantConnect-backed |
| **Architecture** | Event-driven (single-threaded) | Vectorized (array-based) | Event-driven | Event-driven (async Rust) | Event-driven (C# async) |
| **Backtest Speed** | Slow (850 tests/hr) | Very fast (2,400 tests/hr) | Medium (620 tests/hr) | Fast (Rust core) | Medium |
| **Paper Trading** | Yes (limited brokers) | No (OS); Yes (PRO) | No | Yes (native + adapters) | Yes (native + cloud) |
| **Live Trading** | Yes (IB, Oanda, VC) | No (OS); Yes (PRO) | No | Yes (10+ venues) | Yes (10+ brokers) |
| **Determinism** | Moderate (manual bias prevention) | Low (vectorized path-dependent) | High (point-in-time data model) | Very high (DST framework, event-sourced) | High |
| **Look-ahead Bias Prevention** | Manual only | None built-in | Pipeline enforces point-in-time | DST guarantees correctness | Pipeline enforces point-in-time |
| **Slippage/Commission** | Customizable | Basic | Advanced models | Advanced models | Advanced models |
| **Portfolio Stats** | Built-in (analyzers) | Built-in (comprehensive) | Pyfolio integration | Comprehensive | Comprehensive |
| **Learning Curve** | Medium | Easy/Medium | Hard | Hard | Medium/Hard |
| **Ease of Integration** | Medium (heavy OOP) | Easy (pandas native) | Hard (bundle system) | Hard (Rust dep, complex API) | Medium (Docker, CLI) |

---

## 2. Individual Candidate Reports

### 2.1 Backtrader

| Dimension | Assessment |
|-----------|-----------|
| **License** | GPL-3.0 (strong copyleft — incompatible with AurumAI's Apache-2.0-friendly ecosystem) |
| **Maturity** | Very mature (2015–2021). 22k+ stars, 5k+ forks, large ecosystem of indicators and samples. |
| **Community** | Largest Python backtesting community. Extensive tutorials, books, forum posts. |
| **Maintenance** | **Dead.** Original author (mementum) stopped meaningful development after 2021. Unofficial forks (cloudQuant, cschrupp_2026) exist but no canonical replacement. |
| **Performance** | Single-threaded event loop. ~850 backtests/hr on modern hardware. Bottleneck on large datasets. |
| **Determinism** | Seeds are controllable but look-ahead bias must be manually prevented. No built-in guards. |
| **Integration** | Heavy OOP — requires subclassing `bt.Strategy`, overriding `next()`, using Cerebro engine. Difficult to adapt to AurumAI's `InstitutionalAssessment`-driven architecture. GPL-3.0 license is a blocker. |
| **Reuse candidate** | Slippage/commission models, trade recording, `Trade`/`Position` data structures. |
| **Do NOT reuse** | The entire event-driven strategy execution loop. The GPL-3.0 license. The monolithic architecture. |

### 2.2 VectorBT (Open Source)

| Dimension | Assessment |
|-----------|-----------|
| **License** | Apache 2.0 with Commons Clause (OS). PRO is proprietary (~$150/mo). The Commons Clause restricts commercial resale — acceptable for AurumAI's internal use. |
| **Maturity** | Very mature (2019–2024). v0.28.1 is the final OS release. |
| **Community** | Large following. PRO has 1,000+ private Discord members. |
| **Maintenance** | **OS is dead.** Author (polakowo) moved active development to PRO entirely. No updates for Python 3.13+ compatibility. PRO is actively maintained but proprietary. |
| **Performance** | **Fastest of all candidates.** Vectorized + Numba + optional Rust backend. 2,400+ tests/hr. Ideal for parameter sweeps. |
| **Determinism** | Weak. Vectorized approach makes path-dependent simulations (e.g., trailing stops) inherently less deterministic. |
| **Integration** | Excellent for pandas-native workflows. Operates on arrays, not event streams. Poor fit for AurumAI's event-driven `InstitutionalAssessment` input. |
| **Reuse candidate** | Portfolio metrics computation (Sharpe, drawdown, etc.). Array-based PnL calculation. |
| **Do NOT reuse** | Event-loop simulation (vectorized doesn't match AurumAI's assessment-driven model). The order execution engine relies on vectorized assumptions. |

### 2.3 Zipline-Reloaded

| Dimension | Assessment |
|-----------|-----------|
| **License** | Apache 2.0 (fully compatible) |
| **Maturity** | Mature (Quantopian heritage, 2012–present). Actively forked and maintained by Stefan Jansen. |
| **Community** | Moderate. ML4Trading book and Discourse community. |
| **Maintenance** | **Sustainable.** v3.1.1 (Jul 2025). Compatible with pandas 2.2+, numpy 2.0. CI passing. |
| **Performance** | Medium. Event-driven Python with some Cython optimization. 620 tests/hr. |
| **Determinism** | High. Pipeline API enforces point-in-time data access. Bundle system prevents look-ahead bias. |
| **Integration** | Hard. Bundle-based data ingestion requires custom ingest functions for non-US-equity data. No live trading support. |
| **Reuse candidate** | Pipeline API's point-in-time data model design pattern. Pyfolio integration for performance reporting. |
| **Do NOT reuse** | The bundle system (too US-equity-centric). The strategy class hierarchy. Lack of live/paper trading means it only covers half the requirement. |

### 2.4 Nautilus Trader

| Dimension | Assessment |
|-----------|-----------|
| **License** | **LGPL-3.0** (weaker copyleft; allows linking from proprietary code. Acceptable for AurumAI.) |
| **Maturity** | Very high. 10+ years of development. Production-grade. |
| **Community** | Active Discord. 7k+ stars. Nautech Systems corporate backing. |
| **Maintenance** | **Extremely active.** Nightly releases. 16k+ commits on develop branch. Python 3.12–3.14 support. |
| **Performance** | **Best-in-class.** Rust core (tokio async), Python control plane. Deterministic Simulation Testing (DST) framework. |
| **Determinism** | **Best-in-class.** DST drives thousands of seeds through execution-path combinations. Event-sourced recording with nanosecond timestamps. Reproducible replay. |
| **Integration** | Hard. Rust toolchain requirement. Complex adapter system. Overwhelming for a lightweight paper trading requirement. |
| **Reuse candidate** | **DST concept** (deterministic simulation with replay). **Event-sourced architecture** pattern. Commission/slippage model design. |
| **Do NOT reuse** | The full engine. AurumAI does NOT need a multi-venue, HFT-capable execution platform. The complexity would violate the "minimum viable" principle. The Rust dependency adds unacceptable build complexity. |

### 2.5 QuantConnect LEAN

| Dimension | Assessment |
|-----------|-----------|
| **License** | Apache 2.0 (fully compatible) |
| **Maturity** | Very high. Founded 2011. 250k+ quant community. $45B monthly notional. |
| **Community** | Largest ecosystem (cloud IDE, forum, 1,200+ shared algorithms). |
| **Maintenance** | **Extremely active.** QuantConnect corporate backing. 180+ contributing engineers. |
| **Performance** | Medium. C# core with Python.NET bridge. Performance is adequate for daily/minute strategies. |
| **Determinism** | High. Point-in-time data model. Pipeline API prevents look-ahead bias. |
| **Integration** | Medium. Requires LEAN CLI or Docker for local operation. Python/C# dual-language adds complexity. The strategy API is tightly coupled to LEAN's data model. |
| **Reuse candidate** | **Paper trading broker adapter** concept. Slippage/commission models. Portfolio statistics reporting. |
| **Do NOT reuse** | The full engine — too heavy for AurumAI. The C# dependency is an unacceptable architectural constraint. The strategy loop cannot accept `InstitutionalAssessment` as input. |

---

## 3. AurumAI Paper Trading Architecture Proposal

### 3.1 Design Constraints (from Project Constitution)

| Constraint | Source |
|-----------|--------|
| Consume `InstitutionalAssessment` only | Phase 21 requirements |
| Never bypass `DecisionEngine` | Constitution §5.3 |
| Never bypass `DecisionGate` | Constitution §4.4 |
| No forecasting, no reasoning, no Risk/Forecast duplication | Phase 21 requirements |
| Execution is the **last and most heavily gated layer** | Constitution §3.4, §5.4 |
| Backtesting AND paper trading must pass before live trading | Constitution §5.4 |
| Build → no mature OSS solves this exact need | Constitution §5.1 (verified below) |
| Zero new runtime dependencies if possible | Phase 20.5 precedent |
| Must be deterministic, explainable, testable | Constitution §4.1, §4.6 |

### 3.2 Why Not Reuse a Full Framework

Every evaluated framework is a **strategy execution engine** — it takes price data and a strategy function, simulates orders through time, and produces PnL. AurumAI does **not** produce price-based trading signals. It produces `InstitutionalAssessment` objects containing:

- A `Decision` from `DecisionEngine` (already gated by `DecisionGate`)
- Supporting evidence, reasoning chains, forecast context, risk metrics
- Confidence bounds, regime classifications, validation reports

The framework needs to **judge** these assessments, not execute a price-driven strategy. A paper trading system that receives `InstitutionalAssessment` as input and manages a virtual portfolio is **fundamentally different** from a backtester that receives price bars and a strategy function. No evaluated framework supports this input model.

Therefore, AurumAI must **Build** a thin `PaperTradingEngine` layer, while **Adapting** specific sub-components from the evaluated frameworks.

### 3.3 Recommended Architecture (Build → Reuse → Adapt)

```
InstitutionalAssessment  ◄── from InstitutionalOrchestrator.run_all()
        │
        ▼
┌─────────────────────────────────────────┐
│  PaperTradingEngine                     │  BUILD (~250 lines)
│                                         │
│  - receives InstitutionalAssessment     │
│  - evaluates Decision + RiskDecision    │
│  - determines action (NONE / BUY /      │
│    SELL / HOLD / ADJUST)                │
│  - updates VirtualPortfolio             │
│  - records to TradeLog                  │
└──────────┬──────────────────────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
┌─────────┐ ┌──────────┐
│  Virtual │ │  Trade   │
│Portfolio│ │   Log    │
├─────────┤ ├──────────┤
│ cash    │ │ timestamp│
│ posns   │ │ action   │
│ equity  │ │ asset    │
│ curve   │ │ qty      │
│ PnL     │ │ price    │
└─────────┘ │ slippage │
            │ commission│
            │ decision_id│
            └──────────┘
```

#### Module: `PaperTradingEngine`  (BUILD)

- **Input:** `InstitutionalAssessment` (containing `Decision`, `RiskDecision`, confidence, forecast, risk metrics)
- **Output:** `PaperTradingReport` (equity curve, trade log, portfolio stats, PnL breakdown)
- **Responsibility:** Gate, translate, execute, record
- **Pure Python** — zero new runtime dependencies
- **No price data ingestion** — price feed is a simple dict or DataFrame input, not a real-time stream

#### Sub-component: `VirtualPortfolio`  (REUSE design patterns)

| Concept | Source | Adaptation |
|---------|--------|------------|
| Position tracking | Backtrader `Position` | Strip to asset ID, qty, cost basis, market value |
| Cash/equity tracking | All frameworks | Standard accounting: cash + market value = equity |
| Equity curve | VectorBT portfolio metrics | Simple pandas Series of daily equity |
| PnL calculation | All frameworks | Realized + unrealized PnL per position |
| **Do NOT reuse** | | Trade management lifecycle, order routing, fill simulation |

#### Sub-component: `SlippageModel`  (ADAPT)

| Component | Source | Adaptation |
|-----------|--------|------------|
| Fixed slippage | All frameworks | `slippage_bps = 1` (1bp default) |
| Percentage slippage | Backtrader `CommissionInfo` | `slippage_pct = 0.001` (0.1%) |
| Volume-aware slippage | LEAN `SlippageModel` | Optional: `slippage = spread + (qty / volume) * impact` |
| **Do NOT reuse** | | Market impact models, order book simulation, fill probability |

#### Sub-component: `CommissionModel`  (ADAPT)

| Component | Source | Adaptation |
|-----------|--------|------------|
| Fixed per-trade | Backtrader `CommissionInfo` | `commission_per_trade = 0` (default) |
| Percentage per-side | All frameworks | `commission_pct = 0.001` (10bps) |
| Tiered commission | LEAN `FeeModel` | Optional: volume-based tiers |
| **Do NOT reuse** | | Broker-specific fee schedules, rebate models, regulatory fees |

#### Sub-component: `PortfolioStatistics`  (REUSE from VectorBT metrics)

| Metric | Source | Notes |
|--------|--------|-------|
| Total return | All | `(final_equity - initial_capital) / initial_capital` |
| Annualized return | All | `(1 + total_return)^(252 / n_days) - 1` |
| Volatility (annualized) | All | `std(daily_returns) * sqrt(252)` |
| Sharpe ratio | VectorBT | `(mean_return - rf) / std_return` |
| Max drawdown | All | `max(1 - equity / running_max)` |
| Calmar ratio | VectorBT | `annualized_return / max_drawdown` |
| Win rate | All | `wins / total_trades` |
| Profit factor | All | `gross_profit / gross_loss` |
| **Do NOT reuse** | | Walk-forward analysis, parameter optimization, factor decomposition |

### 3.4 Paper Trading Engine — Gate Logic

```
For each InstitutionalAssessment:
  1. Extract Decision from assessment.outputs["decision"]
  2. Extract RiskDecision from assessment.outputs["risk_decision"]
  3. Evaluate Gate:
     a. If RiskDecision.action == "halt" → NO TRADE (log reason)
     b. If RiskDecision.action == "delay" → DEFER (log reason)
     c. If Decision is None → NO TRADE (no signal)
  4. Determine position adjustment:
     a. Decision = STRONG_POSITIVE / POSITIVE → INCREASE or ENTER LONG
     b. Decision = STRONG_NEGATIVE / NEGATIVE → DECREASE or ENTER SHORT
     c. Decision = NEUTRAL → HOLD or REDUCE (trailing stop)
  5. Apply SlippageModel → adjust execution price
  6. Apply CommissionModel → deduct cost
  7. Update VirtualPortfolio:
     a. Deduct cash for buys, add cash for sells
     b. Update position quantities and cost basis
     c. Recalculate equity curve
  8. Record to TradeLog:
     timestamp, action, asset, qty, price, slippage, commission, decision_id
```

### 3.5 Output: `PaperTradingReport`

```python
@dataclass(frozen=True)
class PaperTradingReport:
    pipeline_id: str
    initial_capital: float
    final_equity: float
    total_return: float
    annualized_return: float | None
    volatility: float | None
    sharpe: float | None
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    trade_log: tuple[TradeRecord, ...]
    equity_curve: tuple[EquityPoint, ...]
```

### 3.6 Dependencies

| Package | Rationale | Status |
|---------|-----------|--------|
| `pandas` | Already a project dep; used for equity curve DataFrame | Already installed |
| `numpy` | Already a project dep; used for PnL array ops | Already installed |

**Zero new runtime dependencies.**

---

## 4. Implementation Roadmap (Priority Order)

| Priority | Module | Approach | Lines | Depends On |
|----------|--------|----------|-------|------------|
| **P0** | `PaperTradingEngine` (core loop + gate logic) | **Build** | ~120 | `InstitutionalAssessment` (exists) |
| **P1** | `VirtualPortfolio` (cash, positions, equity) | **Build** | ~80 | P0 |
| **P2** | `PortfolioStatistics` (Sharpe, drawdown, etc.) | **Adapt** from VectorBT metrics | ~60 | P1 |
| **P3** | `SlippageModel` | **Adapt** from Backtrader/LEAN | ~40 | P0 |
| **P4** | `CommissionModel` | **Adapt** from Backtrader/LEAN | ~30 | P0 |
| **P5** | `TradeLog` (record + export) | **Build** | ~50 | P0 |
| **P6** | `PaperTradingReport` serialization | **Build** | ~20 | P0–P5 |
| **P7** | Integration with `InstitutionalOrchestrator` | **Build** | ~30 | P0–P6 |
| **P8** | Tests (determinism, scenarios, edge cases) | **Build** | ~150 | P0–P7 |
| **Total** | | | **~580** | |

### Total Code: ~580 lines (pure Python)
### New Dependencies: **Zero**
### Files Touched: `src/execution/paper_trading.py` (new dir), `src/execution/__init__.py`

---

## 5. Decision Summary

| Candidate | Verdict | Rationale |
|-----------|---------|-----------|
| **Backtrader** | Do NOT reuse | GPL-3.0 blocker. Dead maintenance. Heavy OOP incompatible with assessment-driven model. |
| **VectorBT** | Do NOT reuse OS | OS is dead. PRO is proprietary. Vectorized model mismatches event-driven assessment input. |
| **Zipline-Reloaded** | Do NOT reuse | No paper/live trading. Bundle system too US-equity-centric. |
| **Nautilus Trader** | Do NOT reuse engine | Too heavy for this use case. Rust dep adds unacceptable build complexity. Adapt DST concept only. |
| **QuantConnect LEAN** | Do NOT reuse engine | C# dependency. Too heavy. Strategy loop incompatible with `InstitutionalAssessment` input. |
| **AurumAI Build** | **Recommended** | Minimum viable paper trading engine consuming `InstitutionalAssessment`. ~580 lines, zero new deps. Adapt sub-components from multiple frameworks. |
