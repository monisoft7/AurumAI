from pathlib import Path

import pandas as pd

from knowledge.features.feature import Feature, FeatureSet
from knowledge.features.extractor import FeatureExtractor
from knowledge.features.engine import FeatureExtractionEngine
from knowledge.features.extractors.cpi import CPIFeatureExtractor
from knowledge.events.cpi import CPIEvent


def test_featureset_validate_passes_with_all_columns() -> None:
    data = pd.DataFrame({"a": [1], "b": [2]})
    features = {
        "a": Feature(name="a", dtype="int64", description="", source_columns=()),
    }
    fs = FeatureSet(data=data, features=features)
    fs.validate()


def test_featureset_validate_raises_on_missing_column() -> None:
    data = pd.DataFrame({"a": [1]})
    features = {
        "b": Feature(name="b", dtype="int64", description="", source_columns=()),
    }
    fs = FeatureSet(data=data, features=features)
    try:
        fs.validate()
    except ValueError as exc:
        assert "b" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing column")


def test_featureset_get_feature_known() -> None:
    data = pd.DataFrame({"a": [1]})
    f = Feature(name="a", dtype="int64", description="desc", source_columns=("x",))
    fs = FeatureSet(data=data, features={"a": f})
    assert fs.get_feature("a") is f


def test_featureset_get_feature_unknown_raises() -> None:
    data = pd.DataFrame({"a": [1]})
    fs = FeatureSet(data=data, features={})
    try:
        fs.get_feature("a")
    except ValueError as exc:
        assert "Unknown feature" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown feature")


def test_featureset_feature_names() -> None:
    data = pd.DataFrame({"a": [1], "b": [2]})
    features = {
        "a": Feature(name="a", dtype="int64", description="", source_columns=()),
        "b": Feature(name="b", dtype="float64", description="", source_columns=()),
    }
    fs = FeatureSet(data=data, features=features)
    assert sorted(fs.feature_names) == ["a", "b"]


def test_cpi_feature_extractor_defines_features() -> None:
    extractor = CPIFeatureExtractor()
    defs = extractor.feature_definitions
    assert set(defs) == {"previous_value", "cpi_change_pct", "cpi_pressure"}
    assert defs["previous_value"].source_columns == ("Value",)
    assert defs["cpi_change_pct"].source_columns == ("Value", "previous_value")
    assert defs["cpi_pressure"].source_columns == ("cpi_change_pct",)


def test_cpi_feature_extractor_matches_legacy_output() -> None:
    raw = pd.DataFrame({
        "Date": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01"]),
        "Value": [100.0, 101.0, 99.0],
    })
    extractor = CPIFeatureExtractor()
    fs = extractor.extract(raw)
    df = fs.data

    assert list(df["Date"]) == [
        pd.Timestamp("2020-02-01"),
        pd.Timestamp("2020-03-01"),
    ]
    assert list(df["Value"]) == [101.0, 99.0]
    assert list(df["previous_value"]) == [100.0, 101.0]
    assert list(df["cpi_change_pct"]) == [1.0, pytest.approx(-1.980198, rel=1e-5)]
    assert list(df["cpi_pressure"]) == ["inflation_pressure_up", "inflation_pressure_down"]


def test_engine_process_validates_feature_set() -> None:
    engine = FeatureExtractionEngine()
    raw = pd.DataFrame({
        "Date": pd.to_datetime(["2020-01-01", "2020-02-01"]),
        "Value": [100.0, 101.0],
    })
    extractor = CPIFeatureExtractor()
    fs = engine.process(raw, extractor)
    assert isinstance(fs, FeatureSet)
    assert "cpi_pressure" in fs.data.columns


def test_event_load_raw_returns_date_value_only() -> None:
    event = CPIEvent()
    path = _write_csv([
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
    ])
    raw = event.load_raw(path)
    assert list(raw.columns) == ["Date", "Value"]
    assert raw["Date"].dtype.kind == "M"
    assert raw["Value"].dtype == "float64"


def test_event_load_raw_sorts_and_deduplicates() -> None:
    event = CPIEvent()
    path = _write_csv([
        {"Date": "2020-03-01", "Value": 99.0},
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-01-01", "Value": 101.0},
        {"Date": "2020-02-01", "Value": 102.0},
    ])
    raw = event.load_raw(path)
    assert list(raw["Date"]) == [
        pd.Timestamp("2020-01-01"),
        pd.Timestamp("2020-02-01"),
        pd.Timestamp("2020-03-01"),
    ]
    assert list(raw["Value"]) == [101.0, 102.0, 99.0]


