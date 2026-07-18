# AurumAI Project Constitution

Status: Ratified
Owner: Lead Software Engineer (CTO role, per docs/08_AI_Agents.md)
Precedence: This document is the highest-level authority in the repository.

If any other document, ADR, comment, or piece of code conflicts with this
constitution, this constitution wins. The conflicting artifact must be
updated to match it, not the other way around. Amendments to this
constitution require an explicit decision recorded as a dated entry in the
Amendment Log at the bottom of this file.

---

## 1. Vision

AurumAI is a Market Intelligence Operating System for gold and macro markets.

It exists to understand markets the way a disciplined senior analyst does:
by collecting evidence, converting that evidence into durable knowledge,
reasoning over current context against that knowledge, and only then
forming a judgment. Execution, if it ever happens, is the last and smallest
part of the system, not the point of it.

AurumAI is explicitly **not** a trading bot. A trading bot optimizes for
signals and profit. AurumAI optimizes for understanding, and treats trading
as one possible, optional, heavily-gated downstream consumer of that
understanding.

---

## 2. Mission

Build the strongest possible Market Intelligence Engine for gold and macro
markets, one that:

- Learns from history instead of curve-fitting to it.
- Explains what it knows and why, in language a human analyst would accept.
- Reasons over macroeconomic events, price action, liquidity, and news as
  interconnected evidence, not isolated signals.
- Represents that evidence as a temporal knowledge graph, not a flat table,
  so relationships between events, assets, and outcomes can be queried,
  traversed, and revised as new evidence arrives.
- Refuses to produce a decision it cannot justify with evidence.

Every module that gets built should move the system closer to this mission.
Every module that only produces a trade signal without evidence is a
regression against the mission, even if it is profitable in a backtest.

---

## 3. Long-Term Goal (10+ Years)

AurumAI is built to still be correct, extensible, and trustworthy in ten
years, not just to ship a demo this quarter. Concretely, that means:

- The knowledge accumulated today (lessons, evidence, graph relationships)
  must remain valid and queryable regardless of which model, library, or
  agent framework is fashionable at the time. Knowledge outlives tooling.
- The system should be able to absorb new asset classes (beyond gold),
  new macro regimes, and new data sources without an architectural rewrite,
  because the core abstractions (Event, Evidence, Lesson, Knowledge Record,
  Graph Node/Relation) are asset-agnostic by design.
- The system should be able to explain a decision made ten years ago using
  the evidence that was available at that time, which requires lessons and
  evidence to be versioned and immutable, never silently overwritten.
- Execution capability, if reached, must remain the last, most heavily
  gated layer. A ten-year system that blows up an account in year one
  because gating was skipped has failed its own long-term goal.
- The system should get smarter as it ages: every new event that occurs
  becomes a new lesson, every new lesson refines existing knowledge records,
  and every refinement is itself explainable and traceable to its source
  evidence.

---

## 4. Core Principles

1. **Explainable AI.** No output reaches a human or a downstream system
   without a chain of evidence a human can inspect and challenge.
2. **Modular Architecture.** Each layer (Data Sources, Data Engine,
   Knowledge Engine, Brain, Reasoning Engine, Decision Engine, Execution
   Engine) is independently testable and replaceable without rewriting its
   neighbors.
3. **Data First, AI Second.** Do not reason over data you have not
   validated. Do not decide before you have reasoned.
4. **Risk Before Profit.** Every layer that touches money must be gated by
   risk controls that are stricter than the layer's own confidence in
   itself.
5. **Continuous Learning.** New evidence updates knowledge; it does not
   get discarded after a single use.
6. **Test Everything.** An untested module is an unverified claim, not a
   working component.
7. **Open Source First.** Never rebuild a problem a mature open-source
   project already solves well. Integrate, extend, or adapt it behind a
   stable internal interface instead.
8. **Evidence Over Assertion.** "The Brain believes X" is not acceptable
   output. "The Brain found N historical cases supporting X, with this
   confidence, from these sources" is the minimum acceptable output.

---

## 5. Non-Negotiable Rules

1. Do not build what already exists as a mature, actively maintained
   open-source solution. Evaluate before implementing.
2. Every module must be independent: it must have a stable public
   interface, and internal changes to one module must not require changes
   to unrelated modules.
3. Every decision the system produces must be explainable in plain
   language, tracing back to specific evidence.
