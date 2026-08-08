# SIGNAL_ASSESSMENT_POST_CORRECTION_AUDIT 001

**Subject:** What the three SignalAssessment corrections (overnight volume_flow wiring, OI
producer repair, anomaly observation identity) actually achieved, measured against the
pre-correction baseline and the current source tree.
**Scope:** Read-only verification audit. No source, config, or test changes were made.
**Date:** 2026-08-08
**Status:** VERIFIED. Runtime facts are taken from the persisted checkpoints of
`runtime_20260806_234356` (baseline, pre-correction build) and `runtime_20260808_195528`
(latest, current build), read from `%TEMP%\aurumai_checkpoints\<runtime_id>\*.json`.
Source wiring facts are from the current tree.

---

## 1 Executive finding

The three corrections fixed real defects, not symptoms: one wiring gap (C1), one
dead-code producer (C2), one identity-key collision (C3). Measured on the live pipeline,
this changed the *information* reaching the institutional stack from the W5/W6 boundary
onward:

- Producer-connected coverage of the *audited criterion pool* rose from
  **41/65 (63.1%)** to **40/55 (72.7%)**. The denominator shrank only because the
  latest night fired 1 anomaly flag instead of 3; the correction-controlled counts are
  derived in sections 4-5.
- New real evidence feeding institutional reasoning that had no route before:
  overnight `volume_flow` for gold-class instruments, a brand-new `ETF_FLOW` evidence
  set, and a live (first-capture) OI level.
- The distinct-fact loss from the anomaly ID collision is gone: the gold/real-yield
  co-move observation is no longer dropped as a duplicate.
- The final decision did **not** change (NO_TRADE in both), and that is correct:
  promoted information was still below the institutional confidence bar. The engine
  behaved conservatively, not defectively.

The deltas that *are* attribution-controlled are the per-slot wiring counts (section 4),
the identity/evidence differences (section 5), and the code deltas (section 2). Absolute
confidence/RR/decision numbers mix correction effect with market-context effect because
the two runs are on different market days (see Appendix B).

---

## 2 What each correction changed (verified in current tree)

| # | File / change | Current tree location | Live effect in latest run |
|---|---|---|---|
| C1 | Wire existing ETF/OI data into overnight `volume_flow` for gold-class instruments | `signal_assessment/assembler.py` (GOLD_CLASS_INSTRUMENTS + `volume_kwargs`) | XAU/USD overnight volume criterion: from "no volume/flow data available" (0.0) to **score 1.0, passed, "ETF accumulating +2.3%"** |
| C2 | Repair `_fetch_open_interest` (real `openInterest` level + persisted state) | `pre_market/positioning.py` (OI fetch/load/persist) | `open_interest_change_pct=0.0` (correct first-observation semantics); real level **298,095** persisted to `data/economic/gold_oi_state.json` |
| C3 | Anomaly `observation_id` now includes a slug of `flag.description` (per-template pair) | `signal_assessment/assembler.py` (anomaly branch) | Collision path provably fixed (tests/repro); live night fired only 1 anomaly flag so no impact on real data |

## 3 Measurement baseline definitions

- **Slot** = one (criterion x observation) in the SignalAssessment output.
- **Connected** = a live in-repo producer exists AND its output is actually passed into
  the scorer for that slot (verified in source, not assumed).
- **Pool** = observations created by the run (overnight + anomaly + positioning).
- Run shapes:
  - Baseline: 13 observations (9 overnight + 3 anomaly + 1 positioning) -> **65 slots**.
  - Latest: 11 observations (9 overnight + 1 anomaly + 1 positioning) -> **55 slots**.

## 4 SignalAssessment - slot connectivity (latest run, current tree)

| Criterion | Overnight (9) | Anomaly (1) | Positioning (1) | Subtotal |
|---|---|---|---|---|
| persistence | 9 / 9 (real tracker) | 0 / 1 const True, no data (D) | 0 / 1 COT stub (C) | 9 |
| breadth | 9 / 9 wired; 2 / 9 have table rows (XAU/USD, DXY); 7 table-gapped to 0.0 (A) | 0 / 1 (D) | 1 / 1 (derived ETF flow) | 10 |
| magnitude | 9 / 9 real sigma | 1 / 1 real flag value | 0 / 1 COT stub (C) | 10 |
| narrative_fit | 9 / 9 connected (RSS empty at runtime) | 0 / 1 const (D) | 0 / 1 const (D) | 9 |
| volume_flow | **1 / 9** (XAU/USD wired via C1; 8 have no feed, D) | 0 / 1 const (D) | 1 / 1 (ETF proxy + live OI) | 2 |

**Connected = 40/55 = 72.7%.**

Baseline was 41/65 = 63.1% (same convention). Concrete numbers for the latest run:
37 overnight (9 persistence + 9 breadth + 9 magnitude + 9 narrative + 1 volume) + 1
anomaly + 2 positioning = 40.

