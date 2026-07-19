from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from knowledge.events.base import MacroEvent


@dataclass(frozen=True)
class ExpansionSpec:
    """Minimal specification from which a full MacroEvent implementation
    can be scaffolded.

    A developer fills these ~10 fields and calls ``EventScaffolder`` to
    generate the event class, feature extractor, and test template.
    """

    event_type: str
    """Example: 'PPI', 'PMI', 'GDP'."""

    country: str = "US"
    currency: str = "USD"
    unit: str = "index"
    importance: int = 2
    source: str = ""
    reference_period_type: str = "monthly"

    lesson_version: str = ""
    condition_columns: list[str] | None = None
    knowledge_version: str = ""

    def __post_init__(self) -> None:
        if not self.lesson_version:
            object.__setattr__(
                self,
                "lesson_version",
                f"{self.event_type.lower()}_gold_v1",
            )
        if self.condition_columns is None:
            object.__setattr__(self, "condition_columns", [f"{self.event_type.lower()}_trend"])
        if not self.knowledge_version:
            object.__setattr__(
                self,
                "knowledge_version",
                f"{self.event_type.lower()}_gold_summary_v1",
            )

    @property
    def event_type_lower(self) -> str:
        return self.event_type.lower()

    @property
    def extractor_class_name(self) -> str:
        return self._class_name_base() + "FeatureExtractor"

    @property
    def event_class_name(self) -> str:
        return self._class_name_base() + "Event"

    def _class_name_base(self) -> str:
        if self.event_type.isupper() and "_" not in self.event_type:
            return self.event_type
        return "".join(p.capitalize() for p in self.event_type.split("_"))


_EVENT_CLASS_TEMPLATE = '''\
from pathlib import Path

import pandas as pd

from knowledge.events.base import MacroEvent, StandardEventMetadata
from knowledge.features.engine import FeatureExtractionEngine
from knowledge.features.extractors.{event_type_lower} import {extractor_class_name}


class {event_class_name}(MacroEvent):
    """Lesson-building logic for {event_type} releases."""

    event_type = "{event_type}"
    lesson_version = "{lesson_version}"
    condition_columns = {condition_columns!r}
    knowledge_version = "{knowledge_version}"

    @property
    def metadata(self) -> StandardEventMetadata:
        return StandardEventMetadata(
            country={country!r},
            currency={currency!r},
            unit={unit!r},
            importance={importance},
            source={source!r},
            reference_period_type={reference_period_type!r},
        )

    def __init__(self) -> None:
        self._extraction_engine = FeatureExtractionEngine()
        self._extractor = {extractor_class_name}()

    def load_raw(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        required = {{"Date", "Value"}}
        missing = required.difference(df.columns)
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(f"{{path}} is missing required columns: {{missing_text}}")

        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="raise")
        df["Value"] = pd.to_numeric(df["Value"], errors="raise")
        df = df.sort_values("Date").drop_duplicates("Date", keep="last")
        return df.reset_index(drop=True)

    def load_and_extract(self, path: Path) -> pd.DataFrame:
        raw = self.load_raw(path)
        feature_set = self._extraction_engine.process(raw, self._extractor)
        return feature_set.data

    def build_lesson_fields(
        self, event_row: pd.Series, anchor_date: str
    ) -> dict[str, object]:
        condition_col = self.condition_columns[0]
        return {{
            "{event_type_lower}_value": round(float(event_row["Value"]), 6),
            "previous_{event_type_lower}_value": round(
                float(event_row["previous_value"]), 6
            ),
            "{event_type_lower}_change": round(
                float(event_row["{event_type_lower}_change"]), 6
            ),
            condition_col: str(event_row[condition_col]),
        }}

    def lesson_text(self, lesson: dict[str, object]) -> str:
        horizon = int(lesson["primary_horizon_days"])
        direction = lesson[f"gold_direction_{{horizon}}d"]
        move = lesson[f"gold_return_{{horizon}}d_pct"]
        change_key = "{event_type_lower}_change"
        change_val = lesson[change_key]
        return (
            f"After {{self.event_type}} changed by {{change_val}}{{unit_suffix}} "
            f"on {{lesson['event_date']}}, "
            f"gold moved {{move}}% over {{horizon}} trading days "
            f"({{direction}})."
        )
'''


