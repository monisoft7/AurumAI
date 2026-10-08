"""Sprint 061 -- Canonical Fact Identity + Cross-Desk Provenance tests.

Covers the mandatory verification points: deterministic identity, same /
changed primitive semantics, provenance + JSON roundtrips, source-hash
integrity, registry lookup, duplicate identity, derived lineage, cross-desk
relations, as-of rejection (single fact, future facts, transitive lineage),
desk reference integrations (news / technical / macro / historical / risk),
deterministic repeated builds, source mutation protection, decision-numeric
invariance, and non-regression of 057 reference price, 058 news and 060
neutral-evidence semantics.
"""

from __future__ import annotations

import copy
import gc
import json
import time
import tracemalloc
from types import SimpleNamespace

import pandas as pd
import pytest

from knowledge.facts import (
    RELATION_DERIVED_AGREEMENT,
    RELATION_GENUINE_DISAGREEMENT,
    RELATION_INDEPENDENT_AGREEMENT,
    RELATION_SAME_FACT_AGREEMENT,
    RELATION_UNKNOWN,
    CanonicalFact,
    CanonicalFactRegistry,
    DeskProvenance,
    FactClaim,
    FactLookaheadError,
    assert_no_lookahead,
    classify_pair,
    parse_temporal,
    primitive_fact_id,
    vote_clusters,
)
from knowledge.facts.builders import (
    analogue_reference_fact,
    news_fact_references,
    reference_price_fact,
    regime_fact_references,
    risk_desk_provenance,
    technical_fact_references,
)
from knowledge.facts.contracts import canonical_json


NOW = "2026-08-25T12:00:00+00:00"
AS_OF = "2026-08-25T00:00:00+00:00"
PAST = "2026-08-24T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _fact(**overrides) -> CanonicalFact:
    base = dict(
        fact_id=primitive_fact_id("DXY", "close", "2026-08-24"),
        asset="DXY",
        topic="close",
        as_of="2026-08-24",
        observed_at=PAST,
        value="103.5",
        unit="index",
        source="stooq",
        source_artifact_id="macro_obs_001",
        source_hash="a" * 64,
        producer="macro_regime",
        confidence=0.9,
        valid_from="2026-08-24",
    )
    base.update(overrides)
    return CanonicalFact(**base)


def _ohlcv_frame(n: int = 300) -> pd.DataFrame:
    idx = pd.bdate_range("2025-06-02", periods=n)
    close = [1900.0 + i * 0.5 for i in range(n)]
    return pd.DataFrame(
        {
            "date": idx.strftime("%Y-%m-%d"),
            "open": [c - 0.5 for c in close],
            "high": [c + 1.0 for c in close],
            "low": [c - 1.0 for c in close],
            "close": close,
        }
    )


def _news_article(title, summary="", source="TestWire", published=PAST):
    from news.models import NewsArticle, Topic

    return NewsArticle(
        title=title,
        source=source,
        url=f"https://example.com/{title[:12]}",
        published=published,
        summary=summary,
        topics=(Topic.GOLD,),
    )


@pytest.fixture()
def news_payload():
    from news.intelligence import run_news_intelligence

    return run_news_intelligence(
        data_source=lambda: [
            _news_article(
                "Central bank gold buying accelerates", summary="reserves up"
            ),
            _news_article("USD strengthened after data", summary="dollar up"),
            _news_article("CPI comes in hotter than expected"),
            _news_article("Yields climb as market prices Fed path"),
            _news_article("FOMC minutes signal patience"),
            _news_article(
                "Gold steadies as traders weigh rate outlook",
                summary="bullion rangebound",
            ),
        ],
        as_of=AS_OF,
        now=_dt_now(),
    )


def _dt_now():
    import datetime as _dt

    return _dt.datetime(2026, 8, 25, 12, 0, tzinfo=_dt.timezone.utc)


