"""Unit and regression tests for institutional production upgrades on XAU/USD.

Verifies:
1. Multi-timeframe pullback logic (H1/H4, D1, W1) with true R:R from avg_entry.
2. Hard logic rules for the Institutional Risk Gate (Rules A, B, C).
3. Macro event currency and impact filtering (US vs. non-US CPI).
4. Scenario A simulation (Low confidence 51.3% + downtrend -> WAIT/hold).
5. Scenario B simulation (High confidence 72.0% + uptrend -> BUY/proceed with distinct pullback zones).
"""

from __future__ import annotations

import pytest
from forecasting.decision_gate import apply_institutional_risk_gate
from operational_summary import (
    _compute_timeframe_levels,
    format_telegram_arabic_trade_card,
    resolve_macro_event_label,
)


def test_multi_timeframe_pullback_levels_distinct_and_true_rr():
    """Verify H1/H4, D1, and W1 have distinct entry zones and mathematically true 1:2.00 R:R."""
    ref_price = 4143.90
    atr = 74.95
    direction = "BUY"

    h1_h4 = _compute_timeframe_levels(ref_price, atr, direction, timeframe="H1_H4")
    d1 = _compute_timeframe_levels(ref_price, atr, direction, timeframe="D1")
    w1 = _compute_timeframe_levels(ref_price, atr, direction, timeframe="W1")

    # 1. Entry zones must NOT be identical
    assert h1_h4["entry"] != d1["entry"]
    assert d1["entry"] != w1["entry"]
    assert h1_h4["entry"] != w1["entry"]

    # 2. H1_H4 anchor: 4143.90 - (0.05 * 74.95) = 4140.1525
    # width = 0.15 * 74.95 = 11.2425 -> half = 5.62125
    # entry_low = 4134.53, entry_high = 4145.77, avg_entry = 4140.15
    assert float(h1_h4["avg_entry"]) < ref_price
    assert float(d1["avg_entry"]) < float(h1_h4["avg_entry"])
    assert float(w1["avg_entry"]) < float(d1["avg_entry"])

    # 3. Mathematically true 1:2.00 R:R from avg_entry
    for lvl in (h1_h4, d1, w1):
        avg = float(lvl["avg_entry"])
        stop = float(lvl["stop"])
        tp1 = float(lvl["tp1"])
        tp2 = float(lvl["tp2"])
        risk = abs(avg - stop)
        reward_1 = abs(tp1 - avg)
        reward_2 = abs(tp2 - avg)

        assert pytest.approx(reward_1, rel=1e-2) == risk
        assert pytest.approx(reward_2, rel=1e-2) == 2.0 * risk


def test_structural_anchor_hybrid_logic():
    """Verify that structural support/resistance correctly anchors the entry zone."""
    ref_price = 4143.90
    atr = 74.95

    # BUY with structural support below current price: anchor = 0.60*S + 0.40*atr_anchor
    s_tf = 4120.00
    lvl_struct = _compute_timeframe_levels(
        ref_price, atr, "BUY", timeframe="D1", s_tf=s_tf
    )
    atr_anchor = ref_price - (0.25 * atr)  # 4125.1625
    expected_anchor = (0.60 * s_tf) + (0.40 * atr_anchor)
    assert pytest.approx(float(lvl_struct["anchor_price"]), rel=1e-3) == expected_anchor

    # SELL with structural resistance above current price: anchor = 0.60*R + 0.40*atr_anchor
    r_tf = 4170.00
    lvl_sell_struct = _compute_timeframe_levels(
        ref_price, atr, "SELL", timeframe="D1", r_tf=r_tf
    )
    atr_anchor_sell = ref_price + (0.25 * atr)
    expected_anchor_sell = (0.60 * r_tf) + (0.40 * atr_anchor_sell)
    assert (
        pytest.approx(float(lvl_sell_struct["anchor_price"]), rel=1e-3)
        == expected_anchor_sell
    )


def test_risk_gate_rule_a_low_confidence():
    """Rule A: If confidence < 60%, force WAIT, risk_gate='hold', watchlist only."""
    res = apply_institutional_risk_gate(
        decision="BUY",
        confidence=0.513,
        structure="uptrend",
        current_risk_status="proceed",
    )
    assert res["action"] == "WAIT"
    assert res["risk_status"] == "hold"
    assert res["watchlist_only"] is True


def test_risk_gate_rule_b_gray_zone():
    """Rule B: 60% <= confidence < 65% allows directional bias only if structure aligns."""
    # Gray zone with aligned structure -> allowed directional, human_review forced
    res_aligned = apply_institutional_risk_gate(
        decision="BUY",
        confidence=0.62,
        structure="uptrend",
        current_risk_status="proceed",
    )
    assert res_aligned["action"] == "BUY"
    assert res_aligned["risk_status"] == "proceed"
    assert res_aligned["human_review"] is True

    # Gray zone with non-aligned structure (e.g. range) -> forced WAIT
    res_unaligned = apply_institutional_risk_gate(
        decision="BUY",
        confidence=0.62,
        structure="range",
        current_risk_status="proceed",
    )
    assert res_unaligned["action"] == "WAIT"
    assert res_unaligned["risk_status"] == "hold"
    assert res_unaligned["human_review"] is True


