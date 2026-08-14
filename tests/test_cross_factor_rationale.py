"""Trace 016-B: explanation-only cross-factor rationale (Gold Rule 001).

Real Yield + DXY FactorSignals (existing adapters) are combined by the
existing gold_rule_001 rule into a deterministic rationale carried in
``reasoning.metadata["factor_rationale"]`` and composed into the thesis
explanation by ThesisBuilder (W8) and recomposed by ThesisUpdater (W10).

All assertions verify the rationale is:
- deterministic (identical inputs -> identical rationale),
- honest about data quality (stale inputs are marked, never presented as
  current; missing inputs omit the chunk),
- purely explanatory (no scoring field changes).
"""

import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from counter_evidence.contracts import CounterEvidenceAssessment
from evidence_collection.collector import EvidenceCollector
from evidence_reasoning.cross_factor_rationale import build_cross_factor_rationale
from evidence_reasoning.contracts import EvidenceReasoning
from evidence_reasoning.reasoner import EvidenceReasoner
from knowledge.graph.builder import GraphBuilder
from test_evidence_collection import (
    _cpi_semantics_records,
    _make_assessment,
    _make_observation,
)
from thesis_construction.builder import ThesisBuilder
from thesis_construction.contracts import ThesisConstruction
from thesis_update.updater import ThesisUpdater


def _write_series(path: Path, dates: list[str], values: list[float]) -> None:
    path.write_text(
        "Date,Value\n"
        + "".join(f"{d},{v}\n" for d, v in zip(dates, values)),
        encoding="utf-8",
    )


def _fresh_dates(count: int = 60) -> list[str]:
    today = date.today()
    return [(today - timedelta(days=count - 1 - i)).isoformat() for i in range(count)]


def _stale_dates(count: int = 60) -> list[str]:
    return [
        (date.today() - timedelta(days=250) + timedelta(days=i)).isoformat()
        for i in range(count)
    ]


def _values(count: int = 60) -> list[float]:
    return [round(2.0 + 0.01 * i, 4) for i in range(count)]


def _collect_and_reason() -> EvidenceReasoning:
    obs = _make_observation(
        obs_id="obs_016b_cpi",
        classification="Signal",
        confidence=0.8,
        instrument="Breakeven Inflation",
        evidence_count=3,
    )
    assessment = _make_assessment([obs])
    kg = GraphBuilder().build(_cpi_semantics_records())
    collection = EvidenceCollector(knowledge_graph=kg).collect(
        assessment,
        regime_weight=0.8,
        cpi_condition={"cpi_pressure": "inflation_pressure_up"},
    )
    return EvidenceReasoner().reason(collection)


def _make_assessment_for(
    reasoning: EvidenceReasoning, supporting_set_id: str
) -> CounterEvidenceAssessment:
    return CounterEvidenceAssessment(
        assessment_id="cea_016b",
        reasoning_id=reasoning.reasoning_id,
        timestamp="2026-08-14T00:00:00",
        regime=reasoning.regime,
        related_set_ids=(supporting_set_id,),
        supporting_set_ids=(supporting_set_id,),
        contradicting_set_ids=(),
        conflict_severity=0.0,
        confidence_penalty=0.0,
        regime_conflict=False,
        bias_flags=(),
    )


def _make_construction(
    thesis, reasoning_id: str, assessment_id: str
) -> ThesisConstruction:
    return ThesisConstruction(
        construction_id="construction_016b",
        reasoning_id=reasoning_id,
        assessment_id=assessment_id,
        timestamp="2026-08-14T00:00:00",
        regime=thesis.regime,
        theses=(thesis,),
        ranked_thesis_ids=(thesis.thesis_id,),
        total_theses=1,
        primary_thesis_id=thesis.thesis_id,
    )


