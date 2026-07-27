# Reference Department Implementation Template

## 1. Purpose

This document defines the canonical engineering implementation standard for every AurumAI institutional intelligence department. It is not architecture (see `Central-Bank-Intelligence.md`, `Cross-Asset-Intelligence.md`). It is not governance (see `PROJECT_CONSTITUTION_V2.md`). It is the engineering playbook that translates both into a repeatable, proven build sequence.

Every pattern documented here was extracted from the completed implementation of Central Bank Intelligence (Wave-1A through Wave-1G) and the partial implementation of Cross-Asset Intelligence (Wave-2A through Wave-2B). Nothing is invented. Nothing is theoretical. Every requirement maps to working code that passes 267+ tests.

Future departments — Capital Flow Intelligence, Narrative Intelligence, and any department created after them — must follow this template exactly.

---

## 2. Department Admission Criteria

A new institutional department may only be created if it satisfies **all** of the following conditions:

- **Adds a new institutional intelligence dimension.** The department must represent a distinct analytical domain that does not overlap with any existing department's charter.
- **Cannot be represented by an existing department.** If the proposed intelligence can be modeled as knowledge objects within an existing department, it must be added there instead.
- **Produces reusable knowledge objects.** The department must define frozen dataclass contracts that other departments and the reasoning pipeline can consume through the standard Evidence pathway.
- **Has clearly identifiable upstream data providers.** The department must have concrete, named data sources from which its knowledge objects are derived.
- **Has clearly identifiable downstream consumers.** At least one other department or the orchestration pipeline must consume the department's evidence output.
- **Improves institutional reasoning quality.** The department must demonstrably improve the institution's ability to produce accurate, well-reasoned decisions — not merely add analytical surface area.

If these conditions are not satisfied: **expand an existing department instead of creating a new one.**

Adding a knowledge object to an existing department costs one wave. Creating a new department costs seven waves minimum. The burden of proof is on the proposal to demonstrate that a new department is the only correct solution.

---

## 3. Department Lifecycle

```
Design
  │     Department charter drafted and ratified.
  │     Admission criteria verified.
  ▼
Infrastructure
  │     Wave A: contracts.py + repository.py + __init__.py
  │     Wave B: adapter.py
  ▼
Minimum Institutional Capability (MIC)
  │     Waves C–E: Three knowledge objects fully lifecycle-tested.
  │     Assessment triad established.
  ▼
Activation
  │     Wave G: OrchestrationContext fields, _run_{dept}(),
  │     OrchestrationReport field, analyze() wiring.
  ▼
Impact Validation
  │     Validation document: evidence flow analysis,
  │     weight impact assessment, architectural guardrails.
  ▼
Production
  │     Full regression suite passes. Completion docs written.
  │     CURRENT_STATE.md updated. Department is operational.
  ▼
Institutional Expansion
  │     Additional knowledge objects beyond the MIC triad.
  │     Each follows the same wave pattern (one wave per object).
  │     Enhances depth, not a prerequisite for operation.
  ▼
Maintenance
  │     Bug fixes, data source updates, confidence recalibration.
  │     No structural changes. No new contracts without a wave.
  ▼
Frozen
        Department's contract set and pipeline wiring are permanent.
        Modifications require a verified engineering defect plus
        Architecture Council approval (same rules as Frozen Core).
```

Every department progresses through these phases in order. No phase may be skipped. A department does not regress to a prior phase once it has passed the phase's gate.

---

## 4. Required Directory Structure

```
src/knowledge/{dept_code}/
    __init__.py          # Module re-exports: all contracts, constants, repository, adapter
    contracts.py         # Frozen dataclass contracts + domain constants
    repository.py        # JSON persistence with atomic writes
    adapter.py           # Evidence translation layer

tests/
    test_{dept_code}_{object_name}.py   # One test file per knowledge object

docs/
    architecture/{Department-Name}.md   # Department charter (ratified before Wave A)
    Wave-{N}A-Completion.md             # One completion doc per wave
    Wave-{N}B-Completion.md
    ...
    Wave-{N}G-Completion.md
```

**Reference — CBI:**
```
src/knowledge/cbi/__init__.py
src/knowledge/cbi/contracts.py
src/knowledge/cbi/repository.py
src/knowledge/cbi/adapter.py
tests/test_cbi_policy_bias.py
tests/test_cbi_forward_guidance.py
tests/test_cbi_rate_path.py
docs/architecture/Central-Bank-Intelligence.md
```