def _regime_diagnosis_dict() -> dict:
    return {
        "regime": "EXPANSION",
        "label": "Gold expansion",
        "confidence": 0.7,
        "probabilities": {"EXPANSION": 0.7, "RECESSION": 0.2, "OVERHEATING": 0.1},
        "in_transition": False,
        "transition_type": "none",
        "previous_regime": "",
        "timestamp": NOW,
        "transition_confidence": 0.0,
        "regime_duration_days": 30,
        "gram_residual": 0.1,
        "gram_trend": "stable",
        "indicator_hierarchy": [],
        "trigger_levels": [],
        "cross_asset_consistency": {},
    }


@pytest.fixture()
def technical_payload():
    pytest.importorskip("pandas_ta_classic")
    from technical.desk import TechnicalResearchDesk

    frame = _ohlcv_frame()
    as_of = str(frame["date"].iloc[-1])
    assessment = TechnicalResearchDesk().assess(
        frame, as_of=as_of, timeframe="D1", asset="XAU/USD"
    )
    errors = assessment.validate()
    assert errors == []
    assert "indicator_snapshot" in assessment.metadata, (
        "fixture must exercise the full computation path"
    )
    return assessment.to_dict()


# ===========================================================================
# 1-4. Fact contract + identity rules
# ===========================================================================


class TestIdentityRules:
    def test_1_contract_fields_and_validation(self) -> None:
        fact = _fact()
        assert fact.validate() == []
        broken = _fact(confidence=1.5)
        assert any("confidence" in e for e in broken.validate())
        wrong_id = _fact(fact_id=primitive_fact_id("XAU/USD", "close", "2026-01-01"))
        assert any("mismatch" in e for e in wrong_id.validate())

    def test_2_deterministic_fact_id(self) -> None:
        a = primitive_fact_id("DXY", "close", "2026-08-24")
        b = primitive_fact_id(" DXY ", "Close", "2026-08-24")
        c = primitive_fact_id("DXY", "close", "2026-08-24")
        assert a == b == c
        assert a.startswith("fct_")

    def test_3_same_primitive_same_fact_id_across_producers(self) -> None:
        macro = _fact(producer="macro_regime", value="103.5")
        tech = _fact(producer="technical_research", value="103.50")
        news = _fact(producer="news_intelligence", value=None)
        assert macro.fact_id == tech.fact_id == news.fact_id

    def test_4_changed_primitive_changes_identity(self) -> None:
        base = _fact()
        other_day = _fact(as_of="2026-08-25",
                          fact_id=primitive_fact_id("DXY", "close", "2026-08-25"))
        other_topic = _fact(topic="real_yield",
                            fact_id=primitive_fact_id("DXY", "real_yield", "2026-08-24"))
        other_asset = _fact(asset="US10Y",
                            fact_id=primitive_fact_id("US10Y", "close", "2026-08-24"))
        assert len({base.fact_id, other_day.fact_id, other_topic.fact_id,
                    other_asset.fact_id}) == 4
        # Same primitive, different value => same identity, different assertion
        changed_value = _fact(value="104.1")
        assert changed_value.fact_id == base.fact_id
        assert changed_value.record_hash() != base.record_hash()


# ===========================================================================
# 5-8. Serialization, hashing, registry
# ===========================================================================


class TestSerializationAndRegistry:
    def test_5_json_roundtrip_preserves_semantics(self) -> None:
        fact = _fact(metadata={"note": "x"})
        restored = CanonicalFact.from_dict(json.loads(json.dumps(fact.to_dict())))
        assert restored == fact
        assert restored.to_dict() == fact.to_dict()

    def test_6_source_hash_integrity(self) -> None:
        fact = _fact(source_hash="b" * 64)
        digest_a = fact.record_hash()
        tampered = CanonicalFact.from_dict({**fact.to_dict(), "source_hash": "c" * 64})
        assert tampered.source_hash == "c" * 64
        assert tampered.record_hash() != digest_a

    def test_7_registry_lookup_and_provenance(self) -> None:
        registry = CanonicalFactRegistry()
        registered = registry.register(_fact())
        assert registry.get(_fact().fact_id) == (registered,)
        assert registry.find(asset="DXY") == (registered,)
        assert registry.find(producer="macro_regime") == (registered,)
        assert registry.find(topic="nope") == ()
        assert registered.producer == "macro_regime"
        assert registered.source_artifact_id == "macro_obs_001"

    def test_8_duplicate_identity_is_idempotent(self) -> None:
        registry = CanonicalFactRegistry()
        first = registry.register(_fact())
        second = registry.register(CanonicalFact.from_dict(first.to_dict()))
        assert first is second or first == second
        assert len(registry.all_facts()) == 1
        # Different assertion of the SAME primitive stays visible separately.
        variant = _fact(value="104.0", producer="technical_research")
        registry.register(variant)
        assert len(registry.all_facts()) == 2
        assert registry.producers(first.fact_id) == (
            "macro_regime",
            "technical_research",
        )


