from __future__ import annotations

import pandas as pd
import pytest

from forecasting.models import ForecastPoint, ForecastResult
from forecasting.validation import (
    ForecastValidationReport,
    ForecastValidator,
)


def _df(
    pairs: list[tuple[str, float]],
) -> pd.DataFrame:
    return pd.DataFrame({"ds": [p[0] for p in pairs], "y": [p[1] for p in pairs]})


def _result(
    model_name: str,
    points: tuple[ForecastPoint, ...],
) -> ForecastResult:
    return ForecastResult(
        model_name=model_name,
        confidence_level=0.95,
        points=points,
        metadata={},
    )


def _pt(ds: str, y: float, y_lo: float, y_hi: float) -> ForecastPoint:
    return ForecastPoint(ds=ds, y=y, y_lo=y_lo, y_hi=y_hi)


class TestForecastValidationReport:

    def test_frozen(self) -> None:
        r = ForecastValidationReport(
            validation_strategy="walk_forward",
            metrics={"mae": 0.5},
            horizon=1,
            sample_size=10,
            passed=True,
            notes="OK",
        )
        with pytest.raises(AttributeError):
            r.metrics = {}  # type: ignore[misc]

    def test_all_fields(self) -> None:
        r = ForecastValidationReport(
            validation_strategy="expanding_window",
            metrics={"mae": 1.0, "rmse": 1.5},
            horizon=3,
            sample_size=5,
            passed=False,
            notes="Bad",
        )
        assert r.validation_strategy == "expanding_window"
        assert r.metrics == {"mae": 1.0, "rmse": 1.5}
        assert r.horizon == 3
        assert r.sample_size == 5
        assert r.passed is False
        assert r.notes == "Bad"

    def test_to_dict_keys(self) -> None:
        r = ForecastValidationReport(
            validation_strategy="walk_forward",
            metrics={"mae": 0.3},
            horizon=2,
            sample_size=4,
            passed=True,
            notes="Good",
        )
        d = r.to_dict()
        assert set(d) == {
            "validation_strategy",
            "metrics",
            "horizon",
            "sample_size",
            "passed",
            "notes",
        }

    def test_to_dict_values(self) -> None:
        r = ForecastValidationReport(
            validation_strategy="walk_forward",
            metrics={"mae": 0.3},
            horizon=2,
            sample_size=4,
            passed=True,
            notes="Good",
        )
        d = r.to_dict()
        assert d["validation_strategy"] == "walk_forward"
        assert d["metrics"] == {"mae": 0.3}
        assert d["horizon"] == 2
        assert d["sample_size"] == 4
        assert d["passed"] is True
        assert d["notes"] == "Good"


class TestValidatorEdgeCases:

    def test_empty_actual_data(self) -> None:
        validator = ForecastValidator()
        results = {"m1": _result("m1", (_pt("d1", 100.0, 90.0, 110.0),))}
        report = validator.validate(
            actual_data=pd.DataFrame(columns=["ds", "y"]),
            forecast_results=results,
        )
        assert report.passed is False
        assert report.sample_size == 0
        assert "No aligned" in report.notes

    def test_empty_forecast_results(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0)])
        report = validator.validate(
            actual_data=actual,
            forecast_results={},
        )
        assert report.passed is False
        assert report.sample_size == 0
        assert "No aligned" in report.notes

    def test_no_matching_dates(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0)])
        results = {"m1": _result("m1", (_pt("d2", 105.0, 95.0, 115.0),))}
        report = validator.validate(
            actual_data=actual,
            forecast_results=results,
        )
        assert report.passed is False
        assert report.sample_size == 0

    def test_single_pair(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0)])
        results = {"m1": _result("m1", (_pt("d1", 105.0, 95.0, 115.0),))}
        report = validator.validate(actual, results)
        assert report.sample_size == 1
        assert report.metrics["directional_accuracy"] == 0.0
        assert report.metrics["mae"] > 0
        assert report.metrics["coverage"] == 1.0

    def test_unknown_strategy(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0)])
        results = {"m1": _result("m1", (_pt("d1", 100.0, 90.0, 110.0),))}
        with pytest.raises(ValueError, match="Unknown validation strategy"):
            validator.validate(actual, results, strategy="unknown")

    def test_invalid_horizon(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0)])
        results = {"m1": _result("m1", (_pt("d1", 100.0, 90.0, 110.0),))}
        with pytest.raises(ValueError, match="horizon must be >= 1"):
            validator.validate(actual, results, horizon=0)

    def test_expanding_window_accepted(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0)])
        results = {"m1": _result("m1", (_pt("d1", 100.0, 90.0, 110.0),))}
        report = validator.validate(
            actual, results, strategy="expanding_window"
        )
        assert report.validation_strategy == "expanding_window"

    def test_multiple_models_uses_first(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0), ("d2", 102.0)])
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 100.0, 90.0, 110.0),
                    _pt("d2", 102.0, 92.0, 112.0),
                ),
            ),
            "m2": _result(
                "m2",
                (_pt("d1", 999.0, 0.0, 9999.0),),
            ),
        }
        report = validator.validate(actual, results)
        assert report.passed is True
        assert report.metrics["mae"] == 0.0

    def test_deterministic(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0), ("d2", 102.0)])
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 101.0, 90.0, 110.0),
                    _pt("d2", 103.0, 92.0, 112.0),
                ),
            ),
        }
        r1 = validator.validate(actual, results)
        r2 = validator.validate(actual, results)
        assert r1 == r2


