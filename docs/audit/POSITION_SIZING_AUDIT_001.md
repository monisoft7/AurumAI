# Position Sizing Pipeline Audit 001

- **Audit type:** data-flow audit (read-only; no fixes, no recommendations, no implementation)
- **Audit date:** 2026-08-04
- **Scope:** the `position_sizing` stage, its producers (`risk_measures`), consumers (`risk_gate`, `finalize`, report, historical replay), and the sizing/risk-budget modules (`VolatilityTargetSizer`, `RiskParitySizer`, `DrawdownManager`, `KellyCap`)
- **Repo state:** git HEAD `78c9ad4` (`version1`); working tree modified (`src/orchestration/stages.py`, `scripts/generate_institutional_report.py`, `run.py`, etc. — unrelated in-flight work)
- **Companion audit:** `docs/audit/RUNTIME_TRACE_AUDIT_001.md` §8.6 documents the same issue from the runtime-trace side

---

## 1. Module inventory

| Module | Purpose | Producer of |
| --- | --- | --- |
| `src/forecasting/position_sizing.py` (140 lines) | `PositionSizing` dataclass; `VolatilityTargetSizer`; `DrawdownManager`; `KellyCap` | `position_sizing` stage output |
| `src/forecasting/risk_budgeting.py` (80 lines) | `RiskBudget` dataclass; `RiskParitySizer` | `risk_budget` half of the stage output |
| `src/orchestration/stages.py:296-313` | `_position_sizing` orchestration function | the stage payload |
| `src/orchestration/stages.py:258-293` | `_risk_measures` upstream stage | `RiskMetrics` |
| `src/orchestration/stages.py:316-354` | `_risk_gate` consumer of `scaling_factor` | `RiskDecision` |
| `src/orchestration/stages.py:808-829` | `_finalize` aggregation | `finalize.json` blocks |
| `src/pre_market/risk_reporter.py` | uses `DrawdownManager` in the portfolio path | `RiskSnapshot` |

## 2. DAG wiring (`src/orchestration/orchestrator.py`)

| Job | Line | Dependencies | ttl / checkpoint |
| --- | --- | --- | --- |
| `risk_measures` | 409-414 | `forecast` | 300 / yes |
| `position_sizing` | 416-422 | `risk_measures` | 300 / yes |
| `risk_gate` | 425-431 | `build_context`, `build_legacy_pipeline`, `risk_measures` | 300 / yes |
| `finalize` | 433-441 | `risk_gate`, `position_sizing`, `forecast_confidence`, `forecast_validation`, `decision_engine` | 300 / yes |

Verified edges (from `job_id=`/`dependencies=` scan): `position_sizing` depends on `risk_measures` and feeds only `risk_gate` and `finalize`. `trade_recommendation` (line 345-346) depends only on `decision_engine`; `decision_engine` (line 331) does not declare `position_sizing`. Neither reads sizing/budget (see §6, grep evidence).

## 3. Complete data flow

```
forecast ──> risk_measures (RiskMetrics) ──declared dep──> position_sizing
                                                              │
                          synthetic returns (seed 42, n=252) ─┤
                          hardcoded covariance ───────────────┤
                                                              ▼
                                        {position_sizing: PositionSizing,
                                         risk_budget: RiskBudget}
                                                              │
                          scaling_factor ──> risk_gate ──> RiskDecision ──> finalize.json["risk_decision"]
                          position_sizing ─────────────────> finalize.json["position_sizing"] ──> report §10, replay
                          risk_budget ─────────────────────> finalize.json["risk_budget"] ──────> report §10
```

Step-by-step:

1. `_position_sizing` fetches `results["risk_measures"]` into `risk_metrics` (`stages.py:301`) and **never references it again** (dead read; declared dep edge is scheduling-only in effect).
2. Creates `np_rng = np.random.default_rng(42)` (`stages.py:304`) and synthesizes `returns = np_rng.normal(0.005, 0.02, 252)` (`stages.py:305`).
3. `VolatilityTargetSizer().compute(returns)` with defaults `target_vol=0.15`, `window=60`, `annualization_factor=252.0` (`stages.py:307`; `position_sizing.py:30-35`). `current_vol = std(ddof=1) of returns[-60:] × sqrt(252)` (`position_sizing.py:52-53`); `scale = clamp(0.15 / current_vol, 0, 1)` (`position_sizing.py:55-60`). Returned `PositionSizing` hardcodes `drawdown_state="normal"` (`position_sizing.py:68`) and `kelly_cap=None` (`position_sizing.py:69`). The empty-returns branch (`position_sizing.py:37-44`) is unreachable from this caller (always 252 samples).
4. `RiskParitySizer().compute(np.array([[0.0004, 0.0001], [0.0001, 0.0003]]))` (`stages.py:310-311`) — hardcoded covariance, not market-derived.
5. Stage returns `{"position_sizing": sizing, "risk_budget": budget}` (`stages.py:313`).
6. `_risk_gate` reads `ps_result = results.get("position_sizing", {})`, unwraps `ps_result["position_sizing"]`, then `.scaling_factor` (`stages.py:336-340`). Drawdown state is **re-hardcoded** `"normal"` at `stages.py:344` regardless of the sizing payload (which is also always `"normal"`). `UncertaintyBudget.evaluate(context_coherence=0.5, var_95=var_95 or -0.05, tail_index=tail_index)` hardcodes coherence at 0.5 (`stages.py:331`). `DecisionGate.evaluate(...)` (`stages.py:347-352`) multiplies `score` by `scaling_factor` (`decision_gate.py:102`) and gates on `has_room = scaling_factor >= 0.30` (`decision_gate.py:89`).
7. `_finalize` copies `position_sizing` → `finalize.json["position_sizing"]` (`stages.py:827`), `risk_budget` → `["risk_budget"]` (`stages.py:828`), `risk_gate` → `["risk_decision"]` (`stages.py:821`).
8. Report (`scripts/generate_institutional_report.py`): reads both at lines 206-207; renders scaling factor / target vol / current vol / drawdown state / Kelly cap at 608-612 and 628-632; renders budget method / weights / contributions at 621-623 and 635-639.
9. Historical replay (`src/simulation/historical_replay.py`): `_extract_position_scaling` reads `finalize.position_sizing.scaling_factor` (1070-1077); value propagates into `EventRunResult.position_scaling` (780-786, 840-846, 1596-1602).

## 4. Inputs / outputs of the stage

| Direction | Item | Source | Value class |
| --- | --- | --- | --- |
| In | `risk_measures` (`RiskMetrics`) | `forecast` stage | fetched (`stages.py:301`) but **unused** |
| In | `returns` (252) | `np.random.default_rng(42).normal(0.005, 0.02, 252)` | **synthetic** (seeded) |
| In | `cov` 2×2 | `np.array([[0.0004, 0.0001], [0.0001, 0.0003]])` | **hardcoded placeholder** |
| Out | `position_sizing.scaling_factor` | 0.432555 (constant, see §5) | synthetic-derived |
| Out | `position_sizing.target_vol` | default 0.15 | constant |
| Out | `position_sizing.current_vol` | 0.346777 (constant, see §5) | synthetic-derived |
| Out | `position_sizing.drawdown_state` | hardcoded `"normal"` | constant |
| Out | `position_sizing.kelly_cap` | hardcoded `None` | constant |
| Out | `risk_budget.weights` | (0.464102, 0.535898) (constant) | placeholder-derived |
| Out | `risk_budget.risk_contributions` | (0.5, 0.5) (constant) | placeholder-derived |
| Out | `risk_budget.method` | `"risk_parity"` | constant |

## 5. Runtime effect (computed, seed 42)

Verified by direct execution (deterministic — identical every run because no market input reaches the stage):