# ===========================================================================
# 9-10. Derived lineage + cross-desk relations
# ===========================================================================


class TestLineageAndRelations:
    def _registry_with_lineage(self) -> tuple[CanonicalFactRegistry, CanonicalFact]:
        registry = CanonicalFactRegistry()
        close = registry.register(_fact(topic="close"))
        stance_src = _fact(
            topic="net_technical_stance",
            value="bullish",
            producer="technical_research",
            derived_from=(close.fact_id,),
            fact_id=primitive_fact_id("DXY", "net_technical_stance", "2026-08-24"),
        )
        stance = registry.register(stance_src)
        return registry, stance

    def test_9_derived_closure_and_lineage_wiring(self) -> None:
        registry, stance = self._registry_with_lineage()
        closure = registry.derivation_closure(stance.fact_id)
        close_id = primitive_fact_id("DXY", "close", "2026-08-24")
        assert closure == (close_id,)
        assert registry.derivation_upstream(stance.fact_id) == (close_id,)

        from knowledge.integrity.lineage import LineageRegistry

        lineage = LineageRegistry()
        emitted = registry.wire_lineage(lineage)
        assert emitted >= 2
        ancestors = lineage.trace(stance.fact_id, "canonical_fact")
        assert any(r.target_id == stance.fact_id for r in ancestors)

    def test_10_cross_desk_relation_taxonomy(self) -> None:
        dxy_close = primitive_fact_id("DXY", "close", "2026-08-24")
        us10y = primitive_fact_id("US10Y", "close", "2026-08-24")

        macro = FactClaim(
            desk_id="macro_regime", assessment_id="m1", polarity="bullish",
            facts_used=(dxy_close,),
        )
        macro_again = FactClaim(
            desk_id="news_intelligence", assessment_id="n1", polarity="bullish",
            facts_used=(dxy_close,),
        )
        derived_view = FactClaim(
            desk_id="technical_research", assessment_id="t1", polarity="bullish",
            facts_used=(us10y,), derived_facts=(dxy_close,),
        )
        independent = FactClaim(
            desk_id="historical_research", assessment_id="h1", polarity="bullish",
            facts_used=(us10y,),
        )
        bearish_macro = FactClaim(
            desk_id="macro_regime", assessment_id="m2", polarity="bearish",
            facts_used=(dxy_close,),
        )

        def closure(fid: str) -> tuple[str, ...]:
            if fid == us10y:
                return ()
            return ()

        assert classify_pair(macro, macro_again) == RELATION_SAME_FACT_AGREEMENT
        assert (
            classify_pair(macro, derived_view, closure=closure)
            == RELATION_DERIVED_AGREEMENT
        )
        assert classify_pair(macro, independent) == RELATION_INDEPENDENT_AGREEMENT
        assert classify_pair(macro, bearish_macro) == RELATION_GENUINE_DISAGREEMENT
        neutral = FactClaim(desk_id="d", assessment_id="x", facts_used=(dxy_close,))
        assert classify_pair(macro, neutral) == RELATION_UNKNOWN

        report = vote_clusters([macro, macro_again, independent])
        assert report["total_claims"] == 3
        assert report["deduplicated_votes"] == 2

    def test_10b_registry_backed_closure_feeds_dedup(self) -> None:
        registry, stance = self._registry_with_lineage()
        claim_a = FactClaim(
            desk_id="macro_regime", assessment_id="m1", polarity="bearish",
            facts_used=(stance.fact_id,),
        )
        claim_b = FactClaim(
            desk_id="technical_research", assessment_id="t1", polarity="bearish",
            facts_used=(primitive_fact_id("DXY", "close", "2026-08-24"),),
        )
        relation = classify_pair(
            claim_a, claim_b, closure=registry.derivation_closure
        )
        assert relation == RELATION_DERIVED_AGREEMENT


