"""Tests for the W4 institutional signal tiering stage (src/event_triage)."""

from orchestration.stages import _event_triage, _evidence_collection
from signal_assessment.contracts import (
    ClassificationLabel,
    ClassifiedObservation,
    SignalAssessment,
)
from event_triage.contracts import SignalTiering, TierAssignment
from event_triage.tierer import SignalTierer


def _make_observation(
    obs_id: str,
    classification: str = "Signal",
    confidence: float = 0.9,
    instrument: str = "",
    source: str = "",
    reason: str = "",
    change_sigma: float = 0.0,
    change_pct: float = 0.0,
) -> ClassifiedObservation:
    return ClassifiedObservation(
        observation_id=obs_id,
        source=source,
        classification=classification,
        confidence=confidence,
        regime="NORMAL_GROWTH",
        reason=reason,
        instrument=instrument,
        change_sigma=change_sigma,
        change_pct=change_pct,
    )


def _make_assessment(
    observations: list[ClassifiedObservation],
    regime: str = "NORMAL_GROWTH",
) -> SignalAssessment:
    return SignalAssessment(
        assessment_id="tst-assess-1",
        briefing_id="brief-1",
        timestamp="2026-08-01T00:00:00Z",
        regime=regime,
        regime_confidence=0.8,
        observations=tuple(observations),
    )


def test_tier1_overriding_fomc_signal():
    obs = _make_observation(
        obs_id="obs_fomc",
        classification=ClassificationLabel.SIGNAL.value,
        confidence=0.9,
        instrument="XAUUSD",
        source="FOMC Decision",
        reason="dot plot signals higher for longer",
        change_sigma=1.8,
    )
    tiering = SignalTierer().tier(_make_assessment([obs]))
    assignment = tiering.assignments[0]
    assert assignment.tier == "Tier 1"
    assert assignment.trigger_level
    assert assignment.monitoring_frequency == "continuous"
    assert assignment.portfolio_impact > 0.7
    assert assignment.regime_relevance > 0.8


def test_tier2_important_etf_signal():
    obs = _make_observation(
        obs_id="obs_etf",
        classification=ClassificationLabel.WEAK_SIGNAL.value,
        confidence=0.55,
        instrument="GLD",
        source="ETF flows report",
        reason="sustained inflows into gold ETFs",
    )
    assignment = SignalTierer().tier_observation(obs, "NORMAL_GROWTH")
    assert assignment.tier == "Tier 2"
    assert assignment.trigger_level
    assert assignment.monitoring_frequency == "intraday"


def test_tier3_routine_low_impact():
    obs = _make_observation(
        obs_id="obs_routine",
        classification=ClassificationLabel.WATCH.value,
        confidence=0.35,
        source="generic macro feed",
        reason="routine data release",
    )
    assignment = SignalTierer().tier_observation(obs, "NORMAL_GROWTH")
    assert assignment.tier == "Tier 3"
    assert not assignment.trigger_level
    assert assignment.monitoring_frequency == "daily"


def test_tier4_filtered_noise_and_ignore():
    noise = _make_observation(
        obs_id="obs_noise",
        classification=ClassificationLabel.NOISE.value,
        confidence=0.2,
        source="noisy feed",
        reason="unstructured chatter",
    )
    ignore = _make_observation(
        obs_id="obs_ignore",
        classification=ClassificationLabel.IGNORE.value,
        confidence=0.9,
        source="ignored source",
        reason="out of scope",
    )
    tiering = SignalTierer().tier(_make_assessment([noise, ignore]))
    assert {a.observation_id: a.tier for a in tiering.assignments} == {
        "obs_noise": "Tier 4",
        "obs_ignore": "Tier 4",
    }
    assert all(not a.trigger_level for a in tiering.assignments)
    assert all(a.monitoring_frequency == "weekly" for a in tiering.assignments)


def test_every_observation_assigned_a_tier():
    observations = [
        _make_observation(obs_id=f"obs_{i}", classification=label, confidence=conf)
        for i, (label, conf) in enumerate([
            ("Signal", 0.9), ("Weak Signal", 0.55), ("Watch", 0.35),
            ("Noise", 0.2), ("Ignore", 0.9),
        ])
    ]
    tiering = SignalTierer().tier(_make_assessment(observations))
    assert len(tiering.assignments) == len(observations)
    tiers = [a.tier for a in tiering.assignments]
    assert all(t in {"Tier 1", "Tier 2", "Tier 3", "Tier 4"} for t in tiers)
    assert sum(tiering.tier_counts.values()) == len(observations)


def test_determinism_same_input_same_tiers():
    observations = [
        _make_observation(obs_id="a", classification="Signal", confidence=0.9, source="FOMC"),
        _make_observation(obs_id="b", classification="Weak Signal", confidence=0.55, source="ETF"),
        _make_observation(obs_id="c", classification="Noise", confidence=0.2, source="feed"),
    ]
    assessment = _make_assessment(observations)
    tierer = SignalTierer()
    first = tierer.tier(assessment).to_dict()
    second = tierer.tier(assessment).to_dict()
    assert first == second


def test_explainability_reason_reports_scores_and_rule():
    obs = _make_observation(
        obs_id="obs_expl",
        classification="Signal",
        confidence=0.9,
        instrument="XAUUSD",
        source="FOMC Decision",
        reason="dot plot",
    )
    assignment = SignalTierer().tier_observation(obs, "NORMAL_GROWTH")
    assert "FED/RATES" in assignment.reason
    assert "portfolio_impact" in assignment.reason
    assert "regime_relevance" in assignment.reason
    assert "price_impact" in assignment.reason
    assert "Tier 1" in assignment.reason