_EXTRACTOR_TEMPLATE = '''\
import pandas as pd

from knowledge.features.feature import Feature, FeatureSet
from knowledge.features.extractor import FeatureExtractor

{class_name_comment}
_{event_type_upper}_HIGH_THRESHOLD = 0.5
_{event_type_upper}_LOW_THRESHOLD = -0.5


class {extractor_class_name}(FeatureExtractor):
    @property
    def feature_definitions(self) -> dict[str, Feature]:
        return {{
            "previous_value": Feature(
                name="previous_value",
                dtype="float64",
                description="{event_type} value from the previous release",
                source_columns=("Value",),
            ),
            "{event_type_lower}_change": Feature(
                name="{event_type_lower}_change",
                dtype="float64",
                description="Period-over-period {event_type} change",
                source_columns=("Value", "previous_value"),
            ),
            "{condition_col}": Feature(
                name="{condition_col}",
                dtype="object",
                description="Condition classification for {event_type}",
                source_columns=("{event_type_lower}_change",),
            ),
        }}

    def extract(self, raw: pd.DataFrame) -> FeatureSet:
        df = raw.copy()
        df["previous_value"] = df["Value"].shift(1)
        df["{event_type_lower}_change"] = (
            (df["Value"] - df["previous_value"]) / df["previous_value"]
        ) * 100.0
        df["{condition_col}"] = df["{event_type_lower}_change"].apply(
            self._classify_condition
        )
        df = df.dropna(subset=["previous_value", "{event_type_lower}_change"])
        return FeatureSet(data=df, features=self.feature_definitions)

    @staticmethod
    def _classify_condition(change: float) -> str:
        if change > _{event_type_upper}_HIGH_THRESHOLD:
            return "{event_type_lower}_up"
        if change < _{event_type_upper}_LOW_THRESHOLD:
            return "{event_type_lower}_down"
        return "{event_type_lower}_flat"
'''


