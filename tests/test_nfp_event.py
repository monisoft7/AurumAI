import tempfile
from pathlib import Path

import pandas as pd
import pytest

from knowledge.events.base import StandardEventMetadata
from knowledge.events.nfp import NFPEvent
from knowledge.events.registry import EventRegistry
from knowledge.features.extractors.nfp import (
    NFPEventFeatureExtractor,
    NFE_HIGH_THRESHOLD,
    NFE_LOW_THRESHOLD,
)
from knowledge.builders.lesson_builder import (
    LessonBuilder,
    LessonBuilderConfig,
    LegacyLessonBuilder,
)
from knowledge.lesson_summary import LessonSummaryAggregator, LessonSummaryConfig


def _write_csv(rows: list[dict]) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="")
    pd.DataFrame(rows).to_csv(tmp.name, index=False)
    return Path(tmp.name)


# --------------------------------------------------------------------------
# Feature extractor
# --------------------------------------------------------------------------


class TestNFPEventFeatureExtractor:

    def test_defines_features(self) -> None:
        extractor = NFPEventFeatureExtractor()
        defs = extractor.feature_definitions
        assert set(defs) == {"previous_value", "nfp_change", "nfp_trend"}
        assert defs["previous_value"].source_columns == ("Value",)
        assert defs["nfp_change"].source_columns == ("Value", "previous_value")
        assert defs["nfp_trend"].source_columns == ("nfp_change",)

    def test_matches_expected_output(self) -> None:
        raw = pd.DataFrame({
            "Date": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01"]),
            "Value": [152000.0, 152177.0, 152050.0],
        })
        extractor = NFPEventFeatureExtractor()
        fs = extractor.extract(raw)
        df = fs.data

        assert list(df["Date"]) == [
            pd.Timestamp("2020-02-01"),
            pd.Timestamp("2020-03-01"),
        ]
        assert list(df["Value"]) == [152177.0, 152050.0]
        assert list(df["previous_value"]) == [152000.0, 152177.0]
        assert list(df["nfp_change"]) == [177.0, -127.0]
        assert list(df["nfp_trend"]) == ["jobs_market_stable", "jobs_market_deteriorating"]

    def test_strong_job_growth_classification(self) -> None:
        raw = pd.DataFrame({
            "Date": pd.to_datetime(["2020-01-01", "2020-02-01"]),
            "Value": [150000.0, 150350.0],
        })
        extractor = NFPEventFeatureExtractor()
        df = extractor.extract(raw).data
        assert df.iloc[0]["nfp_change"] > NFE_HIGH_THRESHOLD
        assert df.iloc[0]["nfp_trend"] == "jobs_market_improving"

    def test_weak_job_growth_classification(self) -> None:
        raw = pd.DataFrame({
            "Date": pd.to_datetime(["2020-01-01", "2020-02-01"]),
            "Value": [150000.0, 150030.0],
        })
        extractor = NFPEventFeatureExtractor()
        df = extractor.extract(raw).data
        assert df.iloc[0]["nfp_change"] < NFE_LOW_THRESHOLD
        assert df.iloc[0]["nfp_trend"] == "jobs_market_deteriorating"

    def test_negative_nfp_change_is_deteriorating(self) -> None:
        raw = pd.DataFrame({
            "Date": pd.to_datetime(["2020-01-01", "2020-02-01"]),
            "Value": [150000.0, 149000.0],
        })
        extractor = NFPEventFeatureExtractor()
        df = extractor.extract(raw).data
        assert df.iloc[0]["nfp_change"] < 0
        assert df.iloc[0]["nfp_trend"] == "jobs_market_deteriorating"


# --------------------------------------------------------------------------
# NFPEvent metadata and type strings
# --------------------------------------------------------------------------