# ===========================================================================
# 11-12. As-of safety
# ===========================================================================


class TestAsOfSafety:
    def test_11_as_of_rejection_single_fact(self) -> None:
        fact = _fact(as_of="2026-08-24",
                     fact_id=primitive_fact_id("DXY", "close", "2026-08-24"))
        fact.assert_not_after("2026-08-24")  # boundary is inclusive
        with pytest.raises(FactLookaheadError):
            fact.assert_not_after("2026-08-23")
        with pytest.raises(FactLookaheadError):
            assert_no_lookahead(fact, "2026-08-23")
        with pytest.raises(ValueError):
            parse_temporal("not-a-date")  # fail-closed on garbage

    def test_12_future_fact_rejection_transitive(self) -> None:
        past_close = _fact()
        future_parent = _fact(
            topic="close", as_of="2026-09-01", observed_at="2026-09-01T00:00:00+00:00",
            valid_from="2026-09-01",
            fact_id=primitive_fact_id("DXY", "close", "2026-09-01"),
        )
        derived_future = _fact(
            topic="net_technical_stance", value="bullish",
            producer="technical_research",
            derived_from=(future_parent.fact_id,),
            fact_id=primitive_fact_id("DXY", "net_technical_stance", "2026-08-24"),
        )
        registry = CanonicalFactRegistry()
        registry.register(past_close)
        registry.register(future_parent)
        registry.register(derived_future)

        # The derived fact's own dates are clean, but its lineage reaches a
        # future primitive -- the transitive guard must catch it.
        with pytest.raises(FactLookaheadError):
            assert_no_lookahead(
                derived_future, "2026-08-25", resolve=registry.get
            )
        with pytest.raises(FactLookaheadError):
            registry.assert_no_lookahead_all("2026-08-25")
        # The clean subset passes.
        registry.assert_no_lookahead_all("2026-09-01")


# ===========================================================================
# 13-17. Desk integrations
# ===========================================================================


class TestNewsReferences:
    def test_13_news_reference_integration(self, news_payload) -> None:
        baseline = copy.deepcopy(news_payload)
        references = news_fact_references(news_payload)

        assert references["status"] == "ok"
        by_event = {r["event_type"]: r for r in references["references"]}
        mapped_events = set(by_event)
        assert mapped_events and mapped_events <= {
            "cb_gold_demand", "usd_dollar", "cpi_inflation", "yields", "fed_fomc",
        }
        # Honest unmapped gap: gold_market has no clean market primitive.
        assert "gold_market" not in by_event
        unmapped_ids = set(references["unmapped_article_ids"])
        expected_unmapped = {
            i["article_id"] for i in news_payload["items"]
            if i["event_type"] not in mapped_events
        }
        assert unmapped_ids == expected_unmapped
        gold_item = next(
            i for i in news_payload["items"] if i["event_type"] == "gold_market"
        )
        assert gold_item["article_id"] in unmapped_ids

        dxy_ref = by_event["usd_dollar"]["facts"][0]
        assert dxy_ref["asset"] == "DXY"
        usd_item = next(
            i for i in news_payload["items"] if i["event_type"] == "usd_dollar"
        )
        assert dxy_ref["observed_at"] == usd_item["published_at"]
        assert dxy_ref["source_artifact_id"] == usd_item["article_id"]
        assert dxy_ref["source_hash"] == next(
            i["content_hash"] for i in news_payload["items"]
            if i["event_type"] == "usd_dollar"
        )
        assert dxy_ref["value"] is None  # never invents direction here

        declaration = DeskProvenance.from_dict(references["desk_provenance"])
        assert declaration.validate() == []
        assert declaration.desk_id == "news_intelligence"
        assert declaration.facts_used
        assert all(f in declaration.facts_used for f in
                   (by_event["usd_dollar"]["facts"][0]["fact_id"],))

        # Source payload untouched (mutation protection rides along here).
        assert news_payload == baseline

    def test_13b_stage_attaches_references_without_changing_status(
        self, monkeypatch, tmp_path
    ) -> None:
        from orchestration.stages import _ingest_news
        from news.intelligence import run_news_intelligence

        def fake_run(**kwargs):
            payload = run_news_intelligence(
                data_source=lambda: [_news_article("Central bank gold reserves rise")],
                as_of=kwargs.get("as_of"),
                now=_dt_now(),
            )
            return payload

        monkeypatch.setattr(
            "news.intelligence.run_news_intelligence", fake_run
        )
        params = {"news_as_of": AS_OF, "_news_now": _dt_now()}
        payload = _ingest_news(params, {})
        assert payload["status"] == "ok"
        refs = payload["fact_references"]
        assert refs["status"] == "ok"
        assert refs["references"], "recognized event must carry fact refs"