class TestCrossFactorRationale:
    def test_fresh_inputs_produce_deterministic_ok_rationale(self, tmp_path):
        ry = tmp_path / "DFII10.csv"
        dx = tmp_path / "dxy.csv"
        _write_series(ry, _fresh_dates(), _values())
        _write_series(dx, _fresh_dates(), [v + 50.0 for v in _values()])

        first = build_cross_factor_rationale(ry, dx)
        second = build_cross_factor_rationale(ry, dx)

        assert first is not None
        assert second == first
        assert first["rule_id"] == "gold_rule_001"
        assert first["status"] == "ok"
        assert first["observation_date"] == date.today().isoformat()
        for key in (
            "composite_bias", "composite_strength", "composite_confidence",
            "signal_dispersion", "explanation",
        ):
            assert key in first
        assert len(first["factors"]) == 2
        for factor in first["factors"]:
            assert factor["status"] == "current"
            assert factor["data_quality"] == "high"
            assert factor["factor_id"] in ("real_yield_10y", "us_dollar_index")

    def test_stale_dxy_is_marked_stale_not_current(self, tmp_path):
        ry = tmp_path / "DFII10.csv"
        dx = tmp_path / "dxy.csv"
        _write_series(ry, _fresh_dates(), _values())
        stale_dates = _stale_dates()
        _write_series(dx, stale_dates, [v + 50.0 for v in _values()])

        rationale = build_cross_factor_rationale(ry, dx)

        assert rationale is not None
        assert rationale["status"] == "stale"
        dxy_entry = next(
            f for f in rationale["factors"] if f["factor_id"] == "us_dollar_index"
        )
        assert dxy_entry["status"] == "stale"
        assert dxy_entry["data_quality"] == "stale"
        note = rationale["freshness_note"]
        assert "us_dollar_index" in note
        assert stale_dates[-1] in note
        assert "stale - not a current observation" in note
        ry_entry = next(
            f for f in rationale["factors"] if f["factor_id"] == "real_yield_10y"
        )
        assert ry_entry["status"] == "current"

    def test_missing_input_omits_rationale(self, tmp_path):
        ry = tmp_path / "DFII10.csv"
        missing = tmp_path / "missing.csv"
        _write_series(ry, _fresh_dates(), _values())

        assert build_cross_factor_rationale(ry, missing) is None
        assert build_cross_factor_rationale(missing, ry) is None
        assert build_cross_factor_rationale(missing, missing) is None

    def test_default_paths_resolve_and_produce_rationale(self):
        rationale = build_cross_factor_rationale()
        assert rationale is not None
        assert rationale["rule_id"] == "gold_rule_001"
        assert len(rationale["factors"]) == 2


class TestReasonerMetadata:
    def test_reasoner_attaches_factor_rationale_metadata(self):
        reasoning = _collect_and_reason()
        assert "factor_rationale" in reasoning.metadata
        rationale = reasoning.metadata["factor_rationale"]
        assert rationale["rule_id"] == "gold_rule_001"
        assert rationale["composite_bias"] in (
            "strong_bullish", "strong_bearish", "mixed",
        )

    def test_reasoner_rationale_is_deterministic(self):
        first = _collect_and_reason()
        second = _collect_and_reason()
        assert first.metadata["factor_rationale"] == second.metadata["factor_rationale"]

    def test_roundtrip_preserves_factor_rationale(self):
        reasoning = _collect_and_reason()
        raw = json.dumps(reasoning.to_dict())
        restored = EvidenceReasoning.from_dict(json.loads(raw))
        assert restored.metadata["factor_rationale"] == (
            reasoning.metadata["factor_rationale"]
        )


