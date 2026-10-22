"""AurumAI daily operational summary (additive measurement layer).

Builds ``daily_operational_summary.json`` inside an existing run directory
(``outputs/YYYY-MM-DD/<pipeline_id>/``) by *reading only* artifacts the
pipeline already wrote.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forecasting.decision_gate import apply_institutional_risk_gate

SCHEMA_VERSION = "1.1"
SUMMARY_FILENAME = "daily_operational_summary.json"

_UNAVAILABLE = "unavailable"


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _clean(value: Any) -> Any:
    """Normalize empty producer values to explicit nulls."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _load_registry_record(root: Path, run_id: str) -> dict[str, Any] | None:
    registry = root / "runtime" / "run_registry.jsonl"
    if not registry.exists() or not run_id:
        return None
    try:
        lines = registry.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    record: dict[str, Any] | None = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict) and parsed.get("run_id") == run_id:
            record = parsed
    return record


def _build_decision(finalize: dict[str, Any]) -> dict[str, Any]:
    decision = finalize.get("decision") or {}
    metadata = decision.get("metadata") or {}
    execution = finalize.get("execution_decision") or {}
    result = {
        "action": _clean(execution.get("action")) if execution else _clean(decision.get("decision")),
        "confidence": _clean(decision.get("institutional_confidence")),
        "selected_thesis_id": _clean(decision.get("selected_thesis_id")),
        "gate_reason": _clean(execution.get("gate_reason")) if execution else _clean(metadata.get("gate_reason")),
    }
    if execution:
        result.update({
            "research_direction": _clean(decision.get("decision")),
            "execution_allowed": execution.get("execution_allowed"),
            "execution_reasons": execution.get("reasons"),
            "unavailable_sources": execution.get("unavailable_sources"),
        })
    return result


def _build_news(finalize: dict[str, Any]) -> dict[str, Any]:
    news = finalize.get("news_intelligence")
    if not isinstance(news, dict) or not news:
        return {
            "status": _UNAVAILABLE,
            "article_count": None,
            "relevant_count": None,
            "directional_count": None,
            "unknown_count": None,
            "sentiment_status": None,
        }
    items = news.get("items") or []
    if not isinstance(items, list):
        items = []
    directional_count = 0
    unknown_count = 0
    relevant_count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        implication = str(item.get("directional_implication", ""))
        if implication == "unknown":
            unknown_count += 1
        elif implication:
            directional_count += 1
        relevance = str(item.get("gold_relevance", ""))
        if relevance in ("high", "medium"):
            relevant_count += 1
    return {
        "status": _clean(news.get("status")),
        "article_count": len(items),
        "relevant_count": relevant_count,
        "directional_count": directional_count,
        "unknown_count": unknown_count,
        "sentiment_status": _clean(news.get("sentiment_status")),
    }


def _build_technical(run_dir: Path) -> dict[str, Any]:
    technical = _read_json(run_dir / "artifacts" / "technical_assessment.json")
    if not isinstance(technical, dict) or not technical:
        return {
            "status": _UNAVAILABLE,
            "trend_direction": None,
            "momentum_direction": None,
            "structure_state": None,
            "technical_confidence": None,
        }
    return {
        "status": "ok",
        "trend_direction": _clean(technical.get("trend_direction")),
        "momentum_direction": _clean(technical.get("momentum_direction")),
        "structure_state": _clean(technical.get("structure_state")),
        "technical_confidence": _clean(technical.get("technical_confidence")),
    }


def _build_risk(finalize: dict[str, Any]) -> dict[str, Any]:
    recommendation = finalize.get("trade_recommendation") or {}
    metadata = recommendation.get("metadata") or {}
    atr_provenance = metadata.get("atr_provenance") or {}
    market_summary = metadata.get("market_risk_summary") or {}
    risk_decision = finalize.get("risk_decision") or {}
    reference_price = _clean(metadata.get("reference_price"))
    atr = _clean(atr_provenance.get("atr_14"))
    if atr is None and market_summary:
        atr = _clean(market_summary.get("atr_14"))
    result = {
        "status": "ok" if recommendation else _UNAVAILABLE,
        "reference_price": reference_price,
        "atr": atr,
        "stop": _clean(recommendation.get("stop_loss")),
        "tp1": _clean(recommendation.get("take_profit_1")),
        "tp2": _clean(recommendation.get("take_profit_2")),
        "market_risk_reward": _clean(market_summary.get("market_reward_risk_ratio")),
        "risk_status": _clean(risk_decision.get("action")),
    }
    if finalize.get("execution_decision"):
        provenance = metadata.get("reference_price_provenance") or {}
        result.update({
            "instrument": _clean(recommendation.get("instrument")),
            "entry_zone": recommendation.get("entry_zone") or None,
            "price_bar_date": _clean(provenance.get("bar_date")),
            "price_source": finalize["execution_decision"].get("price_source"),
            "price_freshness": (finalize.get("source_freshness") or {}).get("Gold"),
        })
    return result


