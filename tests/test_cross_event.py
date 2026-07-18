from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.evidence import Evidence
from knowledge.orchestration.context import OrchestrationContext
from knowledge.orchestration.engine import OrchestrationEngine, OrchestrationReport
from knowledge.reasoning.cross_event import (
    AgreementPair,
    CrossEventAnalyzer,
    CrossEventResult,
)


def _ev(
    event_type: str,
    bias: str = "gold_positive_bias",
    confidence: float = 0.7,
    evidence_id: str | None = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id or f"{event_type}_{bias}_{id}",
        source_node_id=f"{event_type}_node",
        event_type=event_type,
        condition={},
        horizon_days=20,
        sample_count=50,
        average_return_pct=0.5,
        confidence=confidence,
        bias=bias,
        explanation="",
    )


# --------------------------------------------------------------------------
# Dataclass tests
# --------------------------------------------------------------------------


class TestCrossEventResult:

    def test_is_frozen(self) -> None:
        r = CrossEventResult(event_type_groups={})
        with pytest.raises((AttributeError, TypeError)):
            r.overall_consensus = "agreement"  # type: ignore[misc]


class TestAgreementPair:

    def test_is_frozen(self) -> None:
        p = AgreementPair(
            event_type_a="CPI",
            event_type_b="NFP",
            agreement="agreement",
            agreement_score=0.9,
            a_avg_confidence=0.7,
            b_avg_confidence=0.8,
            a_positive_ratio=0.8,
            b_positive_ratio=0.9,
            a_negative_ratio=0.1,
            b_negative_ratio=0.1,
        )
        with pytest.raises((AttributeError, TypeError)):
            p.agreement = "conflict"  # type: ignore[misc]


# --------------------------------------------------------------------------
# CrossEventAnalyzer tests
# --------------------------------------------------------------------------


class TestCrossEventAnalyzerSingleEventType:

    def test_returns_insufficient_for_single_type(self) -> None:
        coll = EvidenceCollection([_ev("CPI"), _ev("CPI")])
        result = CrossEventAnalyzer().analyze(coll)
        assert result.overall_consensus == "insufficient"

    def test_returns_insufficient_for_empty(self) -> None:
        coll = EvidenceCollection()
        result = CrossEventAnalyzer().analyze(coll)
        assert result.overall_consensus == "insufficient"

    def test_single_type_no_pairwise(self) -> None:
        coll = EvidenceCollection([_ev("CPI")])
        result = CrossEventAnalyzer().analyze(coll)
        assert len(result.pairwise_agreements) == 0

    def test_single_type_conflict_message(self) -> None:
        coll = EvidenceCollection([_ev("CPI")])
        result = CrossEventAnalyzer().analyze(coll)
        assert len(result.conflicts) == 1
        assert "CPI" in result.conflicts[0]


class TestCrossEventAnalyzerAgreement:

    def test_both_positive_detects_agreement(self) -> None:
        coll = EvidenceCollection([
            _ev("CPI", "gold_positive_bias", 0.7),
            _ev("CPI", "gold_positive_bias", 0.8),
            _ev("NFP", "gold_positive_bias", 0.6),
            _ev("NFP", "gold_positive_bias", 0.9),
        ])
        result = CrossEventAnalyzer().analyze(coll)
        assert result.overall_consensus in ("strong_agreement", "agreement")
        assert len(result.pairwise_agreements) == 1
        pair = result.pairwise_agreements[0]
        assert pair.agreement in ("agreement", "weak_agreement")

    def test_both_negative_detects_agreement(self) -> None:
        coll = EvidenceCollection([
            _ev("CPI", "gold_negative_bias", 0.7),
            _ev("CPI", "gold_negative_bias", 0.8),
            _ev("NFP", "gold_negative_bias", 0.6),
            _ev("NFP", "gold_negative_bias", 0.9),
        ])
        result = CrossEventAnalyzer().analyze(coll)
        assert result.overall_consensus in ("strong_agreement", "agreement")

    def test_high_confidence_agreement_score(self) -> None:
        coll = EvidenceCollection([
            _ev("CPI", "gold_positive_bias", 0.9),
            _ev("NFP", "gold_positive_bias", 0.95),
        ])
        result = CrossEventAnalyzer().analyze(coll)
        assert result.consensus_confidence > 0.5


