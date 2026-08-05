# EVIDENCE_FILTERING_V2 — minimum additive design

Design only. Not implemented. No code. No modification of any source, test, or
contract beyond the additive changes specified below. Based exclusively on the
findings of `docs/audit/EVIDENCE_COLLECTION_AUDIT_001.md` and
`docs/audit/EVIDENCE_FILTERING_AUDIT_001.md`.

## 1. Objectives and constraints

The design must (requirements 4.1-4.5 of this task):

| # | Goal | Audit basis |
|---|---|---|
| G1 | Prevent stub evidence from surviving as real evidence | COLLECTION §5 (E1 Medium: stub fields, hard-coded breadth); FILTERING §5.2 |
| G2 | Allow genuine market signals to reach WEAK_SIGNAL/SIGNAL when justified | COLLECTION §3.3; FILTERING §5.1, §5.3 |
| G3 | Preserve existing contracts | FILTERING §8 (contract surfaces used unchanged) |
| G4 | Preserve weighting mathematics | COLLECTION §2; weighter formula `raw×0.5 + recency×0.3 + prov×0.2` (weighter.py:37-51) unchanged |
| G5 | Preserve reasoning and decision logic | FILTERING §3 R8-R12; engine.py:180-182,207 unchanged |

Design rule: every change is additive (new defaulted data, new derived values,
or a constant replaced by a data-driven value). No existing field, formula,
rule, or consumer is altered.

## 2. Findings that drive the design (from the audits only)

F1. The +0.64% XAU/USD move was discarded because `_compute_sigma` returns
0.0 when the fetched window has fewer than 5 bars (FILTERING §5.1; R0/R3) — the
GC=F 5-day window returned 4 bars (run.log:69). Magnitude then can never pass
(`|z| ≥ 2` unreachable), and `temporal_recency` is pinned at 1.0 (COLLECTION
§3.5) instead of reflecting the real move size.

F2. Persistence is structurally disabled: `assembler.py:44-47` hard-codes
`deviation_days=1.0, instrument_type="ETF"` for every overnight observation
(FILTERING §5.3). Because persistence never passes, SIGNAL (needs ≥3 positives
or ≥2 + persistence, classifier.py:58) is unreachable and WEAK_SIGNAL requires
2 other positives (breadth + magnitude).

F3. The stub positioning evidence survives solely because its breadth
criterion is hard-coded `passed=True` (assembler.py:112) while every
quantitative field is a stub (cot_z 0.0, gofo 0.0; positioning.py:40-41,87-89)
(FILTERING §5.2). With 1 positive it is WATCH 0.3 (cw 0.24) and produces a
0.62-weight set (COLLECTION §4).

F4. Only WATCH reaches reasoning: with F1-F3, `positive_count ≤ 1` for every
observation class, so W6's existing keep-set (SIGNAL/WEAK/WATCH, collector.py:
79-92) admits only WATCH items (FILTERING §5.4). The W6 filter itself and the
W7-W13 chain are sound; the fault is upstream at W4/W5 inputs.

## 3. Proposed changes

### C1 — Real z-scores for the four 4-bar instruments (root cause of F1)

- Affected component: `src/pre_market/overnight_fetcher.py` —
  `OvernightDataFetcher` default `lookback_days = 5` → `10` (line 38). The
  `_compute_sigma` formula and its `len(series) < 5` guard are unchanged.
- Rationale: run.log:317 shows the same fetcher already obtains 8 bars with a
  10-day window; the guard then yields 7 returns and a real standard
  deviation. The +0.64% move currently degenerates to z = 0.0
  (overnight_fetcher.py:113-114), which simultaneously kills the magnitude
  criterion and inflates recency to 1.0. C1 restores the information already
  present in the fetch without new fetches or logic.
- Why smallest: a single default-value change. No formula change, no new
  component, no contract change; the alternative (relaxing the guard to
  `len(series) < 4`) is a weaker form that would estimate sigma on 3 returns.
- Expected runtime effect: GC=F, DX-Y.NYB, ES=F, BZ=F receive
  `z = single_return / std(daily returns)` instead of 0.0.
  - `magnitude` passes only for genuine ≥2σ moves (classifier gate unchanged);
    a +0.64% one-day move with σ ≈ 0.5-0.9% yields |z| ≈ 0.7-1.3 — below
    threshold (correctly: it remains a sub-2σ move).
  - `temporal_recency = 1/(1+|z|)` (collector.py:160) becomes < 1.0 for real
    moves — the preserved formula now receives honest inputs.
  - Two-gate behavior change: WATCH/WEAK_SIGNAL become data-dependent instead
    of impossible.

