# Phase 17 — Risk Intelligence: Research Report

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Candidate Evaluation](#2-candidate-evaluation)
   - 2.1 Risk Parity
   - 2.2 Expected Shortfall (CVaR) & Value at Risk (VaR)
   - 2.3 Kelly Criterion
   - 2.4 Volatility Targeting
   - 2.5 Drawdown Control
   - 2.6 Position Sizing Frameworks
   - 2.7 Black Swan / Tail-Risk Detection
   - 2.8 Regime-Aware Risk Models
3. [Integrated Architecture Proposal](#3-integrated-architecture-proposal)
4. [Implementation Roadmap](#4-implementation-roadmap)
5. [References](#5-references)

---

## 1. Executive Summary

This report evaluates eight categories of risk intelligence methodologies for AurumAI. Each candidate is assessed against the project's core constraints: **determinism, explainability, zero new dependencies (unless justified), and reuse-before-build.**

**Primary finding:** The existing Forecast Intelligence pipeline (Phases 16.1–16.10) provides forecast context, confidence, evidence, and validation — but no mechanism for *actionable risk decisions*. The proposed Risk Intelligence layer fills this gap by answering five questions:

| Question | Risk Component |
|---|---|
| Should we trust the forecast? | **Forecast Integrity** (VaR/CVaR of forecast error) |
| Should we act now? | **Execution Readiness** (volatility regime, positioning) |
| Is the current regime too risky? | **Regime Risk Overlay** |
| Is uncertainty acceptable? | **Uncertainty Budget** (entropic risk, tail detection) |
| Should execution be delayed? | **Drawdown Lock / Decision Gate** |

**No new external dependencies are required.** All computations use numpy, pandas, and math — already in the project. Riskfolio-Lib, cvxportfolio, skfolio, and riskkit are evaluated as *reference implementations* whose algorithms can be adapted deterministically.

---

## 2. Candidate Evaluation

### 2.1 Risk Parity

| Attribute | Assessment |
|---|---|
| **Purpose** | Allocate capital so each asset contributes equal risk to the portfolio. Prevents any single position from dominating total portfolio risk. |
| **License** | MIT (riskparity.py), BSD-3 (Riskfolio-Lib), Apache 2.0 (skfolio) |
| **Maturity** | **High.** Riskfolio-Lib v7.3 (2026), 3,900+ GitHub stars. riskparity.py v0.1 (324 stars, academic peer review). Algorithms trace to Spinu (2013) and Feng & Palomar (2015). |
| **Community adoption** | Riskfolio-Lib: 3.9k stars, 1.1k forks, active PyPI downloads. Used in CAIA webinars, academic courses. |
| **Explainability** | **Excellent.** Risk contribution per asset is a single scalar: `RC_i = w_i * (Σw)_i / σ_p`. The equal-risk objective `min Σ(RC_i - RC_target)²` is transparent and auditable. |
| **Determinism** | **Fully deterministic.** The SLSQP or cyclical algorithm converges to the same weights for identical input covariance. No randomness. |
| **Reuse / Adapt / Build** | **Adapt.** The *algorithmic pattern* (risk contribution equalization) should be reimplemented lightweight. Riskfolio-Lib is too heavy as a dependency (requires cvxpy, scipy). Build a `RiskParitySizer` class using numpy-only matrix operations, following Spinu's cyclical coordinate descent. |

**Recommendation: ADAPT** — Implement risk contribution equalization as a deterministic numpy function. ~80 lines of code.

---

### 2.2 Expected Shortfall (CVaR) & Value at Risk (VaR)

| Attribute | Assessment |
|---|---|
| **Purpose** | VaR: maximum loss at a given confidence level. CVaR/ES: expected loss beyond VaR. Institutional standard under Basel III. |
| **License** | MIT (pyRisk, SquareQuant), BSD-3 (Riskfolio-Lib), Apache 2.0 (cvxportfolio) |
| **Maturity** | **Very high.** VaR is the canonical risk metric (Jorion, 2001). CVaR is Basel III mandated. Multiple well-understood estimation methods: historical, parametric (Gaussian), Monte Carlo, Extreme Value Theory. |
| **Community adoption** | Universally adopted. Every major risk library implements both. Backtesting literature spans Kupiec (1995), Christoffersen (1998), Du-Escanciano (2024+). |
| **Explainability** | **Excellent for historical/parametric.** CVaR = mean of tail observations — directly interpretable. EVT-based requires more expertise. |
| **Determinism** | **Deterministic for historical and parametric methods.** Monte Carlo simulation is non-deterministic (random sampling) and should be excluded. EVT estimation via MLE is deterministic. |
| **Reuse / Adapt / Build** | **Build.** VaR and CVaR computations are ~20 lines of numpy each. Historical simulation: `np.percentile(returns, 100-conf)` for VaR; `returns[returns <= var].mean()` for CVaR. No dependency needed. |

**Recommendation: BUILD** — Two functions `compute_var` and `compute_cvar` using numpy. Historical and parametric methods only (no MCMC). ~40 lines of code total.

---

### 2.3 Kelly Criterion

| Attribute | Assessment |
|---|---|
| **Purpose** | Determine optimal bet size to maximize long-run geometric growth: `f* = (bp - q) / b`. Adapted from gambling to portfolio management. |
| **License** | N/A (mathematical formula, public domain) |
| **Maturity** | **Very high** (Kelly, 1956). Used by Buffett, Gross, Thorp. Extensive academic validation (BSIC, 2023). |
| **Community adoption** | Widely adopted with strong caveats. Standard institutional practice is **fractional Kelly** (0.25×–0.50×) to mitigate drawdown risk. |
| **Explainability** | **Excellent.** Formula is transparent: edge ÷ odds. Each input (win rate, payoff ratio) is interpretable. |
| **Determinism** | **Deterministic.** Given fixed `p` (win probability) and `b` (odds), output is fixed. |
| **Reuse / Adapt / Build** | **Build** as a ceiling cap only. Full Kelly is too aggressive for AurumAI's institutional mandate. Implement as `KellySizer.fractional(p, b, fraction=0.25)` — an *upper bound* on position size, not the primary sizer. ~15 lines. |

**Recommendation: BUILD (evaluation-only)** — Fractional Kelly as a protective cap on position size. Never the primary sizing mechanism.

---

### 2.4 Volatility Targeting

| Attribute | Assessment |
|---|---|
| **Purpose** | Scale position size inversely to current volatility to maintain constant risk exposure. `Position = TargetVol / (CurrentVol × sqrt(T))`. |
| **License** | N/A (industry standard, public domain) |
| **Maturity** | **Very high.** Used systematically by CTA funds, risk parity funds (Bridgewater All Weather). |
| **Community adoption** | Industry standard. Implemented in riskkit, Riskfolio-Lib, Cvxportfolio. Academic papers by Harvey et al., Moreira & Muir. |
| **Explainability** | **Excellent.** Single formula: higher volatility → smaller position. Intuitive and auditable. |
| **Determinism** | **Deterministic.** Volatility estimate (e.g., 20-day EWMA or 60-day rolling std) produces the same scaling factor given identical input. |
| **Reuse / Adapt / Build** | **Build.** Core computation: `target_vol / (rolling_std(returns) * sqrt(252))`. Uses existing pandas/numpy. ~20 lines. |

**Recommendation: BUILD** — VolatilityTargetSizer using rolling or EWMA volatility. Primary position-sizer for AurumAI. ~20 lines.

---

### 2.5 Drawdown Control

| Attribute | Assessment |
|---|---|
| **Purpose** | Monitor peak-to-trough decline. Trigger size reduction or halt when drawdown exceeds predefined thresholds. |
| **License** | MIT (riskkit) |
| **Maturity** | **Very high.** Maximum Drawdown (Calmar Ratio), Conditional Drawdown at Risk (CDaR) from Chekhlov et al. (2005). Riskfolio-Lib implements 6 drawdown risk measures. |
| **Community adoption** | Universal. Every institutional risk framework includes drawdown limits. |
| **Explainability** | **Excellent.** Drawdown = current value / peak value − 1. CDaR = CVaR of drawdown distribution. Both transparent. |
| **Determinism** | **Deterministic.** Drawdown is a deterministic function of the price series. |
| **Reuse / Adapt / Build** | **Build.** DrawdownManager with tiered thresholds: `Monitor → CutSize → Halt`. Inspired by riskkit's pattern but deterministic. ~60 lines. |

**Recommendation: BUILD** — DrawdownManager with state machine (normal → caution → halt → recover). ~60 lines.

---

### 2.6 Position Sizing Frameworks

| Attribute | Assessment |
|---|---|
| **Purpose** | Determine how much capital to allocate to each position. Primary lever for risk control. |
| **License** | MIT (riskkit) |
| **Maturity** | **Very high.** Multiple well-studied methods: fixed-fractional (1% rule), percent volatility, Kelly, ATR-based. |
| **Community adoption** | Universal. Institutional standard: equalize Marginal Contribution to Risk (MCR) across positions. |
| **Explainability** | **Excellent.** Each method has a clear formula. The MCR equalization approach directly answers "which position is driving risk?" |
| **Determinism** | **Deterministic.** All methods produce fixed output for fixed input. |
| **Reuse / Adapt / Build** | **Build.** Combine volatility targeting (primary), with drawdown as override, and fractional Kelly as ceiling. No external dependency. ~100 lines total for the composite PositionSizer. |

**Recommendation: BUILD** — Composite sizer: `VolatilityTargetSizer` (primary) + `DrawdownOverride` (override) + `KellyCap` (ceiling). ~100 lines.

---

### 2.7 Black Swan / Tail-Risk Detection

| Attribute | Assessment |
|---|---|
| **Purpose** | Detect extreme market events (fat tails) that standard models miss. Use Extreme Value Theory (EVT) to model tail behavior. |
| **License** | MIT (pyRisk implements Picklands estimator and GPD) |
| **Maturity** | **High** academically (Taleb, 2007; Embrechts et al., 1997). Production implementations exist but are less common than VaR. |
| **Community adoption** | Growing. EVT-based VaR/CVaR gaining traction. Entropic bubble detection (Ardakani, 2025) offers novel early-warning signals. |
| **Explainability** | **Moderate.** EVT (GPD fitting, Peaks-over-Threshold) requires statistical expertise. Entropy-based methods (bubble detection index) are newer and less familiar. |
| **Determinism** | **Deterministic.** GPD parameter estimation via MLE or method of moments is deterministic. Peak-over-threshold selection can be rule-based. |
| **Reuse / Adapt / Build** | **Adapt.** Implement Peaks-over-Threshold (POT) with GPD fitting. The key metric: tail index (shape parameter ξ). ξ > 0.5 indicates heavy tail regime. ~80 lines. |

**Recommendation: ADAPT** — Build a `TailRiskDetector` using Peaks-over-Threshold EVT. Compute tail index and flag when ξ exceeds threshold. Approx 80 lines.

---

### 2.8 Regime-Aware Risk Models

| Attribute | Assessment |
|---|---|
| **Purpose** | Adjust risk parameters based on detected market regime (bull/bear/high-vol/crisis). Integrates with AurumAI's existing `MacroRegimeDetector`. |
| **License** | BSD-3 (statsmodels MarkovRegression), MIT (hidden-regime, hmmlearn) |
| **Maturity** | **High.** Markov-switching models (Hamilton, 1989). statsmodels provides production-grade implementation. HMMs are standard in quantitative finance. |
| **Community adoption** | Widely used. Hidden-regime (PyPI), MarkovRegression in statsmodels. Regime-aware RL (2026) is an active research area. |
| **Explainability** | **High.** Regime probabilities are intuitive: `P(regime = high_vol | data) = 0.85`. Smoothed probabilities provide clear transition visualization. |
| **Determinism** | **Deterministic** for a fitted model. The forward-backward algorithm (Baum-Welch) is deterministic for a given random seed. However, statsmodels' EM may have convergence sensitivity. AurumAI already has `MacroRegimeDetector` which is deterministic with fixed seed. |
| **Reuse / Adapt / Build** | **Reuse.** AurumAI already has `MacroRegimeDetector` (Capability 15.0) and `ForecastContext.current_regime`. No new detection needed. The risk layer consumes regime labels and confidence from this existing component. |

**Recommendation: REUSE** — Consume `ForecastContext.current_regime` and `regime_confidence` directly. No new detection code. Build a `RegimeRiskOverlay` that maps regime → risk multiplier (e.g., expansion=1.0×, recession=0.5×, crisis=0.25×).

---

## 3. Integrated Architecture Proposal

### 3.1 Design Principles

1. **Deterministic only.** No random sampling, no MCMC, no stochastic simulation.
2. **Explainable.** Every risk decision traces to a single formula or threshold.
3. **Reuse first.** Consume existing Forecast Intelligence and Regime Detection outputs.
4. **No scope creep.** Risk Intelligence answers five questions — nothing more.
5. **Layered.** Each component is independent and testable.

### 3.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Forecast Intelligence                        │
│  (Phases 16.1–16.10)                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Forecast     │  │ Forecast     │  │ ForecastValidator    │  │
│  │ Confidence   │  │ Context      │  │ (MAE, RMSE, MAPE,   │  │
│  │ (spread,     │  │ (regime,     │  │  DA, Coverage)       │  │
│  │  agreement,  │  │  news, FOMC, │  └──────────────────────┘  │
│  │  coherence)  │  │  events)     │                            │
│  └──────────────┘  └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RISK INTELLIGENCE                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  1. RiskBudget (risk parity allocation)                   │   │
│  │     - RiskParitySizer: equalize RC across positions       │   │
│  │     - Output: target_weights                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  2. RiskMeasure (VaR / CVaR / tail index)                │   │
│  │     - compute_var(returns, 0.95) → max_loss              │   │
│  │     - compute_cvar(returns, 0.95) → expected_tail_loss   │   │
│  │     - TailRiskDetector(returns) → tail_index              │   │
│  │     - Output: risk_metrics dict                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  3. PositionSizer (vol-target, drawdown, Kelly cap)      │   │
│  │     - VolatilityTargetSizer: target_vol / current_vol    │   │
│  │     - DrawdownManager: state machine (monitor/cut/halt)  │   │
│  │     - KellyCap: fractional Kelly upper bound             │   │
│  │     - Output: position_size, scaling_factor              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  4. DecisionGate (should we act? should we delay?)       │   │
│  │     - RegimeRiskOverlay: regime → risk_multiplier        │   │
│  │     - UncertaintyBudget: entropic risk threshold         │   │
│  │     - DrawdownLock: halt if drawdown > limit             │   │
│  │     - Output: RiskDecision(action, reason, score)        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Answering the Five Questions

#### Q1: Should we trust the forecast?

**Component: RiskMeasure + ForecastValidator**

| Input | Decision |
|---|---|
| `ForecastValidator.report.passed == True` | Forecast accuracy thresholds met |
| `compute_var(forecast_errors, 0.95)` < tolerance | Error tail within acceptable bounds |
| `TailRiskDetector(forecast_errors).tail_index < 0.5` | No heavy tail in error distribution |
| → **TRUST** if all conditions pass; **REDUCE CONFIDENCE** otherwise |

#### Q2: Should we act now?

**Component: PositionSizer + DecisionGate**

| Input | Decision |
|---|---|
| `VolatilityTargetSizer.scaling_factor > 0.3` | Sufficient room to act |
| `DrawdownManager.state == "normal"` | Not in drawdown halt |
| `RegimeRiskOverlay.multiplier > 0.25` | Not crisis regime |
| → **ACT** if all conditions pass; **SCALE DOWN or DELAY** otherwise |

#### Q3: Is the current market regime too risky?

**Component: RegimeRiskOverlay**

| Regime | Risk Multiplier | Interpretation |
|---|---|---|
| `EXPANSION` | 1.0× | Full allocation |
| `STAGNATION` | 0.75× | Moderate reduction |
| `CONTRACTION` | 0.50× | Significant reduction |
| `CRISIS` | 0.25× | Minimal exposure |

Regime is consumed from `ForecastContext.current_regime` — no new detection.

#### Q4: Is uncertainty acceptable?

**Component: UncertaintyBudget**

| Input | Decision |
|---|---|
| `ForecastConfidence.context_coherence < 0.30` | Low coherence → unacceptable |
| `compute_var(returns, 0.99) > max_tolerable_loss` | VaR breach → unacceptable |
| `TailRiskDetector.tail_index > 0.5` | Heavy tails → unacceptable |
| → **ACCEPTABLE** only if all thresholds pass; flag uncertainty otherwise |

#### Q5: Should execution be delayed?

**Component: DecisionGate**

The DecisionGate is a state machine:

```
normal ──→ drawdown > limit ──→ caution ──→ drawdown > halt_limit ──→ halted
  ↑                                                                     │
  └────────────── recovery period elapsed ←─────────────────────────────┘
```

Additional delays triggered by:
- `TailRiskDetector.tail_index > 0.7` (extreme tail regime)
- Weekly loss exceeding rolling VaR
- Regime transition detected but confidence < 0.50

### 3.4 Data Model

```python
@dataclass(frozen=True)
class RiskBudget:
    target_weights: dict[str, float]
    risk_contributions: dict[str, float]
    method: str  # "risk_parity" | "equal_weight"

@dataclass(frozen=True)
class RiskMetrics:
    var_95: float
    var_99: float
    cvar_95: float
    tail_index: float | None
    method: str  # "historical" | "parametric"

@dataclass(frozen=True)
class PositionSizing:
    scaling_factor: float
    target_vol: float
    current_vol: float
    kelly_cap: float | None
    drawdown_state: str

@dataclass(frozen=True)
class RiskDecision:
    action: str  # "proceed" | "scale_down" | "delay" | "halt"
    reason: str
    score: float  # 0.0 (max risk) to 1.0 (no risk)
    components: dict[str, bool]  # per-gate pass/fail
```

All output dataclasses are frozen (immutable), deterministic, and serializable via `to_dict()`.

### 3.5 Estimated Code Size

| Component | Lines | Dependencies |
|---|---|---|
| `RiskBudget` + `RiskParitySizer` | ~80 | numpy |
| `RiskMetrics` + VaR/CVaR | ~50 | numpy |
| `TailRiskDetector` (EVT) | ~80 | numpy, scipy (optional) |
| `VolatilityTargetSizer` | ~30 | numpy, pandas |
| `DrawdownManager` | ~60 | numpy |
| `KellyCap` | ~15 | math |
| `RegimeRiskOverlay` | ~30 | (consumes ForecastContext) |
| `UncertaintyBudget` | ~30 | numpy |
| `DecisionGate` | ~60 | (consumes all above) |
| `RiskDecision` dataclass | ~20 | — |
| **Total** | **~455** | **numpy, pandas, math** |

---

## 4. Implementation Roadmap

### Phase 17.1 — Core Risk Measures (priority: highest)
- `compute_var` / `compute_cvar` (historical + parametric)
- `TailRiskDetector` (Peaks-over-Threshold EVT)
- `RiskMetrics` frozen dataclass
- Tests: random data, known outputs, edge cases

### Phase 17.2 — Position Sizing (priority: high)
- `VolatilityTargetSizer` (rolling/EWMA vol)
- `DrawdownManager` (tiered state machine)
- `KellyCap` (fractional)
- `PositionSizing` frozen dataclass
- Tests: known vol → known scaling, drawdown state transitions

### Phase 17.3 — Risk Budgeting (priority: medium)
- `RiskParitySizer` (cyclical coordinate descent)
- `RiskBudget` frozen dataclass
- Tests: equal correlation → equal weights, known covariance → known RC

### Phase 17.4 — Decision Gate (priority: medium)
- `RegimeRiskOverlay` (consumes ForecastContext)
- `UncertaintyBudget` (consumes ForecastConfidence)
- `DecisionGate` (state machine)
- `RiskDecision` frozen dataclass
- Tests: all five questions answered correctly

### Phase 17.5 — Integration
- Integration tests: full Forecast Intelligence → Risk Intelligence pipeline
- Tests: serialization, determinism, context immutability preservation
- Verify: no new dependencies, zero regressions

---

## 5. References

### Academic Papers
- Spinu, F. (2013). *An Algorithm for Computing Risk Parity Weights*. SSRN.
- Feng, Y. & Palomar, D. P. (2015). *SCRIP: Successive Convex Optimization Methods for Risk Parity Portfolio Design*. IEEE Trans. Signal Process.
- Kelly, J. L. (1956). *A New Interpretation of Information Rate*. Bell System Technical Journal.
- Taleb, N. N. (2007). *The Black Swan: The Impact of the Highly Improbable*.
- Hamilton, J. D. (1989). *A New Approach to the Economic Analysis of Nonstationary Time Series*. Econometrica.
- Chekhlov, A., Uryasev, S., & Zabarankin, M. (2005). *Drawdown Measure in Portfolio Optimization*. International Journal of Theoretical and Applied Finance.
- Jorion, P. (2001). *Value at Risk: The New Benchmark for Managing Financial Risk*.
- Ardakani, O. (2025). *Detecting Financial Bubbles with Tail-Weighted Entropy*. CSMF.
- Moreira, A. & Muir, T. (2017). *Volatility-Managed Portfolios*. Journal of Finance.

### Open-Source Projects (Reference Only — Not Direct Dependencies)
- **Riskfolio-Lib** (BSD-3, 3.9k ★) — Comprehensive risk measure implementations
- **cvxportfolio** (Apache 2.0, Stanford/Boyd) — Convex portfolio optimization
- **skfolio** (Apache 2.0, scikit-learn based) — Portfolio optimization
- **riskkit** (MIT, zero deps) — Framework-agnostic risk toolkit
- **pyRisk** (MIT) — VaR, ES, EVT, backtesting
- **riskparity.py** (MIT, convexfi) — Fast risk parity solvers
- **hidden-regime** (MIT) — HMM-based regime detection

### Institutional Frameworks
- Basel III market risk framework (CVaR mandate)
- Bridgewater All Weather (risk parity)
- AQR risk management framework (vol targeting, drawdown control)
- BlackRock portfolio construction (MCR equalization)

---

*End of research report. No code committed.*
