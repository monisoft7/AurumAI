from datetime import datetime, timezone

import pytest

from knowledge.factors.contracts import (
    BIAS_BEARISH,
    BIAS_BULLISH,
    BIAS_NEUTRAL,
    MECHANISM_OPPORTUNITY_COST,
    FactorSignal,
)
from knowledge.integrity.provenance import Provenance
from knowledge.reasoning.rules.gold_rule_001 import (
    ASSESSMENT_MIXED,
    ASSESSMENT_STRONG_BEARISH,
    ASSESSMENT_STRONG_BULLISH,
    InstitutionalAssessment,
    apply,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _make_signal(
    factor_id: str = "real_yield_10y",
    bias: str = BIAS_NEUTRAL,
    strength: float = 0.0,
    confidence: float = 0.75,
    observation_date: str = "2026-07-28",
) -> FactorSignal:
    return FactorSignal(
        factor_id=factor_id,
        observation_date=observation_date,
        value=2.0,
        z_score=0.5,
        percentile=0.6,
        direction="rising",
        influence_bias=bias,
        influence_strength=strength,
        mechanism=MECHANISM_OPPORTUNITY_COST,
        data_quality="high",
        confidence=confidence,
    )


def _make_ry(
    bias: str = BIAS_NEUTRAL,
    strength: float = 0.0,
    confidence: float = 0.75,
    observation_date: str = "2026-07-28",
) -> FactorSignal:
    return _make_signal("real_yield_10y", bias, strength, confidence, observation_date)


def _make_dxy(
    bias: str = BIAS_NEUTRAL,
    strength: float = 0.0,
    confidence: float = 0.75,
    observation_date: str = "2026-07-28",
) -> FactorSignal:
    return _make_signal("us_dollar_index", bias, strength, confidence, observation_date)


# ── InstitutionalAssessment contract ──────────────────────────────────


class TestInstitutionalAssessmentContract:
    def test_creation_with_all_fields(self) -> None:
        assessment = InstitutionalAssessment(
            assessment_id="test_001",
            rule_id="gold_rule_001",
            observation_date="2026-07-28",
            composite_bias=ASSESSMENT_STRONG_BULLISH,
            composite_strength=0.5,
            composite_confidence=0.85,
            signal_dispersion=0.0,
            input_signals=(_make_ry(), _make_dxy()),
            explanation="Test assessment.",
            provenance=Provenance(
                created_at="2026-07-28T12:00:00Z",
                created_by="test.v1",
                entity_version="1.0.0",
            ),
        )
        assert assessment.assessment_id == "test_001"
        assert assessment.rule_id == "gold_rule_001"
        assert assessment.composite_bias == ASSESSMENT_STRONG_BULLISH
        assert assessment.composite_strength == 0.5
        assert assessment.composite_confidence == 0.85
        assert assessment.signal_dispersion == 0.0
        assert len(assessment.input_signals) == 2
        assert isinstance(assessment.provenance, Provenance)

    def test_default_fields(self) -> None:
        assessment = InstitutionalAssessment(
            assessment_id="test_002",
            rule_id="gold_rule_001",
            observation_date="2026-07-28",
            composite_bias=ASSESSMENT_MIXED,
            composite_strength=0.0,
            composite_confidence=0.5,
            signal_dispersion=0.0,
        )
        assert assessment.input_signals == ()
        assert assessment.explanation == ""
        assert assessment.provenance is None
        assert assessment.metadata == {}

    def test_frozen_dataclass(self) -> None:
        assessment = InstitutionalAssessment(
            assessment_id="test_003",
            rule_id="gold_rule_001",
            observation_date="2026-07-28",
            composite_bias=ASSESSMENT_STRONG_BULLISH,
            composite_strength=0.5,
            composite_confidence=0.85,
            signal_dispersion=0.0,
        )
        with pytest.raises((TypeError, AttributeError)):
            assessment.composite_bias = "changed"  # type: ignore[misc]

    def test_input_signals_are_frozen_tuple(self) -> None:
        signals = (_make_ry(), _make_dxy())
        assessment = InstitutionalAssessment(
            assessment_id="test_004",
            rule_id="gold_rule_001",
            observation_date="2026-07-28",
            composite_bias=ASSESSMENT_STRONG_BULLISH,
            composite_strength=0.5,
            composite_confidence=0.85,
            signal_dispersion=0.0,
            input_signals=signals,
        )
        assert isinstance(assessment.input_signals, tuple)
        with pytest.raises(TypeError):
            assessment.input_signals[0] = None  # type: ignore[index]

    def test_metadata_is_frozen(self) -> None:
        assessment = InstitutionalAssessment(
            assessment_id="test_005",
            rule_id="gold_rule_001",
            observation_date="2026-07-28",
            composite_bias=ASSESSMENT_MIXED,
            composite_strength=0.0,
            composite_confidence=0.5,
            signal_dispersion=0.0,
            metadata={"key": "value"},
        )
        with pytest.raises(TypeError):
            assessment.metadata["key"] = "changed"  # type: ignore[index]

    def test_invalid_bias_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid composite_bias"):
            InstitutionalAssessment(
                assessment_id="bad",
                rule_id="gold_rule_001",
                observation_date="2026-07-28",
                composite_bias="invalid_bias",
                composite_strength=0.0,
                composite_confidence=0.5,
                signal_dispersion=0.0,
            )


# ── apply function: validation ────────────────────────────────────────


class TestApplyValidation:
    def test_raises_on_non_factor_signal(self) -> None:
        with pytest.raises(TypeError, match="Expected FactorSignal"):
            apply("not_a_signal", _make_dxy())  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="Expected FactorSignal"):
            apply(_make_ry(), None)  # type: ignore[arg-type]

    def test_returns_institutional_assessment(self) -> None:
        result = apply(_make_ry(), _make_dxy())
        assert isinstance(result, InstitutionalAssessment)


