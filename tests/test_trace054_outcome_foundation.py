# tests/test_trace054_outcome_foundation.py

"""Trace 054 — final outcome-foundation sprint regressions.

Covers: automatic evaluation sweep, --force versioned sibling contract,
NO_TRADE explicit non-scoring semantics, gold provenance hash,
decision-artifact immutability, and lookahead-safe evaluation windows.
"""

from __future__ import annotations

import hashlib
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


EVAL = _load_module("scripts/evaluate_outcome.py", "trace054_evaluator_mod")
DAILY = _load_module("scripts/run_daily.py", "trace054_run_daily_mod")

GOLD_UP_ROWS = [
    ("2024-01-01", 100.0),
    ("2024-01-02", 101.0),
    ("2024-01-07", 106.0),
    ("2024-01-08", 107.0),
]


def _write_gold(path: Path, rows: list[tuple[str, float]]) -> None:
    path.write_text(
        "Date,Close\n" + "".join(f"{d},{c}\n" for d, c in rows),
        encoding="utf-8",
    )


def _write_run(
    run_dir: Path,
    *,
    decision: str = "BUY",
    entry_date: str = "2024-01-02",
    gold_rows: list[tuple[str, float]] | None = GOLD_UP_ROWS,
    horizon: int = 5,
) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    gold_path = run_dir / "gold.csv"
    if gold_rows:
        _write_gold(gold_path, gold_rows)
    (run_dir / "outcome.json").write_text(
        json.dumps({
            "run_id": f"runtime_{run_dir.name}",
            "decision": decision,
            "institutional_confidence": 0.62,
            "event_type": "CPI",
            "asset": "XAU/USD",
            "horizon_days": horizon,
            "gold_path": str(gold_path) if gold_rows is not None else str(gold_path),
            "entry_date": entry_date,
            "realized_gold_return": None,
            "decision_correct": None,
            "evaluation_timestamp": None,
            "notes": [],
            "decision_id": None,
        }),
        encoding="utf-8",
    )
    return run_dir


# ===========================================================================
# Automatic evaluation trigger (pending sweep)
# ===========================================================================


class TestAutomaticEvaluationSweep:
    def test_sweep_evaluates_elapsed_horizon(self, tmp_path: Path) -> None:
        base = tmp_path / "outputs"
        run_dir = _write_run(base / "2026-01-10" / "runtime_a")

        results = EVAL.evaluate_pending_outcomes(base)

        assert len(results) == 1
        assert results[0]["wrote"] is True
        record = results[0]["record"]
        assert record["status"] == "evaluated"
        assert record["decision_correct"] is True
        assert (run_dir / "outcome.evaluated.json").is_file()

    def test_sweep_is_idempotent_on_evaluated_runs(self, tmp_path: Path) -> None:
        base = tmp_path / "outputs"
        run_dir = _write_run(base / "2026-01-10" / "runtime_a")
        EVAL.evaluate_pending_outcomes(base)
        canonical_before = (run_dir / "outcome.evaluated.json").read_bytes()

        second = EVAL.evaluate_pending_outcomes(base)

        assert second == []
        assert (run_dir / "outcome.evaluated.json").read_bytes() == canonical_before

    def test_sweep_retries_pending_until_horizon_elapsed(
        self, tmp_path: Path
    ) -> None:
        base = tmp_path / "outputs"
        run_dir = _write_run(
            base / "2026-01-10" / "runtime_a",
            gold_rows=GOLD_UP_ROWS[:2],
            horizon=30,
        )

        first = EVAL.evaluate_pending_outcomes(base)
        assert first[0]["record"]["status"] == "pending"

        _write_gold(
            run_dir / "gold.csv",
            GOLD_UP_ROWS[:2]
            + [("2024-02-05", 110.0), ("2024-02-06", 111.0)],
        )
        second = EVAL.evaluate_pending_outcomes(base)

        assert second[0]["wrote"] is True
        record = second[0]["record"]
        assert record["status"] == "evaluated"
        assert record["decision_correct"] is True

    def test_sweep_skips_directories_without_outcome(self, tmp_path: Path) -> None:
        base = tmp_path / "outputs"
        (base / "2026-01-10" / "not_a_run").mkdir(parents=True)

        assert EVAL.evaluate_pending_outcomes(base) == []

    def test_sweep_supports_legacy_flat_layout(self, tmp_path: Path) -> None:
        flat = _write_run(tmp_path / "outputs" / "2026-01-10")

        results = EVAL.evaluate_pending_outcomes(tmp_path / "outputs")

        assert len(results) == 1
        assert results[0]["path"].parent == flat
        assert results[0]["record"]["status"] == "evaluated"

    def test_sweep_isolates_malformed_run(self, tmp_path: Path) -> None:
        base = tmp_path / "outputs"
        bad = base / "2026-01-09" / "runtime_bad"
        bad.mkdir(parents=True)
        (bad / "outcome.json").write_text("{not json", encoding="utf-8")
        good = _write_run(base / "2026-01-10" / "runtime_good")

        results = EVAL.evaluate_pending_outcomes(base)

        assert len(results) == 2
        by_dir = {r["path"].parent.name: r for r in results}
        assert "error" in by_dir["runtime_bad"]
        assert by_dir["runtime_good"]["record"]["status"] == "evaluated"


