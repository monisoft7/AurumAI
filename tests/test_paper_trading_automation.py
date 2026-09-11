from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import paper_trading.automation as automation
from paper_trading.automation import (
    AutomationFailure,
    LockedBaseline,
    deterministic_evaluation_id,
    evaluation_exists,
    execute_automation,
    format_failure_message,
    format_success_message,
    immutable_snapshot,
    mode_plan,
    resolve_mode,
    scan_runtime_secrets,
    secret_presence,
    validate_append_only,
    write_failure_artifacts,
)
from paper_trading.ledger import HorizonNotComplete, evaluate_prediction


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "paper-trading-daily.yml"
BASELINE = "57f7cf70878dd364c4cb346ef19d129d54877e30"
COHORT_ID = "xauusd-paper-57f7cf7-v3"
HARNESS = "6ce0d848cd24167317f228ffd8772274e9a58166"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _environment() -> dict[str, str]:
    return {
        "FRED_API_KEY": "fred-value",
        "TELEGRAM_BOT_TOKEN": "telegram-value",
        "TELEGRAM_CHAT_ID": "chat-value",
        "PAPER_LEDGER_TOKEN": "ledger-value",
    }


def _success_context(decision: str = "BUY") -> dict[str, object]:
    return {
        "mode": "live-paper",
        "utc_time": "2026-09-07T07:17:00+00:00",
        "libya_time": "2026-09-07T09:17:00+02:00",
        "evaluation_id": "paper-2026-09-07",
        "runtime_id": "runtime_20260907_071700",
        "freshness": "FRED=fresh, XAU/USD=fresh, DXY=fresh, price=fresh",
        "decision": decision,
        "direction": "bullish" if decision == "BUY" else "bearish",
        "confidence": 0.81,
        "reliability": 0.74,
        "first_gate": "conviction_gate_pass",
        "gate_reason": "recorded decision-time reason",
        "risk_size": {"recommended_size": 0.2},
        "stage_count": "27/27",
        "completed_predictions": 3,
        "total_predictions": 8,
        "sample_status": "INSUFFICIENT_SAMPLE",
        "eligibility": "ELIGIBLE",
        "outcome_note": "pending; no horizon is due",
        "run_url": "https://github.example/actions/runs/1",
    }


def test_scheduled_mode_is_always_live_paper() -> None:
    assert resolve_mode("schedule", "dry-run") == "live-paper"


def test_workflow_dispatch_defaults_to_dry_run() -> None:
    assert resolve_mode("workflow_dispatch", None) == "dry-run"


def test_strategy_baseline_is_pinned_and_does_not_follow_main() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    config = json.loads(
        (ROOT / "config" / "paper_trading_baseline.json").read_text(encoding="utf-8")
    )
    assert config["baseline_commit"] == BASELINE
    assert config["cohort_id"] == COHORT_ID
    assert "ref: ${{ steps.paper-baseline.outputs.baseline_commit }}" in text
    strategy_block = text.split("Checkout frozen strategy baseline", 1)[1]
    strategy_block = strategy_block.split("Checkout private paper ledger", 1)[0]
    assert "ref: main" not in strategy_block


def test_daily_config_uses_only_the_locked_v3_cohort(tmp_path: Path) -> None:
    target = automation._create_daily_config(
        ROOT / "config" / "paper_trading_baseline.json",
        tmp_path / "paper-config.json",
        evaluation_id="paper-2026-09-10",
        harness_commit=HARNESS,
        github_actions={
            "run_id": "1",
            "run_attempt": "1",
            "run_url": "https://github.example/actions/runs/1",
            "run_created_at_utc": "2026-09-10T07:17:00Z",
        },
    )
    config = json.loads(target.read_text(encoding="utf-8"))
    assert config["cohort_id"] == COHORT_ID
    assert config["baseline_commit"] == BASELINE
    legacy_fragment = "2acd" + "5ad"
    assert legacy_fragment not in (
        ROOT / "src" / "paper_trading" / "automation.py"
    ).read_text(encoding="utf-8")


