from pathlib import Path

import pandas as pd
import pytest

from knowledge.events.base import MacroEvent, StandardEventMetadata
from knowledge.events.cpi import CPIEvent


class TestStandardEventMetadata:

    def test_is_frozen(self) -> None:
        m = StandardEventMetadata(country="US", importance=3)
        with pytest.raises((AttributeError, TypeError)):
            m.country = "CA"

    def test_defaults_are_none(self) -> None:
        m = StandardEventMetadata()
        assert m.country is None
        assert m.currency is None
        assert m.unit is None
        assert m.importance is None
        assert m.source is None
        assert m.reference_period_type is None

    def test_positional_and_keyword(self) -> None:
        m = StandardEventMetadata("US", "USD", "percent", 3, "BLS", "monthly")
        assert m.country == "US"
        assert m.currency == "USD"
        assert m.unit == "percent"
        assert m.importance == 3
        assert m.source == "BLS"
        assert m.reference_period_type == "monthly"


class TestMacroEventMetadata:

    def test_base_metadata_returns_none(self) -> None:
        class MinimalEvent(MacroEvent):
            event_type = "TEST"
            lesson_version = "test_v1"
            condition_columns = ["condition"]
            knowledge_version = "test_summary_v1"

            def load_and_extract(self, path: Path) -> pd.DataFrame:
                return pd.DataFrame()

            def build_lesson_fields(self, event_row, anchor_date):
                return {}

            def lesson_text(self, lesson):
                return ""

        event = MinimalEvent()
        assert event.metadata is None

    def test_cpi_metadata_returns_cpi_values(self) -> None:
        event = CPIEvent()
        m = event.metadata
        assert m is not None
        assert m.country == "US"
        assert m.currency == "USD"
        assert m.unit == "percent"
        assert m.importance == 3
        assert m.source == "Bureau of Labor Statistics"
        assert m.reference_period_type == "monthly"

    def test_new_event_with_full_metadata(self) -> None:
        class MockEvent(MacroEvent):
            event_type = "MOCK"
            lesson_version = "mock_v1"
            condition_columns = ["mock_condition"]
            knowledge_version = "mock_summary_v1"

            @property
            def metadata(self) -> StandardEventMetadata:
                return StandardEventMetadata(
                    country="UK",
                    currency="GBP",
                    unit="index",
                    importance=2,
                    source="Office for National Statistics",
                    reference_period_type="quarterly",
                )

            def load_and_extract(self, path: Path) -> pd.DataFrame:
                return pd.DataFrame()

            def build_lesson_fields(self, event_row, anchor_date):
                return {}

            def lesson_text(self, lesson):
                return ""

        event = MockEvent()
        m = event.metadata
        assert m.country == "UK"
        assert m.currency == "GBP"
        assert m.unit == "index"
        assert m.importance == 2
        assert m.source == "Office for National Statistics"
        assert m.reference_period_type == "quarterly"

    def test_metadata_is_optional_abstract_not_required(self) -> None:
        class LegacyEvent(MacroEvent):
            event_type = "LEGACY"
            lesson_version = "legacy_v1"
            condition_columns = ["x"]
            knowledge_version = "legacy_summary_v1"

            def load_and_extract(self, path: Path) -> pd.DataFrame:
                return pd.DataFrame()

            def build_lesson_fields(self, event_row, anchor_date):
                return {}

            def lesson_text(self, lesson):
                return ""

        event = LegacyEvent()
        assert event.metadata is None


class TestCpiBackwardCompatibility:

    def test_cpi_event_type_unchanged(self) -> None:
        event = CPIEvent()
        assert event.event_type == "CPI"

    def test_cpi_lesson_version_unchanged(self) -> None:
        event = CPIEvent()
        assert event.lesson_version == "cpi_gold_v1"

    def test_cpi_condition_columns_unchanged(self) -> None:
        event = CPIEvent()
        assert event.condition_columns == ["cpi_pressure"]

    def test_cpi_knowledge_version_unchanged(self) -> None:
        event = CPIEvent()
        assert event.knowledge_version == "cpi_gold_summary_v1"

    def test_cpi_metadata_does_not_affect_pipeline_contract(self) -> None:
        event = CPIEvent()
        assert hasattr(event, "metadata")
        assert event.metadata is not None
        assert "country" in dir(event.metadata)


class TestEventModuleExports:

    def test_standard_event_metadata_importable(self) -> None:
        from knowledge.events import StandardEventMetadata
        assert StandardEventMetadata is not None

    def test_macro_event_importable(self) -> None:
        from knowledge.events import MacroEvent
        assert MacroEvent is not None

    def test_economic_event_importable(self) -> None:
        from knowledge.events import EconomicEvent
        assert EconomicEvent is not None
        assert EconomicEvent.CPI.value == "Consumer Price Index"