class TestNFPEventMetadata:

    def test_metadata_returns_nfp_values(self) -> None:
        event = NFPEvent()
        m = event.metadata
        assert m.country == "US"
        assert m.currency == "USD"
        assert m.unit == "thousands"
        assert m.importance == 3
        assert m.source == "Bureau of Labor Statistics"
        assert m.reference_period_type == "monthly"


class TestNFPEventTypeStrings:

    def test_event_type_is_nfp(self) -> None:
        assert NFPEvent.event_type == "NFP"

    def test_lesson_version(self) -> None:
        assert NFPEvent.lesson_version == "nfp_gold_v1"

    def test_condition_columns(self) -> None:
        assert NFPEvent.condition_columns == ["nfp_trend"]

    def test_knowledge_version(self) -> None:
        assert NFPEvent.knowledge_version == "nfp_gold_summary_v1"


# --------------------------------------------------------------------------
# NFPEvent data loading
# --------------------------------------------------------------------------


class TestNFPEventLoadRaw:

    def test_returns_date_value_only(self) -> None:
        event = NFPEvent()
        path = _write_csv([
            {"Date": "2020-01-01", "Value": 152000.0},
            {"Date": "2020-02-01", "Value": 152177.0},
        ])
        raw = event.load_raw(path)
        assert list(raw.columns) == ["Date", "Value"]
        assert raw["Date"].dtype.kind == "M"
        assert raw["Value"].dtype == "float64"

    def test_sorts_and_deduplicates(self) -> None:
        event = NFPEvent()
        path = _write_csv([
            {"Date": "2020-03-01", "Value": 152050.0},
            {"Date": "2020-01-01", "Value": 152000.0},
            {"Date": "2020-01-01", "Value": 152010.0},
            {"Date": "2020-02-01", "Value": 152177.0},
        ])
        raw = event.load_raw(path)
        assert list(raw["Date"]) == [
            pd.Timestamp("2020-01-01"),
            pd.Timestamp("2020-02-01"),
            pd.Timestamp("2020-03-01"),
        ]
        assert list(raw["Value"]) == [152010.0, 152177.0, 152050.0]

    def test_raises_on_missing_columns(self) -> None:
        event = NFPEvent()
        path = _write_csv([{"Date": "2020-01-01"}])
        with pytest.raises(ValueError, match="missing required columns"):
            event.load_raw(path)


class TestNFPEventLoadAndExtract:

    def test_includes_all_columns(self) -> None:
        event = NFPEvent()
        path = _write_csv([
            {"Date": "2020-01-01", "Value": 152000.0},
            {"Date": "2020-02-01", "Value": 152177.0},
            {"Date": "2020-03-01", "Value": 152050.0},
        ])
        df = event.load_and_extract(path)
        assert set(df.columns) == {
            "Date", "Value", "previous_value", "nfp_change", "nfp_trend",
        }
        assert len(df) == 2
        assert df.iloc[0]["nfp_trend"] == "jobs_market_stable"
        assert df.iloc[1]["nfp_trend"] == "jobs_market_deteriorating"

    def test_empty_on_single_row(self) -> None:
        event = NFPEvent()
        path = _write_csv([{"Date": "2020-01-01", "Value": 152000.0}])
        df = event.load_and_extract(path)
        assert len(df) == 0


# --------------------------------------------------------------------------
# NFPEvent lesson fields and text
# --------------------------------------------------------------------------


class TestNFPEventLesson:

    def test_build_lesson_fields(self) -> None:
        event = NFPEvent()
        path = _write_csv([
            {"Date": "2020-01-01", "Value": 152000.0},
            {"Date": "2020-02-01", "Value": 152177.0},
        ])
        df = event.load_and_extract(path)
        fields = event.build_lesson_fields(df.iloc[0], "2020-02-03")
        assert fields["nfp_value"] == 152177.0
        assert fields["previous_nfp_value"] == 152000.0
        assert fields["nfp_change"] == 177.0
        assert fields["nfp_trend"] == "jobs_market_stable"

    def test_lesson_text(self) -> None:
        event = NFPEvent()
        text = event.lesson_text({
            "event_date": "2020-02-01",
            "primary_horizon_days": 5,
            "gold_direction_5d": "UP",
            "gold_return_5d_pct": 1.5,
            "nfp_change": 177.0,
        })
        assert "NFP" in text
        assert "177.0" in text
        assert "2020-02-01" in text
        assert "1.5" in text
        assert "UP" in text


