"""AurumAI Institutional Daily Report generator.

Reporting layer only: transforms the serialized pipeline outputs already
written under ``outputs/YYYY-MM-DD/<pipeline_id>/`` into
``institutional_report.md`` and ``institutional_report.html``.

This script never computes, recalculates, or invents values. Every figure
in the report is a value the pipeline already wrote to disk; the only
transformations applied are presentational (number formatting, markup).

Usage:
    python scripts/generate_institutional_report.py [--date YYYY-MM-DD]
    python scripts/generate_institutional_report.py [--output-dir PATH]

``--date`` resolves to the most recent run under ``outputs/<date>/``;
``--output-dir`` may point directly at a run directory or at a date
directory. Legacy flat run directories (``outputs/YYYY-MM-DD/`` holding the
run files directly) are resolved as well.

Exit codes:
    0  report generated
    2  inputs missing or invalid
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from runtime_registry.outputs import is_run_dir, latest_run_dir  # noqa: E402

EXIT_OK = 0
EXIT_INPUT_ERROR = 2

REPORT_TITLE = "AurumAI Institutional Daily Report"


@dataclass(frozen=True)
class Section:
    number: int
    title: str
    md: str
    html: str


# ---------------------------------------------------------------------------
# Formatting helpers (presentation only)
# ---------------------------------------------------------------------------


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if value != value:
            return "n/a"
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def _pct(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if v != v:
        return "n/a"
    return f"{v * 100.0:.2f}%"


def _scaled(value: Any) -> str:
    return f"{_fmt(value)} ({_pct(value)})"


def _md_escape(text: Any) -> str:
    s = str(text)
    for token in ("\\", "|", "*", "_", "`"):
        s = s.replace(token, "\\" + token)
    return s


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _parse_kv(explanation: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in str(explanation).split(";"):
        if "=" in part:
            key, _, value = part.partition("=")
            result[key.strip()] = value.strip()
    return result


def _kv(explanation: Any, key: str) -> str:
    return _parse_kv(str(explanation)).get(key, "")


def _strip_paren(value: str) -> str:
    idx = value.find(" (")
    return value[:idx] if idx != -1 else value


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return ""
    lines = [
        "| " + " | ".join(_md_escape(h) for h in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_md_escape(c) for c in row) + " |")
    return "\n".join(lines)


def _html_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return ""
    parts = ["<table>", "<thead><tr>"]
    parts.extend(f"<th>{html.escape(h)}</th>" for h in headers)
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        parts.extend(f"<td>{html.escape(c)}</td>" for c in row)
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _md_list(items: list[str]) -> str:
    return "\n".join(f"- {_md_escape(item)}" for item in items)


def _html_list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def _md_pre(text: Any) -> str:
    return "```\n" + str(text).strip() + "\n```"


def _html_pre(text: Any) -> str:
    return "<pre>" + html.escape(str(text).strip()) + "</pre>"


def _md_para(text: Any) -> str:
    return str(text)


def _html_para(text: Any) -> str:
    return f"<p>{html.escape(str(text))}</p>"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _driver_rows(decision: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for driver in decision.get("decision_drivers", []):
        rows.append(
            [
                str(driver.get("name", "")),
                _fmt(driver.get("value")),
                _fmt(driver.get("score")),
                _fmt(driver.get("weight")),
            ]
        )
    return rows


def build_sections(data: dict[str, Any]) -> list[Section]:
    cfg = data.get("config", {}) or {}
    summary = data.get("summary", {}) or {}
    finalize = data.get("finalize", {}) or {}
    stages = data.get("stages") or []

    context = finalize.get("context", {}) or {}
    confidence = finalize.get("confidence", {}) or {}
    decision = finalize.get("decision", {}) or {}
    forecast = finalize.get("forecast_result", {}) or {}
    validation = finalize.get("validation", {}) or {}
    risk_metrics = finalize.get("risk_metrics", {}) or {}
    risk_decision = finalize.get("risk_decision", {}) or {}
    position_sizing = finalize.get("position_sizing", {}) or {}
    risk_budget = finalize.get("risk_budget", {}) or {}

    metadata = decision.get("metadata", {}) or {}
    bias_review = metadata.get("bias_review", {}) or {}
    explanation = decision.get("decision_explanation", "")
    kv = _parse_kv(explanation)
    drivers = decision.get("decision_drivers", [])
    rejected = decision.get("rejected_alternatives", [])

    def driver(driver_name: str) -> dict[str, Any]:
        for d in drivers:
            if d.get("name") == driver_name:
                return d
        return {}

    sections: list[Section] = []

    # 1 -----------------------------------------------------------------
    stage_counts = summary.get("stage_counts", {}) or {}
    status_line = (
        "completed with no errors"
        if summary.get("success")
        else "completed with errors"
    )
    md_1 = [
        f"- **Decision:** {_md_escape(summary.get('decision'))}",
        f"- **Decision confidence:** {_fmt(summary.get('decision_confidence'))}",
        f"- **Event type:** {_md_escape(summary.get('event_type'))}",
        f"- **Asset:** {_md_escape(cfg.get('asset'))} | **Horizon:** {_fmt(cfg.get('horizon'))} months",
        f"- **Economic data:** {_md_escape(summary.get('data_path'))}",
        f"- **Gold data:** {_md_escape(summary.get('gold_path'))}",
        f"- **Pipeline status:** {status_line} (stages ok: {stage_counts.get('ok')})",
        f"- **Pipeline ID:** {_md_escape(summary.get('pipeline_id'))}",
        f"- **Run timestamp:** {_md_escape(summary.get('timestamp'))}",
        f"- **Wall time:** {_fmt(summary.get('wall_time_seconds'))} s",
    ]
    failed_stages = summary.get("failed_stages", [])
    if failed_stages:
        md_1.append(f"- **Failed stages:** {_md_escape(', '.join(failed_stages))}")
    errors = summary.get("errors", [])
    if errors:
        md_1.append(f"- **Errors:** {_md_escape('; '.join(str(e) for e in errors))}")
    md_1 = "\n".join(md_1)

    rows_1 = [
        ["Decision", _fmt(summary.get("decision"))],
        ["Decision confidence", _fmt(summary.get("decision_confidence"))],
        ["Event type", _fmt(summary.get("event_type"))],
        ["Asset", _fmt(cfg.get("asset"))],
        ["Horizon (months)", _fmt(cfg.get("horizon"))],
        ["Economic data", _fmt(summary.get("data_path"))],
        ["Gold data", _fmt(summary.get("gold_path"))],
        ["Pipeline status", status_line],
        ["Stages ok", _fmt(stage_counts.get("ok"))],
        ["Pipeline ID", _fmt(summary.get("pipeline_id"))],
        ["Run timestamp", _fmt(summary.get("timestamp"))],
        ["Wall time (s)", _fmt(summary.get("wall_time_seconds"))],
    ]
    if failed_stages:
        rows_1.append(["Failed stages", _fmt(", ".join(failed_stages))])
    if errors:
        rows_1.append(["Errors", _fmt("; ".join(str(e) for e in errors))])
    html_1 = _html_table(["Field", "Value"], rows_1)

    sections.append(Section(1, "Executive Summary", md_1, html_1))

    # 2 -----------------------------------------------------------------
    date_range = context.get("data_date_range") or []
    range_text = " to ".join(_fmt(d) for d in date_range)
    md_2 = [
        f"- **Current regime:** {_md_escape(context.get('current_regime'))}",
        f"- **Regime confidence:** {_scaled(context.get('regime_confidence'))}",
        f"- **Regime source variable:** {_md_escape(context.get('source_variable'))}",
        f"- **Data date range:** {_md_escape(range_text)}",
        f"- **News mood:** {_md_escape(_fmt(context.get('news_mood')))} (confidence {_scaled(context.get('news_confidence'))})",
        f"- **FOMC mood:** {_md_escape(_fmt(context.get('fomc_mood')))} (confidence {_scaled(context.get('fomc_confidence'))})",
        f"- **Context timestamp:** {_md_escape(context.get('context_timestamp'))}",
    ]
    rows_2 = [
        ["Current regime", _fmt(context.get("current_regime"))],
        ["Regime confidence", _scaled(context.get("regime_confidence"))],
        ["Source variable", _fmt(context.get("source_variable"))],
        ["Data date range", range_text],
        ["News mood", _fmt(context.get("news_mood"))],
        ["News confidence", _scaled(context.get("news_confidence"))],
        ["FOMC mood", _fmt(context.get("fomc_mood"))],
        ["FOMC confidence", _scaled(context.get("fomc_confidence"))],
        ["Context timestamp", _fmt(context.get("context_timestamp"))],
    ]
    sections.append(
        Section(
            2,
            "Market Regime",
            "\n".join(md_2),
            _html_table(["Field", "Value"], rows_2),
        )
    )

    # 3 -----------------------------------------------------------------
    events = context.get("recent_events", [])
    if events:
        headers = ["Event type", "Date", "Condition", "Gold direction", "Gold return %"]
        md_rows = [
            [
                str(e.get("event_type", "")),
                str(e.get("date", "")),
                str(e.get("condition", "")),
                str(e.get("gold_direction", "")),
                _fmt(e.get("gold_return_pct")),
            ]
            for e in events
        ]
        md_3 = (
            f"Focal event type analyzed: **{_md_escape(summary.get('event_type'))}**.\n\n"
            "Recent economic events recorded by the pipeline:\n\n"
            + _md_table(headers, md_rows)
        )
        html_3 = (
            _html_para(f"Focal event type analyzed: {summary.get('event_type')}.")
            + _html_para("Recent economic events recorded by the pipeline:")
            + _html_table(headers, md_rows)
        )
    else:
        md_3 = (
            f"Focal event type analyzed: **{_md_escape(summary.get('event_type'))}**. "
            "No recent economic events were recorded by the pipeline for this run."
        )
        html_3 = _html_para(
            f"Focal event type analyzed: {summary.get('event_type')}. "
            "No recent economic events were recorded by the pipeline for this run."
        )
    sections.append(Section(3, "Key Economic Events", md_3, html_3))

    # 4 -----------------------------------------------------------------
    ev_quality = driver("evidence_quality")
    counter_quality = driver("counter_evidence_quality")
    legacy = finalize.get("legacy_decision", {}) or {}
    legacy_meta = legacy.get("metadata", {}) or {}
    ev_lines = [
        f"- **Evidence quality:** value {_fmt(ev_quality.get('value'))} | score {_fmt(ev_quality.get('score'))} | weight {_fmt(ev_quality.get('weight'))}",
        f"- **Counter-evidence quality:** value {_fmt(counter_quality.get('value'))} | score {_fmt(counter_quality.get('score'))} | weight {_fmt(counter_quality.get('weight'))}",
    ]
    bias_lines: list[str] = []
    if bias_review:
        bias_lines = [
            f"- **Bias review id:** {_md_escape(bias_review.get('review_id'))}",
            f"- **Overall severity:** {_md_escape(bias_review.get('overall_severity'))}",
            f"- **Total confidence impact:** {_scaled(bias_review.get('total_confidence_impact'))}",
            f"- **Human review required:** {_fmt(bias_review.get('human_review_flag'))}",
            f"- **Bias findings:** {_md_escape(', '.join(str(f) for f in bias_review.get('findings', []))) or 'none'}",
        ]
    legacy_lines = [
        f"- **Legacy evidence count:** {_fmt(legacy.get('evidence_count'))}",
        f"- **Legacy chain confidence:** {_scaled(legacy_meta.get('chain_confidence'))}",
        f"- **Legacy average return %:** {_fmt(legacy_meta.get('avg_return_pct'))}",
        f"- **Legacy reasoning chain:** {_md_escape(legacy.get('reasoning_chain_id'))}",
    ]
    md_4 = (
        "\n".join(ev_lines)
        + "\n\n**Bias prevention review**\n\n"
        + ("\n".join(bias_lines) if bias_lines else "- No bias review recorded on the decision.")
        + "\n\n**Legacy pipeline evidence (for reference)**\n\n"
        + "\n".join(legacy_lines)
    )
    html_parts = [
        _html_table(
            ["Evidence driver", "Value", "Score", "Weight"],
            [
                [
                    "Evidence quality",
                    _fmt(ev_quality.get("value")),
                    _fmt(ev_quality.get("score")),
                    _fmt(ev_quality.get("weight")),
                ],
                [
                    "Counter-evidence quality",
                    _fmt(counter_quality.get("value")),
                    _fmt(counter_quality.get("score")),
                    _fmt(counter_quality.get("weight")),
                ],
            ],
        ),
        "<h3>Bias prevention review</h3>",
    ]
    if bias_review:
        html_parts.append(
            _html_table(
                ["Field", "Value"],
                [
                    ["Review id", _fmt(bias_review.get("review_id"))],
                    ["Overall severity", _fmt(bias_review.get("overall_severity"))],
                    ["Total confidence impact", _scaled(bias_review.get("total_confidence_impact"))],
                    ["Human review required", _fmt(bias_review.get("human_review_flag"))],
                    [
                        "Bias findings",
                        _fmt(", ".join(str(f) for f in bias_review.get("findings", []))),
                    ],
                ],
            )
        )
    else:
        html_parts.append(_html_para("No bias review recorded on the decision."))
    html_parts.extend(
        [
            "<h3>Legacy pipeline evidence (for reference)</h3>",
            _html_table(
                ["Field", "Value"],
                [
                    ["Evidence count", _fmt(legacy.get("evidence_count"))],
                    ["Chain confidence", _scaled(legacy_meta.get("chain_confidence"))],
                    ["Average return %", _fmt(legacy_meta.get("avg_return_pct"))],
                    ["Reasoning chain id", _fmt(legacy.get("reasoning_chain_id"))],
                ],
            ),
        ]
    )
    sections.append(Section(4, "Evidence Summary", md_4, "".join(html_parts)))

    # 5 -----------------------------------------------------------------
    selected_thesis_raw = _kv(explanation, "selected_thesis")
    selected_thesis_id = _strip_paren(selected_thesis_raw)
    rejected_rows = [
        [
            str(r.get("thesis_id", "")),
            str(r.get("thesis_direction", "")),
            _fmt(r.get("composite_score")),
            str(r.get("rejection_reason", "")),
        ]
        for r in rejected
    ]
    md_5 = [
        f"- **Selected thesis id:** {_md_escape(selected_thesis_id)}",
        f"- **Selected thesis direction:** {_md_escape(metadata.get('selected_thesis_direction'))}",
        f"- **Theses evaluated:** {_fmt(metadata.get('total_theses_evaluated'))}",
        f"- **Rejected alternatives:** {_fmt(metadata.get('total_rejected_alternatives'))}",
    ]
    if rejected_rows:
        md_5.append(
            "\nRejected alternative theses:\n\n"
            + _md_table(
                ["Thesis id", "Direction", "Composite score", "Rejection reason"],
                rejected_rows,
            )
        )
    html_parts = [
        _html_table(
            ["Field", "Value"],
            [
                ["Selected thesis id", _fmt(selected_thesis_id)],
                ["Selected thesis direction", _fmt(metadata.get("selected_thesis_direction"))],
                ["Theses evaluated", _fmt(metadata.get("total_theses_evaluated"))],
                ["Rejected alternatives", _fmt(metadata.get("total_rejected_alternatives"))],
            ],
        )
    ]
    if rejected_rows:
        html_parts.append(
            _html_para("Rejected alternative theses:")
            + _html_table(
                ["Thesis id", "Direction", "Composite score", "Rejection reason"],
                rejected_rows,
            )
        )
    sections.append(Section(5, "Institutional Thesis", "\n".join(md_5), "".join(html_parts)))

    # 6 -----------------------------------------------------------------
    conf_driver = driver("institutional_confidence")
    md_6 = [
        f"- **Overall forecast confidence:** {_scaled(confidence.get('overall'))}",
        f"- **Agreement score:** {_scaled(confidence.get('agreement_score'))}",
        f"- **Context coherence:** {_scaled(confidence.get('context_coherence'))}",
        f"- **Spread score:** {_scaled(confidence.get('spread_score'))}",
        f"- **Institutional confidence (decision):** {_scaled(decision.get('institutional_confidence'))}",
        f"- **Institutional confidence driver:** value {_fmt(conf_driver.get('value'))} | score {_fmt(conf_driver.get('score'))} | weight {_fmt(conf_driver.get('weight'))}",
    ]
    rows_6 = [
        ["Overall forecast confidence", _scaled(confidence.get("overall"))],
        ["Agreement score", _scaled(confidence.get("agreement_score"))],
        ["Context coherence", _scaled(confidence.get("context_coherence"))],
        ["Spread score", _scaled(confidence.get("spread_score"))],
        ["Institutional confidence (decision)", _scaled(decision.get("institutional_confidence"))],
        [
            "Institutional confidence driver",
            f"value {_fmt(conf_driver.get('value'))} | score {_fmt(conf_driver.get('score'))} | weight {_fmt(conf_driver.get('weight'))}",
        ],
    ]
    sections.append(
        Section(6, "Confidence Assessment", "\n".join(md_6), _html_table(["Field", "Value"], rows_6))
    )

    # 7 -----------------------------------------------------------------
    scenario_driver = driver("scenario_probability")
    selected_scenario_raw = _kv(explanation, "selected_scenario")
    selected_scenario_id = _strip_paren(selected_scenario_raw)
    md_7 = [
        f"- **Selected scenario id:** {_md_escape(selected_scenario_id)}",
        f"- **Selected scenario type:** {_md_escape(metadata.get('selected_scenario_type'))}",
        f"- **Scenario probability driver:** value {_fmt(scenario_driver.get('value'))} | score {_fmt(scenario_driver.get('score'))} | weight {_fmt(scenario_driver.get('weight'))}",
    ]
    if selected_scenario_raw != selected_scenario_id:
        md_7.append(
            f"- **Scenario detail:** {_md_escape(selected_scenario_raw)} (as recorded in the decision explanation)"
        )
    md_7 = "\n".join(md_7)
    rows_7 = [
        ["Selected scenario id", _fmt(selected_scenario_id)],
        ["Selected scenario type", _fmt(metadata.get("selected_scenario_type"))],
        [
            "Scenario probability driver",
            f"value {_fmt(scenario_driver.get('value'))} | score {_fmt(scenario_driver.get('score'))} | weight {_fmt(scenario_driver.get('weight'))}",
        ],
    ]
    if selected_scenario_raw != selected_scenario_id:
        rows_7.append(["Scenario detail (from decision explanation)", selected_scenario_raw])
    sections.append(
        Section(7, "Scenario Analysis", md_7, _html_table(["Field", "Value"], rows_7))
    )

    # 8 -----------------------------------------------------------------
    rr_driver = driver("risk_reward_quality")
    rr_status = kv.get("risk_reward_status", "")
    rr_ratio = kv.get("risk_reward_ratio", "")
    w12_notes = [
        str(r.get("rejection_reason", ""))
        for r in rejected
        if "W12" in str(r.get("rejection_reason", ""))
    ]
    md_8 = [
        f"- **Risk/reward quality driver:** value {_fmt(rr_driver.get('value'))} | score {_fmt(rr_driver.get('score'))} | weight {_fmt(rr_driver.get('weight'))}",
    ]
    if rr_status:
        md_8.append(f"- **Risk/reward status:** {_md_escape(rr_status)}")
    if rr_ratio:
        md_8.append(f"- **Risk/reward ratio:** {_md_escape(rr_ratio)}")
    if w12_notes:
        md_8.append("\nRisk/reward validation notes from rejected alternatives:\n\n" + "\n".join(f"- {_md_escape(n)}" for n in w12_notes))
    rows_8 = [
        [
            "Risk/reward quality driver",
            f"value {_fmt(rr_driver.get('value'))} | score {_fmt(rr_driver.get('score'))} | weight {_fmt(rr_driver.get('weight'))}",
        ]
    ]
    if rr_status:
        rows_8.append(["Risk/reward status", rr_status])
    if rr_ratio:
        rows_8.append(["Risk/reward ratio", rr_ratio])
    html_8 = _html_table(["Field", "Value"], rows_8)
    if w12_notes:
        html_8 += _html_para("Risk/reward validation notes from rejected alternatives:")
        html_8 += _html_list(w12_notes)
    sections.append(Section(8, "Risk / Reward Summary", "\n".join(md_8), html_8))

    # 9 -----------------------------------------------------------------
    md_9 = [
        f"- **Decision:** {_md_escape(decision.get('decision'))}",
        f"- **Decision id:** {_md_escape(decision.get('decision_id'))}",
        f"- **Institutional confidence:** {_scaled(decision.get('institutional_confidence'))}",
        f"- **Composite score:** {_fmt(metadata.get('composite_score'))}",
        "\n**Decision drivers**\n\n"
        + _md_table(["Driver", "Value", "Score", "Weight"], _driver_rows(decision)),
        "\n**Decision explanation (verbatim)**\n\n" + _md_pre(explanation),
    ]
    html_9 = (
        _html_table(
            ["Field", "Value"],
            [
                ["Decision", _fmt(decision.get("decision"))],
                ["Decision id", _fmt(decision.get("decision_id"))],
                ["Institutional confidence", _scaled(decision.get("institutional_confidence"))],
                ["Composite score", _fmt(metadata.get("composite_score"))],
            ],
        )
        + "<h3>Decision drivers</h3>"
        + _html_table(["Driver", "Value", "Score", "Weight"], _driver_rows(decision))
        + "<h3>Decision explanation (verbatim)</h3>"
        + _html_pre(explanation)
    )
    sections.append(Section(9, "Final Institutional Decision", "\n".join(md_9), html_9))

    # 10 ----------------------------------------------------------------
    components = risk_decision.get("components", {}) or {}
    comp_lines = [
        f"- **Risk gate action:** {_md_escape(risk_decision.get('action'))} (score {_scaled(risk_decision.get('score'))})",
        f"- **Risk gate reason:** {_md_escape(risk_decision.get('reason'))}",
    ]
    for key in ("regime_acceptable", "uncertainty_acceptable", "has_room_to_act", "not_halted", "not_caution"):
        if key in components:
            comp_lines.append(f"- **{key}:** {_fmt(components.get(key))}")
    md_10 = [
        f"The institutional decision is **{_md_escape(decision.get('decision'))}**; "
        "no trade action is recommended.",
        "",
        "**Forecast risk gate (informs sizing)**",
        "",
        "\n".join(comp_lines),
        "",
        "**Position sizing**",
        "",
        _md_table(
            ["Field", "Value"],
            [
                ["Scaling factor", _scaled(position_sizing.get("scaling_factor"))],
                ["Target volatility", _fmt(position_sizing.get("target_vol"))],
                ["Current volatility", _fmt(position_sizing.get("current_vol"))],
                ["Drawdown state", _fmt(position_sizing.get("drawdown_state"))],
                ["Kelly cap", _fmt(position_sizing.get("kelly_cap"))],
            ],
        ),
        "",
        "**Risk budget**",
        "",
        _md_table(
            ["Field", "Value"],
            [
                ["Method", _fmt(risk_budget.get("method"))],
                ["Weights", _fmt(", ".join(_fmt(w) for w in risk_budget.get("weights", [])))],
                ["Risk contributions", _fmt(", ".join(_fmt(c) for c in risk_budget.get("risk_contributions", [])))],
            ],
        ),
    ]
    sizing_rows = [
        ["Scaling factor", _scaled(position_sizing.get("scaling_factor"))],
        ["Target volatility", _fmt(position_sizing.get("target_vol"))],
        ["Current volatility", _fmt(position_sizing.get("current_vol"))],
        ["Drawdown state", _fmt(position_sizing.get("drawdown_state"))],
        ["Kelly cap", _fmt(position_sizing.get("kelly_cap"))],
    ]
    budget_rows = [
        ["Method", _fmt(risk_budget.get("method"))],
        ["Weights", _fmt(", ".join(_fmt(w) for w in risk_budget.get("weights", [])))],
        [
            "Risk contributions",
            _fmt(", ".join(_fmt(c) for c in risk_budget.get("risk_contributions", []))),
        ],
    ]
    component_display = [
        [key, _fmt(components.get(key))]
        for key in (
            "regime_acceptable",
            "uncertainty_acceptable",
            "has_room_to_act",
            "not_halted",
            "not_caution",
        )
        if key in components
    ]
    html_10 = (
        _html_para(
            f"The institutional decision is {decision.get('decision')}; no trade action is recommended."
        )
        + "<h3>Forecast risk gate (informs sizing)</h3>"
        + _html_table(
            ["Field", "Value"],
            [
                [
                    "Risk gate action",
                    f"{_fmt(risk_decision.get('action'))} (score {_scaled(risk_decision.get('score'))})",
                ],
                ["Risk gate reason", _fmt(risk_decision.get("reason"))],
            ]
            + component_display,
        )
        + "<h3>Position sizing</h3>"
        + _html_table(["Field", "Value"], sizing_rows)
        + "<h3>Risk budget</h3>"
        + _html_table(["Field", "Value"], budget_rows)
    )
    sections.append(Section(10, "Trade Recommendation", "\n".join(md_10), html_10))

    # 11 ----------------------------------------------------------------
    preconditions = decision.get("preconditions", [])
    md_11 = (
        _md_list(preconditions)
        if preconditions
        else "No preconditions were recorded on the institutional decision."
    )
    html_11 = (
        _html_list(preconditions)
        if preconditions
        else _html_para("No preconditions were recorded on the institutional decision.")
    )
    sections.append(Section(11, "Preconditions", md_11, html_11))

    # 12 ----------------------------------------------------------------
    invalidation = decision.get("invalidation_conditions", [])
    md_12 = (
        _md_list(invalidation)
        if invalidation
        else "No invalidation conditions were recorded on the institutional decision."
    )
    html_12 = (
        _html_list(invalidation)
        if invalidation
        else _html_para("No invalidation conditions were recorded on the institutional decision.")
    )
    sections.append(Section(12, "Invalidation Conditions", md_12, html_12))

    # 13 ----------------------------------------------------------------
    val_metrics = validation.get("metrics", {}) or {}
    tail_text = _fmt(risk_metrics.get("tail_index"))
    if risk_metrics.get("tail_index") is None:
        tail_text = "not detected (null)"
    md_13 = [
        "**Forecast risk measures**",
        "",
        _md_table(
            ["Field", "Value"],
            [
                ["VaR 95", _fmt(risk_metrics.get("var_95"))],
                ["VaR 99", _fmt(risk_metrics.get("var_99"))],
                ["CVaR 95", _fmt(risk_metrics.get("cvar_95"))],
                ["Tail index", tail_text],
                ["Method", _fmt(risk_metrics.get("method"))],
            ],
        ),
        "",
        "**Forecast validation**",
        "",
        _md_table(
            ["Field", "Value"],
            [
                ["Passed", _fmt(validation.get("passed"))],
                ["Sample size", _fmt(validation.get("sample_size"))],
                ["Strategy", _fmt(validation.get("validation_strategy"))],
                ["Notes", _fmt(validation.get("notes"))],
            ],
        ),
        "",
        "**Validation metrics**",
        "",
        _md_table(
            ["Metric", "Value"],
            [
                ["RMSE", _fmt(val_metrics.get("rmse"))],
                ["MAE", _fmt(val_metrics.get("mae"))],
                ["MAPE", _fmt(val_metrics.get("mape"))],
                ["Coverage", _scaled(val_metrics.get("coverage"))],
                ["Directional accuracy", _scaled(val_metrics.get("directional_accuracy"))],
            ],
        ),
        "",
        "**Risk gate components**",
        "",
        _md_table(
            ["Component", "Value"],
            [
                [key, _fmt(components.get(key))]
                for key in (
                    "regime_acceptable",
                    "uncertainty_acceptable",
                    "has_room_to_act",
                    "not_halted",
                    "not_caution",
                )
                if key in components
            ],
        ),
        "",
        "**Bias review**",
        "",
        _md_table(
            ["Field", "Value"],
            [
                ["Overall severity", _fmt(bias_review.get("overall_severity"))],
                ["Total confidence impact", _scaled(bias_review.get("total_confidence_impact"))],
                ["Human review required", _fmt(bias_review.get("human_review_flag"))],
            ],
        ),
    ]
    risk_metrics_rows = [
        ["VaR 95", _fmt(risk_metrics.get("var_95"))],
        ["VaR 99", _fmt(risk_metrics.get("var_99"))],
        ["CVaR 95", _fmt(risk_metrics.get("cvar_95"))],
        ["Tail index", tail_text],
        ["Method", _fmt(risk_metrics.get("method"))],
    ]
    validation_rows = [
        ["Passed", _fmt(validation.get("passed"))],
        ["Sample size", _fmt(validation.get("sample_size"))],
        ["Strategy", _fmt(validation.get("validation_strategy"))],
        ["Notes", _fmt(validation.get("notes"))],
    ]
    metrics_rows = [
        ["RMSE", _fmt(val_metrics.get("rmse"))],
        ["MAE", _fmt(val_metrics.get("mae"))],
        ["MAPE", _fmt(val_metrics.get("mape"))],
        ["Coverage", _scaled(val_metrics.get("coverage"))],
        ["Directional accuracy", _scaled(val_metrics.get("directional_accuracy"))],
    ]
    component_rows = [
        [key, _fmt(components.get(key))]
        for key in (
            "regime_acceptable",
            "uncertainty_acceptable",
            "has_room_to_act",
            "not_halted",
            "not_caution",
        )
        if key in components
    ]
    bias_rows = [
        ["Overall severity", _fmt(bias_review.get("overall_severity"))],
        ["Total confidence impact", _scaled(bias_review.get("total_confidence_impact"))],
        ["Human review required", _fmt(bias_review.get("human_review_flag"))],
    ]
    html_13 = (
        "<h3>Forecast risk measures</h3>"
        + _html_table(["Field", "Value"], risk_metrics_rows)
        + "<h3>Forecast validation</h3>"
        + _html_table(["Field", "Value"], validation_rows)
        + "<h3>Validation metrics</h3>"
        + _html_table(["Metric", "Value"], metrics_rows)
        + "<h3>Risk gate components</h3>"
        + _html_table(["Component", "Value"], component_rows)
        + "<h3>Bias review</h3>"
        + _html_table(["Field", "Value"], bias_rows)
    )
    sections.append(Section(13, "Major Risks", "\n".join(md_13), html_13))

    # 14 ----------------------------------------------------------------
    provenance_rows = [
        [
            str(p.get("created_by", "")),
            str(p.get("created_at", "")),
            str(p.get("entity_version", "")),
        ]
        for p in decision.get("provenance_chain", [])
    ]
    stage_rows = [
        [str(s.get("stage_id", "")), str(s.get("status", "")), _fmt(s.get("duration_ms"))]
        for s in stages
    ]
    artifacts_dir = Path(str(summary.get("artifacts_directory", "")))
    artifact_names: list[str] = []
    if artifacts_dir.is_dir():
        artifact_names = sorted(p.name for p in artifacts_dir.iterdir())
    md_14 = [
        "**Decision provenance chain**",
        "",
        _md_table(["Created by", "Created at", "Entity version"], provenance_rows),
        "",
        "**Stage execution records**",
        "",
        _md_table(["Stage", "Status", "Duration (ms)"], stage_rows),
        "",
        "**Artifacts**",
        "",
        "\n".join(f"- {_md_escape(name)}" for name in artifact_names)
        if artifact_names
        else "- No artifact files found.",
        "",
        f"- **Pipeline ID:** {_md_escape(summary.get('pipeline_id'))}",
        f"- **Output directory:** {_md_escape(summary.get('output_directory'))}",
    ]
    html_14 = (
        "<h3>Decision provenance chain</h3>"
        + _html_table(["Created by", "Created at", "Entity version"], provenance_rows)
        + "<h3>Stage execution records</h3>"
        + _html_table(["Stage", "Status", "Duration (ms)"], stage_rows)
        + "<h3>Artifacts</h3>"
        + (
            _html_list(artifact_names)
            if artifact_names
            else _html_para("No artifact files found.")
        )
        + "<p>"
        + f"Pipeline ID: {html.escape(str(summary.get('pipeline_id')))}<br>"
        + f"Output directory: {html.escape(str(summary.get('output_directory')))}"
        + "</p>"
    )
    sections.append(Section(14, "Provenance Summary", "\n".join(md_14), html_14))

    # Final Hardening (Group D): execution levels section.  The finalize
    # payload carries the executable recommendation (entry/stop/target and
    # the market-anchored risk summary) as a first-class artifact.
    recommendation = finalize.get("trade_recommendation") or {}
    if isinstance(recommendation, dict) and recommendation:
        action = recommendation.get("recommendation_action", "")
        levels_rows: list[list[str]] = []
        if action in ("BUY", "SELL"):
            entry_zone = recommendation.get("entry_zone") or ()
            levels_rows.append(["Action", _md_escape(action), ""])
            if len(entry_zone) >= 1:
                levels_rows.append(["Entry zone", _md_escape(" - ".join(str(e) for e in entry_zone)), ""])
            levels_rows.append(["Stop loss", _md_escape(recommendation.get("stop_loss", "")), ""])
            levels_rows.append(["Take profit 1", _md_escape(recommendation.get("take_profit_1", "")), ""])
            levels_rows.append(["Take profit 2", _md_escape(recommendation.get("take_profit_2", "")), ""])
            levels_rows.append(["Risk %", str(recommendation.get("risk_pct", "")), ""])
            levels_rows.append(
                ["Holding days", str(recommendation.get("expected_holding_days", "")), ""]
            )
        metadata_14b = recommendation.get("metadata") or {}
        market_summary = metadata_14b.get("market_risk_summary") or {}
        levels_basis = metadata_14b.get("levels_basis", "unknown")
        rr_market = market_summary.get("market_reward_risk_ratio")
        conviction_rr = (decision.get("risk_reward_summary") or {}).get(
            "risk_reward_ratio"
        )
        md_levels = [
            f"**Recommendation:** {_md_escape(action or 'n/a')} "
            f"(levels basis: {_md_escape(levels_basis)})",
            "",
            _md_table(
                ["Level", "Value"],
                [[row[0], row[1]] for row in levels_rows]
                if levels_rows
                else [["Levels", "none emitted for this decision class"]],
            ),
            "",
            "**Risk / reward**",
            "",
            _md_table(
                ["Measure", "Value", "Basis"],
                [
                    [
                        "Market reward:risk",
                        _md_escape(rr_market if rr_market is not None else "n/a"),
                        "ATR-anchored levels",
                    ],
                    [
                        "W12 conviction ratio",
                        _md_escape(
                            conviction_rr if conviction_rr is not None else "n/a"
                        ),
                        "conviction proxy (W12)",
                    ],
                ],
            ),
            "",
            "The W12 conviction ratio measures thesis-conviction quality; the "
            "market reward:risk ratio is computed from the actual ATR-anchored "
            "entry/stop/target levels. They are different measures and are "
            "reported side by side.",
        ]
        html_levels = (
            "<h3>Recommendation</h3>"
            + _html_table(
                ["Level", "Value"],
                [[row[0], row[1]] for row in levels_rows]
                if levels_rows
                else [["Levels", "none emitted for this decision class"]],
            )
            + "<h3>Risk / reward</h3>"
            + _html_table(
                ["Measure", "Value", "Basis"],
                [
                    [
                        "Market reward:risk",
                        str(rr_market if rr_market is not None else "n/a"),
                        "ATR-anchored levels",
                    ],
                    [
                        "W12 conviction ratio",
                        str(conviction_rr if conviction_rr is not None else "n/a"),
                        "conviction proxy (W12)",
                    ],
                ],
            )
        )
        sections.append(
            Section(15, "Execution Levels", "\n".join(md_levels), html_levels)
        )

    # 16 -- Sprint 058 news-intelligence observability (additive).  Rendered
    # only when the ingest_news stage produced its explicit payload so an
    # unavailable/filtered news day can never masquerade as a healthy empty
    # feed in the human-readable report.
    news_intel = finalize.get("news_intelligence") or {}
    if news_intel.get("status"):
        news_rows = [
            ["Status", _fmt(news_intel.get("status"))],
            ["Reason", _fmt(news_intel.get("reason")) or "—"],
            ["Articles ingested", _fmt(len(news_intel.get("items") or []))],
            ["Duplicates", _fmt(news_intel.get("duplicate_count"))],
            ["Malformed skipped", _fmt(news_intel.get("malformed_count"))],
            ["Excluded after as_of", _fmt(news_intel.get("excluded_after_asof_count"))],
            ["FOMC status", _fmt(news_intel.get("fomc_status"))],
            ["FOMC events", _fmt(len(news_intel.get("fomc_events") or []))],
            ["Sentiment status", _fmt(news_intel.get("sentiment_status"))],
        ]
        fetch_errors = news_intel.get("fetch_errors") or []
        if fetch_errors:
            news_rows.append(
                ["Fetch errors", "; ".join(str(e) for e in fetch_errors)]
            )
        md_16 = [
            "News intelligence channel state (ingest_news stage payload, "
            "verbatim). An explicit non-ok status means the news day is not "
            "a healthy empty feed.",
            "",
            _md_table(["Field", "Value"], [[r[0], r[1]] for r in news_rows]),
        ]
        html_16 = _html_table(["Field", "Value"], news_rows)
        sections.append(
            Section(16, "News Intelligence", "\n".join(md_16), html_16)
        )

    return sections


# ---------------------------------------------------------------------------
# Document rendering
# ---------------------------------------------------------------------------


def render_markdown(title: str, date_label: str, sections: list[Section], footer: str) -> str:
    parts = [f"# {title}", "", f"**{date_label}**", ""]
    for section in sections:
        parts.append(f"## {section.number}. {section.title}")
        parts.append("")
        parts.append(section.md)
        parts.append("")
    parts.append("---")
    parts.append("")
    parts.append(footnote := footer)
    return "\n".join(parts)


_CSS = """
body { font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial,
       sans-serif; margin: 2rem auto; max-width: 960px; padding: 0 1rem;
       color: #1a1a1a; line-height: 1.5; }
h1 { border-bottom: 3px solid #1a1a1a; padding-bottom: .4rem; }
h2 { border-bottom: 1px solid #cccccc; padding-bottom: .3rem;
     margin-top: 2.4rem; }
h3 { margin-top: 1.6rem; }
table { border-collapse: collapse; width: 100%; margin: .8rem 0; }
th, td { border: 1px solid #cccccc; padding: .4rem .6rem; text-align: left;
         font-size: .92rem; }
th { background: #f2f2f2; }
pre { background: #f6f6f6; border: 1px solid #dddddd; padding: .8rem;
      overflow-x: auto; font-size: .88rem; }
ul { margin: .4rem 0; }
p { margin: .4rem 0; }
footer { margin-top: 3rem; color: #666666; font-size: .85rem;
         border-top: 1px solid #cccccc; padding-top: .6rem; }
"""


def render_html(title: str, date_label: str, sections: list[Section], footer: str) -> str:
    parts = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "<meta charset=\"utf-8\">",
        f"<title>{html.escape(title)}</title>",
        "<style>",
        _CSS.strip(),
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{html.escape(title)}</h1>",
        f"<p>{html.escape(date_label)}</p>",
    ]
    for section in sections:
        parts.append(f"<h2>{section.number}. {html.escape(section.title)}</h2>")
        parts.append(section.html)
    parts.append(f"<footer>{html.escape(footer)}</footer>")
    parts.append("</body></html>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _resolve_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir:
        path = Path(args.output_dir)
        if not path.is_absolute():
            path = Path.cwd() / path
        if is_run_dir(path):
            return path
        resolved = latest_run_dir(path)
        return resolved if resolved is not None else path
    if args.date:
        base = ROOT / "outputs" / args.date
        resolved = latest_run_dir(ROOT / "outputs", args.date)
        return resolved if resolved is not None else base
    resolved = latest_run_dir(ROOT / "outputs")
    return resolved if resolved is not None else ROOT / "outputs"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/generate_institutional_report.py",
        description="Generates the Institutional Daily Report from existing "
                    "pipeline outputs (outputs/YYYY-MM-DD/<pipeline_id>/).",
    )
    parser.add_argument(
        "--date",
        help="Run date as YYYY-MM-DD; resolves to the latest run under "
             "outputs/<date>/ (default: most recent run directory under "
             "outputs/).",
    )
    parser.add_argument(
        "--output-dir",
        help="Explicit output directory containing the run files.",
    )
    args = parser.parse_args(argv)

    run_dir = _resolve_output_dir(args)
    summary_path = run_dir / "summary.json"
    finalize_path = run_dir / "finalize.json"

    missing = [p.name for p in (summary_path, finalize_path) if not p.exists()]
    if missing:
        print(
            f"generate_institutional_report: run directory {run_dir} is "
            f"missing required files: {', '.join(missing)}",
            file=sys.stderr,
        )
        return EXIT_INPUT_ERROR

    summary = _load_json(summary_path) or {}
    finalize = _load_json(finalize_path) or {}
    if not isinstance(summary, dict) or not isinstance(finalize, dict):
        print("generate_institutional_report: invalid run files", file=sys.stderr)
        return EXIT_INPUT_ERROR

    config_raw = _load_json(run_dir / "config.json")
    config = config_raw.get("config", config_raw) if isinstance(config_raw, dict) else {}
    stages = _load_json(run_dir / "stages.json")
    if not isinstance(stages, list):
        stages = []

    data: dict[str, Any] = {
        "config": config if isinstance(config, dict) else {},
        "summary": summary,
        "finalize": finalize,
        "stages": stages,
    }

    sections = build_sections(data)

    date_label = f"Run date: {run_dir.name}"
    generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    footer = (
        f"Generated by scripts/generate_institutional_report.py at "
        f"{generated_at} from {run_dir}"
    )

    md_path = run_dir / "institutional_report.md"
    html_path = run_dir / "institutional_report.html"
    md_path.write_text(
        render_markdown(REPORT_TITLE, date_label, sections, footer),
        encoding="utf-8",
    )
    html_path.write_text(
        render_html(REPORT_TITLE, date_label, sections, footer),
        encoding="utf-8",
    )

    print("AurumAI Institutional Daily Report generated")
    print(f"  Source : {run_dir}")
    print(f"  Markdown : {md_path}")
    print(f"  HTML     : {html_path}")
    print(f"  Sections : {len(sections)}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
