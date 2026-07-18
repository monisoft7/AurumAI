from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knowledge.events.base import MacroEvent
from knowledge.events.registry import EventRegistry
from knowledge.expansion.validator import EventValidator, ValidationReport


@dataclass
class LifecycleStep:
    name: str
    description: str
    files: list[str]
    duration_minutes: int | None = None


@dataclass
class ExpansionAudit:
    """Complete audit of a MacroEvent expansion."""

    spec: dict[str, Any]
    validation: ValidationReport
    pipeline_readiness: list[str]
    step_timing: dict[str, float]
    total_minutes: float

    @property
    def is_ready(self) -> bool:
        return self.validation.is_valid and all(
            "not ready" not in r for r in self.pipeline_readiness
        )

    def print_audit(self) -> None:
        print("\n" + "=" * 60)
        print(f"Expansion Audit: {self.spec.get('event_type', 'unknown')}")
        print("=" * 60)
        print(f"  Validation: {'PASS' if self.validation.is_valid else 'FAIL'}")
        print(f"  Pipeline ready: {self.is_ready}")
        print(f"  Total time: {self.total_minutes:.1f} minutes")
        print(f"  Within 1-hour budget: {'YES' if self.total_minutes <= 60 else 'NO'}")
        print()
        self.validation.print_report()
        for r in self.pipeline_readiness:
            print(f"  • {r}")
        print()


_PIPELINE_STEPS = [
    LifecycleStep(
        "1. Create data file",
        "Place the CSV file for the new event in data/economic/.",
        ["data/economic/{NAME}.csv"],
        5,
    ),
    LifecycleStep(
        "2. Define ExpansionSpec",
        "Fill in ~10 fields describing the event.",
        ["(inline configuration)"],
        3,
    ),
    LifecycleStep(
        "3. Run EventScaffolder",
        "Generate event class, feature extractor, and test template.",
        [
            "src/knowledge/events/{name}.py",
            "src/knowledge/features/extractors/{name}.py",
            "tests/test_{name}_event.py",
        ],
        2,
    ),
    LifecycleStep(
        "4. Customize the feature extractor",
        "Adjust thresholds and classification logic for the new event.",
        ["src/knowledge/features/extractors/{name}.py"],
        10,
    ),
    LifecycleStep(
        "5. Run EventValidator",
        "Verify the event class implements the full MacroEvent contract.",
        ["(framework)"],
        1,
    ),
    LifecycleStep(
        "6. Register in __init__.py",
        "Add one line: EventRegistry.register({NAME}Event)",
        ["src/knowledge/events/__init__.py"],
        2,
    ),
    LifecycleStep(
        "7. Run the scaffolded tests",
        "Execute pytest tests/test_{name}_event.py and fix any failures.",
        ["tests/test_{name}_event.py"],
        15,
    ),
    LifecycleStep(
        "8. Full pipeline smoke test",
        "Run InferencePipeline or LessonBuilder to confirm end-to-end.",
        [],
        10,
    ),
    LifecycleStep(
        "9. Cross-event registration",
        "Add the event type to EconomicEvent enum if needed.",
        ["src/knowledge/events/__init__.py"],
        2,
    ),
    LifecycleStep(
        "10. Benchmark run",
        "Run pytest tests/ -v to confirm no regressions.",
        [],
        5,
    ),
]


