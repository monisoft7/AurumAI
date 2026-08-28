"""Final Hardening — Group E: outcome calibration loop (D-05).

decision -> outcome -> evaluation -> aggregation/calibration -> future
confidence, using ONLY existing infrastructure: the immutable
``outcome.evaluated.json`` records (054/055-A) and the existing W9
``oos_ece`` confidence cap channel.

Point-in-time safety invariants:
- only evaluated, scored records (decision_correct is True/False);
- records whose entry_date is not strictly before the calibration date are
  excluded (never learn from an unsafe window);
- no decision-time fact is ever recomputed.
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from knowledge.learning.outcome_calibration import (  # noqa: E402
    MIN_CALIBRATION_SAMPLES,
    collect_evaluated_outcomes,
    compute_calibration,
    load_oos_ece,
    update_calibration_file,
)

AS_OF = datetime.date(2026, 8, 27)


def _write_evaluated(
    root: Path,
    date: str,
    pipeline: str,
    *,
    status: str = "evaluated",
    decision: str = "BUY",
    correct: bool | None = True,
    confidence: float = 0.7,
    entry_date: str = "2026-08-01",
) -> None:
    run_dir = root / date / pipeline
    run_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": "1.1",
        "artifact": "decision_outcome",
        "status": status,
        "run_id": f"run_{date}_{pipeline}",
        "decision": decision,
        "institutional_confidence": confidence,
        "event_type": "CPI",
        "asset": "XAU/USD",
        "horizon_days": 5,
        "gold_path": "data/history/gold/gold.csv",
        "entry_date": entry_date,
        "realized_gold_return": 1.2 if correct else -0.8,
        "decision_correct": correct,
        "evaluation_timestamp": "2026-08-10T00:00:00+00:00",
        "notes": [],
        "decision_id": "dec_x",
        "decision_snapshot": {},
    }
    (run_dir / "outcome.evaluated.json").write_text(
        json.dumps(record), encoding="utf-8"
    )


def test_collect_only_scored_evaluated_past_records(tmp_path):
    _write_evaluated(tmp_path, "2026-08-01", "p1", correct=True, entry_date="2026-08-01")
    # pending record: excluded
    _write_evaluated(tmp_path, "2026-08-02", "p2", status="pending", correct=None)
    # abstention: decision_correct None -> excluded
    _write_evaluated(tmp_path, "2026-08-03", "p3", decision="NO_TRADE", correct=None)
    # future entry (>= as_of): excluded -- point-in-time guard
    _write_evaluated(tmp_path, "2026-08-04", "p4", correct=True, entry_date="2026-08-27")
    # malformed entry date: excluded
    _write_evaluated(tmp_path, "2026-08-05", "p5", correct=True, entry_date="not-a-date")

    records = collect_evaluated_outcomes(tmp_path, as_of_date=AS_OF)
    assert len(records) == 1
    assert records[0]["run_id"] == "run_2026-08-01_p1"


def test_compute_calibration_statistics(tmp_path):
    records = []
    for i in range(10):
        correct = i % 2 == 0
        confidence = 0.8
        records.append(
            {
                "run_id": f"r{i}",
                "decision_correct": correct,
                "institutional_confidence": confidence,
                "entry_date": "2026-08-01",
                "status": "evaluated",
            }
        )
    stats = compute_calibration(records)
    assert stats["sample_count"] == 10
    # 5 correct (|0.8-1|=0.2), 5 wrong (|0.8-0|=0.8) -> mean abs error 0.5
    assert stats["mean_abs_error"] == 0.5
    assert stats["oos_ece"] == 0.5
    assert stats["accuracy"] == 0.5
    assert stats["mean_confidence"] == 0.8
    assert stats["brier"] == pytest.approx(0.5 * 0.04 + 0.5 * 0.64)


def test_calibration_not_published_below_min_samples():
    stats = compute_calibration(
        [
            {
                "decision_correct": True,
                "institutional_confidence": 0.7,
            }
        ]
    )
    assert stats["sample_count"] == 1
    assert stats["oos_ece"] is None


def test_update_and_load_roundtrip(tmp_path):
    for i in range(MIN_CALIBRATION_SAMPLES + 3):
        date = f"2026-08-{i + 1:02d}"
        _write_evaluated(
            tmp_path,
            date,
            f"p{i}",
            correct=(i % 3 != 0),
            confidence=0.75,
            entry_date=date,
        )
    calibration_path = tmp_path / "runtime" / "calibration.json"
    payload = update_calibration_file(
        tmp_path, calibration_path, as_of_date=AS_OF
    )
    assert payload["sample_count"] == MIN_CALIBRATION_SAMPLES + 3
    assert payload["oos_ece"] is not None
    assert len(payload["source_run_ids"]) == MIN_CALIBRATION_SAMPLES + 3

    # idempotent rewrite
    again = update_calibration_file(tmp_path, calibration_path, as_of_date=AS_OF)
    assert again["oos_ece"] == payload["oos_ece"]

    loaded = load_oos_ece(calibration_path)
    assert loaded == payload["oos_ece"]

    # determinism: identical inputs produce the identical statistic
    assert again["statistics"] == payload["statistics"]


def test_load_oos_ece_absent_or_invalid_is_none(tmp_path):
    assert load_oos_ece(tmp_path / "missing.json") is None
    bad = tmp_path / "calibration.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_oos_ece(bad) is None
    bad.write_text(json.dumps({"oos_ece": "high"}), encoding="utf-8")
    assert load_oos_ece(bad) is None
    bad.write_text(json.dumps({"oos_ece": 1.7}), encoding="utf-8")
    assert load_oos_ece(bad) is None
    bad.write_text(json.dumps({"oos_ece": 0.21}), encoding="utf-8")
    assert load_oos_ece(bad) == 0.21


def test_w9_cap_consumes_published_calibration():
    """End-to-end loop proof: published oos_ece flows into the W9 cap."""
    from confidence_engine.engine import ConfidenceEngine
    from confidence_engine.contracts import InstitutionalConfidence
    from thesis_construction.contracts import (
        InvestmentThesis,
        ThesisConstruction,
    )

    def _construction() -> ThesisConstruction:
        thesis = InvestmentThesis(
            thesis_id="th_cal",
            direction="bullish",
            supporting_set_ids=("a", "b"),
            counter_evidence_ids=(),
            regime="NORMAL_GROWTH",
            economic_mechanism="m",
            time_horizon_days=90,
            invalidating_conditions=("i",),
            remaining_unknowns=(),
            confidence_inputs={
                "avg_supporting_weight": 0.9,
                "avg_supporting_consensus": 1.0,
                "conflict_severity": 0.0,
                "confidence_penalty": 0.0,
                "raw_support": 0.9,
            },
            institutional_support=0.9,
            explanation="calibration loop test",
        )
        return ThesisConstruction(
            construction_id="tc_cal",
            reasoning_id="rsn_cal",
            assessment_id="cae_cal",
            timestamp="2026-08-27T00:00:00Z",
            regime="NORMAL_GROWTH",
            theses=(thesis,),
            ranked_thesis_ids=(thesis.thesis_id,),
            total_theses=1,
            primary_thesis_id=thesis.thesis_id,
        )

    construction = _construction()
    no_cal = ConfidenceEngine().evaluate(_construction(), oos_ece=None)
    capped = ConfidenceEngine().evaluate(_construction(), oos_ece=0.30)
    assert no_cal.theses_confidence[0].metadata.get("oos_calibration", {}).get(
        "cap_applied"
    ) in (None, "none")
    assert capped.theses_confidence[0].final_confidence <= 0.35 + 1e-9
    assert capped.theses_confidence[0].metadata["oos_calibration"]["cap_applied"] == "low"


import pytest  # noqa: E402
