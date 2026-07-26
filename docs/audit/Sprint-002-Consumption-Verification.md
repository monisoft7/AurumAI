# Sprint-002 Consumption Verification: Macro Regime Through the Institutional Pipeline

**Date:** 2026-07-25  
**Question:** Is the `macro_regime` information produced by Sprint-002 actually consumed by the institutional reasoning pipeline?

---

## Trace: MacroRegimeDetector → InstitutionalAssessment

### Stage 1: MacroRegimeDetector → FeatureExtractionEngine

```
CompositeScoreBuilder.build()
  → MacroRegimeDetector.fit(data)
  → MacroRegimeFeatureExtractor(detector)
  → FeatureExtractionEngine.register_global(extractor)
```

| Question | Answer |
|----------|--------|
| Regime present? | ✅ `_global_extractors` list has one extractor |
| Regime consumed? | ✅ Engine will call `extract()` on global extractors in `process()` |
| Regime ignored? | ❌ Not ignored |

---

### Stage 2: FeatureExtractionEngine.process() → FeatureSet

```
event.load_and_extract(path)
  → engine.process(raw, primary_extractor)
    → primary_extractor.extract(raw) → FeatureSet with event columns
    → FeatureSet.validate()
    → for gx in _global_extractors: gx.extract(data) → adds macro_regime column
    → return FeatureSet
```

| Question | Answer |
|----------|--------|
| Regime present? | ✅ `feature_set.data` contains `macro_regime` column |
| Regime consumed? | ✅ Engine actively calls the regime extractor |
| Regime used for confidence? | ❌ Not applicable at this stage |
| Regime used for reasoning? | ❌ Not applicable at this stage |

---

### Stage 3: FeatureSet → LessonBuilder → Lesson Dict ⚠️ **INFORMATION LOST HERE**

```
LessonBuilder._build_lessons(event_data, gold, horizons)
  → for each row in event_data:
      lesson = {"lesson_id": ..., "event_date": ..., ...}
      lesson.update(self.event.build_lesson_fields(row, anchor_date))  ← KEY CALL
      lesson["lesson_text"] = self.event.lesson_text(lesson)
```

`event_data` (the DataFrame returned by `load_and_extract()`) **has** the `macro_regime` column. But the lesson dict is constructed from two sources:

1. **Standard fields** (lesson_id, event_type, event_date, gold values, etc.) — hardcoded in `_build_lessons`
2. **`self.event.build_lesson_fields(row, anchor_date)`** — returns event-specific fields

For CPIEvent:
```python
def build_lesson_fields(self, event_row, anchor_date):
    return {
        "cpi_value": round(float(event_row["Value"]), 6),
        "previous_cpi_value": round(float(event_row["previous_value"]), 6),
        "cpi_change_pct": round(float(event_row["cpi_change_pct"]), 6),
        **self.build_reasoning_condition(event_row),
    }
```

`build_reasoning_condition` returns:
```python
{column: str(event_row[column]) for column in self.condition_columns}
```

CPIEvent.condition_columns = `["cpi_pressure"]` — **macro_regime is NOT in condition_columns**.

| Question | Answer |
|----------|--------|
| Regime present in event_data? | ✅ `row` has `macro_regime` |
| Regime present in lesson dict? | ❌ **NO** — `build_lesson_fields` does not include it |
| Regime consumed? | ❌ **NO** — lesson construction is the ownership boundary |
| Why lost? | `build_lesson_fields()` explicitly selects which columns to copy from `event_row` into the lesson dict. `macro_regime` is not selected. |

**Boundary:** `MacroEvent.build_lesson_fields()` at `src/knowledge/events/base.py:180`

---

### Stage 4: Lesson → LessonSummaryAggregator → KnowledgeRecord

```
LessonSummaryAggregator.build()
  → lessons.groupby(condition_columns)
  → _summarize_group() builds KnowledgeRecord dict
```

