"""Tests for the Knowledge Expansion Framework."""

from pathlib import Path

import pandas as pd
import pytest

from knowledge.events.base import MacroEvent, StandardEventMetadata
from knowledge.events.registry import EventRegistry
from knowledge.expansion import (
    EventScaffolder,
    EventValidator,
    ExpansionLifecycle,
    ExpansionSpec,
)
from knowledge.expansion.lifecycle import ExpansionAudit
from knowledge.expansion.validator import ValidationReport


# ---------------------------------------------------------------------------
# ExpansionSpec
# ---------------------------------------------------------------------------


class TestExpansionSpec:
    def test_minimal_spec(self) -> None:
        spec = ExpansionSpec(event_type="TEST")
        assert spec.event_type == "TEST"
        assert spec.lesson_version == "test_gold_v1"
        assert spec.condition_columns == ["test_trend"]
        assert spec.knowledge_version == "test_gold_summary_v1"

    def test_custom_spec(self) -> None:
        spec = ExpansionSpec(
            event_type="PMI",
            country="US",
            unit="index",
            importance=2,
            lesson_version="pmi_gold_v2",
            condition_columns=["pmi_sector", "pmi_trend"],
            knowledge_version="pmi_gold_summary_v2",
        )
        assert spec.lesson_version == "pmi_gold_v2"
        assert spec.condition_columns == ["pmi_sector", "pmi_trend"]
        assert spec.knowledge_version == "pmi_gold_summary_v2"

    def test_class_names(self) -> None:
        spec = ExpansionSpec(event_type="GDP")
        assert spec.event_class_name == "GDPEvent"
        assert spec.extractor_class_name == "GDPFeatureExtractor"

    def test_multi_word_event_type(self) -> None:
        spec = ExpansionSpec(event_type="INTEREST_RATE")
        assert spec.event_class_name == "InterestRateEvent"
        assert spec.extractor_class_name == "InterestRateFeatureExtractor"

    def test_acronym_class_name(self) -> None:
        spec = ExpansionSpec(event_type="PPI")
        assert spec.event_class_name == "PPIEvent"
        spec2 = ExpansionSpec(event_type="CPI")
        assert spec2.event_class_name == "CPIEvent"


# ---------------------------------------------------------------------------
# EventScaffolder
# ---------------------------------------------------------------------------


class TestEventScaffolder:
    @pytest.fixture
    def tmp_src(self, tmp_path: Path) -> Path:
        src = tmp_path / "src"
        (src / "knowledge" / "events").mkdir(parents=True)
        (src / "knowledge" / "features" / "extractors").mkdir(parents=True)
        (tmp_path / "tests").mkdir(parents=True)
        return src

    @pytest.fixture
    def spec(self) -> ExpansionSpec:
        return ExpansionSpec(
            event_type="PPI",
            country="US",
            unit="index",
            importance=2,
            source="Bureau of Labor Statistics",
        )

    def test_scaffold_event_class(self, tmp_src: Path, spec: ExpansionSpec) -> None:
        scaffolder = EventScaffolder(spec, src_root=tmp_src)
        path = scaffolder.scaffold_event_class()
        assert path.exists()
        content = path.read_text()
        assert "class PPIEvent(MacroEvent):" in content
        assert 'event_type = "PPI"' in content
        assert 'lesson_version = "ppi_gold_v1"' in content

    def test_scaffold_extractor(self, tmp_src: Path, spec: ExpansionSpec) -> None:
        scaffolder = EventScaffolder(spec, src_root=tmp_src)
        path = scaffolder.scaffold_extractor()
        assert path.exists()
        content = path.read_text()
        assert "class PPIFeatureExtractor(FeatureExtractor):" in content
        assert "PPI_HIGH_THRESHOLD" in content
        assert "ppi_trend" in content

    def test_scaffold_tests(self, tmp_src: Path, spec: ExpansionSpec) -> None:
        scaffolder = EventScaffolder(spec, src_root=tmp_src)
        path = scaffolder.scaffold_tests()
        assert path.exists()
        content = path.read_text()
        assert "class TestPPIEventFeatureExtractor:" in content
        assert "class TestPPIEventTypeStrings:" in content
        assert "class TestPPIEventPipelineEndToEnd:" in content
        assert '"PPI"' in content or "'PPI'" in content

    def test_scaffold_all(self, tmp_src: Path, spec: ExpansionSpec) -> None:
        scaffolder = EventScaffolder(spec, src_root=tmp_src)
        files = scaffolder.scaffold_all(overwrite=True)
        assert len(files) == 3
        assert all(p.exists() for p in files.values())

    def test_scaffold_no_overwrite(self, tmp_src: Path, spec: ExpansionSpec) -> None:
        scaffolder = EventScaffolder(spec, src_root=tmp_src)
        path = scaffolder.scaffold_event_class()
        original = path.read_text()
        path.write_text("modified")
        result = scaffolder.scaffold_event_class(overwrite=False)
        assert result.read_text() == "modified"


# ---------------------------------------------------------------------------
# EventValidator
# ---------------------------------------------------------------------------


