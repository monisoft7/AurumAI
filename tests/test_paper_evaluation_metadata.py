from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path

import pytest

import paper_trading.ledger as ledger
from paper_trading.automation import format_success_message


BASELINE = "46fd62f1212a225446694fb85655936571625148"
RETRIEVED_AT = "2026-09-09T08:10:25Z"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _source(
    status: str,
    observation_date: str | None,
    *,
    max_age_days: int | None = 7,
) -> dict[str, object]:
    value: dict[str, object] = {
        "status": status,
        "observation_date": observation_date,
        "retrieved_at": RETRIEVED_AT,
    }
    if max_age_days is not None:
        value["max_age_days"] = max_age_days
    return value


def _run_343_outputs(*, include_cpi: bool = False) -> dict[str, object]:
    sources = {
        "DGS10": _source("refreshed", "2026-09-04"),
        "DFII10": _source("refreshed", "2026-09-04"),
        "T5YIE": _source("refreshed", "2026-09-08"),
        "Gold": _source("ok", "2026-09-09"),
        "DXY": _source("refreshed", "2026-09-09"),
    }
    if include_cpi:
        sources["CPI"] = _source(
            "fresh", "2026-07-01", max_age_days=90
        )
    return {
        "confidence_engine": {
            "primary_thesis_id": "th_b4a3e4f3da16.v2",
            "theses_confidence": [
                {
                    "thesis_id": "th_b4a3e4f3da16.v2",
                    "final_confidence": 0.3925,
                    "reliability_category": "low",
                }
            ],
        },
        "decision_engine": {"selected_thesis_id": "th_b4a3e4f3da16.v2"},
        "finalize": {
            "source_freshness": sources,
            "decision": {
                "decision": "NO_TRADE",
                "metadata": {"selected_thesis_direction": "bearish"},
            },
        },
        # Run 34327598113 had no reliability field in this output.
        "trade_recommendation": {"recommendation_action": "NO_TRADE"},
    }


def _runtime(tmp_path: Path, *, include_cpi: bool = False) -> Path:
    run = tmp_path / "runtime_20260909_081020"
    outputs = _run_343_outputs(include_cpi=include_cpi)
    stage_ids = sorted(outputs)
    _write_json(
        run / "stage_outputs.json",
        {
            "schema_version": "1.0",
            "pipeline_id": run.name,
            "stage_count": len(stage_ids),
            "stage_ids": stage_ids,
            "outputs": outputs,
        },
    )
    _write_json(
        run / "summary.json",
        {
            "pipeline_id": run.name,
            "timestamp": "2026-09-09T08:11:17.114001Z",
            "success": True,
            "errors": [],
            "failed_stages": [],
            "stage_output_count": len(stage_ids),
            "decision": "NO_TRADE",
            "decision_confidence": 0.3925,
            "data_path": "data/economic/CPIAUCSL.csv",
            "gold_path": "data/history/gold/gold.csv",
        },
    )
    _write_json(
        run / "outcome.json",
        {
            "schema_version": "1.1",
            "status": "pending",
            "run_id": run.name,
            "decision": "NO_TRADE",
            "evaluation_timestamp": None,
        },
    )
    return run


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "paper-config.json"
    _write_json(
        path,
        {
            "evaluation_id": "paper-2026-09-09-regression",
            "cohort_id": "xauusd-paper-46fd62f-v2",
            "baseline_commit": BASELINE,
            "instrument": "XAU/USD",
            "timezone": "Africa/Tripoli",
            "evaluation_horizons_sessions": [1, 3, 5],
            "entry_rule": {"entry": "next close", "exit": "Nth close"},
            "transaction_costs": {},
            "minimum_completed_trades": 30,
            "minimum_calendar_days": 60,
            "go_thresholds": {},
        },
    )
    return path


