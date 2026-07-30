# PROJECT CONSTITUTION v2

**Status**: Ratified
**Authority**: Supreme Governing Document — all project activity is subordinate to this constitution
**Effective**: 2026-07-26
**Supersedes**: PROJECT_NORTH_STAR.md, PROJECT_CONSTITUTION.md (v1), CURRENT_STATE.md (governance sections)

This document is the single governing authority for all AurumAI engineering, architecture, operations, and expansion from this point until project completion. No other document, ADR, comment, commit message, or piece of code may contradict this constitution. Where conflict exists, this constitution prevails and the conflicting artifact must be corrected.

Amendments require an explicit decision recorded as a dated entry in the Amendment Log (Section 16), approved by the Chief Architect.

---

## 1. Permanent Project Mission

AurumAI exists to build an Institutional Financial Intelligence System capable of producing deterministic, explainable, and evidence-based investment assessments from historical macroeconomic data.

AurumAI is **not** a trading bot.

Trading execution is a downstream consumer of AurumAI intelligence. The execution layer is not the product. Institutional Intelligence is the product.

The system optimizes for institutional trust, not feature count. Every engineering task must increase one or more of:

- Correctness
- Determinism
- Explainability
- Reproducibility
- Measurable predictive value

Any task that does not improve at least one of these properties must be postponed.

---

## 2. Permanent Engineering Principles

These principles are mandatory and permanent. They apply to every line of code, every document, every decision, and every contributor — human or AI.

### 2.1 Determinism

The same inputs must always produce the same outputs. No hidden randomness. No hidden state. No time-dependent behavior. All IDs are content-derived. All RNG is seeded. All source data is in-repo or deterministically fetchable.

### 2.2 Explainability

Every decision must be traceable through the complete chain:

```
Source Data → Events → Features → Lessons → Knowledge Records →
Knowledge Graph → Evidence → Reasoning → Decision → Institutional Assessment
```

No black-box decisions are permitted. Every number the system surfaces (confidence, bias, win rate, average return) must be reproducible by re-running the pipeline against the same input data. Every qualitative label must have a documented, fixed threshold that produced it.

### 2.3 Evidence First

Opinions are prohibited. Every engineering decision must be backed by reproducible evidence. "The Brain believes X" is not acceptable. "The Brain found N historical cases supporting X, with this confidence, from these sources" is the minimum acceptable output.

### 2.4 Smallest Correct Fix

Never redesign when a wiring fix is sufficient. Never expand scope while fixing a bug. Fix only the verified root cause. Every reported issue must follow:

```
Verification → Reproduction → Root Cause → Smallest Correct Fix → Tests → Regression → Commit
```

No implementation before verification.

### 2.5 Reuse Before Build

Always prefer mature open-source solutions when they satisfy the architectural requirements. Never rebuild existing engineering work without evidence. The adoption hierarchy is: Reuse > Extend > Integrate > Build.

### 2.6 Backward Compatibility

Public APIs remain stable whenever reasonably possible. Breaking changes require explicit architectural justification and Architecture Council approval.

### 2.7 Risk Before Profit

Every layer that touches money must be gated by risk controls that are stricter than the layer's own confidence in itself. No real trading before successful backtesting and paper trading have both passed their defined gates. No exceptions.

### 2.8 Continuous Learning

New evidence updates knowledge; it does not get discarded after a single use. The system must get smarter as it ages: every new event becomes a new lesson, every new lesson refines existing knowledge records, and every refinement is traceable to its source evidence.

### 2.9 Test Everything

An untested module is an unverified claim, not a working component. Tests are deterministic, use no live network calls in unit tests, and must pass before any sprint is considered complete. The 18-benchmark suite is the permanent acceptance gate.

### 2.10 Rule of Focus

No new capability shall be implemented until the previous capability has demonstrated measurable value. Engineering effort must always maximize institutional intelligence rather than feature count.

---

## 3. Permanent Architecture Principles

### 3.1 Seven-Layer Architecture

AurumAI is organized into seven layers. Each layer has one responsibility and depends only on the layer(s) below it, never sideways or upward.

