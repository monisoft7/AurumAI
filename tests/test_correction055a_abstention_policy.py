# tests/test_correction055a_abstention_policy.py

"""Correction 055-A — abstention policy foundation regressions.

Covers: decision-time snapshot emit/immutability, the abstention verdict
taxonomy (justified_abstention / missed_opportunity / unresolvable /
unevaluable), bias-block outcome dependence, HOLD/BUY/SELL scoring
preservation, provenance, and backward compatibility with schema-1.0
artifacts.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module(rel_path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVAL = _load_module("scripts/evaluate_outcome.py", "c055_evaluator_mod")
RUN = _load_module("run.py", "c055_runtime_mod")
DAILY = _load_module("scripts/run_daily.py", "c055_run_daily_mod")

GOLD_UP_ROWS = [
    ("2024-01-01", 100.0),
    ("2024-01-02", 101.0),
    ("2024-01-07", 106.0),
    ("2024-01-08", 107.0),
]
GOLD_DOWN_ROWS = [
    ("2024-01-01", 100.0),
    ("2024-01-02", 101.0),
    ("2024-01-07", 96.0),
    ("2024-01-08", 95.0),
]
GOLD_FLAT_ROWS = [
    ("2024-01-01", 100.0),
    ("2024-01-02", 101.0),
    ("2024-01-07", 101.05),
    ("2024-01-08", 101.04),
]


def _snapshot(
    *,
    direction: str | None = "bullish",
    thesis_id: str | None = "th_best",
    composite_score: float | None = 0.41,
    conviction_pass: bool | None = False,
    rr_pass: bool | None = True,
    ratio: float | None = 1.5,
    bias_blocked: bool = False,
    evidence_quality: float | None = 0.55,
    counter_quality: float | None = 0.8,
    prob_max: float | None = 0.7,
    theses: int | None = 2,
) -> dict[str, Any]:
    return {
        "best_rejected": (
            None
            if direction is None
            else {
                "thesis_id": thesis_id,
                "direction": direction,
                "composite_score": composite_score,
            }
        ),
        "gate_reasons": {
            "conviction_gate_pass": conviction_pass,
            "rr_gate_pass": rr_pass,
            "risk_reward_ratio": ratio,
            "bias_review_blocked": bias_blocked,
        },
        "evidence_snapshot": {
            "evidence_quality": evidence_quality,
            "counter_evidence_quality": counter_quality,
            "scenario_probability_max": prob_max,
            "total_theses_evaluated": theses,
        },
    }


def _write_gold(path: Path, rows: list[tuple[str, float]]) -> None:
    path.write_text(
        "Date,Close\n" + "".join(f"{d},{c}\n" for d, c in rows),
        encoding="utf-8",
    )


def _write_run(
    run_dir: Path,
    *,
    decision: str = "NO_TRADE",
    entry_date: str = "2024-01-02",
    gold_rows: list[tuple[str, float]] | None = GOLD_UP_ROWS,
    horizon: int = 5,
    snapshot: dict[str, Any] | None = None,
    evaluated_sibling: dict[str, Any] | None = None,
) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    gold_path = run_dir / "gold.csv"
    if gold_rows:
        _write_gold(gold_path, gold_rows)
    record: dict[str, Any] = {
        "schema_version": "1.1",
        "artifact": "decision_outcome",
        "status": "pending",
        "run_id": f"runtime_{run_dir.name}",
        "decision": decision,
        "institutional_confidence": 0.31 if decision == "NO_TRADE" else 0.62,
        "event_type": "CPI",
        "asset": "XAU/USD",
        "horizon_days": horizon,
        "gold_path": str(gold_path),
        "entry_date": entry_date,
        "realized_gold_return": None,
        "decision_correct": None,
        "evaluation_timestamp": None,
        "notes": [],
        "decision_id": "dec_test",
    }
    if snapshot is not None:
        record["decision_snapshot"] = snapshot
    (run_dir / "outcome.json").write_text(json.dumps(record), encoding="utf-8")
    if evaluated_sibling is not None:
        (run_dir / "outcome.evaluated.json").write_text(
            json.dumps(evaluated_sibling), encoding="utf-8"
        )
    return run_dir


# ===========================================================================
# 1-2. Snapshot emission and immutability
# ===========================================================================


class TestDecisionSnapshotEmit:
    def test_snapshot_fields_emitted(self) -> None:
        record = RUN._outcome_record(
            run_id="runtime_x",
            event_type="CPI",
            asset="XAU/USD",
            horizon=12,
            gold_path="data/history/gold/gold.csv",
            entry_date="2026-08-24",
            decision="NO_TRADE",
            institutional_confidence=0.31,
            decision_id="dec_x",
            decision_snapshot=_snapshot(),
        )
        assert record["schema_version"] == "1.1"
        snap = record["decision_snapshot"]
        assert snap["best_rejected"] == {
            "thesis_id": "th_best",
            "direction": "bullish",
            "composite_score": 0.41,
        }
        assert snap["gate_reasons"] == {
            "conviction_gate_pass": False,
            "rr_gate_pass": True,
            "risk_reward_ratio": 1.5,
            "bias_review_blocked": False,
        }
        assert snap["evidence_snapshot"]["evidence_quality"] == 0.55

    def test_existing_fields_preserved(self) -> None:
        record = RUN._outcome_record(
            run_id="runtime_x",
            event_type="CPI",
            asset="XAU/USD",
            horizon=12,
            gold_path="g.csv",
            entry_date="2026-08-24",
            decision="BUY",
            institutional_confidence=0.62,
            decision_id=None,
        )
        assert record["decision_snapshot"] == {}
        for key in (
            "run_id", "decision", "institutional_confidence", "event_type",
            "asset", "horizon_days", "gold_path", "entry_date",
            "realized_gold_return", "decision_correct", "evaluation_timestamp",
            "notes", "decision_id",
        ):
            assert key in record

    def test_snapshot_extracted_from_decision_object(self) -> None:
        class DriverStub:
            def __init__(self, name: str, value: float) -> None:
                self._d = {"name": name, "value": value}

            def to_dict(self) -> dict[str, Any]:
                return self._d

        class Decision:
            decision = "NO_TRADE"
            selected_thesis_id = "th_sel"
            rejected_alternatives: list = []
            institutional_confidence = 0.42
            risk_reward_summary = {"risk_reward_ratio": 3.2}
            metadata = {
                "selected_thesis_direction": "bearish",
                "composite_score": 0.44,
                "total_theses_evaluated": 3,
                "bias_review": {"human_review_flag": True},
            }

            def __init__(self) -> None:
                object.__setattr__(
                    self,
                    "decision_drivers",
                    [
                        DriverStub("evidence_quality", 0.51),
                        DriverStub("counter_evidence_quality", 0.77),
                        DriverStub("scenario_probability", 0.66),
                    ],
                )

        snap = RUN._decision_snapshot(Decision())
        assert snap["best_rejected"]["direction"] == "bearish"
        assert snap["gate_reasons"]["conviction_gate_pass"] is False
        assert snap["gate_reasons"]["rr_gate_pass"] is False
        assert snap["gate_reasons"]["bias_review_blocked"] is True
        assert snap["evidence_snapshot"] == {
            "evidence_quality": 0.51,
            "counter_evidence_quality": 0.77,
            "scenario_probability_max": 0.66,
            "total_theses_evaluated": 3,
        }

    def test_snapshot_is_immutable_through_evaluation(self, tmp_path: Path) -> None:
        run_dir = _write_run(tmp_path / "run", snapshot=_snapshot())
        before = (run_dir / "outcome.json").read_bytes()

        EVAL.evaluate_run(run_dir)
        EVAL.evaluate_run(run_dir, force=True)

        assert (run_dir / "outcome.json").read_bytes() == before
        sibling = json.loads(
            (run_dir / "outcome.evaluated.v2.json").read_text(encoding="utf-8")
        )
        assert sibling["decision_snapshot"] == json.loads(before)["decision_snapshot"]


# ===========================================================================
# 3-9. Verdict taxonomy
# ===========================================================================


class TestAbstentionVerdicts:
    def test_g4_no_eligible_thesis_is_unresolvable(self, tmp_path: Path) -> None:
        run_dir = _write_run(
            tmp_path / "run",
            gold_rows=GOLD_UP_ROWS,
            snapshot=_snapshot(
                direction="bullish",
                conviction_pass=False,
                rr_pass=None,
                ratio=None,
            ),
        )

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["status"] == "evaluated"
        assert record["abstention_verdict"] == "unresolvable"
        assert "no_eligible_thesis" in record["abstention_basis"]

    def test_low_confidence_flat_outcome_justified(self, tmp_path: Path) -> None:
        run_dir = _write_run(
            tmp_path / "run",
            gold_rows=GOLD_FLAT_ROWS,
            snapshot=_snapshot(conviction_pass=False, rr_pass=True),
        )

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["abstention_verdict"] == "justified_abstention"
        assert record["abstention_basis"] == ["low_conviction"]

    def test_rr_blocked_flat_outcome_justified(self, tmp_path: Path) -> None:
        run_dir = _write_run(
            tmp_path / "run",
            gold_rows=GOLD_FLAT_ROWS,
            snapshot=_snapshot(
                conviction_pass=True, rr_pass=False, ratio=3.0, direction="bearish"
            ),
        )

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["abstention_verdict"] == "justified_abstention"
        assert "rr_asymmetry" in record["abstention_basis"]

    def test_named_candidate_profitable_is_missed_opportunity(
        self, tmp_path: Path
    ) -> None:
        run_dir = _write_run(
            tmp_path / "run",
            gold_rows=GOLD_UP_ROWS,
            snapshot=_snapshot(direction="bullish"),
        )

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["abstention_verdict"] == "missed_opportunity"
        assert record["decision_correct"] is None
        assert record["abstention_return"] == pytest.approx(4.9505, abs=1e-3)

    def test_named_candidate_losing_is_justified(self, tmp_path: Path) -> None:
        run_dir = _write_run(
            tmp_path / "run",
            gold_rows=GOLD_DOWN_ROWS,
            snapshot=_snapshot(direction="bullish"),
        )

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["abstention_verdict"] == "justified_abstention"

    def test_bear_candidate_in_down_move_is_missed_opportunity(
        self, tmp_path: Path
    ) -> None:
        run_dir = _write_run(
            tmp_path / "run",
            gold_rows=GOLD_DOWN_ROWS,
            snapshot=_snapshot(direction="bearish"),
        )

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["abstention_verdict"] == "missed_opportunity"

    def test_bias_blocked_stays_outcome_dependent(self, tmp_path: Path) -> None:
        profitable = _write_run(
            tmp_path / "win",
            gold_rows=GOLD_UP_ROWS,
            snapshot=_snapshot(bias_blocked=True),
        )
        losing = _write_run(
            tmp_path / "loss",
            gold_rows=GOLD_DOWN_ROWS,
            snapshot=_snapshot(bias_blocked=True),
        )

        win_record = EVAL.evaluate_run(profitable)["record"]
        loss_record = EVAL.evaluate_run(losing)["record"]

        assert win_record["abstention_basis"] == ["bias_review", "low_conviction"]
        assert loss_record["abstention_basis"] == ["bias_review", "low_conviction"]
        assert win_record["abstention_verdict"] == "missed_opportunity"
        assert loss_record["abstention_verdict"] == "justified_abstention"

    def test_missing_horizon_is_unevaluable_then_upgrades(
        self, tmp_path: Path
    ) -> None:
        run_dir = _write_run(
            tmp_path / "run",
            gold_rows=GOLD_UP_ROWS[:2],
            horizon=30,
            snapshot=_snapshot(),
        )

        pending = EVAL.evaluate_run(run_dir)["record"]
        assert pending["status"] == "pending"
        assert pending["abstention_verdict"] == "unevaluable"

        _write_gold(
            run_dir / "gold.csv",
            GOLD_UP_ROWS[:2] + [("2024-02-06", 111.0)],
        )
        resolved = EVAL.evaluate_run(run_dir)["record"]

        assert resolved["status"] == "evaluated"
        assert resolved["abstention_verdict"] == "missed_opportunity"

    def test_missing_gold_is_unevaluable(self, tmp_path: Path) -> None:
        run_dir = _write_run(
            tmp_path / "run", gold_rows=[], snapshot=_snapshot()
        )

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["abstention_verdict"] == "unevaluable"

    def test_no_directional_candidate_is_unresolvable(self, tmp_path: Path) -> None:
        run_dir = _write_run(
            tmp_path / "run",
            gold_rows=GOLD_UP_ROWS,
            snapshot=_snapshot(direction=None, conviction_pass=True, rr_pass=True),
        )

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["abstention_verdict"] == "unresolvable"

    def test_legacy_pending_without_snapshot_stays_unscored(
        self, tmp_path: Path
    ) -> None:
        run_dir = _write_run(tmp_path / "run", gold_rows=GOLD_UP_ROWS)

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["abstention_verdict"] == "unscored"
        assert record["abstention_basis"] == []
        assert record["decision_correct"] is None


# ===========================================================================
# 10-12. Scoring invariants
# ===========================================================================


class TestScoringInvariants:
    def test_no_trade_decision_correct_stays_null(self, tmp_path: Path) -> None:
        run_dir = _write_run(tmp_path / "run", snapshot=_snapshot())

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["decision_correct"] is None
        assert record["abstention_evaluable"] is True
        assert any("DEFERRED" in note for note in record["notes"])

    def test_hold_scoring_unchanged_flat_is_correct(self, tmp_path: Path) -> None:
        run_dir = _write_run(
            tmp_path / "run",
            decision="HOLD",
            gold_rows=GOLD_FLAT_ROWS,
            snapshot=_snapshot(conviction_pass=True, rr_pass=True),
        )

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["decision_correct"] is True
        assert record["abstention_evaluable"] is False
        assert record["abstention_verdict"] is None
        assert record["abstention_basis"] == []

    def test_buy_sell_scoring_unchanged(self, tmp_path: Path) -> None:
        buy = EVAL.evaluate_run(
            _write_run(
                tmp_path / "buy",
                decision="BUY",
                gold_rows=GOLD_UP_ROWS,
                snapshot=_snapshot(conviction_pass=True, rr_pass=True),
            )
        )["record"]
        sell = EVAL.evaluate_run(
            _write_run(
                tmp_path / "sell",
                decision="SELL",
                gold_rows=GOLD_UP_ROWS,
                snapshot=_snapshot(conviction_pass=True, rr_pass=True),
            )
        )["record"]

        assert buy["decision_correct"] is True
        assert sell["decision_correct"] is False
        assert buy["abstention_verdict"] is None
        assert sell["abstention_verdict"] is None


# ===========================================================================
# 13. Lookahead safety
# ===========================================================================


class TestLookaheadSafety:
    def test_verdict_uses_window_not_post_horizon_crash(self, tmp_path: Path) -> None:
        run_dir = _write_run(
            tmp_path / "run",
            gold_rows=[
                ("2024-01-01", 100.0),
                ("2024-01-02", 101.0),
                ("2024-01-07", 106.0),
                ("2024-01-20", 40.0),
            ],
            snapshot=_snapshot(direction="bullish"),
        )

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["realized_gold_return"] == pytest.approx(4.9505, abs=1e-3)
        assert record["abstention_verdict"] == "missed_opportunity"


# ===========================================================================
# 14-16. Mechanics preservation
# ===========================================================================


class TestMechanicsPreserved:
    def test_idempotent_reevaluation_with_snapshot(self, tmp_path: Path) -> None:
        run_dir = _write_run(
            tmp_path / "run", gold_rows=GOLD_UP_ROWS, snapshot=_snapshot()
        )
        first = EVAL.evaluate_run(run_dir)
        second = EVAL.evaluate_run(run_dir)

        assert first["wrote"] is True
        assert second["wrote"] is False
        assert second["record"] == first["record"]

    def test_force_writes_versioned_sibling(self, tmp_path: Path) -> None:
        run_dir = _write_run(
            tmp_path / "run", gold_rows=GOLD_UP_ROWS, snapshot=_snapshot()
        )
        canonical_before = None
        EVAL.evaluate_run(run_dir)
        canonical_before = (run_dir / "outcome.evaluated.json").read_bytes()

        result = EVAL.evaluate_run(run_dir, force=True)

        assert result["path"] == run_dir / "outcome.evaluated.v2.json"
        assert (run_dir / "outcome.evaluated.json").read_bytes() == canonical_before

    def test_daily_sweep_wiring_preserved(self, monkeypatch) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append([str(part) for part in cmd])
            return type(
                "R",
                (),
                {"returncode": 0, "stdout": "outcome sweep: processed=0 written=0 errors=0\n"},
            )()

        monkeypatch.setattr(DAILY.subprocess, "run", fake_run)

        ok, note = DAILY._evaluate_outcomes()

        assert ok is True
        assert calls[0][1].endswith("evaluate_outcome.py")
        assert "--all-pending" in calls[0]
        assert note.startswith("outcome sweep:")

    def test_sweep_picks_up_snapshotted_runs(self, tmp_path: Path) -> None:
        base = tmp_path / "outputs"
        run_dir = _write_run(
            base / "2026-01-10" / "runtime_a",
            gold_rows=GOLD_UP_ROWS,
            snapshot=_snapshot(),
        )

        results = EVAL.evaluate_pending_outcomes(base)

        assert len(results) == 1
        assert results[0]["record"]["abstention_verdict"] == "missed_opportunity"
        assert (run_dir / "outcome.evaluated.json").is_file()


# ===========================================================================
# 17. Backward compatibility with schema 1.0 artifacts
# ===========================================================================


class TestLegacyArtifacts:
    def test_old_evaluated_artifact_readable_and_immutable(
        self, tmp_path: Path
    ) -> None:
        legacy = {
            "schema_version": "1.0",
            "artifact": "decision_outcome",
            "status": "evaluated",
            "run_id": "runtime_old",
            "decision": "NO_TRADE",
            "institutional_confidence": 0.29,
            "event_type": "CPI",
            "asset": "XAU/USD",
            "horizon_days": 12,
            "gold_path": "data/history/gold/gold.csv",
            "entry_date": "2026-08-04",
            "realized_gold_return": -1.2,
            "decision_correct": None,
            "evaluation_timestamp": "2026-08-16T12:00:00+00:00",
            "notes": [],
            "decision_id": "dec_old",
        }
        run_dir = _write_run(
            tmp_path / "run",
            evaluated_sibling=legacy,
        )
        before = (run_dir / "outcome.evaluated.json").read_bytes()

        result = EVAL.evaluate_run(run_dir)

        assert result["wrote"] is False
        assert result["record"]["schema_version"] == "1.0"
        assert result["record"]["decision_correct"] is None
        assert (run_dir / "outcome.evaluated.json").read_bytes() == before

    def test_legacy_pending_artifact_without_snapshot_evaluates_unscored(
        self, tmp_path: Path
    ) -> None:
        legacy_pending = {
            "schema_version": "1.0",
            "artifact": "decision_outcome",
            "status": "pending",
            "run_id": "runtime_old2",
            "decision": "NO_TRADE",
            "institutional_confidence": 0.29,
            "event_type": "CPI",
            "asset": "XAU/USD",
            "horizon_days": 5,
            "gold_path": "",
            "entry_date": "2026-08-04",
            "realized_gold_return": None,
            "decision_correct": None,
            "evaluation_timestamp": None,
            "notes": [],
            "decision_id": "dec_old2",
        }
        run_dir = _write_run(tmp_path / "run", gold_rows=[])
        (run_dir / "outcome.json").write_text(
            json.dumps(legacy_pending), encoding="utf-8"
        )

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["schema_version"] == "1.1"
        assert record["decision_correct"] is None
        assert record["abstention_verdict"] == "unscored"