def _build_governance(finalize: dict[str, Any]) -> dict[str, Any]:
    decision = finalize.get("decision") or {}
    metadata = decision.get("metadata") or {}
    bias_review = metadata.get("bias_review") or {}
    provenance_chain = decision.get("provenance_chain") or []
    return {
        "bias_review_flag": _clean(bias_review.get("human_review_flag")),
        "bias_severity": _clean(bias_review.get("overall_severity")),
        "provenance_status": "ok" if provenance_chain else _UNAVAILABLE,
    }


def _build_outcome(run_dir: Path) -> dict[str, Any]:
    outcome = _read_json(run_dir / "outcome.evaluated.json")
    if not isinstance(outcome, dict) or not outcome:
        return {
            "status": _UNAVAILABLE,
            "decision_correct": None,
            "abstention_verdict": None,
            "realized_return": None,
        }
    return {
        "status": _clean(outcome.get("status")),
        "decision_correct": _clean(outcome.get("decision_correct")),
        "abstention_verdict": _clean(outcome.get("abstention_verdict")),
        "realized_return": _clean(outcome.get("realized_gold_return")),
    }


def _build_calibration(root: Path) -> dict[str, Any]:
    calibration = _read_json(root / "runtime" / "calibration.json")
    if not isinstance(calibration, dict) or not calibration:
        return {
            "sample_count": None,
            "oos_ece": None,
            "calibration_status": _UNAVAILABLE,
        }
    statistics = calibration.get("statistics") or {}
    sample_count = _clean(calibration.get("sample_count"))
    if sample_count is None:
        sample_count = _clean(statistics.get("sample_count"))
    minimum = statistics.get("min_samples_required")
    if sample_count is not None and isinstance(minimum, (int, float)):
        calibration_status = (
            "dormant" if sample_count < minimum
            else "active" if calibration.get("eligible_for_confidence_cap") is True
            else "diagnostic_only"
        )
    elif sample_count == 0:
        calibration_status = "dormant"
    else:
        calibration_status = _UNAVAILABLE
    return {
        "sample_count": sample_count,
        "oos_ece": _clean(calibration.get("oos_ece")),
        "calibration_status": calibration_status,
    }


def _build_provenance(run_dir: Path, root: Path, run_id: str) -> dict[str, Any]:
    source_hashes: dict[str, str] = {}
    outcome = _read_json(run_dir / "outcome.evaluated.json") or {}
    if isinstance(outcome, dict):
        gold_hash = _clean(outcome.get("gold_source_sha256"))
        if gold_hash:
            source_hashes["gold_history"] = str(gold_hash)
    technical = _read_json(run_dir / "artifacts" / "technical_assessment.json") or {}
    if isinstance(technical, dict):
        technical_hash = _clean(technical.get("source_data_hash"))
        if technical_hash:
            source_hashes["technical_assessment"] = str(technical_hash)
    record = _load_registry_record(root, run_id)
    git_commit = _clean(record.get("git_commit")) if record else None
    return {
        "git_commit": git_commit,
        "source_hashes": source_hashes,
    }


