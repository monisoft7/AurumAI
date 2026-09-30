# Trade Alert Challenger v1 — DATA_REQUIRED

This branch is an isolated paper-only challenger. It does not modify the
DecisionEngine, baseline v3, existing paper ledger, cron, broker, or MT5.
The daily Telegram sender suppresses every non-`TRADE_ALERT BUY/SELL` message.
No alert service is wired or active.

## Missing evidence

The repository's gold history is daily (`data/history/gold/gold.csv`), not
M15/H1. The private paper ledger is not present in this checkout and GitHub
authentication is unavailable in this environment. Consequently, attribution,
the 0.30–0.60 threshold sweep, and real walk-forward validation are **not
verified**. The supplied cohort counts (12/12 NO_TRADE; 6 justified and 3
missed of 9 evaluated) are observations, not proof that lowering confidence
would be profitable. `scripts/trade_alert_attribution.py` reads a supplied
private ledger without writing to it; each horizon is swept separately and
costs are subtracted. Counterfactual returns are not trade PnL.

## Required real data

Provide at least 12 contiguous months of real XAU/USD M15 and H1 completed
candles, preferably 24 months, including UTC candle-close timestamp, open,
high, low, close, volume, source, availability timestamp, and bid/ask or
observed spread per bar. Provide real execution slippage and commission/cost
history, trading calendar, DXY, US yields, Fed decisions, and timestamped
high-impact news with publication and availability times. All sources must
be point-in-time. Supply the read-only private daily paper ledger with
`predictions/` and `outcomes/` to run the attribution sweep.

Walk forward chronologically with at least three non-overlapping OOS periods
and multiple market regimes. Require at least 100 OOS trades, net expectancy
above zero after spread/slippage/commission, profit factor >= 1.20, max
drawdown <= 10% of equity, no single trade accounting for more than 25% of
absolute PnL, and stable results across periods and regimes. Until these
data and tests exist, the only verdict is `DATA_REQUIRED`; no shadow service
should be activated.