class TestTechnicalReferences:
    def test_14_technical_reference_integration(self, technical_payload) -> None:
        baseline = copy.deepcopy(technical_payload)
        references = technical_fact_references(technical_payload)

        topics = {f["topic"] for f in references["facts"]}
        assert {"close", "ema200_trend_state", "rsi14_state",
                "net_technical_stance"} <= topics

        close_fact = next(f for f in references["facts"] if f["topic"] == "close")
        stance = next(f for f in references["facts"]
                      if f["topic"] == "net_technical_stance")
        assert close_fact["derived_from"] == []
        # Stance derives from indicator states, which derive from close.
        state_ids = {
            f["fact_id"] for f in references["facts"]
            if f["topic"] in {"ema200_trend_state", "rsi14_state",
                              "structure_bos_event"}
        }
        assert set(stance["derived_from"]) and set(stance["derived_from"]) <= state_ids
        registry = CanonicalFactRegistry()
        for fd in references["facts"]:
            registry.register(CanonicalFact.from_dict(fd))
        assert close_fact["fact_id"] in registry.derivation_closure(stance["fact_id"])

        declaration = DeskProvenance.from_dict(references["desk_provenance"])
        assert declaration.validate() == []
        assert declaration.desk_id == "technical_research"
        assert declaration.assessment_id == technical_payload["assessment_id"]
        assert stance["fact_id"] in declaration.derived_facts
        assert close_fact["fact_id"] in declaration.facts_used

        assert technical_payload == baseline

    def test_14b_technical_close_converges_with_reference_price(
        self, technical_payload, tmp_path
    ) -> None:
        frame = _ohlcv_frame()
        csv_path = tmp_path / "gold.csv"
        frame.to_csv(csv_path, index=False)
        from trade_recommendation.reference_price import resolve_reference_price

        as_of = str(technical_payload["as_of"])
        price, reason = resolve_reference_price(str(csv_path), as_of=as_of)
        assert price is not None and reason == ""
        # Aligned anchors: both producers describe state-as-of the same day.
        rp_fact = reference_price_fact(price, as_of=as_of)
        tech_refs = technical_fact_references(technical_payload)
        tech_close = next(
            f for f in tech_refs["facts"] if f["topic"] == "close"
        )
        assert tech_close["fact_id"] == rp_fact.fact_id


class TestMacroReferences:
    def test_15_macro_reference_integration(self) -> None:
        diagnosis = _regime_diagnosis_dict()
        baseline = copy.deepcopy(diagnosis)
        references = regime_fact_references(diagnosis, as_of="2026-08-25")

        state = references["facts"][0]
        assert state["asset"] == "GOLD"
        assert state["topic"] == "macro_regime_state"
        assert state["value"] == "EXPANSION"
        assert state["as_of"] == "2026-08-25"

        transitioned = dict(diagnosis, in_transition=True,
                            transition_type="accelerating",
                            transition_confidence=0.5)
        refs_t = regime_fact_references(transitioned, as_of="2026-08-25")
        assert len(refs_t["facts"]) == 2
        transition = refs_t["facts"][1]
        assert state["fact_id"] in transition["derived_from"]

        declaration = DeskProvenance.from_dict(refs_t["desk_provenance"])
        assert declaration.validate() == []
        assert declaration.desk_id == "macro_regime"
        assert diagnosis == baseline