# ── apply function: both bullish ──────────────────────────────────────


class TestBothBullish:
    def test_both_bullish_returns_strong_bullish(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=0.4, confidence=0.80),
            _make_dxy(bias=BIAS_BULLISH, strength=0.6, confidence=0.90),
        )
        assert result.composite_bias == ASSESSMENT_STRONG_BULLISH

    def test_composite_strength_is_average(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=0.4, confidence=0.80),
            _make_dxy(bias=BIAS_BULLISH, strength=0.6, confidence=0.90),
        )
        assert result.composite_strength == pytest.approx(0.5)

    def test_confidence_is_max(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=0.4, confidence=0.80),
            _make_dxy(bias=BIAS_BULLISH, strength=0.6, confidence=0.90),
        )
        assert result.composite_confidence == 0.90

    def test_dispersion_is_zero(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=0.4, confidence=0.80),
            _make_dxy(bias=BIAS_BULLISH, strength=0.6, confidence=0.90),
        )
        assert result.signal_dispersion == 0.0

    def test_explanation_contains_reinforcing(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=0.4, confidence=0.80),
            _make_dxy(bias=BIAS_BULLISH, strength=0.5, confidence=0.90),
        )
        assert "reinforcing the bullish case" in result.explanation
        assert "Both factors are bullish" in result.explanation


# ── apply function: both bearish ──────────────────────────────────────


class TestBothBearish:
    def test_both_bearish_returns_strong_bearish(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BEARISH, strength=-0.5, confidence=0.85),
            _make_dxy(bias=BIAS_BEARISH, strength=-0.3, confidence=0.70),
        )
        assert result.composite_bias == ASSESSMENT_STRONG_BEARISH

    def test_composite_strength_is_average_of_negatives(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BEARISH, strength=-0.5, confidence=0.85),
            _make_dxy(bias=BIAS_BEARISH, strength=-0.3, confidence=0.70),
        )
        assert result.composite_strength == pytest.approx(-0.4)

    def test_confidence_is_max(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BEARISH, strength=-0.5, confidence=0.85),
            _make_dxy(bias=BIAS_BEARISH, strength=-0.3, confidence=0.70),
        )
        assert result.composite_confidence == 0.85

    def test_dispersion_is_zero(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BEARISH, strength=-0.5, confidence=0.85),
            _make_dxy(bias=BIAS_BEARISH, strength=-0.3, confidence=0.70),
        )
        assert result.signal_dispersion == 0.0

    def test_explanation_contains_reinforcing(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BEARISH, strength=-0.5, confidence=0.85),
            _make_dxy(bias=BIAS_BEARISH, strength=-0.4, confidence=0.70),
        )
        assert "reinforcing the bearish case" in result.explanation
        assert "Both factors are bearish" in result.explanation


# ── apply function: conflict ──────────────────────────────────────────


class TestConflict:
    def test_opposing_signals_returns_mixed(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=0.5, confidence=0.80),
            _make_dxy(bias=BIAS_BEARISH, strength=-0.5, confidence=0.80),
        )
        assert result.composite_bias == ASSESSMENT_MIXED

    def test_bullish_vs_neutral_returns_mixed(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=0.5, confidence=0.80),
            _make_dxy(bias=BIAS_NEUTRAL, strength=0.0, confidence=0.70),
        )
        assert result.composite_bias == ASSESSMENT_MIXED

    def test_bearish_vs_neutral_returns_mixed(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BEARISH, strength=-0.3, confidence=0.80),
            _make_dxy(bias=BIAS_NEUTRAL, strength=0.0, confidence=0.70),
        )
        assert result.composite_bias == ASSESSMENT_MIXED

    def test_both_neutral_returns_mixed(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_NEUTRAL, strength=0.0, confidence=0.60),
            _make_dxy(bias=BIAS_NEUTRAL, strength=0.0, confidence=0.60),
        )
        assert result.composite_bias == ASSESSMENT_MIXED

    def test_conflict_confidence_is_halved(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=0.5, confidence=0.80),
            _make_dxy(bias=BIAS_BEARISH, strength=-0.3, confidence=0.70),
        )
        expected = ((0.80 + 0.70) / 2.0) * 0.5
        assert result.composite_confidence == pytest.approx(expected)

    def test_dispersion_is_non_zero_on_conflict(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=0.5, confidence=0.80),
            _make_dxy(bias=BIAS_BEARISH, strength=-0.3, confidence=0.70),
        )
        expected_dispersion = abs(0.5 - (-0.3)) / 2.0
        assert result.signal_dispersion == pytest.approx(expected_dispersion)

    def test_explanation_contains_conflict(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=0.5, confidence=0.80),
            _make_dxy(bias=BIAS_BEARISH, strength=-0.5, confidence=0.80),
        )
        assert "in conflict" in result.explanation
        assert "reducing conviction" in result.explanation

    def test_composite_strength_is_still_average(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=0.8, confidence=0.80),
            _make_dxy(bias=BIAS_BEARISH, strength=-0.4, confidence=0.70),
        )
        assert result.composite_strength == pytest.approx(0.2)