def test_event_load_raw_raises_on_missing_columns() -> None:
    event = CPIEvent()
    path = _write_csv([{"Date": "2020-01-01"}])
    try:
        event.load_raw(path)
    except ValueError as exc:
        assert "missing required columns" in str(exc)
        assert "Value" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing columns")


def test_event_load_and_extract_with_global_extractor(tmp_path: Path) -> None:
    from knowledge.features.extractors.macro_regime import (
        MacroRegimeFeatureExtractor,
    )
    from knowledge.regime.macro_regime_detector import (
        REGIMES,
        MacroRegimeDetector,
    )

    # Use the same synthetic data pattern as test_macro_regime.py:_make_synthetic_data
    rng = __import__("numpy").random.default_rng(42)
    dates = pd.date_range("2000-01-01", periods=48, freq="ME")
    scores = list(rng.normal(2.0, 0.3, 12)) + list(rng.normal(0.5, 0.3, 12)) + \
             list(rng.normal(-2.0, 0.4, 12)) + list(rng.normal(-0.5, 0.3, 12))
    synthetic = pd.DataFrame({"Date": dates, "composite_score": scores})
    detector = MacroRegimeDetector(random_state=42).fit(synthetic)
    regime_extractor = MacroRegimeFeatureExtractor(detector)
    FeatureExtractionEngine.register_global(regime_extractor)

    event = CPIEvent()
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({
        "Date": ["2020-01-01", "2020-02-01", "2020-03-01"],
        "Value": [100.0, 101.0, 99.0],
    }).to_csv(csv_path, index=False)

    df = event.load_and_extract(csv_path)
    assert "macro_regime" in df.columns
    assert df["macro_regime"].iloc[0] in [*REGIMES, "UNKNOWN"]
    assert not df["macro_regime"].isna().any()


def test_event_load_and_extract_includes_all_columns() -> None:
    event = CPIEvent()
    path = _write_csv([
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
    ])
    df = event.load_and_extract(path)
    assert set(df.columns) == {
        "Date", "Value", "previous_value", "cpi_change_pct", "cpi_pressure",
    }
    assert len(df) == 2
    assert df.iloc[0]["cpi_pressure"] == "inflation_pressure_up"
    assert df.iloc[1]["cpi_pressure"] == "inflation_pressure_down"


def test_event_load_and_extract_empty_on_single_row() -> None:
    event = CPIEvent()
    path = _write_csv([{"Date": "2020-01-01", "Value": 100.0}])
    df = event.load_and_extract(path)
    assert len(df) == 0


def test_global_extractor_adds_column() -> None:
    class TagExtractor(FeatureExtractor):
        @property
        def feature_definitions(self):
            return {
                "tag": Feature(
                    name="tag", dtype="object", description="Test tag",
                    source_columns=("Date",),
                ),
            }

        def extract(self, raw: pd.DataFrame) -> FeatureSet:
            df = raw.copy()
            df["tag"] = "global"
            return FeatureSet(data=df, features=self.feature_definitions)

    FeatureExtractionEngine.register_global(TagExtractor())
    engine = FeatureExtractionEngine()
    raw = pd.DataFrame({"Date": pd.to_datetime(["2020-01-01"]), "Value": [1.0]})

    class PassThroughExtractor(FeatureExtractor):
        @property
        def feature_definitions(self):
            return {
                "Value": Feature(
                    name="Value", dtype="float64", description="Test",
                    source_columns=("Value",),
                ),
            }

        def extract(self, raw: pd.DataFrame) -> FeatureSet:
            return FeatureSet(data=raw.copy(), features=self.feature_definitions)

    fs = engine.process(raw, PassThroughExtractor())
    assert "tag" in fs.data.columns
    assert fs.data["tag"].iloc[0] == "global"