class TestEventValidator:
    def test_validate_nfp_passes(self) -> None:
        from knowledge.events.nfp import NFPEvent

        report = EventValidator().validate_class(NFPEvent)
        assert report.is_valid, report.summary
        assert len(report.errors) == 0

    def test_validate_cpi_passes(self) -> None:
        from knowledge.events.cpi import CPIEvent

        report = EventValidator().validate_class(CPIEvent)
        assert report.is_valid, report.summary
        assert len(report.errors) == 0

    def test_validate_broken_event(self) -> None:
        class BrokenEvent(MacroEvent):
            event_type = "BROKEN"
            lesson_version = "broken_v1"
            condition_columns = ["x"]
            knowledge_version = "broken_v1"
            def load_and_extract(self, path): raise NotImplementedError
            def build_lesson_fields(self, r, a): return {}
            def lesson_text(self, l): return "broken event lesson"

        report = EventValidator().validate_class(BrokenEvent)
        assert report.is_valid, report.summary
        assert len(report.errors) == 0

    def test_validation_report_summary(self) -> None:
        report = ValidationReport(
            event_type="TEST", class_name="TestEvent",
            passed=["p1"], warnings=["w1"], errors=[],
        )
        assert "PASS" in report.summary
        assert "TEST" in report.summary

        report.errors.append("e1")
        assert "FAIL" in report.summary


# ---------------------------------------------------------------------------
# ExpansionLifecycle
# ---------------------------------------------------------------------------


class TestExpansionLifecycle:
    def test_audit_nfp(self) -> None:
        from knowledge.events.nfp import NFPEvent

        lifecycle = ExpansionLifecycle()
        audit = lifecycle.audit(NFPEvent)
        assert isinstance(audit, ExpansionAudit)
        assert audit.spec["event_type"] == "NFP"

    def test_audit_cpi(self) -> None:
        from knowledge.events.cpi import CPIEvent

        lifecycle = ExpansionLifecycle()
        audit = lifecycle.audit(CPIEvent)
        assert isinstance(audit, ExpansionAudit)
        assert audit.spec["event_type"] == "CPI"

    def test_pipeline_readiness_checks(self) -> None:
        from knowledge.events.nfp import NFPEvent

        lifecycle = ExpansionLifecycle()
        audit = lifecycle.audit(NFPEvent)
        assert len(audit.pipeline_readiness) > 0

    def test_lifecycle_step_count(self) -> None:
        assert len(ExpansionLifecycle.STEPS) == 10

    def test_total_under_one_hour(self) -> None:
        from knowledge.events.nfp import NFPEvent

        lifecycle = ExpansionLifecycle()
        audit = lifecycle.audit(NFPEvent)
        assert audit.total_minutes <= 60, (
            f"Estimated {audit.total_minutes} min > 60 min budget"
        )

    def test_measure_event_complexity(self) -> None:
        from knowledge.events.nfp import NFPEvent

        metrics = ExpansionLifecycle.measure_event_complexity(NFPEvent)
        assert "event_class_lines" in metrics
        assert "test_file_lines" in metrics
        assert "total" in metrics
        assert metrics["total"] > 0


# ---------------------------------------------------------------------------
# End-to-end: scaffold a dummy event, validate it
# ---------------------------------------------------------------------------


def test_scaffold_and_import_end_to_end(tmp_path: Path) -> None:
    """Verify the scaffolder generates syntactically valid Python."""
    spec = ExpansionSpec(
        event_type="DUMMY",
        country="US",
        unit="index",
        importance=1,
    )
    (tmp_path / "knowledge" / "events").mkdir(parents=True)
    (tmp_path / "knowledge" / "features" / "extractors").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    scaffolder = EventScaffolder(spec, src_root=tmp_path)
    files = scaffolder.scaffold_all(overwrite=True)

    for name, path in files.items():
        content = path.read_text()
        compile(content, str(path), "exec")
        assert len(content) > 0, f"{name} is empty"


def test_scaffolder_generated_code_contains_expected_patterns(tmp_path: Path) -> None:
    spec = ExpansionSpec(
        event_type="TEST_EVENT",
        country="CA",
        unit="percent",
        source="Stats Canada",
    )
    (tmp_path / "knowledge" / "events").mkdir(parents=True)
    (tmp_path / "knowledge" / "features" / "extractors").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    scaffolder = EventScaffolder(spec, src_root=tmp_path)
    files = scaffolder.scaffold_all(overwrite=True)

    event_content = files["event_class"].read_text()
    assert "class TestEventEvent(MacroEvent):" in event_content
    assert 'event_type = "TEST_EVENT"' in event_content
    assert "CA" in event_content
    assert "Stats Canada" in event_content


def test_registry_round_trip() -> None:
    """Verify that registering and retrieving works."""
    EventRegistry.clear()
    try:
        from knowledge.events.nfp import NFPEvent

        EventRegistry.register(NFPEvent, replace=True)
        cls = EventRegistry.get("NFP")
        assert cls is NFPEvent
    finally:
        EventRegistry.clear()
        from knowledge.events.cpi import CPIEvent
        from knowledge.events.fomc import FOMCEvent
        from knowledge.events.gdp import GDPEvent
        from knowledge.events.interest_rate import InterestRateEvent
        from knowledge.events.pmi import PMIEvent
        from knowledge.events.ppi import PPIEvent
        EventRegistry.register(CPIEvent)
        EventRegistry.register(NFPEvent)
        EventRegistry.register(GDPEvent)
        EventRegistry.register(InterestRateEvent)
        EventRegistry.register(PPIEvent)
        EventRegistry.register(PMIEvent)
        EventRegistry.register(FOMCEvent)
