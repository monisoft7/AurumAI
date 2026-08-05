# CONFIDENCE_PENALTY_AUDIT_001 — Engineering Rationale for `confidence_penalty` in `institutional_support = mean(weight × consensus) × (1 − confidence_penalty)`

**Run audited:** `outputs/2026-08-04/runtime_20260804_230820` (`finalize.json`; `git_commit` `78c9ad4`)
**Objective:** determine where `confidence_penalty` is computed, which conditions increase it, whether the runtime value `0.2` is fully justified, and how to classify the `0.2` (evidence-driven / empirically calibrated / specification-driven / arbitrary implementation choice).
**Method:** read-only; code, tests, docs, ADRs, and run output inspected. No code or test modified. No fixes or recommendations.

---

## 1. Where `confidence_penalty` is computed

`confidence_penalty` is computed in exactly one place: `BiasAnalyzer.compute_confidence_penalty` in `src/counter_evidence/analyzer.py:47-56`.

| Step | Location |
| --- | --- |
| Formula definition | `src/counter_evidence/analyzer.py:47-56` |
| Called from | `CounterEvidenceAssessor.assess` → `src/counter_evidence/assessor.py:49-53` |
| Stored on contract | `CounterEvidenceAssessment.confidence_penalty` — `src/counter_evidence/contracts.py:35` |
| Domain validation | `[0, 1]` — `src/counter_evidence/contracts.py:98-99` |
| Consumed in `institutional_support` | `_compute_institutional_support` — `src/thesis_construction/builder.py:131-137`, multiplier `(1 − confidence_penalty)` at `builder.py:135` |
| Persisted (derived form) | `counter_evidence_quality = 1 − confidence_penalty = 0.8` — `finalize.json:44-49` |

The exact formula (`analyzer.py:52-55`):

```
penalty = conflict_severity * 0.4
penalty += len(bias_flags) * 0.1
if regime_conflict:
    penalty += 0.2
clamp: max(0.0, min(round(penalty, 4), 1.0))     # analyzer.py:56
```

`confidence_penalty` itself is **not persisted directly**; `finalize.json` records only the downstream driver `counter_evidence_quality` value `0.8` (`finalize.json:45-49`), from which `penalty = 1 − 0.8 = 0.2` is derived. The value is reconstructed in audits from the formula plus the observed evidence state (see §4).

---

## 2. Conditions that increase `confidence_penalty`

Three additive terms, each with a fixed literal weight in `analyzer.py:52-55`:

| # | Term | Weight | Condition that increases it | Source of the condition's inputs |
| --- | --- | --- | --- | --- |
| 1 | `conflict_severity × 0.4` | `0.4` per unit severity | Any cross-set contradiction. `conflict_severity` is computed by `compute_conflict_severity` (`analyzer.py:29-44`) as `round(cross_ratio × 0.5 + avg_conflict × 0.5, 4)`, where `cross_ratio = n_contradicting / n_sets` and `avg_conflict` = mean `EvidenceSet.conflict_score`. `contradicting_ids` come from `ConflictDetector.cross_set_conflicts` (`src/counter_evidence/detector.py:33-69`). | `analyzer.py:29-44`; `detector.py:33-69` |
| 2 | `len(bias_flags) × 0.1` | `0.1` per flag | Every flag present in `bias_flags` adds `0.1`. Flags are appended in `CounterEvidenceAssessor.assess` (`assessor.py:25-51`) when heuristics fire: `confirmation_bias` (all sets agree or ≤ 1 set, `analyzer.py:15-20`), `no_dissent` (all `conflict_score == 0.0`, `analyzer.py:23-27`), `cross_set_conflict`, `source_concentration`, `missing_event_types`, `regime_conflict` (via `ConflictDetector.regime_conflict`, `detector.py:19-26`, `REGIME_EXPECTED_BIAS`). | `assessor.py:25-51`; `analyzer.py:15-27`; `detector.py:19-26` |
| 3 | `0.2` (flat) | `0.2` | `regime_conflict` truthy, i.e. evidence bias contradicts the regime-expected bias (`detector.py:19-26`). | `analyzer.py:54-55`; `detector.py:19-26` |

So `penalty` increases monotonically with: any cross-set contradiction severity; each additional bias flag; and any regime conflict. `penalty` is capped at `1.0` (clamp test at `tests/test_counter_evidence.py:319-321`).

---

## 3. Which conditions were active in the latest run

