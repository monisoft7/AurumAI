from __future__ import annotations

import hashlib
import json
import datetime as dt
from pathlib import Path

import pytest

from paper_trading.ledger import (
    HorizonNotComplete,
    PaperTradingError,
    create_prediction_manifest,
    evaluate_prediction,
    prediction_sha256,
    summarize_cohort,
)


BASELINE = "57f7cf70878dd364c4cb346ef19d129d54877e30"
EVALUATION_ID = "test-paper-v1"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "paper-config.json"
    _write_json(
        path,
        {
            "evaluation_id": EVALUATION_ID,
            "cohort_id": EVALUATION_ID,
            "baseline_commit": BASELINE,
            "instrument": "XAU/USD",
            "timezone": "UTC",
            "evaluation_horizons_sessions": [1, 3, 5],
            "entry_rule": {
                "entry": "first session close strictly after decision",
                "exit": "Nth completed session close",
            },
            "transaction_costs": {
                "round_trip_cost_bps": 10.0,
                "slippage_bps_per_side": 2.0,
            },
            "minimum_completed_trades": 30,
            "minimum_calendar_days": 60,
            "go_thresholds": {
                "net_expectancy_pct_gt": 0.0,
                "profit_factor_gte": 1.2,
                "max_drawdown_pct_lte": 10.0,
            },
        },
    )
    return path


def _runtime(
    tmp_path: Path,
    runtime_id: str = "runtime_1",
    decision: str = "BUY",
    *,
    secret: str | None = None,
) -> Path:
    run = tmp_path / runtime_id
    source_freshness = {
        name: {
            "status": "fresh",
            "observation_date": "2026-01-01",
            "retrieved_at": "2026-01-01T12:00:00Z",
            "max_age_days": 7,
        }
        for name in (
            "DGS10",
            "DFII10",
            "T5YIE",
            "CPI",
            "Gold",
            "DXY",
        )
    }
    outputs = {
        "finalize": {
            "source_freshness": source_freshness,
            "decision": {
                "decision": decision,
                "institutional_confidence": 0.8,
                "decision_explanation": "recorded gate result",
                "metadata": {"selected_thesis_direction": "bullish"},
            },
        },
        "trade_recommendation": {
            "source_freshness": {"recommendation": "fresh"},
            "reliability": 0.7,
            "recommended_size": 0.25,
        },
    }
    if secret:
        outputs["finalize"]["credentials"] = {
            "api_key": secret,
            "token": secret,
        }
    _write_json(
        run / "stage_outputs.json",
        {
            "schema_version": "1.0",
            "pipeline_id": runtime_id,
            "stage_count": 2,
            "stage_ids": ["finalize", "trade_recommendation"],
            "outputs": outputs,
        },
    )
    _write_json(
        run / "summary.json",
        {
            "pipeline_id": runtime_id,
            "timestamp": "2026-01-01T12:00:00Z",
            "success": True,
            "errors": [],
            "failed_stages": [],
            "stage_output_count": 2,
            "decision": decision,
            "decision_confidence": 0.8,
            "debug_secret": secret,
        },
    )
    _write_json(
        run / "outcome.json",
        {
            "schema_version": "1.1",
            "status": "pending",
            "run_id": runtime_id,
            "decision": decision,
            "decision_snapshot": {
                "gate_reasons": {"conviction_gate_pass": decision != "NO_TRADE"}
            },
        },
    )
    return run


def _manifest(
    tmp_path: Path, runtime_id: str = "runtime_1", decision: str = "BUY"
) -> tuple[Path, Path]:
    ledger = tmp_path / "ledger"
    path = create_prediction_manifest(
        _runtime(tmp_path / "runs", runtime_id, decision),
        ledger,
        _config(tmp_path),
        baseline_commit=BASELINE,
        created_at_utc="2026-01-01T12:01:00Z",
    )
    return path, ledger


