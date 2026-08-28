"""Focused tests for the daily operational summary contract.

The daily operational summary is an additive measurement layer: it must
read existing run artifacts, never recalculate any pipeline value, never
mutate any artifact, and preserve unavailability honestly.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from operational_summary import (  # noqa: E402
    SCHEMA_VERSION,
    SUMMARY_FILENAME,
    build_summary,
    format_telegram_compact,
    write_summary,
)

CONTRACT_TOP_LEVEL_KEYS = {
    "schema_version",
    "run_id",
    "entry_date",
    "event_type",
    "regime",
    "decision",
    "news",
    "technical",
    "risk",
    "governance",
    "outcome",
    "calibration",
    "provenance",
}

CONTRACT_SUBKEYS = {
    "decision": {"action", "confidence", "selected_thesis_id", "gate_reason"},
    "news": {
        "status",
        "article_count",
        "relevant_count",
        "directional_count",
        "unknown_count",
        "sentiment_status",
    },
    "technical": {
        "status",
        "trend_direction",
        "momentum_direction",
        "structure_state",
        "technical_confidence",
    },
    "risk": {
        "status",
        "reference_price",
        "atr",
        "stop",
        "tp1",
        "tp2",
        "market_risk_reward",
        "risk_status",
    },
    "governance": {"bias_review_flag", "bias_severity", "provenance_status"},
    "outcome": {
        "status",
        "decision_correct",
        "abstention_verdict",
        "realized_return",
    },
    "calibration": {"sample_count", "oos_ece", "calibration_status"},
    "provenance": {"git_commit", "source_hashes"},
}

# Sentinel values that must never be used to fake a healthy state.
FORBIDDEN_UNAVAILABLE_SENTINELS = {0, "healthy", "stable"}


# ---------------------------------------------------------------------------
# Fixture: a synthetic run directory holding minimal real-shaped artifacts.
# ---------------------------------------------------------------------------


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    root = tmp_path
    run = root / "outputs" / "2026-08-28" / "runtime_20260828_000000"
    (run / "artifacts").mkdir(parents=True)

    _write(
        run / "summary.json",
        {
            "pipeline_id": "runtime_20260828_000000",
            "event_type": "CPI",
            "decision": "NO_TRADE",
            "decision_confidence": 0.4992,
            "success": True,
            "artifacts_directory": str(run / "artifacts"),
        },
    )
    _write(
        run / "finalize.json",
        {
            "context": {"current_regime": "LATE_CYCLE"},
            "decision": {
                "decision": "NO_TRADE",
                "institutional_confidence": 0.4992,
                "selected_thesis_id": "th_test",
                "decision_id": "dec_test",
                "metadata": {
                    "gate_reason": "confidence_below_threshold",
                    "bias_review": {
                        "human_review_flag": False,
                        "overall_severity": "medium",
                    },
                },
                "provenance_chain": [{"created_by": "W13"}],
            },
            "risk_decision": {"action": "proceed"},
            "news_intelligence": {
                "status": "ok",
                "sentiment_status": "skipped_none",
                "items": [
                    {"directional_implication": "bullish", "gold_relevance": "high"},
                    {"directional_implication": "unknown", "gold_relevance": "medium"},
                    {"directional_implication": "unknown", "gold_relevance": "low"},
                ],
            },
            "trade_recommendation": {
                "recommendation_action": "NO_TRADE",
                "metadata": {
                    "reference_price": 4660.60009765625,
                    "levels_basis": "not_applicable_no_levels",
                    "atr_provenance": {"atr_14": 80.189956, "status": "ok"},
                },
            },
        },
    )
    _write(
        run / "artifacts" / "technical_assessment.json",
        {
            "trend_direction": "bullish",
            "momentum_direction": "bullish",
            "structure_state": "uptrend",
            "technical_confidence": 0.8696,
            "source_data_hash": "c1826115a6240a4d",
        },
    )
    _write(
        run / "outcome.evaluated.json",
        {
            "status": "pending",
            "entry_date": "2026-08-28",
            "decision_correct": None,
            "abstention_verdict": "unevaluable",
            "realized_gold_return": None,
            "gold_source_sha256": "9861bfcb2ab131d3",
        },
    )
    _write(
        root / "runtime" / "calibration.json",
        {
            "sample_count": 3,
            "oos_ece": None,
            "statistics": {
                "sample_count": 3,
                "min_samples_required": 10,
            },
        },
    )
    _write(
        root / "runtime" / "run_registry.jsonl",
        {"run_id": "runtime_20260828_000000", "git_commit": "c5aa5f7"},
    )
    return run


# ---------------------------------------------------------------------------
# 1. The summary is strictly additive (contract shape).
# ---------------------------------------------------------------------------


def test_summary_is_additive_contract_shape(run_dir: Path) -> None:
    summary = build_summary(run_dir, run_dir.parents[2])
    assert set(summary) == CONTRACT_TOP_LEVEL_KEYS
    for section, keys in CONTRACT_SUBKEYS.items():
        assert set(summary[section]) == keys, section
    assert summary["schema_version"] == SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 2. Values come from existing artifacts (verbatim reads).
# ---------------------------------------------------------------------------


def test_values_come_from_existing_artifacts(run_dir: Path) -> None:
    root = run_dir.parents[2]
    summary = build_summary(run_dir, root)
    finalize = json.loads((run_dir / "finalize.json").read_text(encoding="utf-8"))
    technical = json.loads(
        (run_dir / "artifacts" / "technical_assessment.json").read_text(
            encoding="utf-8"
        )
    )
    outcome = json.loads(
        (run_dir / "outcome.evaluated.json").read_text(encoding="utf-8")
    )
    calibration = json.loads(
        (root / "runtime" / "calibration.json").read_text(encoding="utf-8")
    )

    assert summary["regime"] == finalize["context"]["current_regime"]
    assert summary["decision"]["gate_reason"] == (
        finalize["decision"]["metadata"]["gate_reason"]
    )
    assert summary["technical"]["trend_direction"] == technical["trend_direction"]
    assert summary["technical"]["technical_confidence"] == (
        technical["technical_confidence"]
    )
    assert summary["risk"]["reference_price"] == (
        finalize["trade_recommendation"]["metadata"]["reference_price"]
    )
    assert summary["risk"]["atr"] == (
        finalize["trade_recommendation"]["metadata"]["atr_provenance"]["atr_14"]
    )
    assert summary["outcome"]["status"] == outcome["status"]
    assert summary["calibration"]["sample_count"] == calibration["sample_count"]
    assert summary["provenance"]["git_commit"] == "c5aa5f7"
    assert summary["provenance"]["source_hashes"]["gold_history"] == (
        outcome["gold_source_sha256"]
    )


# ---------------------------------------------------------------------------
# 3. No recalculation: producer values pass through untouched.
# ---------------------------------------------------------------------------


def test_no_recalculation(run_dir: Path) -> None:
    summary = build_summary(run_dir, run_dir.parents[2])
    # A deliberately irregular producer value must survive verbatim, with
    # no rounding, scaling, or re-derivation.
    irregular = 80.1899561234
    finalize = json.loads((run_dir / "finalize.json").read_text(encoding="utf-8"))
    finalize["trade_recommendation"]["metadata"]["atr_provenance"]["atr_14"] = (
        irregular
    )
    _write(run_dir / "finalize.json", finalize)
    summary = build_summary(run_dir, run_dir.parents[2])
    assert summary["risk"]["atr"] == irregular
    assert summary["risk"]["reference_price"] == 4660.60009765625
    assert summary["decision"]["confidence"] == 0.4992


# ---------------------------------------------------------------------------
# 4. Deterministic normalized form.
# ---------------------------------------------------------------------------


def test_deterministic_normalized_form(run_dir: Path) -> None:
    first = build_summary(run_dir, run_dir.parents[2])
    second = build_summary(run_dir, run_dir.parents[2])
    dump_first = json.dumps(first, sort_keys=True)
    dump_second = json.dumps(second, sort_keys=True)
    assert dump_first == dump_second
    assert json.loads(dump_first) == first


# ---------------------------------------------------------------------------
# 5. Unavailable states preserved (never 0 / healthy / stable).
# ---------------------------------------------------------------------------


def test_unavailable_states_preserved(run_dir: Path) -> None:
    (run_dir / "artifacts" / "technical_assessment.json").unlink()
    (run_dir / "finalize.json").unlink()
    summary = build_summary(run_dir, run_dir.parents[2])

    assert summary["technical"]["status"] == "unavailable"
    assert summary["technical"]["trend_direction"] is None
    assert summary["decision"]["action"] is None
    assert summary["regime"] is None
    assert summary["risk"]["status"] == "unavailable"
    assert summary["news"]["status"] == "unavailable"

    # No forbidden healthy-looking sentinels in unavailable sections.
    for section in ("technical", "risk", "news"):
        for value in summary[section].values():
            assert value not in FORBIDDEN_UNAVAILABLE_SENTINELS


# ---------------------------------------------------------------------------
# 6. Pending outcome handled honestly.
# ---------------------------------------------------------------------------


def test_pending_outcome_handled(run_dir: Path) -> None:
    summary = build_summary(run_dir, run_dir.parents[2])
    assert summary["outcome"]["status"] == "pending"
    assert summary["outcome"]["decision_correct"] is None
    assert summary["outcome"]["realized_return"] is None
    assert summary["outcome"]["abstention_verdict"] == "unevaluable"


# ---------------------------------------------------------------------------
# 7. Calibration dormant below the producer's minimum sample count.
# ---------------------------------------------------------------------------


def test_calibration_dormant_below_minimum(run_dir: Path) -> None:
    summary = build_summary(run_dir, run_dir.parents[2])
    assert summary["calibration"]["calibration_status"] == "dormant"

    root = run_dir.parents[2]
    calibration = json.loads(
        (root / "runtime" / "calibration.json").read_text(encoding="utf-8")
    )
    calibration["sample_count"] = 10
    calibration["statistics"]["sample_count"] = 10
    calibration["oos_ece"] = 0.07
    _write(root / "runtime" / "calibration.json", calibration)

    summary = build_summary(run_dir, root)
    assert summary["calibration"]["calibration_status"] == "active"
    assert summary["calibration"]["oos_ece"] == 0.07


# ---------------------------------------------------------------------------
# 8. No decision change: the summary mirrors the recorded decision exactly.
# ---------------------------------------------------------------------------


def test_no_decision_change(run_dir: Path) -> None:
    before = json.loads((run_dir / "finalize.json").read_text(encoding="utf-8"))
    summary = build_summary(run_dir, run_dir.parents[2])
    after = json.loads((run_dir / "finalize.json").read_text(encoding="utf-8"))
    assert before == after
    decision = before["decision"]
    assert summary["decision"]["action"] == decision["decision"]
    assert summary["decision"]["confidence"] == decision["institutional_confidence"]
    assert summary["decision"]["selected_thesis_id"] == decision["selected_thesis_id"]
    # The compact Telegram rendering changes nothing either.
    text = format_telegram_compact(summary)
    assert "NO_TRADE" in text
    assert "0.4992" in text


# ---------------------------------------------------------------------------
# 9. No-lookahead: nothing beyond recorded artifacts is produced.
# ---------------------------------------------------------------------------


def test_no_lookahead(run_dir: Path) -> None:
    root = run_dir.parents[2]
    summary = build_summary(run_dir, root)
    # Outcome facts exist only when the evaluator recorded them; the
    # summary must never fill them in from any other source.
    outcome = summary["outcome"]
    assert outcome["status"] == "pending"
    assert outcome["decision_correct"] is None
    assert outcome["realized_return"] is None
    # entry_date is the recorded entry date only.
    assert summary["entry_date"] == "2026-08-28"
    # No evaluation, forecast, or simulation fields exist in the contract.
    assert "forecast" not in summary
    assert "simulation" not in summary
    assert "evaluated_at" not in summary


# ---------------------------------------------------------------------------
# 10. Write isolation: writing the summary touches nothing else.
# ---------------------------------------------------------------------------


def test_write_isolation(run_dir: Path) -> None:
    root = run_dir.parents[2]

    def _digest_tree() -> dict[str, str]:
        digests: dict[str, str] = {}
        for path in sorted(run_dir.rglob("*")):
            if path.is_file():
                digests[str(path.relative_to(run_dir))] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        return digests

    before = _digest_tree()
    path = write_summary(run_dir, root)
    after = _digest_tree()

    assert path == run_dir / SUMMARY_FILENAME
    assert path.exists()
    # Exactly one new file; every pre-existing file is byte-identical.
    assert set(after) - set(before) == {SUMMARY_FILENAME}
    for name, digest in before.items():
        assert after[name] == digest, name
    # Serialized form is stable across rewrites.
    first = path.read_text(encoding="utf-8")
    write_summary(run_dir, root)
    assert path.read_text(encoding="utf-8") == first