```
current_vol  = 0.346777
scaling_factor = 0.432555
weights      = (0.464102, 0.535898)
contributions = (0.5, 0.5)   # normalized risk parity on the hardcoded matrix
```

`scaling_factor` therefore always passes the `has_room` check (`0.432555 >= 0.30`), and `risk_gate` drawdown logic never engages (state always `"normal"`).

## 6. Value classification (real / synthetic / unused / ignored)

| Item | Classification | Evidence |
| --- | --- | --- |
| `returns` (vol targeting) | **synthetic** | `stages.py:304-305`, seeded RNG |
| `cov` (risk parity) | **synthetic placeholder** | `stages.py:310`, literal array |
| `risk_measures` stage input | **unused** (dead read) | `stages.py:301` — no use after assignment |
| `risk_gate`'s `build_legacy_pipeline` dep | **unused** (scheduling-only edge) | `stages.py:316-354` never reads it; `orchestrator.py:425-426` |
| `drawdown_state` in `PositionSizing` | **ignored** (overwritten downstream) | `stages.py:344` hardcodes `"normal"` again |
| `kelly_cap` | **never computed in pipeline** | `stages.py` never instantiates `KellyCap`; value always `None` |
| `risk_budget` (weights/contributions) | **produced & reported, consumed by no decision logic** | grep: only `finalize`/report/replay touch it |
| `scaling_factor` | **consumed by `risk_gate`** | `stages.py:338-340, 350` → `DecisionGate`; synthetic value flows into `risk_decision` |
| `DrawdownManager` | **not used by pipeline** | only `pre_market/risk_reporter.py:30` (portfolio path) |

Grep evidence (all `src/**/*.py`, non-test): `risk_budget` and `kelly_cap` appear only in `position_sizing.py`, `stages.py:313/828`, `risk_budgeting.py`, `decision_gate` (scaling factor only), and report rendering; `decision_engine` / `trade_recommendation` / `confidence_engine` never reference sizing or budget.

## 7. Hardcoded constants and seeded random sources (exact locations)

| Location | Value | Role |
| --- | --- | --- |
| `stages.py:304` | `np.random.default_rng(42)` | seeded RNG for synthetic returns |
| `stages.py:305` | `normal(0.005, 0.02, 252)` | synthetic return series (loc, scale, n) |
| `stages.py:310` | `[[0.0004, 0.0001], [0.0001, 0.0003]]` | placeholder covariance |
| `stages.py:331` | `context_coherence=0.5` | hardcoded coherence into `UncertaintyBudget` |
| `stages.py:344` | `drawdown_state = "normal"` | hardcoded drawdown override |
| `stages.py:273` | `np.random.default_rng(42).normal(0, 1, 252)` | `_risk_measures` degenerate-residual fallback |
| `position_sizing.py:33-35` | `target_vol=0.15`, `window=60`, `annualization_factor=252.0` | sizer defaults |
| `position_sizing.py:68` | `drawdown_state="normal"` | always-normal in `compute` |
| `position_sizing.py:69` | `kelly_cap=None` | Kelly never populated by sizer |
| `risk_reporter.py:43` | `np.random.default_rng(42).normal(0, 1, 252)` | synthetic portfolio returns fallback |
| `decision_gate.py:23-31` | `_REGIME_MULTIPLIERS` | regime→multiplier table |
| `decision_gate.py:82` | `min_scaling=0.30` | gate room threshold |
| `decision_gate.py:56-58` | `max_tolerable_var=-0.05`, `coherence_threshold=0.30`, `tail_threshold=0.50` | uncertainty budget thresholds |

## 8. Test coverage (facts)

