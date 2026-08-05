# tests/test_runtime_output_isolation.py

"""Regression tests for per-run output isolation.

Every run must persist under ``outputs/YYYY-MM-DD/<pipeline_id>/`` so that no
run ever sees or overwrites another run's artifacts. These tests cover the
shared resolver, the runtime id generation, and every consumer that resolves
run directories.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module(rel_path: str, name: str):
    import sys

    spec = importlib.util.spec_from_file_location(name, ROOT / rel_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


OUT = _load_module("src/runtime_registry/outputs.py", "runtime_outputs")
RUN = _load_module("run.py", "runtime_entry")
REPORT = _load_module(
    "scripts/generate_institutional_report.py", "institutional_report_mod"
)
EVAL = _load_module("scripts/evaluate_outcome.py", "outcome_evaluator_mod")
DAILY = _load_module("scripts/run_daily.py", "run_daily_mod")
MON = _load_module("scripts/continuous_monitor.py", "continuous_monitor_mod")


def _write_run_dir(path: Path, *, with_outcome: bool = True) -> Path:
    """Create a minimal run directory as run.py would persist it."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "summary.json").write_text(json.dumps({"pipeline_id": path.name}))
    (path / "finalize.json").write_text("{}")
    (path / "config.json").write_text("{}")
    if with_outcome:
        (path / "outcome.json").write_text("{}")
    return path


# ===========================================================================
# Shared resolver (src/runtime_registry/outputs.py)
# ===========================================================================


class TestOutputsResolver:
    def test_date_dir_composes_expected_layout(self, tmp_path: Path) -> None:
        run_date = "2026-08-04"
        pipeline_id = "runtime_20260804_200330"
        expected = tmp_path / "outputs" / run_date / pipeline_id
        assert OUT.date_dir(tmp_path / "outputs", run_date) / pipeline_id == expected

    def test_latest_run_dir_new_layout(self, tmp_path: Path) -> None:
        outputs = tmp_path / "outputs"
        older = _write_run_dir(outputs / "2026-08-04" / "runtime_20260804_100000")
        newer = _write_run_dir(outputs / "2026-08-04" / "runtime_20260804_110000")
        assert OUT.latest_run_dir(outputs, "2026-08-04") == newer
        assert OUT.latest_run_dir(outputs) == newer
        assert older != newer

    def test_latest_run_dir_across_dates(self, tmp_path: Path) -> None:
        outputs = tmp_path / "outputs"
        _write_run_dir(outputs / "2026-08-03" / "runtime_20260803_090000")
        latest = _write_run_dir(outputs / "2026-08-04" / "runtime_20260804_120000")
        assert OUT.latest_run_dir(outputs) == latest

    def test_latest_run_dir_legacy_flat_layout(self, tmp_path: Path) -> None:
        outputs = tmp_path / "outputs"
        flat = _write_run_dir(outputs / "2026-08-03")
        assert OUT.latest_run_dir(outputs, "2026-08-03") == flat

    def test_latest_run_dir_mixed_layout_prefers_per_run_dirs(
        self, tmp_path: Path
    ) -> None:
        outputs = tmp_path / "outputs"
        _write_run_dir(outputs / "2026-08-04")  # legacy flat run dir
        older = _write_run_dir(outputs / "2026-08-04" / "runtime_20260804_100000")
        newer = _write_run_dir(outputs / "2026-08-04" / "runtime_20260804_110000")
        assert OUT.latest_run_dir(outputs, "2026-08-04") == newer
        assert OUT.latest_run_dir(outputs) == newer
        assert older != newer

    def test_latest_run_dir_none_when_empty(self, tmp_path: Path) -> None:
        assert OUT.latest_run_dir(tmp_path / "outputs") is None
        assert OUT.latest_run_dir(tmp_path / "outputs", "2026-08-04") is None

    def test_latest_run_dir_ignores_incomplete_dirs(self, tmp_path: Path) -> None:
        outputs = tmp_path / "outputs"
        (outputs / "2026-08-04" / "runtime_20260804_100000").mkdir(parents=True)
        assert OUT.latest_run_dir(outputs, "2026-08-04") is None

    def test_latest_run_dir_custom_predicate(self, tmp_path: Path) -> None:
        outputs = tmp_path / "outputs"
        _write_run_dir(outputs / "2026-08-04" / "runtime_20260804_100000")
        with_outcome = _write_run_dir(
            outputs / "2026-08-04" / "runtime_20260804_110000", with_outcome=True
        )
        no_outcome = _write_run_dir(
            outputs / "2026-08-04" / "runtime_20260804_120000", with_outcome=False
        )
        pred = lambda d: (d / "outcome.json").is_file()  # noqa: E731
        assert OUT.latest_run_dir(outputs, "2026-08-04", predicate=pred) == with_outcome
        assert no_outcome is not None