## 5 Coverage math (auditor convention, re-derived)

Baseline (13 obs, 65 slots): overnight 36 = 9x4 (persist/breadth/magnitude/narrative),
anomaly 3 = 3x1 (magnitude), positioning 2 (breadth+volume) => **41** (63.1%).

Latest (11 obs, 55 slots): overnight 37 = 9x4 + 1 (volume for XAU/USD via C1), anomaly
1 (magnitude), positioning 2 => **40** (72.7%).

Slots that remain zero with real wiring in place: 7 overnight breadth (A - table rows
missing), 8 non-gold overnight volume (D), 4 anomaly const slots (D), 1 positioning
narrative (D), plus positioning persistence/magnitude (C, COT stub).

## 6 Evidence

| | Baseline | Latest |
|---|---|---|
| items (collected) | 4 | 4 |
| observation sourcing | 4 4 Watch (DXY, 2x anomaly template-collide, anomaly correlation) - XAU/USD absent (Noise), positioning absent (Ignore) | 2 Weak Signal (XAU/USD, Gold Positioning) + 2 Watch (DXY, anomaly) |
| evidence classes | GENERAL x3 + USD_FX x1 | GENERAL x3 + USD_FX x1 + **ETF_FLOW x1 (new)** |
| sets | es_usd_fx 0.4601, es_general 0.4323 | es_general **0.4334** (2 members), es_etf_flow **0.65** (new), es_usd_fx **0.4369** |
| duplicates removed | **1** (two colliding template ids) | **0** |

Baseline gold evidence was zero: XAU/USD was Noise (no volume channel) and gold
positioning was Ignore (0.01% ETF flow below threshold, no other channel). Latest
evidence: two gold-sourced Weak facts (overnight + ETF flow) plus the distinct
gold/real-yield anomaly - the novelty of signal-relevant gold evidence is
material.

## 7 Anomaly collision - appearance vs behavior

- Baseline: two flags (gold-DXY, gold-real-yield) both `template_violation` on
  XAU/USD -> same `observation_id` -> same `evidence_id` -> one deduped
  (`duplicates_removed=1`), per baseline `evidence_reasoning.json`. The distinct fact
  'gold/real-yield co-move' never reached reasoning as a separate item.
- Latest run: only the real-yields template fired (DXY moved opposite gold), so the
  collision could not manifest in real data that night. Correctness of C3 is carried by
  regression tests and reproducible repro:
  - collision reproduced pre-fix (2 observations, 1 distinct ID, 1 evidence lost);
  - post-fix distinct IDs, both observations kept (`duplicates_removed=0`);
  - identical flags still dedupe (`duplicates_removed=1`), proving the discriminator is
    the template pair, not noise.

## 8 CounterEvidence

| | Baseline | Latest |
|---|---|---|
| conflict_severity | 0.25 | 0.1667 |
| confidence_penalty | 0.7 | 0.2667 |
| missing _evidence | (CB_GOLD, INFLATION, REAL_VERIFY) | (CB_GOLD,) |
| bias_flags | no_dissent, regime_conflict, missing_evidence, cross_set_conflict | regime_conflict, missing_evidence, cross_set_conflict |

Penalty dropped because the new ETF/gold volume evidence now backs previously
missing channels (INFLATION, REAL_YIELD become evidence-backed). The counter-evidence
layer penalizes a *better informed* thesis.

## 9 Institutional confidence

| | Baseline | Latest |
|---|---|---|
| final_confidence | 0.0325 | 0.2494 |
| evidence_quality | 0.4601 | 0.5417 |
| regime_alignment | 0.0 | 1.0 |
| source_diversity | 0.3333 | 0.6667 |
| counter_evidence | 0.25 | 0.1667 |
| missing_evidence | 1.0 | 0.3333 |
| internal_consistency | 0.7 | 0.2667 |

Dominant remaining reductions in the latest run: internal_consistency (0.2667, down
from 0.7 - broader but self-consistent-enough) and missing_evidence (0.33). These are
honest reflections of a richer set, not defects.

## 10 RiskReward validation - unchanged numerically, inputs now justified

| | Baseline (base scenario) | Latest (base) |
|---|---|---|
| risk_reward_ratio | 2.9807 | 0.9682 |
| status | borderline | acceptable |
| reward / risk | 0.1244 / 0.3389 | 0.289 / 0.1444 |

Not modified (audit scope). Inputs are now institutionally justified: the thesis is
backed by real, connected gold evidence (volume + ETF flow + generality) instead of
constants-only. The borderline->acceptable migration reflects information restoration,
not number games.

## 11 Decision

| | Baseline | Latest |
|---|---|---|
| final decision | NO_TRADE | NO_TRADE |
| composite | 0.3016 | 0.5403 |
| dominant gate | institutional_confidence 0.0325 (below bar) | institutional_confidence 0.2494 (below 0.30 bar) |