- `tests/test_position_sizing.py` (187 lines): covers `PositionSizing` dataclass, `VolatilityTargetSizer` (incl. determinism, clamping, empty-returns, validation), `DrawdownManager` states/recovery, `KellyCap` math. Tests the modules in isolation; uses its own `np.random.default_rng(42)` fixture. **No test asserts the stage-level synthetic inputs** (`stages.py:304-310`) or pins `0.432555`/`(0.464102, 0.535898)`.
- `tests/test_risk_budgeting.py`: `RiskParitySizer` behavior (n==1 shortcut, validation).
- `tests/test_risk_integration.py`: end-to-end `VolatilityTargetSizer` → `DecisionGate` with constructed data (lines 83-342); asserts `scaling_factor >= 0.0` — not the seeded stage values.
- `tests/test_institutional_orchestrator.py`: asserts DAG presence/order (`"position_sizing"` in deps, line 662/1035/1052); mocks the stage output at 826 (`{"position_sizing": 0.5, "risk_budget": {}}`).
- `tests/test_decision_gate.py`: gate behavior across `scaling_factor` values (0.1-1.0); does not exercise the synthetic producer.

## 9. Findings (trace-level facts)

1. **The stage's declared input is dead.** `risk_measures` is fetched (`stages.py:301`) and never read; the DAG dependency (`orchestrator.py:418`) is the only coupling, and it enforces ordering with zero data use.
2. **Both numeric inputs are synthetic/constant.** Volatility uses seeded pseudo-random returns; the risk budget uses a hardcoded covariance. No market, portfolio, or forecast data reaches the stage.
3. **`scaling_factor` is deterministic and constant at 0.432555** across all runs (no input variation), yet feeds a decision-affecting gate (`DecisionGate` score, `has_room`). The value never depends on run context.
4. **Drawdown logic is inert in the pipeline.** `compute` always returns `"normal"` (`position_sizing.py:68`) and `_risk_gate` re-hardcodes `"normal"` (`stages.py:344`); halt/caution branches of `DecisionGate` (`decision_gate.py:103-106, 124-130`) cannot be reached via this path. `DrawdownManager` is never used by the pipeline (only `risk_reporter.py:30`).
5. **`kelly_cap` is always `None`.** `KellyCap` (`position_sizing.py:119-140`) is exercised only by tests; the report renders the empty field.
6. **`risk_budget` is output-only.** Produced, persisted to `finalize.json`, rendered in the report, but never read by any decision or sizing logic.
7. **Seeded fallbacks exist in both `_risk_measures` and `risk_reporter`** (same seed 42), so even the upstream risk metrics and the portfolio report can be synthetic when data is absent — the same seed pattern as the sizing stage.
8. **The empty-returns branch** (`position_sizing.py:37-44`, all-zero/`normal`/`None` sizing) is not reachable from the stage, which always supplies 252 samples; it is exercised only in tests.
9. **No output of the stage influences trade sizing.** `trade_recommendation` depends only on `decision_engine`; the only runtime consumer of `scaling_factor` is `risk_gate`'s `RiskDecision` (finalize/report/replay).

## 10. Method and sources

- Read code: `src/forecasting/position_sizing.py` (full), `src/forecasting/risk_budgeting.py` (full), `src/forecasting/decision_gate.py` (full), `src/orchestration/stages.py` (258-354, 808-829), `src/orchestration/orchestrator.py` (DAG registration scan + 340-441), `src/pre_market/risk_reporter.py` (full), `src/simulation/historical_replay.py` (760-899, 1020-1093), `scripts/generate_institutional_report.py` (grep of sizing/budget fields).
- Grep evidence: all `src/**/*.py` for `scaling_factor|risk_budget|kelly_cap|KellyCap|DrawdownManager`; all `tests/**/*.py` for the same plus the pinned stage values (`0.432555`, `0.464102`).
- Executed: computed the exact stage outputs with seed 42 (current_vol 0.346777, scale 0.432555, weights (0.464102, 0.535898), contributions (0.5, 0.5)) using `forecasting.risk_budgeting.RiskParitySizer` and the same normal-draw as `stages.py:304-305`.
- Verified: git HEAD `78c9ad4`; DAG edges via `job_id=`/`dependencies=` scan.
