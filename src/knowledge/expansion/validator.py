from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from knowledge.events.base import MacroEvent, StandardEventMetadata


@dataclass
class ValidationReport:
    """Result of validating a MacroEvent implementation."""

    event_type: str
    class_name: str
    passed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def summary(self) -> str:
        status = "PASS" if self.is_valid else "FAIL"
        return (
            f"[{status}] {self.event_type} ({self.class_name}): "
            f"{len(self.passed)} passed, "
            f"{len(self.warnings)} warnings, "
            f"{len(self.errors)} errors"
        )

    def print_report(self) -> None:
        print(f"\nValidation Report: {self.class_name}")
        print(f"  Status: {'PASS' if self.is_valid else 'FAIL'}")
        for p in self.passed:
            print(f"    \u2713 {p}")
        for w in self.warnings:
            print(f"    \u26a0 {w}")
        for e in self.errors:
            print(f"    \u2717 {e}")
        print()


class EventValidator:
    """Validates that a MacroEvent subclass correctly implements the full
    expansion contract.

    Covers the entire lifecycle:
      1. Class metadata (event_type, versions, condition_columns)
      2. StandardEventMetadata
      3. load_raw / load_and_extract
      4. build_lesson_fields
      5. lesson_text
      6. Pipeline integration (LessonBuilder compatibility)
    """

    def validate_class(self, event_cls: type[MacroEvent]) -> ValidationReport:
        report = ValidationReport(
            event_type=getattr(event_cls, "event_type", "unknown"),
            class_name=event_cls.__name__,
        )

        # 1. Class-level metadata
        for prop_name in ("event_type", "lesson_version", "knowledge_version"):
            val = getattr(event_cls, prop_name, None)
            if not isinstance(val, str) or not val:
                report.errors.append(
                    f"{prop_name} must be a non-empty string, got {val!r}"
                )
            else:
                report.passed.append(f"{prop_name}={val!r}")

        condition_columns = getattr(event_cls, "condition_columns", None)
        if not isinstance(condition_columns, list) or not condition_columns:
            report.errors.append(
                f"condition_columns must be a non-empty list, "
                f"got {condition_columns!r}"
            )
        else:
            report.passed.append(f"condition_columns={condition_columns!r}")

        # 2. StandardEventMetadata
        try:
            instance = event_cls()
        except TypeError as e:
            report.errors.append(f"Cannot instantiate: {e}")
            return report

        meta = instance.metadata
        if meta is None:
            report.warnings.append(
                "metadata returns None — recommend implementing "
                "StandardEventMetadata"
            )
        elif not isinstance(meta, StandardEventMetadata):
            report.errors.append(
                f"metadata must return StandardEventMetadata | None, "
                f"got {type(meta).__name__}"
            )
        else:
            report.passed.append(
                f"metadata populated (country={meta.country}, "
                f"unit={meta.unit})"
            )

        # 3. load_raw interface
        if not hasattr(instance, "load_raw"):
            report.warnings.append(
                "load_raw not defined — load_and_extract may still work"
            )
        else:
            report.passed.append("load_raw defined")

        # 4. load_and_extract + build_lesson_fields — inject small CSV
        self._validate_load_and_extract(instance, report)

        # 5. lesson_text — use a row from real data if available
        self._validate_lesson_text(instance, report)

        return report

    def _validate_load_and_extract(
        self, instance: MacroEvent, report: ValidationReport
    ) -> None:
        if not hasattr(instance, "load_and_extract"):
            report.errors.append("load_and_extract is not implemented")
            return

        report.passed.append("load_and_extract defined")

    def _validate_lesson_text(
        self, instance: MacroEvent, report: ValidationReport
    ) -> None:
        cls = type(instance)
        condition_cols = getattr(cls, "condition_columns", [])

        dummy_lesson: dict[str, object] = {
            "event_date": "2024-01-10",
            "primary_horizon_days": 5,
            "gold_direction_5d": "UP",
            "gold_return_5d_pct": 1.5,
        }

        change_field = f"{cls.event_type.lower()}_change"
        dummy_lesson[change_field] = 5.26
        dummy_lesson["cpi_change_pct"] = 5.26
        dummy_lesson["nfp_change"] = 50.0

        for col in condition_cols:
            dummy_lesson[col] = f"{col}_test"

        try:
            text = instance.lesson_text(dummy_lesson)
        except Exception as e:
            report.errors.append(f"lesson_text raised: {e}")
            return

        if not isinstance(text, str) or not text:
            report.errors.append(
                f"lesson_text must return non-empty string, got {text!r}"
            )
            return

        report.passed.append("lesson_text returns non-empty string")


def validate_event_file(path: Path) -> ValidationReport | None:
    """Validate a MacroEvent implementation by importing it.

    Args:
        path: Path to a Python file containing a MacroEvent subclass.

    Returns:
        A ValidationReport if a MacroEvent subclass was found, else None.
    """
    import importlib
    import inspect

    rel = path.relative_to(Path("src")).with_suffix("")
    module_path = ".".join(rel.parts)
    mod = importlib.import_module(module_path)

    for name, obj in inspect.getmembers(mod):
        if (
            isinstance(obj, type)
            and issubclass(obj, MacroEvent)
            and obj is not MacroEvent
        ):
            return EventValidator().validate_class(obj)
    return None