**Reference — CAI:**
```
src/knowledge/cai/__init__.py
src/knowledge/cai/contracts.py
src/knowledge/cai/repository.py
src/knowledge/cai/adapter.py
tests/test_cai_cross_asset_correlation.py
docs/architecture/Cross-Asset-Intelligence.md
```

No additional directories, no subdirectories within the department package, no utility modules. Four source files. One test file per knowledge object. One charter. One completion doc per wave.

---

## 5. Required Files

### 3.1 `contracts.py`

Contains all frozen dataclass contracts and domain constants for the department.

**Required elements:**

| Element | Pattern | CBI Reference |
|---------|---------|---------------|
| Base contract | `@dataclass(frozen=True)` class `{Dept}BaseContract` | `CbiBaseContract` |
| Domain contracts | `@dataclass(frozen=True)` inheriting base contract | `PolicyBiasScore`, `RatePathProjection`, `ForwardGuidanceRecord`, `LiquidityOutlook`, `GlobalMonetaryRegime` |
| Domain constants | String constants with `frozenset` validators | `VALID_CENTRAL_BANKS`, `VALID_DIRECTIONS`, `VALID_TIME_HORIZONS`, etc. |

**Base contract mandatory fields** (common contract framework from `Institutional-Knowledge-Contracts.md`):

```
confidence: float          # 0.00–1.00 institutional scale
valid_from: str             # ISO 8601 timestamp
valid_until: str            # ISO 8601 timestamp
time_horizon: str           # T0, T1, T2, T3, or T4
provenance: Provenance | None
evidence_references: list
cross_references: list | None
methodology_version: str | None
scenario_analysis: list | None
```

**Rules:**
- Every contract must be a frozen dataclass (`@dataclass(frozen=True)`)
- Every contract must inherit from the department's base contract
- Dict fields must be auto-frozen to `FrozenDict` via `__post_init__` using `object.__setattr__`
- Constants must use `frozenset` for validation sets
- No methods on contracts beyond `__post_init__` for field freezing

### 3.2 `repository.py`

Contains `{Dept}Repository` with exactly two methods per contract type: `save_{object}` and `load_{object}`.

**Required elements:**

| Element | Pattern | CBI Reference |
|---------|---------|---------------|
| Repository class | `{Dept}Repository` | `CbiRepository` |
| Save methods | Construct dict manually, call `serialize_provenance()`, call `atomic_write_json(path, payload)` | `save_policy_bias`, `save_rate_path`, `save_forward_guidance`, `save_liquidity_outlook`, `save_regime` |
| Load methods | `json.loads(path.read_text())`, call `deserialize_provenance()`, construct frozen dataclass | `load_policy_bias`, `load_rate_path`, `load_forward_guidance`, `load_liquidity_outlook`, `load_regime` |

**Rules:**
- All writes use `atomic_write_json` (write-to-temp then rename) — never direct file writes
- Provenance serialization uses the shared `serialize_provenance` / `deserialize_provenance` from `knowledge.integrity.provenance`
- Load methods use `.get()` with defaults for forward compatibility
- No query methods, no indexing, no search — repositories are pure persistence

### 3.3 `adapter.py`

Contains `{Dept}EvidenceAdapter` with one translation method per knowledge object.

**Required elements:**

| Element | Pattern | CBI Reference |
|---------|---------|---------------|
| Adapter class | `{Dept}EvidenceAdapter` | `CbiEvidenceAdapter` |
| Translation methods | `{object}_to_evidence(obj) -> Evidence` | `policy_bias_to_evidence`, `rate_path_to_evidence`, `forward_guidance_to_evidence`, `liquidity_to_evidence`, `regime_to_evidence` |

**Rules:**
- Every method is a pure translation — no side effects, no repository calls, no pipeline interaction
- Every method produces a canonical `Evidence` frozen dataclass (14 fields)
- `sample_count=1`, `average_return_pct=0.0`, `horizon_days=0` for all institutional evidence
- Provenance is passed through directly from the source contract
- All domain-specific fields are preserved in `Evidence.metadata`
- Evidence ID format: `{dept_code}_{object_type}_{key_identifier}`
- Event type format: `{DEPT_CODE}_{OBJECT_TYPE}` (e.g., `CBI_POLICY`, `CAI_CORRELATION`)
- Bias mapping must be explicit and documented — every domain value maps to exactly one of: `bullish`, `bearish`, `neutral`