- **condition_columns** = `("cpi_pressure",)` — macro_regime NOT a condition column
- **Lesson CSV** has no `macro_regime` column (it was never written)
- **KnowledgeRecord.condition** = `{"cpi_pressure": "inflation_pressure_up"}` — no regime info

| Question | Answer |
|----------|--------|
| Regime present in KnowledgeRecord? | ❌ NO — never made it into the lesson CSV |
| Regime consumed? | ❌ NO |
| Regime in condition dict? | ❌ NO |
| Regime in metadata? | ❌ NO |

---

### Stage 5: KnowledgeRecord → GraphBuilder → GraphNode

```
GraphBuilder.build(records)
  → GraphNode(node_id, node_type, properties=dict(rec))
```

Properties are a copy of the KnowledgeRecord dict. Since KnowledgeRecord has no macro_regime, the GraphNode has no macro_regime.

| Question | Answer |
|----------|--------|
| Regime present in graph node? | ❌ NO |
| Regime consumable via graph traversal? | ❌ NO |

---

### Stage 6: GraphNode → EvidenceQuery → Evidence

```
EvidenceQuery.matching(condition=reasoning_condition)
  → _node_to_evidence(node)
  → Evidence(
        condition=props.get("condition", {}),
        metadata=dict(props),  ← all remaining properties
        ...
    )
```

Evidence.condition is `{"cpi_pressure": "inflation_pressure_up"}`. Evidence.metadata contains all node properties — but macro_regime was never in those properties.

| Question | Answer |
|----------|--------|
| Regime present in Evidence.condition? | ❌ NO |
| Regime present in Evidence.metadata? | ❌ NO (never reached graph) |
| Regime consumable via Evidence? | ❌ NO |

---

### Stage 7: Evidence → ReasoningEngine → ReasoningChain

```
ReasoningEngine.reason(evidence, context)
  → _build_evidence_review(ev):
      condition_str = format_condition(ev.condition)
      conclusion = f"{ev.event_type} with condition {condition_str} ..."
```

The reasoning engine reads `ev.condition`, `ev.confidence`, `ev.average_return_pct`, `ev.bias`, `ev.sample_count`. It does NOT reference any regime field.

Even if macro_regime were present in `ev.condition`, the reasoning engine has no regime-aware logic — it treats condition as a generic key-value bag.

| Question | Answer |
|----------|--------|
| Regime present in reasoning step? | ❌ NO |
| Regime used to change confidence? | ❌ NO — confidence from evidence.sample_count + average_return |
| Regime used to change reasoning? | ❌ NO — reasoning only uses event_type, condition, horizon, stats |
| Regime used for explainability? | ❌ NO — condition text only includes condition_columns |

---

### Stage 8: ReasoningChain → DecisionEngine → Decision

```
DecisionEngine.decide(chain, context)
  → avg_return = extract_avg_return(chain)
  → confidence = chain.overall_confidence
  → decision_type = classify(avg_return, confidence, evidence_count)
```

DecisionEngine uses weighted average return, confidence, and evidence count. No regime reference.

| Question | Answer |
|----------|--------|
| Regime present in Decision? | ❌ NO |
| Regime consumed? | ❌ NO |
| Regime used to change decision? | ❌ NO |

---

### Stage 9: Decision → Finalize → InstitutionalAssessment

```
_finalize()
  → {"decision": ..., "context": ..., "risk_decision": ..., ...}
```

InstitutionalAssessment.outputs contains finalize results. No regime in the decision or assessment output.

| Question | Answer |
|----------|--------|
| Regime present in assessment? | ❌ NO |
| Regime consumed? | ❌ NO |

---

## Where Regime IS Consumed (Outside Reasoning Pipeline)

### ForecastContextBuilder._resolve_regime()

```
_forecast_confidence / _build_context
  → ForecastContextBuilder(regime_detector=params["_regime_detector"])
  → _resolve_regime()
      → detector.regime_labels.iloc[-1]  ← latest regime label
      → returns {"label": "EXPANSION", "confidence": 0.35}
  → ForecastContext(current_regime="EXPANSION", regime_confidence=0.35)
```