def _prices(path: Path) -> Path:
    path.write_text(
        "timestamp,close,available_at_utc\n"
        "2026-01-02T21:00:00Z,100,2026-01-02T21:00:00Z\n"
        "2026-01-05T21:00:00Z,110,2026-01-05T21:00:00Z\n"
        "2026-01-06T21:00:00Z,108,2026-01-06T21:00:00Z\n"
        "2026-01-07T21:00:00Z,112,2026-01-07T21:00:00Z\n"
        "2026-01-08T21:00:00Z,115,2026-01-08T21:00:00Z\n"
        "2026-01-09T21:00:00Z,116,2026-01-09T21:00:00Z\n",
        encoding="utf-8",
    )
    return path


def test_create_complete_prediction_manifest(tmp_path: Path) -> None:
    manifest_path, _ = _manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "pending"
    assert manifest["decision"] == "BUY"
    assert manifest["evaluation_horizons_sessions"] == [1, 3, 5]
    assert manifest["financially_eligible"] is True
    assert {item["path"] for item in manifest["artifacts"]} == {
        "stage_outputs.json",
        "summary.json",
        "outcome.json",
    }
    assert all(len(item["sha256"]) == 64 for item in manifest["artifacts"])


def test_rejects_incomplete_runtime_and_wrong_baseline(tmp_path: Path) -> None:
    run = _runtime(tmp_path / "runs")
    (run / "outcome.json").unlink()
    with pytest.raises(PaperTradingError, match="outcome.json"):
        create_prediction_manifest(
            run, tmp_path / "ledger", _config(tmp_path), baseline_commit=BASELINE
        )
    run = _runtime(tmp_path / "other-runs")
    with pytest.raises(PaperTradingError, match="baseline"):
        create_prediction_manifest(
            run, tmp_path / "ledger", _config(tmp_path), baseline_commit="0" * 40
        )


def test_rejects_schema_count_mismatch(tmp_path: Path) -> None:
    run = _runtime(tmp_path / "runs")
    payload = json.loads((run / "stage_outputs.json").read_text(encoding="utf-8"))
    payload["stage_count"] = 99
    _write_json(run / "stage_outputs.json", payload)
    with pytest.raises(PaperTradingError, match="count mismatch"):
        create_prediction_manifest(
            run, tmp_path / "ledger", _config(tmp_path), baseline_commit=BASELINE
        )


def test_rejects_duplicate_prediction(tmp_path: Path) -> None:
    run = _runtime(tmp_path / "runs")
    kwargs = {
        "baseline_commit": BASELINE,
        "created_at_utc": "2026-01-01T12:01:00Z",
    }
    create_prediction_manifest(run, tmp_path / "ledger", _config(tmp_path), **kwargs)
    with pytest.raises(PaperTradingError, match="already exists"):
        create_prediction_manifest(run, tmp_path / "ledger", _config(tmp_path), **kwargs)


def test_prediction_hash_stable_when_outcome_is_written(tmp_path: Path) -> None:
    manifest, ledger = _manifest(tmp_path)
    before = manifest.read_bytes()
    before_hash = prediction_sha256(manifest)
    outcome = evaluate_prediction(
        manifest,
        ledger / "outcomes",
        _prices(tmp_path / "prices.csv"),
        horizon_sessions=1,
        as_of_utc="2026-01-05T21:00:00Z",
    )
    assert manifest.read_bytes() == before
    assert prediction_sha256(manifest) == before_hash
    assert json.loads(outcome.read_text())["prediction_sha256"] == before_hash


def test_prevents_lookahead_and_early_evaluation(tmp_path: Path) -> None:
    manifest, ledger = _manifest(tmp_path)
    prices = _prices(tmp_path / "prices.csv")
    with pytest.raises(HorizonNotComplete):
        evaluate_prediction(
            manifest,
            ledger / "outcomes",
            prices,
            horizon_sessions=3,
            as_of_utc="2026-01-05T20:59:59Z",
        )
    assert not (ledger / "outcomes").exists()


