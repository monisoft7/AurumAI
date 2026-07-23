from __future__ import annotations

import pytest

from simulation.models import EventRunResult
from simulation.attribution import (
    AttributionPerformanceAggregator,
    AttributionPerformanceRecord,
    AttributionPerformanceReport,
)


def _result(
    event_type: str = "CPI",
    decision_correct: bool | None = True,
    attribution: dict[str, float] | None = None,
) -> EventRunResult:
    return EventRunResult(
        event_type=event_type,
        event_date_min="2020-01-01",
        event_date_max="2020-01-01",
        event_count=1,
        success=True,
        execution_time_ms=100.0,
        cache_hits=0,
        checkpoints_used=0,
        decision="POSITIVE",
        decision_correct=decision_correct,
        attribution=attribution or {},
    )


# ── AttributionPerformanceAggregator ────────────────────────────────────


class TestAttributionPerformanceAggregator:

    def test_empty_history(self) -> None:
        agg = AttributionPerformanceAggregator()
        report = agg.aggregate(tuple())
        assert len(report.records) == 0

    def test_single_experiment(self) -> None:
        agg = AttributionPerformanceAggregator()
        r = _result(attribution={"CPI": 1.0})
        report = agg.aggregate((r,))
        assert len(report.records) == 1
        rec = report.records[0]
        assert rec.event_type == "CPI"
        assert rec.appearances == 1
        assert rec.weighted_contribution == 1.0
        assert rec.correct_count == 1
        assert rec.incorrect_count == 0
        assert rec.weighted_accuracy == 1.0
        assert rec.avg_contribution == 1.0

    def test_multiple_experiments_same_type(self) -> None:
        agg = AttributionPerformanceAggregator()
        results = (
            _result(decision_correct=True, attribution={"CPI": 0.8, "NFP": 0.2}),
            _result(decision_correct=False, attribution={"CPI": 0.6, "NFP": 0.4}),
        )
        report = agg.aggregate(results)
        assert len(report.records) == 2

        cpi = next(r for r in report.records if r.event_type == "CPI")
        assert cpi.appearances == 2
        assert cpi.weighted_contribution == pytest.approx(0.8 + 0.6)
        assert cpi.correct_count == 1
        assert cpi.incorrect_count == 1
        # weighted accuracy: (0.8 * correct + 0.6 * 0) / (0.8 + 0.6)
        assert cpi.weighted_accuracy == pytest.approx(0.8 / (0.8 + 0.6))
        assert cpi.avg_contribution == pytest.approx((0.8 + 0.6) / 2)

        nfp = next(r for r in report.records if r.event_type == "NFP")
        assert nfp.appearances == 2
        assert nfp.correct_count == 1
        assert nfp.incorrect_count == 1
        # weighted accuracy: (0.2 * correct + 0.4 * 0) / (0.2 + 0.4)
        assert nfp.weighted_accuracy == pytest.approx(0.2 / (0.2 + 0.4))

    def test_weighted_accuracy(self) -> None:
        agg = AttributionPerformanceAggregator()
        results = (
            _result(decision_correct=True, attribution={"A": 0.9, "B": 0.1}),
            _result(decision_correct=False, attribution={"A": 0.7, "B": 0.3}),
            _result(decision_correct=True, attribution={"A": 0.5, "B": 0.5}),
        )
        report = agg.aggregate(results)

        a = next(r for r in report.records if r.event_type == "A")
        # correct_weight: 0.9 + 0.0 + 0.5 = 1.4
        # total_weight: 0.9 + 0.7 + 0.5 = 2.1
        assert a.weighted_accuracy == pytest.approx(1.4 / 2.1)

    def test_deterministic_ordering(self) -> None:
        agg = AttributionPerformanceAggregator()
        results = (
            _result(attribution={"A": 0.1, "B": 0.5, "C": 0.4}),
            _result(attribution={"A": 0.2, "B": 0.3, "C": 0.5}),
        )
        report1 = agg.aggregate(results)
        report2 = agg.aggregate(results)

        for r1, r2 in zip(report1.records, report2.records):
            assert r1.event_type == r2.event_type
            assert r1.weighted_accuracy == r2.weighted_accuracy

    def test_no_scored_results_skipped(self) -> None:
        agg = AttributionPerformanceAggregator()
        r = _result(decision_correct=None, attribution={"CPI": 1.0})
        report = agg.aggregate((r,))
        assert len(report.records) == 0

    def test_no_attribution_skipped(self) -> None:
        agg = AttributionPerformanceAggregator()
        r = _result(decision_correct=True, attribution={})
        report = agg.aggregate((r,))
        assert len(report.records) == 0

    def test_single_type_single_decision(self) -> None:
        agg = AttributionPerformanceAggregator()
        r = _result(decision_correct=True, attribution={"CPI": 1.0})
        report = agg.aggregate((r,))
        assert len(report.records) == 1
        rec = report.records[0]
        assert rec.event_type == "CPI"
        assert rec.weighted_accuracy == 1.0
        assert rec.avg_contribution == 1.0

    def test_single_type_mixed_correctness(self) -> None:
        agg = AttributionPerformanceAggregator()
        results = tuple(
            _result(decision_correct=i < 3, attribution={"CPI": 1.0})
            for i in range(5)
        )
        report = agg.aggregate(results)
        rec = report.records[0]
        assert rec.appearances == 5
        assert rec.correct_count == 3
        assert rec.incorrect_count == 2
        assert rec.weighted_accuracy == 3.0 / 5.0


# ── AttributionPerformanceReport ────────────────────────────────────────


class TestAttributionPerformanceReport:

    def test_to_dict(self) -> None:
        rec = AttributionPerformanceRecord(
            event_type="CPI", appearances=5,
            weighted_contribution=2.0, correct_count=4,
            incorrect_count=1, weighted_accuracy=0.8,
            avg_contribution=0.4,
        )
        report = AttributionPerformanceReport(records=(rec,))
        d = report.to_dict()
        assert len(d["records"]) == 1
        assert d["records"][0]["event_type"] == "CPI"
        assert d["records"][0]["weighted_accuracy"] == 0.8

    def test_format_table(self) -> None:
        rec = AttributionPerformanceRecord(
            event_type="CPI", appearances=5,
            weighted_contribution=2.0, correct_count=4,
            incorrect_count=1, weighted_accuracy=0.8,
            avg_contribution=0.4,
        )
        report = AttributionPerformanceReport(records=(rec,))
        table = report.format_table()
        assert "Event" in table
        assert "Accuracy" in table
        assert "Avg Contribution" in table
        assert "CPI" in table
        assert "80.0%" in table
        assert "40%" in table


# ── Backward Compatibility ──────────────────────────────────────────────


class TestBackwardCompatibility:

    def test_event_run_result_default_attribution(self) -> None:
        r = _result()
        assert r.attribution == {}

    def test_existing_tests_unaffected(self) -> None:
        r = EventRunResult(
            event_type="CPI",
            event_date_min="2020-01-01",
            event_date_max="2020-01-01",
            event_count=1,
            success=True,
            execution_time_ms=100.0,
            cache_hits=0,
            checkpoints_used=0,
        )
        assert r.attribution == {}
        assert r.decision is None
        assert r.decision_correct is None