def _create(tmp_path: Path, *, include_cpi: bool = False) -> dict[str, object]:
    path = ledger.create_prediction_manifest(
        _runtime(tmp_path, include_cpi=include_cpi),
        tmp_path / "ledger",
        _config(tmp_path),
        baseline_commit=BASELINE,
        created_at_utc="2026-09-09T08:11:18Z",
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_run_343_contract_maps_reliability_and_fails_closed_for_cpi(
    tmp_path: Path,
) -> None:
    prediction = _create(tmp_path)
    evaluation = prediction["paper_evaluation"]
    assert evaluation["reliability_category"] == "low"
    assert evaluation["source_freshness"]["DGS10"]["status"] == "fresh"
    assert evaluation["source_freshness"]["Gold"]["status"] == "fresh"
    assert evaluation["source_freshness"]["CPI"] == {
        "status": "unknown",
        "observation_date": None,
        "retrieved_at": None,
        "age_days": None,
        "max_age_days": None,
        "availability": "unknown",
        "reason": "structured freshness metadata missing",
    }
    assert evaluation["financially_eligible"] is False
    assert "CPI:unknown:structured freshness metadata missing" in evaluation[
        "integrity_exclusions"
    ]


@pytest.mark.parametrize("status", ["refreshed", "ok", "fresh", "current"])
def test_positive_status_requires_dates_and_explicit_threshold(status: str) -> None:
    outputs = _run_343_outputs(include_cpi=True)
    outputs["finalize"]["source_freshness"]["Gold"] = {"status": status}
    evaluation = ledger.build_paper_evaluation(outputs, {}, {})
    assert evaluation["source_freshness"]["Gold"]["status"] == "unknown"
    assert evaluation["financially_eligible"] is False


def test_explicit_age_over_threshold_is_stale() -> None:
    outputs = _run_343_outputs(include_cpi=True)
    outputs["finalize"]["source_freshness"]["DGS10"] = _source(
        "refreshed", "2026-08-01"
    )
    evaluation = ledger.build_paper_evaluation(outputs, {}, {})
    assert evaluation["source_freshness"]["DGS10"]["status"] == "stale"
    assert evaluation["financially_eligible"] is False


def test_cpi_observation_date_without_retrieval_contract_stays_unknown() -> None:
    outputs = _run_343_outputs(include_cpi=True)
    outputs["finalize"]["source_freshness"]["CPI"] = {
        "status": "refreshed",
        "observation_date": "2026-07-01",
    }
    evaluation = ledger.build_paper_evaluation(outputs, {}, {})
    assert evaluation["source_freshness"]["CPI"]["status"] == "unknown"
    assert evaluation["financially_eligible"] is False


def test_all_required_sources_fresh_are_eligible(tmp_path: Path) -> None:
    prediction = _create(tmp_path, include_cpi=True)
    evaluation = prediction["paper_evaluation"]
    assert all(
        item["status"] == "fresh"
        for item in evaluation["source_freshness"].values()
    )
    assert evaluation["financially_eligible"] is True
    assert evaluation["integrity_exclusions"] == []


def test_pending_outcome_price_is_not_a_prediction_input(tmp_path: Path) -> None:
    outputs = _run_343_outputs(include_cpi=True)
    outputs["finalize"]["source_freshness"]["outcome_price"] = {
        "status": "unknown",
        "observation_date": None,
        "retrieved_at": None,
        "max_age_days": 7,
        "reason": "future horizon price is pending",
    }
    evaluation = ledger.build_paper_evaluation(outputs, {}, {"status": "pending"})
    assert set(evaluation["source_freshness"]) == {
        "DGS10", "DFII10", "T5YIE", "CPI", "Gold", "DXY"
    }
    assert evaluation["financially_eligible"] is True
    assert evaluation["integrity_exclusions"] == []


def test_telegram_reports_reliability_eligibility_and_exclusions() -> None:
    message = format_success_message(
        {
            "mode": "live-paper",
            "reliability": "low",
            "eligibility": "INELIGIBLE",
            "integrity_exclusions": [
                "CPI:unknown:structured freshness metadata missing"
            ],
        }
    )
    assert "Reliability: low" in message
    assert "الحالة: INELIGIBLE" in message
    assert "أسباب الاستبعاد:" in message
    assert "CPI:unknown" in message


def test_creating_new_prediction_does_not_modify_old_record(tmp_path: Path) -> None:
    old = tmp_path / "ledger" / "predictions" / "old.json"
    _write_json(old, {"immutable": True})
    before = old.read_bytes()
    _create(tmp_path, include_cpi=True)
    assert old.read_bytes() == before


def test_metadata_builder_has_no_network_git_runtime_or_file_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("metadata extraction must remain pure")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(Path, "write_text", forbidden)
    evaluation = ledger.build_paper_evaluation(
        _run_343_outputs(include_cpi=True), {}, {}
    )
    assert evaluation["reliability_category"] == "low"
    assert evaluation["financially_eligible"] is True