_TEST_TEMPLATE = '''\
"""Tests for the {event_type} event implementation.

Generated by ``EventScaffolder``.
"""

from pathlib import Path
import pandas as pd
import pytest

from knowledge.events.{event_type_lower} import {event_class_name}
from knowledge.features.extractors.{event_type_lower} import (
    {extractor_class_name},
)
from knowledge.builders.lesson_builder import LessonBuilder, LessonBuilderConfig
from knowledge.lesson_summary import LessonSummaryAggregator, LessonSummaryConfig
from knowledge.events.registry import EventRegistry


class Test{event_class_name}FeatureExtractor:
    """Feature extraction tests."""

    def test_defines_features(self) -> None:
        ext = {extractor_class_name}()
        assert "previous_value" in ext.feature_definitions
        assert "{event_type_lower}_change" in ext.feature_definitions
        assert "{condition_col}" in ext.feature_definitions

    def test_classifies_condition(self) -> None:
        assert {extractor_class_name}._classify_condition(1.0) \
            == "{event_type_lower}_up"
        assert {extractor_class_name}._classify_condition(-1.0) \
            == "{event_type_lower}_down"
        assert {extractor_class_name}._classify_condition(0.0) \
            == "{event_type_lower}_flat"

    def test_extract_adds_columns(self, tmp_path: Path) -> None:
        csv = tmp_path / "test.csv"
        csv.write_text("Date,Value\\n2024-01-10,100\\n2024-02-10,105\\n")
        ext = {extractor_class_name}()
        raw = pd.read_csv(csv)
        result = ext.extract(raw)
        assert "{event_type_lower}_change" in result.data.columns
        assert "{condition_col}" in result.data.columns


class Test{event_class_name}TypeStrings:
    """Event metadata string constants."""

    def test_event_type(self) -> None:
        assert {event_class_name}.event_type == "{event_type}"

    def test_lesson_version(self) -> None:
        assert {event_class_name}.lesson_version == "{lesson_version}"

    def test_condition_columns(self) -> None:
        assert {event_class_name}.condition_columns == {condition_columns!r}

    def test_knowledge_version(self) -> None:
        assert {event_class_name}.knowledge_version == "{knowledge_version}"


class Test{event_class_name}Metadata:
    """StandardEventMetadata tests."""

    def test_metadata_returns_expected_values(self) -> None:
        ev = {event_class_name}()
        m = ev.metadata
        assert m is not None
        assert m.country == "{country}"
        assert m.currency == "{currency}"
        assert m.unit == "{unit}"
        assert m.importance == {importance}


class Test{event_class_name}LoadRaw:
    """Raw data loading tests."""

    def test_returns_date_value_only(self, tmp_path: Path) -> None:
        csv = tmp_path / "test.csv"
        csv.write_text("Date,Value\\n2024-01-10,100\\n")
        ev = {event_class_name}()
        df = ev.load_raw(csv)
        assert list(df.columns) == ["Date", "Value"]

    def test_sorts_and_deduplicates(self, tmp_path: Path) -> None:
        csv = tmp_path / "test.csv"
        csv.write_text(
            "Date,Value\\n2024-01-10,100\\n2024-01-10,101\\n"
            "2024-01-05,99\\n"
        )
        ev = {event_class_name}()
        df = ev.load_raw(csv)
        assert len(df) == 2
        assert df["Date"].iloc[0].date().isoformat() == "2024-01-05"

    def test_raises_on_missing_columns(self, tmp_path: Path) -> None:
        csv = tmp_path / "bad.csv"
        csv.write_text("Col1,Col2\\n1,2\\n")
        ev = {event_class_name}()
        with pytest.raises(ValueError, match="missing required columns"):
            ev.load_raw(csv)


class Test{event_class_name}LoadAndExtract:
    """Full load + extract pipeline tests."""

    def test_includes_all_columns(self, tmp_path: Path) -> None:
        csv = tmp_path / "test.csv"
        csv.write_text("Date,Value\\n2024-01-10,100\\n2024-02-10,105\\n")
        ev = {event_class_name}()
        df = ev.load_and_extract(csv)
        assert "Date" in df.columns
        assert "{event_type_lower}_change" in df.columns
        assert "{condition_col}" in df.columns

    def test_empty_on_single_row(self, tmp_path: Path) -> None:
        csv = tmp_path / "single.csv"
        csv.write_text("Date,Value\\n2024-01-10,100\\n")
        ev = {event_class_name}()
        df = ev.load_and_extract(csv)
        assert len(df) == 0


class Test{event_class_name}Lesson:
    """Lesson field and text tests."""

    def test_build_lesson_fields(self) -> None:
        ev = {event_class_name}()
        row = pd.Series({{
            "Date": pd.Timestamp("2024-01-10"),
            "Value": 100.0,
            "previous_value": 95.0,
            "{event_type_lower}_change": 5.26,
            "{condition_col}": "{event_type_lower}_up",
        }})
        fields = ev.build_lesson_fields(row, "2024-01-10")
        assert "{event_type_lower}_value" in fields
        assert "{event_type_lower}_change" in fields
        assert "{condition_col}" in fields

    def test_lesson_text(self) -> None:
        ev = {event_class_name}()
        lesson = {{
            "event_date": "2024-01-10",
            "primary_horizon_days": 5,
            "gold_direction_5d": "UP",
            "gold_return_5d_pct": 1.5,
            "{event_type_lower}_change": 5.26,
            "{condition_col}": "{event_type_lower}_up",
        }}
        text = ev.lesson_text(lesson)
        assert "{event_type}" in text


class Test{event_class_name}Registry:
    """Registry integration tests."""

    def test_is_registered_after_import(self) -> None:
        assert EventRegistry.is_registered("{event_type}")

    def test_can_be_instantiated_from_registry(self) -> None:
        cls = EventRegistry.get("{event_type}")
        assert cls is not None
        instance = cls()
        assert instance.event_type == "{event_type}"


class Test{event_class_name}PipelineEndToEnd:
    """End-to-end: LessonBuilder -> LessonSummaryAggregator."""

    def test_knowledge_from_{event_type_lower}_lessons(
        self, tmp_path: Path
    ) -> None:
        ev = {event_class_name}()
        data_csv = tmp_path / "{event_type_lower}.csv"
        data_csv.write_text(
            "Date,Value\\n2024-01-10,100\\n2024-02-10,105\\n"
            "2024-03-10,103\\n"
        )
        gold_csv = tmp_path / "gold.csv"
        gold_csv.write_text(
            "Date,Close\\n"
            "2024-01-10,2000\\n2024-01-11,2010\\n2024-01-12,2020\\n"
            "2024-01-15,2030\\n2024-01-16,2025\\n2024-01-17,2015\\n"
            "2024-01-18,2020\\n2024-01-19,2025\\n2024-01-22,2030\\n"
            "2024-02-10,2100\\n2024-02-11,2110\\n2024-02-12,2120\\n"
            "2024-02-13,2130\\n2024-02-14,2125\\n2024-02-15,2115\\n"
            "2024-02-16,2120\\n2024-02-17,2125\\n2024-02-20,2130\\n"
            "2024-03-10,2200\\n2024-03-11,2210\\n2024-03-12,2220\\n"
            "2024-03-13,2230\\n2024-03-14,2225\\n"
        )
        config = LessonBuilderConfig(
            event_data_path=data_csv,
            gold_path=gold_csv,
            output_path=tmp_path / "lessons.csv",
            horizons=(1, 5),
        )
        builder = LessonBuilder(config=config, event=ev)
        lessons = builder.build_and_save()
        assert len(lessons) > 0
        assert "event_type" in lessons.columns
        assert "{condition_col}" in lessons.columns
        assert lessons["event_type"].iloc[0] == "{event_type}"
'''