class TestHistoricalAndRisk:
    def test_16_historical_compatibility(self) -> None:
        fact = analogue_reference_fact(
            lesson_id="CPI_GOLD_2015-01-09",
            event_date="2015-01-09",
            source_artifact_sha256="d" * 64,
            similarity_label="exact",
        )
        assert fact.validate() == []
        assert fact.source_artifact_id == "CPI_GOLD_2015-01-09"
        assert fact.assert_not_after("2015-01-09") is None
        with pytest.raises(FactLookaheadError):
            fact.assert_not_after("2015-01-08")  # strict historical cutoffs

        registry = CanonicalFactRegistry()
        registry.register(fact)
        registry.assert_no_lookahead_all("2015-01-09")
        with pytest.raises(FactLookaheadError):
            registry.assert_no_lookahead_all("2015-01-08")

    def test_17_risk_lineage_declaration(self) -> None:
        chain = SimpleNamespace(created_by="W11 ScenarioGeneration")
        validation = SimpleNamespace(
            validation_id="rv_test123",
            scenario_id="sc_test123",
            thesis_id="th_test123",
            provenance_chain=(chain,),
        )
        declaration = risk_desk_provenance(validation)
        assert declaration.validate() == []
        assert declaration.desk_id == "risk_reward"
        assert declaration.assessment_id == "rv_test123"
        assert "sc_test123" in declaration.source_artifacts
        assert "th_test123" in declaration.source_artifacts
        assert declaration.facts_used == ()  # conviction proxies, no primitives

        registry = CanonicalFactRegistry()
        registry.declare_desk(declaration)
        assert registry.desk_provenances(desk_id="risk_reward")[0] == declaration


# ===========================================================================
# 18-20. Determinism, mutation protection, invariance
# ===========================================================================


def _typed_briefing(news_payload):
    """Typed briefing mirroring the Sprint-058 fixture pattern."""
    from pre_market.contracts import OvernightPriceChange, PreMarketBriefing
    from pre_market.positioning import PositioningDataFetcher
    from pre_market.risk_reporter import RiskReportGenerator
    from news.intelligence import to_pre_market_news_items

    items = to_pre_market_news_items(news_payload)
    return PreMarketBriefing(
        briefing_id="premarket_inv061",
        timestamp=NOW,
        regime="EXPANSION",
        regime_confidence=0.7,
        overnight_changes=(
            OvernightPriceChange(
                instrument="DXY",
                previous_close=103.0,
                current_price=103.5,
                change_pct=0.485,
                change_sigma=1.0,
            ),
        ),
        news_items=tuple(items),
        risk_snapshot=RiskReportGenerator().generate(),
        positioning_snapshot=PositioningDataFetcher().fetch(),
        anomaly_flags=(),
        watchlist=(),
        metadata={"news_source_path": "ingest_news_stage"},
    )


_VOLATILE_KEYS = frozenset({
    "timestamp", "collection_id", "evidence_id", "provenance",
    "reasoning_id", "created_at",
})
# Pre-existing W-path volatility: evidence ids carry a wall-clock suffix
# (ev_..._YYYYMMDD_HHMMSS) -- the same noise historical_validation/compare.py
# already normalizes away.
import re as _re

_VOLATILE_ID_SUFFIX = _re.compile(r"_\d{8}_\d{6}$")


def _clean_string(value: str) -> str:
    return _VOLATILE_ID_SUFFIX.sub("", value)


def _strip_volatile(obj):
    """Normalize wall-clock/uuid fields so semantic equality is comparable."""
    if isinstance(obj, dict):
        return {
            k: _strip_volatile(v)
            for k, v in sorted(obj.items())
            if k not in _VOLATILE_KEYS
        }
    if isinstance(obj, (list, tuple)):
        normalized = [_strip_volatile(v) for v in obj]
        return sorted(
            normalized, key=lambda v: json.dumps(v, sort_keys=True, default=str)
        )
    if isinstance(obj, str):
        return _clean_string(obj)
    return obj


