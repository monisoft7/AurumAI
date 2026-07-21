"""Tests for the Institutional Experiment Framework."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from simulation.experiment import (
    ComparisonMetrics,
    DecisionComparison,
    ExperimentComparator,
    ExperimentConfig,
    ExperimentReport,
    ExperimentReportBuilder,
    ExperimentResult,
    ExperimentRunner,
    RunConfig,
)
from simulation.historical_replay import (
    ChronologicalOOSResult,
    EventRunResult,
    OOSSummary,
)


# ===========================================================================
# Fixtures
# ===========================================================================


def _fake_result(
    event_type: str,
    decision: str | None = "POSITIVE",
    decision_correct: bool | None = True,
    event_count: int = 1,
) -> EventRunResult:
    return EventRunResult(
        event_type=event_type,
        event_date_min="2020-01-01",
        event_date_max="2020-06-01",
        event_count=event_count,
        success=True,
        execution_time_ms=100.0,
        cache_hits=0,
        checkpoints_used=0,
        decision=decision,
        decision_correct=decision_correct,
    )


@pytest.fixture
def fake_baseline_result() -> ChronologicalOOSResult:
    return ChronologicalOOSResult(
        cutoff_date="2020-06-01",
        evaluation_results=(
            _fake_result("CPI", "POSITIVE", True),
            _fake_result("NFP", "NEGATIVE", True),
            _fake_result("PPI", "POSITIVE", False),
        ),
        summary=OOSSummary(
            total_events=3,
            scored_events=3,
            abstained_events=0,
            directional_accuracy=0.667,
            macro_precision=0.600,
            macro_recall=0.600,
            coverage=1.0,
            abstention_rate=0.0,
            strong_error_rate=0.0,
            ece=0.05,
        ),
    )


@pytest.fixture
def fake_candidate_result() -> ChronologicalOOSResult:
    return ChronologicalOOSResult(
        cutoff_date="2020-06-01",
        evaluation_results=(
            _fake_result("CPI", "NEGATIVE", False),
            _fake_result("NFP", "NEGATIVE", True),
            _fake_result("PPI", "POSITIVE", True),
        ),
        summary=OOSSummary(
            total_events=3,
            scored_events=3,
            abstained_events=0,
            directional_accuracy=0.333,
            macro_precision=0.400,
            macro_recall=0.400,
            coverage=1.0,
            abstention_rate=0.0,
            strong_error_rate=0.333,
            ece=0.10,
        ),
    )


# ===========================================================================
# DecisionComparison
# ===========================================================================


class TestDecisionComparison:
    def test_to_dict(self) -> None:
        dc = DecisionComparison(
            event_type="CPI",
            total_events=4,
            decisions_changed=2,
            decisions_improved=1,
            decisions_degraded=1,
            baseline_correct=3,
            candidate_correct=2,
        )
        d = dc.to_dict()
        assert d["event_type"] == "CPI"
        assert d["total_events"] == 4
        assert d["decisions_changed"] == 2
        assert json.dumps(d)


# ===========================================================================
# ComparisonMetrics
# ===========================================================================


class TestComparisonMetrics:
    def test_to_dict(self) -> None:
        cm = ComparisonMetrics(
            directional_accuracy_delta=-0.1,
            macro_precision_delta=0.05,
            macro_recall_delta=-0.02,
            coverage_delta=0.0,
            abstention_rate_delta=-0.01,
            strong_error_rate_delta=0.03,
            ece_delta=0.02,
        )
        d = cm.to_dict()
        assert d["directional_accuracy_delta"] == -0.1
        assert json.dumps(d)

    def test_empty(self) -> None:
        cm = ComparisonMetrics()
        d = cm.to_dict()
        assert d["directional_accuracy_delta"] is None


# ===========================================================================
# ExperimentComparator
# ===========================================================================


class TestExperimentComparator:
    def test_compare_identical(self) -> None:
        """Same results → zero deltas and no decision changes."""
        r = ChronologicalOOSResult(
            cutoff_date="2020-06-01",
            evaluation_results=(
                _fake_result("CPI", "POSITIVE", True),
            ),
            summary=OOSSummary(
                total_events=1, scored_events=1, abstained_events=0,
                directional_accuracy=1.0, macro_precision=1.0, macro_recall=1.0,
                coverage=1.0, abstention_rate=0.0, strong_error_rate=0.0, ece=0.0,
            ),
        )
        comp = ExperimentComparator.compare(r, r)
        assert comp.directional_accuracy_delta == 0.0
        assert comp.total_decisions_changed == 0

    def test_compare_different(
        self,
        fake_baseline_result: ChronologicalOOSResult,
        fake_candidate_result: ChronologicalOOSResult,
    ) -> None:
        comp = ExperimentComparator.compare(
            fake_baseline_result, fake_candidate_result
        )
        # CPI changed from correct POSITIVE → incorrect NEGATIVE
        assert comp.total_decisions_changed > 0
        assert comp.total_decisions_improved == 1  # PPI improved
        assert comp.total_decisions_degraded == 1  # CPI degraded

    def test_compare_only_baseline(self) -> None:
        """Candidate with no evaluation results."""
        b = ChronologicalOOSResult(
            cutoff_date="2020-06-01",
            evaluation_results=(_fake_result("CPI", "POSITIVE", True),),
            summary=OOSSummary(total_events=1, scored_events=1, abstained_events=0),
        )
        c = ChronologicalOOSResult(
            cutoff_date="2020-06-01",
            evaluation_results=(),
            summary=None,
        )
        comp = ExperimentComparator.compare(b, c)
        # No aligned types with data → no decision comparisons
        assert comp.decision_comparisons == ()

    def test_missing_summary(self) -> None:
        """Both results have summary=None → all deltas are None."""
        b = ChronologicalOOSResult(cutoff_date="2020-01-01")
        c = ChronologicalOOSResult(cutoff_date="2020-01-01")
        comp = ExperimentComparator.compare(b, c)
        assert comp.directional_accuracy_delta is None
        assert comp.macro_precision_delta is None


# ===========================================================================
# ExperimentConfig + RunConfig
# ===========================================================================


class TestExperimentConfig:
    def test_defaults(self) -> None:
        cfg = ExperimentConfig(
            experiment_name="test_exp",
            cutoff_date="2020-06-01",
        )
        assert cfg.experiment_name == "test_exp"
        assert cfg.baseline.name == "baseline"
        assert cfg.candidate.name == "candidate"
        assert cfg.baseline.horizon == 12
        assert cfg.candidate.horizon == 12

    def test_custom_arms(self) -> None:
        cfg = ExperimentConfig(
            experiment_name="cpi_vs_cpi_us10y",
            cutoff_date="2023-01-01",
            baseline=RunConfig(name="cpi_only", horizon=12, max_workers=2),
            candidate=RunConfig(name="cpi_us10y", horizon=26, max_workers=4),
            description="CPI only vs CPI + US10Y",
        )
        assert cfg.baseline.horizon == 12
        assert cfg.candidate.horizon == 26
        assert cfg.candidate.max_workers == 4


# ===========================================================================
# ExperimentResult
# ===========================================================================


class TestExperimentResult:
    def test_to_dict(
        self,
        fake_baseline_result: ChronologicalOOSResult,
        fake_candidate_result: ChronologicalOOSResult,
    ) -> None:
        cfg = ExperimentConfig(
            experiment_name="test",
            cutoff_date="2020-06-01",
        )
        comp = ExperimentComparator.compare(
            fake_baseline_result, fake_candidate_result
        )
        result = ExperimentResult(
            config=cfg,
            baseline_result=fake_baseline_result,
            candidate_result=fake_candidate_result,
            comparison=comp,
        )
        d = result.to_dict()
        assert d["experiment_name"] == "test"
        assert "baseline" in d
        assert "candidate" in d
        assert "comparison" in d
        assert json.dumps(d)


# ===========================================================================
# ExperimentReport
# ===========================================================================


class TestExperimentReport:
    def test_human_readable(
        self,
        fake_baseline_result: ChronologicalOOSResult,
        fake_candidate_result: ChronologicalOOSResult,
    ) -> None:
        cfg = ExperimentConfig(
            experiment_name="test_report",
            cutoff_date="2020-06-01",
            description="Unit test comparison",
        )
        comp = ExperimentComparator.compare(
            fake_baseline_result, fake_candidate_result
        )
        result = ExperimentResult(
            config=cfg,
            baseline_result=fake_baseline_result,
            candidate_result=fake_candidate_result,
            comparison=comp,
        )
        report = ExperimentReportBuilder.build(result)
        assert isinstance(report.human_text, str)
        assert len(report.human_text) > 100
        assert "test_report" in report.human_text
        assert "baseline" in report.human_text.lower()
        assert "candidate" in report.human_text.lower()
        assert "Directional Acc" in report.human_text
        assert isinstance(report.machine_dict, dict)

    def test_to_json(
        self,
        fake_baseline_result: ChronologicalOOSResult,
        fake_candidate_result: ChronologicalOOSResult,
    ) -> None:
        cfg = ExperimentConfig(
            experiment_name="test_report",
            cutoff_date="2020-06-01",
        )
        comp = ExperimentComparator.compare(
            fake_baseline_result, fake_candidate_result
        )
        result = ExperimentResult(
            config=cfg,
            baseline_result=fake_baseline_result,
            candidate_result=fake_candidate_result,
            comparison=comp,
        )
        report = ExperimentReportBuilder.build(result)
        j = report.to_json()
        parsed = json.loads(j)
        assert parsed["experiment_name"] == "test_report"