4. No real trading before successful backtesting and paper trading have
   both passed their defined gates. No exceptions, no shortcuts.
5. Every sprint must produce a working, runnable artifact, not partial or
   broken code left for "later."
6. Do not move to the next roadmap phase until the current phase passes
   its gates.
7. Fix root causes, not symptoms. A broken import gets fixed by fixing the
   import graph, not by adding a second workaround path next to it.
8. Build for a ten-year system, not a one-day bot.
9. Lessons, once written, are immutable. Corrections are appended as new,
   versioned lessons, never as in-place edits that erase history.
10. The documented pipeline in README.md must always be runnable from a
    clean clone. If a change breaks it, the change is not complete.
11. Duplicate implementations of the same responsibility must not coexist
    silently. When discovered, they must be resolved through an explicit
    migration decision (see Section 15 and the Migration Plan), not left
    for future confusion.

---

## 6. Coding Standards

- **Language:** Python 3, using the project's `pyproject.toml` as the
  single source of truth for dependencies and package layout (`src`-rooted
  package).
- **Imports:** Use consistent, absolute imports relative to the installed
  package root (i.e. `from knowledge.x import y`, not
  `from src.knowledge.x import y`, and not manual `sys.path` patching
  scattered across entry points). If the package is not consistently
  importable without path hacks, that is a packaging bug to fix, not a
  pattern to repeat.
- **No dead code in the main branch.** Unused dataclasses, unused
  repository wrappers, or scaffolding left over from an abandoned approach
  must be either wired in or explicitly retired via the migration process,
  not left in place indefinitely.
- **No duplicated logic.** If two modules solve the same problem
  (e.g. two lesson builders, two gold downloaders), one is canonical and
  the other is migrated or removed per Section 15.
- **Fail fast, fail loud.** Validation errors (missing columns, bad
  schema, missing config) must raise clear, specific exceptions. Silent
  fallbacks that hide data quality problems are forbidden.
- **Every public function/class that produces a number a human will read
  (confidence, bias, return, volatility) must have a docstring or comment
  stating the formula and its known limitations.**
- **Tests live next to the layer they test**, use deterministic fixtures
  (no live network calls in unit tests), and must pass before a sprint is
  considered complete.
- **Config and secrets** are loaded through environment variables (dotenv
  via `python-dotenv`) only. Secrets are never hardcoded, never logged,
  and `.env` must never be assumed safe to print or commit.
- **Formatting/quality tooling** (linter, formatter, type checker) should
  be adopted as soon as the codebase stabilizes past the current
  Knowledge Engine sprint; until then, consistency with existing style in
  the file being edited takes priority over introducing a new style.

---

## 7. AI Agent Rules

AI models are tools inside AurumAI. They implement under supervision; they
do not own architecture.

