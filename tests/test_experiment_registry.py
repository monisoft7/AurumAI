"""Tests for the Institutional Experiment Registry."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from simulation.experiment import (
    ExperimentConfig,
    ExperimentResult,
    RunConfig,
)
from simulation.experiment_registry import (
    ApprovalStatus,
    ExperimentRecord,
    ExperimentRegistry,
    _compute_experiment_id,
)
from simulation.historical_replay import ChronologicalOOSResult


# ===========================================================================
# Helpers
# ===========================================================================

_GIT_COMMIT = "960cb2bb6ad150211816a6283eb78b1f1685892a"


def _fake_result(
    name: str = "test_exp",
    cutoff: str = "2020-06-01",
    baseline_horizon: int = 12,
    candidate_horizon: int = 12,
) -> ExperimentResult:
    cfg = ExperimentConfig(
        experiment_name=name,
        cutoff_date=cutoff,
        baseline=RunConfig(name="baseline", horizon=baseline_horizon),
        candidate=RunConfig(name="candidate", horizon=candidate_horizon),
    )
    return ExperimentResult(
        config=cfg,
        baseline_result=ChronologicalOOSResult(cutoff_date=cutoff),
        candidate_result=ChronologicalOOSResult(cutoff_date=cutoff),
        comparison=None,
    )


# ===========================================================================
# ApprovalStatus
# ===========================================================================


class TestApprovalStatus:
    def test_values(self) -> None:
        assert ApprovalStatus.PENDING.value == "PENDING"
        assert ApprovalStatus.APPROVED.value == "APPROVED"
        assert ApprovalStatus.REJECTED.value == "REJECTED"
        assert ApprovalStatus.SUPERSEDED.value == "SUPERSEDED"

    def test_str(self) -> None:
        assert str(ApprovalStatus.PENDING) == "PENDING"


# ===========================================================================
# ExperimentRecord
# ===========================================================================


class TestExperimentRecord:
    def test_to_dict(self) -> None:
        r = ExperimentRecord(
            experiment_id="exp_abc123",
            experiment_name="test",
            timestamp="2026-07-21T12:00:00+00:00",
            git_commit=_GIT_COMMIT,
            framework_version="0.1.0",
            baseline_config={"name": "baseline", "horizon": 12},
            candidate_config={"name": "candidate", "horizon": 26},
            cutoff_date="2020-06-01",
            evaluation_horizon=26,
            tags=("cpi", "us10y"),
        )
        d = r.to_dict()
        assert d["experiment_id"] == "exp_abc123"
        assert d["approval_status"] == "PENDING"
        assert d["tags"] == ["cpi", "us10y"]
        assert json.dumps(d)

    def test_default_status(self) -> None:
        r = ExperimentRecord(
            experiment_id="exp_def456",
            experiment_name="test",
            timestamp="2026-07-21T12:00:00+00:00",
            git_commit=_GIT_COMMIT,
            framework_version="0.1.0",
            baseline_config={},
            candidate_config={},
            cutoff_date="2020-06-01",
            evaluation_horizon=12,
        )
        assert r.approval_status == "PENDING"


# ===========================================================================
# Deterministic ID
# ===========================================================================


class TestExperimentId:
    def test_deterministic(self) -> None:
        cfg = ExperimentConfig(
            experiment_name="test",
            cutoff_date="2023-01-01",
        )
        id1 = _compute_experiment_id(cfg, _GIT_COMMIT)
        id2 = _compute_experiment_id(cfg, _GIT_COMMIT)
        assert id1 == id2
        assert id1.startswith("exp_")
        assert len(id1) == 16 + 4  # "exp_" + 16 hex chars

    def test_different_config_produces_different_id(self) -> None:
        cfg_a = ExperimentConfig(experiment_name="exp_a", cutoff_date="2023-01-01")
        cfg_b = ExperimentConfig(experiment_name="exp_b", cutoff_date="2023-06-01")
        id_a = _compute_experiment_id(cfg_a, _GIT_COMMIT)
        id_b = _compute_experiment_id(cfg_b, _GIT_COMMIT)
        assert id_a != id_b

    def test_different_commit_produces_different_id(self) -> None:
        cfg = ExperimentConfig(experiment_name="test", cutoff_date="2023-01-01")
        id1 = _compute_experiment_id(cfg, "aaa")
        id2 = _compute_experiment_id(cfg, "bbb")
        assert id1 != id2


# ===========================================================================
# Registry — Persistence
# ===========================================================================


class TestRegistryPersistence:
    def test_save_and_reload(self, tmp_path: Path) -> None:
        path = tmp_path / "registry.json"
        result = _fake_result("persist_test", "2020-06-01")

        # Round 1: register
        reg = ExperimentRegistry(registry_path=path)
        record = reg.register(result, git_commit=_GIT_COMMIT)
        assert record.experiment_id in [
            r.experiment_id for r in reg.list()
        ]

        # Round 2: fresh registry reads same data
        reg2 = ExperimentRegistry(registry_path=path)
        reloaded = reg2.get(record.experiment_id)
        assert reloaded is not None
        assert reloaded.experiment_name == "persist_test"
        assert reloaded.cutoff_date == "2020-06-01"

    def test_empty_registry(self, tmp_path: Path) -> None:
        path = tmp_path / "empty_registry.json"
        reg = ExperimentRegistry(registry_path=path)
        assert reg.list() == []
        assert reg.latest() is None
        assert reg.latest_approved() is None

    def test_corrupt_file(self, tmp_path: Path) -> None:
        path = tmp_path / "corrupt.json"
        path.write_text("not valid json", encoding="utf-8")
        reg = ExperimentRegistry(registry_path=path)
        assert reg.list() == []


# ===========================================================================
# Registry — Registration
# ===========================================================================


class TestRegistryRegistration:
    def test_register_returns_record(self, tmp_path: Path) -> None:
        path = tmp_path / "reg.json"
        reg = ExperimentRegistry(registry_path=path)
        result = _fake_result("registration_test", "2023-01-01")
        record = reg.register(
            result,
            git_commit=_GIT_COMMIT,
            recommendation="Proceed with candidate",
            notes="First run",
            tags=("cpi",),
        )
        assert record.experiment_name == "registration_test"
        assert record.recommendation == "Proceed with candidate"
        assert record.notes == "First run"
        assert record.tags == ("cpi",)
        assert record.approval_status == "PENDING"
        assert record.git_commit == _GIT_COMMIT

    def test_register_idempotent(self, tmp_path: Path) -> None:
        path = tmp_path / "idempotent.json"
        reg = ExperimentRegistry(registry_path=path)
        result = _fake_result("idempotent", "2023-01-01")
        r1 = reg.register(result, git_commit=_GIT_COMMIT)
        r2 = reg.register(result, git_commit=_GIT_COMMIT)
        assert r1.experiment_id == r2.experiment_id
        assert len(reg.list()) == 1  # not duplicated


# ===========================================================================
# Registry — Retrieval
# ===========================================================================


class TestRegistryRetrieval:
    def test_get_nonexistent(self, tmp_path: Path) -> None:
        reg = ExperimentRegistry(registry_path=tmp_path / "r.json")
        assert reg.get("nonexistent") is None

    def test_latest(self, tmp_path: Path) -> None:
        reg = ExperimentRegistry(registry_path=tmp_path / "r.json")
        r1 = reg.register(
            _fake_result("exp_a", "2022-01-01"),
            git_commit=_GIT_COMMIT,
        )
        r2 = reg.register(
            _fake_result("exp_b", "2023-01-01"),
            git_commit=_GIT_COMMIT,
        )
        latest = reg.latest()
        assert latest is not None
        assert latest.experiment_name == "exp_b"

    def test_latest_approved(self, tmp_path: Path) -> None:
        reg = ExperimentRegistry(registry_path=tmp_path / "r.json")
        reg.register(_fake_result("exp_a"), git_commit=_GIT_COMMIT)
        r2 = reg.register(_fake_result("exp_b"), git_commit=_GIT_COMMIT)
        reg.approve(r2.experiment_id, "Looks good")
        approved = reg.latest_approved()
        assert approved is not None
        assert approved.experiment_name == "exp_b"


# ===========================================================================
# Registry — Approval Workflow
# ===========================================================================


class TestRegistryApproval:
    def test_approve_updates_status(self, tmp_path: Path) -> None:
        reg = ExperimentRegistry(registry_path=tmp_path / "r.json")
        r = reg.register(_fake_result(), git_commit=_GIT_COMMIT)
        assert r.approval_status == "PENDING"
        updated = reg.approve(r.experiment_id, "Test passed")
        assert updated is not None
        assert updated.approval_status == "APPROVED"
        assert "APPROVED" in updated.notes
        assert "Test passed" in updated.notes

    def test_reject_updates_status(self, tmp_path: Path) -> None:
        reg = ExperimentRegistry(registry_path=tmp_path / "r.json")
        r = reg.register(_fake_result(), git_commit=_GIT_COMMIT)
        updated = reg.reject(r.experiment_id, "Failed validation")
        assert updated is not None
        assert updated.approval_status == "REJECTED"

    def test_supersede_updates_status(self, tmp_path: Path) -> None:
        reg = ExperimentRegistry(registry_path=tmp_path / "r.json")
        r = reg.register(_fake_result(), git_commit=_GIT_COMMIT)
        updated = reg.supersede(r.experiment_id, "Replaced by exp_v2")
        assert updated is not None
        assert updated.approval_status == "SUPERSEDED"

    def test_update_nonexistent(self, tmp_path: Path) -> None:
        reg = ExperimentRegistry(registry_path=tmp_path / "r.json")
        assert reg.approve("nope") is None
        assert reg.reject("nope") is None
        assert reg.supersede("nope") is None


# ===========================================================================
# Registry — Search
# ===========================================================================


class TestRegistrySearch:
    def test_find_by_name(self, tmp_path: Path) -> None:
        reg = ExperimentRegistry(registry_path=tmp_path / "r.json")
        reg.register(_fake_result("cpi_test", "2023-01-01"), git_commit=_GIT_COMMIT)
        reg.register(_fake_result("us10y_test", "2023-06-01"), git_commit=_GIT_COMMIT)
        found = reg.find_by_name("cpi_test")
        assert len(found) == 1
        assert found[0].experiment_name == "cpi_test"

    def test_find_by_tag(self, tmp_path: Path) -> None:
        reg = ExperimentRegistry(registry_path=tmp_path / "r.json")
        reg.register(
            _fake_result("exp_a"), git_commit=_GIT_COMMIT, tags=("cpi", "gold")
        )
        reg.register(
            _fake_result("exp_b"), git_commit=_GIT_COMMIT, tags=("us10y",)
        )
        found = reg.find_by_tag("cpi")
        assert len(found) == 1
        found = reg.find_by_tag("gold")
        assert len(found) == 1
        found = reg.find_by_tag("nonexistent")
        assert len(found) == 0

    def test_find_by_commit(self, tmp_path: Path) -> None:
        reg = ExperimentRegistry(registry_path=tmp_path / "r.json")
        reg.register(_fake_result("a"), git_commit="abc123")
        reg.register(_fake_result("b"), git_commit="def456")
        assert len(reg.find_by_commit("abc123")) == 1
        assert len(reg.find_by_commit("def456")) == 1
        assert len(reg.find_by_commit("xyz")) == 0


# ===========================================================================
# Registry — Comparison
# ===========================================================================


class TestRegistryCompare:
    def test_compare_two(self, tmp_path: Path) -> None:
        reg = ExperimentRegistry(registry_path=tmp_path / "r.json")
        r1 = reg.register(
            _fake_result("exp_a", "2022-01-01"),
            git_commit=_GIT_COMMIT,
        )
        r2 = reg.register(
            _fake_result("exp_b", "2023-01-01"),
            git_commit=_GIT_COMMIT,
        )
        comp = reg.compare_two(r1.experiment_id, r2.experiment_id)
        assert comp["id_a"] == r1.experiment_id
        assert comp["id_b"] == r2.experiment_id
        assert comp["cutoff_a"] == "2022-01-01"
        assert comp["cutoff_b"] == "2023-01-01"

    def test_compare_missing(self, tmp_path: Path) -> None:
        reg = ExperimentRegistry(registry_path=tmp_path / "r.json")
        result = reg.compare_two("exists", "missing")
        assert "error" in result


# ===========================================================================
# Registry — Serialization
# ===========================================================================


class TestRegistrySerialization:
    def test_to_dict(self, tmp_path: Path) -> None:
        reg = ExperimentRegistry(registry_path=tmp_path / "r.json")
        reg.register(_fake_result("ser_test"), git_commit=_GIT_COMMIT)
        d = reg.to_dict()
        assert d["experiment_count"] == 1
        assert d["framework_version"] == "0.1.0"
        assert len(d["records"]) == 1

    def test_to_json(self, tmp_path: Path) -> None:
        reg = ExperimentRegistry(registry_path=tmp_path / "r.json")
        reg.register(_fake_result("json_test"), git_commit=_GIT_COMMIT)
        j = reg.to_json()
        parsed = json.loads(j)
        assert parsed["experiment_count"] == 1

    def test_summary_text(self, tmp_path: Path) -> None:
        reg = ExperimentRegistry(registry_path=tmp_path / "r.json")
        reg.register(_fake_result("summary_test"), git_commit=_GIT_COMMIT)
        text = reg.summary_text()
        assert "Experiment Registry Summary" in text
        assert "summary_test" in text
        assert "Total experiments: 1" in text
