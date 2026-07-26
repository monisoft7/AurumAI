# Sprint-004: KnowledgeRecord — Canonical Institutional Context Review

**Date:** 2026-07-25  
**Status:** Ownership Analysis — No Implementation  

---

## 1. Current KnowledgeRecord Schema

File: `src/knowledge/integrity/knowledge_record.py`

```python
@dataclass(frozen=True)
class KnowledgeRecord:
    knowledge_id: str
    event_type: str
    asset: str
    condition: dict[str, str]
    horizon_days: int
    sample_count: int
    positive_return_rate_pct: float
    negative_return_rate_pct: float
    up_direction_rate_pct: float
    down_direction_rate_pct: float
    flat_direction_rate_pct: float
    average_return_pct: float
    median_return_pct: float
    min_return_pct: float
    max_return_pct: float
    first_event_date: str
    last_event_date: str
    bias: str
    confidence: float
    explanation: str
    source_lesson_ids: tuple[str, ...] = ()
    source_artifact_path: str = ""
    source_artifact_sha256: str = ""
    provenance: Provenance | None = None
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())
```

### Field Semantics

| Field | Type | Role |
|-------|------|------|
| `condition` | `dict[str, str]` | The **event's analytical condition** — values of the event that define which historical bucket this record belongs to (e.g., `{"cpi_pressure": "inflation_pressure_up"}`). Used as grouping key in `LessonSummaryAggregator` and exact-match filter in `EvidenceQuery`. |
| `provenance` | `Provenance \| None` | Origin and versioning metadata — `created_at`, `created_by`, `entity_version`, `previous_version_id`. |
| `metadata` | `dict[str, Any]` | Unstructured extension bag. Used downstream by `EvidenceQuery._node_to_evidence()` as a full property dump (`metadata=dict(props)`), and by `KnowledgeCalibrator` for preserving record metadata through calibration. |
| All other fields | Various | Statistical summaries of the lesson group (return rates, direction rates, sample count, confidence, etc.). |

---

## 2. Existing Extension Points

### 2a. `condition: dict[str, str]`

**Purpose:** Event condition values used for grouping and filtering.

**Current usage in aggregation flow:**
1. `LessonSummaryAggregator` groups by `condition_columns` (default: `("cpi_pressure",)`)
2. Each group produces one `KnowledgeRecord` with `condition` = the group's key
3. `GraphBuilder` creates `RELATION_SAME_CONDITION` edges between records with identical condition dicts
4. `EvidenceQuery.matching()` filters by exact condition match
5. `HistoricalSituationRetriever` computes Jaccard similarity on condition keys
6. `ReasoningEngine` includes condition in step conclusions and context descriptions

**Can `condition` represent institutional context?**

If `macro_regime` were added to `condition_columns`, lessons would be grouped by `(cpi_pressure, macro_regime)` instead of just `(cpi_pressure,)`. This would produce separate KnowledgeRecords for `cpi_pressure=UP, macro_regime=EXPANSION` vs `cpi_pressure=UP, macro_regime=CONTRACTION`.

This is semantically incorrect: macro_regime is the **environmental context** in which the event occurred, not a condition of the event itself. The event's analytical condition (`cpi_pressure=UP`) is invariant across regimes. Grouping by regime fragments the statistical sample without adding analytical precision — the record's statistics should describe the event's behavior, not slice by regime.

Furthermore, `EvidenceQuery.matching()` requires exact-match on condition. To find evidence for `cpi_pressure=UP` you would need to know the regime of the current event. This conflates query-time context with historical grouping context.

**Verdict: `condition` cannot represent institutional context.** They are orthogonal analytical dimensions.

### 2b. `provenance: Provenance | None`

**Structure:**
```python
@dataclass(frozen=True)
class Provenance:
    created_at: str
    created_by: str
    entity_version: str
    previous_version_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())
```

**Purpose:** Track the origin and versioning of a knowledge record. `created_by` identifies the pipeline/component that produced it, `entity_version` tracks calibration iterations, `previous_version_id` links to predecessor versions.

**Can `provenance` represent institutional context?**

Institutional context is analytical content — the macro environment at the time of the observed events. It describes the **subject matter** of the record, not the **provenance of the record itself**. Putting institutional context into `provenance` would conflate "what the record describes" with "how the record was created."