For `runtime_20260804_230820` (evidence reconstructed in `CONFIDENCE_AUDIT_001.md` §8 and `INSTITUTIONAL_SUPPORT_AUDIT_001.md` §3):

| Term | Run value | Active conditions |
| --- | --- | --- |
| `conflict_severity × 0.4` | `0.0 × 0.4 = 0.0` | No contradiction: all evidence sets single-direction (bullish), no `contradicting_ids`; `conflict_severity = 0.0` |
| `len(bias_flags) × 0.1` | `2 × 0.1 = 0.2` | Exactly two flags: `confirmation_bias` (all sets agree) and `no_dissent` (all `conflict_score = 0.0`) |
| regime-conflict flat | `0.0` | `regime_conflict = False`; `LATE_CYCLE` is not a key in `REGIME_EXPECTED_BIAS` (`detector.py:19-26`), so no regime expected-bias fires |
| **Total** | **`0.2`** | ⇒ multiplier `(1 − 0.2) = 0.8` |

The `0.2` is therefore **fully determined by the formula given the evidence state**: two bias flags × `0.1`, zero contribution from the other two terms. This matches the persisted `counter_evidence_quality = 0.8` (`finalize.json:45-49`) and the `institutional_support ∈ [0.4551, 0.48752]` interval derived in `INSTITUTIONAL_SUPPORT_AUDIT_001.md` §4 (upper bound `0.6094 × 0.8 = 0.48752`).

---

## 4. Is the runtime `0.2` justified?

**Yes, but only in the narrow, deterministic sense:** given (a) the implemented formula at `analyzer.py:52-55`, and (b) the observed evidence state (`{confirmation_bias, no_dissent}`, `conflict_severity = 0.0`, no regime conflict), the value `0.2` follows mechanically. It is reproducible, clamped to `[0,1]`, and consistent with all persisted outputs.

**No in the broader sense:** the *magnitude* `0.2` is not supported by any spec, ADR, calibration study, or empirical derivation found in the repository (see §5). The per-flag weight `0.1` (and the `0.4` severity weight, `0.2` regime-conflict increment) are hardcoded literals with no documented provenance.

---

## 5. Search results — why is the default `0.2`?

### 5.1 Contracts
- `CounterEvidenceAssessment.confidence_penalty: float` declared at `src/counter_evidence/contracts.py:35`; validation `0.0 ≤ confidence_penalty ≤ 1.0` at `contracts.py:98-99`. **No formula or rationale in contracts.**

### 5.2 Architecture / design docs
- `docs/audit/Architecture-Audit-A1.md:81-87` — `counter_evidence` described only as "W7 conflict resolution — `BiasAnalyzer`, `CounterEvidenceAssessor`, `ConflictDetector`, `contracts`". No formula.
- `docs/audit/Architecture-Audit-A1.5.md:99-103,111` — records the counter-evidence package as a single bias-detection heuristic ("one bias-detection heuristic"; `analyzer.py:15` confirmation_bias; `assessor.py:33-34` appends flag) and, as finding A-004, that "no checklist/remediation" exists. No penalty-weight rationale.
- `docs/design/CONFIDENCE_PROVENANCE.md:55,80` — documents only the *downstream* multiplication of `institutional_support` by penalties in `ConfidenceComputer.compute`; does not document the penalty formula or weights.
- `docs/PROJECT_SCOPE_V1.md:39` — lists W7 `counter_evidence` as in scope; no formula.

### 5.3 ADRs
- `docs/adr/` contains 17 ADRs (`ADR-0001` through `ADR-0013` plus reports). **None mention `confidence_penalty`, the bias-flag penalty, or any penalty formula** (grep for `penalty` / `confirmation_bias` / `no_dissent` / `bias flag` over `docs/adr` returned no matches). The closest related ADRs concern evidence weighting (`ADR-0010`) and institutional memory (`ADR-0011`), neither of which specifies this penalty.

### 5.4 Source comments / docstrings
- `analyzer.py:11-12` class docstring: "Analyzes confirmation bias, missing evidence, and computes contradiction severity and confidence penalty." No rationale for the numeric weights.
- `analyzer.py:16,24` method docstrings state only the *trigger conditions*, not the weight rationale.