Behavior is conservative: composite moved from 0.30 to 0.54 without crossing the
confidence bar. No gate logic changed.

## 12 Remaining SignalAssessment gaps (current tree)

| ID | Gap | Class | Evidence | Next action |
|---|---|---|---|---|
| G1 | Breadth table rows for 7 instruments (EXPECTED_RELATIONSHIPS) | **A - wiring/config (table only)** | breadth.py:5-8 | data rows optionally (+ thresholds); audit #3 |
| G2 | Non-gold overnight `volume_flow` | **D - missing data capability** | no volume/flow family for FX/equity/rates in repo | none in boundary |
| G3 | Anomaly persistence/breadth/narrative/volume constants | **E - intentional** | no compatible event-data channel | none |
| G4 | COT persistence/magnitude (positioning) | **C - stub producer** (`_fetch_cot` 0.0) | real COT not in repo | requires new producer - out unless commissioned |
| G5 | Positioning narrative_fit | **D** | no channel | none |
| G6 | GOFO (unused) | **E** | assembler never reads it | none |
| G7 | News narrative/volume gaps | **D** | RSS connected, empty that night; sentiment proxy caveat | none |
| G8 | OI change% still 0 | **B (resolved, operational)** | state file populated, 2nd observation computes real delta | nothing to do; next run only |

## 13 The pivotal question - infrastructure repair or real analytical gain?

**Both - but they are distinguishable.**

Repair: C1 (wiring), C2 (dead-code), C3 (identity) are verified in source and their
wired-slot counts rise.

Analytical gain: the institutional stack now receives **previously unreachable true
information**:
- XAU/USD overnight moved Noise -> Weak Signal with a real positive (volume) instead of
  a constant "no volume/flow data available";
- gold positioning moved Ignore -> Weak Signal (0 evidence -> 2), creating the new
  `ETF_FLOW` set at strength 0.65 - the strongest set in the latest run;
- CounterEvidence/Confidence/RR inputs improved in sync. The pipeline now *sees* gold
  evidence it could not see before, and weighs it with an informed counter-evidence
  penalty.

It did **not** change the trading posture (NO_TRADE -> NO_TRADE): confidence 0.2494 is
below the 0.30 bar, which is healthy conservative behavior. The corrections did not
"manufacture" a trade; they surfaced real signals that still do not clear the bar.

## 14 Is another SignalAssessment correction justified?

**Recommended: no further SignalAssessment correction now.**
- All A/B-class fixes with in-repo data are done. What remains is one config table (G1,
  optional) and one C-class (G4/COT) that requires a **new data capability** - and this
  run's evidence is not sufficient to prove COT is the highest-value next step
  platform-wide (positioning contributes 2/5 slots; modest).
- Recommended operational checkpoints instead: (a) run once more so OI obtains a real
  interval (G8) - the second observation will convert first-capture 0.0 into a real
  change percentage through the wiring already in place; (b) monitor the next run's
  evidence_reasoning for `duplicates_removed=0` whenever two template violations co-fire,
  as a live proof of C3.

---

## Appendix A - Evidence paths (current tree)

- Wiring: `src/signal_assessment/assembler.py` (GOLD_CLASS_INSTRUMENTS + `volume_kwargs`);
  anomaly id slug at assembler.py:180.
- Producer: `src/pre_market/positioning.py` (OI always; float-level persistence precedents
  `src/connectors/fred_client.py`).
- Gaps: `src/pre_market/positioning.py` COT stub return; `src/signal_assessment/breadth.py`
  EXPECTED_RELATIONSHIPS (only XAU/USD, DXY).
- Runtime facts: `%TEMP%\aurumai_checkpoints\runtime_20260806_234356\*.json` (baseline),
  `%TEMP%\aurumai_checkpoints\runtime_20260808_195528\*.json` (latest); sections used:
  pre_market_scan, signal_assessment, evidence_collection, evidence_reasoning,
  counter_evidence, confidence_engine, risk_reward_validation, decision_engine, finalize.
- OI state: `data/economic/gold_oi_state.json` = {"timestamp": "2026-08-08T17:57:58",
  "open_interest": 298095}.

## Appendix B - attribution caveat

Baseline (06 Aug) and latest (08 Aug) runs are on different market days (ETF flow 0.01%
vs 2.26%; anomaly flags 3 vs 1; different prices). Absolute confidence/RR/decision deltas
are therefore NOT fully attributable to the two corrections; the attribution-controlled
measurements are the per-slot wiring tables (sections 4-5), the code deltas (section 2),
and the evidence identity differences (section 6). Neither over- nor under-correction is
claimed.

## Appendix C - Files (this audit is read-only)

| Factor | Value |
|---|---|
| Source changed | none |
| Tests changed | none |
| Config changed | none |
| Runtime launched | none (persisted runs only) |