"""Tests for EXP-002 (Evidence Isolation Experiment).

Verifies that the experiment executes correctly, does not modify
frozen core, and produces the expected output structure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.run_experiment_002 import (
    EvidenceIsolationExperiment,
    condition_label,
    extract_unique_conditions,
)


# ===========================================================================
# Unit tests: helper functions
# ===========================================================================


class TestExtractUniqueConditions:
    def test_empty_list(self) -> None:
        assert extract_unique_conditions([]) == []

    def test_no_conditions(self) -> None:
        records = [
            {"knowledge_id": "r1", "event_type": "CPI"},
            {"knowledge_id": "r2", "event_type": "CPI"},
        ]
        assert extract_unique_conditions(records) == []

    def test_single_condition(self) -> None:
        records = [
            {"condition": {"cpi_pressure": "up"}, "horizon_days": 1},
            {"condition": {"cpi_pressure": "up"}, "horizon_days": 5},
        ]
        result = extract_unique_conditions(records)
        assert len(result) == 1
        assert result[0] == {"cpi_pressure": "up"}

    def test_multiple_conditions(self) -> None:
        records = [
            {"condition": {"cpi_pressure": "up"}, "horizon_days": 1},
            {"condition": {"cpi_pressure": "down"}, "horizon_days": 1},
            {"condition": {"cpi_pressure": "up"}, "horizon_days": 5},
        ]
        result = extract_unique_conditions(records)
        assert len(result) == 2
        assert {"cpi_pressure": "up"} in result
        assert {"cpi_pressure": "down"} in result

    def test_preserves_order(self) -> None:
        records = [
            {"condition": {"cpi_pressure": "b"}, "horizon_days": 1},
            {"condition": {"cpi_pressure": "a"}, "horizon_days": 1},
        ]
        result = extract_unique_conditions(records)
        assert result[0] == {"cpi_pressure": "b"}
        assert result[1] == {"cpi_pressure": "a"}

    def test_empty_condition_dict(self) -> None:
        records = [
            {"condition": {}, "horizon_days": 1},
        ]
        assert extract_unique_conditions(records) == []

    def test_none_condition(self) -> None:
        records = [
            {"condition": None, "horizon_days": 1},
        ]
        assert extract_unique_conditions(records) == []

    def test_multi_key_condition(self) -> None:
        records = [
            {"condition": {"cpi_pressure": "up", "us10y_trend": "rising"}},
            {"condition": {"cpi_pressure": "up", "us10y_trend": "falling"}},
        ]
        result = extract_unique_conditions(records)
        assert len(result) == 2


class TestConditionLabel:
    def test_single_key(self) -> None:
        assert condition_label({"cpi_pressure": "up"}) == "cpi_pressure=up"

    def test_multi_key(self) -> None:
        label = condition_label({"a": "1", "b": "2"})
        assert "a=1" in label
        assert "b=2" in label

    def test_empty(self) -> None:
        assert condition_label({}) == ""


# ===========================================================================
# Integration test: experiment execution
# ===========================================================================


class TestEvidenceIsolationExperiment:
    """Integration test that runs the experiment end-to-end.

    These tests verify the experiment produces the correct output structure
    and does not modify frozen core (no files under src/knowledge/ changed).
    """

    @pytest.fixture(scope="class")
    def experiment_results(self) -> dict:
        exp = EvidenceIsolationExperiment(
            output_dir=Path("data/experiments/EXP-002-Evidence-Isolation")
        )
        return exp.run()

    def test_experiment_has_correct_name(
        self, experiment_results: dict
    ) -> None:
        assert experiment_results["experiment"] == "EXP-002-Evidence-Isolation"

    def test_hypothesis_is_present(self, experiment_results: dict) -> None:
        assert "hypothesis" in experiment_results
        assert len(experiment_results["hypothesis"]) > 50

    def test_methodology_is_present(self, experiment_results: dict) -> None:
        m = experiment_results["methodology"]
        assert "baseline" in m
        assert "isolated" in m

    def test_event_type_is_cpi(self, experiment_results: dict) -> None:
        assert experiment_results["event_type"] == "CPI"

    def test_condition_columns(self, experiment_results: dict) -> None:
        assert "cpi_pressure" in experiment_results["condition_columns"]

    def test_baseline_has_decision(self, experiment_results: dict) -> None:
        b = experiment_results["baseline"]
        assert b["decision_type"] in (
            "STRONG_POSITIVE", "POSITIVE", "NEUTRAL",
            "NEGATIVE", "STRONG_NEGATIVE", "INSUFFICIENT_EVIDENCE",
            "NO_DECISION",
        )
        assert b["confidence"] >= 0.0
        assert b["evidence_count"] >= 0

    def test_baseline_knowledge_records(self, experiment_results: dict) -> None:
        assert experiment_results["knowledge_records"] >= 6

    def test_conditions_found(self, experiment_results: dict) -> None:
        assert experiment_results["conditions_found"] >= 1
        assert experiment_results["conditions_found"] <= experiment_results["knowledge_records"]

    def test_isolated_has_per_condition_results(
        self, experiment_results: dict
    ) -> None:
        iso = experiment_results["isolated"]
        assert len(iso) == experiment_results["conditions_found"]
        for cond_label, cond_result in iso.items():
            assert "condition" in cond_result
            assert "decision_type" in cond_result
            assert "confidence" in cond_result
            assert "evidence_count" in cond_result

    def test_per_condition_evidence_counts(
        self, experiment_results: dict
    ) -> None:
        iso = experiment_results["isolated"]
        total_iso_evidence = sum(
            r["evidence_count"] for r in iso.values()
        )
        merged_count = experiment_results["baseline"]["evidence_count"]
        assert total_iso_evidence == merged_count

    def test_comparison_structure(self, experiment_results: dict) -> None:
        c = experiment_results["comparison"]
        assert "merged_decision_type" in c
        assert "per_condition" in c
        assert c["total_conditions"] == experiment_results["conditions_found"]
        assert len(c["per_condition"]) == c["total_conditions"]

    def test_per_condition_comparison_entries(
        self, experiment_results: dict
    ) -> None:
        c = experiment_results["comparison"]
        for pc in c["per_condition"]:
            assert "condition" in pc
            assert "decision_type" in pc
            assert "matches_baseline" in pc
            assert isinstance(pc["matches_baseline"], bool)

    def test_conditions_accounted(self, experiment_results: dict) -> None:
        c = experiment_results["comparison"]
        assert (
            c["conditions_matching_baseline"] + c["conditions_differing"]
            == c["total_conditions"]
        )

    def test_report_generates(self, experiment_results: dict) -> None:
        exp = EvidenceIsolationExperiment(
            output_dir=Path("data/experiments/EXP-002-Evidence-Isolation")
        )
        exp._results = experiment_results
        report = exp._build_report()
        assert isinstance(report, str)
        assert len(report) > 100
        assert "EXP-002-Evidence-Isolation" in report
        assert "Baseline: Merged Pipeline" in report
        assert "Isolated: Per-Condition Pipeline" in report
        assert "Comparison" in report

    def test_results_serializable(self, experiment_results: dict) -> None:
        dumped = json.dumps(experiment_results, indent=2, default=str)
        parsed = json.loads(dumped)
        assert parsed["experiment"] == "EXP-002-Evidence-Isolation"
        assert "baseline" in parsed
        assert "isolated" in parsed
        assert "comparison" in parsed

    def test_no_frozen_core_modification(self) -> None:
        """Verify no files under src/knowledge/ were modified."""
        knowledge_files = list(Path("src/knowledge").rglob("*.py"))
        for f in knowledge_files:
            content = f.read_text()
            assert "EXP-002" not in content, (
                f"Frozen core file {f} contains EXP-002 code"
            )