# ===========================================================================
# Runtime (run.py) — id generation and per-run directory
# ===========================================================================


class TestRuntimePipelineId:
    def test_new_pipeline_id_matches_output_dir_format(self, tmp_path: Path) -> None:
        outputs = tmp_path / "outputs"
        pipeline_id = RUN._new_pipeline_id(outputs, "2026-08-04")
        assert pipeline_id.startswith("runtime_")
        assert len(pipeline_id.split("_")) == 3
        dir_path = outputs / "2026-08-04" / pipeline_id
        assert not dir_path.exists()

    def test_new_pipeline_id_stays_unique_on_collision(self, tmp_path: Path) -> None:
        outputs = tmp_path / "outputs"
        first = RUN._new_pipeline_id(outputs, "2026-08-04")
        (outputs / "2026-08-04" / first).mkdir(parents=True)
        second = RUN._new_pipeline_id(outputs, "2026-08-04")
        assert second != first
        assert not (outputs / "2026-08-04" / second).exists()


# ===========================================================================
# Report generator — directory resolution
# ===========================================================================


class TestReportResolution:
    def test_date_resolves_to_latest_run_dir(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(REPORT, "ROOT", tmp_path)
        newer = _write_run_dir(
            tmp_path / "outputs" / "2026-08-04" / "runtime_20260804_110000"
        )
        _write_run_dir(tmp_path / "outputs" / "2026-08-04" / "runtime_20260804_100000")
        args = REPORT.argparse.Namespace(date="2026-08-04", output_dir=None)
        assert REPORT._resolve_output_dir(args) == newer

    def test_output_dir_run_dir_passthrough(self, tmp_path: Path) -> None:
        run_dir = _write_run_dir(tmp_path / "runtime_20260804_110000")
        args = REPORT.argparse.Namespace(date=None, output_dir=str(run_dir))
        assert REPORT._resolve_output_dir(args) == run_dir

    def test_output_dir_date_dir_resolves_to_latest_run(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(REPORT, "ROOT", tmp_path)
        newer = _write_run_dir(
            tmp_path / "outputs" / "2026-08-04" / "runtime_20260804_110000"
        )
        args = REPORT.argparse.Namespace(
            date=None, output_dir=str(tmp_path / "outputs" / "2026-08-04")
        )
        assert REPORT._resolve_output_dir(args) == newer

    def test_date_resolves_legacy_flat_dir(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(REPORT, "ROOT", tmp_path)
        flat = _write_run_dir(tmp_path / "outputs" / "2026-08-03")
        args = REPORT.argparse.Namespace(date="2026-08-03", output_dir=None)
        assert REPORT._resolve_output_dir(args) == flat

    def test_default_resolves_latest_run_dir(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(REPORT, "ROOT", tmp_path)
        latest = _write_run_dir(
            tmp_path / "outputs" / "2026-08-04" / "runtime_20260804_110000"
        )
        _write_run_dir(tmp_path / "outputs" / "2026-08-04" / "runtime_20260804_100000")
        args = REPORT.argparse.Namespace(date=None, output_dir=None)
        assert REPORT._resolve_output_dir(args) == latest


# ===========================================================================
# Outcome evaluator — directory resolution
# ===========================================================================


class TestEvaluatorResolution:
    def test_latest_run_dir_requires_outcome(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(EVAL, "ROOT", tmp_path)
        _write_run_dir(
            tmp_path / "outputs" / "2026-08-04" / "runtime_20260804_100000",
            with_outcome=False,
        )
        latest = _write_run_dir(
            tmp_path / "outputs" / "2026-08-04" / "runtime_20260804_110000",
            with_outcome=True,
        )
        assert EVAL._latest_run_dir() == latest

    def test_output_dir_date_dir_resolves_to_latest_with_outcome(
        self, tmp_path: Path
    ) -> None:
        latest = _write_run_dir(tmp_path / "outputs" / "2026-08-04" / "runtime_20260804_110000")
        _write_run_dir(tmp_path / "outputs" / "2026-08-04" / "runtime_20260804_100000")
        resolved = EVAL.latest_run_dir(
            tmp_path / "outputs" / "2026-08-04", predicate=EVAL._has_outcome
        )
        assert resolved == latest

    def test_output_dir_run_dir_kept_as_is(self, tmp_path: Path) -> None:
        run_dir = _write_run_dir(tmp_path / "runtime_20260804_110000")
        resolved = EVAL.latest_run_dir(run_dir, predicate=EVAL._has_outcome)
        assert resolved == run_dir


# ===========================================================================
# Daily scheduler — run directory resolution
# ===========================================================================


class TestDailyResolution:
    def test_resolve_run_dir_returns_latest_per_run_dir(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(DAILY, "ROOT", tmp_path)
        latest = _write_run_dir(
            tmp_path / "outputs" / "2026-08-04" / "runtime_20260804_110000"
        )
        _write_run_dir(tmp_path / "outputs" / "2026-08-04" / "runtime_20260804_100000")
        assert DAILY._resolve_run_dir("2026-08-04") == latest

    def test_resolve_run_dir_legacy_flat(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(DAILY, "ROOT", tmp_path)
        flat = _write_run_dir(tmp_path / "outputs" / "2026-08-04")
        assert DAILY._resolve_run_dir("2026-08-04") == flat

    def test_resolve_run_dir_none_when_absent(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(DAILY, "ROOT", tmp_path)
        assert DAILY._resolve_run_dir("2026-08-04") is None


# ===========================================================================
# Continuous monitor — PipelineRunner integration
# ===========================================================================


class TestMonitorRunner:
    @staticmethod
    def _patch_today(monkeypatch, run_date: str) -> None:
        from types import SimpleNamespace

        fake_date = type(
            "FakeDate",
            (),
            {
                "today": staticmethod(
                    lambda: type("D", (), {"isoformat": lambda self: run_date})()
                )
            },
        )
        monkeypatch.setattr(MON, "_dt", SimpleNamespace(date=fake_date))

    def test_run_resolves_new_run_dir_and_passes_output_dir(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        runner = MON.PipelineRunner(root=tmp_path, state_dir=tmp_path / "state")
        run_date = "2099-01-01"
        self._patch_today(monkeypatch, run_date)

        calls: list[list[str]] = []

        def fake_subprocess_run(cmd, **kwargs):
            calls.append(list(cmd))
            if str(cmd[1]).endswith("run.py"):
                run_dir = (
                    tmp_path / "outputs" / run_date / "runtime_20990101_120000"
                )
                _write_run_dir(run_dir)
            return type("R", (), {"returncode": 0})()

        monkeypatch.setattr(MON.subprocess, "run", fake_subprocess_run)

        rc, run_dir = runner.run("economic")
        assert rc == 0
        assert run_dir.name == "runtime_20990101_120000"
        assert (run_dir / "summary.json").read_text() != ""
        assert len(calls) == 2
        report_call = calls[1]
        assert report_call[1].endswith("generate_institutional_report.py")
        assert "--output-dir" in report_call
        assert report_call[report_call.index("--output-dir") + 1] == str(run_dir)

    def test_dry_run_returns_date_dir(self, tmp_path: Path, monkeypatch) -> None:
        runner = MON.PipelineRunner(
            root=tmp_path, state_dir=tmp_path / "state", dry_run=True
        )
        run_date = "2099-01-01"
        self._patch_today(monkeypatch, run_date)
        rc, run_dir = runner.run("economic")
        assert rc == 0
        assert run_dir == tmp_path / "outputs" / run_date

    def test_failed_run_does_not_generate_report(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        runner = MON.PipelineRunner(root=tmp_path, state_dir=tmp_path / "state")
        run_date = "2099-01-01"
        self._patch_today(monkeypatch, run_date)

        calls: list[list[str]] = []

        def fake_subprocess_run(cmd, **kwargs):
            calls.append(list(cmd))
            return type("R", (), {"returncode": 1})()

        monkeypatch.setattr(MON.subprocess, "run", fake_subprocess_run)

        rc, run_dir = runner.run("economic")
        assert rc == 1
        assert len(calls) == 1  # report script never invoked


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
