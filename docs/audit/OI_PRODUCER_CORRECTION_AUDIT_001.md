# OI_PRODUCER_CORRECTION_AUDIT 001

**Subject:** Whether the Open Interest producer can be made institutionally real
using data/connectors **already present in the repository**, or whether a genuinely
new external data source is required. Follows `SIGNAL_ASSESSMENT_CORRECTION_AUDIT_001`
(candidate #2, category B placeholder/broken).
**Scope:** Read-only investigation + design. No source, config, or test changes.
Correction #1 is complete and is **not** modified by this audit.
**Date:** 2026-08-08
**Status:** VERIFIED AGAINST CURRENT TREE AND LIVE QUOTES. Every claim below was
confirmed either at a code location, in a persisted checkpoint, or by executing a
read-only query of the repository's existing data provider (yfinance) on 2026-08-08.

---

## §1 Executive finding

The OI producer **is broken by dead code** and produces 0.0 for a second, deeper
reason: even if the dead code were removed, the field it currently computes is the
yfinance **`Volume`** column of `GC=F` — traded volume, *not* open interest. So the
producer is a **B (broken existing producer) + D (semantics mismatch)** combination.

A **genuine OI level IS obtainable from an already-present provider**: a live,
read-only call to the repository's existing yfinance dependency returned
`openInterest = 298095` for `GC=F` on 2026-08-08 — a plausible COMEX gold futures
open interest. No new external provider is required to obtain an OI *level*.

The remaining gap is the consumed **metric**: the contract field is
`open_interest_change_pct` (day-over-day change). yfinance exposes only the current
snapshot — there is **no OI history, dataset, cached file, or second-dataset
anywhere in the repository** from which a previous-day level can be read. That part
is either (a) synthesized in-repo by persisting the daily level (in-repo state
capture, precedent: `fred_client.py` CSV cache), or (b) requires a genuinely new
external source with OI history — which is **out of scope** by constraint.

Therefore: **small producer repair, achievable with zero new connectors** — an OI
level is re-supplied from the existing yfinance dependency, the dead code is the
only logic defect, and the change-% field needs a minimal in-repo state element
(previous-day level) rather than a new data vendor. Even with all that, a
day-over-day change > OI_THRESHOLD_PCT (5.0) may legitimately not occur on
a given day; the criterion is not "must pass", and no scorer or classifier rule
changes.

---

## §2 Current OI data path (verified)

```
PositioningDataFetcher.fetch                                pre_market/positioning.py:24-38
  └─ _fetch_open_interest()                                pre_market/positioning.py:72-96
        ├─ yfinance.download("GC=F", period="10d")         (existing dependency)
        ├─ data["Volume"] columns  ← yfinance OHLCV        ⚠️ Volume, NOT open interest
        ├─ prev_oi / curr_oi computed ONLY inside the
        │    `data.empty or len(data) < 2` early-return branch  positioning.py:77-80
        ├─ ❌ unreachable statements after `return` (dead code)
        └─ NameError (prev_oi unbound for len>=2) → except → {"change_pct": 0.0}
                                                          positioning.py:85
PositioningSnapshot.open_interest_change_pct = 0.0        pre_market/contracts.py:130,152
  ├─ assembler.py:90 (Correction #1 wiring, overnight GOLD branch only):
  │     VolumeFlowConfirmator.evaluate(open_interest_change_pct=0.0)  volume.py:40-47
  │       → abs(0.0) > 0.01? NO → no detail, no confirm → volume_flow unaffected
  └─ assembler.py:117-120 (positioning branch): passes ONLY etf_flow_change_pct +
       etf_flow_momentum — OI never reaches the evaluator via the positioning branch
SignalAssessment → volume_flow CriterionScore → classifier positive_count
EvidenceCollection (evidence items) → EvidenceReasoning set weights →
CounterEvidence → Confidence → Risk/Reward → Decision (formulas untouched)
```

Persisted proof (both runs):
- `runtime_20260806_234356` → `pre_market_scan.json`:
  `PositioningSnapshot(..., etf_flow_change_pct=0.01, open_interest_change_pct=0.0, ...)`
- `runtime_20260808_180855` → `pre_market_scan.json`:
  `PositioningSnapshot(..., etf_flow_change_pct=2.26, open_interest_change_pct=0.0, ...)`

In the edited (post-Correction-#1) run, ETF flow reached the confirmator while
**OI remained 0.0** — exactly the dead producer.

## §3 Producer classification

| Question | Answer |
|---|---|
| What is the current OI producer? | `PositioningDataFetcher._fetch_open_interest` (pre_market/positioning.py:72-96) — yfinance `GC=F` "10d" download; computes per-cent from last two `Volume` rows |
| Why does it produce 0.0? | ① dead code: `prev_oi`/`curr_oi` are only assigned **after** an unconditional `return` inside the `len<2` branch (positioning.py:77-80); for `len>=2` (every real runtime) the names are unbound → `NameError` → swallowed `except Exception` → 0.0. ② if the dead code were removed, the value would be **Volume** (traded contracts), not OI — semantically wrong even when returning nonzero |
| Classification | **B + D — broken producer (dead code) combined with a semantic mismatch** (traded volume ≠ open interest). Not C (the repo does not lack a value supply — see §4) and not A (the wiring added in Correction #1 is already correct once a real value exists) |
| Is OI positively expected? | No — `open_interest_change_pct` is a *measurement*, not a default. OI may legitimately be flat. The criterion confirms only when `abs(changes) > 5.0%` (volume.py:41) — a rare institutional event. No inference that OI "should be positive" |

---

## §4 Existing data/connector availability (verified)

| Candidate | Verified result |
|---|---|
| yfinance `Ticker("GC=F").get_info()["openInterest"]` | **AVAILABLE, live-checked 298095 on 2026-08-08** — the existing yfinance dependency (already used by pre_market, connectors, gold_data_provider) exposes a genuine OI level. No new provider selected |
| yfinance `download()` columns for GC=F | OHLCV only (`Close High Low Open Volume`); **no Open Interest column** (verified live 2026-08-08; Volume row showed 3,101 stale/odd + info-`volume` 182,381) — Volume ≠ OI |
| OI history / datasets / cached files | **None.** `data/` contains no cot/futures/position/OI files (glob over csv/json/parquet; zero matches). No `open_interest` key in `data/economic/output/knowledge.json` |
| Connectors present | `connectors/`: gold_data_provider.py (yfinance GC=F; schema `Date,Close,High,Low,Open,Volume`, gold_data_provider.py:38), dxy_fetcher.py (yfinance), fred_client.py (FRED, CSV cache precedent), real_yield_fetcher.py, cb_gold_fetcher.py (WGC-ish cache note). **No CME/CFTC/COT/OI connector of any kind** |
| Knowledge layer | `knowledge/cfi/contracts.py` defines `GoldPositioningDashboard.cot_net_non_commercial` (dict) + `ETFFlowMonitor` — contracts only; **no producer populates them** (grep: zero constructor calls); adapters map shapes to Evidence, no data |
| yfinance as "OI" history | `Ticker.get_info()` returns the current OI snapshot only; `download`/`history` never returns Open Interest; no endpoint in the repo's existing usage returns a second OI timestamp |

**Conclusion for §4:** An in-repo provider can legitimately supply a **current OI
level**. No in-repository source can supply the **previous-day level**, hence the
daily % change cannot be sourced from anything already stored. Fine-grained
alternatives requiring *new* endpoints/providers (CME settlement, CFTC COT, broker
APIs) — explicitly out of scope per constraints.

---

## §5 Architectural impact (a repair would touch only)

| Layer | Impact |
|---|---|
| `pre_market/positioning.py:72-96` | The only logic change: dead-code removal + source selection (from §8) |
| `pre_market/contracts.py` `PositioningSnapshot.open_interest_flow_change_pct` | **Unchanged** contract; the field already exists and is serialized |
| `signal_assessment/volume.py` `OI_THRESHOLD_PCT=5.0`, `evaluate()` | Unchanged — it already consumes `open_interest_change_pct` correctly; non-none values are expense-gated (volume.py:28-31) |
| `signal_assessment/assembler.py:90` (Correction #1) | Unchanged — already passes the field to the evaluator for gold overnight; would now receive a real value instead of 0.0 |
| `signal_assessment/assembler.py:117-120` (positioning branch) | Unchanged — OI intentionally not passed there today |
| Classifier, evidence, counter-evidence, confidence, risk-reward, decision layers | **Zero changes** — this is a producer fix, never a model change |

---

## §6 Downstream impact (once OI produces real change%)

1. Only one criterion input changes: `volume_flow` for **gold-class overnight
   observations** (the Correction #1 wiring). `VolumeFlowConfirmator` adds "OI
   rising/falling <x>%[(below threshold)]" (volume.py:40-47) and confirm only at
   `|x| > 5.0`.
2. If `|ΔOI| > 5%` → `volume_flow.passed=True` → `positive_count` +1 → for the
   gold overnight observation: e.g. WATCH→WEAK_SIGNAL or WEAK→SIGNAL; the
   classifier rule table and thresholds are untouched.
3. Evidence layer: the same observation is already kept (Watch-and-above are kept);
   its `classification` metadata and `composite_weight` may rise (0.18 → 0.30
   pattern observed in the Correction #1 run), flowing into the evidence set net
   weight (es_usd_fx / es_general depend on event_type mapping, not on OI).
4. CounterEvidence, Confidence, RiskReward, Decision formulas — unaffected chord
   by construction; they consume the same Evidence sets.
5. O (flat) days: no change at all. First day after a state-capture setup: change
   not computable → fallback 0.0 → identical behavior to today.

---

## §7 Test coverage today

| Test | Touches OI? | Would change? |
|---|---|---|
| `tests/test_pre_market.py::TestPositioningDataFetcher::test_fetch_returns_snapshot` | Implicit (fetches full snapshot; asserts only cot_regime/etf momentum) | **YES** — extend to assert `open_interest_change_pct` semantics with mocked yfinance |
| (none) unit test for `_fetch_open_interest` | — | **New test needed**: real-OI path (two levels) → change inside class; OI missing → 0.0; empty cache → 0.0 |
| `tests/test_signal_assessment.py::TestVolumeConfirmator::test_mixed_signals` | passes `open_interest_change_pct=1.0` | No (scorer contract unchanged) |
| `tests/test_signal_assessment.py` Correction #1 wiring tests (`test_overnight_volume_producer_reaches_confirmator` — OI fixture 0.5 through assembler; `..._unchanged_with_stub_level_data` — OI 0.0 → fallback) | Yes | No — they pin the in-place wiring/fallback behavior which stays; only the *producer* changes |
| `tests/test_signal_assessment.py::TestPositioningDataFetcher`-adjacent, `TestPositioningSnapshot::test_to_dict_from_dict_roundtrip` (fixture OI -0.5) | Contract only | No |

So the real OI tests needed for a future implementation: **one new unit test for
`_fetch_open_interest` + one assertion extension in `test_pre_market.py`**.

---

## §8 Smallest possible correction (design — NOT implemented here)

Scope first: a repair must not create a connector or select a new provider. The
legitimate path:

1. **Fix the dead code** in `_fetch_open_interest` (positioning.py:72-96): remove the
   unreachable `prev_oi`/`curr_oi` assignments; return `{"change_pct": 0.0}` on the
   empty/`len<2` path (already the case).
2. **Source a real OI level from the existing dependency**: `yf.Ticker("GC=F").get_info()["openInterest"]`
   (live-verified **298,095** on 2026-08-08 — the single in-repo source yielding a
   real OI number).
3. **Compute day-over-day change from in-repo state**: persist the level (JSON or
   the precedent `fred_client.py:15-30,201` CSV-cache pattern) under
   `data/controller/...` or `%TEMP%`; on the next fetch `(curr − prev)/prev × 100`
   = `open_interest_change_pct`. Empty/missing prev → `0.0` (fallback semantics of
   the scorer already handle it: `abs(0.0) > 0.01` is False, no confirm).
4. **Nothing else.** `volume.py`, assembler.py (both branches), classifier,
   evidence, decision layers stay byte-identical.

A repair can run the *full* lifecycle institutionally only after it has stored one
prior level; day 1 output = 0.0, day 2 onward = real change. An implementation that
wants historical deltas immediately (before the in-repo accumulation) would
necessarily need an external OI-history source — **outside this correction's
constraints**; for that reason day-1 semantics are documented and the "first
period flat" behavior is the by-design boundary.

---

## §9 Scope classification

| Candidate | Classification |
|---|---|
| Fix dead code + source OI level from existing yfinance (no new provider) | **Small producer repair** |
| + persist previous level for %-change (fred_client cache precedent) | Still **Small producer repair** (in-repo state, no new provider) |
| Pull OI history from an external CFTC/CME/Yahoo-endpoint feed to get deltas without waiting | **New connector — explicitly out of scope** (constraint: "do not create a new connector"; no such source exists in the repository) |

Net estimated scope if commissioned: **small producer repair** — one method
(`_fetch_open_interest`), one tiny state file, one test; lower than a "wiring-only"
boundary? No — wiring-only applies only when a working producer exists (Correction #1);
here the producer itself is nonfunctional, so the smallest is at the producer level.
Not "large/new capability" (no contracts, no evidence model, no orchestration change).

---

## §10 Explicit non-goals

1. Do not use `Volume` as OI (it is traded volume; the correction must not
   institutionalize a data-type mismatch).
2. Do not change `OI_THRESHOLD_PCT` (5.0), `VolumeFlowConfirmator`, classifier
   rules, `SIGNAL_LABELS`, or any downstream weight.
3. Do not add a new external OI/CFTC/COT endpoint/connector — the constraint set
   only allows sources already in the repository (`yfinance`), verified above.
4. Do not change `PositioningSnapshot` (field names/semantics) and do not change
   `assembler.py:90` or the positioning branch (assembler.py:117-120) added in
   Correction #1.
5. OI is not required to pass; flat OI days remain flat. The flag exists for
   >5% shift events only.
6. No scrubbed runtime in this audit; all flows above are code-location and
   persisted-artifact facts (both 2026-08-06 and 2026-08-08 runs persisted
   `open_interest_change_pct=0.0`).

---

### Appendix: live verification commands (executed 2026-08-08, read-only)

```
python -c "import yfinance as yf; print(yf.Ticker('GC=F').get_info().get('openInterest'))"
# -> 298095   (a real COMEX gold futures open interest level)
python -c "import yfinance as yf; print(list(yf.download('GC=F', period='5d', progress=False).columns))"
# -> [('Close','GC=F'), ('High','GC=F'), ('Low','GC=F'), ('Open','GC=F'), ('Volume','GC=F')]
#    (no Open Interest column; Volume is traded volume)
```

Both cross-checked against persisted `pre_market_scan.json` of
`runtime_20260806_234356` and `runtime_20260808_180855`
(`open_interest_change_pct=0.0` in both).