class EventScaffolder:
    """Generates a complete MacroEvent implementation from a minimal spec.

    Usage::

        from knowledge.expansion import EventScaffolder, ExpansionSpec

        spec = ExpansionSpec(event_type="PPI", unit="index", source="BLS")
        scaffolder = EventScaffolder(spec)
        scaffolder.scaffold_event_class(overwrite=False)
        scaffolder.scaffold_extractor(overwrite=False)
        scaffolder.scaffold_tests(overwrite=False)
    """

    PYPI_CLASSIFIERS: ClassVar[str] = (
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
    )

    def __init__(self, spec: ExpansionSpec, src_root: Path | None = None) -> None:
        self.spec = spec
        self.src_root = src_root or Path("src")

    @property
    def _events_dir(self) -> Path:
        return self.src_root / "knowledge" / "events"

    @property
    def _extractors_dir(self) -> Path:
        return self.src_root / "knowledge" / "features" / "extractors"

    @property
    def _tests_dir(self) -> Path:
        root = self.src_root.parent if self.src_root.name == "src" else self.src_root
        return root / "tests"

    def scaffold_event_class(self, overwrite: bool = False) -> Path:
        path = self._events_dir / f"{self.spec.event_type_lower}.py"
        if path.exists() and not overwrite:
            return path
        content = _EVENT_CLASS_TEMPLATE.format(
            event_type=self.spec.event_type,
            event_type_lower=self.spec.event_type_lower,
            event_class_name=self.spec.event_class_name,
            extractor_class_name=self.spec.extractor_class_name,
            lesson_version=self.spec.lesson_version,
            condition_columns=self.spec.condition_columns,
            knowledge_version=self.spec.knowledge_version,
            country=self.spec.country,
            currency=self.spec.currency,
            unit=self.spec.unit,
            importance=self.spec.importance,
            source=self.spec.source,
            reference_period_type=self.spec.reference_period_type,
            unit_suffix="%" if self.spec.unit == "percent" else "",
        )
        path.write_text(content)
        return path

    def scaffold_extractor(self, overwrite: bool = False) -> Path:
        path = self._extractors_dir / f"{self.spec.event_type_lower}.py"
        if path.exists() and not overwrite:
            return path
        content = _EXTRACTOR_TEMPLATE.format(
            event_type=self.spec.event_type,
            event_type_lower=self.spec.event_type_lower,
            event_type_upper=self.spec.event_type.upper(),
            extractor_class_name=self.spec.extractor_class_name,
            class_name_comment=f"# Feature extractor for {self.spec.event_type}.",
            condition_col=self.spec.condition_columns[0],
        )
        path.write_text(content)
        return path

    def scaffold_tests(self, overwrite: bool = False) -> Path:
        path = self._tests_dir / f"test_{self.spec.event_type_lower}_event.py"
        if path.exists() and not overwrite:
            return path
        content = _TEST_TEMPLATE.format(
            event_type=self.spec.event_type,
            event_type_lower=self.spec.event_type_lower,
            event_class_name=self.spec.event_class_name,
            extractor_class_name=self.spec.extractor_class_name,
            lesson_version=self.spec.lesson_version,
            condition_columns=self.spec.condition_columns,
            condition_col=self.spec.condition_columns[0],
            knowledge_version=self.spec.knowledge_version,
            country=self.spec.country,
            currency=self.spec.currency,
            unit=self.spec.unit,
            importance=self.spec.importance,
        )
        path.write_text(content)
        return path

    def scaffold_all(self, overwrite: bool = False) -> dict[str, Path]:
        return {
            "event_class": self.scaffold_event_class(overwrite),
            "extractor": self.scaffold_extractor(overwrite),
            "tests": self.scaffold_tests(overwrite),
        }