class TestCrossEventAnalyzerConflict:

    def test_positive_vs_negative_detects_conflict(self) -> None:
        coll = EvidenceCollection([
            _ev("CPI", "gold_positive_bias", 0.7),
            _ev("CPI", "gold_positive_bias", 0.8),
            _ev("DXY", "gold_negative_bias", 0.6),
            _ev("DXY", "gold_negative_bias", 0.9),
        ])
        result = CrossEventAnalyzer().analyze(coll)
        assert result.overall_consensus in ("conflict", "mixed")
        assert len(result.conflicts) >= 1

    def test_conflict_message_format(self) -> None:
        coll = EvidenceCollection([
            _ev("CPI", "gold_positive_bias", 0.7),
            _ev("DXY", "gold_negative_bias", 0.6),
        ])
        result = CrossEventAnalyzer().analyze(coll)
        if result.conflicts:
            msg = result.conflicts[0]
            assert "CPI" in msg
            assert "DXY" in msg
            assert "%+" in msg
            assert "%-" in msg


class TestCrossEventAnalyzerMixed:

    def test_mixed_signals(self) -> None:
        coll = EvidenceCollection([
            _ev("CPI", "gold_positive_bias", 0.7),
            _ev("NFP", "mixed_or_context_dependent", 0.5),
        ])
        result = CrossEventAnalyzer().analyze(coll)
        assert len(result.pairwise_agreements) == 1
        pair = result.pairwise_agreements[0]
        assert pair.agreement == "mixed"

    def test_three_types_two_agree_one_conflict(self) -> None:
        coll = EvidenceCollection([
            _ev("CPI", "gold_positive_bias", 0.7),
            _ev("NFP", "gold_positive_bias", 0.8),
            _ev("DXY", "gold_negative_bias", 0.6),
        ])
        result = CrossEventAnalyzer().analyze(coll)
        assert len(result.pairwise_agreements) == 3
        assert result.overall_consensus is not None


class TestCrossEventAnalyzerGroupBy:

    def test_groups_by_event_type(self) -> None:
        coll = EvidenceCollection([
            _ev("CPI"),
            _ev("CPI"),
            _ev("NFP"),
        ])
        result = CrossEventAnalyzer().analyze(coll)
        assert set(result.event_type_groups.keys()) == {"CPI", "NFP"}
        assert len(result.event_type_groups["CPI"]) == 2
        assert len(result.event_type_groups["NFP"]) == 1

    def test_three_event_types(self) -> None:
        coll = EvidenceCollection([
            _ev("CPI"),
            _ev("NFP"),
            _ev("DXY"),
        ])
        result = CrossEventAnalyzer().analyze(coll)
        assert len(result.pairwise_agreements) == 3
        pair_types = {(p.event_type_a, p.event_type_b) for p in result.pairwise_agreements}
        assert ("CPI", "DXY") in pair_types
        assert ("CPI", "NFP") in pair_types
        assert ("DXY", "NFP") in pair_types


# --------------------------------------------------------------------------
# Orchestration integration tests
# --------------------------------------------------------------------------


class TestOrchestrationContextEventTypes:

    def test_defaults_to_none(self) -> None:
        ctx = OrchestrationContext()
        assert ctx.event_types is None
        assert ctx.event_type == "CPI"

    def test_can_set_multiple_types(self) -> None:
        ctx = OrchestrationContext(event_types=("CPI", "NFP"))
        assert ctx.event_types == ("CPI", "NFP")

    def test_backward_compatible(self) -> None:
        ctx = OrchestrationContext(event_type="CPI")
        assert ctx.event_type == "CPI"
        assert ctx.event_types is None


