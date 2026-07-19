from __future__ import annotations

import datetime
from typing import Any

import pandas as pd
import pytest

from forecasting.context import EventSummary, ForecastContext, ForecastContextBuilder
from forecasting.knowledge import ForecastKnowledge, ForecastPackage
from forecasting.models import ForecastPoint, ForecastResult
from forecasting.provenance import ForecastProvenance
from forecasting.registry import DuplicateRegistrationError, ForecastModelSpec, ForecastRegistry

try:
    from statsforecast.models import AutoARIMA, AutoETS, AutoTheta

    HAS_STATSFORECAST = True
except ImportError:
    HAS_STATSFORECAST = False

_PINNED_TS = "2026-07-18T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_and_seed_registry() -> None:
    ForecastRegistry._reset()
    _seed_registry()
    yield
    ForecastRegistry._reset()


def _seed_registry() -> None:
    ForecastRegistry.register(
        ForecastModelSpec(
            name="cpi_arima",
            model_cls=AutoARIMA,
            model_kwargs={"season_length": 12},
            target_variable="CPI",
            freq="ME",
            default_horizon=12,
            max_horizon=24,
            training_window="2y",
            validation_strategy="backtest",
            validation_split=0.2,
            approval_status="approved",
            approved_by="admin",
            approval_date="2026-07-01",
            description="AutoARIMA for CPI",
        ),
    )
    ForecastRegistry.register(
        ForecastModelSpec(
            name="cpi_ets",
            model_cls=AutoETS,
            model_kwargs={"season_length": 12, "model": "ZZZ"},
            target_variable="CPI",
            freq="ME",
            default_horizon=12,
            max_horizon=24,
            training_window="2y",
            validation_strategy="backtest",
            validation_split=0.2,
            approval_status="approved",
            approved_by="admin",
            approval_date="2026-07-01",
            description="AutoETS for CPI",
        ),
    )
    ForecastRegistry.register(
        ForecastModelSpec(
            name="gdp_unapproved",
            model_cls=AutoTheta,
            model_kwargs={"season_length": 12},
            target_variable="GDP",
            freq="ME",
            default_horizon=6,
            max_horizon=12,
            training_window="2y",
            validation_strategy="backtest",
            validation_split=0.2,
            approval_status="pending",
            approved_by=None,
            approval_date=None,
            description="Pending GDP model",
        ),
    )


@pytest.fixture
def sample_data() -> pd.DataFrame:
    return pd.DataFrame({
        "ds": pd.date_range("2020-01-01", periods=24, freq="ME"),
        "y": [100.0 + i * 0.5 for i in range(24)],
    })


# ---------------------------------------------------------------------------
# ForecastPackage
# ---------------------------------------------------------------------------


class TestForecastPackage:

    def test_frozen_dataclass(self) -> None:
        ctx = _minimal_context()
        prov = _dummy_provenance()
        pkg = ForecastPackage(
            target_variable="CPI",
            context=ctx,
            results={},
            provenance=prov,
            model_specs=(),
            horizon=12,
        )
        with pytest.raises(AttributeError):
            pkg.target_variable = "GDP"  # type: ignore[misc]

    def test_all_fields(self, sample_data: pd.DataFrame) -> None:
        ctx = _minimal_context()
        prov = _dummy_provenance()
        result = ForecastResult(
            model_name="AutoARIMA",
            confidence_level=0.95,
            points=(
                ForecastPoint(ds="2026-07-31", y=105.0, y_lo=100.0, y_hi=110.0),
            ),
            metadata={"h": 1, "n_obs": 24},
        )
        pkg = ForecastPackage(
            target_variable="CPI",
            context=ctx,
            results={"AutoARIMA": result},
            provenance=prov,
            model_specs=(_cpi_arima_spec(),),
            horizon=12,
        )
        assert pkg.target_variable == "CPI"
        assert pkg.context == ctx
        assert "AutoARIMA" in pkg.results
        assert pkg.provenance == prov
        assert len(pkg.model_specs) == 1
        assert pkg.horizon == 12

    def test_to_dict_keys(self) -> None:
        ctx = _minimal_context()
        prov = _dummy_provenance()
        pkg = ForecastPackage(
            target_variable="CPI",
            context=ctx,
            results={},
            provenance=prov,
            model_specs=(),
            horizon=6,
        )
        d = pkg.to_dict()
        expected = {"target_variable", "context", "results", "provenance", "model_specs", "horizon"}
        assert set(d) == expected

    def test_to_dict_results_structure(self) -> None:
        ctx = _minimal_context()
        prov = _dummy_provenance()
        result = ForecastResult(
            model_name="AutoARIMA",
            confidence_level=0.95,
            points=(
                ForecastPoint(ds="2026-07-31", y=105.0, y_lo=100.0, y_hi=110.0),
            ),
            metadata={"h": 1, "n_obs": 24},
        )
        pkg = ForecastPackage(
            target_variable="CPI",
            context=ctx,
            results={"AutoARIMA": result},
            provenance=prov,
            model_specs=(_cpi_arima_spec(),),
            horizon=6,
        )
        d = pkg.to_dict()
        assert "AutoARIMA" in d["results"]
        r = d["results"]["AutoARIMA"]
        assert r["model_name"] == "AutoARIMA"
        assert r["confidence_level"] == 0.95
        assert len(r["points"]) == 1
        assert r["points"][0]["ds"] == "2026-07-31"

    def test_to_dict_model_specs_structure(self) -> None:
        ctx = _minimal_context()
        prov = _dummy_provenance()
        pkg = ForecastPackage(
            target_variable="CPI",
            context=ctx,
            results={},
            provenance=prov,
            model_specs=(_cpi_arima_spec(), _cpi_ets_spec()),
            horizon=6,
        )
        d = pkg.to_dict()
        assert len(d["model_specs"]) == 2
        names = [s["name"] for s in d["model_specs"]]
        assert "cpi_arima" in names
        assert "cpi_ets" in names


