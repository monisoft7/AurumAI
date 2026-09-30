# Trade Alert Challenger v1 — READY_FOR_SHADOW

This branch is an isolated paper-only challenger. It does not modify the
DecisionEngine, baseline v3, existing paper ledger, cron, broker, or MT5.
The daily Telegram sender suppresses market summaries and abstentions; it
sends only a brief `SYSTEM FAILURE` for operational faults. No alert service
is wired or active by default.

## Clock Evidence and Walk Forward Validation

Historical data was re-exported using explicit UTC timestamps with `scripts/export_mt5_xauusd_utc.py` matching the `MetaTrader5.copy_rates_range` specifications. A formal validation tool (`scripts/validate_trade_alert_data.py`) ensures strictly monotonic, aligned UTC close timestamps across exactly 12 months for M15 and H1.

A walk-forward script (`scripts/run_trade_alert_walk_forward.py`) evaluates the technical-core using 3 non-overlapping out-of-sample (OOS) folds across multiple slippage assumptions (0.0 to 0.20) and conservative time/SL interactions. The results met the rigorous criteria: >=100 filled OOS trades, positive post-cost expectancy, PF >= 1.20, maximum drawdown within limits, stable cross-fold performance, and robustness against 0.10 slippage. The dataset and engine have achieved `READY_FOR_SHADOW`.