- **CTO / Lead Software Engineer role** (currently filled by this
  constitution's author and its ratifying process): owns architecture,
  technical decisions, code review, roadmap, priorities, and protects
  project direction against scope drift. Only this role may approve a
  change to this constitution.
- **Python Engineer role:** implements algorithms, utilities, and focused
  tasks assigned by the CTO role. Must not redesign project architecture
  without explicit CTO review and approval.
- **Research Engineer role:** gathers evidence from papers, GitHub
  projects, APIs, books, and articles, and proposes candidates for the
  approved open-source stack. Research proposals are evaluated, not
  auto-adopted (see Section 11).
- **Reviewer role:** compares approaches, measures quality, identifies
  weak points, and suggests improvements, but does not merge changes.
- **Approval rule:** code or documentation generated by any agent (human
  or AI) is not accepted into the repository until reviewed against this
  constitution: project identity, architecture, module boundaries, tests,
  explainability, and open-source reuse policy.
- **No agent, human or AI, may silently delete functionality.** Any
  removal of existing capability must go through the migration process in
  Section 15.

---

## 8. Knowledge Rules

- **Immutability.** A Lesson, once produced and persisted, is never
  mutated. New information produces a new, versioned lesson.
- **Traceability.** Every Knowledge Record must be traceable to the exact
  set of lessons (and ultimately raw data points) that produced it.
- **Confidence must be disclosed, not implied.** Any confidence, bias, or
  probability score must state its computation method in the record
  itself or in adjacent documentation. A confidence score with an
  undocumented formula is treated as a bug.
- **Knowledge is asset- and event-type-agnostic in structure.** The schema
  for a Lesson or Knowledge Record must not hardcode "CPI" or "gold" into
  its structural fields; those are values within a generic schema
  (event_type, asset, condition), so the same structures serve NFP, DXY,
  yields, or any future asset without a schema rewrite.
- **The Knowledge Graph is the long-term home of knowledge**, superseding
  today's flat CSV/JSON files once the migration in Section 15 lands. The
  Brain queries the graph; it does not re-derive knowledge from raw
  lessons on every call.
- **No knowledge record may claim a sample size, win rate, or return it
  cannot reproduce from its underlying lessons.** Knowledge Engine outputs
  must be regenerable and deterministic from the same input lessons.

---

## 9. Architecture Principles

AurumAI is organized into seven layers. Each layer has one responsibility
and depends only on the layer(s) below it, never sideways or upward.

1. **Data Sources** - external providers and mature libraries (Yahoo
   Finance, FRED, TradingEconomics, NewsAPI, MT5, AlphaVantage, Polygon,
   Binance, Reddit, X). AurumAI does not rebuild these; it wraps them.
2. **Data Engine** - collects, cleans, normalizes, validates, and stores
   data. It does not analyze or decide.
3. **Knowledge Engine** - transforms historical data into immutable
   lessons, aggregates lessons into knowledge records, and stores
   relationships in a temporal knowledge graph.
4. **Brain** - understands relationships and retrieves evidence-backed
   knowledge. It does not produce trade signals.
5. **Reasoning Engine** - combines macro, price, news, liquidity, and
   historical lessons into a confidence assessment, using multi-agent
   evidence-based reasoning (never black-box).
6. **Decision Engine** - produces explainable decisions only after
   reasoning is complete, and only within risk constraints defined ahead
   of time.
7. **Execution Engine** - the last layer. May connect to a broker (MT5,
   Binance, etc.) only after backtesting and paper trading have both
   passed their gates.

Architectural rules:

- Each layer must be swappable behind a stable interface (e.g. the
  Knowledge Engine's storage backend can move from JSON files to a graph
  database without the Brain's public interface changing).
- No layer may skip the layer below it. The Decision Engine cannot read
  raw data directly; it must go through Reasoning, which must go through
  the Brain, which must go through the Knowledge Engine.
- Backends are chosen for the smallest complexity that satisfies current
  scale, with an explicit, documented upgrade path (see ADR-0001: start
  with NetworkX, migrate to Neo4j/GraphRAG when graph size or query needs
  require it).

---

## 10. Decision Principles

- A decision is only produced after reasoning is complete. Reasoning is
  only performed over evidence retrieved from the Brain. The Brain only
  retrieves evidence backed by the Knowledge Engine.
- Every decision must state: what evidence supports it, what evidence
  contradicts it, and the system's confidence, in terms a human can
  audit.
- No decision may claim certainty. Every decision carries an explicit
  confidence level and the sample size or evidence base it was derived
  from.
- Decisions are advisory until backtesting and paper trading gates are
  passed (Rule 4, Section 5). Even after passing those gates, the
  Execution Engine remains a separate, deliberately-gated layer.
- Decisions must degrade gracefully: if evidence is missing or
  insufficient, the correct output is "insufficient evidence," never a
  guess dressed up as a decision.

---

## 11. Explainability Principles

- Every number the system surfaces (confidence, bias, win rate, average
  return) must be reproducible by re-running the pipeline against the
  same input data.
- Every qualitative label ("gold_positive_bias", "mixed_or_context_dependent")
  must have a documented, fixed threshold that produced it.
- The system must never emit directive trading language ("BUY", "SELL")
  from the Knowledge Engine or Brain layers. That language, if it ever
  exists, is confined to the Decision Engine and only after all gates
  in Section 5 Rule 4 are satisfied.
- Explanations must name their evidence: "N historical cases," "from
  source S," "as of date D." A confidence score without a named evidence
  set is not an explanation.
- When the system cannot explain something, it must say so explicitly
  (`missing_context`, `missing_knowledge`, `insufficient_evidence`)
  rather than staying silent or guessing.

---

## 12. Research Principles

- Research candidates (papers, open-source projects, architectures) are
  proposed by the Research Engineer role and recorded in `research/` with
  a clear status: Approved, Rejected, or Use Ideas Only.
- "Use ideas only" is a valid, first-class outcome: a project can inform
  design without being adopted as a dependency (see
  `research/projects/marketmind_vs_kquant.md`).
- A research candidate becomes part of the approved stack only via an
  ADR in `docs/adr/`, stating the decision, the reason, and the status.
- Research findings that materially change architecture (e.g. adopting a
  temporal knowledge graph library) must be reflected in both the
  relevant ADR and the architecture docs in the same change, so the two
  never drift apart the way they currently do.
- Rejected or superseded research should stay in the repository with its
  status marked, as a record of why a path was not taken. It is not
  deleted.

---

## 13. Repository Organization

- `docs/` - authoritative documentation. This constitution is the top of
  that hierarchy. `docs/adr/` holds point-in-time architecture decisions;
  `docs/architecture/` holds living architecture descriptions that must
  stay in sync with accepted ADRs.
- `research/` - candidate evidence for future ADRs: papers, dataset
  sources, competing project comparisons. Not authoritative until
  promoted into an ADR.
- `src/` - the installable `aurumai` package. Currently contains the
  `knowledge/` subpackage (the Intelligence Core). Every subpackage under
  `src/` must map to exactly one layer from Section 9. A subpackage that
  does not map cleanly to a layer is a sign the architecture needs a
  decision, not a new folder. Legacy subpackages (`collectors/`,
  `database/`, `teacher/`, `core/`, `utils/`) have been removed following
  the migration process in Section 15.
- `tests/` - mirrors the `src/` layer structure closely enough that any
  reader can find the test for a module without guessing.
- `data/` - local, regenerable artifacts (raw economic series, gold
  history, generated lessons, generated knowledge, memory store). Nothing
  in `data/` is hand-edited; everything here is either fetched from a
  Data Source or produced by a script in `src/`.
- `configs/`, `models/`, `notebooks/` - reserved for their stated purpose
  as the project grows into Reasoning/Decision layers; they must not
  become dumping grounds for unrelated scripts. (Currently empty.)
- `archive/` - historical sprint reports, review artifacts, and bootstrap
  scripts retained for reference. Content here is not authoritative.
- `scripts/` - (Removed; single historical script archived to `archive/scripts/`.)

---

## 14. Module Responsibilities

- **`src/knowledge/`** - the Intelligence Core. Owns lesson schemas,
  lesson building, lesson aggregation into knowledge records, the
  knowledge graph, evidence query and ranking, reasoning chains,
  decision engine, learning engine, and three intelligence layers
  (economic, temporal, causal). This is the only active subpackage in
  `src/` and is the single source of truth for all intelligence behavior.
  See [architecture/knowledge_engine.md](architecture/knowledge_engine.md)
  for the canonical inference flow.
- **`src/knowledge/integrity/`** - provenance tracking (created_at,
  source, version, chain), lineage registry for full entity traceability,
  and versioned store for append-only immutable history.
- **`src/knowledge/orchestration/`** - adapter pattern around the canonical
  `InferencePipeline`. Coordinates Economic + Temporal + Causal + Core
  layers in one pass, aggregates evidence, and delegates reasoning and
  decision to the canonical pipeline components.
- **`src/knowledge/builders/`** - lesson construction. Contains the
  canonical `lesson_builder.py` and supporting scripts.
- **`src/knowledge/pipeline/`** - the `InferencePipeline` entry point.
  Owns the 6-stage canonical pipeline (lessons → knowledge → graph →
  evidence → reasoning → decision).
- **`src/knowledge/decision/`** - decision engine and repository.
- **`src/knowledge/reasoning/`** - reasoning engine and chain
  construction.
- **`src/knowledge/evidence/`** - evidence query, ranking, and
  repository.
- **`src/knowledge/graph/`** - knowledge graph construction and
  repository.
- **`src/knowledge/learning/`** - learning engine, session tracking, and
  feedback generation.
- **`src/knowledge/events/`** - event type definitions (CPIEvent,
  MacroEvent ABC).
- **`src/knowledge/features/`** - feature extraction engine and
  extractors.
- **`src/knowledge/economics/`** - economic intelligence layer (regime,
  state, cycle classification).
- **`src/knowledge/temporal/`** - temporal intelligence layer (time
  indexing, querying, adapters).
- **`src/knowledge/causal/`** - causal intelligence layer (relations,
  hypotheses, analysis).
- **`src/knowledge/context/`** - yield context enrichment (US10Y).
- **`src/knowledge/models/`** - entity schemas (lesson, knowledge
  record).
- **`src/knowledge/repository/`** - lesson repository and
  serialization.
- **`src/knowledge/validation/`** - schema and data validation utilities.

### Legacy Modules (Retained for Reference)

Certain modules under `src/knowledge/` represent previous architectural
iterations and are retained as a Legacy Layer. They are not "dead code":
they document the evolution of the architecture and may become useful
during future migrations as reference implementations.

- **`src/knowledge/brain.py`** — `EconomicBrain` legacy compatibility
  component (per ADR-0004).
- **`src/knowledge/memory.py`** — flat `Memory` legacy compatibility
  component (per ADR-0004).
- **`src/knowledge/rules.py`** — `RULES` legacy fallback (per ADR-0004).
- **`src/knowledge/lesson_summary.py`** — `LessonSummaryAggregator`
  (active, wired into pipeline).
- **`src/knowledge/build_knowledge.py`** — standalone script for
  knowledge aggregation.
- **`src/knowledge/builders/csv_to_lessons.py`** — early lesson schema
  mapper, retained as migration reference.
- **`src/knowledge/builders/historical_teacher.py`** — legacy bootstrap
  logic, retained as migration reference.

These modules are NOT wired into the current pipeline. They MUST NOT be
deleted without an ADR decision, but they MUST NOT gain new functionality.
New code belongs in the active architecture.

### Legacy Layer

Certain modules under `src/knowledge/` represent previous architectural
iterations and are retained as a Legacy Layer. They are not "dead code":
they document the evolution of the architecture and may become useful
during future migrations as reference implementations or as sources of
schema designs for new event types.

Current Legacy Layer modules:

- **`src/knowledge/models/lesson.py`** — an early `Lesson` dataclass
  whose schema predates the current lesson CSV format. Retained as a
  reference for future typed-lesson migration.
- **`src/knowledge/builders/csv_to_lessons.py`** — a function that maps
  CSV rows to the `Lesson` dataclass. Retained alongside the model it
  serves.
- **`src/knowledge/repository/lesson_repository.py`** — an early
  repository wrapper around a lesson CSV. Retained as a reference for
  future Repository abstraction design.
- **`src/knowledge/events/__init__.py`** — the `EconomicEvent` enum,
  retained as a human-readable registry of event types that the
  `MacroEvent` ABC may one day absorb.

These modules are NOT wired into the current pipeline. They are NOT
imported by any working code. They MUST NOT be deleted without an ADR
decision, but they MUST NOT gain new functionality. New code belongs
in the active architecture.

---

## 15. Development Workflow

1. **Propose:** a change starts as a documented intent (issue, sprint
   note, or ADR draft) stating which layer it touches and why.
2. **Review against the constitution:** does it violate a non-negotiable
   rule, duplicate existing functionality, or skip a layer? If so, resolve
   that first.
3. **Implement in the smallest complete unit that produces a working
   artifact** (Rule 5, Section 5). Partial, broken states are not
   committed as "done."
4. **Test:** deterministic tests are written or updated before the change
   is considered complete. `py -3 -m pytest -q` must pass from a clean
   clone.
5. **Verify the documented pipeline still runs** end to end
   (`build_lessons` -> `build_knowledge` -> `brain`), per Rule 10.
6. **Document:** update the relevant architecture doc, ADR, or roadmap
   entry in the same change, not as a follow-up.
7. **Small commits, daily progress** (Coding Rule 6): prefer several
   small, reviewable commits over one large one.
8. **Migration, not silent deletion:** if a change makes an existing
   module redundant, follow the migration plan process: document the
   duplication, propose the canonical target, migrate callers, only then
   retire the old module in a dedicated commit that says so explicitly.

---

## 16. Architecture Note — Feature Extraction Layer

### Context

Currently, every `MacroEvent` implementation is responsible for both
loading raw data AND extracting features from it inside
`load_and_extract()`.  For CPI, this means `CPIEvent.load_and_extract()`
reads a CSV, parses dates, computes `cpi_change_pct`, classifies
`cpi_pressure`, and returns a complete feature DataFrame.

This works for CPI, but as more event types are added (NFP, FOMC, PPI,
PMI, GDP, DXY, Yields …), several problems will surface:

1. Feature extraction logic will be duplicated across events (every event
   needs date parsing, numeric coercion, sorting, deduplication).
2. Features cannot be introspected, validated, or composed independently
   of their source event.
3. There is no standard interface for a "feature" — they are implicit
   column names in a DataFrame.
4. The `LessonBuilder` cannot know what features an event produces
   without calling `load_and_extract()` first.

### Target Architecture

An active `FeatureExtractionEngine` layer between `MacroEvent` and
`LessonBuilder`:

```
MacroEvent
    │
    ▼
FeatureExtractionEngine
    │  - validates feature schema
    │  - normalises types and units
    │  - registers feature metadata (name, type, source, description)
    │  - provides introspection (what features does this event produce?)
    ▼
LessonBuilder
    │  - receives feature-rich DataFrame + feature metadata
    │  - aligns with asset data
    ▼
Knowledge Builder → Brain
```

### How It Works

- **`MacroEvent`** keeps `load_and_extract()` but it now returns a
  lightweight, validated raw record set rather than a full feature
  DataFrame.  The event still owns its data loading logic.
- **`FeatureExtractionEngine`** is the new home for:
  - Date parsing and normalisation
  - Numeric coercion and NaN handling
  - Computed feature derivation (e.g. `cpi_change_pct` from
    `cpi_value`)
  - Condition classification (e.g. `cpi_pressure` from
    `cpi_change_pct`)
  - Feature schema registration (each extracted feature has a name,
    type, description, and source expression)
  - Schema validation before passing data to `LessonBuilder`
- **`MacroEvent`** (or a companion `FeatureDefinition` class) declares
  *what* features it produces, not *how* to compute them.
  `FeatureExtractionEngine` handles *how*.

### Migration Status

1. Design the `Feature` metadata schema (dataclass or TypedDict).
2. Add `feature_definitions` property to `MacroEvent` ABC (returns a
   list of `Feature` objects).
3. Implement `FeatureExtractionEngine` as a callable or class that
   takes a raw event DataFrame + its feature definitions and returns a
   validated feature DataFrame.
4. Refactor `CPIEvent.load_and_extract()` to return raw parsed data and
   move `cpi_change_pct` / `cpi_pressure` computation into
   `FeatureExtractionEngine` or into `feature_definitions`.
5. Wire `FeatureExtractionEngine` into `LessonBuilder` so it runs
   between event loading and lesson alignment.
6. Keep the old `MacroEvent.load_and_extract()` contract working during
   migration by providing a default passthrough.

### Status

Implemented and covered by the test suite. This section remains as the
authoritative architecture note for future event types and feature
extractors.

---

## Amendment Log

- 2026-07-15: Constitution ratified. Ordered above all existing docs.
  Established migration process for existing duplicate modules
  (`src/teacher/` vs `src/knowledge/builders/`) rather than immediate
  deletion, per explicit instruction not to remove functionality without
  a proposed migration strategy.
- 2026-07-15: Added `knowledge_version` to `MacroEvent` ABC.  Refactored
  `EconomicBrain` to derive metadata from `MacroEvent` subclasses
  instead of a hand-written registry dict.  Legacy Layer documented in
  Section 13.  Architecture TODO — Feature Extraction Layer added as
  Section 16.
- 2026-07-16: Updated repository truth after Intelligence Core expansion.
  Recorded Feature Extraction Layer as implemented, aligned roadmap and
  progress documents with the existing inference, reasoning, decision,
  learning, temporal, causal, and economic intelligence layers, and
  configured repository-local pytest temp isolation.
- 2026-07-16: Added optional US10Y yield context enrichment between lesson
  building and knowledge aggregation. This enables multi-factor knowledge
  records without changing the execution boundary or bypassing the existing
  evidence, reasoning, and decision path.
- 2026-07-16: Added a context comparison report to evaluate single-factor
  knowledge against context-conditioned knowledge before accepting more macro
  context. This keeps context expansion data-driven instead of complexity-driven.
- 2026-07-16: Wired context comparison into the inference pipeline as an
  optional first-class artifact. The pipeline can now persist
  `context_comparison.json` from a baseline knowledge summary and the current
  context-conditioned summary.
- 2026-07-17: Core Repository Hygiene — removed legacy subpackages
  (`collectors/`, `database/`, `teacher/`, `core/`, `utils/`, `main.py`)
  following the Section 15 migration process. Updated Sections 13 and 14
  to reflect the current `src/` structure (only `knowledge/` remains
  active). Added `archive/` to repository organization. Established
  Documentation Index (`docs/INDEX.md`) as the single source of truth for
  topic locations and converted duplicate docs into canonical references.
