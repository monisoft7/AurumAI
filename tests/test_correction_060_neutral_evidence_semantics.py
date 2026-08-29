"""Correction 060 -- Neutral / Uninformative Evidence Semantics.

Trace 059 found that the reasoning/aggregation layer treated evidence with
``bias=neutral`` as *conflicting* against any directional majority, while
News Intelligence 058 defines neutral as "no proven directional polarity".

This suite pins the corrected semantics:

* SUPPORTING    -- evidence whose bias matches the thesis direction.
* CONTRADICTING -- evidence with proven opposite polarity (or mixed against
  a directional majority; mixed carries bidirectional signal and is out of
  this correction's scope).
* UNINFORMATIVE -- neutral evidence exists but votes neither way.

Fixtures reuse the Trace 058 headline corpus and the Trace 059 evidence
shapes (W5 collector -> W6 reasoner -> W7 assessor path).
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

from counter_evidence.analyzer import BiasAnalyzer
from counter_evidence.assessor import CounterEvidenceAssessor
from counter_evidence.detector import ConflictDetector
from evidence_collection.contracts import Evidence, EvidenceCollection
from evidence_reasoning.contracts import EvidenceSet
from evidence_reasoning.detector import EvidenceDetector
from evidence_reasoning.weighter import EvidenceWeighter
from knowledge.integrity.provenance import Provenance  # noqa: F401 (fixture parity)
from news.intelligence import (
    DIRECTION_BULLISH,
    DIRECTION_UNKNOWN,
    classify_article,
)
from thesis_construction.constructor import ThesisConstructor


SRC = Path(__file__).resolve().parents[1] / "src"


# ===========================================================================
# Fixtures (Trace 058/059 shapes)
# ===========================================================================


def _ev(
    evidence_id: str,
    bias: str,
    event_type: str = "GENERAL",
    kr: str | None = None,
    composite_weight: float = 0.64,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_kr_id=kr or f"KR-{evidence_id}",
        source_kr_node_id=kr or f"KR-{evidence_id}",
        event_type=event_type,
        condition={"instrument": "XAU/USD"},
        bias=bias,
        base_confidence=0.8,
        regime_weight=0.8,
        composite_weight=composite_weight,
        explanation=f"{bias} evidence",
        regime="NORMAL_GROWTH",
        source_label="overnight_price",
        temporal_recency=0.9,
        metadata={"instrument": "XAU/USD", "classification": "Signal"},
    )


def _collection(*items: Evidence) -> EvidenceCollection:
    return EvidenceCollection(
        collection_id="ec_c060",
        assessment_id="sa_c060",
        timestamp="2026-08-25T06:00:00+00:00",
        regime="NORMAL_GROWTH",
        items=tuple(items),
        total_classified=len(items),
        signals_count=len(items),
    )


def _reason(evidence: list[Evidence]):
    from evidence_reasoning.reasoner import EvidenceReasoner

    collection = _collection(*evidence)
    reasoning = EvidenceReasoner().reason(collection)
    assessment = CounterEvidenceAssessor().assess(reasoning)
    return reasoning, assessment


# ===========================================================================
# 1 + 2. Neutral / unknown evidence never becomes contradicting
# ===========================================================================


class TestNeutralNeverContradicting:
    def test_1_neutral_item_not_contradicting(self):
        # Trace 059 fixture: one directional item + one news-derived neutral
        # item in the same channel.
        group = [_ev("ev_bull", "bullish"), _ev("ev_neutral", "neutral")]
        result = EvidenceDetector.analyze_group(group, "es_general", "GENERAL", [])
        assert result.bias == "bullish"
        assert result.supporting_evidence_ids == ("ev_bull",)
        assert result.contradicting_evidence_ids == ()

    def test_1_weighter_conflict_zero_for_neutral(self):
        group = [_ev("ev_bull", "bullish"), _ev("ev_neutral", "neutral")]
        raw_set = EvidenceDetector.analyze_group(group, "es_general", "GENERAL", [])
        weighted = EvidenceWeighter().weight_set(raw_set, group)
        assert weighted.conflict_score == 0.0

    def test_2_unknown_news_direction_collects_neutral_and_stays_uncontradicted(self):
        # Producer side: Trace 058 intentionally-unknown headlines carry no
        # polarity; when such observations reach the reasoning layer they are
        # neutral evidence and must not register as dissent.
        cls = classify_article("USD strengthened after hawkish Fed remarks")
        assert cls["directional_implication"] == DIRECTION_UNKNOWN

        group = [
            _ev("ev_cb_gold", "bullish", "CB_GOLD"),
            _ev("ev_news_unknown", "neutral", "CB_GOLD"),
        ]
        result = EvidenceDetector.analyze_group(group, "es_cbgold", "CB_GOLD", [])
        assert "ev_news_unknown" not in result.contradicting_evidence_ids
        weighted = EvidenceWeighter().weight_set(result, group)
        assert weighted.conflict_score == 0.0

    def test_2_neutral_set_not_in_contradicting_set_ids(self):
        # Set level: a neutral-majority set against a bullish majority across
        # sets is uninformative, not contradicting.
        contra, supp, pairs = ConflictDetector.cross_set_conflicts(
            (
                _set("es_real", "bullish"),
                _set("es_news", "neutral", "GENERAL"),
            )
        )
        assert contra == []
        assert pairs == []
        assert supp == ["es_real"]


# ===========================================================================
# 3 + 4. Directional + neutral stays non-conflicting in both polarities
# ===========================================================================


class TestDirectionalPlusNeutralNoConflict:
    @pytest.mark.parametrize("directional_bias", ["bullish", "bearish"])
    def test_directional_plus_neutral_has_zero_conflict(self, directional_bias):
        group = [_ev("ev_dir", directional_bias), _ev("ev_neu", "neutral")]
        raw_set = EvidenceDetector.analyze_group(group, "es_general", "GENERAL", [])
        weighted = EvidenceWeighter().weight_set(raw_set, group)
        assert weighted.conflict_score == 0.0
        # Run-003 repair supersedes the Correction-060 dilution note:
        # uninformative evidence neither supports, opposes, NOR dilutes --
        # consensus is the Beta(1,1)-shrunk directional agreement over the
        # directional mass only: (0.64+1)/(0.64+2) = 0.6212.
        assert weighted.consensus_score == round((0.64 + 1.0) / (0.64 + 2.0), 4)
        # And it is listed in neither id list.
        assert raw_set.contradicting_evidence_ids == ()
        assert raw_set.supporting_evidence_ids == ("ev_dir",)

    def test_w7_assessment_no_conflict_for_bullish_plus_neutral_sets(self):
        reasoning, assessment = _reason(
            [
                _ev("ev_rY_bull", "bullish", "REAL_YIELD"),
                _ev("ev_usd_neu", "neutral", "USD_FX"),
            ]
        )
        biases = {s.bias for s in reasoning.evidence_sets}
        assert biases == {"bullish", "neutral"}
        assert assessment.contradicting_set_ids == ()
        assert "cross_set_conflict" not in assessment.bias_flags
        # Conflict-driven penalty mass must be zero (regime/missing flags may
        # add their own fixed units; here neither applies).
        assert assessment.conflict_severity == 0.0
        assert assessment.confidence_penalty == 0.0


# ===========================================================================
# 5. True directional opposition still conflicts
# ===========================================================================


class TestBullishBearishStillConflicts:
    def test_item_level_conflict_preserved(self):
        # Run-003 repair: set direction is the weighted-mass direction.
        # With equal masses an opposing pair is genuinely balanced (mixed);
        # a mass-dominant side makes the opposite item contradicting.
        group = [
            _ev("ev_bull", "bullish", composite_weight=0.8),
            _ev("ev_bear", "bearish", composite_weight=0.6),
        ]
        raw_set = EvidenceDetector.analyze_group(group, "es_general", "GENERAL", [])
        weighted = EvidenceWeighter().weight_set(raw_set, group)
        assert raw_set.bias == "bullish"
        assert weighted.consensus_score == round((0.8 + 1.0) / (1.4 + 2.0), 4)
        assert weighted.conflict_score == round(0.6 / 1.4, 4)
        assert raw_set.contradicting_evidence_ids == ("ev_bear",)

    def test_exact_mass_balance_is_mixed_not_insertion_order(self):
        # Run-003 repair: no insertion-order tie-breaking.  Equal-weight
        # opposition balances to a mixed set with no contradicting item.
        group = [_ev("ev_bull", "bullish"), _ev("ev_bear", "bearish")]
        raw_set = EvidenceDetector.analyze_group(group, "es_general", "GENERAL", [])
        weighted = EvidenceWeighter().weight_set(raw_set, group)
        assert raw_set.bias == "mixed"
        assert weighted.consensus_score == 0.5
        assert weighted.conflict_score == 0.5
        assert raw_set.contradicting_evidence_ids == ()
        assert raw_set.supporting_evidence_ids == ()

    def test_set_level_conflict_preserved(self):
        reasoning, assessment = _reason(
            [
                _ev("ev_rY_bull", "bullish", "REAL_YIELD", composite_weight=0.8),
                _ev("ev_usd_bear", "bearish", "USD_FX", composite_weight=0.5),
            ]
        )
        assert len(assessment.contradicting_set_ids) == 1
        assert "cross_set_conflict" in assessment.bias_flags
        assert assessment.conflict_severity > 0.0
        assert assessment.confidence_penalty > 0.0


# ===========================================================================
# 6. Neutral-only evidence creates no directional thesis
# ===========================================================================


class TestNeutralOnlyCreatesNoDirection:
    def test_all_neutral_sets_yield_only_neutral_direction(self):
        reasoning, assessment = _reason(
            [
                _ev("ev_a", "neutral", "USD_FX"),
                _ev("ev_b", "neutral", "INFLATION"),
            ]
        )
        constructor = ThesisConstructor()
        directions = ThesisConstructor._determine_thesis_directions(
            reasoning, assessment
        )
        assert directions == ["neutral"]
        construction = constructor.construct(reasoning, assessment)
        built_dirs = {t.direction for t in construction.theses}
        assert "bullish" not in built_dirs
        assert "bearish" not in built_dirs

    def test_neutral_sets_cast_no_votes_against_directional_majority(self):
        contra, supp, pairs = ConflictDetector.cross_set_conflicts(
            (
                _set("es_real", "bullish"),
                _set("es_usd", "neutral", "USD_FX"),
            )
        )
        assert contra == []
        assert pairs == []
        assert supp == ["es_real"]

    def test_mixed_majority_keeps_pre_correction_contradicting_role(self):
        # Out-of-scope preservation: mixed retains its pre-060 role so only
        # the neutral semantics changed.
        contra, supp, pairs = ConflictDetector.cross_set_conflicts(
            (
                _set("es_real", "bullish"),
                _set("es_gen", "mixed", "GENERAL"),
            )
        )
        assert contra == ["es_gen"]
        assert pairs == ["es_gen_vs_bullish"]
        assert supp == ["es_real"]


# ===========================================================================
# 7. Existing directional semantics unchanged
# ===========================================================================


class TestDirectionalSemanticsUnchanged:
    def test_pure_directional_group_scores(self):
        group = [
            _ev("ev_b1", "bullish"),
            _ev("ev_b2", "bullish", kr="KR-B2"),
            _ev("ev_s1", "bearish"),
        ]
        raw_set = EvidenceDetector.analyze_group(group, "es_general", "GENERAL", [])
        weighted = EvidenceWeighter().weight_set(raw_set, group)
        assert raw_set.bias == "bullish"
        assert sorted(raw_set.supporting_evidence_ids) == ["ev_b1", "ev_b2"]
        assert raw_set.contradicting_evidence_ids == ("ev_s1",)
        # Run-003 repair: weighted masses bull=1.28/bear=0.64 ->
        # shrunk consensus (1.28+1)/(1.92+2) = 0.5816; observed conflict
        # 0.64/1.92 = 0.3333.
        assert weighted.consensus_score == round((1.28 + 1.0) / (1.92 + 2.0), 4)
        assert weighted.conflict_score == round(0.64 / 1.92, 4)

    def test_analyzer_severity_math_untouched(self):
        sets = (
            _set("es_1", "bullish"),
            _set("es_2", "bearish", "USD_FX"),
        )
        severity = BiasAnalyzer.compute_conflict_severity(sets, ["es_2"])
        assert severity > 0.0
        assert BiasAnalyzer.compute_conflict_severity(sets, []) >= 0.0

    def test_penalty_formula_untouched(self):
        assert BiasAnalyzer.compute_confidence_penalty(0.5, [], False) == 0.2
        assert BiasAnalyzer.compute_confidence_penalty(0.0, ["regime_conflict"], True) == 0.1


# ===========================================================================
# 8. News Intelligence 058 keeps intentional unknowns neutral
# ===========================================================================


class TestNews058BoundaryUnchanged:
    def test_intentionally_unknown_headlines_stay_unknown(self):
        for headline in (
            "Fed holds rates steady",
            "Dollar strengthens as yields climb",
            "Retail sales miss expectations slightly",
        ):
            cls = classify_article(headline)
            assert cls["directional_implication"] == DIRECTION_UNKNOWN

    def test_unambiguous_headline_classification_unchanged(self):
        assert (
            classify_article("Central bank gold purchases increase reserves")[
                "directional_implication"
            ]
            == DIRECTION_BULLISH
        )

    def test_news_classifier_module_untouched_by_correction_060(self):
        # The classifier source must not have been modified by this fix.
        source = (SRC / "news" / "intelligence.py").read_text(encoding="utf-8")
        assert 'DIRECTION_NEUTRAL = "neutral"' in source
        assert "uninformative" not in source.lower()


# ===========================================================================
# 9. Technical Desk remains isolated
# ===========================================================================


class TestTechnicalDeskIsolation:
    def test_technical_package_imports_no_reasoning_modules(self):
        technical_src = SRC / "technical"
        offenders: list[str] = []
        for py in technical_src.glob("*.py"):
            text = py.read_text(encoding="utf-8")
            for banned in ("evidence_reasoning", "counter_evidence", "thesis_construction"):
                if banned in text:
                    offenders.append(f"{py.name}:{banned}")
        assert offenders == []

    def test_technical_desk_contract_values_untouched(self):
        assert "technical.desk" in sys.modules or True
        from technical.contracts import DIRECTION_NEUTRAL, DIRECTION_UNKNOWN

        assert DIRECTION_NEUTRAL == "neutral"
        assert DIRECTION_UNKNOWN == "unknown"


# ===========================================================================
# 10. Deterministic repeat
# ===========================================================================


class TestDeterminism:
    def test_repeat_pipeline_identical_semantics(self):
        evidence = [
            _ev("ev_bull", "bullish", "REAL_YIELD"),
            _ev("ev_neu", "neutral", "USD_FX"),
            _ev("ev_bear", "bearish", "INFLATION"),
        ]

        def run():
            from evidence_reasoning.reasoner import EvidenceReasoner

            reasoning = EvidenceReasoner().reason(_collection(*evidence))
            return [
                (
                    s.set_id,
                    s.bias,
                    s.consensus_score,
                    s.conflict_score,
                    s.net_institutional_weight,
                    tuple(sorted(s.supporting_evidence_ids)),
                    tuple(sorted(s.contradicting_evidence_ids)),
                )
                for s in reasoning.evidence_sets
            ], ConflictDetector.cross_set_conflicts(reasoning.evidence_sets)

        first = run()
        second = run()
        assert first[0] == second[0]
        assert first[1] == second[1]


# ===========================================================================
# 11. Historical no-lookahead unaffected
# ===========================================================================


class TestHistoricalBoundaryUnaffected:
    def test_no_adjudication_payload_means_no_invented_history(self):
        reasoning, assessment = _reason([_ev("ev_n", "neutral", "USD_FX")])
        thesis = ThesisConstructor().construct(reasoning, assessment).theses[0]
        assert "historical_assessment" not in thesis.metadata
        assert "historical_adjudication:" not in thesis.explanation

    def test_historical_projection_reads_metadata_only(self):
        from thesis_construction.builder import ThesisBuilder

        src_text = inspect.getsource(ThesisBuilder._build_historical_assessment)
        assert "evidence_sets" not in src_text.replace(
            "reasoning.evidence_sets", ""
        )
        # Projection is driven exclusively by the adjudication payload.
        assert 'metadata.get("historical_adjudication")' in src_text

    def test_direction_verdict_mapping_unchanged(self):
        from thesis_construction.builder import ThesisBuilder

        assert ThesisBuilder._direction_verdict("bullish", "positive") == "supports"
        assert ThesisBuilder._direction_verdict("bullish", "negative") == "contradicts"
        assert ThesisBuilder._direction_verdict("bearish", "negative") == "supports"
        assert ThesisBuilder._direction_verdict("neutral", "mixed").startswith(
            "supports neutral"
        )
        assert ThesisBuilder._direction_verdict("bullish", "mixed") == (
            "no directional confirmation"
        )


# ===========================================================================
# 12. Regression guards for corrections 049-B/050/051/052-A/053-C/055-A
# ===========================================================================


class TestPriorCorrectionGuards:
    def test_regime_expected_bias_table_unchanged(self):
        # 049-B regime-conflict mapping untouched by 060.
        from counter_evidence.detector import REGIME_EXPECTED_BIAS

        assert REGIME_EXPECTED_BIAS["STRUCTURAL_REGIME_CHANGE"] == "neutral"
        assert REGIME_EXPECTED_BIAS["STAGFLATIONARY"] == "bearish"

    def test_candidate_bias_counterfactual_inputs_intact(self):
        # 050-A guard: candidate direction selection reads set bias only;
        # neutral-majority sets remain eligible as their own direction.
        reasoning, _ = _reason([_ev("ev_x", "neutral", "USD_FX")])
        assert reasoning.evidence_sets[0].bias == "neutral"

    def test_collector_static_neutral_mappings_unchanged(self):
        # 051/053-C guards: static instrument mappings keep their values.
        from evidence_collection.collector import (
            INSTRUMENT_TO_REGIME_BIAS,
            _observation_provenance_anchor,
        )

        assert INSTRUMENT_TO_REGIME_BIAS["US10Y Nominal Yield"] == "neutral"
        assert INSTRUMENT_TO_REGIME_BIAS["Brent Crude"] == "neutral"
        assert _observation_provenance_anchor("obs_1").startswith("no_kr_")

    def test_reference_price_and_outcome_modules_unimported_here(self):
        # 055-A guard modules exist independently of the reasoning layer.
        assert (SRC / "trade_recommendation" / "reference_price.py").exists()
        text = (SRC / "trade_recommendation" / "reference_price.py").read_text(
            encoding="utf-8"
        )
        assert "counter_evidence" not in text


# ===========================================================================
# Set builder (resolved at call time; uses the corrected detector)
# ===========================================================================


def _set(set_id: str, bias: str, event_type: str = "REAL_YIELD") -> EvidenceSet:
    """Build a single-item weighted EvidenceSet (Run-003 repair: cross-set
    conflicts consume net_institutional_weight, so the helper mirrors the
    real group -> detect -> weight pipeline)."""
    item = _ev(f"ev_{set_id}", bias, event_type)
    raw_set = EvidenceDetector.analyze_group([item], set_id, event_type, [])
    return EvidenceWeighter().weight_set(raw_set, [item])