### 5.5 Tests
- `tests/test_counter_evidence.py` — verifies trigger semantics: `confirmation_bias` (`:259-275`), `no_dissent` (`:277-289`), conflict severity (`:291-305`), and penalty behaviors: `penalty == 0.0` for `(0.0, [], False)` (`:307-309`), `penalty > 0.0` with conflict (`:311-313`), **`penalty == 0.2` for regime-conflict-only `(0.0, [], True)`** (`:315-317`), clamp `≤ 1.0` (`:319-321`), assessor integration (`:338-369`). **No test pins the `0.2` two-flag default** — the closest scenario (`test_assess_no_conflict`, `:338-348`, two all-bullish zero-conflict sets ⇒ would compute `2 × 0.1 = 0.2`) asserts only flag membership, `regime_conflict is False`, and `conflict_severity == 0.0`, not the penalty value.
- `tests/test_thesis_construction.py:308-322` — exercises `confidence_penalty = 0.5` as an input; pins that the penalty flows to `thesis.confidence_inputs` (`:322`), not the `0.2` default.
- `tests/test_thesis_update.py:261` — `support == 0.72` for `weight=0.8, consensus=0.9, penalty=0`; no `0.2` default.
- `tests/test_confidence_engine.py:41,267,282,294,434,445,463,482,494,625` — penalty values passed only as fixtures; no default-penalty assertion.
- Conclusion: tests encode *behavioral* constraints (triggers, monotonic increase, clamp, `0.2` for regime conflict) but **no test pins the two-flag `0.2` default or the weight magnitudes as specified requirements**.

### 5.6 Prior audits
- `docs/audit/NO_TRADE_AUDIT_001.md:67-68` — records the formula and its consumers; no rationale.
- `docs/audit/CONFIDENCE_AUDIT_001.md:75,103,118,167,169` — reconstructs penalty `0.2` for the run; treats `0.2` as the internal-consistency penalty consumed with weight `0.40`.
- `docs/audit/INSTITUTIONAL_SUPPORT_AUDIT_001.md:92-94` — states the `(1 − confidence_penalty)` factor "is a chosen composition. The only property used is that the factor is in `[0,1]`"; classifies the `0.8` multiplier as a hardcoded implementation choice.

---

## 6. Classification of the `0.2` default

| Category | Verdict | Basis |
| --- | --- | --- |
| **Evidence-driven** | **No (magnitude); Yes (occurrence)** | The *occurrence* of two flags is driven by evidence semantics (`analyzer.py:15-27`; tested at `tests/test_counter_evidence.py:259-289`). The *magnitude* `0.1` per flag is not derived from any evidence statistic, calibration, or backtest. |
| **Empirically calibrated** | **No** | No calibration study, experiment, or OOS/backtest of the penalty weights found in `docs/`, ADRs, or tests. `CONFIDENCE_PROVENANCE.md` documents OOS calibration only for `cap_oos` (`CONFIDENCE_PROVENANCE.md:58,83`), not for the penalty weights. |
| **Specification-driven** | **No** | No spec, design doc, or ADR states the formula or the `0.4`/`0.1`/`0.2` weights. The single literal pinned in a test is the regime-conflict increment `0.2` (`tests/test_counter_evidence.py:315-317`), which is a test-pinned implementation behavior, not a spec requirement. |
| **Arbitrary implementation choice** | **Yes** | The weights `0.4` (`analyzer.py:52`), `0.1` (`analyzer.py:53`), and `0.2` (`analyzer.py:55`) are hardcoded literals with no documented rationale anywhere in the repo; consistent with the prior classification of the resulting `0.8` multiplier in `INSTITUTIONAL_SUPPORT_AUDIT_001.md:92-94`. |

**Bottom line for this run:** `confidence_penalty = 0.2` is *deterministic and reproducible* given the formula (`analyzer.py:47-56`) and the evidence state (two flags, no severity, no regime conflict), and it is consistent with every persisted output (`finalize.json:45-49`; `institutional_support ≤ 0.6094 × 0.8 = 0.48752`). The value is **not** evidence-driven, empirically calibrated, or specification-driven in magnitude; it is the product of an arbitrary (hardcoded) per-flag weight of `0.1` times the two flags present.

---

## 7. Observability limitations

- `confidence_penalty` is not persisted in `finalize.json`; only the derived driver `counter_evidence_quality = 0.8` is recorded (`finalize.json:45-49`). Reconstructing the penalty requires the formula (`analyzer.py:47-56`) plus the evidence state (bias flags, conflict severity, regime conflict), the latter not persisted in the run output and derived in prior audits (`CONFIDENCE_AUDIT_001.md` §8).
- The bias flags that produced the two `0.1` terms originate from the same evidence set and are correlated with the `no_dissent` state (all-zero `conflict_score`), but the formula treats each flag as an independent additive `0.1` with no interaction term (`analyzer.py:53`).