### 3.4 `__init__.py`

Re-exports everything: all contracts, all constants, the repository class, and the adapter class. Defines `__all__` explicitly.

**CBI reference:** 107 lines, exports 52 names.
**CAI reference:** 96 lines, exports 44 names.

### 3.5 Test files

One test file per knowledge object: `tests/test_{dept_code}_{object_name}.py`

Every test file follows the same 5-group structure:

| Group | Tests | What it validates |
|-------|-------|-------------------|
| 1. Creation | 10-11 | Field construction, defaults, enum coverage, frozen immutability, base contract inheritance, optional field completeness |
| 2. Repository | 4 | Save/load roundtrip, all-fields preservation, null-optional roundtrip, raw JSON structure |
| 3. Adapter | 9 | Evidence output, bias mapping, provenance passthrough, confidence preservation, validity in metadata, domain fields in metadata, explanation format |
| 4. Aggregator Integration | 1 | 2-layer merge (department + event), layer counts, conflict-free coexistence |
| 5. Conflict Detection | 1 | Same `evidence_id` with different `bias` across layers triggers conflict logging |

**CBI reference:** 25 tests (PolicyBiasScore) + 30 tests (ForwardGuidanceRecord) + 27 tests (RatePathProjection) = 82 tests.
**CAI reference:** 24 tests (CrossAssetCorrelation).

---

## 6. Canonical Implementation Order

```
Department Charter (prerequisite — ratified in docs/architecture/)
       │
       ▼
   Wave A: Infrastructure
   (contracts.py + repository.py + __init__.py)
       │
       ▼
   Wave B: Evidence Adapter
   (adapter.py — one method per knowledge object)
       │
       ▼
   Wave C: Knowledge Object #1 Lifecycle Tests
   (test file #1 — full 5-group test suite)
       │
       ▼
   Wave D: Knowledge Object #2 Lifecycle Tests
   (test file #2 — full 5-group test suite)
       │
       ▼
   Wave E: Knowledge Object #3 Lifecycle Tests
   (test file #3 — full 5-group test suite)
       │
       ▼
   ── MIC Gate ──────────────────────────────
   Three knowledge objects form the assessment triad.
   Wave G may not begin until this gate passes.
   ──────────────────────────────────────────
       │
       ▼
   Wave F: Additional Knowledge Objects (optional)
   (one wave per additional object beyond the triad)
       │
       ▼
   Wave G: Department Activation
   (OrchestrationContext fields + _run_{dept}() + OrchestrationReport field)
       │
       ▼
   Impact Validation
   (Validation document: evidence flow analysis, weight impact, guardrails)
       │
       ▼
   Production Ready
   (full regression suite passes, completion doc written, CURRENT_STATE.md updated)
```

**CBI reference mapping:**

| Step | CBI Wave | Deliverable |
|------|----------|-------------|
| Charter | Pre-Wave | `docs/architecture/Central-Bank-Intelligence.md` |
| Infrastructure | Wave-1A | `contracts.py` (6 contracts, 9 constant groups), `repository.py` (10 methods), `__init__.py` |
| Adapter | Wave-1B | `adapter.py` (5 translation methods) |
| Object #1 tests | Wave-1C | `test_cbi_policy_bias.py` (25 tests) |
| Pipeline review | Wave-1D | Read-only architecture trace (no code) |
| Object #2 tests | Wave-1E | `test_cbi_forward_guidance.py` (30 tests) |
| Object #3 tests | Wave-1F | `test_cbi_rate_path.py` (27 tests) |
| Activation | Wave-1G | `OrchestrationContext` +4 fields, `_run_cbi()`, `OrchestrationReport.cbi_evidence` |
| Validation | Post-Wave | `docs/Validation-002-CBI-Impact.md` |

---

## 7. Required Contracts

Every department must define these contract elements in `contracts.py`:

### 5.1 Base Contract

One `{Dept}BaseContract` frozen dataclass containing all common contract framework fields. This base is inherited by every domain contract in the department.