def test_dry_run_never_calls_pipeline_or_writes_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    strategy = tmp_path / "strategy"
    harness = tmp_path / "harness"
    ledger = tmp_path / "ledger"
    for path in (strategy, harness, ledger):
        path.mkdir()
    monkeypatch.setattr(
        automation,
        "_preflight",
        lambda **_: (LockedBaseline(COHORT_ID, BASELINE), HARNESS),
    )
    monkeypatch.setattr(automation, "evaluation_exists", lambda *_: False)
    called = False

    def forbidden_runner(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("pipeline must not run")

    before = list(ledger.rglob("*"))
    result = execute_automation(
        mode="dry-run",
        strategy_dir=strategy,
        harness_dir=harness,
        ledger_dir=ledger,
        output_dir=tmp_path / "artifacts",
        market_date="2026-09-07",
        ledger_repository="owner/private-ledger",
        run_id="1",
        run_url="https://github.example/actions/runs/1",
        environment=_environment(),
        runner=forbidden_runner,
    )
    assert called is False
    assert list(ledger.rglob("*")) == before
    assert result["mode"] == "dry-run"
    dry_message = (
        tmp_path / "artifacts" / "telegram_message.txt"
    ).read_text(encoding="utf-8")
    assert "اختبار AurumAI Paper Trading" in dry_message
    assert "0/27" in dry_message


def test_cli_loads_from_github_checkout_layout_without_installed_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "parent"
    harness = parent / "harness"
    for path in (
        harness / "scripts",
        harness / "src" / "paper_trading",
        parent / "strategy",
        parent / "ledger",
        parent / "automation-artifacts",
    ):
        path.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts" / "paper_trading.py", harness / "scripts")
    for name in ("__init__.py", "ledger.py"):
        shutil.copy2(
            ROOT / "src" / "paper_trading" / name,
            harness / "src" / "paper_trading" / name,
        )

    monkeypatch.chdir(parent)
    legacy = subprocess.run(
        [sys.executable, str(Path("harness/scripts/paper_trading.py")), "--help"],
        cwd=harness,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert legacy.returncode != 0
    assert "[Errno 2]" in legacy.stderr

    automation._load_paper_trading_cli(Path("harness"))


def test_failure_result_has_safe_error_type_without_internal_details(
    tmp_path: Path,
) -> None:
    secret = "never-write-this-secret"
    failure = AutomationFailure(
        "preflight",
        "paper-trading CLI failed to load",
        error_type="ModuleNotFoundError",
        missing_module="paper_trading.ledger",
    )
    write_failure_artifacts(
        tmp_path,
        failure,
        run_url="https://github.example/actions/runs/1",
        environment={**_environment(), "TELEGRAM_BOT_TOKEN": secret},
    )
    result_text = (tmp_path / "result.json").read_text(encoding="utf-8")
    result = json.loads(result_text)
    assert result["error_type"] == "ModuleNotFoundError"
    assert result["missing_module"] == "paper_trading.ledger"
    assert secret not in result_text
    assert "Traceback" not in result_text
    assert "environment" not in result
    message = (tmp_path / "telegram_message.txt").read_text(encoding="utf-8")
    assert "ModuleNotFoundError" not in message
    assert "paper_trading.ledger" not in message


def test_evaluation_id_is_daily_and_deterministic() -> None:
    assert deterministic_evaluation_id("2026-09-07") == "paper-2026-09-07"
    assert deterministic_evaluation_id("2026-09-07") == deterministic_evaluation_id(
        "2026-09-07"
    )


def test_duplicate_daily_evaluation_stops_before_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    strategy = tmp_path / "strategy"
    harness = tmp_path / "harness"
    ledger = tmp_path / "ledger"
    for path in (strategy, harness, ledger):
        path.mkdir()
    _write_json(
        ledger / "predictions" / "existing.json",
        {"evaluation_id": "paper-2026-09-07"},
    )
    assert evaluation_exists(ledger, "paper-2026-09-07") is True
    monkeypatch.setattr(
        automation,
        "_preflight",
        lambda **_: (LockedBaseline(COHORT_ID, BASELINE), HARNESS),
    )
    with pytest.raises(AutomationFailure, match="already exists"):
        execute_automation(
            mode="live-paper",
            strategy_dir=strategy,
            harness_dir=harness,
            ledger_dir=ledger,
            output_dir=tmp_path / "artifacts",
            market_date="2026-09-07",
            ledger_repository="owner/private-ledger",
            run_id="1",
            run_url="https://github.example/actions/runs/1",
            environment=_environment(),
            runner=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("pipeline must not run")
            ),
        )


def test_market_holiday_or_stale_sources_are_ineligible() -> None:
    freshness = automation._major_freshness(
        {"FRED": "fresh", "gold": "stale", "dxy": "fresh"}
    )
    assert freshness["XAU/USD"] == "stale"
    assert freshness["price"] == "stale"
    context = _success_context("NO_TRADE")
    context["eligibility"] = "INELIGIBLE"
    assert "INELIGIBLE" in format_success_message(context)


@pytest.mark.parametrize("decision", ["BUY", "SELL", "NO_TRADE"])
def test_success_formatter_covers_all_decisions_in_arabic(decision: str) -> None:
    message = format_success_message(_success_context(decision))
    assert "PAPER TRADING فقط" in message
    assert f"القرار: {decision}" in message
    assert "حالة العينة:" in message


def test_failure_formatter_is_short_and_confirms_no_prediction() -> None:
    message = format_failure_message(
        stage="pipeline",
        reason="exit code 1",
        run_url="https://github.example/actions/runs/1",
    )
    assert "المرحلة: pipeline" in message
    assert "لم يتم إنشاء prediction مؤهلة" in message
    assert "Traceback" not in message
    assert len(message) < 3500


def test_telegram_escapes_external_text_and_enforces_length() -> None:
    context = _success_context()
    context["gate_reason"] = "<unsafe>&" + "x" * 5000
    message = format_success_message(context)
    assert "&lt;unsafe&gt;&amp;" in message
    assert len(message) < 3500


def test_secret_values_never_appear_in_messages_or_sanitized_logs(
    tmp_path: Path,
) -> None:
    secret = "do-not-leak-this-value"
    context = _success_context()
    context["gate_reason"] = f"token={secret}"
    message = format_success_message(context, secrets=(secret,))
    assert secret not in message
    automation._write_sanitized_log(
        tmp_path / "safe.log", f"authorization: {secret}", (secret,)
    )
    assert secret not in (tmp_path / "safe.log").read_text(encoding="utf-8")


def test_structural_secret_scan_reports_location_not_value(tmp_path: Path) -> None:
    secret = "private-token-value"
    path = tmp_path / "runtime.json"
    _write_json(path, {"nested": {"token": secret}})
    with pytest.raises(AutomationFailure) as caught:
        scan_runtime_secrets([path], (secret,))
    assert secret not in str(caught.value)


def test_ledger_diff_rejects_modify_or_delete_of_prediction(tmp_path: Path) -> None:
    prediction = tmp_path / "predictions" / "one.json"
    _write_json(prediction, {"immutable": True})
    before = immutable_snapshot(tmp_path)
    _write_json(prediction, {"immutable": False})
    with pytest.raises(AutomationFailure, match="changed"):
        validate_append_only(tmp_path, before)
    prediction.unlink()
    with pytest.raises(AutomationFailure, match="changed"):
        validate_append_only(tmp_path, before)


def test_pending_outcome_is_not_evaluated_early(tmp_path: Path) -> None:
    prediction = tmp_path / "prediction.json"
    _write_json(
        prediction,
        {
            "schema_version": "1.0",
            "prediction_id": "pred_one",
            "evaluation_id": "paper-2026-09-07",
            "cohort_id": COHORT_ID,
            "baseline_commit": BASELINE,
            "runtime_id": "runtime_one",
            "decision": "BUY",
            "decision_timestamp": "2026-09-07T07:17:00Z",
            "evaluation_horizons_sessions": [1, 3, 5],
            "transaction_costs": {
                "round_trip_cost_bps": 10,
                "slippage_bps_per_side": 2,
            },
            "financially_eligible": True,
        },
    )
    prices = tmp_path / "prices.csv"
    prices.write_text(
        "timestamp,close,available_at_utc\n"
        "2026-09-07T21:00:00Z,2500,2026-09-07T21:00:00Z\n",
        encoding="utf-8",
    )
    with pytest.raises(HorizonNotComplete):
        evaluate_prediction(
            prediction,
            tmp_path / "outcomes",
            prices,
            horizon_sessions=1,
            as_of_utc="2026-09-07T21:00:00Z",
        )
    assert not (tmp_path / "outcomes").exists()


def test_workflow_yaml_policy_is_valid_and_read_only() -> None:
    data = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert data["on"]["schedule"][0]["cron"] == "17 7 * * 1-5"
    mode = data["on"]["workflow_dispatch"]["inputs"]["mode"]
    assert mode["default"] == "dry-run"
    assert data["permissions"] == {"contents": "read", "actions": "read"}
    assert data["concurrency"]["group"] == "aurumai-paper-trading-daily"
    assert data["concurrency"]["cancel-in-progress"] == "false"
    install = next(
        step for step in data["jobs"]["paper-trading"]["steps"]
        if step.get("name") == "Install strategy dependencies"
    )
    assert install["if"] == "env.AUTOMATION_MODE == 'live-paper'"
    assert "pull_request_target" not in data["on"]
    assert "\t" not in WORKFLOW.read_text(encoding="utf-8")


def test_paper_trading_is_the_only_daily_schedule_and_legacy_workflow_is_gone() -> None:
    workflow_dir = ROOT / ".github" / "workflows"
    assert not (workflow_dir / "aurumai-daily.yml").exists()
    scheduled_names = []
    for path in sorted((*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml"))):
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        if isinstance(data, dict) and isinstance(data.get("on"), dict):
            if data["on"].get("schedule"):
                scheduled_names.append(data.get("name"))
    assert scheduled_names == ["AurumAI Daily Paper Trading"]


def test_cleanup_does_not_modify_historical_data_outputs_or_runtime() -> None:
    historical = ROOT / "data" / "economic" / "DGS10.csv"
    before = historical.read_bytes()
    with pytest.raises(AssertionError, match="protected repository"):
        historical.write_bytes(b"must not replace historical data")
    with pytest.raises(AssertionError, match="protected repository"):
        historical.unlink()
    assert historical.read_bytes() == before


def test_workflow_has_no_broker_or_live_order_integration() -> None:
    text = WORKFLOW.read_text(encoding="utf-8").lower()
    forbidden = ("place_order", "submit_order", "metatrader5", "mt5.initialize", "alpaca")
    assert all(item not in text for item in forbidden)


def test_secret_presence_returns_names_and_status_only() -> None:
    result = secret_presence(_environment())
    assert set(result.values()) == {"PRESENT"}
    assert not any(value in json.dumps(result) for value in _environment().values())


def test_mode_plan_separates_dry_and_live_side_effects() -> None:
    dry = mode_plan("dry-run")
    live = mode_plan("live-paper")
    assert (dry.run_pipeline, dry.write_ledger) == (False, False)
    assert (live.run_pipeline, live.write_ledger) == (True, True)
