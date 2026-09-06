# AurumAI Paper Trading Protocol

Protocol version 1.0 is frozen before the first paper signal. Its evaluation
cohort is `xauusd-paper-2acd5ad-v1`, based on immutable baseline commit
`2acd5adb7ab286c9cb362d5d94dcea0f58f83277`.

## Scope and schedule

- The sole instrument is XAU/USD. This layer sends no orders, uses no real
  money, has no broker integration, and is not permission to trade live.
- Exactly one run is scheduled per market day. Every production decision is
  registered before its outcome, including `NO_TRADE`.
- Decision timestamps are retained in UTC together with the configured
  decision timezone, `Asia/Jerusalem`.
- The production Evidence, Confidence, Decision, and Recommendation
  calculations, thresholds, data sources, and pipeline stages are unchanged.
- Model or threshold changes are forbidden during the cohort. Any later change
  starts a new evaluation/cohort identifier and its observations must not be
  pooled with this cohort.

## Point-in-time entry, exit, and costs

The entry is the first completed market-session close strictly after the
recorded decision timestamp. For horizon N, the exit is the completed
market-session close exactly N observations after the entry. Only price rows
whose `available_at_utc` is no later than the evaluation timestamp may be
read. The locked horizons are 1, 3, and 5 sessions; no horizon is evaluated
until its exit observation is available.

Costs are explicit cohort configuration, never hidden constants: 10 basis
points round-trip transaction cost plus 2 basis points slippage per side, or
14 basis points total. Gross return is the XAU/USD percentage move for `BUY`
and its sign-reversed value for `SELL`; net return subtracts the locked total
cost. `NO_TRADE` has no fabricated trade return.

Each decision-time source/stage carries a freshness status. `stale`,
`unavailable`, `missing`, or `unknown` input makes the signal financially
ineligible. Stale or unavailable outcome prices are recorded as unevaluable,
not silently treated as current.

## Immutable records

`paper_trading.py create` accepts only a successful, internally consistent
runtime containing `stage_outputs.json`, `summary.json`, and the pending
`outcome.json`. It validates the stage schema, count, identifiers, runtime ID,
and locked baseline SHA. It then creates one new prediction file with exclusive
create semantics. A second prediction for the same runtime/evaluation ID is
rejected.

The prediction stores its schema and cohort IDs, baseline and runtime IDs,
decision timestamps, instrument, normalized trading decision, direction,
confidence, reliability, any recorded risk/size, first recorded gate and
rejection explanation, entry/horizon/cost rules, freshness statuses, and
relative paths plus SHA-256 hashes for the three required runtime artifacts
and a report when explicitly referenced by the summary. It uses a whitelist;
environment variables, API keys, credentials, tokens, and complete runtime
payloads are never copied.

Outcomes are new immutable files, one per prediction and horizon. They bind to
the exact prediction SHA-256. They contain the actual entry/exit observations,
price-source hash and freshness, gross and net return, cost, hit result, and
integrity flags. Creating an outcome never rewrites the prediction. Duplicate
horizons are rejected. The cohort reader excludes a changed prediction hash,
or timestamps that do not satisfy decision < entry < exit <= evaluation, and
such an integrity failure forces `NO_GO`.

## Cohort metrics and economic gate

Headline metrics use the primary 1-session horizon so a decision is not
triple-counted; 3- and 5-session results are reported separately. The summary
reports total decisions; `BUY`, `SELL`, and `NO_TRADE` counts; eligible and
completed trades; coverage and abstention rates; hit rate; average win and
loss; net expectancy; compounded cumulative net return; profit factor;
compounded-equity maximum drawdown; results by horizon; confidence and
reliability buckets; and data-integrity exclusions.

The precommitted minimum is 30 completed primary-horizon trades and at least
60 calendar days. Before both are met, status is `INSUFFICIENT_SAMPLE`, never a
profitability pass. Afterward, status cannot be `GO` when net expectancy after
costs is at or below zero, profit factor is below 1.20, paper maximum drawdown
exceeds 10%, or any look-ahead/prediction-mutation integrity failure exists.
These are initial eligibility conditions only: they do not guarantee profit
and never authorize real trading.

## Offline commands

```text
python scripts/paper_trading.py create --runtime-dir RUN --registry-dir LEDGER --baseline-commit 2acd5adb7ab286c9cb362d5d94dcea0f58f83277
python scripts/paper_trading.py evaluate --prediction PREDICTION --outcomes-dir LEDGER/outcomes --prices PRICES.csv --horizon 1 --as-of-utc 2026-09-10T21:00:00Z
python scripts/paper_trading.py summarize --registry-dir LEDGER --evaluation-id xauusd-paper-2acd5ad-v1
```

These commands only read local artifacts and write ledger files. They contain
no network or broker code.