# ===========================================================================
# --force versioned-sibling contract
# ===========================================================================


class TestForceVersionedSibling:
    def test_force_writes_sibling_and_preserves_canonical(
        self, tmp_path: Path
    ) -> None:
        run_dir = _write_run(tmp_path / "run")
        EVAL.evaluate_run(run_dir)
        canonical_before = (run_dir / "outcome.evaluated.json").read_bytes()

        result = EVAL.evaluate_run(run_dir, force=True)

        sibling = run_dir / "outcome.evaluated.v2.json"
        assert result["wrote"] is True
        assert result["path"] == sibling
        assert sibling.is_file()
        assert (run_dir / "outcome.evaluated.json").read_bytes() == canonical_before
        assert result["record"]["status"] == "evaluated"

    def test_force_versions_increase_monotonically(self, tmp_path: Path) -> None:
        run_dir = _write_run(tmp_path / "run")
        EVAL.evaluate_run(run_dir)
        EVAL.evaluate_run(run_dir, force=True)

        result = EVAL.evaluate_run(run_dir, force=True)

        assert result["path"] == run_dir / "outcome.evaluated.v3.json"

    def test_without_force_canonical_still_authoritative_after_forced_siblings(
        self, tmp_path: Path
    ) -> None:
        run_dir = _write_run(tmp_path / "run")
        first = EVAL.evaluate_run(run_dir)
        EVAL.evaluate_run(run_dir, force=True)

        again = EVAL.evaluate_run(run_dir)

        assert again["wrote"] is False
        assert again["path"] == run_dir / "outcome.evaluated.json"
        assert again["record"] == first["record"]

    def test_force_while_pending_rewrites_canonical_not_sibling(
        self, tmp_path: Path
    ) -> None:
        run_dir = _write_run(
            tmp_path / "run", gold_rows=GOLD_UP_ROWS[:2], horizon=30
        )
        pending = EVAL.evaluate_run(run_dir)
        assert pending["record"]["status"] == "pending"

        retried = EVAL.evaluate_run(run_dir, force=True)

        assert retried["path"] == run_dir / "outcome.evaluated.json"
        assert not list(run_dir.glob("outcome.evaluated.v*.json"))


# ===========================================================================
# NO_TRADE explicit non-scoring semantics
# ===========================================================================


class TestNoTradeSemantics:
    def test_no_trade_explicit_unscored_status(self, tmp_path: Path) -> None:
        run_dir = _write_run(tmp_path / "run", decision="NO_TRADE")

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["status"] == "evaluated"
        assert record["decision_correct"] is None
        assert record["abstention_evaluable"] is True
        assert record["abstention_verdict"] == "unscored"
        assert record["abstention_return"] == record["realized_gold_return"]
        assert record["abstention_return"] is not None
        assert any("DEFERRED" in note for note in record["notes"])

    def test_insufficient_evidence_is_also_abstention(self, tmp_path: Path) -> None:
        run_dir = _write_run(tmp_path / "run", decision="INSUFFICIENT_EVIDENCE")

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["decision_correct"] is None
        assert record["abstention_evaluable"] is True
        assert record["abstention_verdict"] == "unscored"

    def test_buy_semantics_unchanged_and_non_abstention(self, tmp_path: Path) -> None:
        run_dir = _write_run(tmp_path / "run", decision="BUY")

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["decision_correct"] is True
        assert record["abstention_evaluable"] is False
        assert record["abstention_verdict"] is None
        assert record["abstention_return"] is None

    def test_sell_semantics_unchanged_and_non_abstention(self, tmp_path: Path) -> None:
        run_dir = _write_run(tmp_path / "run", decision="SELL")

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["decision_correct"] is False
        assert record["abstention_evaluable"] is False
        assert record["abstention_verdict"] is None
        assert record["abstention_return"] is None

    def test_hold_scored_not_abstention(self, tmp_path: Path) -> None:
        run_dir = _write_run(
            tmp_path / "run",
            decision="HOLD",
            gold_rows=[
                ("2024-01-01", 100.0),
                ("2024-01-02", 101.0),
                ("2024-01-07", 101.09),
                ("2024-01-08", 101.08),
            ],
        )

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["decision_correct"] is True
        assert record["abstention_evaluable"] is False