class TestPerfectPredictions:

    def test_all_exact(self) -> None:
        validator = ForecastValidator()
        actual = _df(
            [
                ("d1", 100.0),
                ("d2", 102.0),
                ("d3", 101.0),
            ]
        )
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 100.0, 99.0, 101.0),
                    _pt("d2", 102.0, 101.0, 103.0),
                    _pt("d3", 101.0, 100.0, 102.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert report.metrics["mae"] == 0.0
        assert report.metrics["rmse"] == 0.0
        assert report.metrics["mape"] == 0.0
        assert report.metrics["directional_accuracy"] == 1.0
        assert report.metrics["coverage"] == 1.0
        assert report.passed is True
        assert report.sample_size == 3


class TestTerriblePredictions:

    def test_very_wrong(self) -> None:
        validator = ForecastValidator()
        actual = _df(
            [
                ("d1", 100.0),
                ("d2", 100.0),
            ]
        )
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 0.0, -100.0, 10.0),
                    _pt("d2", 0.0, -100.0, 10.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert not report.passed
        assert report.metrics["mae"] > 80
        assert report.metrics["mape"] > 80


class TestZeroActualValues:

    def test_division_by_zero_handled(self) -> None:
        validator = ForecastValidator()
        actual = _df(
            [
                ("d1", 0.0),
                ("d2", 0.0),
            ]
        )
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 0.5, -1.0, 1.0),
                    _pt("d2", -0.3, -1.0, 1.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert report.metrics["mape"] == 0.0
        assert report.metrics["mae"] > 0
        assert report.sample_size == 2


class TestNegativeActualValues:

    def test_negative_predictions_and_actuals(self) -> None:
        validator = ForecastValidator()
        actual = _df(
            [
                ("d1", -50.0),
                ("d2", -55.0),
            ]
        )
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", -50.0, -55.0, -45.0),
                    _pt("d2", -55.0, -60.0, -50.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert report.metrics["mae"] == 0.0
        assert report.metrics["directional_accuracy"] == 1.0
        assert report.metrics["coverage"] == 1.0
        assert report.passed is True


class TestCoverage:

    def test_all_in_interval(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0), ("d2", 102.0)])
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 100.0, 50.0, 150.0),
                    _pt("d2", 102.0, 52.0, 152.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert report.metrics["coverage"] == 1.0

    def test_none_in_interval(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0), ("d2", 102.0)])
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 100.0, 0.0, 1.0),
                    _pt("d2", 102.0, 0.0, 1.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert report.metrics["coverage"] == 0.0

    def test_half_in_interval(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0), ("d2", 102.0)])
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 100.0, 0.0, 200.0),
                    _pt("d2", 102.0, 0.0, 1.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert report.metrics["coverage"] == 0.5


class TestDirectionalAccuracy:

    def test_all_correct(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0), ("d2", 105.0), ("d3", 103.0)])
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 100.0, 90.0, 110.0),
                    _pt("d2", 105.0, 95.0, 115.0),
                    _pt("d3", 103.0, 93.0, 113.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert report.metrics["directional_accuracy"] == 1.0

    def test_all_wrong(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0), ("d2", 105.0), ("d3", 103.0)])
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 105.0, 95.0, 115.0),
                    _pt("d2", 100.0, 90.0, 110.0),
                    _pt("d3", 105.0, 95.0, 115.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert report.metrics["directional_accuracy"] == 0.0

    def test_mixed(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0), ("d2", 105.0), ("d3", 100.0)])
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 100.0, 90.0, 110.0),
                    _pt("d2", 105.0, 95.0, 115.0),
                    _pt("d3", 105.0, 95.0, 115.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert report.metrics["directional_accuracy"] == 0.5

    def test_no_change_both_correct(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0), ("d2", 100.0)])
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 100.0, 90.0, 110.0),
                    _pt("d2", 100.0, 90.0, 110.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert report.metrics["directional_accuracy"] == 1.0


class TestPassFailThresholds:

    def test_passes_when_all_conditions_met(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0), ("d2", 101.0)])
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 100.0, 80.0, 120.0),
                    _pt("d2", 102.0, 82.0, 122.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert report.passed is True

    def test_fails_on_high_mape(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0), ("d2", 100.0)])
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 50.0, 0.0, 200.0),
                    _pt("d2", 50.0, 0.0, 200.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert report.passed is False

    def test_fails_on_low_coverage(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0), ("d2", 101.0)])
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 100.0, 0.0, 1.0),
                    _pt("d2", 101.0, 0.0, 1.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert report.passed is False

    def test_fails_on_low_da(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0), ("d2", 105.0)])
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 105.0, 0.0, 200.0),
                    _pt("d2", 100.0, 0.0, 200.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert report.passed is False


class TestNotes:

    def test_passed_notes(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0), ("d2", 101.0)])
        results = {
            "m1": _result(
                "m1",
                (
                    _pt("d1", 100.0, 0.0, 200.0),
                    _pt("d2", 101.0, 0.0, 200.0),
                ),
            ),
        }
        report = validator.validate(actual, results)
        assert "All thresholds met" in report.notes
        assert "2 aligned" in report.notes

    def test_failed_notes(self) -> None:
        validator = ForecastValidator()
        actual = _df([("d1", 100.0)])
        results = {"m1": _result("m1", (_pt("d1", 200.0, 0.0, 200.0),))}
        report = validator.validate(actual, results)
        assert "Thresholds not met" in report.notes

    def test_no_pairs_notes(self) -> None:
        validator = ForecastValidator()
        report = validator.validate(
            actual_data=pd.DataFrame(columns=["ds", "y"]),
            forecast_results={},
        )
        assert "No aligned" in report.notes