def build_summary(run_dir: Path, root: Path | None = None) -> dict[str, Any]:
    """Build the daily operational summary dict from existing artifacts."""
    run_dir = Path(run_dir)
    root = Path(root) if root is not None else run_dir
    summary = _read_json(run_dir / "summary.json") or {}
    finalize = _read_json(run_dir / "finalize.json") or {}
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(finalize, dict):
        finalize = {}

    run_id = _clean(summary.get("pipeline_id"))
    outcome = _read_json(run_dir / "outcome.evaluated.json") or {}
    entry_date = (
        _clean(outcome.get("entry_date"))
        if isinstance(outcome, dict)
        else None
    )
    if entry_date is None and run_dir.parent.name:
        entry_date = run_dir.parent.name

    context = finalize.get("context") or {}

    dec = _build_decision(finalize)
    news_dict = _build_news(finalize)
    tech = _build_technical(run_dir)
    risk_dict = _build_risk(finalize)
    gov = _build_governance(finalize)

    conf_val = dec.get("confidence")
    action_val = dec.get("action")
    struct_val = tech.get("structure_state")
    risk_status_val = risk_dict.get("risk_status") or "proceed"
    review_val = gov.get("bias_review_flag") or False

    execution = finalize.get("execution_decision") or {}
    if execution:
        risk_dict["risk_status"] = execution.get("risk_status")
        if execution.get("human_review"):
            gov["bias_review_flag"] = True
    elif conf_val is not None and isinstance(conf_val, (int, float)):
        gate_res = apply_institutional_risk_gate(
            decision=action_val or "HOLD",
            confidence=float(conf_val),
            structure=struct_val,
            current_risk_status=risk_status_val,
            human_review=bool(review_val),
        )
        if gate_res["action"] != action_val and action_val in ("BUY", "SELL"):
            dec["action"] = gate_res["action"]
            dec["gate_reason"] = gate_res["gate_reason"]
        if gate_res["risk_status"] != risk_status_val:
            risk_dict["risk_status"] = gate_res["risk_status"]
        if gate_res["human_review"]:
            gov["bias_review_flag"] = True

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "entry_date": entry_date,
        "event_type": _clean(summary.get("event_type")),
        "event_calendar": finalize.get("event_calendar") or {"status": "unavailable"},
        "regime": _clean(context.get("current_regime")),
        "decision": dec,
        "news": news_dict,
        "technical": tech,
        "risk": risk_dict,
        "governance": gov,
        "outcome": _build_outcome(run_dir),
        "calibration": _build_calibration(root),
        "provenance": _build_provenance(run_dir, root, str(run_id) if run_id else ""),
    }


def write_summary(run_dir: Path, root: Path | None = None) -> Path:
    """Write ``daily_operational_summary.json`` into the run directory."""
    summary = build_summary(run_dir, root)
    path = Path(run_dir) / SUMMARY_FILENAME
    path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def format_telegram_compact(summary: dict[str, Any]) -> str:
    """Render the compact phone-readable Telegram snapshot (contract-tested)."""
    decision = summary.get("decision") or {}
    news = summary.get("news") or {}
    technical = summary.get("technical") or {}
    risk = summary.get("risk") or {}
    governance = summary.get("governance") or {}
    outcome = summary.get("outcome") or {}
    calibration = summary.get("calibration") or {}

    def fmt(value: Any) -> str:
        if value is None:
            return "n/a"
        if isinstance(value, float):
            return f"{value:.4f}".rstrip("0").rstrip(".")
        return str(value)

    lines = [
        "AURUMAI DAILY SNAPSHOT",
        f"Date: {fmt(summary.get('entry_date'))} | Event: {fmt(summary.get('event_type'))}",
        f"Regime: {fmt(summary.get('regime'))}",
        f"Decision: {fmt(decision.get('action'))} "
        f"(confidence {fmt(decision.get('confidence'))})",
        f"Gate: {fmt(decision.get('gate_reason'))}",
        f"Technical: {fmt(technical.get('trend_direction'))} / "
        f"{fmt(technical.get('momentum_direction'))} / "
        f"{fmt(technical.get('structure_state'))} "
        f"(conf {fmt(technical.get('technical_confidence'))})",
        f"News: {fmt(news.get('status'))} | "
        f"articles {fmt(news.get('article_count'))} | "
        f"directional {fmt(news.get('directional_count'))} | "
        f"unknown {fmt(news.get('unknown_count'))} | "
        f"sentiment {fmt(news.get('sentiment_status'))}",
        f"Execution: ref {fmt(risk.get('reference_price'))} | "
        f"stop {fmt(risk.get('stop'))} | "
        f"tp1 {fmt(risk.get('tp1'))} | tp2 {fmt(risk.get('tp2'))}",
        f"Market RR: {fmt(risk.get('market_risk_reward'))} | "
        f"risk gate: {fmt(risk.get('risk_status'))}",
        f"Bias: severity {fmt(governance.get('bias_severity'))} | "
        f"human review {fmt(governance.get('bias_review_flag'))}",
        f"Outcome: {fmt(outcome.get('status'))} | "
        f"Calibration: {fmt(calibration.get('calibration_status'))} "
        f"({fmt(calibration.get('sample_count'))} samples)",
    ]
    return "\n".join(lines)


TIMEFRAME_PULLBACK_CONFIGS: dict[str, dict[str, float]] = {
    "H1_H4": {
        "offset_atr": 0.05,
        "width_atr": 0.15,
        "sl_buffer_atr": 0.40,
        "lookback": 12,
    },
    "D1": {
        "offset_atr": 0.25,
        "width_atr": 0.25,
        "sl_buffer_atr": 0.75,
        "lookback": 5,
    },
    "W1": {
        "offset_atr": 0.60,
        "width_atr": 0.40,
        "sl_buffer_atr": 1.10,
        "lookback": 3,
    },
}


