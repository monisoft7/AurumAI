# tests/test_outcome_validation.py

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from run import _outcome_record


def _load_evaluator():
    spec = importlib.util.spec_from_file_location(
        "evaluate_outcome",
        Path(__file__).resolve().parents[1] / "scripts" / "evaluate_outcome.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVAL = _load_evaluator()


def _write_run(run_dir: Path, *, decision: str, entry_date: str,
               gold_rows: list[tuple[str, float]], confidence: float = 0.62,
               horizon: int = 5) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    gold_path = run_dir / "gold.csv"
    if gold_rows:
        gold_path.write_text(
            "Date,Close\n" + "".join(f"{d},{c}\n" for d, c in gold_rows),
            encoding="utf-8",
        )
    (run_dir / "outcome.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "artifact": "decision_outcome",
            "status": "pending",
            "run_id": "runtime_test_0001",
            "decision": decision,
            "institutional_confidence": confidence,
            "event_type": "CPI",
            "asset": "XAU/USD",
            "horizon_days": horizon,
            "gold_path": str(gold_path),
            "entry_date": entry_date,
            "realized_gold_return": None,
            "decision_correct": None,
            "evaluation_timestamp": None,
            "notes": [],
            "decision_id": None,
        }),
        encoding="utf-8",
    )


# ===========================================================================
# Runtime emit
# ===========================================================================


class TestOutcomeRecordEmit:
    def test_outcome_record_schema(self) -> None:
        record = _outcome_record(
            run_id="runtime_20260804_182103",
            event_type="CPI",
            asset="XAU/USD",
            horizon=12,
            gold_path="data/history/gold/gold.csv",
            entry_date="2026-08-04",
            decision="NO_TRADE",
            institutional_confidence=0.3139,
            decision_id="dec_0f5f745cf534",
        )
        assert record["schema_version"] == "1.0"
        assert record["artifact"] == "decision_outcome"
        assert record["status"] == "pending"
        assert record["run_id"] == "runtime_20260804_182103"
        assert record["decision"] == "NO_TRADE"
        assert record["institutional_confidence"] == 0.3139
        assert record["event_type"] == "CPI"
        assert record["asset"] == "XAU/USD"
        assert record["horizon_days"] == 12
        assert record["gold_path"] == "data/history/gold/gold.csv"
        assert record["entry_date"] == "2026-08-04"
        assert record["realized_gold_return"] is None
        assert record["decision_correct"] is None
        assert record["evaluation_timestamp"] is None
        assert record["notes"] == []
        assert record["decision_id"] == "dec_0f5f745cf534"


# ===========================================================================
# Evaluation
# ===========================================================================


class TestEvaluateRun:
    def test_buy_correct_when_gold_up(self, tmp_path: Path) -> None:
        _write_run(
            tmp_path,
            decision="BUY",
            entry_date="2024-01-02",
            gold_rows=[
                ("2024-01-01", 100.0),
                ("2024-01-02", 101.0),
                ("2024-01-07", 106.0),
                ("2024-01-08", 107.0),
            ],
        )
        result = EVAL.evaluate_run(tmp_path)
        record = result["record"]
        assert result["wrote"] is True
        assert record["status"] == "evaluated"
        assert record["realized_gold_return"] == pytest.approx(4.9505, abs=1e-3)
        assert record["decision_correct"] is True
        assert record["evaluation_timestamp"] is not None

    def test_buy_incorrect_when_gold_down(self, tmp_path: Path) -> None:
        _write_run(
            tmp_path,
            decision="BUY",
            entry_date="2024-01-02",
            gold_rows=[
                ("2024-01-01", 100.0),
                ("2024-01-02", 101.0),
                ("2024-01-07", 94.0),
                ("2024-01-08", 93.0),
            ],
        )
        record = EVAL.evaluate_run(tmp_path)["record"]
        assert record["status"] == "evaluated"
        assert record["decision_correct"] is False

    def test_no_trade_is_abstention_not_scored(self, tmp_path: Path) -> None:
        _write_run(
            tmp_path,
            decision="NO_TRADE",
            entry_date="2024-01-02",
            gold_rows=[
                ("2024-01-01", 100.0),
                ("2024-01-02", 101.0),
                ("2024-01-07", 106.0),
                ("2024-01-08", 107.0),
            ],
        )
        record = EVAL.evaluate_run(tmp_path)["record"]
        assert record["status"] == "evaluated"
        assert record["realized_gold_return"] is not None
        assert record["decision_correct"] is None

    def test_horizon_not_elapsed_stays_pending(self, tmp_path: Path) -> None:
        _write_run(
            tmp_path,
            decision="BUY",
            entry_date="2024-01-02",
            gold_rows=[
                ("2024-01-01", 100.0),
                ("2024-01-02", 101.0),
            ],
            horizon=10,
        )
        record = EVAL.evaluate_run(tmp_path)["record"]
        assert record["status"] == "pending"
        assert record["realized_gold_return"] is None
        assert record["decision_correct"] is None
        assert any("horizon" in n for n in record["notes"])

    def test_missing_gold_file_records_nulls_and_notes(self, tmp_path: Path) -> None:
        _write_run(tmp_path, decision="BUY", entry_date="2024-01-02", gold_rows=[])
        record = EVAL.evaluate_run(tmp_path)["record"]
        assert record["status"] == "evaluated"
        assert record["realized_gold_return"] is None
        assert record["decision_correct"] is None
        assert any("gold data unavailable" in n for n in record["notes"])

    def test_outcome_json_never_modified(self, tmp_path: Path) -> None:
        _write_run(
            tmp_path,
            decision="BUY",
            entry_date="2024-01-02",
            gold_rows=[
                ("2024-01-01", 100.0),
                ("2024-01-02", 101.0),
                ("2024-01-07", 106.0),
                ("2024-01-08", 107.0),
            ],
        )
        before = (tmp_path / "outcome.json").read_bytes()
        EVAL.evaluate_run(tmp_path)
        assert (tmp_path / "outcome.json").read_bytes() == before

    def test_already_evaluated_not_rewritten(self, tmp_path: Path) -> None:
        _write_run(
            tmp_path,
            decision="BUY",
            entry_date="2024-01-02",
            gold_rows=[
                ("2024-01-01", 100.0),
                ("2024-01-02", 101.0),
                ("2024-01-07", 106.0),
                ("2024-01-08", 107.0),
            ],
        )
        first = EVAL.evaluate_run(tmp_path)
        second = EVAL.evaluate_run(tmp_path)
        assert first["wrote"] is True
        assert second["wrote"] is False
        assert second["record"] == first["record"]

    def test_force_reevaluates(self, tmp_path: Path) -> None:
        _write_run(
            tmp_path,
            decision="BUY",
            entry_date="2024-01-02",
            gold_rows=[
                ("2024-01-01", 100.0),
                ("2024-01-02", 101.0),
                ("2024-01-07", 106.0),
                ("2024-01-08", 107.0),
            ],
        )
        EVAL.evaluate_run(tmp_path)
        result = EVAL.evaluate_run(tmp_path, force=True)
        assert result["wrote"] is True
