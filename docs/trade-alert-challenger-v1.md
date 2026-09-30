# Trade Alert Challenger v1 — DATA_REQUIRED

This branch is an isolated paper-only challenger. It does not modify the
DecisionEngine, baseline v3, existing paper ledger, cron, broker, or MT5.
The daily Telegram sender suppresses every non-`TRADE_ALERT BUY/SELL` message.
No alert service is wired or active.

## Missing evidence

The repository's gold history is daily (`data/history/gold/gold.csv`), not
M15/H1. The private paper ledger was inspected read-only in a separate
temporary checkout. The 0.30–0.60 threshold sweep was run by horizon, with
recorded costs subtracted. A positive one-session counterfactual appears in
only five evaluated outcomes and is dominated by one outcome; longer horizons
are negative or too sparse. This does not justify changing the current
confidence threshold. Real intraday walk-forward validation is **not
possible** yet. `scripts/trade_alert_attribution.py` reads a supplied
private ledger without writing to it. Counterfactual returns are not trade PnL.

## Required real data

Provide at least 12 contiguous months of real XAU/USD M15 and H1 completed
candles, preferably 24 months, including UTC candle-close timestamp, open,
high, low, close, volume, source, availability timestamp, and bid/ask or
observed spread per bar. Provide real execution slippage and commission/cost
history, trading calendar, DXY, US yields, Fed decisions, and timestamped
high-impact news with publication and availability times. All sources must
be point-in-time.

Walk forward chronologically with at least three non-overlapping OOS periods
and multiple market regimes. Require at least 100 OOS trades, net expectancy
above zero after spread/slippage/commission, profit factor >= 1.20, max
drawdown <= 10% of equity, no single trade accounting for more than 25% of
absolute PnL, and stable results across periods and regimes. Until these
data and tests exist, the only verdict is `DATA_REQUIRED`; no shadow service
should be activated.