`Provenance.metadata` is already used for calibration source tracking (`{"calibration_source": feedback.feedback_id}`). Using it for institutional context would mix two unrelated concerns.

**Verdict: `provenance` is structurally inappropriate for institutional context.**

### 2c. `metadata: dict[str, Any]`

**Purpose:** Unstructured extension bag. Present on `KnowledgeRecord`, `Evidence`, `Provenance`, `Decision`, `DecisionContext`, `ReasoningStep`.

**Current usage in the codebase:**

| Location | Usage |
|----------|-------|
| `EvidenceQuery._node_to_evidence()` | `metadata=dict(props)` — dumps ALL node properties into Evidence.metadata. This is a pass-through, not a semantic use. |
| `KnowledgeCalibrator.calibrate()` | `metadata=dict(knowledge_record.metadata)` — preserves metadata through calibration. Purely pass-through. |
| `DecisionEngine.decide()` | `metadata={"avg_return_pct": ..., "chain_confidence": ...}` — stores computed metrics. |
| `OrchestrationEngine._run_economic()` | `metadata["_source_layer"] = "economic"` — tags evidence source layer. |

**Is metadata defined as canonical institutional knowledge?**

No. The architecture does not define `metadata` as canonical institutional knowledge. It is:
- A full-property dump in `EvidenceQuery` (all node properties → metadata)
- A pass-through preservation mechanism in `KnowledgeCalibrator`
- A tagging mechanism in `OrchestrationEngine` (`_source_layer`)
- A metric store in `DecisionEngine`

There is zero precedent for `metadata` carrying semantically typed institutional context. Using it for institutional context would make context:
- **Unsearchable** — no typed field to query against
- **Unfilterable** — arbitrary key names with no schema validation
- **Second-class** — invisible to serialization/deserialization contracts
- **Fragile** — downstream consumers must know opaque key names

**Verdict: `metadata` is not architecturally defined as canonical institutional knowledge. Using it would violate KnowledgeRecord's role as the canonical institutional knowledge entity.**

---

## 3. Canonical Ownership

### What KnowledgeRecord owns

KnowledgeRecord is defined as the **single source of truth for institutional knowledge** in this architecture. It is:
1. The output of `LessonSummaryAggregator.build()` (aggregated from lessons)
2. The input to `GraphBuilder.build()` → `KnowledgeGraph` → `EvidenceQuery`
3. The input to `KnowledgeCalibrator.calibrate()` (evolution)
4. Preserved through serialization/deserialization in `from_dict()` / `to_dict()`
5. Persisted as JSON and stored in the graph database

### What KnowledgeRecord does NOT yet own

| Concept | Ownership | Status |
|---------|-----------|--------|
| Event analytical condition | KnowledgeRecord.`condition` | Owned |
| Return statistics | KnowledgeRecord fields | Owned |
| Creation provenance | KnowledgeRecord.`provenance` | Owned |
| **Institutional context** | **NOWHERE** | **Unowned** |
| Lesson source IDs | KnowledgeRecord.`source_lesson_ids` | Owned |

### The gap

Institutional context (`macro_regime` and future contexts like `liquidity_regime`, `volatility_regime`, `geopolitical_state`) is produced by `FeatureExtractionEngine`, forwarded into lesson dicts by `LessonBuilder._add_institutional_context()` (Sprint-003), but is **dropped before reaching KnowledgeRecord** because no field exists to carry it through the aggregation boundary.

All downstream components — Evidence, EvidenceWeighting, HistoricalSituationRetrieval, ReasoningChain, Decision — derive their information from KnowledgeRecord (via GraphNode → Evidence). Since KnowledgeRecord does not contain institutional context, none of these components can consume it.

---

## 4. Recommendation

**Minimal canonical extension**: Add a dedicated `institutional_context: dict[str, str]` field to `KnowledgeRecord`.

### Rationale

