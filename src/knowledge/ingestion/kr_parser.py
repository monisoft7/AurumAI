from __future__ import annotations

import re
from typing import Any

FIELD_MAP: dict[str, str] = {
    "title": "title",
    "category": "category",
    "mechanism": "mechanism",
    "preconditions": "preconditions",
    "trigger": "trigger",
    "expected gold impact": "expected_impact",
    "strength": "strength",
    "confidence": "confidence",
    "historical evidence": "historical_evidence",
    "counter examples": "counter_examples",
    "regime dependence": "regime_dependence",
    "failure conditions": "failure_conditions",
    "references": "references",
}

CONFIDENCE_MAP: dict[str, float] = {
    "very high": 0.95,
    "high": 0.85,
    "medium-high": 0.75,
    "medium": 0.50,
    "medium-low": 0.30,
    "low": 0.15,
    "very low": 0.05,
}

STRENGTH_MAP: dict[str, float] = {
    "very strong": 0.95,
    "strong": 0.85,
    "moderate": 0.50,
    "weak": 0.20,
}

KR_HEADER_RE = re.compile(r"^### (KR-\d+)")


def _normalize_field_name(raw: str) -> str:
    key = raw.strip().lower().rstrip(":")
    return FIELD_MAP.get(key, key)


def _parse_confidence(text: str) -> float:
    text_lower = text.strip().lower().rstrip(".")
    for phrase, value in sorted(CONFIDENCE_MAP.items(), key=lambda x: -len(x[0])):
        if phrase in text_lower:
            return value
    return 0.0


def _parse_bias(expected_impact: str) -> str:
    text = expected_impact.lower()
    negative_words = ["inverse", "bearish", "headwind", "negative", "decline", "fall", "pressure"]
    positive_words = ["positive", "bullish", "support", "rally", "appreciate", "gain", "rise", "supportive"]
    mixed_words = ["mixed", "depends", "asymmetric", "indirect", "non-binding"]
    has_negative = any(w in text for w in negative_words)
    has_positive = any(w in text for w in positive_words)
    has_mixed = any(w in text for w in mixed_words)
    if has_mixed:
        return "mixed"
    if has_positive and has_negative:
        return "mixed"
    if has_positive:
        return "bullish"
    if has_negative:
        return "bearish"
    return "neutral"


def _parse_strength(text: str) -> float:
    text_lower = text.strip().lower().rstrip(".")
    for phrase, value in sorted(STRENGTH_MAP.items(), key=lambda x: -len(x[0])):
        if phrase in text_lower:
            return value
    return 0.5


def parse_kr_section(lines: list[str]) -> dict[str, Any]:
    """Parse a single KR section into a structured dict matching KnowledgeRecord schema."""
    kr: dict[str, Any] = {
        "asset": "gold",
        "condition": {},
        "horizon_days": 0,
        "sample_count": 0,
        "positive_return_rate_pct": 0.0,
        "negative_return_rate_pct": 0.0,
        "up_direction_rate_pct": 0.0,
        "down_direction_rate_pct": 0.0,
        "flat_direction_rate_pct": 0.0,
        "average_return_pct": 0.0,
        "median_return_pct": 0.0,
        "min_return_pct": 0.0,
        "max_return_pct": 0.0,
        "first_event_date": "",
        "last_event_date": "",
        "source_lesson_ids": (),
        "source_artifact_path": "",
        "source_artifact_sha256": "",
        "provenance": None,
        "metadata": {},
        "institutional_context": {},
    }

    header_match = KR_HEADER_RE.match(lines[0])
    if header_match:
        kr["knowledge_id"] = header_match.group(1)

    raw_fields: dict[str, str] = {}
    for line in lines[1:]:
        match = re.match(r"^-\s*(.+?):\s*(.*)", line)
        if match:
            raw_key = match.group(1).strip()
            raw_value = match.group(2).strip()
            normalized = _normalize_field_name(raw_key)
            raw_fields[normalized] = raw_value

    kr["title"] = raw_fields.get("title", "")
    kr["explanation"] = raw_fields.get("title", "")
    kr["category"] = raw_fields.get("category", "")
    kr["mechanism"] = raw_fields.get("mechanism", "")
    kr["preconditions"] = raw_fields.get("preconditions", "")
    kr["trigger"] = raw_fields.get("trigger", "")
    kr["expected_impact"] = raw_fields.get("expected_impact", "")
    kr["failure_conditions"] = raw_fields.get("failure_conditions", "")
    kr["counter_examples"] = raw_fields.get("counter_examples", "")
    kr["regime_dependence"] = raw_fields.get("regime_dependence", "")
    kr["references"] = raw_fields.get("references", "")

    strength_text = raw_fields.get("strength", "")
    confidence_text = raw_fields.get("confidence", "")

    kr["bias"] = _parse_bias(kr["expected_impact"])
    kr["confidence"] = _parse_confidence(confidence_text)

    kr["metadata"] = {
        "strength": strength_text,
        "strength_score": _parse_strength(strength_text),
        "confidence_text": confidence_text,
        "historical_evidence": raw_fields.get("historical_evidence", ""),
        "kb_source": "Institutional_Gold_Knowledge_Base.md",
        "kb_version": "1.0",
    }

    cat = kr.get("category", "").lower()
    if "central bank" in cat:
        kr["event_type"] = "CB_GOLD"
        kr["condition"] = {"driver": "central_bank_demand"}
    elif "etf" in cat:
        kr["event_type"] = "ETF_FLOW"
        kr["condition"] = {"driver": "etf_flows"}
    elif "real yield" in cat or "interest rate" in cat:
        kr["event_type"] = "REAL_YIELD"
        kr["condition"] = {"driver": "real_yields"}
    elif "usd" in cat or "fx" in cat or "dollar" in cat:
        kr["event_type"] = "USD_FX"
        kr["condition"] = {"driver": "usd_fx"}
    elif "inflation" in cat or "breakeven" in cat:
        kr["event_type"] = "INFLATION"
        kr["condition"] = {"driver": "inflation_breakevens"}
    elif "geopolitical" in cat:
        kr["event_type"] = "GEOPOLITICAL"
        kr["condition"] = {"driver": "geopolitical_risk"}
    else:
        kr["event_type"] = "GENERAL"
        kr["condition"] = {"driver": "general"}

    return kr


def parse_kb_document(path: str) -> list[dict[str, Any]]:
    """Parse the full Institutional Gold Knowledge Base markdown document."""
    with open(path, encoding="utf-8") as f:
        content = f.read()

    sections = re.split(r"\n(?=### KR-\d+)", content)
    results: list[dict[str, Any]] = []
    for section in sections:
        section = section.strip()
        if not section.startswith("### KR-"):
            continue
        lines = section.split("\n")
        kr = parse_kr_section(lines)
        results.append(kr)
    return results