**CBI reference:** `CbiBaseContract` — 9 fields (confidence, valid_from, valid_until, time_horizon, provenance, evidence_references, cross_references, methodology_version, scenario_analysis).

**CAI reference:** `CaiBaseContract` — identical 9-field signature.

### 5.2 Domain Contracts

Minimum three frozen dataclasses inheriting the base contract, each representing one knowledge object.

**CBI reference:** `PolicyBiasScore`, `RatePathProjection`, `ForwardGuidanceRecord` (MIC triad), plus `LiquidityOutlook`, `GlobalMonetaryRegime` (expansion).

**CAI reference:** `CrossAssetCorrelation`, `SpreadAnalysis`, `RelativeValueAssessment`, `FlowPressure`, `VolatilityRegime`.

### 5.3 Domain Constants

All enumerated values as module-level string constants with corresponding `frozenset` validators.

**Naming convention:** `VALID_{CATEGORY}` for the frozenset, individual constants in `SCREAMING_SNAKE_CASE`.

**CBI reference:** `VALID_CENTRAL_BANKS` (9 values), `VALID_DIRECTIONS` (3), `VALID_TIME_HORIZONS` (5), `VALID_GUIDANCE_TYPES` (4), `VALID_CLASSIFICATIONS` (3), `VALID_PACE_QUALIFIERS` (3), `VALID_RESERVE_TRENDS` (3), `VALID_REGIME_TYPES` (5).

### 5.4 Identity Format

Every knowledge object instance is identified as:

```
{DEPT_CODE}:{ObjectType}:{observation_date}
```

**CBI reference:** `CBI:PolicyBiasScore:2026-07-26`
**CAI reference:** `CAI:CrossAssetCorrelation:2026-07-26`

### 5.5 Confidence Scale

All confidence values use the institutional 0.00–1.00 scale with the following labels:

| Range | Label |
|-------|-------|
| 0.00–0.20 | Speculative |
| 0.21–0.40 | Low |
| 0.41–0.60 | Moderate |
| 0.61–0.80 | High |
| 0.81–0.95 | Very High |
| 0.96–1.00 | Near-Certain |

---

## 8. Repository Requirements

### 6.1 Method Signature

Two methods per contract type, no exceptions:

```python
def save_{object}(self, obj: {ObjectType}, path: Path) -> None
def load_{object}(self, path: Path) -> {ObjectType}
```

### 6.2 Persistence Format

- JSON only
- All writes through `atomic_write_json` (from `knowledge._compat`)
- Provenance serialized via `serialize_provenance` / `deserialize_provenance` (from `knowledge.integrity.provenance`)
- Load methods use `payload.get(field, default)` for forward compatibility

### 6.3 Roundtrip Guarantee

For every contract type: `load(save(obj)) == obj`. This is verified in the repository test group.

**CBI reference:** `CbiRepository` — 10 methods (5 save + 5 load), 211 lines.
**CAI reference:** `CaiRepository` — 10 methods (5 save + 5 load), 233 lines.

---

## 9. Adapter Requirements

### 7.1 Method Signature

One method per knowledge object:

```python
def {object}_to_evidence(self, obj: {ObjectType}) -> Evidence
```

### 7.2 Evidence Output Contract

Every adapter method must produce a canonical `Evidence` instance with:

| Field | Value | Rationale |
|-------|-------|-----------|
| `evidence_id` | `{dept}_{type}_{key}` | Unique within the evidence collection |
| `event_type` | `{DEPT}_{TYPE}` | Layer identification |
| `sample_count` | `1` | Institutional evidence is a single assessment, not a sample |
| `average_return_pct` | `0.0` | Can only dilute existing return signals, never create new ones |
| `horizon_days` | `0` | Time horizon is in metadata, not the evidence horizon field |
| `confidence` | Pass through from contract | Institutional scale preserved |
| `bias` | Explicit domain-to-bias mapping | Must be one of: bullish, bearish, neutral |
| `provenance` | Pass through from contract | Never synthesized by the adapter |
| `metadata` | All domain-specific fields | Full contract preservation |

### 7.3 Bias Mapping

Every domain value must have an explicit, documented mapping to `bullish`, `bearish`, or `neutral`. No implicit defaults.