| Layer | Responsibility | Rule |
|-------|---------------|------|
| 1. Data Sources | External providers and mature libraries | AurumAI wraps them, never rebuilds them |
| 2. Data Engine | Collect, clean, normalize, validate, store | Does not analyze or decide |
| 3. Knowledge Engine | Transform data into immutable lessons, aggregate into knowledge records, store in temporal knowledge graph | Owns all intelligence structures |
| 4. Brain | Understand relationships, retrieve evidence-backed knowledge | Does not produce trade signals |
| 5. Reasoning Engine | Combine macro, price, news, liquidity, and historical lessons into a confidence assessment | Multi-agent evidence-based reasoning only |
| 6. Decision Engine | Produce explainable decisions within risk constraints | Only after reasoning is complete |
| 7. Execution Engine | Connect to broker after backtesting and paper trading gates pass | Last layer, most heavily gated |

### 3.2 Layer Rules

- Each layer must be swappable behind a stable interface.
- No layer may skip the layer below it. The Decision Engine cannot read raw data directly.
- Backends are chosen for the smallest complexity that satisfies current scale, with a documented upgrade path.
- All data flow is one-directional: Event → Evidence → Aggregate → Reasoning → Decision → Record. This directional purity must be preserved.

### 3.3 Canonical Pipeline Flow

```
Raw Data → Events → Feature Extraction → Lessons → Knowledge Records →
Knowledge Graph → Evidence Query & Ranking → Reasoning Engine →
Decision Engine → Learning Engine → Institutional Assessment
```

`InferencePipeline` is the canonical entry point. `OrchestrationEngine` is an adapter pattern around it, coordinating Economic + Temporal + Causal + Core layers.

### 3.4 No Circular Dependencies

No circular dependencies may exist between any subsystems. All data flow must remain one-directional.

---

## 4. Department Development Rules

### 4.1 Department Classification

AurumAI has four Tier-1 Intelligence Departments:

| Code | Department | Mission |
|------|-----------|---------|
| CBI | Central Bank Intelligence | Monitor, analyze, and synthesize monetary policy across 9 major central banks |
| CAI | Cross-Asset Intelligence | Track cross-asset correlations, divergences, rotations, and regime states |
| CFI | Capital Flow Intelligence | Monitor positioning, flows, market structure, and accumulation signals |
| NI | Narrative Intelligence | Track narrative strength, conflicts, lifecycle phases, and market discourse |

### 4.2 Department Charter Requirements

Every department must have:

1. A ratified department charter document in `docs/architecture/`
2. A defined set of knowledge objects with frozen contracts (per Section 5)
3. A code implementation under `src/knowledge/{department_code}/`
4. A `contracts.py` file defining all knowledge object dataclasses as frozen
5. A `repository.py` file implementing save/load for all knowledge objects
6. An evidence adapter translating department knowledge objects to the canonical `Evidence` type
7. Tests covering every knowledge object lifecycle (create → persist → retrieve → adapt to Evidence)

### 4.3 Department Development Order

Departments are developed in implementation waves. Each wave follows the pattern:

```
Wave A: Infrastructure (contracts.py + repository.py + __init__.py)
Wave B: Evidence Adapter (adapter.py mapping knowledge objects to Evidence)
Wave C-F: Knowledge Object Lifecycle Tests (one wave per knowledge object)
Wave G: Pipeline Activation (wiring into OrchestrationEngine)
```

A department's Wave G may not begin until at least three knowledge objects have completed lifecycle testing (forming a minimum viable "assessment triad").

### 4.4 Department Interaction Rules

- Departments communicate exclusively through the Knowledge Department (Evidence Repository, Reasoning Engine).
- No department may directly call another department's internal methods.
- Cross-department references use the `cross_references` field on knowledge objects, resolved through published knowledge object IDs.
- Cross-department intelligence reconciliation (e.g., three-way liquidity assessment between CBI, CAI, CFI) is performed by the Knowledge Department's Reasoning Engine, not by the departments themselves.

---

## 5. Knowledge Object Rules

### 5.1 Common Contract Framework

Every knowledge object exported by any Tier-1 department conforms to the common contract framework. The following are mandatory on every knowledge object:

- **Identity**: `{department_code}:{object_type}:{observation_date}`
- **Confidence**: 0.00–1.00 on the six-label institutional scale (Speculative, Low, Moderate, High, Very High, Near-Certain)
- **Provenance**: producing_department, object_type, observation_timestamp, publication_timestamp, producing_analyst, source_data_descriptor, last_updated
- **Evidence References**: source_category, source_descriptor, contribution, confidence_contribution
- **Validity Period**: valid_from, valid_until
- **Time Horizon**: T0 (Event/Now), T1 (Short-Term, 1-5 days), T2 (Medium-Term, 1-4 weeks), T3 (Long-Term, 1-12 months), T4 (Structural, 1+ years)

### 5.2 Knowledge Object Inventory

The following 40 knowledge objects are the permanent institutional inventory. No name may be changed, deprecated, or reassigned.

**CBI (5 objects, 5 expansion pending)**: PolicyBiasScore, RatePathProjection, ForwardGuidanceRecord, LiquidityOutlook, GlobalMonetaryRegime

**CAI (5 objects, 2 expansion pending)**: CrossAssetCorrelation, SpreadAnalysis, RelativeValueAssessment, FlowPressure, VolatilityRegime

**CFI (10 objects)**: GoldPositioningDashboard, COTPositioningReport, ETFFlowMonitor, CentralBankReserveFlowReport, MarketStructureGammaProfile, SafeHavenFlowIndex, DeDollarizationFlowIndex, SpeculativeFlowAsymmetryAssessment, InstitutionalAccumulationSignal, LiquidityMigrationMap

**NI (10 objects)**: NarrativeStrengthDashboard, NarrativeConflictMatrix, NarrativePositioningGapReport, NarrativeRegimeAssessment, NarrativeDataGapAlert, NarrativeCollapseWarning, SellSideConsensusIndex, NarrativeImpactDecomposition, CrossDepartmentNarrativeCoherenceScore, NarrativeCatalystCalendar

### 5.3 Contract Compliance Rules

1. Common fields (5.1) must never be removed from any knowledge object.
2. Mandatory fields must always be populated. If a department cannot produce a mandatory field, the knowledge object must not be published.
3. Optional fields may be omitted but their semantics must not change.
4. The 0.00–1.00 confidence scale is the only authorized confidence representation.
5. `valid_until` must be set to a date no later than the next scheduled update.
6. Consumer lists are additive — a consumer may be added but never removed without Architecture Council approval.
7. Object names are permanent.
8. Field semantics are permanent.
9. Cross-references must be resolvable to published knowledge objects.
10. New knowledge objects require Architecture Council approval.

### 5.4 Contract Change Procedure

1. Department head proposes change with exact element, new specification, and rationale.
2. Impact assessment: identify all affected objects, consumers, and migration cost.
3. Architecture Council review against backward compatibility, migration cost, and institutional coherence.
4. Approval: majority for department-specific changes; unanimous for common framework changes.
5. Migration with specified transition period.
6. Archive superseded specification with effective date range.

---

## 6. Adapter Rules

### 6.1 Evidence Adapter Contract

Every department must provide an Evidence Adapter that translates its knowledge objects into the canonical `Evidence` type. The adapter is a pure translation layer — it must not contain business logic, state, or side effects.

### 6.2 Adapter Requirements

- One adapter class per department (e.g., `CbiEvidenceAdapter`, `CaiEvidenceAdapter`)
- One method per knowledge object type (e.g., `policy_bias_to_evidence()`)
- Input: a single knowledge object instance
- Output: one or more `Evidence` instances
- No access to repositories, databases, or external services
- No modification of the input knowledge object
- Deterministic: same input always produces the same output

### 6.3 Adapter Placement

Adapters live in `src/knowledge/{department_code}/adapter.py`. They are consumed by the OrchestrationEngine during pipeline execution.

---

## 7. Evidence Rules

### 7.1 Evidence Data Structure (Frozen)

The `Evidence` data structure has 14 fields and is permanently frozen:

evidence_id, event_type, asset, condition, value, confidence, direction, horizon, impact, returns_weight, average_return_pct, bias, source_timestamp, metadata

No fields may be added, removed, or have their semantics changed without Architecture Council approval.

### 7.2 Evidence Weighting (Frozen)

The 5-factor geometric mean weighting model is permanent:

| Factor | Purpose |
|--------|---------|
| confidence_weight | Intrinsic confidence of the evidence source |
| sample_size_weight | Statistical reliability based on sample count |
| provenance_weight | Quality and reliability of the data source |
| consistency_weight | Agreement with other evidence in the collection |
| recency_weight | Temporal relevance of the evidence |

The institutional_context factor was evaluated (Sprint-006) and rejected — it belongs in reasoning explanation, not evidence weighting. This decision is final.

### 7.3 Evidence Collection Rules

- Evidence is filtered by event_type, condition, and requested horizon.
- Evidence with insufficient quantity triggers `INSUFFICIENT_EVIDENCE` — the system must never guess.
- Evidence must degrade gracefully: missing or insufficient evidence produces "insufficient evidence," never a guess dressed up as a decision.

---

## 8. Validation Rules

### 8.1 Institutional Validation Categories

Every capability must pass validation across these 10 categories:

1. **Evidence Quality**: uses all relevant evidence, ignores irrelevant
2. **Knowledge Consistency**: consistent records produce consistent decisions
3. **Temporal Consistency**: mixed horizons are detected and flagged
4. **Causal Consistency**: internal causal consistency is verified
5. **Cross-Layer Consistency**: conflicts between layers are documented
6. **Explainability Integrity**: full decision → chain → evidence trace
7. **Deterministic Behavior**: same input = same output
8. **Traceability**: lineage verified end-to-end (decision → source_data)
9. **Insufficient Evidence**: code path works and is reachable
10. **End-to-End**: all layers + all step types + decision + lineage

### 8.2 Gate 6 Validation Criteria

The Out-of-Sample validation must answer:

1. Is AurumAI correct? (Directional accuracy)
2. Is confidence calibrated? (ECE)
3. Does context enrichment improve decisions?
4. Is internal consistency maintained?
5. Is evidence quality sufficient?
6. Is the system deterministic? (SHA-256 artifact comparison)

### 8.3 Validation Hierarchy

```
Unit Tests → Integration Tests → Benchmark Suite (18 tests) →
Institutional Validation (10 scenarios) → OOS Validation (Gate 6) →
Paper Trading Validation → Live Execution Gate
```

Each level must pass before the next is attempted.

---

## 9. GitHub Rules

### 9.1 Branch Policy

- `main` is the only long-lived branch.
- All work is committed to `main` through small, reviewable commits.
- Every commit must leave the test suite passing.
- No partial or broken code is committed as "done."

### 9.2 Commit Rules

- Small commits, daily progress.
- Each commit produces a working, runnable artifact.
- Commit messages state what changed and why.
- No commit may silently delete functionality — removals follow the migration process (Section 11.4).

### 9.3 Repository Organization

| Directory | Purpose | Authority |
|-----------|---------|-----------|
| `docs/` | Authoritative documentation | This constitution is the top |
| `docs/adr/` | Point-in-time architecture decisions | Each ADR is authoritative for its scope |
| `docs/architecture/` | Living architecture descriptions | Must stay in sync with accepted ADRs |
| `docs/audit/` | Sprint reports, CER documents, validation reports | Historical record |
| `research/` | Candidate evidence for future ADRs | Not authoritative until promoted |
| `src/` | Installable package | Every subpackage maps to exactly one layer |
| `src/knowledge/` | Intelligence Core (the only active `src/` subpackage for core intelligence) | Single source of truth for all intelligence behavior |
| `tests/` | Mirrors `src/` layer structure | Any reader can find tests without guessing |
| `data/` | Local, regenerable artifacts | Nothing hand-edited; everything fetched or produced |
| `archive/` | Historical sprint reports and bootstrap scripts | Not authoritative |

### 9.4 Code Review Rule

Code or documentation generated by any agent (human or AI) is not accepted into the repository until reviewed against this constitution: project identity, architecture, module boundaries, tests, explainability, and open-source reuse policy.

---

## 10. Benchmark Rules

### 10.1 The 18-Benchmark Acceptance Gate

The benchmark suite (`tests/test_benchmark.py`) is the permanent acceptance gate. Every capability added to AurumAI must not degrade any metric below its threshold.

### 10.2 Benchmark Suites and Thresholds