# ---------------------------------------------------------------------------
# ForecastKnowledge — full integration (statsforecast required)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_STATSFORECAST, reason="statsforecast not installed")
class TestForecastKnowledgeFull:

    def test_forecast_returns_package(self, sample_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=sample_data, horizon=6)
        assert isinstance(pkg, ForecastPackage)
        assert pkg.target_variable == "CPI"
        assert pkg.horizon == 6
        assert isinstance(pkg.context, ForecastContext)
        assert isinstance(pkg.provenance, ForecastProvenance)

    def test_forecast_runs_all_approved_models(self, sample_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=sample_data, horizon=6)
        assert len(pkg.results) == 2
        assert "AutoARIMA" in pkg.results
        assert "AutoETS" in pkg.results

    def test_forecast_results_have_points(self, sample_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=sample_data, horizon=6)
        for name, result in pkg.results.items():
            assert len(result.points) == 6
            for pt in result.points:
                assert isinstance(pt.ds, str)
                assert isinstance(pt.y, float)

    def test_forecast_model_specs_attached(self, sample_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=sample_data, horizon=6)
        assert len(pkg.model_specs) == 2
        names = {s.name for s in pkg.model_specs}
        assert names == {"cpi_arima", "cpi_ets"}

    def test_forecast_only_unapproved_if_named(self, sample_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(
            target_variable="GDP",
            training_data=sample_data,
            horizon=6,
            model_names=["gdp_unapproved"],
        )
        assert len(pkg.results) == 1
        assert len(pkg.model_specs) == 1
        assert pkg.model_specs[0].name == "gdp_unapproved"

    def test_forecast_skips_unapproved_by_default(self, sample_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="GDP", training_data=sample_data, horizon=6)
        assert len(pkg.results) == 0
        assert len(pkg.model_specs) == 0

    def test_forecast_raises_on_missing_columns(self) -> None:
        knowledge = ForecastKnowledge()
        bad_data = pd.DataFrame({"a": [1, 2, 3]})
        with pytest.raises(ValueError, match="ds"):
            knowledge.forecast(target_variable="CPI", training_data=bad_data)

    def test_provenance_includes_data_hash(self, sample_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=sample_data, horizon=6)
        assert pkg.provenance.data_hash != ""
        assert pkg.provenance.git_commit != ""

    def test_provenance_includes_registry_version(self, sample_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=sample_data, horizon=6)
        assert pkg.provenance.registry_version == "3"

    def test_context_is_built(self, sample_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=sample_data, horizon=6)
        assert pkg.context.source_variable == "CPI"
        assert pkg.context.data_date_range != ("", "")

    def test_deterministic_with_same_data(self, sample_data: pd.DataFrame) -> None:
        from forecasting.context import ForecastContextBuilder

        class StubBuilder(ForecastContextBuilder):
            def build(self, *args: Any, **kwargs: Any) -> ForecastContext:
                kwargs["_timestamp"] = _PINNED_TS
                return super().build(*args, **kwargs)

        knowledge = ForecastKnowledge(context_builder=StubBuilder())
        pkg1 = knowledge.forecast(target_variable="CPI", training_data=sample_data, horizon=6)
        pkg2 = knowledge.forecast(target_variable="CPI", training_data=sample_data, horizon=6)
        assert pkg1.context == pkg2.context

    def test_news_and_fomc_in_context(self, sample_data: pd.DataFrame) -> None:
        from forecasting.context import ForecastContextBuilder
        from tests.test_forecast_context import _MockNewsSentimentAnalyzer, _MockFOMCSentimentAnalyzer, _MockRegimeDetector

        builder = ForecastContextBuilder(
            regime_detector=_MockRegimeDetector("EXPANSION"),
            news_analyzer=_MockNewsSentimentAnalyzer("positive", 0.9),
            fomc_analyzer=_MockFOMCSentimentAnalyzer("hawkish", 0.8),
        )
        knowledge = ForecastKnowledge(context_builder=builder)
        pkg = knowledge.forecast(
            target_variable="CPI",
            training_data=sample_data,
            horizon=6,
            news_texts=["Good news", "Better news"],
            fomc_texts=["Hawkish statement"],
        )
        assert pkg.context.current_regime == "EXPANSION"
        assert pkg.context.news_mood == "positive"
        assert pkg.context.fomc_mood == "hawkish"


# ---------------------------------------------------------------------------
# ForecastKnowledge — graceful degradation
# ---------------------------------------------------------------------------


class TestForecastKnowledgeDegradation:

    def test_empty_registry_returns_no_results(self, sample_data: pd.DataFrame) -> None:
        ForecastRegistry._reset()
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=sample_data, horizon=6)
        assert pkg.results == {}
        assert pkg.model_specs == ()

    def test_no_matching_target_returns_no_results(self, sample_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="NONEXISTENT", training_data=sample_data, horizon=6)
        assert pkg.results == {}
        assert pkg.model_specs == ()

    def test_context_still_built_even_with_no_models(self, sample_data: pd.DataFrame) -> None:
        ForecastRegistry._reset()
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=sample_data, horizon=6)
        assert isinstance(pkg.context, ForecastContext)
        assert pkg.context.source_variable == "CPI"

    def test_provenance_still_attached_even_with_no_models(self, sample_data: pd.DataFrame) -> None:
        ForecastRegistry._reset()
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=sample_data, horizon=6)
        assert isinstance(pkg.provenance, ForecastProvenance)