**CBI reference — PolicyBiasScore:**
- tightening → bearish
- easing → bullish
- neutral → neutral

**CBI reference — LiquidityOutlook:**
- Expanding → bullish
- Stable → neutral
- Contracting → bearish

**CAI reference — CrossAssetCorrelation:**
- positive → neutral
- negative → bearish
- diverging → neutral
- converging → neutral
- decoupling → bearish

### 7.4 Purity

Adapter methods are pure translations:
- No side effects
- No repository calls
- No pipeline interaction
- No state mutation
- Provenance and evidence_references pass through unchanged

---

## 10. Evidence Requirements

### 8.1 Evidence Data Structure

The `Evidence` frozen dataclass has exactly 14 fields. This is Frozen Core. Adapters must populate all 14 fields.

### 8.2 Source Layer Tagging

During pipeline activation (Wave G), each evidence item produced by the department must be tagged with `_source_layer: "{dept_code}"` in its metadata.

**CBI reference:** `_source_layer: "cbi"` — stamped in `_run_cbi()` at `engine.py:192-217`.

### 8.3 Aggregator Compatibility

Department evidence must merge cleanly with `EvidenceAggregator.merge()`. This is verified by the aggregator integration test (Group 4 in the test suite).

### 8.4 Conflict Handling

When the same `evidence_id` appears in multiple layers with different `bias` values, the aggregator must detect and log the conflict. This is verified by the conflict detection test (Group 5 in the test suite).

---

## 11. Validation Requirements

### 9.1 Per-Wave Validation

Each wave must pass before the next begins (Constitution Rule 11):

| Wave | Gate Criteria |
|------|--------------|
| A | Contracts compile. Repository save/load works for every contract type. |
| B | Adapter produces valid `Evidence` from each knowledge object. |
| C–F | Each object: create → persist → retrieve → adapt to Evidence. Full 5-group test suite passes. |
| G | Department wired into OrchestrationEngine. All tests pass including regression. |

### 9.2 Regression Rule

Zero regressions at every wave boundary. The full test suite count is recorded in each wave completion document.

**CBI reference:** Wave-1G completion recorded 243 total passing tests (82 CBI + 161 regression).
**CAI reference:** Wave-2B completion recorded 267 total passing tests (24 CAI + 243 regression).

### 9.3 Verification Check Matrix

Each wave completion document must include a numbered check matrix (e.g., "12/12 checks passed") listing exactly which verifications were performed and their results.

---

## 12. Activation Requirements

### 10.1 OrchestrationContext Fields

Add fields to `OrchestrationContext` (in `src/knowledge/orchestration/context.py`) for:
- One list field per activated knowledge object type (typed `list[{ObjectType}] | None`)
- One adapter field (`{Dept}EvidenceAdapter | None`)

**CBI reference:** 4 fields added — `cbi_bias_scores`, `cbi_guidance_records`, `cbi_rate_paths`, `cbi_adapter`.

### 10.2 `_run_{dept}()` Method

Add a private method to `OrchestrationEngine` following the exact pattern:

1. Check if adapter is `None` — return empty `EvidenceCollection` if so (graceful skip)
2. Iterate each knowledge object list (skip if `None`)
3. Call the corresponding adapter method for each item
4. Tag each evidence item with `_source_layer: "{dept_code}"` in metadata
5. Return `EvidenceCollection(items)`

**CBI reference:** `_run_cbi()` at `engine.py:192-217`.

### 10.3 OrchestrationReport Field

Add `{dept_code}_evidence: EvidenceCollection` to `OrchestrationReport`.

**CBI reference:** `cbi_evidence` field on `OrchestrationReport`.

### 10.4 `analyze()` Wiring

Wire `_run_{dept}()` into the `analyze()` method. The department's evidence collection is added to the `collections` dict under the key `"{dept_code}"` and merged via `EvidenceAggregator.merge()`.

**CBI reference:** `collections["cbi"]` merged alongside economic, temporal, causal, and core layers.

---

## 13. Production Acceptance Checklist

Before a department is declared production-ready, every item must be checked:

- [ ] Department charter ratified in `docs/architecture/`
- [ ] `contracts.py` contains base contract + all domain contracts as frozen dataclasses
- [ ] All domain constants defined with `frozenset` validators
- [ ] `repository.py` contains save/load method pair for every contract type
- [ ] All repository methods use `atomic_write_json`
- [ ] `adapter.py` contains one translation method per knowledge object
- [ ] All adapter methods are pure (no side effects, no repository calls)
- [ ] All bias mappings are explicit and documented
- [ ] `__init__.py` re-exports all contracts, constants, repository, and adapter
- [ ] At least three knowledge objects have full 5-group lifecycle test suites
- [ ] All lifecycle tests pass: create → persist → retrieve → adapt
- [ ] Aggregator integration tests pass for each tested object
- [ ] Conflict detection tests pass for each tested object
- [ ] `OrchestrationContext` fields added for the department
- [ ] `_run_{dept}()` method added to `OrchestrationEngine`
- [ ] `OrchestrationReport` field added for department evidence
- [ ] `analyze()` wiring complete
- [ ] Full regression suite passes with zero regressions
- [ ] Impact validation document written
- [ ] Wave completion documents written for every wave (A through G)
- [ ] `CURRENT_STATE.md` updated
- [ ] No Frozen Core modification required

---

## 14. Common Implementation Mistakes

These mistakes have been identified from the CBI and CAI implementation experience. Each represents a real risk.

| # | Mistake | Why It Fails | Correct Pattern |
|---|---------|-------------|-----------------|
| 1 | Adding methods to contract dataclasses | Contracts are data, not behavior. Methods create coupling between data and logic. | All behavior lives in adapter or external functions. |
| 2 | Writing repository query/search methods | Repositories are persistence only. Querying belongs in the orchestration layer. | Two methods per type: `save_` and `load_`. Nothing else. |
| 3 | Making adapter methods call the repository | Adapters are pure translators. Mixing persistence into translation creates hidden dependencies. | Adapter receives the contract object as input. It never loads anything. |
| 4 | Skipping the base contract | Departments without a base contract cannot share common framework fields and break the identity/provenance model. | Every domain contract inherits `{Dept}BaseContract`. |
| 5 | Using mutable dataclasses | Mutable contracts break the Evidence pipeline which depends on immutability guarantees. | `@dataclass(frozen=True)` on every contract. `FrozenDict` for dict fields. |
| 6 | Creating subdirectories in the department package | The proven structure is exactly 4 files. Subdirectories add complexity with no benefit. | `__init__.py`, `contracts.py`, `repository.py`, `adapter.py`. No subdirectories. |
| 7 | Synthesizing provenance in the adapter | Provenance must originate from the producing analyst or system, not from the translation layer. | Pass through `obj.provenance` directly. |
| 8 | Beginning Wave G before three objects are tested | Constitution Section 4.3 requires three lifecycle-tested objects before pipeline activation. | Complete Waves C, D, and E before starting Wave G. |
| 9 | Modifying `Evidence`, `EvidenceWeighter`, or `EvidenceAggregator` | These are Frozen Core. Department evidence must work within the existing 14-field structure. | All domain-specific fields go in `Evidence.metadata`. |
| 10 | Using `sample_count > 1` for institutional evidence | Institutional assessments are single observations, not statistical samples. Inflating `sample_count` corrupts the 5-factor weighting model. | Always `sample_count=1`. |
| 11 | Skipping the conflict detection test | Without it, duplicate evidence IDs across layers silently corrupt the aggregation. | Group 5 in every test file. |
| 12 | Direct dict writes instead of `atomic_write_json` | Non-atomic writes can corrupt JSON files on crash or concurrent access. | All persistence through `atomic_write_json`. |

---

## 15. Mandatory Invariants

These invariants are unconditional. They apply to every department, every wave, every knowledge object.

1. **Never bypass Evidence.** Every institutional insight must be translated into the canonical `Evidence` frozen dataclass before it can influence reasoning or decisions. There is no shortcut to the Decision Engine.

2. **Never modify Frozen Core.** The 14-field `Evidence` structure, the `EvidenceWeighter`, the `ReasoningEngine`, the `DecisionEngine`, the `InferencePipeline`, and all other components listed in Constitution Section 12.1 are permanently frozen. Department implementations must work within these structures, not modify them.

3. **Never add pipeline stages.** The canonical pipeline is frozen. Department evidence enters through `EvidenceAggregator.merge()` via the `OrchestrationEngine` adapter pattern. No new stages may be inserted into `InferencePipeline`.