# ===========================================================================
# Gold provenance hash
# ===========================================================================


class TestGoldProvenance:
    def test_provenance_hash_matches_consulted_file(self, tmp_path: Path) -> None:
        run_dir = _write_run(tmp_path / "run")

        record = EVAL.evaluate_run(run_dir)["record"]

        expected = hashlib.sha256((run_dir / "gold.csv").read_bytes()).hexdigest()
        assert record["gold_source_sha256"] == expected

    def test_provenance_null_when_gold_missing(self, tmp_path: Path) -> None:
        run_dir = _write_run(tmp_path / "run", gold_rows=[])

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["gold_source_sha256"] is None
        assert record["decision_correct"] is None

    def test_provenance_distinguishes_data_vintages(self, tmp_path: Path) -> None:
        run_a = _write_run(tmp_path / "a")
        run_b = _write_run(
            tmp_path / "b",
            gold_rows=[("2024-01-01", 100.0), ("2024-01-07", 106.0)],
        )

        hash_a = EVAL.evaluate_run(run_a)["record"]["gold_source_sha256"]
        hash_b = EVAL.evaluate_run(run_b)["record"]["gold_source_sha256"]

        assert hash_a != hash_b


# ===========================================================================
# Decision-time artifact immutability
# ===========================================================================


class TestArtifactImmutability:
    def test_decision_artifacts_never_mutated_by_evaluation_and_force(
        self, tmp_path: Path
    ) -> None:
        run_dir = _write_run(tmp_path / "run")
        (run_dir / "finalize.json").write_text('{"decision": {"decision": "BUY"}}')
        (run_dir / "summary.json").write_text('{"success": true}')
        snapshots = {
            name: (run_dir / name).read_bytes()
            for name in ("outcome.json", "finalize.json", "summary.json")
        }

        EVAL.evaluate_run(run_dir)
        EVAL.evaluate_run(run_dir, force=True)

        for name, content in snapshots.items():
            assert (run_dir / name).read_bytes() == content

    def test_schema_version_of_evaluated_artifact(self, tmp_path: Path) -> None:
        run_dir = _write_run(tmp_path / "run")

        record: dict[str, Any] = EVAL.evaluate_run(run_dir)["record"]

        assert record["schema_version"] == "1.1"


# ===========================================================================
# Lookahead safety
# ===========================================================================


class TestLookaheadSafety:
    def test_return_anchored_at_horizon_not_beyond(self, tmp_path: Path) -> None:
        run_dir = _write_run(
            tmp_path / "run",
            gold_rows=[
                ("2024-01-01", 100.0),
                ("2024-01-02", 101.0),
                ("2024-01-07", 106.0),
                ("2024-01-20", 200.0),
            ],
        )

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["realized_gold_return"] == pytest.approx(4.9505, abs=1e-3)

    def test_no_partial_evaluation_before_horizon_elapses(
        self, tmp_path: Path
    ) -> None:
        run_dir = _write_run(
            tmp_path / "run",
            gold_rows=[("2024-01-01", 100.0), ("2024-01-02", 101.0)],
            horizon=30,
        )

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["status"] == "pending"
        assert record["realized_gold_return"] is None
        assert record["decision_correct"] is None
        assert any("horizon" in n for n in record["notes"])

    def test_entry_before_gold_data_range_is_terminal_failure(
        self, tmp_path: Path
    ) -> None:
        run_dir = _write_run(tmp_path / "run", entry_date="2020-01-01")

        record = EVAL.evaluate_run(run_dir)["record"]

        assert record["status"] == "evaluated"
        assert record["realized_gold_return"] is None
        assert record["decision_correct"] is None
        assert any("before gold data range" in n for n in record["notes"])


# ===========================================================================
# Daily execution path wiring
# ===========================================================================