# ── apply function: metadata ──────────────────────────────────────────


class TestMetadata:
    def test_rule_id(self) -> None:
        result = apply(_make_ry(), _make_dxy())
        assert result.rule_id == "gold_rule_001"

    def test_assessment_id_includes_date(self) -> None:
        result = apply(
            _make_ry(observation_date="2026-07-28"),
            _make_dxy(observation_date="2026-07-28"),
        )
        assert "2026-07-28" in result.assessment_id

    def test_assessment_id_includes_factor_ids(self) -> None:
        result = apply(
            _make_ry(observation_date="2026-07-28"),
            _make_dxy(observation_date="2026-07-28"),
        )
        assert "real_yield_10y" in result.assessment_id
        assert "us_dollar_index" in result.assessment_id

    def test_observation_date_is_latest(self) -> None:
        result = apply(
            _make_ry(observation_date="2026-07-27"),
            _make_dxy(observation_date="2026-07-28"),
        )
        assert result.observation_date == "2026-07-28"

    def test_observation_date_uses_first_if_second_empty(self) -> None:
        ry = _make_ry(observation_date="2026-07-28")
        dxy = _make_dxy(observation_date="")
        result = apply(ry, dxy)
        assert result.observation_date == "2026-07-28"

    def test_provenance_created(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=0.5, confidence=0.80),
            _make_dxy(bias=BIAS_BULLISH, strength=0.5, confidence=0.80),
        )
        assert isinstance(result.provenance, Provenance)
        assert result.provenance.created_by == "gold_rule_001.v1"
        assert result.provenance.entity_version == "1.0.0"

    def test_provenance_timestamp_is_utc_iso(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=0.5, confidence=0.80),
            _make_dxy(bias=BIAS_BULLISH, strength=0.5, confidence=0.80),
        )
        dt = datetime.fromisoformat(result.provenance.created_at)
        assert dt.tzinfo is not None

    def test_input_signals_preserved(self) -> None:
        ry = _make_ry(bias=BIAS_BULLISH, strength=0.5, confidence=0.80)
        dxy = _make_dxy(bias=BIAS_BEARISH, strength=-0.3, confidence=0.70)
        result = apply(ry, dxy)
        assert result.input_signals[0] is ry
        assert result.input_signals[1] is dxy

    def test_explanation_includes_both_signals(self) -> None:
        ry = _make_ry(bias=BIAS_BULLISH, strength=0.4, confidence=0.80)
        dxy = _make_dxy(bias=BIAS_BEARISH, strength=-0.6, confidence=0.70)
        result = apply(ry, dxy)
        assert "Real Yield" in result.explanation
        assert "DXY" in result.explanation
        assert "bullish" in result.explanation
        assert "bearish" in result.explanation


# ── apply function: numeric edge cases ────────────────────────────────


class TestNumericEdgeCases:
    def test_zero_strengths(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_NEUTRAL, strength=0.0, confidence=0.50),
            _make_dxy(bias=BIAS_NEUTRAL, strength=0.0, confidence=0.50),
        )
        assert result.composite_strength == 0.0
        assert result.composite_bias == ASSESSMENT_MIXED

    def test_symmetric_strengths_cancel(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=0.5, confidence=0.80),
            _make_dxy(bias=BIAS_BEARISH, strength=-0.5, confidence=0.80),
        )
        assert result.composite_strength == pytest.approx(0.0)

    def test_extreme_strengths_bounded(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=1.0, confidence=0.95),
            _make_dxy(bias=BIAS_BULLISH, strength=1.0, confidence=0.95),
        )
        assert result.composite_strength == pytest.approx(1.0)
        assert result.composite_confidence == pytest.approx(0.95)

    def test_extreme_negative_strengths_bounded(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BEARISH, strength=-1.0, confidence=0.95),
            _make_dxy(bias=BIAS_BEARISH, strength=-1.0, confidence=0.95),
        )
        assert result.composite_strength == pytest.approx(-1.0)
        assert result.composite_confidence == pytest.approx(0.95)

    def test_conflict_dispersion_capped(self) -> None:
        result = apply(
            _make_ry(bias=BIAS_BULLISH, strength=1.0, confidence=0.80),
            _make_dxy(bias=BIAS_BEARISH, strength=-1.0, confidence=0.80),
        )
        assert result.signal_dispersion == pytest.approx(1.0)