### C2 — Data-driven positioning breadth (root cause of F3, G1)

- Affected component: `src/signal_assessment/assembler.py` — the positioning
  block (line 112): the constant `passed=True` breadth criterion is replaced
  by a pass condition derived from the snapshot's live field
  (e.g. `abs(etf_flow_change_pct) > 1.0`, reusing the existing
  `ETF_FLOW_THRESHOLD_PCT` constant from `volume.py:7`). All other positioning
  criteria are untouched (persistence |cot_z| ≥ 1, magnitude |cot_z| ≥ 2,
  narrative, volume remain as-is).
- Rationale: the audits prove the stub item's entire qualification is this one
  hard-coded value (FILTERING §5.2); the only live positioning field is ETF
  flow (positioning.py:43-70). Tying the breadth criterion to the live field
  makes survival contingent on genuine data and reuses an existing threshold,
  so no new threshold is invented.
- Why smallest: one `CriterionScore` construction changes from a constant to a
  derived boolean. No contract change (CriterionScore fields unchanged), no
  new gate, no change to the W6 keep-set (the existing IGNORE drop at
  collector.py:83-85 does the removal).
- Expected runtime effect: in the run's data state (COT stub z=0, ETF flow
  |Δ| ≤ 1%) the positioning observation has 0 positives → IGNORE →
  dropped. **Stub evidence no longer survives.** When live GLD/IAUM flow
  exceeds 1% (the live path already exists), the item returns as WATCH, and
  with volume confirmation as WEAK_SIGNAL 0.5 — genuine flow still reaches the
  pipeline. Downstream: the ETF_FLOW set may not form in stub-only runs; with
  one supporting set the mean (builder.py:110-112) then equals that set's
  weight and `evidence_quality` changes numerically — a consequence of
  corrected inputs, not of any change to W8/W10/W13 logic.

### C3 — Real persistence evaluation (root cause of F2, enables G2/SIGNAL)

- Affected components:
  1. `src/pre_market/contracts.py` — additive field on `OvernightPriceChange`
     (e.g. `persistence_days: float = 0.0`, defaulted). Existing fields,
     constructors, and consumers are untouched; all current call sites keep
     working unchanged (backward-compatible extension).
  2. `src/pre_market/overnight_fetcher.py` — populate the field from the
     series already held in `_fetch_yfinance_change`/the FRED path: count of
     consecutive same-direction daily returns ending at the last bar
     (direction = sign of each daily return). No new fetch, no new I/O.
  3. `src/signal_assessment/assembler.py` — pass the real value
     (`deviation_days = change.persistence_days`) and a per-instrument
     persistence type instead of the hard-coded `1.0`/`"ETF"` (line 44-47).
     The instrument→type mapping reuses the existing `NOISE_FILTERS` keys
     (COMEX for XAU/USD, DXY for DXY/EUR/USD/USD/JPY, `gold_real_yield` for
     the yield series, ETF fallback), restoring the Meth.§7 thresholds that
     `persistence.py:12-18` already defines.
- Rationale: the audits show persistence is structurally disabled by the
  hard-coded 1-day/ETF call (FILTERING §5.3), which caps every observation at
  WATCH and makes SIGNAL syntactically unreachable. `PersistenceTracker`
  itself already implements the correct noise/signal thresholds
  (persistence.py:36-75) — only its inputs are wrong. C3 supplies the real
  inputs.
- Why smallest: the evaluation logic, thresholds, and persistence contract are
  all reused verbatim; the only additions are one defaulted contract field
  (populated from data already in hand) and one small type-mapping constant.
- Expected runtime effect:
  - Single-day moves stay `passed=False` (1 ≤ noise thresholds: ETF 1d, COMEX
    7d, DXY 1d — same Meth.§7 semantics), so one-day noise is still filtered
    exactly as before.
  - A multi-day persistent move (e.g. gold up 2+ consecutive days) now passes
    persistence → with breadth confirmed and magnitude ≥2σ (C1) the
    observation reaches `positive_count ≥ 2 + persistence` or `≥ 3` →
    **SIGNAL** (classifier.py:58, confidence 0.5+0.1·n, capped 0.95), and
    `≥ 2` without persistence → **WEAK_SIGNAL** (0.5). Genuine signals reach
    the upper tiers; the confidence caps (classifier caps) and
    `composite_weight = confidence × 0.8` are unchanged, so the W7 weights
    stay within the existing [0, 1] clamp and the 0.88 structural ceiling
    (COLLECTION §5, "structural ceiling").

