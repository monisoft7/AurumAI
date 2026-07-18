# Event Onboarding Guide

Add a new macroeconomic event type to AurumAI in under one hour.

---

## Prerequisites

- Python 3.14+ installed
- Working knowledge of `pandas` and `pathlib`
- AurumAI repository cloned and `pip install -e .` completed
- Gold price history in `data/history/gold/gold.csv`
- Event data CSV with `Date` and `Value` columns in `data/economic/`

---

## Step 1: Prepare the Data CSV (5 min)

Place the CSV file in `data/economic/{EVENT}.csv`.

The CSV must have at least two columns:
- `Date` — ISO format date string (e.g., `2024-01-10`)
- `Value` — numeric value of the economic indicator

Example (`data/economic/PPI.csv`):
```
Date,Value
2024-01-10,120.5
2024-02-10,121.3
2024-03-10,121.8
```

The `LessonBuilder` will align each event date to the next gold trading session.

---

## Step 2: Define the ExpansionSpec (3 min)

Create a Python script or use the Python REPL:

```python
from knowledge.expansion import ExpansionSpec

spec = ExpansionSpec(
    event_type="PPI",          # Your event type (e.g., PPI, PMI, GDP)
    country="US",
    currency="USD",
    unit="index",
    importance=2,              # 1=low, 2=medium, 3=high
    source="Bureau of Labor Statistics",
    reference_period_type="monthly",
    # The following are auto-generated but can be overridden:
    # lesson_version="ppi_gold_v1",
    # condition_columns=["ppi_trend"],
    # knowledge_version="ppi_gold_summary_v1",
)
```

---

## Step 3: Scaffold the Event (2 min)

```python
from knowledge.expansion import EventScaffolder

scaffolder = EventScaffolder(spec)
files = scaffolder.scaffold_all(overwrite=False)

for name, path in files.items():
    print(f"  Created {name}: {path}")
```

Output:
```
  Created event_class: src\knowledge\events\ppi.py
  Created extractor: src\knowledge\features\extractors\ppi.py
  Created tests: tests\test_ppi_event.py
```

---

## Step 4: Customize the Feature Extractor (10 min)

Edit `src/knowledge/features/extractors/ppi.py`:

1. **Adjust thresholds** — change `PPI_HIGH_THRESHOLD` and `PPI_LOW_THRESHOLD`
2. **Refine classification** — update `_classify_condition()` if the event needs different labels
3. **Add custom features** — if the event needs additional computed columns, add them to `extract()` and `feature_definitions`

Example PPI customization:

```python
# PPI has different deflation thresholds than CPI
_PPI_HIGH_THRESHOLD = 0.3   # PPI is more volatile than CPI
_PPI_LOW_THRESHOLD = -0.3

class PPIFeatureExtractor(FeatureExtractor):
    @staticmethod
    def _classify_condition(change: float) -> str:
        if change > _PPI_HIGH_THRESHOLD:
            return "ppi_producer_prices_up"
        if change < _PPI_LOW_THRESHOLD:
            return "ppi_producer_prices_down"
        return "ppi_producer_prices_stable"
```

---

## Step 5: Customize the Event Class (5 min)

Edit `src/knowledge/events/ppi.py`:

1. **Metadata** — verify `StandardEventMetadata` values
2. **`lesson_text()`** — rewrite to describe the causal story for this event

Example PPI lesson text:

```python
def lesson_text(self, lesson: dict[str, object]) -> str:
    horizon = int(lesson["primary_horizon_days"])
    direction = lesson[f"gold_direction_{horizon}d"]
    move = lesson[f"gold_return_{horizon}d_pct"]
    ppi_change = lesson["ppi_change"]
    return (
        f"After PPI changed by {ppi_change}% on {lesson['event_date']}, "
        f"gold moved {move}% over {horizon} trading days "
        f"({direction})."
    )
```

---

## Step 6: Run the Validator (1 min)

```python
from knowledge.expansion import EventValidator
from knowledge.events.ppi import PPIEvent

report = EventValidator().validate_class(PPIEvent)
report.print_report()
```

Fix any errors before proceeding.

---

## Step 7: Register the Event (2 min)

Open `src/knowledge/events/__init__.py` and add two lines:

```python
from knowledge.events.ppi import PPIEvent
# ... existing imports ...

EventRegistry.register(CPIEvent)
EventRegistry.register(NFPEvent)
EventRegistry.register(PPIEvent)   # <-- add this line
```

Also add to the `EconomicEvent` enum if desired:

```python
class EconomicEvent(Enum):
    # ... existing ...
    PPI = "Producer Price Index"
```

---

## Step 8: Run the Tests (15 min)

```bash
python -m pytest tests/test_ppi_event.py -v --tb=short
```

Expected: ~30 tests pass.

If tests fail:
- **Extractor tests** — verify feature definitions and `_classify_condition` logic
- **Load raw tests** — verify CSV column validation
- **Pipeline tests** — verify data file path and gold data availability

---

## Step 9: Pipeline Smoke Test (10 min)

```python
from pathlib import Path
from knowledge.events.ppi import PPIEvent
from knowledge.builders.lesson_builder import LessonBuilder, LessonBuilderConfig

ev = PPIEvent()
config = LessonBuilderConfig(
    event_data_path=Path("data/economic/PPI.csv"),
    gold_path=Path("data/history/gold/gold.csv"),
    output_path=Path("data/lessons/ppi_gold_lessons.csv"),
)
builder = LessonBuilder(config=config, event=ev)
lessons = builder.build_and_save()

print(f"Built {len(lessons)} PPI lessons")
print(lessons[["event_type", "event_date", "lesson_text"]].head())
```

---

## Step 10: Verify No Regressions (5 min)

```bash
python -m pytest tests/ -v --tb=short
```

Confirm all existing tests still pass. The benchmark suite will validate that the system's reasoning, retrieval, decision, and stability metrics remain above thresholds.

---

## What Questions to Ask

When defining a new event, ask:

1. **What is the causal mechanism?** How does this event affect gold (or the target asset)?
2. **What conditions matter?** Should lessons be grouped by trend (up/down/flat), magnitude (high/low), or something else?
3. **What are reasonable thresholds?** Look at the event's historical distribution to set classification boundaries.
4. **What is the lag?** Does the market react immediately, or is there a delayed effect?
5. **Is the data clean?** Are there missing values, outliers, or structural breaks in the CSV?

---

## Common Customizations

| Scenario | Change |
|----------|--------|
| Different condition columns | Set `condition_columns=["col1", "col2"]` in ExpansionSpec |
| Multiple classification dimensions | Add more features in the extractor's `extract()` method |
| Non-percent change | Override `_classify_condition` with raw difference logic |
| Different data format | Override `load_raw()` in the event class |
| Multiple source files | Override `load_and_extract()` to merge datasets |