def _compute_timeframe_levels(
    ref_price: float,
    atr: float,
    direction: str,
    timeframe: str = "H1_H4",
    offset_atr: float | None = None,
    width_atr: float | None = None,
    sl_buffer_atr: float | None = None,
    s_tf: float | None = None,
    r_tf: float | None = None,
    *args: Any,
    **kwargs: Any,
) -> dict[str, str]:
    """Compute multi-timeframe pullback & structural entry zones for Gold.

    Logic:
    - H1_H4 (Intraday): offset_atr=0.05, width_atr=0.15, sl_buffer_atr=0.40 (Lookback: 12 H4 candles min/max)
    - D1 (Swing): offset_atr=0.25, width_atr=0.25, sl_buffer_atr=0.75 (Lookback: 5 D1 candles min/max)
    - W1 (Position): offset_atr=0.60, width_atr=0.40, sl_buffer_atr=1.10 (Lookback: 3 W1 candles min/max)

    Hybrid Anchor:
    - BUY: atr_anchor = current_price - (offset_atr * atr). If S_tf < current_price: anchor = 0.60*S_tf + 0.40*atr_anchor
    - SELL: atr_anchor = current_price + (offset_atr * atr). If R_tf > current_price: anchor = 0.60*R_tf + 0.40*atr_anchor

    Entry Zone & True R:R:
    - entry_low / entry_high centered on anchor_price with width = width_atr * atr
    - avg_entry = (entry_low + entry_high) / 2.0
    - SL placed beyond outer edge:
        BUY: sl = entry_low - (sl_buffer_atr * atr)
        SELL: sl = entry_high + (sl_buffer_atr * atr)
    - risk = abs(avg_entry - sl)
    - TP1 = avg_entry ± 1.0 * risk, TP2 = avg_entry ± 2.0 * risk
    """
    # Backward compatibility: if 4th argument is a float (old stop_mult), map it to matching preset
    if isinstance(timeframe, (int, float)):
        old_stop_mult = float(timeframe)
        if old_stop_mult <= 0.60:
            cfg_name = "H1_H4"
        elif old_stop_mult <= 1.20:
            cfg_name = "D1"
        else:
            cfg_name = "W1"
    else:
        cfg_name = str(timeframe).upper()
        if cfg_name in ("H1", "H4"):
            cfg_name = "H1_H4"

    cfg = TIMEFRAME_PULLBACK_CONFIGS.get(cfg_name, TIMEFRAME_PULLBACK_CONFIGS["H1_H4"])
    eff_offset = offset_atr if offset_atr is not None else cfg["offset_atr"]
    eff_width = width_atr if width_atr is not None else cfg["width_atr"]
    eff_sl_buf = sl_buffer_atr if sl_buffer_atr is not None else cfg["sl_buffer_atr"]

    dir_upper = str(direction).upper()
    current_price = float(ref_price)
    atr_val = float(atr)

    if dir_upper == "BUY":
        atr_anchor = current_price - (eff_offset * atr_val)
        if s_tf is not None and float(s_tf) < current_price:
            anchor_price = (0.60 * float(s_tf)) + (0.40 * atr_anchor)
        else:
            anchor_price = atr_anchor

        half_width = (eff_width * atr_val) / 2.0
        entry_low = anchor_price - half_width
        entry_high = anchor_price + half_width
        avg_entry = (entry_low + entry_high) / 2.0
        stop = entry_low - (eff_sl_buf * atr_val)
        risk = abs(avg_entry - stop)
        tp1 = avg_entry + (1.0 * risk)
        tp2 = avg_entry + (2.0 * risk)
    else:
        atr_anchor = current_price + (eff_offset * atr_val)
        if r_tf is not None and float(r_tf) > current_price:
            anchor_price = (0.60 * float(r_tf)) + (0.40 * atr_anchor)
        else:
            anchor_price = atr_anchor

        half_width = (eff_width * atr_val) / 2.0
        entry_low = anchor_price - half_width
        entry_high = anchor_price + half_width
        avg_entry = (entry_low + entry_high) / 2.0
        stop = entry_high + (eff_sl_buf * atr_val)
        risk = abs(avg_entry - stop)
        tp1 = avg_entry - (1.0 * risk)
        tp2 = avg_entry - (2.0 * risk)

    return {
        "entry": f"{entry_low:.2f} - {entry_high:.2f}",
        "stop": f"{stop:.2f}",
        "tp1": f"{tp1:.2f}",
        "tp2": f"{tp2:.2f}",
        "avg_entry": f"{avg_entry:.2f}",
        "risk": f"{risk:.2f}",
        "anchor_price": f"{anchor_price:.2f}",
    }