### C4 — Bias-map value correction (secondary, from audit findings)

- Affected component: `src/evidence_collection/collector.py:46` —
  `INSTRUMENT_TO_REGIME_BIAS["USD/JPY"]` value `"bulllish"` → `"bullish"`.
- Rationale: both audits record the misspelling as an incidental fact
  (COLLECTION §6/§8; FILTERING §8); a future USD/JPY item would currently be
  neither supporting nor contradicting a bullish/bearish majority
  (COLLECTION §6). It did not affect this run (no USD/JPY item reached W6).
- Why smallest: one map-value correction; no logic, contract, or signature
  change.
- Expected runtime effect: none for the audited run; a future USD/JPY evidence
  item would classify with the valid bias value instead of an unrecognized
  one. Optional — G1/G2 do not depend on it.

## 4. End-to-end effect trace (arithmetic consequences, audit values)

- Stub path (this run's data state): positioning breadth now data-driven (C2)
  → 0 positives → IGNORE → dropped (collector.py:83-85). ETF_FLOW set does
  not form from a stub. Remaining GENERAL evidence (anomaly-derived WATCH,
  weight ≈ 0.5988 per COLLECTION §4) is the only set; `evidence_quality` =
  that set's weight (builder.py:110-112 over 1 set). Decision effects flow
  only through the unchanged drivers (engine.py:180-182,207).
- Genuine-signal path: +0.64% gold move with a 10-day window (C1) yields a
  real |z| (sub-2σ ⇒ WATCH at best for a lone move; ≥2σ ⇒ WEAK_SIGNAL with
  breadth). With 2+ days of persistence (C3), the same observation can reach
  SIGNAL. Recency drops from 1.0 to `1/(1+|z|)` — the unchanged
  `raw×0.5 + recency×0.3 + prov×0.2` formula then produces honest set weights.
- Preserved: classifier caps and rules (classifier.py:58-77), `regime_weight`
  default 0.8, W6 keep-set and counters, dedup rule, bias-split, consensus/
  conflict, supporting-set selection (constructor.py:93-101), W10 recompute,
  all decision-driver weights (engine.py) — none touched by C1-C4.

## 5. Explicitly out of scope (audit facts, intentionally not addressed)

These findings are recorded but require no change for G1-G2; touching them
would enlarge the design:

- Per-item persistence/serialization absence (COLLECTION §7, FILTERING §8) —
  observability only, not behavior.
- KG=None wiring making dedup inert (COLLECTION §3.6) — does not cause stub
  survival or signal suppression.
- `LATE_CYCLE` absent from `REGIME_EXPECTED_EVENT_TYPES` / missing-evidence
  no-op (COLLECTION §6) — counter-evidence side, not collection/filtering.
- `counter_evidence_quality = 1 − penalty` semantics (COLLECTION §6) —
  decision-input semantics; G1-G2 are upstream of it.
- Anomaly-derived residual evidence (E2 Low, COLLECTION §5): its survival
  follows the same WATCH path but is not stub data; addressing it would change
  W5 anomaly criteria and is larger than the minimum.
- The ~81% constant-term share of set weight (COLLECTION §6) — would require
  changing the weighter formula, which G4 forbids.

## 6. Preservation checklist

| Surface | Status under C1-C4 |
|---|---|
| `Evidence` / `EvidenceCollection` / `SignalAssessment` / `CriterionScore` / `PositioningSnapshot` contracts | Unchanged (one additive defaulted field on `OvernightPriceChange`, C3) |
| `composite_weight = base_confidence × 0.8` | Unchanged |
| `temporal_recency = min(max(1/(1+|z|), 0.1), 1.0)` | Unchanged formula; input z now real (C1) |
| `net_institutional_weight = raw×0.5 + recency×0.3 + prov×0.2` | Unchanged (weighter.py:37-51) |
| Classifier rules and confidence caps | Unchanged (classifier.py:58-77) |
| W6 NOISE/IGNORE filter and keep-set | Unchanged (collector.py:79-92) |
| Dedup, bias split, consensus/conflict, supporting-set selection | Unchanged |
| Decision drivers, weights, thresholds | Unchanged (engine.py:180-182,207; finalize drivers) |