4. **Always reuse existing infrastructure.** Departments consume shared infrastructure: `atomic_write_json`, `FrozenDict`, `Provenance`, `serialize_provenance`/`deserialize_provenance`, `Evidence`, `EvidenceCollection`, `EvidenceAggregator`. No department may reimplement any of these.

5. **Every knowledge object must have:**
   - **Contract** — frozen dataclass inheriting the department's base contract
   - **Repository support** — `save_` and `load_` methods in the department repository
   - **Adapter** — `{object}_to_evidence()` method producing canonical `Evidence`
   - **Tests** — full 5-group lifecycle test suite (creation, repository, adapter, aggregator integration, conflict detection)

6. **No guessing.** When evidence is insufficient, the system must report `insufficient_evidence`. No department may produce synthetic confidence or fabricated assessments.

7. **Determinism is mandatory.** Same input must produce same output. `determinism_score >= 1.0` in the benchmark suite. No exceptions.

8. **No layer skipping.** Department evidence flows through: Adapter → EvidenceCollection → EvidenceAggregator → EvidenceWeighter → ReasoningEngine → DecisionEngine. No step may be bypassed.

9. **Contracts are immutable.** Once a knowledge object contract is defined and tested, its field set is permanent. New fields require a new contract version or a new knowledge object.

10. **No undocumented confidence.** Every confidence score must state its computation method. A confidence value without provenance is a violation.

11. **Departments communicate through the Knowledge Department only.** No department may directly call another department's internal methods. Cross-department references use the `cross_references` field resolved through published knowledge object IDs.

12. **Knowledge object names are permanent.** No renaming, deprecation, or reassignment (Constitution Section 6.3).

13. **Never modify the Reference Department Template to solve another department's problem.** Fix the new department. Do not change the template. The Reference Department Template represents the canonical implementation pattern. Future departments must conform to it unless a proven architectural defect is discovered, documented with root cause analysis, and approved by the Architecture Council.

---

## 16. Definition of Department Completion

A department is complete when it reaches **Minimum Institutional Capability (MIC)** as defined in `PROJECT_CONSTITUTION_V2.md` Section 15.2.

### MIC Requires:

1. Department charter ratified
2. Infrastructure completed (contracts, repository, package initialization)
3. Evidence Adapter completed
4. **At least three canonical knowledge objects** fully implemented, tested, and together capable of producing a coherent institutional assessment
5. Repository persistence verified
6. Pipeline activation completed
7. End-to-end validation completed
8. Regression tests passing
9. No Frozen Core modification required

### What "Three Objects" Means:

The three objects must form an **assessment triad** — three complementary perspectives that together produce a coherent institutional assessment for the department's domain. They are not three arbitrary objects.

**CBI reference triad:** PolicyBiasScore (stance direction) + ForwardGuidanceRecord (narrative justification) + RatePathProjection (quantitative trajectory). Together they answer: "What is the central bank doing, why, and where is it going?"

### What MIC Does Not Require:

The remaining knowledge objects beyond the triad are classified as **Institutional Expansion**. They enhance analytical depth and coverage but are not prerequisites for departmental activation. This classification is permanent.

### Wave G Gate:

Wave G (pipeline activation) may not begin until at least three knowledge objects have completed lifecycle testing (Constitution Section 4.3). This is not a suggestion. It is a gate.

---

## 17. Reference Implementation Mapping

Every section of this template maps to a specific proven artifact in the CBI (Wave-1) and CAI (Wave-2) implementations.