| Suite | Metric | Threshold | Meaning |
|-------|--------|-----------|---------|
| Reasoning | reasoning_accuracy | >= 0.80 | 80% of reasoning scenarios produce correct conclusions |
| Reasoning | num_scenarios | >= 5 | Minimum scenario coverage |
| Reasoning | confidence_calibration | >= 0.00 | Calibration is measured and reported |
| Retrieval | precision_at_1 | >= 0.90 | Top-1 retrieval is correct 90%+ of the time |
| Retrieval | retrieval_accuracy | >= 0.75 | Overall retrieval accuracy |
| Cross-Event | consensus_accuracy | >= 0.80 | Cross-event consensus is correct 80%+ |
| Cross-Event | conflict_detection_rate | >= 0.50 | At least 50% of conflicts are detected |
| Weighting | quality_weighting_accuracy | >= 1.00 | Perfect quality weighting |
| Weighting | sample_size_sensitivity | >= 1.00 | Perfect sample size sensitivity |
| Decision | decision_consistency | >= 1.00 | Perfect decision consistency |
| Decision | decision_stability | >= 0.50 | Decisions are stable across perturbations |
| Decision | decision_accuracy | >= 0.66 | 66%+ decisions are correct |
| Determinism | determinism_score | >= 1.00 | Perfect determinism — mandatory |
| Stability | decision_stability | >= 0.50 | Stability benchmark confirmation |
| Stability | consensus_stability | >= 0.50 | Consensus is stable |

### 10.3 Benchmark Integrity Rules

- The benchmark suite must contain exactly 7 benchmark classes producing exactly 18 metrics.
- No benchmark may be removed, weakened, or bypassed.
- Thresholds may only be raised (tightened), never lowered.
- Adding new benchmarks requires Architecture Council approval.
- `py -3 -m pytest tests/test_benchmark.py` must pass from a clean clone.

---

## 11. Expansion Rules

### 11.1 Expansion Prerequisite

No new intelligence capability may be added before the current capability has demonstrated measurable value. Specifically, no new capabilities until OOS validation (Gate 6) answers the four fundamental questions (Section 8.2).

### 11.2 Out of Scope Until OOS Validation Succeeds

- New macro indicators
- New event types
- New AI models
- Broker integrations
- Live trading
- Major architectural refactoring
- Cosmetic optimization
- Performance tuning without evidence

### 11.3 Expansion via Extension, Not Modification

All expansion happens by implementing existing contracts:

- New events implement `MacroEvent` ABC
- New features implement `FeatureExtractor` ABC
- New departments implement the department charter framework (Section 4)
- New knowledge objects conform to the common contract framework (Section 5.1)

No expansion may modify Frozen Core components.

### 11.4 Migration Process for Removals

No agent, human or AI, may silently delete functionality. Any removal follows:

1. Document the duplication or obsolescence.
2. Propose the canonical target.
3. Migrate all callers.
4. Only then retire the old module in a dedicated commit.
5. Legacy modules are retained with their status marked as a record of why a path was not taken.

### 11.5 Knowledge Expansion Framework

New event types follow the `EventScaffolder` + `EventValidator` + `ExpansionLifecycle` framework:

1. Prepare CSV data
2. Define `ExpansionSpec`
3. Scaffold (generates 3 files)
4. Customize Extractor and Event Class
5. Run Validator
6. Register Event in `EventRegistry`
7. Run Tests
8. Pipeline Smoke Test
9. Verify No Regressions

Target: new event type in under 1 hour with ~90% code generated.

### 11.6 Department Implementation Waves

New departments are built in the standard wave pattern:

| Wave | Deliverable | Gate |
|------|------------|------|
| A | Infrastructure (contracts + repository + package init) | Contracts compile, repository save/load works |
| B | Evidence Adapter | Adapter produces valid Evidence from each knowledge object |
| C-F | Knowledge Object Lifecycle Tests | Each object: create → persist → retrieve → adapt |
| G | Pipeline Activation | Department wired into OrchestrationEngine, tests pass |

### 11.7 Research Governance

