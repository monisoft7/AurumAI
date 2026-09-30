# Gold Hedge M5 audit — DATA_REQUIRED

Read-only source: `C:\Gold Hedge\data\xauusd_m5.csv`.
SHA-256: `537B3EA73B1ECB547EE29275148C4961D95571664A195EC4681ADAAB5361F418`.
The source file and Gold Hedge project were not edited.

## Observed data

Schema: `timestamp,open,high,low,close,volume,spread_points`.
69,059 rows from `2025-09-15 01:00:00` to `2026-09-11 22:55:00`
in the **unverified source clock**. Timestamps are naive, strictly increasing,
unique and aligned to five minutes. All fields are present; OHLC consistency,
positive prices, nonnegative volume and nonnegative spread pass. Volume is
present on every row (min 1, median 1,374, max 8,217). Spread is in **points**;
Gold Hedge's `csv_loader.py` and broker profile specify point size 0.01 USD/oz.
One conversion gives a median 0.04 USD/oz, mean 0.075 USD/oz and maximum
5.95 USD/oz. The adapter converts points once.

There are 289 timestamp gaps over five minutes: 35,173 absent nominal slots,
of which 29,376 fall on Saturdays/Sundays in the raw clock and 5,797 on
weekdays (including scheduled daily closures). No Saturday/Sunday bars exist.
The common gap lengths are 1h05m (101 events), 2h05m (93), 2d01h05m (23),
and 2d02h05m (22). There are 58 spreads above 1 USD/oz and 118 bars with
high-low range above 50 USD/oz; these are flagged for later source review,
not silently clipped. Maximum range is 212.33 USD/oz.

Grouping on the **raw wall clock only**, provisionally treating timestamps as
bar opens, yields 22,995 complete M15 groups from 23,044 buckets (49
incomplete) and 5,732 complete H1 groups from 5,771 buckets (39 incomplete).
These are audit counts, not UTC-validated bars or walk-forward inputs.

## Blocking clock evidence

The CSV contains no timezone, UTC offset, source/export manifest, or field
defining whether `timestamp` is the M5 open or close. Gold Hedge's broker
profile explicitly states `server_timezone = "UNKNOWN"`; its
`alpha_discovery.py` calls these timestamps *unverified dataset/server time*.
Evidence about a different GoldHunter export cannot establish this file's
clock. The observed session-hour shifts could reflect DST but do not identify
the zone or its transition rules. Assigning UTC would therefore introduce
an unsupported assumption and potential lookahead.

Provide the exact export command or source manifest for this CSV, with the
timestamp field definition and broker IANA timezone or paired source-clock
and UTC samples spanning both DST transitions. Then verify the file hash
against that export. `ClockEvidence` in the adapter requires this proof;
ambiguous and nonexistent DST local times are rejected.

## Validation state

No AurumAI strategy or Gold Hedge Slow Trend/Donchian benchmark was replayed
on this file. There are no valid OOS folds, candidate/alert counts, or cost
sensitivity outcomes. Broker profile confirms zero commission only for 12
observed demo deals; universal commission, production slippage and rollover
timezone remain unknown. The 0/0.05/0.10/0.20 USD/oz sensitivity grid cannot
replace the missing timestamp provenance. Verdict remains `DATA_REQUIRED`.