def _resolve_structural_extrema(
    run_dir: Path | None = None,
    summary: dict[str, Any] | None = None,
) -> dict[str, tuple[float | None, float | None]]:
    """Resolve structural support and resistance (S_tf, R_tf) per timeframe."""
    extrema: dict[str, tuple[float | None, float | None]] = {
        "H1_H4": (None, None),
        "D1": (None, None),
        "W1": (None, None),
    }
    if run_dir is not None:
        tech_file = Path(run_dir) / "artifacts" / "technical_assessment.json"
        if not tech_file.is_file():
            tech_file = Path(run_dir) / "technical_assessment.json"
        if tech_file.is_file():
            tech_data = _read_json(tech_file)
            if isinstance(tech_data, dict):
                structure = (tech_data.get("metadata") or {}).get("structure") or {}
                s_val = structure.get("last_swing_low")
                r_val = structure.get("last_swing_high")
                if s_val is not None and r_val is not None:
                    extrema["D1"] = (float(s_val), float(r_val))
    return extrema


def resolve_macro_event_label(
    event_type: str | None,
    articles: list[dict[str, Any]] | None = None,
) -> str:
    """Filter tier-1 macro event tags strictly by currency == 'USD' (or country == 'US').
    - If a high-impact event belongs to a secondary currency (GBP, CAD, EUR, JPY), prefix with currency/country code (e.g., UK/CA CPI) and reduce weight on Gold by 70%.
    - If no tier-1 US event is scheduled today, display 'تداول قياسي / لا يوجد حدث أمريكي رئيسي' or explicitly tag the secondary event currency.
    """
    ev_str = str(event_type or "").strip()
    sec_tags = set()
    has_us = False

    for art in (articles or []):
        if not isinstance(art, dict):
            continue
        text = f"{art.get('headline', '')} {art.get('title', '')} {art.get('summary', '')}".lower()
        if "cpi" in text or "inflation" in text:
            if any(k in text for k in ("uk", "britain", "british", "england", "boe", "gbp")):
                sec_tags.add("UK")
            if any(k in text for k in ("canada", "canadian", "boc", "cad")):
                sec_tags.add("CA")
            if any(k in text for k in ("eurozone", "ecb", "europe", "eur")):
                sec_tags.add("EUR")
            if any(k in text for k in ("japan", "japanese", "boj", "yen", "jpy")):
                sec_tags.add("JPY")
            if any(k in text for k in ("us ", "u.s.", "united states", "fed ", "federal reserve", "bls")):
                has_us = True

    tier1_names = ("CPI", "CORE CPI", "NFP", "FOMC", "GDP", "PCE", "PPI", "CPIEVENT")
    ev_upper = ev_str.upper()
    is_tier1 = any(t in ev_upper for t in tier1_names)

    if is_tier1:
        if sec_tags and not has_us:
            sec_pfx = "/".join(sorted(sec_tags))
            return f"{sec_pfx} CPI (بيانات تضخم ثانوية - غير أمريكية)"
        elif has_us or "US" in ev_upper:
            return "US CPI (مؤشر أسعار المستهلكين الأمريكي)"
        elif not ev_str or ev_upper in ("CPI", "CPIEVENT"):
            if sec_tags:
                sec_pfx = "/".join(sorted(sec_tags))
                return f"{sec_pfx} CPI (بيانات تضخم ثانوية - غير أمريكية)"
            return "تداول قياسي / لا يوجد حدث أمريكي رئيسي"

    if not ev_str or ev_upper in ("NONE", "UNAVAILABLE", "UNKNOWN", "STANDARD"):
        if sec_tags:
            sec_pfx = "/".join(sorted(sec_tags))
            return f"{sec_pfx} CPI (تأثير غير مباشر - ثانوي)"
        return "تداول قياسي / لا يوجد حدث أمريكي رئيسي"

    return ev_str


