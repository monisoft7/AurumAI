"""Execution eligibility is a single result shared by all daily consumers."""

import json
from datetime import date

from execution_policy import REQUIRED_SOURCES, final_execution_decision, publishable_recommendation
from operational_summary import build_summary, format_telegram_arabic_trade_card
from paper_trading.ledger import _normalise_decision
from scripts.evaluate_outcome import _resolve_abstention


AS_OF = date(2026, 10, 21)


def _fresh_sources():
    return {
        source: {
            "status": "ok" if source == "Gold" else "fresh",
            "observation_date": "2026-10-20" if source != "CPI" else "2026-09-01",
            "max_age_days": 7 if source != "CPI" else 90,
        }
        for source in REQUIRED_SOURCES
    }


def test_eligible_directional_signal_passes_all_gates():
    result = final_execution_decision(
        "BUY", 0.72, "proceed", _fresh_sources(),
        as_of=AS_OF, structure="uptrend",
    )
    assert result["action"] == "BUY"
    assert result["execution_allowed"] is True
    assert not result["unavailable_sources"]


def test_halt_cannot_be_overridden_by_high_confidence():
    result = final_execution_decision(
        "BUY", 0.92, "halt", _fresh_sources(),
        as_of=AS_OF, structure="uptrend",
    )
    assert result["action"] == "WAIT"
    assert result["execution_allowed"] is False
    assert result["risk_status"] == "halt"


def test_structural_override_requires_recorded_human_approval():
    result = final_execution_decision(
        "BUY", 0.75, "proceed", _fresh_sources(),
        as_of=AS_OF, structure="downtrend",
    )
    assert result["action"] == "WAIT"
    assert "human_review_required" in result["reasons"]


def test_stale_yield_blocks_execution_and_card_levels():
    sources = _fresh_sources()
    sources["DFII10"]["status"] = "fallback_stale"
    sources["DFII10"]["observation_date"] = "2026-08-27"
    result = final_execution_decision(
        "BUY", 0.80, "proceed", sources,
        as_of=AS_OF, structure="uptrend",
    )
    assert result["action"] == "WAIT"
    assert result["unavailable_sources"] == ["DFII10:fallback_stale"]
    summary = {
        "decision": {
            "action": result["action"],
            "research_direction": result["research_direction"],
            "execution_allowed": result["execution_allowed"],
            "unavailable_sources": result["unavailable_sources"],
            "confidence": 0.8,
        },
        "risk": {"risk_status": result["risk_status"], "reference_price": 4159.2, "atr": 75.07},
        "technical": {"structure_state": "uptrend"},
    }
    card = format_telegram_arabic_trade_card(summary)
    assert "WAIT" in card
    assert "DFII10:fallback_stale" in card
    assert "منطقة الدخول" not in card
    assert "وقف الخسارة" not in card


def test_missing_source_or_observation_timestamp_fails_closed():
    sources = _fresh_sources()
    del sources["DXY"]
    sources["Gold"]["observation_date"] = None
    result = final_execution_decision(
        "SELL", 0.80, "proceed", sources,
        as_of=AS_OF, structure="downtrend",
    )
    assert result["action"] == "WAIT"
    assert "DXY:unknown" in result["unavailable_sources"]
    assert "Gold:missing_observation_date" in result["unavailable_sources"]


def test_futures_price_cannot_authorize_spot_execution_levels():
    result = final_execution_decision(
        "BUY", 0.80, "proceed", _fresh_sources(),
        as_of=AS_OF, structure="uptrend",
        asset="XAU/USD", price_source="yfinance:GC=F",
    )
    assert result["action"] == "WAIT"
    assert result["gate_reason"] == "instrument_mismatch"
    assert "Gold:instrument_mismatch_or_unknown_source" in result["unavailable_sources"]


def test_approved_card_uses_only_persisted_trade_plan():
    summary = {
        "decision": {
            "action": "BUY", "research_direction": "BUY",
            "execution_allowed": True, "confidence": 0.8,
        },
        "risk": {
            "risk_status": "proceed", "reference_price": 4159.2,
            "instrument": "XAU/USD", "entry_zone": ["4159.20", "4163.20"],
            "stop": "4120.00", "tp1": "4180.00", "tp2": "4230.00",
            "market_risk_reward": 1.81,
        },
    }
    card = format_telegram_arabic_trade_card(summary)
    assert "خطة W14 المحفوظة" in card
    assert "4159.20 - 4163.20" in card
    assert "فريم الساعات" not in card


def test_summary_reads_saved_execution_action_without_redeciding(tmp_path):
    run_dir = tmp_path / "outputs" / AS_OF.isoformat() / "runtime_test"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(json.dumps({"pipeline_id": "runtime_test"}), encoding="utf-8")
    (run_dir / "finalize.json").write_text(json.dumps({
        "decision": {"decision": "BUY", "institutional_confidence": 0.80},
        "risk_decision": {"action": "proceed"},
        "execution_decision": {
            "action": "WAIT", "research_direction": "BUY",
            "execution_allowed": False, "risk_status": "proceed",
            "gate_reason": "data_unavailable_or_stale",
            "reasons": ["data_unavailable_or_stale"],
            "unavailable_sources": ["DFII10:fallback_stale"],
        },
    }), encoding="utf-8")
    summary = build_summary(run_dir, tmp_path)
    assert summary["decision"]["action"] == "WAIT"
    assert summary["decision"]["research_direction"] == "BUY"
    assert summary["decision"]["unavailable_sources"] == ["DFII10:fallback_stale"]


def test_wait_is_unscored_and_ledger_records_no_trade():
    assert _normalise_decision("WAIT") == "NO_TRADE"
    verdict, reasons = _resolve_abstention(
        {"execution_gate_reasons": ["data_unavailable_or_stale"]},
        pending=False, realized=1.5,
    )
    assert verdict == "unresolvable"
    assert reasons == ["data_unavailable_or_stale"]


def test_blocked_recommendation_has_no_published_order_levels():
    original = {
        "recommendation_action": "BUY", "entry_zone": ["4100", "4110"],
        "stop_loss": "4080", "take_profit_1": "4140", "take_profit_2": "4170",
        "position_size_recommendation": "1 lot", "risk_pct": 2.0,
        "metadata": {"market_risk_summary": {"entry": 4105}, "reference_price": 4105},
    }
    blocked = publishable_recommendation(original, {
        "action": "WAIT", "execution_allowed": False,
    })
    assert blocked["recommendation_action"] == "WAIT"
    assert blocked["entry_zone"] == []
    assert all(not blocked[key] for key in (
        "stop_loss", "take_profit_1", "take_profit_2", "position_size_recommendation",
    ))
    assert blocked["risk_pct"] == 0.0
    assert "market_risk_summary" not in blocked["metadata"]
    assert blocked["metadata"]["reference_price"] == 4105
    assert original["entry_zone"] == ["4100", "4110"]