- Research candidates are proposed by the Research Engineer role and recorded in `research/`.
- Status: Approved, Rejected, or Use Ideas Only. All are valid first-class outcomes.
- A candidate becomes part of the approved stack only via an ADR in `docs/adr/`.
- Research findings that change architecture must update both the ADR and architecture docs in the same change.
- Rejected research stays in the repository with status marked.

---

## 12. Rules That Must Never Be Broken

These rules are absolute and unconditional. No exception, no shortcut, no override.

1. **No black-box decisions.** Every decision must be traceable to specific evidence through the complete chain.

2. **No real trading before gates pass.** Backtesting and paper trading must both pass their defined gates before any connection to live execution.

3. **No modification of Frozen Core without a verified defect.** The Frozen Core (Section 12.1) may only be modified when a verified engineering defect cannot be corrected elsewhere.

4. **No silent deletion of functionality.** Removals follow the migration process (Section 11.4).

5. **No duplicate implementations.** When discovered, duplicates must be resolved through explicit migration, not left for future confusion.

6. **Determinism is mandatory.** `determinism_score >= 1.0` in the benchmark suite. No exceptions.

7. **Lessons are immutable.** Once written, lessons are never mutated. Corrections are appended as new, versioned lessons.

8. **Knowledge is asset-agnostic in structure.** Schemas must not hardcode specific event types or assets into structural fields.

9. **No layer skipping.** The Decision Engine cannot read raw data directly. Every layer goes through the layer below it.

10. **No capability without benchmark.** Every capability must pass the 18-benchmark acceptance gate.

11. **No moving to the next phase until the current phase passes its gates.**

12. **The documented pipeline must always be runnable from a clean clone.**

13. **No undocumented confidence.** Any confidence score must state its computation method.

14. **No guessing.** When the system cannot explain or justify, it must say so explicitly (insufficient_evidence, missing_context, missing_knowledge).

### 12.1 Frozen Core Inventory

The following components are permanently frozen. Modifications require a verified engineering defect that cannot be corrected elsewhere, plus Architecture Council approval.

| Component | Location | Frozen Scope |
|-----------|----------|-------------|
| InferencePipeline | `knowledge/pipeline/` | 6-stage canonical pipeline |
| ReasoningEngine | `knowledge/reasoning/engine.py` | `reason()` signature and step generation |
| DecisionEngine | `knowledge/decision/engine.py` | `decide()` signature and `_classify()` 6-type system |
| Evidence | `knowledge/evidence/evidence.py` | 14-field frozen dataclass |
| EvidenceWeighter | `knowledge/evidence/weighting.py` | 5-factor geometric mean model |
| WeightConfig | `knowledge/evidence/weighting.py` | 7-field configuration |
| ReasoningChain | `knowledge/reasoning/chain.py` | 9-field output contract |
| ReasoningStep | `knowledge/reasoning/step.py` | 6-field step with 4 step types |
| KnowledgeRecord | `knowledge/knowledge_record.py` | 37-field persistent knowledge unit |
| MacroEvent ABC | `knowledge/events/base.py` | Abstract method signatures (no new abstract methods) |
| EventRegistry | `knowledge/events/` | Registration contract |
| Knowledge Expansion Framework | `knowledge/events/` | EventScaffolder, EventValidator, ExpansionLifecycle |
| Benchmark Framework | `tests/test_benchmark.py` | 7 suites, 18 metrics, thresholds |
| Core Entity Contracts | `knowledge/models/` | LessonField, StandardEventMetadata |
| Institutional Assessment | `knowledge/orchestration/models.py` | StageRecord, CheckpointResult, InstitutionalAssessment |
| Constitutional Rules | This document | All rules in this section |

### 12.2 Frozen Data Structures

The following data structures have their exact field sets permanently frozen:

| Structure | Fields | Reach |
|-----------|--------|-------|
| FrozenDict | N/A (immutable dict) | Foundation |
| Evidence | 14 | Widest reach — every subsystem |
| EvidenceCollection | 3 | Pipeline core |
| WeightFactors | 7 | Evidence weighting |
| WeightConfig | 7 | Weighting configuration |
| WeightedAggregate | 7 | Reasoning input |
| ReasoningStep | 6 | Reasoning output |
| ReasoningContext | 11 | Reasoning input |
| ReasoningChain | 9 | Decision input |
| Decision | 9 | Final output |
| KnowledgeRecord | 37 | Persistent knowledge unit |
| LessonField | 7 | Event lesson output |
| Provenance | 4 | Audit trail node |
| PipelineContext | 36 keys | Pipeline configuration |

