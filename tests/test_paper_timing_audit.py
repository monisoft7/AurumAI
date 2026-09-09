from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import socket
import subprocess
from pathlib import Path

import pytest
import yaml

import paper_trading.automation as automation
from paper_trading.ledger import (
    PaperTradingError, evaluate_prediction, summarize_cohort,
)
from test_paper_trading import (
    _manifest, _prices, _runtime, _seed_completed_record, _write_json, EVALUATION_ID,
)
from test_paper_trading_automation import ROOT, WORKFLOW, BASELINE, HARNESS, _environment


def _load_cli(path):
    spec = importlib.util.spec_from_file_location("offline_test_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("created", ["2026-01-01T12:00:00Z", "2026-01-01T12:01:00Z"])
def test_order_accepts_equal_decision_and_equal_evaluation(tmp_path, created):
    prediction, ledger = _manifest(tmp_path)
    data = json.loads(prediction.read_text())
    data["created_at_utc"] = created
    _write_json(prediction, data)
    result = evaluate_prediction(
        prediction, ledger / "outcomes", _prices(tmp_path / "prices.csv"),
        horizon_sessions=1, as_of_utc="2026-01-05T21:00:00Z",
    )
    assert json.loads(result.read_text())["status"] == "completed"
    assert summarize_cohort(ledger, EVALUATION_ID)["completed_trades"] == 1


@pytest.mark.parametrize("created", [
    "2026-01-02T21:00:00Z", "2026-01-02T21:00:01Z", "2026-01-01T11:59:59Z",
])
def test_late_or_predated_prediction_rejected_without_outcome(tmp_path, created):
    prediction, ledger = _manifest(tmp_path)
    data = json.loads(prediction.read_text())
    data["created_at_utc"] = created
    _write_json(prediction, data)
    before = prediction.read_bytes()
    with pytest.raises(PaperTradingError, match="lookahead_or_timestamp_violation"):
        evaluate_prediction(
            prediction, ledger / "outcomes", _prices(tmp_path / "prices.csv"),
            horizon_sessions=1, as_of_utc="2026-01-05T21:00:00Z",
        )
    assert prediction.read_bytes() == before
    assert not (ledger / "outcomes").exists()


@pytest.mark.parametrize("created", ["equal", "late", "missing"])
def test_historical_late_prediction_forces_no_go_even_with_matching_hash(tmp_path, created):
    ledger = tmp_path / "ledger"
    for index in range(30):
        _seed_completed_record(ledger, index)
    assert summarize_cohort(ledger, EVALUATION_ID)["economic_gate"]["status"] == "GO"
    prediction = ledger / "predictions/pred_00.json"
    outcome = ledger / "outcomes/pred_00.h1.outcome.json"
    p, o = json.loads(prediction.read_text()), json.loads(outcome.read_text())
    if created == "missing":
        p.pop("created_at_utc")
    else:
        p["created_at_utc"] = o["entry"]["timestamp"] if created == "equal" else o["exit"]["timestamp"]
    _write_json(prediction, p)
    o["prediction_sha256"] = hashlib.sha256(prediction.read_bytes()).hexdigest()
    _write_json(outcome, o)
    result = summarize_cohort(ledger, EVALUATION_ID)
    assert result["economic_gate"]["status"] == "NO_GO"
    assert result["completed_trades"] == 29


def test_real_checkout_layout_preflight_create_summarize_and_manifest(tmp_path, monkeypatch):
    parent = tmp_path / "GitHub workspace with spaces"
    harness, strategy, ledger, output = [parent / n for n in (
        "harness", "strategy", "ledger", "automation-artifacts"
    )]
    for folder in (harness / "scripts", harness / "src/paper_trading", harness / "config",
                   strategy, ledger / ".git", output):
        folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts/paper_trading.py", harness / "scripts")
    for name in ("__init__.py", "ledger.py"):
        shutil.copy2(ROOT / "src/paper_trading" / name, harness / "src/paper_trading")
    shutil.copy2(ROOT / "config/paper_trading_baseline.json", harness / "config")
    monkeypatch.chdir(parent)
    calls = []

    def read_only_git(root, *args, **kwargs):
        assert Path(root).is_absolute()
        if args == ("remote", "get-url", "origin"):
            return subprocess.CompletedProcess(args, 0, "https://github.example/owner/ledger", "")
        assert args == ("rev-parse", "HEAD")
        return subprocess.CompletedProcess(args, 0, BASELINE if root == strategy else HARNESS, "")

    monkeypatch.setattr(automation, "_git", read_only_git)
    original_load = automation._load_paper_trading_cli

    def preflight_cli(root):
        assert root == harness and root.is_absolute()
        calls.append("preflight")
        original_load(root)  # Actual offline --help subprocess, guarded by conftest.

    monkeypatch.setattr(automation, "_load_paper_trading_cli", preflight_cli)
    published = []
    monkeypatch.setattr(automation, "_commit_ledger", lambda *args: published.append(args))

    def synthetic_runner(command, *, cwd, environment, **kwargs):
        assert Path(cwd).is_absolute()
        assert all(key not in environment for key in (
            "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "PAPER_LEDGER_TOKEN"
        ))
        if command[1] == "run.py":
            calls.append("synthetic-runtime")
            run = _runtime(strategy / "outputs")
            stage = json.loads((run / "stage_outputs.json").read_text())
            stage["outputs"]["finalize"]["source_freshness"]["dxy"] = "fresh"
            stage["outputs"].update({f"fixture_{i}": {} for i in range(25)})
            stage["stage_count"] = 27
            stage["stage_ids"] = list(stage["outputs"])
            _write_json(run / "stage_outputs.json", stage)
            summary = json.loads((run / "summary.json").read_text())
            summary["stage_output_count"] = 27
            _write_json(run / "summary.json", summary)
            _write_json(run / "stages.json", [
                {"stage_id": stage_id, "status": "ok", "duration_ms": 1.5}
                for stage_id in stage["stage_ids"]
            ])
            _write_json(run / "finalize.json", {})
            _write_json(strategy / "runtime/run_registry.jsonl", {
                "run_id": "runtime_1", "output_directory": str(run),
                "report_path": str(run / "institutional_report.md"),
            })
        elif command[1] == "scripts/generate_institutional_report.py":
            (Path(command[-1]) / "institutional_report.md").write_text("Synthetic report")
        else:
            cli = Path(command[1])
            assert cwd == harness and cli == harness / "scripts/paper_trading.py"
            assert cli.is_file()
            assert command[2] in {"create", "summarize"}
            calls.append(command[2])
            for flag in ("--registry-dir", "--runtime-dir", "--config", "--output"):
                if flag in command:
                    assert Path(command[command.index(flag) + 1]).is_absolute()
            with monkeypatch.context() as nested:
                nested.chdir(cwd)
                assert _load_cli(cli).main(command[2:]) == 0
        return subprocess.CompletedProcess(command, 0, "", "")

    result = automation.execute_automation(
        mode="live-paper", strategy_dir=Path("strategy"), harness_dir=Path("harness"),
        ledger_dir=Path("ledger"), output_dir=Path("automation-artifacts"),
        market_date="2026-01-01", ledger_repository="owner/ledger", run_id="123",
        run_attempt="2", run_created_at_utc="2026-01-01T11:59:00Z",
        run_url="https://github.example/owner/repo/actions/runs/123",
        environment=_environment(), runner=synthetic_runner,
    )
    assert calls == ["preflight", "synthetic-runtime", "create", "summarize"]
    assert len(published) == 1  # A stub only: no Git mutation or network.
    prediction = output / "prediction.json"
    manifest = json.loads((output / "run-manifest.json").read_text())
    assert manifest["prediction_sha256"] == hashlib.sha256(prediction.read_bytes()).hexdigest()
    assert manifest["github_actions"] == json.loads(prediction.read_text())["github_actions"]
    assert manifest["github_actions"]["run_attempt"] == "2"
    assert manifest["paper_evaluation"] == result["paper_evaluation"]
    assert result["paper_evaluation"]["financially_eligible"] is True
    assert "not proof" in manifest["timing_evidence"]
    assert result["mode"] == "live-paper"


@pytest.mark.parametrize("mode,failed", [("dry-run", True), ("dry-run", False),
                                          ("live-paper", True), ("live-paper", False)])
def test_telegram_mode_and_failure_delivery_are_hermetic(tmp_path, monkeypatch, mode, failed):
    cli = _load_cli(ROOT / "scripts/paper_trading_automation.py")
    monkeypatch.setattr(cli.os, "environ", {})
    sent = []
    monkeypatch.setattr(cli, "send_telegram_message", lambda text, **kwargs: sent.append(text))
    if failed:
        automation.write_failure_artifacts(
            tmp_path, automation.AutomationFailure("pipeline", "synthetic failure"),
            run_url="https://github.example/actions/runs/123", environment={},
        )
    else:
        (tmp_path / "telegram_message.txt").write_text("Synthetic success")
    assert cli.main([
        "send-telegram", "--mode", mode, "--run-url", "https://github.example/actions/runs/123",
        "--message-file", str(tmp_path / "telegram_message.txt"),
    ]) == 0
    assert len(sent) == (1 if mode == "live-paper" else 0)
    if sent and failed:
        assert "pipeline" in sent[0]


def test_live_failure_before_message_exists_has_fallback(tmp_path, monkeypatch):
    cli = _load_cli(ROOT / "scripts/paper_trading_automation.py")
    monkeypatch.setattr(cli.os, "environ", {})
    sent = []
    monkeypatch.setattr(cli, "send_telegram_message", lambda text, **kwargs: sent.append(text))
    assert cli.main(["send-telegram", "--mode", "live-paper", "--run-url",
                     "https://github.example/actions/runs/123", "--message-file",
                     str(tmp_path / "missing.txt")]) == 0
    assert len(sent) == 1 and "workflow" in sent[0]


def test_workflow_schedule_provenance_and_explicit_telegram_condition():
    paper = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    operations = yaml.load((ROOT / ".github/workflows/aurumai-daily.yml").read_text(),
                           Loader=yaml.BaseLoader)
    assert paper["on"]["schedule"] == [{"cron": "17 7 * * 1-5"}]
    assert operations["on"]["schedule"] == [{"cron": "0 22 * * 1-5"}]
    steps = paper["jobs"]["paper-trading"]["steps"]
    telegram = next(s for s in steps if s["name"] == "Send Arabic Telegram summary")
    assert telegram["if"] == "${{ always() && env.AUTOMATION_MODE == 'live-paper' }}"
    metadata = next(s for s in steps if s.get("id") == "run-metadata")
    assert "--jq .created_at" in metadata["run"]
    execute = next(s for s in steps if s.get("id") == "paper")
    assert '--run-attempt "${{ github.run_attempt }}"' in execute["run"]
    assert '--run-created-at-utc "$RUN_CREATED_AT_UTC"' in execute["run"]
    assert next(s for s in steps if s["name"] == "Checkout frozen strategy baseline")["with"]["ref"] == BASELINE


def test_test_boundary_blocks_git_network_and_runtime():
    for command in (["git", "commit", "-m", "forbidden"], ["git", "push"],
                    ["python", "run.py"], ["gh", "api", "user"]):
        with pytest.raises(AssertionError, match="forbidden"):
            subprocess.run(command)
    with pytest.raises(AssertionError, match="forbidden"):
        socket.create_connection(("example.invalid", 443))


@pytest.mark.parametrize("attempt,created", [
    (None, "2026-01-01T00:00:00Z"), ("0", "2026-01-01T00:00:00Z"),
    ("1", None), ("1", "not-a-time"), ("1", "2999-01-01T00:00:00Z"),
])
def test_incomplete_run_provenance_stops_before_runtime(tmp_path, monkeypatch, attempt, created):
    monkeypatch.setattr(automation, "_preflight", lambda **kwargs: (BASELINE, HARNESS))
    monkeypatch.setattr(automation, "evaluation_exists", lambda *args: False)

    def forbidden_runtime(*args, **kwargs):
        raise AssertionError("runtime must not be reached")

    with pytest.raises(automation.AutomationFailure):
        automation.execute_automation(
            mode="live-paper", strategy_dir=tmp_path / "strategy", harness_dir=tmp_path / "harness",
            ledger_dir=tmp_path / "ledger", output_dir=tmp_path / "artifacts",
            market_date="2026-01-01", ledger_repository="owner/ledger", run_id="123",
            run_attempt=attempt, run_created_at_utc=created,
            run_url="https://github.example/actions/runs/123", environment={},
            runner=forbidden_runtime,
        )