def test_triplet_scores_are_bounded_and_rounded():
    obs = _make_observation(
        obs_id="obs_scores",
        classification="Signal",
        confidence=0.9,
        source="FOMC",
        change_sigma=2.0,
        change_pct=8.0,
    )
    assignment = SignalTierer().tier_observation(obs, "NORMAL_GROWTH")
    for score in (assignment.portfolio_impact, assignment.regime_relevance, assignment.price_impact):
        assert 0.0 <= score <= 1.0
        assert score == round(score, 4)


def test_tier1_by_extreme_price_impact():
    obs = _make_observation(
        obs_id="obs_black_swan",
        classification="Weak Signal",
        confidence=0.5,
        source="unscheduled alert",
        reason="geopolitical escalation",
        change_sigma=2.5,
        change_pct=9.0,
    )
    assignment = SignalTierer().tier_observation(obs, "NORMAL_GROWTH")
    assert assignment.price_impact == 1.0
    assert assignment.tier == "Tier 1"
    assert "price_impact>0.9" in assignment.reason


def test_regime_boost_only_for_dominant_driver():
    obs = _make_observation(
        obs_id="obs_infl",
        classification="Signal",
        confidence=0.9,
        source="CPI release",
        reason="inflation beat expectations",
    )
    tierer = SignalTierer()
    boosted = tierer.tier_observation(obs, "INFLATION")
    plain = tierer.tier_observation(obs, "DEFLATION")
    assert boosted.regime_relevance == 0.85
    assert plain.regime_relevance == 0.75
    assert boosted.regime_relevance > plain.regime_relevance


def test_prioritized_watchlist_ordering():
    observations = [
        _make_observation(obs_id="routine", classification="Watch", confidence=0.35),
        _make_observation(obs_id="noise", classification="Noise", confidence=0.2),
        _make_observation(obs_id="overriding", classification="Signal", confidence=0.9, source="FOMC"),
        _make_observation(obs_id="important", classification="Weak Signal", confidence=0.55, source="ETF"),
    ]
    tiering = SignalTierer().tier(_make_assessment(observations))
    watchlist = tiering.prioritized_watchlist
    assert [entry["observation_id"] for entry in watchlist] == [
        "overriding", "important", "routine", "noise",
    ]
    assert all("trigger_level" in e and "monitoring_frequency" in e for e in watchlist)


def test_tiering_roundtrip():
    observations = [_make_observation(obs_id="a", classification="Signal", confidence=0.9)]
    tiering = SignalTierer().tier(_make_assessment(observations))
    restored = SignalTiering.from_dict(tiering.to_dict())
    assert restored == tiering


def test_validate_flags_invalid_tiers_and_missing_triggers():
    bad = SignalTiering(
        tiering_id="t",
        assessment_id="a",
        timestamp="now",
        regime="NORMAL_GROWTH",
        assignments=(
            TierAssignment(
                observation_id="x",
                tier="Tier 9",
                classification="Signal",
                confidence=0.9,
                instrument="",
                portfolio_impact=2.0,
                regime_relevance=0.5,
                price_impact=0.1,
                reason="r",
            ),
            TierAssignment(
                observation_id="y",
                tier="Tier 1",
                classification="Signal",
                confidence=0.9,
                instrument="",
                portfolio_impact=0.8,
                regime_relevance=0.9,
                price_impact=0.1,
                reason="r",
                trigger_level="",
            ),
        ),
    )
    errors = bad.validate()
    assert any("invalid tier" in e for e in errors)
    assert any("requires a trigger level" in e for e in errors)


def test_stage_with_dict_input():
    assessment = _make_assessment(
        [_make_observation(obs_id="a", classification="Signal", confidence=0.9, source="FOMC")]
    )
    result = _event_triage({}, {"signal_assessment": assessment.to_dict()})
    assert isinstance(result, SignalTiering)
    assert result.assignments[0].tier == "Tier 1"


def test_stage_without_assessment_returns_error():
    result = _event_triage({}, {})
    assert isinstance(result, dict)
    assert "error" in result
    assert result["assignments"] == []


def test_evidence_collection_receives_tiering_metadata():
    assessment = _make_assessment(
        [
            _make_observation(obs_id="a", classification="Signal", confidence=0.9, source="FOMC"),
            _make_observation(obs_id="b", classification="Noise", confidence=0.2, source="feed"),
        ]
    )
    tiering = _event_triage({}, {"signal_assessment": assessment.to_dict()})
    results = {
        "signal_assessment": assessment.to_dict(),
        "event_triage": tiering.to_dict(),
    }
    collection = _evidence_collection({}, results)
    tier_info = collection.metadata.get("event_tiering")
    assert tier_info is not None
    assert tier_info["tiering_id"] == tiering.tiering_id
    assert tier_info["tier_counts"]["tier1"] >= 1
    assert tier_info["tiers"]["a"] == "Tier 1"
    assert tier_info["tiers"]["b"] == "Tier 4"


def test_evidence_collection_backward_compatible_without_tiering():
    assessment = _make_assessment(
        [_make_observation(obs_id="a", classification="Signal", confidence=0.9, source="FOMC")]
    )
    collection = _evidence_collection({}, {"signal_assessment": assessment.to_dict()})
    assert "event_tiering" not in collection.metadata
    assert collection.evidence_count > 0