def test_global_extractors_chain_in_order() -> None:
    class FirstExtractor(FeatureExtractor):
        @property
        def feature_definitions(self):
            return {
                "first": Feature(
                    name="first", dtype="int64", description="First",
                    source_columns=("Value",),
                ),
            }

        def extract(self, raw: pd.DataFrame) -> FeatureSet:
            df = raw.copy()
            df["first"] = 1
            return FeatureSet(data=df, features=self.feature_definitions)

    class SecondExtractor(FeatureExtractor):
        @property
        def feature_definitions(self):
            return {
                "second": Feature(
                    name="second", dtype="int64", description="Second",
                    source_columns=("first",),
                ),
            }

        def extract(self, raw: pd.DataFrame) -> FeatureSet:
            df = raw.copy()
            df["second"] = df["first"] + 1
            return FeatureSet(data=df, features=self.feature_definitions)

    FeatureExtractionEngine.register_global(FirstExtractor())
    FeatureExtractionEngine.register_global(SecondExtractor())
    engine = FeatureExtractionEngine()
    raw = pd.DataFrame({"Date": pd.to_datetime(["2020-01-01"]), "Value": [0.0]})

    class BaseExtractor(FeatureExtractor):
        @property
        def feature_definitions(self):
            return {
                "Value": Feature(
                    name="Value", dtype="float64", description="Base",
                    source_columns=("Value",),
                ),
            }

        def extract(self, raw: pd.DataFrame) -> FeatureSet:
            return FeatureSet(data=raw.copy(), features=self.feature_definitions)

    fs = engine.process(raw, BaseExtractor())
    assert fs.data["first"].iloc[0] == 1
    assert fs.data["second"].iloc[0] == 2


def test_global_extractors_backward_compatible() -> None:
    engine = FeatureExtractionEngine()
    raw = pd.DataFrame({"Date": pd.to_datetime(["2020-01-01"]), "Value": [5.0]})

    class DoublerExtractor(FeatureExtractor):
        @property
        def feature_definitions(self):
            return {
                "doubled": Feature(
                    name="doubled", dtype="float64", description="Value * 2",
                    source_columns=("Value",),
                ),
            }

        def extract(self, raw: pd.DataFrame) -> FeatureSet:
            df = raw.copy()
            df["doubled"] = df["Value"] * 2.0
            return FeatureSet(data=df, features=self.feature_definitions)

    fs = engine.process(raw, DoublerExtractor())
    assert fs.data["doubled"].iloc[0] == 10.0


def test_global_extractors_cleared_by_clear_global() -> None:
    class TagExtractor(FeatureExtractor):
        @property
        def feature_definitions(self):
            return {
                "tag": Feature(
                    name="tag", dtype="object", description="Test",
                    source_columns=("Date",),
                ),
            }

        def extract(self, raw: pd.DataFrame) -> FeatureSet:
            df = raw.copy()
            df["tag"] = "present"
            return FeatureSet(data=df, features=self.feature_definitions)

    FeatureExtractionEngine.register_global(TagExtractor())
    FeatureExtractionEngine.clear_global()

    engine = FeatureExtractionEngine()
    raw = pd.DataFrame({"Date": pd.to_datetime(["2020-01-01"]), "Value": [1.0]})

    class PassThroughExtractor(FeatureExtractor):
        @property
        def feature_definitions(self):
            return {
                "Value": Feature(
                    name="Value", dtype="float64", description="Test",
                    source_columns=("Value",),
                ),
            }

        def extract(self, raw: pd.DataFrame) -> FeatureSet:
            return FeatureSet(data=raw.copy(), features=self.feature_definitions)

    fs = engine.process(raw, PassThroughExtractor())
    assert "tag" not in fs.data.columns


def test_engine_with_custom_extractor() -> None:
    class DoublerExtractor(FeatureExtractor):
        @property
        def feature_definitions(self):
            return {
                "doubled": Feature(
                    name="doubled", dtype="float64", description="Value * 2",
                    source_columns=("Value",),
                ),
            }

        def extract(self, raw: pd.DataFrame) -> FeatureSet:
            df = raw.copy()
            df["doubled"] = df["Value"] * 2.0
            return FeatureSet(data=df, features=self.feature_definitions)

    engine = FeatureExtractionEngine()
    raw = pd.DataFrame({"Date": pd.to_datetime(["2020-01-01"]), "Value": [5.0]})
    fs = engine.process(raw, DoublerExtractor())
    assert fs.data["doubled"].iloc[0] == 10.0


import pytest


def _write_csv(rows: list[dict]) -> Path:
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="")
    pd.DataFrame(rows).to_csv(tmp.name, index=False)
    return Path(tmp.name)