class TestOrchestrationReportCrossEvent:

    def test_defaults_to_none(self) -> None:
        report = OrchestrationReport()
        assert report.cross_event_result is None

    def test_can_set_cross_event_result(self) -> None:
        result = CrossEventResult(event_type_groups={})
        report = OrchestrationReport(cross_event_result=result)
        assert report.cross_event_result is result


class TestOrchestrationEngineMultiEvent:

    def test_run_core_queries_multiple_types(self) -> None:
        ctx = OrchestrationContext(
            event_type="CPI",
            event_types=("CPI", "NFP"),
        )
        assert ctx.event_types == ("CPI", "NFP")

    def test_run_core_falls_back_to_single_type(self) -> None:
        ctx = OrchestrationContext(event_type="CPI")
        engine = OrchestrationEngine()
        result = engine._run_core(ctx)
        assert isinstance(result, EvidenceCollection)


# --------------------------------------------------------------------------
# End-to-end integration tests
# --------------------------------------------------------------------------


class TestCrossEventFullIntegration:

    def test_analyzer_with_real_evidence_pattern(self) -> None:
        cpi_ev = [
            _ev("CPI", "gold_positive_bias", 0.7, "cpi_1"),
            _ev("CPI", "gold_positive_bias", 0.8, "cpi_2"),
        ]
        nfp_ev = [
            _ev("NFP", "gold_positive_bias", 0.6, "nfp_1"),
            _ev("NFP", "gold_positive_bias", 0.75, "nfp_2"),
        ]
        coll = EvidenceCollection(cpi_ev + nfp_ev)
        result = CrossEventAnalyzer().analyze(coll)
        assert result.overall_consensus in ("strong_agreement", "agreement")
        assert result.consensus_confidence > 0.0

    def test_analyzer_with_opposing_signals(self) -> None:
        cpi_ev = [
            _ev("CPI", "gold_positive_bias", 0.8, "cpi_1"),
            _ev("CPI", "gold_positive_bias", 0.7, "cpi_2"),
        ]
        dxy_ev = [
            _ev("DXY", "gold_negative_bias", 0.75, "dxy_1"),
            _ev("DXY", "gold_negative_bias", 0.65, "dxy_2"),
        ]
        coll = EvidenceCollection(cpi_ev + dxy_ev)
        result = CrossEventAnalyzer().analyze(coll)
        assert result.overall_consensus in ("conflict", "mixed")
        assert len(result.conflicts) >= 1

    def test_analyzer_with_three_way_signals(self) -> None:
        coll = EvidenceCollection([
            _ev("CPI", "gold_positive_bias", 0.7, "cpi_1"),
            _ev("NFP", "gold_positive_bias", 0.8, "nfp_1"),
            _ev("DXY", "gold_negative_bias", 0.6, "dxy_1"),
            _ev("US10Y", "gold_negative_bias", 0.65, "yield_1"),
        ])
        result = CrossEventAnalyzer().analyze(coll)
        assert len(result.pairwise_agreements) == 6
        assert len(result.event_type_groups) == 4

    def test_analyzer_with_mixed_confidence(self) -> None:
        coll = EvidenceCollection([
            _ev("CPI", "gold_positive_bias", 0.95, "cpi_high"),
            _ev("CPI", "gold_positive_bias", 0.9, "cpi_high2"),
            _ev("NFP", "gold_positive_bias", 0.5, "nfp_low"),
            _ev("NFP", "gold_positive_bias", 0.55, "nfp_low2"),
        ])
        result = CrossEventAnalyzer().analyze(coll)
        assert result.overall_consensus in ("strong_agreement", "agreement")
        assert result.consensus_confidence > 0.0

    def test_single_type_via_analyzer_never_crashes(self) -> None:
        coll = EvidenceCollection([
            _ev("CPI", "gold_positive_bias", 0.7, "cpi_1"),
        ])
        result = CrossEventAnalyzer().analyze(coll)
        assert result.overall_consensus == "insufficient"


import pytest