# --------------------------------------------------------------------------
# Integration: EventRegistry
# --------------------------------------------------------------------------


class TestNFPEventRegistry:

    def test_nfp_is_registered_after_import(self) -> None:
        assert EventRegistry.is_registered("NFP")

    def test_nfp_can_be_instantiated_from_registry(self) -> None:
        cls = EventRegistry.get("NFP")
        assert cls is not None
        instance = cls()
        assert isinstance(instance, NFPEvent)
        assert instance.event_type == "NFP"


# --------------------------------------------------------------------------
# Integration: LessonBuilder works with NFP (proves architecture is generic)
# --------------------------------------------------------------------------


class TestLessonBuilderWithNFPEvent:

    def test_build_lessons_with_nfp_event(self) -> None:
        base = Path(tempfile.mkdtemp())
        nfp_path = base / "PAYEMS.csv"
        gold_path = base / "gold.csv"
        output_path = base / "lessons.csv"

        nfp_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({
            "Date": ["2020-01-01", "2020-02-01", "2020-03-01"],
            "Value": [152000.0, 152177.0, 152050.0],
        }).to_csv(nfp_path, index=False)

        gold_dates = [
            "2020-01-31", "2020-02-03", "2020-02-04", "2020-02-05",
            "2020-02-06", "2020-02-07", "2020-02-10", "2020-02-11",
            "2020-02-12", "2020-02-13", "2020-02-14", "2020-02-17",
            "2020-02-18", "2020-02-19", "2020-02-20", "2020-02-21",
            "2020-02-24", "2020-02-25", "2020-02-26", "2020-02-27",
            "2020-02-28", "2020-03-02", "2020-03-03", "2020-03-04",
            "2020-03-05", "2020-03-06", "2020-03-09", "2020-03-10",
            "2020-03-11", "2020-03-12", "2020-03-13", "2020-03-16",
            "2020-03-17", "2020-03-18", "2020-03-19", "2020-03-20",
            "2020-03-23", "2020-03-24", "2020-03-25", "2020-03-26",
            "2020-03-27", "2020-03-30",
        ]
        gold_close = [float(1000 + i * 10) for i in range(len(gold_dates))]
        pd.DataFrame({"Date": gold_dates, "Close": gold_close}).to_csv(
            gold_path, index=False
        )

        config = LessonBuilderConfig(
            event_data_path=nfp_path,
            gold_path=gold_path,
            output_path=output_path,
        )
        builder = LegacyLessonBuilder(config=config, event=NFPEvent())
        lessons = builder.build()

        assert len(lessons) == 2
        assert list(lessons["lesson_id"]) == [
            "NFP_GOLD_2020-02-01",
            "NFP_GOLD_2020-03-01",
        ]
        assert list(lessons["event_type"]) == ["NFP", "NFP"]
        assert lessons.iloc[0]["nfp_trend"] == "jobs_market_stable"
        assert lessons.iloc[1]["nfp_trend"] == "jobs_market_deteriorating"
        assert "After NFP changed by" in lessons.iloc[0]["lesson_text"]
        assert lessons.iloc[0]["lesson_version"] == "nfp_gold_v1"


# --------------------------------------------------------------------------
# Integration: Full pipeline (LessonBuilder → LessonSummaryAggregator)
# --------------------------------------------------------------------------