class TestExplanationComposition:
    def test_builder_composes_factor_chunk_into_explanation(self):
        reasoning = _collect_and_reason()
        kr_sets = [
            s for s in reasoning.evidence_sets
            if "knowledge_rationale" in s.metadata
        ]
        supporting = kr_sets or list(reasoning.evidence_sets)
        assessment = _make_assessment_for(reasoning, supporting[0].set_id)
        thesis = ThesisBuilder().build_thesis(
            "bullish", reasoning, assessment,
            [s.set_id for s in supporting], [],
        )
        assert "factor: gold_rule_001" in thesis.explanation
        assert "bias=" in thesis.explanation
        assert "knowledge:" in thesis.explanation

    def test_builder_without_factor_rationale_unchanged(self):
        reasoning = _collect_and_reason()
        plain_reasoning = replace(
            reasoning,
            metadata={
                k: v for k, v in reasoning.metadata.items()
                if k != "factor_rationale"
            },
        )
        assert "factor_rationale" not in plain_reasoning.metadata

        supporting = list(reasoning.evidence_sets)
        assessment = _make_assessment_for(reasoning, supporting[0].set_id)
        plain_thesis = ThesisBuilder().build_thesis(
            "bullish", plain_reasoning, assessment,
            [s.set_id for s in supporting], [],
        )
        rich_thesis = ThesisBuilder().build_thesis(
            "bullish", reasoning, assessment,
            [s.set_id for s in supporting], [],
        )

        assert "factor: gold_rule_001" not in plain_thesis.explanation
        assert "factor: gold_rule_001" in rich_thesis.explanation
        expected_chunk = ThesisBuilder._compose_factor_rationale(reasoning)
        assert rich_thesis.explanation == plain_thesis.explanation + (
            f" | {expected_chunk}"
        )

    def test_updater_preserves_factor_chunk(self):
        reasoning = _collect_and_reason()
        supporting = list(reasoning.evidence_sets)
        assessment = _make_assessment_for(reasoning, supporting[0].set_id)
        thesis = ThesisBuilder().build_thesis(
            "bullish", reasoning, assessment,
            [s.set_id for s in supporting], [],
        )
        update = ThesisUpdater().update(
            _make_construction(
                thesis, reasoning.reasoning_id, assessment.assessment_id
            ),
            reasoning,
            assessment,
        )
        assert "factor: gold_rule_001" in update.updated_thesis.explanation
        assert "knowledge:" in update.updated_thesis.explanation
        assert "UPDATED v2" in update.updated_thesis.explanation


class TestNumericInertness:
    def test_factor_rationale_does_not_change_any_numeric_field(self):
        reasoning = _collect_and_reason()
        plain_reasoning = replace(
            reasoning,
            metadata={
                k: v for k, v in reasoning.metadata.items()
                if k != "factor_rationale"
            },
        )
        supporting = list(reasoning.evidence_sets)
        assessment = _make_assessment_for(reasoning, supporting[0].set_id)

        plain = ThesisBuilder().build_thesis(
            "bullish", plain_reasoning, assessment,
            [s.set_id for s in supporting], [],
        )
        rich = ThesisBuilder().build_thesis(
            "bullish", reasoning, assessment,
            [s.set_id for s in supporting], [],
        )

        assert rich.institutional_support == plain.institutional_support
        assert rich.confidence_inputs == plain.confidence_inputs
        assert rich.invalidating_conditions == plain.invalidating_conditions
        assert rich.remaining_unknowns == plain.remaining_unknowns
        assert rich.time_horizon_days == plain.time_horizon_days
        assert rich.economic_mechanism == plain.economic_mechanism
        assert rich.regime == plain.regime
        assert rich.supporting_set_ids == plain.supporting_set_ids
        assert rich.counter_evidence_ids == plain.counter_evidence_ids

        plain_update = ThesisUpdater().update(
            _make_construction(
                plain, plain_reasoning.reasoning_id, assessment.assessment_id
            ),
            plain_reasoning,
            assessment,
        )
        rich_update = ThesisUpdater().update(
            _make_construction(
                rich, reasoning.reasoning_id, assessment.assessment_id
            ),
            reasoning,
            assessment,
        )
        assert rich_update.confidence_delta == plain_update.confidence_delta
        assert rich_update.action == plain_update.action
        assert rich_update.trigger_type == plain_update.trigger_type
        assert rich_update.changed_assumptions == plain_update.changed_assumptions
        assert (
            rich_update.updated_thesis.institutional_support
            == plain_update.updated_thesis.institutional_support
        )