class TestDeterminismAndInvariance:
    def test_18_deterministic_repeated_build(
        self, news_payload, technical_payload
    ) -> None:
        def run_build() -> str:
            return json.dumps({
                "news": news_fact_references(news_payload),
                "tech": technical_fact_references(technical_payload),
                "macro": regime_fact_references(
                    _regime_diagnosis_dict(), as_of="2026-08-25"
                ),
            }, sort_keys=True)

        run_one = run_build()
        run_two = run_build()
        assert run_one == run_two
        # Wall-clock strings never enter serialized fact identity output.
        for text in (run_one,):
            for fact in json.loads(text).get("news", {}).get("facts", []):
                assert fact["observed_at"] != NOW

    def test_19_source_mutation_protection(
        self, news_payload, technical_payload
    ) -> None:
        news_before = copy.deepcopy(news_payload)
        tech_before = copy.deepcopy(technical_payload)
        diagnosis = _regime_diagnosis_dict()
        diag_before = copy.deepcopy(diagnosis)

        news_fact_references(news_payload)
        technical_fact_references(technical_payload)
        regime_fact_references(diagnosis, as_of="2026-08-25")

        assert news_payload == news_before
        assert technical_payload == tech_before
        assert diagnosis == diag_before

    def test_20_decision_numeric_invariance(self, news_payload) -> None:
        """Evidence/reasoning outputs are semantically identical with fact
        activity interleaved (volatile wall-clock/uuid fields excluded)."""
        from evidence_collection.collector import EvidenceCollector
        from evidence_reasoning.reasoner import EvidenceReasoner
        from signal_assessment.assembler import SignalAssessmentAssembler

        def build_pipeline_output() -> dict:
            briefing = _typed_briefing(news_payload)
            assessment = SignalAssessmentAssembler(regime="EXPANSION").assemble(
                briefing
            )
            collection = EvidenceCollector().collect(assessment, regime_weight=0.8)
            reasoner_output = EvidenceReasoner().reason(collection)
            return {
                "collection": collection.to_dict(),
                "reasoner": reasoner_output.to_dict(),
            }

        baseline = build_pipeline_output()

        # Interleave full Sprint-061 activity between runs.
        registry = CanonicalFactRegistry()
        for fact_dict in news_fact_references(news_payload)["facts"]:
            registry.register(CanonicalFact.from_dict(fact_dict))
        registry.declare_desk(
            DeskProvenance.from_dict(
                news_fact_references(news_payload)["desk_provenance"]
            )
        )

        after = build_pipeline_output()
        assert _strip_volatile(after["collection"]) == _strip_volatile(
            baseline["collection"]
        )
        assert _strip_volatile(after["reasoner"]) == _strip_volatile(
            baseline["reasoner"]
        )

    def test_20b_decision_path_modules_never_import_facts_layer(self) -> None:
        """Static guard: W-path modules must not consume the fact layer."""
        from pathlib import Path

        src_root = Path(__file__).resolve().parents[1] / "src"
        guarded = [
            "decision_engine/engine.py",
            "confidence_engine/engine.py",
            "risk_reward_validation/validator.py",
            "counter_evidence/assessor.py",
            "evidence_collection/collector.py",
            "evidence_reasoning/reasoner.py",
            "trade_recommendation/recommender.py",
            "trade_recommendation/reference_price.py",
            "knowledge/integrity/provenance.py",
            "knowledge/integrity/knowledge_record.py",
        ]
        for rel in guarded:
            text = (src_root / rel).read_text(encoding="utf-8")
            assert "knowledge.facts" not in text, f"{rel} must stay decoupled"


# ===========================================================================
# 21-23. Non-regression of prior sprints
# ===========================================================================


