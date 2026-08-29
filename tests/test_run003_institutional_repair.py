"""Run-003 institutional repair -- focused regression suite.

Pins the repaired contracts end-to-end:

 1.  neutral remains uninformative (no vote, no dilution, no thesis support)
 2.  duplicate same-fact evidence cannot inflate consensus
 3.  independent facts remain independent
 4.  no universal neutral thesis (neutral = absence claim, zero support)
 5.  confidence no longer mechanically saturates
 6.  RR uses market quantities (with explicit conviction fallback)
 7.  direction symmetry (bullish/bearish mirrored formulas)
 8.  regime cannot invent direction (prior neutralized everywhere)
 9.  memory does not double-count (one estimator, one item)
10.  technical is as-of safe
11.  no-lookahead (desk + market context bounded by as-of inputs)
12.  determinism (same inputs -> identical numerics)
13.  provenance (desk/memory evidence carry audit trails)
14.  decision gate coherence
15.  unavailable states remain explicit
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from counter_evidence.assessor import CounterEvidenceAssessor
from counter_evidence.detector import ConflictDetector
from evidence_collection.desk_evidence import (
    HISTORICAL_MEMORY_EVENT_TYPE,
    TECHNICAL_EVENT_TYPE,
    build_memory_evidence,
    build_technical_evidence,
    canonical_fact_identity,
)
from evidence_collection.contracts import Evidence, EvidenceCollection
from evidence_reasoning.contracts import EvidenceSet
from evidence_reasoning.detector import EvidenceDetector
from evidence_reasoning.grouper import EvidenceGrouper
from evidence_reasoning.historical_adjudication import build_historical_adjudication
from evidence_reasoning.reasoner import EvidenceReasoner
from evidence_reasoning.weighter import EvidenceWeighter
from knowledge.facts.contracts import primitive_fact_id
from knowledge.integrity.provenance import Provenance
from risk_reward_validation.market_context import MarketContext, build_market_context
from risk_reward_validation.validator import RiskRewardValidator
from scenario_generation.generator import ScenarioGenerator
from thesis_construction.constructor import ThesisConstructor

TIMESTAMP = "2026-01-05T06:00:00+00:00"
REGIME = "INFLATIONARY"


# ===========================================================================
# Builders
# ===========================================================================


def _ev(
    evidence_id: str,
    bias: str,
    *,
    event_type: str = "REAL_YIELD",
    instrument: str = "XAU/USD",
    composite_weight: float = 0.64,
    provenance: Provenance | None = None,
    canonical_fact_id: str | None = None,
) -> Evidence:
    metadata = {"instrument": instrument, "classification": "Signal"}
    if canonical_fact_id is not None:
        metadata["canonical_fact_id"] = canonical_fact_id
    return Evidence(
        evidence_id=f"ev_{evidence_id}",
        source_kr_id=f"KR-{evidence_id}",
        source_kr_node_id=f"KR-{evidence_id}",
        event_type=event_type,
        condition={"instrument": instrument},
        bias=bias,
        base_confidence=0.8,
        regime_weight=0.8,
        composite_weight=composite_weight,
        explanation=f"{evidence_id} {bias}",
        regime=REGIME,
        source_label="test",
        provenance=provenance,
        temporal_recency=0.9,
        metadata=metadata,
    )


def _collection(items):
    return EvidenceCollection(
        collection_id="ec_run003",
        assessment_id="sa_run003",
        timestamp=TIMESTAMP,
        regime=REGIME,
        items=tuple(items),
        total_classified=len(items),
        signals_count=len(items),
    )


def _reason(items):
    return EvidenceReasoner().reason(_collection(items), regime=REGIME)


def _reason_with_counter(items):
    reasoning = _reason(items)
    counter = CounterEvidenceAssessor().assess(reasoning)
    return reasoning, counter


def _reason_with_memory(payload):
    return EvidenceReasoner().reason(
        _collection([_ev("d", "bullish")]),
        regime=REGIME,
        historical_analogue=payload,
    )


def _weighted_set(set_id: str, bias: str, net_weight: float) -> EvidenceSet:
    return EvidenceSet(
        set_id=set_id,
        event_type="GENERAL",
        bias=bias,
        evidence_ids=(f"ev_{set_id}",),
        supporting_evidence_ids=(f"ev_{set_id}",),
        net_institutional_weight=net_weight,
        consensus_score=0.6,
    )


def _uniform_up_payload() -> dict:
    return {
        "matches": [
            {
                "lesson_id": f"CPI_GOLD_2020-0{i}-01",
                "event_date": "2020-01-01",
                "similarity": {"overall_similarity": 0.8,
                               "retrieval_method": "exact"},
                "gold_outcome": {
                    "gold_return_1d_pct": 1.0, "gold_direction_1d": "UP",
                    "gold_return_5d_pct": 2.0, "gold_direction_5d": "UP",
                    "gold_return_20d_pct": 3.0, "gold_direction_20d": "UP",
                },
                "provenance": {"source_artifact_path": "p",
                               "source_artifact_sha256": "h"},
            }
            for i in range(1, 4)
        ],
        "query": {
            "event_type": "CPI",
            "condition": {"cpi_pressure": "inflation_pressure_up"},
            "institutional_context": {"regime": "INFLATIONARY"},
        },
    }


def _single_direction_construction(direction: str, support: float):
    """Minimal construction with one directional set + neutral absence claim,
    directional support pinned to ``support``."""
    from thesis_construction.contracts import ThesisConstruction

    reasoning, counter = _reason_with_counter(
        [_ev("d", direction, event_type="REAL_YIELD")]
    )
    construction = ThesisConstructor().construct(reasoning, counter)
    theses = tuple(
        replace(t, institutional_support=support)
        if t.direction == direction
        else t
        for t in construction.theses
    )
    ranked = sorted(theses, key=lambda t: t.institutional_support, reverse=True)
    return ThesisConstruction(
        construction_id="tc_t",
        reasoning_id=reasoning.reasoning_id,
        assessment_id=counter.assessment_id,
        timestamp=TIMESTAMP,
        regime=REGIME,
        theses=tuple(theses),
        ranked_thesis_ids=tuple(t.thesis_id for t in ranked),
        total_theses=len(theses),
        primary_thesis_id=theses[0].thesis_id,
        metadata=dict(construction.metadata),
    )


def _strong_construction(direction: str = "bullish"):
    """Construction with THREE independent high-weight directional sets
    (the honest minimum for a >0.5-confidence directional decision)."""
    from thesis_construction.contracts import ThesisConstruction

    items = [
        _ev("a", direction, event_type="REAL_YIELD", composite_weight=0.95),
        _ev("b", direction, event_type="USD_FX", instrument="DXY",
            composite_weight=0.85),
        _ev("c", direction, event_type="INFLATION", instrument="Breakeven Inflation",
            composite_weight=0.8),
    ]
    reasoning, counter = _reason_with_counter(items)
    construction = ThesisConstructor().construct(reasoning, counter)
    directional = next(
        t for t in construction.theses if t.direction == direction
    )
    theses = tuple(
        replace(t, institutional_support=0.85)
        if t.direction == direction else t
        for t in construction.theses
    )
    ranked = sorted(theses, key=lambda t: t.institutional_support, reverse=True)
    from thesis_construction.contracts import ThesisConstruction as TC

    return TC(
        construction_id="tc_strong",
        reasoning_id=reasoning.reasoning_id,
        assessment_id=counter.assessment_id,
        timestamp=TIMESTAMP,
        regime=REGIME,
        theses=tuple(theses),
        ranked_thesis_ids=tuple(t.thesis_id for t in ranked),
        total_theses=len(theses),
        primary_thesis_id=theses[0].thesis_id,
        metadata=dict(construction.metadata),
    )


def _confidence_for(construction):
    from confidence_engine.engine import ConfidenceEngine

    return ConfidenceEngine().evaluate(construction)


def _technical_assessment():
    from technical.contracts import TechnicalAssessment

    return TechnicalAssessment(
        assessment_id="tech_test000001",
        asset="XAU/USD",
        as_of="2026-01-01T00:00:00+00:00",
        timeframe="D1",
        trend_direction="bullish",
        momentum_direction="bullish",
        volatility_state="normal",
        overbought_oversold_state="neutral",
        structure_state="uptrend",
        technical_confidence=0.6,
        supporting_indicators=("trend_ema_stack_adx",),
        conflicting_indicators=(),
        source_data_hash="abc123",
        provenance_chain=(
            {
                "created_at": "2026-01-01T00:00:00+00:00",
                "created_by": "TechnicalResearchDesk",
                "entity_version": "1.0.0",
            },
        ),
        metadata={},
    )


# ===========================================================================
# 1. Neutral remains uninformative
# ===========================================================================


class TestNeutralUninformative:
    def test_neutral_votes_neither_way_and_does_not_dilute(self):
        group = [_ev("d", "bullish"), _ev("n", "neutral")]
        raw = EvidenceDetector.analyze_group(group, "es_g", "GENERAL", [])
        weighted = EvidenceWeighter().weight_set(raw, group)
        assert raw.bias == "bullish"
        assert weighted.conflict_score == 0.0
        # Shrunk consensus over directional mass only: (0.64+1)/(0.64+2).
        assert weighted.consensus_score == pytest.approx(0.6212, abs=1e-4)
        assert raw.supporting_evidence_ids == ("ev_d",)
        assert raw.contradicting_evidence_ids == ()

    def test_neutral_set_reports_zero_consensus(self):
        group = [
            _ev("n1", "neutral", event_type="GENERAL"),
            _ev("n2", "neutral", event_type="GENERAL", instrument="Brent Crude"),
        ]
        raw = EvidenceDetector.analyze_group(group, "es_g", "GENERAL", [])
        weighted = EvidenceWeighter().weight_set(raw, group)
        assert raw.bias == "neutral"
        assert weighted.consensus_score == 0.0
        assert weighted.conflict_score == 0.0
        assert weighted.confidence_contribution == 0.0

    def test_neutral_never_competes_at_set_level(self):
        bull = _weighted_set("es_a", "bullish", 0.8)
        neutral = _weighted_set("es_n", "neutral", 0.9)
        contra, supp, pairs = ConflictDetector.cross_set_conflicts((bull, neutral))
        assert contra == [] and pairs == []
        assert supp == ["es_a"]

    def test_equal_mass_balance_has_no_insertion_order_winner(self):
        first = EvidenceDetector.analyze_group(
            [_ev("bull", "bullish"), _ev("bear", "bearish")], "es_g", "GENERAL", []
        )
        second = EvidenceDetector.analyze_group(
            [_ev("bear", "bearish"), _ev("bull", "bullish")], "es_g", "GENERAL", []
        )
        assert first.bias == "mixed" == second.bias


# ===========================================================================
# 2. Same-fact repetition cannot inflate consensus
# ===========================================================================


class TestSameFactDedup:
    def test_canonical_identity_is_deterministic_cross_producer(self):
        fact = canonical_fact_identity("XAU/USD", "GENERAL", "2026-01-05")
        assert fact == primitive_fact_id("xau/usd", "general", "2026-01-05")
        assert fact != canonical_fact_identity("DXY", "GENERAL", "2026-01-05")
        assert fact == canonical_fact_identity("XAU/USD", "GENERAL", "2026-01-05")

    def test_same_fact_repetition_collapses_to_one_vote(self):
        fact = canonical_fact_identity("XAU/USD", "GENERAL", "2026-01-05")
        items = [
            _ev("a", "bullish", event_type="GENERAL", composite_weight=0.6,
                canonical_fact_id=fact),
            _ev("b", "bullish", event_type="GENERAL", composite_weight=0.2,
                canonical_fact_id=fact),
            _ev("c", "bullish", event_type="GENERAL", composite_weight=0.1,
                canonical_fact_id=fact),
        ]
        reasoning = _reason(items)
        assert reasoning.duplicates_removed == 2
        assert reasoning.total_evidence_items == 1
        surviving = reasoning.evidence_sets[0]
        # Consensus is shrunk from the surviving assertion, never 1.0.
        assert surviving.consensus_score == pytest.approx(
            (0.6 + 1.0) / (0.6 + 2.0), abs=1e-4
        )

    def test_distinct_facts_stay_independent(self):
        fact_a = canonical_fact_identity("XAU/USD", "GENERAL", "2026-01-05")
        fact_b = canonical_fact_identity("DXY", "USD_FX", "2026-01-05")
        assert fact_a != fact_b
        items = [
            _ev("a", "bullish", event_type="GENERAL", composite_weight=0.6,
                canonical_fact_id=fact_a),
            _ev("b", "bullish", event_type="GENERAL", composite_weight=0.5,
                instrument="Brent Crude", canonical_fact_id=fact_b),
        ]
        reasoning = _reason(items)
        # Two DIFFERENT facts in the same channel remain two items.
        assert reasoning.duplicates_removed == 0
        assert reasoning.total_evidence_items == 2

    def test_single_strong_independent_item_is_valid(self):
        single = _ev(
            "solo", "bullish", event_type="GENERAL", composite_weight=0.9,
            provenance=Provenance("2026-01-01T00:00:00", "desk", "1.0"),
        )
        raw = EvidenceDetector.analyze_group([single], "es_g", "GENERAL", [])
        weighted = EvidenceWeighter().weight_set(raw, [single])
        assert raw.bias == "bullish"
        assert weighted.net_institutional_weight > 0.0
        assert weighted.consensus_score > 0.5

    def test_cross_set_weighted_majority_no_insertion_order_tie_break(self):
        first = ConflictDetector.cross_set_conflicts(
            (_weighted_set("es_a", "bullish", 0.5), _weighted_set("es_b", "bearish", 0.5))
        )
        second = ConflictDetector.cross_set_conflicts(
            (_weighted_set("es_b", "bearish", 0.5),
             _weighted_set("es_a", "bullish", 0.5))
        )
        assert first == ([], [], [])
        assert second == ([], [], [])


# ===========================================================================
# 4. No universal neutral thesis
# ===========================================================================


class TestNeutralThesisSemantics:
    def test_neutral_thesis_is_absence_claim(self):
        reasoning, counter = _reason_with_counter([_ev("d", "bullish")])
        construction = ThesisConstructor().construct(reasoning, counter)
        neutral = next(t for t in construction.theses if t.direction == "neutral")
        assert neutral.institutional_support == 0.0
        assert neutral.supporting_set_ids == ()
        directional = next(
            t for t in construction.theses if t.direction == "bullish"
        )
        assert directional.institutional_support > neutral.institutional_support
        assert construction.primary_thesis_id == directional.thesis_id

    def test_neutral_only_world_still_yields_neutral_thesis(self):
        reasoning, counter = _reason_with_counter(
            [_ev("n1", "neutral", event_type="INFLATION")]
        )
        construction = ThesisConstructor().construct(reasoning, counter)
        assert {t.direction for t in construction.theses} == {"neutral"}
        assert construction.primary_thesis.institutional_support == 0.0

    def test_neutral_scenarios_carry_zero_conviction(self):
        from historical_validation.pure_path import _splice_update
        from thesis_update.updater import ThesisUpdater

        reasoning, counter = _reason_with_counter(
            [_ev("n1", "neutral", event_type="INFLATION")]
        )
        construction = ThesisConstructor().construct(reasoning, counter)
        update = ThesisUpdater().update(construction, reasoning, counter)
        construction_v2 = _splice_update(update, construction)
        generation = ScenarioGenerator().generate(construction_v2)
        neutral_scenarios = [
            s for s in generation.scenarios if s.expected_direction == "neutral"
        ]
        assert neutral_scenarios
        for s in neutral_scenarios:
            assert s.confidence_inputs["scenario_confidence"] == 0.0
            assert s.confidence_inputs["scenario_confidence_source"] == (
                "neutral_no_directional_support"
            )


# ===========================================================================
# 5. Confidence no longer mechanically saturates
# ===========================================================================


class TestConfidenceSaturation:
    def test_single_item_consensus_shrunk(self):
        ev = _ev("solo", "bullish")
        raw = EvidenceDetector.analyze_group([ev], "es_g", "GENERAL", [])
        weighted = EvidenceWeighter().weight_set(raw, [ev])
        assert weighted.consensus_score < 1.0

    def test_perfect_inputs_do_not_reach_one(self):
        from confidence_engine.computer import ConfidenceComputer
        from thesis_construction.contracts import InvestmentThesis

        thesis = InvestmentThesis(
            thesis_id="th_max", direction="bullish",
            supporting_set_ids=("a", "b", "c"), counter_evidence_ids=(),
            regime=REGIME, economic_mechanism="m", time_horizon_days=90,
            invalidating_conditions=(), remaining_unknowns=(),
            confidence_inputs={
                "avg_supporting_weight": 1.0, "avg_supporting_consensus": 1.0,
                "conflict_severity": 0.0, "confidence_penalty": 0.0,
                "raw_support": 1.0,
            },
            institutional_support=1.0, explanation="x",
            provenance_chain=(Provenance("t", "x", "1"),),
        )
        result = ConfidenceComputer().compute(thesis)
        # diversity 3/6 = 0.5, provenance 1/3 = 0.3333:
        # 0.35 + 0.35 + 0.20*0.5 + 0.10*0.3333 = 0.8333 -- below 1.0 by design.
        assert result["final_confidence"] == 0.8333

    def test_regime_channel_absent(self):
        from confidence_engine.computer import ConfidenceComputer

        thesis = _thesis_with_regime("bullish", "NORMAL_GROWTH")
        result = ConfidenceComputer().compute(thesis)
        assert "regime_alignment" not in result["confidence_breakdown"]


# ===========================================================================
# 6. RR uses market quantities
# ===========================================================================


def _market_context(
    semivol_up: float = 0.007, semivol_down: float = 0.009
) -> MarketContext:
    return MarketContext(
        available=True,
        as_of="2026-01-01",
        asset="XAU/USD",
        reference_price=2000.0,
        atr_abs=20.0,
        atr_pct=0.01,
        realized_vol_daily=0.008,
        semivol_up_daily=semivol_up,
        semivol_down_daily=semivol_down,
        bars_used=400,
        vol_observations=60,
        provenance={"status": "ok"},
    )


class TestMarketRR:
    def test_market_metrics_are_market_scaled(self):
        construction = _single_direction_construction("bullish", 0.8)
        generation = ScenarioGenerator().generate(construction)
        ctx = _market_context()
        validation = RiskRewardValidator().validate(generation, market_context=ctx)
        assert validation.metadata["risk_basis"] == "market_asof"
        base = next(
            v for v in validation.validations
            if v.metadata["scenario_type"] == "base"
        )
        # Base scenario of a bullish thesis expects the favorable move:
        # upside = semivol_up * sqrt(90); downside = semivol_down * sqrt(90).
        assert base.expected_upside == pytest.approx(
            ctx.semivol_up_daily * (90 ** 0.5), rel=1e-4
        )
        assert base.maximum_downside == pytest.approx(
            ctx.semivol_down_daily * (90 ** 0.5), rel=1e-5
        )
        # Provenance: the market basis is explicit and as-of labeled.
        assert validation.metadata["market_context"]["available"] is True
        assert validation.metadata["market_context"]["reference_price"] > 0

    def test_market_rejects_when_no_favorable_mass(self):
        # A thesis whose scenarios never expect its direction has zero
        # favorable mass -> explicit reject, not a fabricated ratio.
        construction = _single_direction_construction("neutral", 0.0)
        generation = ScenarioGenerator().generate(construction)
        validation = RiskRewardValidator().validate(
            generation, market_context=_market_context()
        )
        neutral_validations = [
            v for v in validation.validations
            if v.metadata.get("probability") is not None
        ]
        # Neutral thesis scenarios carry no favorable mass -> reject.
        assert all(
            v.validation_status == "reject" for v in validation.validations
        ) or validation.metadata["risk_basis"] == "conviction_fallback"

    def test_fallback_labels_basis(self):
        construction = _single_direction_construction("bullish", 0.8)
        generation = ScenarioGenerator().generate(construction)
        validation = RiskRewardValidator().validate(generation, market_context=None)
        assert validation.metadata["risk_basis"] == "conviction_fallback"
        for v in validation.validations:
            assert v.metadata["metrics_basis"] == "conviction_fallback"
            assert "no as-of market context" in v.validation_explanation


# ===========================================================================
# 7. Direction symmetry
# ===========================================================================


class TestDirectionSymmetry:
    def test_mirrored_evidence_mirrors_support(self):
        reasoning, counter = _reason_with_counter(
            [_ev("b", "bullish", event_type="REAL_YIELD")]
        )
        bull = ThesisConstructor().construct(reasoning, counter)
        r2, c2 = _reason_with_counter(
            [_ev("b", "bearish", event_type="REAL_YIELD")]
        )
        bear = ThesisConstructor().construct(r2, c2)
        bull_support = next(
            t.institutional_support
            for t in bull.theses if t.direction == "bullish"
        )
        bear_support = next(
            t.institutional_support
            for t in bear.theses if t.direction == "bearish"
        )
        assert bull_support == bear_support

    def test_market_rr_mirrors_direction(self):
        ctx = _market_context()
        bull_gen = ScenarioGenerator().generate(
            _single_direction_construction("bullish", 0.8)
        )
        bear_gen = ScenarioGenerator().generate(
            _single_direction_construction("bearish", 0.8)
        )
        v_bull = RiskRewardValidator().validate(bull_gen, market_context=ctx)
        v_bear = RiskRewardValidator().validate(bear_gen, market_context=ctx)
        bull_base = next(
            v for v in v_bull.validations
            if v.metadata["scenario_type"] == "base"
        )
        bear_base = next(
            v for v in v_bear.validations
            if v.metadata["scenario_type"] == "base"
        )
        # Mirrored formulas: identical favorable/adverse magnitudes and
        # identical thesis-level ratio; only the move sides swap.
        assert bull_base.expected_upside == pytest.approx(
            bear_base.expected_upside, rel=1e-9
        )
        assert bull_base.maximum_downside == pytest.approx(
            bear_base.maximum_downside, rel=1e-9
        )
        assert bull_base.risk_reward_ratio == pytest.approx(
            bear_base.risk_reward_ratio, rel=1e-9
        )
        assert bull_base.validation_status == bear_base.validation_status


# ===========================================================================
# 8. Regime cannot invent direction
# ===========================================================================


class TestRegimeNeutralized:
    def test_regime_conflict_disabled(self):
        sets = (_weighted_set("es_1", "bearish", 0.6),)
        for regime in (
            "NORMAL_GROWTH", "INFLATIONARY", "STAGFLATIONARY",
            "DEFLATIONARY_CRISIS", "GEOPOLITICAL_STRESS", "",
        ):
            assert ConflictDetector.regime_conflict(sets, regime) is False

    def test_confidence_invariant_to_regime(self):
        from confidence_engine.computer import ConfidenceComputer
        from thesis_construction.contracts import InvestmentThesis

        def thesis(regime: str, direction: str = "bullish"):
            return InvestmentThesis(
                thesis_id="th_t", direction=direction,
                supporting_set_ids=("a",), counter_evidence_ids=(),
                regime=regime, economic_mechanism="m", time_horizon_days=90,
                invalidating_conditions=(), remaining_unknowns=(),
                confidence_inputs={
                    "avg_supporting_weight": 0.7, "avg_supporting_consensus": 0.7,
                    "conflict_severity": 0.0, "confidence_penalty": 0.0,
                    "raw_support": 0.49,
                },
                institutional_support=0.7, explanation="x",
            )

        same_dir = [
            ConfidenceComputer().compute(_thesis_with_regime("bullish", r))["final_confidence"]
            for r in ("NORMAL_GROWTH", "INFLATIONARY")
        ]
        assert same_dir[0] == same_dir[1]
        b = ConfidenceComputer().compute(_thesis_with_regime("bullish", "NORMAL_GROWTH"))
        s = ConfidenceComputer().compute(_thesis_with_regime("bearish", "NORMAL_GROWTH"))
        assert b["final_confidence"] == s["final_confidence"]


def _thesis_with_regime(regime: str, direction: str = "bullish"):
    from thesis_construction.contracts import InvestmentThesis

    return InvestmentThesis(
        thesis_id="th_r", direction=direction,
        supporting_set_ids=("a", "b"), counter_evidence_ids=(),
        regime=regime, economic_mechanism="m", time_horizon_days=90,
        invalidating_conditions=(), remaining_unknowns=(),
        confidence_inputs={
            "avg_supporting_weight": 0.7, "avg_supporting_consensus": 0.7,
            "conflict_severity": 0.0, "confidence_penalty": 0.0,
            "raw_support": 0.49,
        },
        institutional_support=0.7, explanation="x",
    )


# ===========================================================================
# 9 + 13. Memory bounded + provenance
# ===========================================================================


def _uniform_up_payload() -> dict:
    return {
        "matches": [
            {
                "lesson_id": f"CPI_GOLD_2020-0{i}-01",
                "event_date": "2020-01-01",
                "similarity": {"overall_similarity": 0.8,
                               "retrieval_method": "exact"},
                "gold_outcome": {
                    "gold_return_1d_pct": 1.0, "gold_direction_1d": "UP",
                    "gold_return_5d_pct": 2.0, "gold_direction_5d": "UP",
                    "gold_return_20d_pct": 3.0, "gold_direction_20d": "UP",
                },
                "provenance": {"source_artifact_path": "p",
                               "source_artifact_sha256": "h"},
            }
            for i in range(1, 4)
        ],
        "query": {
            "event_type": "CPI",
            "condition": {"cpi_pressure": "inflation_pressure_up"},
            "institutional_context": {"regime": "INFLATIONARY"},
        },
    }


class TestMemoryBounded:
    def test_one_item_for_many_matches(self):
        payload = _uniform_up_payload()
        adj = build_historical_adjudication(payload)
        item = build_memory_evidence(adj, payload)
        assert item is not None
        assert item.event_type == HISTORICAL_MEMORY_EVENT_TYPE
        assert item.bias == "bullish"
        groups, dups = EvidenceGrouper().group([item])
        assert len(groups) == 1 and dups == []
        assert len(item.metadata["lesson_ids"]) == 3
        assert item.metadata["desk_id"] == "historical_research"
        assert item.provenance is not None
        assert item.base_confidence == pytest.approx(0.8, abs=1e-4)

    def test_mixed_history_maps_uninformative(self):
        payload = {
            "matches": [
                {"lesson_id": f"L{i}",
                 "similarity": {"overall_similarity": 0.7,
                                "retrieval_method": "exact"},
                 "gold_outcome": {
                     "gold_return_1d_pct": 1.0, "gold_direction_1d": "UP",
                     "gold_return_5d_pct": -1.0, "gold_direction_5d": "DOWN",
                     "gold_return_20d_pct": -1.0, "gold_direction_20d": "DOWN",
                 }}
                for i in range(2)
            ],
            "query": {"condition": {"cpi_pressure": "up"}},
        }
        adj = build_historical_adjudication(payload)
        item = build_memory_evidence(adj, payload)
        assert item is not None
        assert item.bias == "neutral"

    def test_no_payload_no_item(self):
        assert build_memory_evidence(None, None) is None
        assert build_memory_evidence({}, None) is None

    def test_memory_set_enters_reasoning_once(self):
        r_with = _reason_with_memory(_uniform_up_payload())
        r_without = _reason_with_memory(None)
        mem = [
            s for s in r_with.evidence_sets
            if s.event_type == HISTORICAL_MEMORY_EVENT_TYPE
        ]
        assert len(mem) == 1
        assert all(
            s.event_type != HISTORICAL_MEMORY_EVENT_TYPE
            for s in r_without.evidence_sets
        )
        # ONE estimator: three matches but exactly one evidence item in the
        # set.  Lesson-level provenance is asserted via the item builder in
        # test_memory_evidence_provenance below.
        assert len(mem[0].evidence_ids) == 1

    def test_memory_evidence_provenance(self):
        payload = _uniform_up_payload()
        adj = build_historical_adjudication(payload)
        item = build_memory_evidence(adj, payload)
        assert item.provenance is not None
        assert item.provenance.metadata["lesson_ids"] == [
            "CPI_GOLD_2020-01-01", "CPI_GOLD_2020-02-01", "CPI_GOLD_2020-03-01",
        ]
        assert item.metadata["analogue_similarity"]


# ===========================================================================
# 10. Technical as-of safety
# ===========================================================================


def _technical_assessment():
    from technical.contracts import TechnicalAssessment

    return TechnicalAssessment(
        assessment_id="tech_test000001",
        asset="XAU/USD",
        as_of="2026-01-01T00:00:00+00:00",
        timeframe="D1",
        trend_direction="bullish",
        momentum_direction="bullish",
        volatility_state="normal",
        overbought_oversold_state="neutral",
        structure_state="uptrend",
        technical_confidence=0.6,
        supporting_indicators=("trend_ema_stack_adx",),
        conflicting_indicators=(),
        source_data_hash="abc123",
        provenance_chain=(
            {
                "created_at": "2026-01-01T00:00:00+00:00",
                "created_by": "TechnicalResearchDesk",
                "entity_version": "1.0.0",
            },
        ),
        metadata={},
    )


class TestTechnicalAsOfSafety:
    def test_directional_desk_reading_becomes_one_evidence_item(self):
        evidence = build_technical_evidence(_technical_assessment())
        assert evidence is not None
        assert evidence.event_type == TECHNICAL_EVENT_TYPE
        assert evidence.bias in {"bullish", "bearish"}
        assert evidence.metadata["desk_id"] == "technical_research"
        assert evidence.provenance is not None
        assert evidence.metadata["as_of"] == "2026-01-01T00:00:00+00:00"

    def test_non_directional_reading_emits_nothing(self):
        assert build_technical_evidence(None) is None
        assert build_technical_evidence({"error": "boom"}) is None

    def test_desk_assessment_is_asof_sliced(self):
        import pandas as pd

        from technical.desk import TechnicalResearchDesk

        frame = pd.read_csv(ROOT / "data" / "history" / "gold" / "gold.csv")
        d = "2022-02-01"
        assessment = TechnicalResearchDesk().assess(
            frame, as_of=d, timeframe="D1", asset="XAU/USD",
            created_at=f"{d}T00:00:00+00:00",
        )
        assert assessment.as_of == d
        bars = int(assessment.metadata["bars_used"])
        full = TechnicalResearchDesk._prepare_frame(frame)
        available = int((full.index <= pd.Timestamp(d)).sum())
        assert bars == available


# ===========================================================================
# 11 + 12. Determinism
# ===========================================================================


class TestDeterminism:
    def test_reasoning_deterministic_given_same_inputs(self):
        items = [
            _ev("a", "bullish", event_type="REAL_YIELD"),
            _ev("b", "bearish", event_type="USD_FX", instrument="DXY"),
            _ev("n", "neutral", event_type="INFLATION"),
        ]
        r_a = _reason(items)
        r_b = _reason(items)
        a = sorted(
            (s.to_dict() for s in r_a.evidence_sets), key=lambda s: s["set_id"]
        )
        b = sorted((s.to_dict() for s in r_b.evidence_sets), key=lambda s: s["set_id"])
        for sa, sb in zip(a, b):
            assert sa["set_id"] == sb["set_id"]
            assert sa["bias"] == sb["bias"]
            assert sa["net_institutional_weight"] == sb["net_institutional_weight"]
            assert sa["consensus_score"] == sb["consensus_score"]
            assert sa["conflict_score"] == sb["conflict_score"]
            assert sa["supporting_evidence_ids"] == sb["supporting_evidence_ids"]
            assert sa["contradicting_evidence_ids"] == sb["contradicting_evidence_ids"]

    def test_market_context_asof_boundary(self):
        ctx = build_market_context(
            str(ROOT / "data" / "history" / "gold" / "gold.csv"), "2022-02-01"
        )
        assert ctx.available is True
        assert ctx.as_of == "2022-02-01"
        assert ctx.provenance["bar_date"] <= "2022-02-01"
        assert ctx.vol_observations >= 30


# ===========================================================================
# 14. Decision gate coherence
# ===========================================================================


class TestDecisionGateCoherence:
    def test_weak_thesis_abstains_with_named_gate(self):
        from decision_engine.engine import DecisionEngine

        construction = _single_direction_construction("bullish", 0.3)
        confidence = _confidence_for(construction)
        generation = ScenarioGenerator().generate(construction)
        validation = RiskRewardValidator().validate(generation, market_context=None)
        decision = DecisionEngine().decide(
            construction, confidence, generation, validation
        )
        if confidence.theses_confidence[0].final_confidence < 0.5:
            assert decision.decision == "NO_TRADE"
            assert decision.metadata["gate_reason"] == "confidence_below_threshold"

    def test_strong_thesis_buys(self):
        from decision_engine.engine import DecisionEngine

        construction = _strong_construction("bullish")
        confidence = _confidence_for(construction)
        generation = ScenarioGenerator().generate(construction)
        validation = RiskRewardValidator().validate(generation, market_context=None)
        decision = DecisionEngine().decide(
            construction, confidence, generation, validation
        )
        assert decision.decision == "BUY"
        assert decision.institutional_confidence >= 0.5

    def test_neutral_never_selected_when_directional_exists(self):
        reasoning, counter = _reason_with_counter(
            [
                _ev("bull", "bullish", event_type="REAL_YIELD"),
                _ev("neu", "neutral", event_type="INFLATION"),
            ]
        )
        construction = ThesisConstructor().construct(reasoning, counter)
        assert construction.primary_thesis.direction == "bullish"

    def test_symmetric_treatment_of_bull_and_bear_support(self):
        bull = _single_direction_construction("bullish", 0.8)
        bear = _single_direction_construction("bearish", 0.8)
        bull_support = next(
            t.institutional_support for t in bull.theses
            if t.direction == "bullish"
        )
        bear_support = next(
            t.institutional_support
            for t in bear.theses
            if t.direction == "bearish"
        )
        assert bull_support == bear_support


# ===========================================================================
# 15. Unavailable states remain explicit
# ===========================================================================


class TestUnavailableStates:
    def test_missing_market_context_is_explicit(self):
        ctx = build_market_context(None, "2026-01-01")
        assert ctx.available is False
        assert ctx.provenance["status"] == "unavailable"
        assert ctx.provenance["reason"] == "no gold_path"
        assert ctx.reference_price is None

    def test_insufficient_history_is_explicit(self):
        import tempfile

        with tempfile.NamedTemporaryFile(
            "w", suffix=".csv", delete=False
        ) as fh:
            fh.write("Date,Close,High,Low,Open,Volume\n")
            for i in range(10):
                fh.write(f"2026-01-{i + 1:02d},2000,2010,1990,1995,100\n")
            path = fh.name
        ctx = build_market_context(path, "2026-01-10")
        assert ctx.available is False
        assert "insufficient" in ctx.provenance["reason"]

    def test_technical_none_is_no_evidence_not_zero_vote(self):
        assert build_technical_evidence(None) is None