class ExpansionLifecycle:
    """Orchestrates and audits the full event expansion process.

    This class encapsulates the knowledge of every step required to add
    a new macro event, from data file placement through to benchmark
    validation.  It does NOT execute the steps — it measures, validates,
    and documents them.
    """

    STEPS: list[LifecycleStep] = _PIPELINE_STEPS

    def __init__(self, event_cls: type[MacroEvent] | None = None) -> None:
        self._event_cls = event_cls

    def audit(self, event_cls: type[MacroEvent] | None = None) -> ExpansionAudit:
        cls = event_cls or self._event_cls
        if cls is None:
            raise ValueError("event_cls is required")

        spec = self._extract_spec(cls)
        validation = EventValidator().validate_class(cls)
        readiness = self._check_pipeline_readiness(cls)
        timing = self._estimate_timing()
        total = sum(timing.values())

        return ExpansionAudit(
            spec=spec,
            validation=validation,
            pipeline_readiness=readiness,
            step_timing=timing,
            total_minutes=total,
        )

    def _extract_spec(self, cls: type[MacroEvent]) -> dict[str, Any]:
        instance = cls()
        meta = instance.metadata
        return {
            "event_type": getattr(cls, "event_type", ""),
            "lesson_version": getattr(cls, "lesson_version", ""),
            "condition_columns": getattr(cls, "condition_columns", []),
            "knowledge_version": getattr(cls, "knowledge_version", ""),
            "metadata": {
                "country": meta.country if meta else None,
                "currency": meta.currency if meta else None,
                "unit": meta.unit if meta else None,
                "importance": meta.importance if meta else None,
                "source": meta.source if meta else None,
            },
        }

    def _check_pipeline_readiness(
        self, cls: type[MacroEvent]
    ) -> list[str]:
        results: list[str] = []
        event_type = getattr(cls, "event_type", "?")

        if EventRegistry.is_registered(event_type):
            results.append("Registered in EventRegistry: ready")
        else:
            results.append(
                "Not registered in EventRegistry: add "
                "EventRegistry.register(...) to events/__init__.py"
            )

        event_lower = event_type.lower()

        data_path = Path(f"data/economic/{event_lower.upper()}.csv")
        if data_path.exists():
            results.append(f"Data file {data_path}: found")
        else:
            data_path_alt = Path("data/economic") / f"{event_lower.upper()}.csv"
            if data_path_alt.exists():
                results.append(f"Data file {data_path_alt}: found")
            else:
                results.append(
                    f"Data file not found at {data_path}: "
                    "create before running pipeline"
                )

        try:
            from knowledge.builders.lesson_builder import LessonBuilder  # noqa: F401
            from knowledge.lesson_summary import LessonSummaryAggregator  # noqa: F401

            results.append("LessonBuilder import: ok")
            results.append("LessonSummaryAggregator import: ok")
        except ImportError as e:
            results.append(f"Import check failed: {e}")

        try:
            from knowledge.features.engine import FeatureExtractionEngine
            FeatureExtractionEngine()
            results.append("FeatureExtractionEngine: ok")
        except ImportError as e:
            results.append(f"FeatureExtractionEngine import failed: {e}")

        return results

    def _estimate_timing(self) -> dict[str, float]:
        return {s.name.split(". ", 1)[-1]: float(s.duration_minutes or 5) for s in self.STEPS}

    def print_lifecycle(self, name: str = "{NAME}") -> None:
        print(f"\nKnowledge Expansion Lifecycle for: {name}")
        print("=" * 60)
        for step in self.STEPS:
            dur = f"~{step.duration_minutes}min" if step.duration_minutes else ""
            print(f"\n  {step.name}  ({dur})")
            print(f"    {step.description}")
            for f in step.files:
                if f:
                    print(f"      → {f}")
        print()
        total = sum(s.duration_minutes or 0 for s in self.STEPS)
        print(f"  Estimated total: ~{total} minutes ({total / 60:.1f} hours)")
        print(f"  Under 1 hour budget: {'YES' if total <= 55 else 'MARGINAL'}")
        print()

    @staticmethod
    def measure_event_complexity(event_cls: type[MacroEvent]) -> dict[str, int]:
        """Measure the total lines of code for a MacroEvent implementation.

        Returns a breakdown of source lines and test lines.
        """
        import inspect

        source_lines = 0
        test_lines = 0

        try:
            source = inspect.getsource(event_cls)
            source_lines = len(source.splitlines())
        except (OSError, TypeError):
            pass

        try:
            mod = inspect.getmodule(event_cls)
            if mod and mod.__file__:
                fpath = Path(mod.__file__)
                test_path = (
                    Path("tests")
                    / f"test_{fpath.stem}_event.py"
                )
                if test_path.exists():
                    test_lines = len(test_path.read_text().splitlines())
        except (OSError, TypeError):
            pass

        return {
            "event_class_lines": source_lines,
            "test_file_lines": test_lines,
            "total": source_lines + test_lines,
        }