# ---------------------------------------------------------------------------
# ForecastKnowledge — context_builder override
# ---------------------------------------------------------------------------


class TestForecastKnowledgeCustomBuilder:

    def test_custom_context_builder(self, sample_data: pd.DataFrame) -> None:
        builder = ForecastContextBuilder()
        builder._regime_detector = None  # type: ignore[assignment]
        knowledge = ForecastKnowledge(context_builder=builder)
        pkg = knowledge.forecast(target_variable="CPI", training_data=sample_data, horizon=6)
        assert pkg.context.current_regime is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_context() -> ForecastContext:
    return ForecastContext(
        current_regime=None,
        regime_confidence=0.0,
        recent_events=(),
        news_mood=None,
        news_confidence=0.0,
        fomc_mood=None,
        fomc_confidence=0.0,
        context_timestamp=_PINNED_TS,
        source_variable="CPI",
        data_date_range=("2020-01-01", "2020-12-31"),
    )


def _dummy_provenance() -> ForecastProvenance:
    return ForecastProvenance(
        source="CPI",
        model_version="1",
        training_window="24 obs",
        registry_version="1",
        git_commit="abc123",
        data_hash="def456",
        created_at=_PINNED_TS,
    )


def _cpi_arima_spec() -> ForecastModelSpec:
    return ForecastModelSpec(
        name="cpi_arima",
        model_cls=AutoARIMA,
        model_kwargs={"season_length": 12},
        target_variable="CPI",
        freq="ME",
        default_horizon=12,
        max_horizon=24,
        training_window="2y",
        validation_strategy="backtest",
        validation_split=0.2,
        approval_status="approved",
        approved_by="admin",
        approval_date="2026-07-01",
        description="AutoARIMA for CPI",
    )


def _cpi_ets_spec() -> ForecastModelSpec:
    return ForecastModelSpec(
        name="cpi_ets",
        model_cls=AutoETS,
        model_kwargs={"season_length": 12, "model": "ZZZ"},
        target_variable="CPI",
        freq="ME",
        default_horizon=12,
        max_horizon=24,
        training_window="2y",
        validation_strategy="backtest",
        validation_split=0.2,
        approval_status="approved",
        approved_by="admin",
        approval_date="2026-07-01",
        description="AutoETS for CPI",
    )