def test_buy_sell_and_locked_costs(tmp_path: Path) -> None:
    prices = _prices(tmp_path / "prices.csv")
    buy, ledger = _manifest(tmp_path, "buy", "BUY")
    sell, _ = _manifest(tmp_path, "sell", "SELL")
    buy_out = evaluate_prediction(
        buy, ledger / "outcomes", prices, horizon_sessions=1, as_of_utc="2026-01-05T21:00:00Z"
    )
    sell_out = evaluate_prediction(
        sell, ledger / "outcomes", prices, horizon_sessions=1, as_of_utc="2026-01-05T21:00:00Z"
    )
    buy_data = json.loads(buy_out.read_text())
    sell_data = json.loads(sell_out.read_text())
    assert buy_data["gross_return_pct"] == 10.0
    assert buy_data["transaction_cost_pct"] == 0.14
    assert buy_data["net_return_pct"] == 9.86
    assert sell_data["gross_return_pct"] == -10.0
    assert sell_data["net_return_pct"] == -10.14


def test_no_trade_has_no_fabricated_return(tmp_path: Path) -> None:
    manifest, ledger = _manifest(tmp_path, decision="NO_TRADE")
    outcome = evaluate_prediction(
        manifest,
        ledger / "outcomes",
        _prices(tmp_path / "prices.csv"),
        horizon_sessions=1,
        as_of_utc="2026-01-05T21:00:00Z",
    )
    data = json.loads(outcome.read_text())
    assert data["status"] == "completed"
    assert data["eligible_trade"] is False
    assert data["gross_return_pct"] is None
    assert data["net_return_pct"] is None


def test_rejects_duplicate_horizon(tmp_path: Path) -> None:
    manifest, ledger = _manifest(tmp_path)
    prices = _prices(tmp_path / "prices.csv")
    kwargs = {"horizon_sessions": 1, "as_of_utc": "2026-01-05T21:00:00Z"}
    evaluate_prediction(manifest, ledger / "outcomes", prices, **kwargs)
    with pytest.raises(PaperTradingError, match="already evaluated"):
        evaluate_prediction(manifest, ledger / "outcomes", prices, **kwargs)


@pytest.mark.parametrize("freshness", ["stale", "unknown"])
def test_due_stale_or_unknown_outcome_is_recorded_unevaluable(
    tmp_path: Path, freshness: str
) -> None:
    manifest, ledger = _manifest(tmp_path)
    outcome = evaluate_prediction(
        manifest,
        ledger / "outcomes",
        _prices(tmp_path / "prices.csv"),
        horizon_sessions=1,
        as_of_utc="2026-01-05T21:00:00Z",
        freshness_status=freshness,
    )
    data = json.loads(outcome.read_text())
    assert data["status"] == "unevaluable"
    assert data["exclusion_reason"] == "outcome_data_not_fresh"
    assert data["price_data"]["sha256"] is not None


def test_stale_outcome_is_not_checked_before_horizon(tmp_path: Path) -> None:
    manifest, ledger = _manifest(tmp_path)
    with pytest.raises(HorizonNotComplete):
        evaluate_prediction(
            manifest,
            ledger / "outcomes",
            _prices(tmp_path / "prices.csv"),
            horizon_sessions=3,
            as_of_utc="2026-01-05T20:59:59Z",
            freshness_status="stale",
        )
    assert not (ledger / "outcomes").exists()