class TestNFPPipelineEndToEnd:

    def test_knowledge_from_nfp_lessons(self) -> None:
        base = Path(tempfile.mkdtemp())
        nfp_path = base / "PAYEMS.csv"
        gold_path = base / "gold.csv"
        lessons_path = base / "lessons.csv"
        knowledge_path = base / "knowledge.json"

        pd.DataFrame({
            "Date": ["2020-01-01", "2020-02-01", "2020-03-01"],
            "Value": [152000.0, 152177.0, 152050.0],
        }).to_csv(nfp_path, index=False)

        gold_dates = [
            "2020-01-31", "2020-02-03", "2020-02-04", "2020-02-05",
            "2020-02-06", "2020-02-07", "2020-02-10", "2020-02-11",
            "2020-02-12", "2020-02-13", "2020-02-14", "2020-02-17",
            "2020-02-18", "2020-02-19", "2020-02-20", "2020-02-21",
            "2020-02-24", "2020-02-25", "2020-02-26", "2020-02-27",
            "2020-02-28", "2020-03-02", "2020-03-03", "2020-03-04",
            "2020-03-05", "2020-03-06", "2020-03-09", "2020-03-10",
            "2020-03-11", "2020-03-12", "2020-03-13", "2020-03-16",
            "2020-03-17", "2020-03-18", "2020-03-19", "2020-03-20",
            "2020-03-23", "2020-03-24", "2020-03-25", "2020-03-26",
            "2020-03-27", "2020-03-30",
        ]
        gold_close = [float(1000 + i * 10) for i in range(len(gold_dates))]
        pd.DataFrame({"Date": gold_dates, "Close": gold_close}).to_csv(
            gold_path, index=False
        )

        builder = LegacyLessonBuilder(
            LessonBuilderConfig(
                event_data_path=nfp_path,
                gold_path=gold_path,
                output_path=lessons_path,
            ),
            event=NFPEvent(),
        )
        lessons = builder.build_and_save()

        aggregator = LessonSummaryAggregator(
            LessonSummaryConfig(
                lessons_path=lessons_path,
                output_path=knowledge_path,
                condition_columns=("nfp_trend",),
                knowledge_prefix="nfp_gold_summary_v1",
                event_type="NFP",
                asset="GOLD",
            )
        )
        summary = aggregator.build()
        assert summary["record_count"] == 6
        assert summary["event_type"] == "NFP"
        assert summary["asset"] == "GOLD"
        for rec in summary["records"]:
            assert rec["event_type"] == "NFP"
            assert rec["knowledge_id"].startswith("NFP_GOLD_")
            assert rec["condition"] is not None

    def test_knowledge_from_real_nfp_data(self) -> None:
        real_path = Path("data/economic/PAYEMS.csv")
        if not real_path.exists():
            pytest.skip("PAYEMS.csv not found at data/economic/PAYEMS.csv")

        base = Path(tempfile.mkdtemp())
        gold_path = base / "gold.csv"
        lessons_path = base / "lessons.csv"
        knowledge_path = base / "knowledge.json"

        gold_data = pd.read_csv(Path("data/history/gold/gold.csv"))
        required_gold = {"Date", "Close"}
        if not required_gold.issubset(gold_data.columns):
            pytest.skip("gold.csv missing required columns")

        gold_subset = gold_data.tail(500)
        gold_subset.to_csv(gold_path, index=False)

        builder = LegacyLessonBuilder(
            LessonBuilderConfig(
                event_data_path=real_path,
                gold_path=gold_path,
                output_path=lessons_path,
            ),
            event=NFPEvent(),
        )
        lessons = builder.build_and_save()
        assert len(lessons) > 0
        assert "nfp_trend" in lessons.columns

        aggregator = LessonSummaryAggregator(
            LessonSummaryConfig(
                lessons_path=lessons_path,
                output_path=knowledge_path,
                condition_columns=("nfp_trend",),
                knowledge_prefix="nfp_gold_summary_v1",
                event_type="NFP",
                asset="GOLD",
            )
        )
        summary = aggregator.build_and_save()
        assert summary["record_count"] >= 1
        assert summary["event_type"] == "NFP"