| Criterion | Evaluation |
|-----------|------------|
| **Canonical** | A typed, named field on KnowledgeRecord makes institutional context a first-class citizen. It is searchable, filterable, serialized, and preserved through calibration. |
| **Minimal** | One field, one type, one serialization entry. No new classes, no new subsystems, no new files. |
| **Generic** | `dict[str, str]` supports any number of institutional context dimensions with arbitrary key names (`macro_regime`, `liquidity_regime`, `volatility_regime`, etc.). |
| **Backward compatible** | Default empty dict `field(default_factory=dict)` ensures all existing code continues to function without changes. |
| **Orthogonal to condition** | Separate from `condition: dict[str, str]` which continues to represent the event's analytical condition. The two dimensions never conflate. |
| **Preserves single source of truth** | KnowledgeRecord remains the single source of truth — downstream components read context from KnowledgeRecord, not from CSV or config. |
| **Extensible** | No code changes needed for new context types. New context columns flow from LessonBuilderConfig → lesson CSV → LessonSummaryConfig → KnowledgeRecord.institutional_context → downstream consumers. |

### Why not the alternatives

| Alternative | Rejected Because |
|-------------|------------------|
| `condition` field | Fragments grouping by regime, conflates event condition with environmental context, breaks exact-match query semantics. |
| `provenance` field | Conflates analytical content with record origin metadata. |
| `metadata` field | Not architecturally defined as canonical institutional knowledge. Would make context second-class, unsearchable, and fragile. |
| New subclass of KnowledgeRecord | Adds complexity of inheritance, breaks `from_dict()` / `to_dict()` contracts, requires changes to GraphBuilder and pipeline wiring. |
| Separate `InstitutionalContext` dataclass composed into KnowledgeRecord | Over-engineered for current needs. A `dict[str, str]` is sufficient; a dataclass wrapper adds indirection without value until context has behavior. |
| Store context in `source_lesson_ids` referencing external context store | Breaks single-source-of-truth principle, adds I/O dependency, defeats purpose of KnowledgeRecord as self-contained knowledge entity. |

### Impact on downstream components

| Component | How it would consume `institutional_context` |
|-----------|----------------------------------------------|
| `EvidenceQuery` | No change needed. Institutional context flows through `GraphNode.properties` → `Evidence.metadata` automatically (via `metadata=dict(props)`). |
| `HistoricalSituationRetriever` | Reads `evidence.metadata.get("institutional_context", {})` for context similarity computation. |
| `EvidenceWeighter` | Reads `evidence.metadata.get("institutional_context", {})` for context-match weight factor. |
| `ReasoningEngine` | Reads `evidence.metadata` or receives `institutional_context` via `ReasoningContext`. |
| `DecisionEngine` | Receives `institutional_context` via `DecisionContext`. |

### Changes required (if implemented)

```
src/knowledge/integrity/knowledge_record.py
  + institutional_context: dict[str, str] = field(default_factory=dict)
  + freeze in __post_init__
  + serialize in to_dict()
  + deserialize in from_dict()

src/knowledge/lesson_summary.py
  + LessonSummaryConfig.institutional_context: tuple[str, ...]
  + _load_lessons validates context columns exist
  + _summarize_group computes majority context and includes in record dict
```

No changes to: `MacroEvent`, any event class, `FeatureExtractionEngine`, `GraphBuilder`, `EvidenceQuery`, `EvidenceWeighter`, `ReasoningEngine`, `DecisionEngine`, or any existing test.

---

## 5. Architectural Justification

KnowledgeRecord is the **canonical institutional knowledge entity**. This means:
1. It is the authoritative representation of knowledge in the system
2. All downstream consumption derives from it
3. Its schema defines what the system considers "knowledge"
4. Its schema is the contract between knowledge production and consumption

If institutional context is not a first-class field on KnowledgeRecord, then by definition the system does not consider institutional context to be part of "knowledge." Every downstream component that needs context must either:
- Re-derive it from source data (violating the single-source-of-truth principle), or
- Look it up from an external store (adding coupling and latency), or
- Extract it from unstructured `metadata` (fragile, untyped, undocumented)

The presence of `metadata: dict[str, Any]` does **not** solve this — metadata is explicitly an escape hatch, not a canonical storage location. Using it for institutional context would be equivalent to saying "institutional context is not really knowledge."

Adding `institutional_context: dict[str, str]` to KnowledgeRecord declares that institutional context IS knowledge — that it belongs in the canonical knowledge entity, is worth preserving through calibration, is worth serializing, and is available for all downstream consumers to use.