def format_telegram_arabic_trade_card(
    summary: dict[str, Any],
    run_dir: Path | None = None,
) -> str:
    """بناء ملخص التداول التنفيذي المختصر للذهب (XAU/USD) باللغة العربية."""
    decision = summary.get("decision") or {}
    risk = summary.get("risk") or {}
    technical = summary.get("technical") or {}
    news = summary.get("news") or {}
    governance = summary.get("governance") or {}

    raw_action = str(decision.get("action") or "NO_TRADE").upper()
    conf = decision.get("confidence")
    conf_pct = f"{float(conf) * 100:.1f}%" if isinstance(conf, (int, float)) else "غير متاح"

    # استخراج الاتجاه المرشح حتى في حالة NO_TRADE ليتمكن المتداول من اتخاذ قراره
    research_dir = str(decision.get("research_direction") or "").upper()
    effective_dir = research_dir if research_dir in ("BUY", "SELL") else (raw_action if raw_action in ("BUY", "SELL") else None)
    if effective_dir is None and run_dir is not None:
        finalize = _read_json(Path(run_dir) / "finalize.json") or {}
        dec_meta = ((finalize.get("decision") or {}).get("metadata")) or {}
        cand_dir = str(dec_meta.get("selected_thesis_direction") or "").lower()
        if cand_dir == "bullish":
            effective_dir = "BUY"
        elif cand_dir == "bearish":
            effective_dir = "SELL"

    # تطبيق قواعد بوابة المخاطر المؤسسية المتقدمة (Rules A, B, C)
    risk_status_raw = str(risk.get("risk_status") or "").lower()
    gov_review = bool(governance.get("bias_review_flag"))
    gov_reason = str(governance.get("bias_review_reason") or "")

    gate_result = None
    if decision.get("execution_allowed") is not None:
        effective_action = raw_action
        risk_status = risk_status_raw or "unknown"
    elif isinstance(conf, (int, float)):
        gate_result = apply_institutional_risk_gate(
            decision=raw_action,
            confidence=float(conf),
            structure=technical.get("structure_state"),
            current_risk_status=risk_status_raw or "proceed",
            human_review=gov_review,
        )
        effective_action = gate_result["action"]
        risk_status = gate_result["risk_status"]
        if gate_result["human_review"]:
            gov_review = True
        if gate_result["human_review_reason"]:
            gov_reason = gate_result["human_review_reason"]
    else:
        effective_action = raw_action
        risk_status = risk_status_raw or "proceed"

    is_hold = (
        risk_status in ("hold", "halt", "delay", "unknown", "unavailable")
        or effective_action in ("WAIT", "HOLD", "NO_TRADE")
        or (isinstance(conf, (int, float)) and float(conf) < 0.60)
    )

    if is_hold or effective_action in ("WAIT", "HOLD"):
        action_ar = "حياد / انتظار شروط الدخول (WAIT) 🟡"
    elif effective_action == "BUY":
        action_ar = "شراء (BUY) 🟢"
    elif effective_action == "SELL":
        action_ar = "بيع (SELL) 🔴"
    else:
        action_ar = "حياد / انتظار شروط الدخول (WAIT) 🟡"

    regime_ar = {
        "INFLATIONARY": "تضخمي (داعم للذهب)",
        "STAGFLATIONARY": "ركود تضخمي",
        "NORMAL_GROWTH": "نمو طبيعي",
        "LATE_CYCLE": "نهاية الدورة الاقتصادية (Late Cycle)",
        "DEFLATIONARY_CRISIS": "انكماشي / أزمة سيولة",
        "GEOPOLITICAL_STRESS": "توتر جيوسياسي",
        "EXPANSION": "توسع اقتصادي",
    }.get(str(summary.get("regime") or ""), str(summary.get("regime") or "غير متاح"))

    ref_price = risk.get("reference_price")
    atr = risk.get("atr")
    ref_str = f"{float(ref_price):.2f}$" if isinstance(ref_price, (int, float)) else "غير متاح"
    atr_str = f"{float(atr):.2f}$" if isinstance(atr, (int, float)) else "غير متاح"
    rr_val = risk.get("market_risk_reward")
    rr_str = f"1 : {float(rr_val):.2f}" if isinstance(rr_val, (int, float)) else "غير متاح"
    if is_hold:
        rr_str = "لا توجد صفقة صالحة"

    calendar = summary.get("event_calendar") or {}
    if calendar.get("status") == "verified":
        names = sorted({str(e["event"]) for e in calendar.get("events_today", [])})
        event_display = " / ".join(names) if names else "لا حدث اليوم ضمن التغطية المتحققة"
    else:
        event_display = "تقويم الأحداث غير متحقق"

    lines = [
        "**📊 ملخص AurumAI التنفيذي للذهب (XAU/USD)**",
        f"📅 التاريخ: `{summary.get('entry_date') or 'اليوم'}` | الحدث: `{event_display}`",
        "",
        f"**🎯 التوصية المؤسسية:** **{action_ar}**",
        f"• درجة الدعم المؤسسي (ليست احتمال نجاح): `{conf_pct}`",
        f"• آخر إغلاق مرجعي محفوظ: `{ref_str}` | التذبذب اليومي (ATR): `{atr_str}`",
        f"• العائد مقابل المخاطرة: `{rr_str}` | بوابة المخاطر: `{risk_status}`",
    ]

    unavailable_sources = decision.get("unavailable_sources") or []
    if unavailable_sources:
        lines.append(f"• بيانات غير صالحة للتنفيذ: `{', '.join(unavailable_sources)}`")
    if risk.get("price_source"):
        lines.append(f"• مصدر سعر الذهب: `{risk['price_source']}` | تاريخ الإغلاق: `{risk.get('price_bar_date') or 'غير متاح'}`")
    price_freshness = risk.get("price_freshness") or {}
    if price_freshness:
        fresh_label = "حديث" if price_freshness.get("status") in ("ok", "fresh", "refreshed") else "متأخر أو غير متاح"
        lines.append(f"• حالة الإغلاق: `{fresh_label}` | آخر يوم تداول مكتمل متوقع: `{price_freshness.get('expected_observation_date') or 'غير متاح'}`")
    if calendar.get("scope"):
        lines.append(f"• تغطية التقويم: `{', '.join(calendar['scope'])}` | يوم التقويم: `{calendar.get('as_of_date')}` بتوقيت نيويورك")
    reason_labels = {
        "data_unavailable_or_stale": "بيانات لازمة متأخرة أو غير متاحة",
        "confidence_below_60_threshold": "درجة الدعم أقل من حد الدخول 60%",
        "risk_status_hold": "بوابة المخاطر في وضع الانتظار",
        "event_calendar_unverified_or_stale": "تعذر التحقق من تقويم الأحداث الحالي",
        "scheduled_high_impact_event_day": "يوم حدث مجدول ضمن التغطية؛ الدخول محجوب وفق السياسة اليومية",
    }
    reasons = decision.get("execution_reasons") or []
    if reasons:
        lines.append("• أسباب الانتظار: " + "؛ ".join(reason_labels.get(r, str(r)) for r in reasons))

    # A hard risk stop or stale critical input cannot produce an actionable
    # price plan.  Preserve a research direction without showing entry/SL/TP.
    hard_stop = is_hold or bool(unavailable_sources)
    if hard_stop:
        lines.append("• الاتجاه البحثي للمراقبة فقط؛ لا توجد خطة دخول صالحة حتى تزول أسباب المنع.")

    if decision.get("execution_allowed") is not None:
        if not hard_stop:
            zone = risk.get("entry_zone") or []
            if zone and risk.get("stop") and risk.get("tp1") and risk.get("tp2"):
                lines.extend([
                    "",
                    "**📌 خطة W14 المحفوظة لهذا القرار:**",
                    f"• الأداة: `{risk.get('instrument') or 'غير متاح'}` | منطقة الدخول: `{' - '.join(str(v) for v in zone)}`",
                    f"• وقف الخسارة: `{risk['stop']}` | الهدف الأول: `{risk['tp1']}` | الهدف الثاني: `{risk['tp2']}`",
                    "• نسبة العائد/المخاطرة أعلاه محسوبة عند السعر المرجعي، وتتغير حسب سعر التعبئة والتكاليف.",
                ])
            else:
                lines.append("• خطة الدخول غير مكتملة؛ لا توجد مستويات تنفيذ معتمدة.")
    elif not hard_stop and isinstance(ref_price, (int, float)) and isinstance(atr, (int, float)) and effective_dir in ("BUY", "SELL"):
        dir_label = "شراء (BUY)" if effective_dir == "BUY" else "بيع (SELL)"
        if is_hold or raw_action in ("NO_TRADE", "WAIT"):
            lines.append(f"• ملاحظة: بوابة المخاطر بحالة انتظار (HOLD) - المستويات التالية هي مناطق مراقبة فقط (Watchlist Zones) وليست أوامر تنفيذ مباشرة:")

        extrema = _resolve_structural_extrema(run_dir=run_dir, summary=summary)
        s_h, r_h = extrema.get("H1_H4", (None, None))
        s_d, r_d = extrema.get("D1", (None, None))
        s_w, r_w = extrema.get("W1", (None, None))

        h_lvl = _compute_timeframe_levels(float(ref_price), float(atr), effective_dir, timeframe="H1_H4", s_tf=s_h, r_tf=r_h)
        d_lvl = _compute_timeframe_levels(float(ref_price), float(atr), effective_dir, timeframe="D1", s_tf=s_d, r_tf=r_d)
        w_lvl = _compute_timeframe_levels(float(ref_price), float(atr), effective_dir, timeframe="W1", s_tf=s_w, r_tf=r_w)

        zone_label = "منطقة مراقبة (Watchlist Zone)" if is_hold else "منطقة الدخول (Pullback Zone)"

        lines.extend([
            "",
            f"**⏱️ 1. فريم الساعات (H1 / H4 - مضاربة يومية سريعة {dir_label}):**",
            f"• {zone_label}: `{h_lvl['entry']}` (متوسط: `{h_lvl['avg_entry']}`)",
            f"• وقف الخسارة (SL): `{h_lvl['stop']}` (مخاطرة: `{h_lvl['risk']}$`)",
            f"• الهدف الأول (TP1 - 1:1): `{h_lvl['tp1']}` | الهدف الثاني (TP2 - 1:2): `{h_lvl['tp2']}`",
            f"• نسبة العائد للمخاطرة (R:R): `1 : 2.00` (حقيقية من متوسط الدخول)",
            "",
            f"**📆 2. الفريم اليومي (D1 - صفقة يومية متأرجحة {dir_label}):**",
            f"• {zone_label}: `{d_lvl['entry']}` (متوسط: `{d_lvl['avg_entry']}`)",
            f"• وقف الخسارة (SL): `{d_lvl['stop']}` (مخاطرة: `{d_lvl['risk']}$`)",
            f"• الهدف الأول (TP1 - 1:1): `{d_lvl['tp1']}` | الهدف الثاني (TP2 - 1:2): `{d_lvl['tp2']}`",
            f"• نسبة العائد للمخاطرة (R:R): `1 : 2.00` (حقيقية من متوسط الدخول)",
            "",
            f"**🗓️ 3. الفريم الأسبوعي (W1 - تمركز أسبوعي {dir_label}):**",
            f"• {zone_label}: `{w_lvl['entry']}` (متوسط: `{w_lvl['avg_entry']}`)",
            f"• وقف الخسارة (SL): `{w_lvl['stop']}` (مخاطرة: `{w_lvl['risk']}$`)",
            f"• الهدف الأول (TP1 - 1:1): `{w_lvl['tp1']}` | الهدف الثاني (TP2 - 1:2): `{w_lvl['tp2']}`",
            f"• نسبة العائد للمخاطرة (R:R): `1 : 2.00` (حقيقية من متوسط الدخول)",
        ])
    elif not hard_stop and risk.get("stop") and risk.get("tp1"):
        lines.extend([
            "",
            "**📌 مستويات التنفيذ الأساسية:**",
            f"• السعر المرجعي: `{ref_str}`",
            f"• وقف الخسارة (SL): `{risk.get('stop')}`",
            f"• الهدف الأول (TP1): `{risk.get('tp1')}` | الهدف الثاني (TP2): `{risk.get('tp2')}`",
        ])

    trend_ar = {"bullish": "صاعد", "bearish": "هابط", "neutral": "محايد"}.get(
        str(technical.get("trend_direction") or ""), "محايد"
    )
    mom_ar = {"bullish": "إيجابي", "bearish": "سلبي", "neutral": "محايد"}.get(
        str(technical.get("momentum_direction") or ""), "محايد"
    )

    review_display = "غير مطلوبة"
    if gov_review:
        review_display = f"مطلوبة ({gov_reason})" if gov_reason else "مطلوبة"

    lines.extend([
        "",
        "**🧭 سياق السوق والفحص الفني:**",
        f"• النظام الكلي: {regime_ar}",
        f"• الفحص الفني: الاتجاه {trend_ar} | الزخم {mom_ar} | الهيكل `{technical.get('structure_state') or 'range'}`",
        f"• الأخبار المرصودة: `{news.get('article_count') if news.get('article_count') is not None else 'غير متاح'}` خبر (`{news.get('directional_count') if news.get('directional_count') is not None else 'غير متاح'}` مؤثر اتجاهياً)",
        f"• فحص التحيز: `{governance.get('bias_severity') or 'غير متاح'}` | مراجعة بشرية: `{review_display}`",
        "",
        "💡 *القرار النهائي للدخول وإدارة حجم العقد يعود لتقديرك الشخصي على الشارت.*",
    ])
    return "\n".join(lines)


__all__ = [
    "SCHEMA_VERSION",
    "SUMMARY_FILENAME",
    "TIMEFRAME_PULLBACK_CONFIGS",
    "build_summary",
    "write_summary",
    "format_telegram_compact",
    "format_telegram_arabic_trade_card",
    "_compute_timeframe_levels",
    "resolve_macro_event_label",
]
