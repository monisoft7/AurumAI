"""Regression tests for the W2 regime_diagnosis orchestration stage.

Verifies the W2 stage emits a valid RegimeDiagnosis, populates the indicator
hierarchy and trigger levels, persists the artifact, and degrades gracefully
when no KnowledgeGraph is present (nil-tolerant reused components).
"""

from __future__ import annotations

import json
from pathlib import Path

from knowledge.regime.contracts import RegimeDiagnosis
from knowledge.regime.constants import CANONICAL_REGIME_SET
from orchestration.institutional_orchestrator import _regime_diagnosis


def _run_stage() -> dict:
    return _regime_diagnosis({"output_dir": None}, {"build_legacy_pipeline": {}})


def test_stage_emits_valid_regime_diagnosis() -> None:
    payload = _run_stage()
    assert isinstance(payload, dict)
    diagnosis = RegimeDiagnosis.from_dict(payload)
    errors = diagnosis.validate()
    assert errors == [], f"validate errors: {errors}"
    assert diagnosis.regime in CANONICAL_REGIME_SET
    assert 0.0 <= diagnosis.confidence <= 1.0
    assert abs(sum(diagnosis.probabilities.values()) - 1.0) <= 0.01


def test_stage_populates_hierarchy_and_trigger_levels() -> None:
    payload = _run_stage()
    diagnosis = RegimeDiagnosis.from_dict(payload)
    assert len(diagnosis.indicator_hierarchy) > 0
    assert len(diagnosis.trigger_levels) > 0
    tiers = {i.tier for i in diagnosis.indicator_hierarchy}
    assert tiers == {"dominant", "secondary", "weaker"}


def test_stage_writes_regime_artifact(tmp_path: Path) -> None:
    output_dir = tmp_path / "artifacts"
    output_dir.mkdir()
    payload = _regime_diagnosis(
        {"output_dir": str(output_dir)},
        {"build_legacy_pipeline": {}},
    )
    artifact = output_dir / "regime_diagnosis.json"
    assert artifact.exists()
    restored = json.loads(artifact.read_text(encoding="utf-8"))
    assert restored == payload
    diagnosis = RegimeDiagnosis.from_dict(restored)
    assert diagnosis.validate() == []


def test_stage_fallback_without_graph() -> None:
    payload = _regime_diagnosis({}, {})
    assert isinstance(payload, dict)
    assert payload["regime"] in CANONICAL_REGIME_SET