| Template Section | CBI Reference | CAI Reference |
|-----------------|---------------|---------------|
| **4. Directory structure** | `src/knowledge/cbi/` (4 files) | `src/knowledge/cai/` (4 files) |
| **5.1 contracts.py** | `src/knowledge/cbi/contracts.py` (131 lines, 6 contracts, 9 constant groups) | `src/knowledge/cai/contracts.py` (137 lines, 5 contracts, 10 constant groups) |
| **5.2 repository.py** | `src/knowledge/cbi/repository.py` (211 lines, 10 methods) | `src/knowledge/cai/repository.py` (233 lines, 10 methods) |
| **5.3 adapter.py** | `src/knowledge/cbi/adapter.py` (206 lines, 5 methods) | `src/knowledge/cai/adapter.py` (59 lines, 1 method — Wave-2B) |
| **5.4 __init__.py** | `src/knowledge/cbi/__init__.py` (107 lines, 52 exports) | `src/knowledge/cai/__init__.py` (96 lines, 44 exports) |
| **5.5 Test files** | `tests/test_cbi_policy_bias.py` (500 lines, 25 tests), `tests/test_cbi_forward_guidance.py` (640 lines, 30 tests), `tests/test_cbi_rate_path.py` (572 lines, 27 tests) | `tests/test_cai_cross_asset_correlation.py` (656 lines, 24 tests) |
| **6. Implementation order** | Wave-1A (infra) → 1B (adapter) → 1C (PolicyBiasScore) → 1D (pipeline review) → 1E (ForwardGuidanceRecord) → 1F (RatePathProjection) → 1G (activation) | Wave-2A (infra) → 2B (CrossAssetCorrelation) → 2C–2F (remaining objects) → 2G (activation) |
| **7. Contracts** | `CbiBaseContract` + 5 domain contracts | `CaiBaseContract` + 5 domain contracts |
| **8. Repository** | `CbiRepository` — `atomic_write_json`, `serialize_provenance` | `CaiRepository` — identical pattern |
| **9. Adapter** | `CbiEvidenceAdapter` — 5 pure translation methods | `CaiEvidenceAdapter` — 1 pure translation method |
| **10. Evidence** | `_source_layer: "cbi"` tagging in `_run_cbi()` | Not yet activated (pending Wave-2G) |
| **11. Validation** | Wave-1G: 243 tests (82 CBI + 161 regression) | Wave-2B: 267 tests (24 CAI + 243 regression) |
| **12. Activation** | `OrchestrationContext` +4 CBI fields, `_run_cbi()`, `OrchestrationReport.cbi_evidence`, `collections["cbi"]` in `analyze()` | Not yet activated (pending Wave-2G) |
| **13. Acceptance** | All 22 checklist items verified at Wave-1G completion | Partially verified through Wave-2B |
| **14. Mistakes** | Extracted from Wave-1A–1G implementation decisions | Confirmed by Wave-2A–2B replication |
| **15. Invariants** | Enforced by Constitution Section 12 rules | Same invariants apply |
| **16. MIC** | Achieved: PolicyBiasScore + ForwardGuidanceRecord + RatePathProjection triad | Not yet achieved (1 of 3 minimum objects tested) |

### Wave Documentation Reference

| Wave Doc | Location |
|----------|----------|
| Infrastructure Readiness | `Implementation-Wave-1-Readiness.md` |
| Wave-1A Completion | `Wave-1A-Completion.md` |
| Wave-1B Readiness | `Wave-1B-Readiness.md` |
| Wave-1B Completion | `Wave-1B-Completion.md` |
| Wave-1C Completion | `Wave-1C-Completion.md` |
| Wave-1D Readiness | `Wave-1D-Readiness.md` |
| Wave-1E Completion | `Wave-1E-Completion.md` |
| Wave-1F Completion | `Wave-1F-Completion.md` |
| Wave-1G Readiness | `Wave-1G-Readiness.md` |
| Wave-1G Completion | `docs/Wave-1G-Completion.md` |
| Wave-2A Completion | `docs/Wave-2A-Completion.md` |
| Wave-2B Completion | `docs/Wave-2B-Completion.md` |
| CBI Impact Validation | `docs/Validation-002-CBI-Impact.md` |
| CBI Architecture | `docs/architecture/Central-Bank-Intelligence.md` |
| CAI Architecture | `docs/architecture/Cross-Asset-Intelligence.md` |
| Knowledge Contracts | `docs/architecture/Institutional-Knowledge-Contracts.md` |
| Interaction Map | `docs/architecture/Institutional-Interaction-Map.md` |
| Gap Analysis | `docs/audit/CER-009-Institutional-Gap-Analysis.md` |

---

*This document is the canonical engineering playbook for AurumAI department implementation. It was derived exclusively from the proven patterns of Central Bank Intelligence (Wave-1A–1G) and Cross-Asset Intelligence (Wave-2A–2B). Nothing was invented. Every requirement maps to working code.*

*Governing document: `docs/PROJECT_CONSTITUTION_V2.md`*