The fitted detector IS passed to `ForecastContextBuilder`. The `_resolve_regime()` method reads the **latest** regime label from the entire fitted history.

### RiskGate._risk_gate()

```
_risk_gate(params, results)
  → context = results.get("build_context")
  → regime_label = context.current_regime  ← e.g. "EXPANSION"
  → regime_confidence = context.regime_confidence
  → RegimeRiskOverlay.evaluate(regime_label, regime_confidence)
  → DecisionGate.evaluate(regime_info=regime_info, ...)
```

The risk gate consumes the **current overall regime** (not per-event regime). This affects position scaling and halting decisions — not reasoning quality.

| Question | Answer |
|----------|--------|
| Regime consumed by ForecastContext? | ✅ YES — current regime label + confidence |
| Regime consumed by RiskGate? | ✅ YES — for position scaling decisions |
| Per-event regime consumed? | ❌ NO — only the latest regime is used, not the per-event historical regime |

---

## Summary: Consumption Chain

```
MacroRegimeDetector.fit()
  ↓
FeatureExtractionEngine.process() → FeatureSet     ✅ PRESENT
  ↓
LessonBuilder._build_lessons() → lesson dict       ❌ LOST (ownership boundary)
  ↓ (never reaches downstream)
LessonSummaryAggregator → KnowledgeRecord           ❌ ABSENT
GraphBuilder → GraphNode                            ❌ ABSENT
EvidenceQuery → Evidence                            ❌ ABSENT
ReasoningEngine → ReasoningChain                    ❌ ABSENT
DecisionEngine → Decision                           ❌ ABSENT
InstitutionalAssessment                             ❌ ABSENT
```

**The regime information is produced and stored in `feature_set.data` but is never forwarded into lesson dicts.** The ownership boundary is `MacroEvent.build_lesson_fields()` (`src/knowledge/events/base.py:180`): each event's implementation explicitly selects which columns from the extracted DataFrame row to include in the lesson dict, and `macro_regime` is not among the selected columns.

---

## Exact Ownership Boundary

| Location | What Happens |
|----------|--------------|
| `src/knowledge/builders/lesson_builder.py:133` | `lesson.update(self.event.build_lesson_fields(row, anchor_date))` — only event-selected fields enter the lesson |
| `src/knowledge/events/base.py:180` | `build_lesson_fields()` contract — subclasses return a dict of event-specific fields |
| `src/knowledge/events/cpi.py:77` | CPIEvent returns `{"cpi_value", "previous_cpi_value", "cpi_change_pct", **condition}` — no `macro_regime` |
| `src/knowledge/events/gdp.py:52` | Same pattern for GDPEvent |
| `src/knowledge/events/nfp.py:50` | Same pattern for NFPEvent |
| `src/knowledge/events/fomc.py:56` | Same pattern for FOMCEvent |

---

## Conclusion

| Aspect | Result |
|--------|--------|
| Regime produced? | ✅ YES — in FeatureSet after engine.process() |
| Regime consumed by reasoning pipeline? | ❌ **NO** — lost at lesson construction boundary |
| Regime consumed by forecasting pipeline? | ✅ **YES** — ForecastContextBuilder + RiskGate use current regime |
| Per-event historical regime available? | ✅ In FeatureSet only; NOT forwarded to lessons |
| Current regime available? | ✅ From ForecastContextBuilder._resolve_regime() using fitted detector |

The macro regime information follows two independent paths:

1. **Feature extraction path**: `macro_regime` column added to `feature_set.data` → consumed by FeatureExtractionEngine → **lost at lesson construction** because `build_lesson_fields()` does not include it.

2. **Forecast context path**: Fitted `MacroRegimeDetector` passed to `ForecastContextBuilder` → latest regime label used for ForecastContext and RiskGate. This path works but only provides the **current** overall regime, not per-event historical regime context.