### 12.3 Permanent Interface Contracts

These interfaces define the contracts between all subsystems and may not change:

**Contract 1**: `MacroEvent` ABC — 5 abstract method signatures (event_type, lesson_version, condition_columns, load_raw, load_and_extract, build_lesson_fields, lesson_text)

**Contract 2**: `EvidenceWeighter.weigh()` → `WeightedAggregate`

**Contract 3**: `ReasoningEngine.reason(evidence, context)` → `ReasoningChain`

**Contract 4**: `DecisionEngine.decide(chain, context, min_evidence_count)` → `Decision`

**Contract 5**: `PipelineLog.explain()` and `explain_structured()`

**Contract 6**: `PipelineContext` — 36-field dictionary-based configuration contract

---

## 13. Decision Hierarchy

### 13.1 Authority Levels

| Level | Authority | Scope |
|-------|----------|-------|
| 1 | This Constitution | All rules, principles, architecture, and governance |
| 2 | Architecture Council | Freeze changes, new knowledge objects, contract changes, new benchmarks |
| 3 | Chief Architect | ADRs, sprint plans, module ownership, expansion decisions |
| 4 | Department Heads | Department-internal decisions within charter scope |
| 5 | Engineering Contributors | Implementation decisions within approved sprint scope |

### 13.2 Document Authority Hierarchy

In case of conflict between documents, the higher-numbered document prevails:

1. Historical documents (archived records, preserved for reference)
2. PROJECT_STATUS.md (version, progress, completed items)
3. ROADMAP.md (phased plan and gates)
4. CURRENT_STATE.md (canonical project snapshot)
5. **PROJECT_CONSTITUTION_V2.md** — This file (supreme authority)

### 13.3 Decision Rules

- A decision is only produced after reasoning is complete.
- Reasoning is only performed over evidence retrieved from the Brain.
- The Brain only retrieves evidence backed by the Knowledge Engine.
- Every decision must state: what evidence supports it, what evidence contradicts it, and the system's confidence.
- No decision may claim certainty. Every decision carries explicit confidence and sample size.
- Decisions are advisory until backtesting and paper trading gates pass.
- Decisions must degrade gracefully: insufficient evidence produces "insufficient evidence," never a guess.

---

## 14. Change Management Process

### 14.1 Development Workflow

Every engineering task follows this sequence without exception:

```
1. Propose   → Documented intent stating which layer it touches and why
2. Review    → Check against this constitution for violations
3. Implement → Smallest complete unit that produces a working artifact
4. Test      → Deterministic tests written or updated
5. Benchmark → 18-benchmark suite passes with zero regressions
6. Verify    → Documented pipeline still runs end-to-end from clean clone
7. Document  → Update relevant architecture doc, ADR, or roadmap in same change
8. Commit    → Small, reviewable commit with passing tests
```

### 14.2 Constitutional Amendment Process

1. Proposal submitted with exact text, rationale, and impact assessment.
2. Review against all existing rules for consistency.
3. Chief Architect approval required.
4. Amendment recorded in the Amendment Log (Section 16) with date and summary.
5. All dependent documents updated in the same change.

### 14.3 Architecture Decision Process

1. Problem statement and context documented.
2. Alternatives evaluated with evidence.
3. Decision recorded as ADR in `docs/adr/`.
4. Architecture docs in `docs/architecture/` updated in the same change.
5. Rejected alternatives preserved with their rejection rationale.

### 14.4 Sprint Process

1. Sprint readiness document verifying prerequisites and architectural compliance.
2. Implementation following the development workflow (14.1).
3. Sprint completion document with test counts, regression status, and deliverables.
4. CURRENT_STATE.md and ROADMAP.md updated.

### 14.5 Frozen Core Change Process

Frozen Core modifications are extraordinary events requiring:

1. Verified engineering defect that cannot be corrected elsewhere.
2. Root cause analysis documenting why the fix cannot be applied outside the frozen component.
3. Architecture Council approval.
4. Smallest possible change with zero regressions.
5. Full benchmark suite must pass after the change.
6. Amendment Log entry documenting the exception.