class TestDailyWiring:
    def test_evaluate_outcomes_invokes_evaluator_sweep(self, monkeypatch) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append([str(part) for part in cmd])
            return type("R", (), {"returncode": 0, "stdout": "outcome sweep: processed=1 written=1 errors=0\n", "stderr": ""})()

        monkeypatch.setattr(DAILY.subprocess, "run", fake_run)

        ok, note = DAILY._evaluate_outcomes()

        assert ok is True
        assert len(calls) == 1
        assert calls[0][1].endswith("evaluate_outcome.py")
        assert "--all-pending" in calls[0]
        assert note == "outcome sweep: processed=1 written=1 errors=0"

    def test_evaluate_outcomes_failure_is_reported_not_raised(
        self, monkeypatch
    ) -> None:
        def fake_run(cmd, **kwargs):
            return type("R", (), {"returncode": 2, "stdout": "", "stderr": "boom"})()

        monkeypatch.setattr(DAILY.subprocess, "run", fake_run)

        ok, note = DAILY._evaluate_outcomes()

        assert ok is False
        assert "pipeline unaffected" in note

    def test_evaluate_outcomes_missing_script_is_fail_safe(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(DAILY, "EVALUATE_SCRIPT", tmp_path / "missing.py")

        ok, note = DAILY._evaluate_outcomes()

        assert ok is False
        assert "pipeline unaffected" in note

    def test_main_invokes_evaluation_regardless_of_run_result(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        pipeline = tmp_path / "pipeline.py"
        report = tmp_path / "report.py"
        pipeline.write_text("")
        report.write_text("")
        run_dir = tmp_path / "outputs" / "2026-01-10" / "runtime_x"
        registry = tmp_path / "registry.jsonl"
        registry.write_text("", encoding="utf-8")
        state = {"calls": 0}

        def fake_registry_records():
            state["calls"] += 1
            if state["calls"] == 1:
                return []
            return [{
                "exit_code": 0,
                "output_directory": str(run_dir),
            }]

        evaluation_calls: list[bool] = []

        def fake_evaluate():
            evaluation_calls.append(True)
            return True, "outcome sweep: processed=0 written=0 errors=0"

        monkeypatch.setattr(DAILY, "PIPELINE_SCRIPT", pipeline)
        monkeypatch.setattr(DAILY, "REPORT_SCRIPT", report)
        monkeypatch.setattr(DAILY, "_resolve_run_dir", lambda date: run_dir)
        monkeypatch.setattr(DAILY, "_run_pipeline", lambda: 0)
        monkeypatch.setattr(DAILY, "_generate_report", lambda run_dir_: 0)
        monkeypatch.setattr(DAILY, "_report_exists", lambda run_dir_: True)
        monkeypatch.setattr(DAILY, "_registry_records", fake_registry_records)
        monkeypatch.setattr(DAILY, "_send_telegram", lambda run_dir_: (True, "test"))
        monkeypatch.setattr(DAILY, "_evaluate_outcomes", fake_evaluate)

        rc = DAILY.main([])

        assert rc == DAILY.EXIT_OK
        assert evaluation_calls == [True]

    def test_main_exit_code_unaffected_by_evaluation_failure(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        pipeline = tmp_path / "pipeline.py"
        report = tmp_path / "report.py"
        pipeline.write_text("")
        report.write_text("")
        run_dir = tmp_path / "outputs" / "2026-01-10" / "runtime_x"
        registry_state = {"calls": 0}

        def fake_registry_records():
            registry_state["calls"] += 1
            if registry_state["calls"] == 1:
                return []
            return [{"exit_code": 0, "output_directory": str(run_dir)}]

        monkeypatch.setattr(DAILY, "PIPELINE_SCRIPT", pipeline)
        monkeypatch.setattr(DAILY, "REPORT_SCRIPT", report)
        monkeypatch.setattr(DAILY, "_resolve_run_dir", lambda date: run_dir)
        monkeypatch.setattr(DAILY, "_run_pipeline", lambda: 0)
        monkeypatch.setattr(DAILY, "_generate_report", lambda run_dir_: 0)
        monkeypatch.setattr(DAILY, "_report_exists", lambda run_dir_: True)
        monkeypatch.setattr(DAILY, "_registry_records", fake_registry_records)
        monkeypatch.setattr(DAILY, "_send_telegram", lambda run_dir_: (True, "test"))
        monkeypatch.setattr(
            DAILY, "_evaluate_outcomes", lambda: (False, "failed (x; pipeline unaffected)")
        )

        rc = DAILY.main([])

        assert rc == DAILY.EXIT_OK