def _seed_completed_record(
    ledger: Path, index: int, *, total: int = 30
) -> None:
    decision_dt = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=index * 2)
    entry_dt = decision_dt + dt.timedelta(hours=6)
    exit_dt = entry_dt + dt.timedelta(days=1)
    decision_time = decision_dt.isoformat().replace("+00:00", "Z")
    entry_time = entry_dt.isoformat().replace("+00:00", "Z")
    exit_time = exit_dt.isoformat().replace("+00:00", "Z")
    prediction_id = f"pred_{index:02d}"
    prediction = {
        "schema_version": "1.0",
        "artifact": "paper_trading_prediction",
        "prediction_id": prediction_id,
        "evaluation_id": EVALUATION_ID,
        "cohort_id": EVALUATION_ID,
        "decision_timestamp": decision_time,
        "created_at_utc": decision_time,
        "decision": "BUY",
        "confidence": 0.8,
        "reliability": 0.8,
        "financially_eligible": True,
        "evaluation_horizons_sessions": [1, 3, 5],
        "economic_gate": {
            "minimum_completed_trades": 30,
            "minimum_calendar_days": 60,
            "net_expectancy_pct_gt": 0.0,
            "profit_factor_gte": 1.2,
            "max_drawdown_pct_lte": 10.0,
        },
    }
    prediction_path = ledger / "predictions" / f"{prediction_id}.json"
    _write_json(prediction_path, prediction)
    prediction_hash = hashlib.sha256(prediction_path.read_bytes()).hexdigest()
    net = 1.0 if index % 3 else -0.2
    outcome = {
        "schema_version": "1.0",
        "prediction_id": prediction_id,
        "prediction_sha256": prediction_hash,
        "evaluation_id": EVALUATION_ID,
        "horizon_sessions": 1,
        "status": "completed",
        "eligible_trade": True,
        "evaluated_at_utc": exit_time,
        "entry": {"timestamp": entry_time, "close": 100.0},
        "exit": {"timestamp": exit_time, "close": 101.0},
        "net_return_pct": net,
    }
    _write_json(ledger / "outcomes" / f"{prediction_id}.h1.outcome.json", outcome)


def test_cohort_metrics_and_minimum_sample_gate(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    for index in range(29):
        _seed_completed_record(ledger, index)
    partial = summarize_cohort(ledger, EVALUATION_ID)
    assert partial["completed_trades"] == 29
    assert partial["economic_gate"]["status"] == "INSUFFICIENT_SAMPLE"
    _seed_completed_record(ledger, 29)
    complete = summarize_cohort(ledger, EVALUATION_ID)
    assert complete["total_decisions"] == 30
    assert complete["completed_trades"] == 30
    assert complete["profit_factor"] > 1.2
    assert complete["economic_gate"]["status"] == "GO"
    assert complete["results_by_horizon"]["1"]["completed_trades"] == 30


def test_sensitive_fields_are_not_copied(tmp_path: Path) -> None:
    secret = "super-secret-api-value"
    run = _runtime(tmp_path / "runs", secret=secret)
    manifest = create_prediction_manifest(
        run,
        tmp_path / "ledger",
        _config(tmp_path),
        baseline_commit=BASELINE,
        created_at_utc="2026-01-01T12:01:00Z",
    )
    raw = manifest.read_text(encoding="utf-8").lower()
    assert secret not in raw
    assert "api_key" not in raw
    assert "credentials" not in raw


def test_artifact_paths_are_relative_and_windows_compatible(tmp_path: Path) -> None:
    manifest, _ = _manifest(tmp_path / "folder with spaces")
    paths = [item["path"] for item in json.loads(manifest.read_text())["artifacts"]]
    assert paths == ["stage_outputs.json", "outcome.json", "summary.json"]
    assert all("\\" not in value and not Path(value).is_absolute() for value in paths)


def test_automation_provenance_is_frozen_into_prediction(tmp_path: Path) -> None:
    config_path = _config(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["automation_context"] = {
        "strategy_baseline_commit": BASELINE,
        "harness_commit": "6ce0d848cd24167317f228ffd8772274e9a58166",
        "github_actions": {
            "run_id": "123",
            "run_attempt": "2",
            "run_created_at_utc": "2026-01-01T11:59:00Z",
            "run_url": "https://github.example/actions/runs/123",
        },
    }
    _write_json(config_path, config)
    manifest_path = create_prediction_manifest(
        _runtime(tmp_path / "runs"),
        tmp_path / "ledger",
        config_path,
        baseline_commit=BASELINE,
        created_at_utc="2026-01-01T12:01:00Z",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["strategy_baseline_commit"] == BASELINE
    assert manifest["harness_commit"] == config["automation_context"]["harness_commit"]
    assert manifest["github_actions"]["run_id"] == "123"

    assert manifest["github_actions"] == config["automation_context"]["github_actions"]