def test_risk_gate_rule_c_structure_conflict():
    """Rule C: BUY in downtrend or SELL in uptrend penalizes confidence by 10% and requires >=70%."""
    # Conflict with confidence < 70% -> rejected to WAIT/hold
    res_conflict = apply_institutional_risk_gate(
        decision="BUY",
        confidence=0.65,
        structure="downtrend",
        current_risk_status="proceed",
    )
    assert res_conflict["action"] == "WAIT"
    assert res_conflict["risk_status"] == "hold"
    assert res_conflict["human_review"] is True
    assert "تعارض هيكلي" in res_conflict["human_review_reason"]

    # Conflict with confidence >= 70% -> macro override allowed with human review
    res_override = apply_institutional_risk_gate(
        decision="BUY",
        confidence=0.75,
        structure="downtrend",
        current_risk_status="proceed",
    )
    # 75% - 10% = 65% >= 60%
    assert res_override["action"] == "BUY"
    assert res_override["human_review"] is True
    assert "تعارض هيكلي" in res_override["human_review_reason"]


def test_macro_event_currency_filtering():
    """Verify non-US CPI is tagged as secondary currency and not bare 'CPI'."""
    # UK and Canada CPI news
    arts_non_us = [
        {"title": "UK Inflation data shows CPI rises to 2.2%", "summary": "GBP holds gains"},
        {"title": "Canada headline CPI slows to 1.6%", "summary": "Bank of Canada rate cut expected"},
    ]
    label = resolve_macro_event_label("CPI", articles=arts_non_us)
    assert "CA" in label or "UK" in label
    assert "غير أمريكية" in label or "ثانوية" in label

    # No tier 1 US event
    label_empty = resolve_macro_event_label(None, articles=[])
    assert "تداول قياسي / لا يوجد حدث أمريكي رئيسي" in label_empty

    # True US event
    arts_us = [
        {"title": "US CPI report shows inflation cool to 2.4%", "summary": "Fed on track"}
    ]
    label_us = resolve_macro_event_label("CPI", articles=arts_us)
    assert "US CPI" in label_us or "الأمريكي" in label_us


def test_scenario_a_simulation_low_conf_downtrend():
    """Simulate Oct 21 live test: price=4143.90, atr=74.95, conf=51.3%, downtrend, non-US CPI."""
    summary_scenario_a = {
        "entry_date": "2026-10-21",
        "event_type": "CPI",
        "regime": "INFLATIONARY",
        "decision": {
            "action": "BUY",
            "confidence": 0.513,
        },
        "risk": {
            "reference_price": 4143.90,
            "atr": 74.95,
            "risk_status": "proceed",  # Old bug had proceed
        },
        "technical": {
            "trend_direction": "bearish",
            "momentum_direction": "bearish",
            "structure_state": "downtrend",
        },
        "governance": {
            "bias_review_flag": False,
        },
        "news": {
            "article_count": 8,
            "directional_count": 2,
        },
        "articles": [
            {"headline": "UK CPI inflation holds at 2.2% in September"},
            {"headline": "Canadian CPI decelerates to 1.6% annualized"},
        ],
    }

    card_a = format_telegram_arabic_trade_card(summary_scenario_a)

    # Verifications for Scenario A
    # 1. Action forced to WAIT with yellow circle
    assert "حياد / انتظار شروط الدخول (WAIT) 🟡" in card_a
    # 2. Risk gate displays hold
    assert "بوابة المخاطر: `hold`" in card_a
    # 3. Macro event tagged as UK/CA or secondary, not generic CPI
    assert ("UK/CA CPI" in card_a) or ("غير أمريكية" in card_a)
    # 4. Levels marked as watchlist zones
    assert "مناطق مراقبة فقط (Watchlist Zones)" in card_a
    # 5. Human review required due to structural conflict
    assert "مراجعة بشرية: `مطلوبة (مطلوبة - تعارض هيكلي)`" in card_a or "مطلوبة" in card_a


def test_scenario_b_simulation_high_conf_uptrend():
    """Simulate Scenario B: conf=72.0%, uptrend, US CPI -> BUY/proceed with distinct pullback zones."""
    summary_scenario_b = {
        "entry_date": "2026-10-21",
        "event_type": "US CPI",
        "regime": "INFLATIONARY",
        "decision": {
            "action": "BUY",
            "confidence": 0.720,
        },
        "risk": {
            "reference_price": 4143.90,
            "atr": 74.95,
            "risk_status": "proceed",
        },
        "technical": {
            "trend_direction": "bullish",
            "momentum_direction": "bullish",
            "structure_state": "uptrend",
        },
        "governance": {
            "bias_review_flag": False,
        },
        "news": {
            "article_count": 12,
            "directional_count": 5,
        },
        "articles": [
            {"headline": "US CPI cools to 2.4% boosting Fed rate cut bets"},
        ],
    }

    card_b = format_telegram_arabic_trade_card(summary_scenario_b)

    # Verifications for Scenario B
    # 1. Action is BUY with green circle
    assert "شراء (BUY) 🟢" in card_b
    # 2. Risk gate is proceed
    assert "بوابة المخاطر: `proceed`" in card_b
    # 3. Distinct timeframe entry zones
    assert "فريم الساعات (H1 / H4" in card_b
    assert "الفريم اليومي (D1" in card_b
    assert "الفريم الأسبوعي (W1" in card_b
    # 4. True R:R
    assert "1 : 2.00" in card_b