---

## 15. Definition of Done

### 15.1 Knowledge Object — Done When:

- [ ] Frozen dataclass defined in department's `contracts.py`
- [ ] All mandatory fields from the Institutional Knowledge Contracts document are present
- [ ] Common contract framework fields (identity, confidence, provenance, evidence references, validity period, time horizon) are implemented
- [ ] `to_dict()` / `from_dict()` serialization works
- [ ] Repository save/load works (department's `repository.py`)
- [ ] Evidence Adapter method exists and produces valid `Evidence` instances
- [ ] Lifecycle test passes: create → persist → retrieve → adapt to Evidence
- [ ] Confidence uses the institutional 0.00–1.00 scale
- [ ] No mandatory field is ever null, empty, or absent
- [ ] Determinism: same input produces same output

### 15.2 Department — Done When:

A department is considered operational when it reaches **Minimum Institutional Capability (MIC)**.

MIC requires:

- [ ] Department charter ratified
- [ ] Infrastructure completed (contracts, repository, package initialization)
- [ ] Evidence Adapter completed
- [ ] At least **three canonical knowledge objects** fully implemented, tested, and together capable of producing a coherent institutional assessment
- [ ] Repository persistence verified
- [ ] Pipeline activation completed
- [ ] End-to-end validation completed
- [ ] Regression tests passing
- [ ] No Frozen Core modification required

The remaining knowledge objects defined for the department are classified as **Institutional Expansion**. They are enhancements to analytical depth and coverage, not prerequisites for departmental activation.

This rule is permanent and applies to every present and future institutional department.

### 15.3 Wave — Done When:

- [ ] Wave deliverable produced (per Section 11.6 wave table)
- [ ] Wave gate passed
- [ ] Tests pass with zero regressions
- [ ] Completion document written with test counts and deliverable summary
- [ ] CURRENT_STATE.md updated (sections 4, 6, 7, 8)
- [ ] No Frozen Core modifications required

### 15.4 Phase — Done When:

- [ ] All waves within the phase are Done
- [ ] Phase gate criteria satisfied (as defined in ROADMAP.md)
- [ ] Full test suite passes: `py -3 -m pytest -q` from clean clone
- [ ] 18-benchmark suite passes with zero regressions
- [ ] ROADMAP.md phase marked complete
- [ ] CURRENT_STATE.md phase transition recorded
- [ ] No items deferred without explicit documentation
- [ ] All documentation synchronized with implementation

---

## 16. Amendment Log

- 2026-07-26: Constitution v2 ratified. Established as supreme governing document. Consolidated all governance from PROJECT_NORTH_STAR.md (v1.1), PROJECT_CONSTITUTION.md (v1), CURRENT_STATE.md governance sections, CER-010 freeze decisions, and Institutional Knowledge Contracts. Defined 15 permanent sections governing mission, engineering principles, architecture, departments, knowledge objects, adapters, evidence, validation, GitHub operations, benchmarks, expansion, inviolable rules, decision hierarchy, change management, and definition of done.
- 2026-07-27: Amendment 1 — CAI knowledge object inventory in Section 5.2 updated from aspirational 8-object design to 5-object implementation as resolved by CAI-Naming-Resolution.md. Aspirational names (CrossAssetStrengthMatrix, CorrelationStabilityIndex, DivergenceAlert, LiquidityRotationMap, SafeHavenRotationIndex, DollarPressureIndex, CrossAssetRegimeAssessment, InstitutionalConfirmationMatrix) replaced with implemented names (CrossAssetCorrelation, SpreadAnalysis, RelativeValueAssessment, FlowPressure, VolatilityRegime). CBI inventory also corrected from 10 aspirational to 5 implemented (BalanceSheetOutlook, PolicyDivergenceMatrix, HawkDoveScore, CentralBankSurpriseIndex, PolicyPathAssessment moved to expansion pending). Two objects pending as Institutional Expansion (RelativeValueAssessment, FlowPressure require adapter methods and test coverage). No implementation changes required.

---

*PROJECT CONSTITUTION v2 — Permanent Governing Document*
*AurumAI Institutional Financial Intelligence System*
