"""Contract tests using run.py's actual serializer and StageRecord schema."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from orchestration.models import StageRecord
from paper_trading.automation import AutomationFailure, _validate_runtime, scan_runtime_secrets
from test_paper_trading import _runtime, _write_json
from test_runtime_output_isolation import RUN


@pytest.fixture
def runtime_artifacts(tmp_path):
    strategy = tmp_path / "strategy"
    run = _runtime(strategy / "outputs")
    stage_outputs = json.loads((run / "stage_outputs.json").read_text())
    outputs = stage_outputs["outputs"]
    outputs["finalize"]["source_freshness"]["dxy"] = "fresh"
    outputs.update({f"fixture_{i}": {} for i in range(25)})
    records = [StageRecord(stage_id, "ok", 1.5) for stage_id in outputs]
    assessment = SimpleNamespace(pipeline_id="runtime_1", stages=records, outputs=outputs)
    # These are the exact transformations used by run.py's output writer.
    RUN._write_json(run / "stages.json", [r.to_dict() for r in assessment.stages])
    RUN._write_json(run / "stage_outputs.json", RUN._stage_outputs_payload(assessment))
    RUN._write_json(run / "finalize.json", outputs["finalize"])
    summary = json.loads((run / "summary.json").read_text())
    summary["stage_output_count"] = 27
    _write_json(run / "summary.json", summary)
    _write_json(strategy / "runtime/run_registry.jsonl", {
        "run_id": "runtime_1", "output_directory": str(run),
        "report_path": str(run / "institutional_report.md"),
    })
    return run, strategy


def test_run_writer_stages_list_passes_real_paper_validator(runtime_artifacts):
    run, strategy = runtime_artifacts
    stages = json.loads((run / "stages.json").read_text())
    assert isinstance(stages, list) and len(stages) == 27
    assert all(set(stage) == {"stage_id", "status", "duration_ms"} for stage in stages)
    validated = _validate_runtime(run, strategy, secret_values=())
    assert validated["runtime_id"] == "runtime_1"
    assert validated["freshness_eligible"] is True


@pytest.mark.parametrize("payload", [None, {}, {"stages": []}, "stages", 27, True, []])
def test_invalid_root_or_empty_payload_is_rejected(runtime_artifacts, payload):
    run, strategy = runtime_artifacts
    _write_json(run / "stages.json", payload)
    with pytest.raises(AutomationFailure, match="must contain 27 stage records"):
        _validate_runtime(run, strategy, secret_values=())


@pytest.mark.parametrize("record", [None, [], "invalid", 27, True])
def test_non_object_record_is_rejected(runtime_artifacts, record):
    run, strategy = runtime_artifacts
    stages = json.loads((run / "stages.json").read_text())
    stages[0] = record
    _write_json(run / "stages.json", stages)
    with pytest.raises(AutomationFailure, match="must be an object"):
        _validate_runtime(run, strategy, secret_values=())


@pytest.mark.parametrize("field,value", [
    ("stage_id", None), ("stage_id", ""), ("stage_id", 12),
    ("stage_id", " stage"), ("stage_id", "bad\x00id"), ("stage_id", []),
    ("status", None), ("status", ""), ("status", "failed"),
    ("status", "cached"), ("status", "skipped"), ("status", "unknown"),
    ("status", True), ("status", {}), ("error", "synthetic stage failure"),
])
def test_invalid_id_or_non_ok_status_is_rejected(runtime_artifacts, field, value):
    run, strategy = runtime_artifacts
    stages = json.loads((run / "stages.json").read_text())
    stages[0][field] = value
    _write_json(run / "stages.json", stages)
    with pytest.raises(AutomationFailure):
        _validate_runtime(run, strategy, secret_values=())


@pytest.mark.parametrize("field", ["stage_id", "status"])
def test_missing_id_or_status_is_rejected(runtime_artifacts, field):
    run, strategy = runtime_artifacts
    stages = json.loads((run / "stages.json").read_text())
    del stages[0][field]
    _write_json(run / "stages.json", stages)
    with pytest.raises(AutomationFailure):
        _validate_runtime(run, strategy, secret_values=())


def test_duplicate_id_is_rejected(runtime_artifacts):
    run, strategy = runtime_artifacts
    stages = json.loads((run / "stages.json").read_text())
    stages[1]["stage_id"] = stages[0]["stage_id"]
    _write_json(run / "stages.json", stages)
    with pytest.raises(AutomationFailure, match="duplicate stage ID"):
        _validate_runtime(run, strategy, secret_values=())


@pytest.mark.parametrize("count", [26, 28])
def test_incorrect_stage_count_is_rejected(runtime_artifacts, count):
    run, strategy = runtime_artifacts
    stages = json.loads((run / "stages.json").read_text())
    if count == 26:
        stages.pop()
    else:
        stages.append(StageRecord("extra", "ok", 1.5).to_dict())
    _write_json(run / "stages.json", stages)
    with pytest.raises(AutomationFailure, match="must contain 27 stage records"):
        _validate_runtime(run, strategy, secret_values=())


@pytest.mark.parametrize("mutation", [
    "count", "float_count", "ids_missing", "ids_wrong_type", "ids_duplicate",
    "ids_mismatch", "ids_non_string", "outputs_missing", "outputs_wrong_type",
    "outputs_count", "outputs_mismatch", "records_mismatch",
])
def test_stage_outputs_mismatch_is_rejected(runtime_artifacts, mutation):
    run, strategy = runtime_artifacts
    path = run / "stage_outputs.json"
    payload = json.loads(path.read_text())
    if mutation == "count":
        payload["stage_count"] = 26
    elif mutation == "float_count":
        payload["stage_count"] = 27.0
    elif mutation == "ids_missing":
        del payload["stage_ids"]
    elif mutation == "ids_wrong_type":
        payload["stage_ids"] = {}
    elif mutation == "ids_duplicate":
        payload["stage_ids"][1] = payload["stage_ids"][0]
    elif mutation == "ids_mismatch":
        payload["stage_ids"][0] = "unexpected"
    elif mutation == "ids_non_string":
        payload["stage_ids"][0] = {}
    elif mutation == "outputs_missing":
        del payload["outputs"]
    elif mutation == "outputs_wrong_type":
        payload["outputs"] = []
    elif mutation == "outputs_count":
        payload["outputs"].pop("finalize")
    elif mutation == "outputs_mismatch":
        payload["outputs"]["unexpected"] = payload["outputs"].pop("finalize")
    else:
        stages = json.loads((run / "stages.json").read_text())
        stages[0]["stage_id"] = "unexpected"
        _write_json(run / "stages.json", stages)
    _write_json(path, payload)
    with pytest.raises(AutomationFailure, match="stages.json and stage_outputs disagree"):
        _validate_runtime(run, strategy, secret_values=())


def test_stage_execution_order_need_not_match_sorted_outputs(runtime_artifacts):
    run, strategy = runtime_artifacts
    stages = json.loads((run / "stages.json").read_text())
    _write_json(run / "stages.json", list(reversed(stages)))
    assert _validate_runtime(run, strategy, secret_values=())["runtime_id"] == "runtime_1"


@pytest.mark.parametrize("kind", ["structural", "known_value"])
def test_secret_scan_still_inspects_nested_stage_records(runtime_artifacts, kind):
    run, strategy = runtime_artifacts
    canary = "synthetic-sensitive-canary"
    stages = json.loads((run / "stages.json").read_text())
    stages[0]["checkpoint"] = {"passed": True, "notes": "note", "severity": "low"}
    if kind == "structural":
        stages[0]["checkpoint"]["api_key"] = canary
        values = ()
    else:
        stages[0]["checkpoint"]["notes"] = canary
        values = (canary,)
    _write_json(run / "stages.json", stages)
    with pytest.raises(AutomationFailure) as caught:
        _validate_runtime(run, strategy, secret_values=values)
    assert caught.value.stage == "secret-scan"
    assert canary not in str(caught.value)
    assert str(run) not in str(caught.value)


def test_malformed_json_failure_is_sanitized(runtime_artifacts):
    run, strategy = runtime_artifacts
    (run / "stages.json").write_text('{"sensitive-canary":')
    with pytest.raises(AutomationFailure) as caught:
        _validate_runtime(run, strategy, secret_values=())
    assert str(caught.value) == "invalid stages.json"
    assert "sensitive-canary" not in str(caught.value)
    assert str(run) not in str(caught.value)


def test_other_runtime_artifacts_still_require_object_root(tmp_path):
    path = tmp_path / "summary.json"
    _write_json(path, [StageRecord("stage", "ok", 1.5).to_dict()])
    with pytest.raises(AutomationFailure, match="invalid summary.json"):
        scan_runtime_secrets([path], ())