class TestPriorSprintRegressions:
    def test_21_reference_price_057_regression(self, tmp_path) -> None:
        csv_path = tmp_path / "gold.csv"
        csv_path.write_text(
            "Date,Close\n2025-12-29,2000.0\n2025-12-30,2010.5\n2026-01-02,2030.0\n",
            encoding="utf-8",
        )
        from trade_recommendation.reference_price import resolve_reference_price

        price, reason = resolve_reference_price(str(csv_path), as_of="2025-12-31")
        assert reason == "" and price.value == 2010.5
        assert str(price.bar_date).startswith("2025-12-30")

        fact = reference_price_fact(price)
        assert fact.value == "2010.5"
        assert fact.as_of == str(price.bar_date)
        assert parse_temporal(fact.as_of).isoformat() == "2025-12-30"
        assert fact.source_hash == price.source_data_hash
        # Re-resolution unchanged after fact building (pure adapter).
        price_again, reason_again = resolve_reference_price(
            str(csv_path), as_of="2025-12-31"
        )
        assert reason_again == "" and price_again.to_dict() == price.to_dict()

    def test_22_news_058_regression(self, news_payload) -> None:
        from news.intelligence import to_pre_market_news_items

        assert news_payload["status"] == "ok"
        assert news_payload["duplicate_count"] == 0
        items = to_pre_market_news_items(news_payload)
        assert len(items) == len(news_payload["items"])
        for item in items:
            assert item.provenance["article_id"]
            assert item.provenance["content_hash"]
        # Correction-051 semantics intact inside classifier output.
        for item in news_payload["items"]:
            if item["event_type"] == "usd_dollar":
                assert item["directional_implication"] == "unknown"

    def test_23_neutral_evidence_060_regression(self, news_payload) -> None:
        from evidence_collection.collector import EvidenceCollector
        from signal_assessment.assembler import SignalAssessmentAssembler

        briefing = _typed_briefing(news_payload)
        assessment = SignalAssessmentAssembler(regime="EXPANSION").assemble(briefing)
        collection = EvidenceCollector().collect(assessment, regime_weight=0.8)
        for evidence in collection.items:
            if evidence.source_label == "news":
                assert evidence.bias == "neutral"


# ===========================================================================
# Performance (Phase 13)
# ===========================================================================

_ISOLATED_MEMORY_SNIPPET = """
import sys
from datetime import date, timedelta
sys.path.insert(0, {src!r})
import tracemalloc
from knowledge.facts import CanonicalFact, CanonicalFactRegistry, primitive_fact_id

base = date(2024, 1, 1)
tracemalloc.start()
registry = CanonicalFactRegistry()
for i in range(5000):
    day = (base + timedelta(days=i)).isoformat()
    registry.register(CanonicalFact(
        fact_id=primitive_fact_id("DXY", "close", day),
        asset="DXY", topic="close", as_of=day, observed_at=day,
        value="103.5", unit="index", source="stooq",
        source_artifact_id="x_" + day, source_hash="a" * 64,
        producer="macro_regime", confidence=0.9, valid_from=day,
    ))
assert len(registry.fact_ids()) == 5000
current_kb, _peak_kb = tracemalloc.get_traced_memory()
print(current_kb // 1024)
"""


def _isolated_registry_memory_kb() -> int:
    import subprocess
    import sys as _sys
    from pathlib import Path

    src_root = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [_sys.executable, "-c", _ISOLATED_MEMORY_SNIPPET.format(src=src_root)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-500:]
    return int(result.stdout.strip().splitlines()[-1])


class TestPerformanceBudget:
    def test_creation_serialization_memory_budget(self) -> None:
        gc.collect()
        start = time.perf_counter()
        for _ in range(1000):
            _fact()
        creation_ms = (time.perf_counter() - start) * 1000

        fact = _fact()
        start = time.perf_counter()
        for _ in range(1000):
            fact.to_dict()
            canonical_json(fact.content_payload())
        serialization_ms = (time.perf_counter() - start) * 1000

        assert creation_ms < 1500, f"creation too slow: {creation_ms:.1f}ms/1000"
        assert serialization_ms < 2500, f"serialization too slow: {serialization_ms:.1f}ms/1000"
        # Memory is measured in an isolated interpreter: in-process tracing
        # accumulates unrelated allocator noise from earlier tests.
        isolated_kb = _isolated_registry_memory_kb()
        assert isolated_kb < 50_000, (
            f"registry memory too high (isolated): {isolated_kb:.0f}KB/5000 facts "
            f"(~{isolated_kb * 1024 / 5000:.0f} bytes/fact)"
        )
        print(
            f"\n[perf] creation {creation_ms / 1000 * 1000:.0f}us/1000 | "
            f"serialize+hash {serialization_ms / 1000 * 1000:.0f}us/1000 | "
            f"registry5000 {isolated_kb:.0f}KB"
        )
