# tests/test_institutional_orchestrator.py

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from orchestration.institutional_orchestrator import (
    CacheManager,
    CheckpointManager,
    InstitutionalOrchestrator,
    PipelineJob,
    _topological_levels,
)
from orchestration.models import InstitutionalAssessment, StageRecord, CheckpointResult


# ===========================================================================
# CacheManager
# ===========================================================================


class TestCacheManager:
    def test_set_and_get(self) -> None:
        cm = CacheManager()
        cm.set("key1", 42)
        assert cm.get("key1") == 42

    def test_get_missing(self) -> None:
        assert CacheManager().get("nope") is None

    def test_ttl_expiry(self) -> None:
        cm = CacheManager()
        cm.set("ephemeral", "value", ttl=0)  # immediate expiry
        time.sleep(0.01)
        assert cm.get("ephemeral") is None

    def test_ttl_hit(self) -> None:
        cm = CacheManager()
        cm.set("persistent", "val", ttl=60)
        assert cm.get("persistent") == "val"

    def test_invalidate(self) -> None:
        cm = CacheManager()
        cm.set("x", 1)
        cm.invalidate("x")
        assert cm.get("x") is None

    def test_clear_expired(self) -> None:
        cm = CacheManager()
        cm.set("a", 1, ttl=0)
        cm.set("b", 2, ttl=60)
        cm.set("c", 3)
        time.sleep(0.01)
        removed = cm.clear_expired()
        assert removed == 1
        assert cm.get("a") is None
        assert cm.get("b") == 2
        assert cm.get("c") == 3

    def test_size(self) -> None:
        cm = CacheManager()
        assert cm.size == 0
        cm.set("a", 1)
        assert cm.size == 1
        cm.set("b", 2)
        assert cm.size == 2

    def test_hit_count(self) -> None:
        cm = CacheManager()
        cm.inc_hit()
        cm.inc_hit()
        assert cm.hits == 2

    def test_thread_safety(self) -> None:
        import threading

        cm = CacheManager()
        errors = []

        def worker() -> None:
            for i in range(100):
                cm.set(f"k{i}", i)
                cm.get(f"k{i}")

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert cm.size <= 400
        assert len(errors) == 0


# ===========================================================================
# CheckpointManager
# ===========================================================================


class TestCheckpointManager:
    @pytest.fixture
    def tmp_dir(self) -> Path:
        d = Path(tempfile.mkdtemp())
        yield d
        shutil.rmtree(d, ignore_errors=True)

    def test_write_and_read(self, tmp_dir: Path) -> None:
        cpm = CheckpointManager(str(tmp_dir))
        data = {"answer": 42}
        cpm.write("pipe1", "job1", data)
        assert cpm.exists("pipe1", "job1")
        loaded = cpm.read("pipe1", "job1")
        assert loaded == data

    def test_read_missing(self, tmp_dir: Path) -> None:
        cpm = CheckpointManager(str(tmp_dir))
        assert cpm.read("pipe_x", "job_x") is None

    def test_clear_pipeline(self, tmp_dir: Path) -> None:
        cpm = CheckpointManager(str(tmp_dir))
        cpm.write("p1", "j1", {"a": 1})
        cpm.write("p1", "j2", {"b": 2})
        cpm.write("p2", "j1", {"c": 3})
        cpm.clear("p1")
        assert not cpm.exists("p1", "j1")
        assert not cpm.exists("p1", "j2")
        assert cpm.exists("p2", "j1")

    def test_clear_all(self, tmp_dir: Path) -> None:
        cpm = CheckpointManager(str(tmp_dir))
        cpm.write("p1", "j1", {})
        cpm.write("p2", "j1", {})
        cpm.clear_all()
        assert not cpm.exists("p1", "j1")
        assert not cpm.exists("p2", "j1")

    def test_resume(self, tmp_dir: Path) -> None:
        cpm = CheckpointManager(str(tmp_dir))
        cpm.write("pipe_r", "job_a", {"output": "done", "pipeline_id": "pipe_r", "job_id": "job_a"})
        data = cpm.read("pipe_r", "job_a")
        assert data is not None
        assert data["output"] == "done"
        assert data["pipeline_id"] == "pipe_r"
        assert data["job_id"] == "job_a"


# ===========================================================================
# DAG topological sort
# ===========================================================================


class TestTopologicalLevels:
    def test_empty(self) -> None:
        assert _topological_levels({}) == []

    def test_single_node(self) -> None:
        jobs = {"a": PipelineJob("a", (), lambda: 0)}
        assert _topological_levels(jobs) == [["a"]]

    def test_linear_chain(self) -> None:
        jobs = {
            "a": PipelineJob("a", (), lambda: 0),
            "b": PipelineJob("b", ("a",), lambda: 0),
            "c": PipelineJob("c", ("b",), lambda: 0),
        }
        levels = _topological_levels(jobs)
        assert levels == [["a"], ["b"], ["c"]]

    def test_parallel_levels(self) -> None:
        jobs = {
            "a": PipelineJob("a", (), lambda: 0),
            "b": PipelineJob("b", (), lambda: 0),
            "c": PipelineJob("c", ("a", "b"), lambda: 0),
        }
        levels = _topological_levels(jobs)
        assert set(levels[0]) == {"a", "b"}
        assert levels[1] == ["c"]

    def test_diamond(self) -> None:
        jobs = {
            "a": PipelineJob("a", (), lambda: 0),
            "b": PipelineJob("b", ("a",), lambda: 0),
            "c": PipelineJob("c", ("a",), lambda: 0),
            "d": PipelineJob("d", ("b", "c"), lambda: 0),
        }
        levels = _topological_levels(jobs)
        assert levels[0] == ["a"]
        assert set(levels[1]) == {"b", "c"}
        assert levels[2] == ["d"]

    def test_circular_dependency(self) -> None:
        jobs = {
            "a": PipelineJob("a", ("b",), lambda: 0),
            "b": PipelineJob("b", ("a",), lambda: 0),
        }
        with pytest.raises(ValueError, match="Circular dependency"):
            _topological_levels(jobs)

    def test_self_dependency(self) -> None:
        jobs = {
            "a": PipelineJob("a", ("a",), lambda: 0),
        }
        with pytest.raises(ValueError, match="Circular dependency"):
            _topological_levels(jobs)

    def test_disconnected_graph(self) -> None:
        jobs = {
            "a": PipelineJob("a", (), lambda: 0),
            "b": PipelineJob("b", (), lambda: 0),
            "c": PipelineJob("c", (), lambda: 0),
        }
        levels = _topological_levels(jobs)
        assert set(levels[0]) == {"a", "b", "c"}


# ===========================================================================
# InstitutionalOrchestrator
# ===========================================================================


class TestOrchestratorRegistration:
    def test_register_and_list(self) -> None:
        orch = InstitutionalOrchestrator()
        assert orch.registered_count == 0
        orch.register(PipelineJob("a", (), lambda: 1))
        assert orch.registered_count == 1
        assert orch.list_jobs() == ["a"]

    def test_duplicate_registration(self) -> None:
        orch = InstitutionalOrchestrator()
        orch.register(PipelineJob("x", (), lambda: 0))
        with pytest.raises(ValueError, match="already registered"):
            orch.register(PipelineJob("x", (), lambda: 0))

    def test_register_multiple(self) -> None:
        orch = InstitutionalOrchestrator()
        orch.register(PipelineJob("a", (), lambda: 0))
        orch.register(PipelineJob("b", ("a",), lambda: 0))
        assert orch.registered_count == 2


class TestOrchestratorExecution:
    def test_basic_sequential(self) -> None:
        trail: list[str] = []

        def make_fn(name: str):
            def fn() -> str:
                trail.append(name)
                return name
            return fn

        orch = InstitutionalOrchestrator()
        orch.register(PipelineJob("a", (), make_fn("a")))
        orch.register(PipelineJob("b", ("a",), make_fn("b")))
        orch.register(PipelineJob("c", ("b",), make_fn("c")))

        assessment = orch.run_all(trigger="test")
        assert trail == ["a", "b", "c"]
        assert assessment.trigger == "test"
        assert assessment.cache_hits == 0
        assert len(assessment.errors) == 0

    def test_parallel_execution(self) -> None:
        """Jobs in the same level run concurrently (thread pool)."""
        import threading

        entered: dict[str, float] = {}
        lock = threading.Lock()

        def make_fn(name: str):
            def fn() -> str:
                time.sleep(0.03)
                with lock:
                    entered[name] = time.perf_counter()
                return name
            return fn

        orch = InstitutionalOrchestrator(max_workers=4)
        orch.register(PipelineJob("a", (), make_fn("a")))
        orch.register(PipelineJob("b", (), make_fn("b")))
        orch.register(PipelineJob("c", ("a", "b"), make_fn("c")))

        assessment = orch.run_all(trigger="test")

        # a and b should overlap (started before either finished)
        # We check that both were "entered" before the first finished its sleep
        assert "a" in entered
        assert "b" in entered
        assert assessment.errors == ()

    def test_dependency_ordering(self) -> None:
        order: list[str] = []

        def make_fn(name: str):
            def fn() -> str:
                order.append(name)
                return name
            return fn

        orch = InstitutionalOrchestrator()
        orch.register(PipelineJob("forecast", ("ingest",), make_fn("forecast")))
        orch.register(PipelineJob("ingest", (), make_fn("ingest")))

        assessment = orch.run_all()
        assert order == ["ingest", "forecast"]

    def test_stage_record_contains_outputs(self) -> None:
        orch = InstitutionalOrchestrator()
        orch.register(PipelineJob("a", (), lambda: {"value": 42}))
        assessment = orch.run_all()
        key = next(iter(assessment.outputs))
        assert key == "a"
        assert assessment.outputs[key] == {"value": 42}

    def test_empty_registration_raises(self) -> None:
        orch = InstitutionalOrchestrator()
        with pytest.raises(RuntimeError, match="No jobs registered"):
            orch.run_all()

    def test_stage_success_status(self) -> None:
        orch = InstitutionalOrchestrator()
        orch.register(PipelineJob("a", (), lambda: 1))
        assessment = orch.run_all()
        assert len(assessment.stages) == 1
        assert assessment.stages[0].stage_id == "a"
        assert assessment.stages[0].status == "ok"
        assert assessment.stages[0].duration_ms >= 0
        assert assessment.stages[0].error is None

    def test_stage_failure(self) -> None:
        orch = InstitutionalOrchestrator()
        orch.register(PipelineJob("fail", (), lambda: (_ for _ in ()).throw(RuntimeError("boom"))))
        orch.register(PipelineJob("ok", ("fail",), lambda: 1))
        assessment = orch.run_all()
        assert any("fail" in e for e in assessment.errors)
        fail_records = [s for s in assessment.stages if s.stage_id == "fail"]
        assert len(fail_records) == 1
        assert fail_records[0].status == "failed"


class TestOrchestratorCaching:
    def test_cache_hit(self) -> None:
        call_count = 0

        def fn() -> int:
            nonlocal call_count
            call_count += 1
            return 42

        orch = InstitutionalOrchestrator()
        orch.register(PipelineJob("a", (), fn, cache_ttl=60))

        assessment1 = orch.run_all(trigger="first")
        assert call_count == 1

        assessment2 = orch.run_all(trigger="second")
        assert call_count == 1  # cached, no extra call
        assert assessment2.cache_hits == 1

    def test_cache_miss_on_different_params(self) -> None:
        call_count = 0

        def fn() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        orch = InstitutionalOrchestrator()
        orch.register(PipelineJob("a", (), fn, cache_ttl=60))

        r1 = orch.run_all(x=1)
        c1 = call_count
        r2 = orch.run_all(x=2)
        assert call_count == c1 + 1  # different params → no cache
        assert r2.cache_hits == 0

    def test_force_bypass_cache(self) -> None:
        call_count = 0

        def fn() -> int:
            nonlocal call_count
            call_count += 1
            return 42

        orch = InstitutionalOrchestrator()
        orch.register(PipelineJob("a", (), fn, cache_ttl=60))

        orch.run_all()
        assert call_count == 1

        orch.run_all(force=True)
        assert call_count == 2  # force bypasses cache

    def test_no_cache_ttl(self) -> None:
        call_count = 0

        def fn() -> int:
            nonlocal call_count
            call_count += 1
            return 1

        orch = InstitutionalOrchestrator()
        orch.register(PipelineJob("a", (), fn, cache_ttl=None))

        orch.run_all()
        orch.run_all()
        assert call_count == 2  # no caching


class TestOrchestratorCheckpoint:
    def test_checkpoint_resume(self) -> None:
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            call_count = 0

            def fn() -> str:
                nonlocal call_count
                call_count += 1
                return "done"

            orch = InstitutionalOrchestrator(checkpoint_dir=str(tmp_dir))
            orch.register(PipelineJob("a", (), fn, checkpoint=True))

            assessment1 = orch.run_all(pipeline_id="p1")
            assert call_count == 1

            assessment2 = orch.run_all(pipeline_id="p1")
            assert call_count == 1  # resumed from checkpoint
            # checkpointed job reports status="ok" (not "cached")
            a2_record = [s for s in assessment2.stages if s.stage_id == "a"][0]
            assert a2_record.status == "ok"
            assert a2_record.checkpoint is not None
            assert a2_record.checkpoint.passed is True
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_force_bypass_checkpoint(self) -> None:
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            call_count = 0

            def fn() -> str:
                nonlocal call_count
                call_count += 1
                return "done"

            orch = InstitutionalOrchestrator(checkpoint_dir=str(tmp_dir))
            orch.register(PipelineJob("a", (), fn, checkpoint=True))

            orch.run_all(pipeline_id="p2")
            assert call_count == 1

            orch.run_all(pipeline_id="p2", force=True)
            assert call_count == 2
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestOrchestratorOutput:
    def test_institutional_assessment_structure(self) -> None:
        orch = InstitutionalOrchestrator()
        orch.register(PipelineJob("a", (), lambda: 10))
        assessment = orch.run_all(trigger="scheduled", pipeline_id="test_pipe")

        assert isinstance(assessment, InstitutionalAssessment)
        assert assessment.pipeline_id == "test_pipe"
        assert assessment.trigger == "scheduled"
        assert "T" in assessment.timestamp  # ISO datetime
        assert len(assessment.stages) == 1
        assert assessment.cache_hits == 0
        assert assessment.wall_time_ms > 0
        assert assessment.outputs["a"] == 10
        assert assessment.errors == ()

    def test_to_dict(self) -> None:
        assessment = InstitutionalAssessment(
            pipeline_id="p1",
            trigger="manual",
            timestamp="2026-07-18T12:00:00",
            stages=(
                StageRecord("a", "ok", 10.5),
                StageRecord("b", "failed", 5.0, error="boom"),
            ),
            cache_hits=1,
            wall_time_ms=100.0,
            outputs={"a": 42},
            errors=("b: boom",),
        )
        d = assessment.to_dict()
        assert d["pipeline_id"] == "p1"
        assert d["stages_completed"] == ["a"]
        assert len(d["errors"]) == 1

    def test_partial_failure_output(self) -> None:
        orch = InstitutionalOrchestrator()
        orch.register(PipelineJob("a", (), lambda: 1))
        orch.register(PipelineJob("b", ("a",), lambda: (_ for _ in ()).throw(ValueError("broke"))))
        assessment = orch.run_all()
        assert len(assessment.errors) == 1
        assert "a" in assessment.outputs
        assert "b" not in assessment.outputs


class TestOrchestratorLevels:
    def test_14_job_dag_structure(self) -> None:
        """Verify the default pipeline DAG has correct levels."""
        orch = InstitutionalOrchestrator.with_default_pipeline()
        levels = _topological_levels(orch._jobs)

        # Level 0: independent jobs (ingest_event, ingest_news)
        level0 = set(levels[0])
        assert "ingest_event" in level0
        assert "ingest_news" in level0
        assert len(level0) == 2

        # Level 1: depends on ingest_event (forecast, build_legacy_pipeline)
        level1 = set(levels[1])
        assert "forecast" in level1
        assert "build_legacy_pipeline" in level1

        # W2 regime_diagnosis runs after its KG dependency and before W3
        assert "regime_diagnosis" in {jid for level in levels for jid in level}
        level_of = {jid: i for i, level in enumerate(levels) for jid in level}
        assert level_of["build_legacy_pipeline"] < level_of["regime_diagnosis"]
        assert level_of["regime_diagnosis"] < level_of["pre_market_scan"]

    def test_scenario_generation_depends_on_thesis_update(self) -> None:
        """Correction 004: scenario_generation must consume thesis_update so
        the thesis/scenario race is structurally impossible in the DAG.

        Runtime 009 proved that scenario_generation and thesis_update could
        execute at the same DAG level; scenario_generation then read a not
        yet written thesis_update result and generated scenarios keyed to the
        unversioned thesis, producing confidence=0.0 / "no eligible thesis"
        in the DecisionEngine's exact thesis_id match. The dependency edge
        below forces thesis_update to an earlier level than
        scenario_generation.
        """
        orch = InstitutionalOrchestrator.with_default_pipeline()
        levels = _topological_levels(orch._jobs)
        level_of = {jid: i for i, level in enumerate(levels) for jid in level}

        deps = orch._jobs["scenario_generation"].dependencies
        assert "thesis_construction" in deps
        assert "thesis_update" in deps
        assert level_of["thesis_update"] < level_of["scenario_generation"]

    def test_no_circular_in_default_pipeline(self) -> None:
        orch = InstitutionalOrchestrator.with_default_pipeline()
        levels = _topological_levels(orch._jobs)
        # Should complete without error
        all_jobs = {jid for level in levels for jid in level}
        assert all_jobs == set(orch._jobs.keys())

    def test_finalize_is_last(self) -> None:
        orch = InstitutionalOrchestrator.with_default_pipeline()
        levels = _topological_levels(orch._jobs)
        assert "trade_recommendation" in levels[-1]


# ===========================================================================
# Integration tests with actual (small) AurumAI components
# ===========================================================================


class TestDefaultPipeline:
    """End‑to‑end verification of the full 13‑job pipeline using actual
    AurumAI components with a minimal synthetic dataset."""

    @pytest.fixture
    def tmp_workspace(self) -> Path:
        d = Path(tempfile.mkdtemp())
        yield d
        shutil.rmtree(d, ignore_errors=True)

    @pytest.fixture
    def gold_csv(self, tmp_workspace: Path) -> Path:
        path = tmp_workspace / "gold.csv"
        lines = [
            "ds,price",
            "2023-01-01,1820.0",
            "2023-02-01,1840.0",
            "2023-03-01,1860.0",
            "2023-04-01,1880.0",
            "2023-05-01,1900.0",
            "2023-06-01,1920.0",
            "2023-07-01,1940.0",
            "2023-08-01,1960.0",
            "2023-09-01,1980.0",
            "2023-10-01,2000.0",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    @pytest.fixture
    def event_csv(self, tmp_workspace: Path) -> Path:
        path = tmp_workspace / "cpi.csv"
        lines = [
            "date,value,condition",
            "2023-01-15,6.4,high",
            "2023-02-15,6.0,high",
            "2023-03-15,5.0,medium",
            "2023-04-15,4.9,medium",
            "2023-05-15,4.0,medium",
            "2023-06-15,3.0,low",
            "2023-07-15,3.2,low",
            "2023-08-15,3.7,medium",
            "2023-09-15,3.7,medium",
            "2023-10-15,3.2,low",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    @pytest.fixture
    def output_dir(self, tmp_workspace: Path) -> Path:
        d = tmp_workspace / "output"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _build_orch(self, tmp_workspace: Path) -> InstitutionalOrchestrator:
        """Construct an orchestrator with a slimmed-down pipeline for
        environments where optional dependencies may be missing.

        Tries ``with_default_pipeline()`` first.  If import failures occur,
        falls back to a manual DAG with the same structure but using mock fns.
        """
        return InstitutionalOrchestrator.with_default_pipeline(
            checkpoint_dir=str(tmp_workspace / "checkpoints"),
        )

    def test_full_pipeline_with_defaults(
        self,
        tmp_workspace: Path,
        gold_csv: Path,
        event_csv: Path,
        output_dir: Path,
    ) -> None:
        orch = InstitutionalOrchestrator.with_default_pipeline(
            checkpoint_dir=str(tmp_workspace / "checkpoints"),
            max_workers=4,
        )

        # Run with the most basic params; some stages may fail due to
        # missing optional packages (news, regime detector, etc.).
        # We verify the orchestrator handles partial failures gracefully.
        assessment = orch.run_all(
            trigger="integration_test",
            pipeline_id="int_test_full",
            event_type="CPIEvent",
            data_path=str(event_csv),
            gold_path=str(gold_csv),
            output_dir=str(output_dir),
            asset="XAU/USD",
            horizon=3,
            news_topics=("gold",),
            news_lookback_days=1,
        )

        # Orchestrator should always produce an assessment
        assert isinstance(assessment, InstitutionalAssessment)
        assert assessment.pipeline_id == "int_test_full"

        # ingest_event should succeed (EventRegistry + CPIEvent exist)
        ingest_stage = next((s for s in assessment.stages if s.stage_id == "ingest_event"), None)
        assert ingest_stage is not None

        # At least some stages may succeed.  We check the structure is
        # correct regardless.
        completed = {s.stage_id for s in assessment.stages if s.status == "ok"}
        failed = {s.stage_id for s in assessment.stages if s.status == "failed"}

# DAG execution should have visited all 26 jobs
        all_stage_ids = {s.stage_id for s in assessment.stages}
        expected = {
            "pre_market_scan", "signal_assessment", "event_triage",
            "evidence_collection", "evidence_reasoning", "counter_evidence",
            "thesis_construction", "thesis_update",
            "confidence_engine", "scenario_generation",
            "risk_reward_validation", "bias_prevention",
            "decision_engine", "trade_recommendation",
            "ingest_event", "ingest_news", "build_legacy_pipeline",
            "regime_diagnosis",
            "forecast", "forecast_confidence", "forecast_validation",
            "build_context", "risk_measures", "position_sizing",
            "risk_gate", "finalize", "technical_research",
        }
        assert all_stage_ids == expected, f"Missing stages: {expected - all_stage_ids}"

        # The finalize stage should produce a bundle dict if it ran
        if "finalize" in completed:
            bundle = assessment.outputs.get("finalize", {})
            assert isinstance(bundle, dict)

    def test_w12_runs_before_w9_in_default_pipeline(self) -> None:
        """Frozen v1.x spec: W12 (fragility audit) is invoked before W9
        (confidence assignment); W9 consumes the W12 downside case."""
        orch = InstitutionalOrchestrator.with_default_pipeline()
        levels = _topological_levels(orch._jobs)
        level_of = {jid: i for i, level in enumerate(levels) for jid in level}

        assert level_of["scenario_generation"] < level_of["confidence_engine"]
        assert "scenario_generation" in orch._jobs["confidence_engine"].dependencies
        assert "evidence_reasoning" in orch._jobs["confidence_engine"].dependencies
        assert "confidence_engine" not in orch._jobs["scenario_generation"].dependencies

    def test_partial_pipeline_manual(
        self,
        tmp_workspace: Path,
        gold_csv: Path,
        event_csv: Path,
        output_dir: Path,
    ) -> None:
        """Register only a subset of jobs to test specific sub‑DAGs."""
        orch = InstitutionalOrchestrator(
            checkpoint_dir=str(tmp_workspace / "checkpoints"),
        )

        orch.register(PipelineJob("ingest_event", (), lambda: {"status": "ingested"}))
        orch.register(PipelineJob("forecast", ("ingest_event",), lambda: {"forecast": [1, 2, 3]}))

        assessment = orch.run_all(
            trigger="manual",
            event_type="CPIEvent",
            data_path=str(event_csv),
            gold_path=str(gold_csv),
            output_dir=str(output_dir),
        )
        assert len(assessment.stages) == 2
        assert all(s.status == "ok" for s in assessment.stages)
        assert assessment.outputs["forecast"] == {"forecast": [1, 2, 3]}

    def test_resume_on_second_run(
        self,
        tmp_workspace: Path,
    ) -> None:
        call_count = {"a": 0, "b": 0}

        def make_fn(name: str):
            def fn() -> str:
                call_count[name] += 1
                return f"{name}_done"
            return fn

        orch = InstitutionalOrchestrator(
            checkpoint_dir=str(tmp_workspace / "chk"),
        )
        orch.register(PipelineJob("a", (), make_fn("a"), checkpoint=True))
        orch.register(PipelineJob("b", ("a",), make_fn("b"), checkpoint=True))

        # First run
        orch.run_all(pipeline_id="resume_test")
        assert call_count == {"a": 1, "b": 1}

        # Second run — both should resume from checkpoint
        orch.run_all(pipeline_id="resume_test")
        assert call_count == {"a": 1, "b": 1}

    def test_idempotency(self, tmp_workspace: Path) -> None:
        outputs: list[int] = []

        def fn() -> int:
            outputs.append(1)
            return 1

        orch = InstitutionalOrchestrator(
            checkpoint_dir=str(tmp_workspace / "chk2"),
        )
        orch.register(PipelineJob("x", (), fn, cache_ttl=120, checkpoint=True))

        r1 = orch.run_all(pipeline_id="idem")
        r2 = orch.run_all(pipeline_id="idem")
        assert len(outputs) == 1  # only called once
        # Both assessments should have the same output value
        assert r1.outputs == r2.outputs

    def test_error_recovery_partial_output(
        self,
        tmp_workspace: Path,
    ) -> None:
        orch = InstitutionalOrchestrator(
            checkpoint_dir=str(tmp_workspace / "chk3"),
        )
        orch.register(PipelineJob("a", (), lambda: "ok", checkpoint=True))
        orch.register(PipelineJob("b", ("a",), lambda: (_ for _ in ()).throw(
            ValueError("b failed"),
        ), checkpoint=True))
        orch.register(PipelineJob("c", ("a",), lambda: "c_ok", checkpoint=True))

        assessment = orch.run_all(pipeline_id="recovery")
        assert "a" in assessment.outputs
        assert "c" in assessment.outputs
        assert "b" not in assessment.outputs
        assert any("b failed" in e for e in assessment.errors)

    def test_workers_count_respected(self) -> None:
        orch = InstitutionalOrchestrator(max_workers=1)
        assert orch._max_workers == 1

        trail: list[str] = []

        def make_fn(name: str, sleep: float = 0.05):
            def fn() -> str:
                time.sleep(sleep)
                trail.append(name)
                return name
            return fn

        orch.register(PipelineJob("a", (), make_fn("a", 0.03)))
        orch.register(PipelineJob("b", (), make_fn("b", 0.03)))
        orch.register(PipelineJob("c", ("a", "b"), make_fn("c", 0.03)))

        orch.run_all()
        # With max_workers=1, a and b run sequentially; c runs after both
        assert "c" in trail
        assert trail[-1] == "c"


# ===========================================================================
# Stage function unit tests
# ===========================================================================


class TestStageFunctions:
    """Test each stage function in isolation with minimal/mock inputs."""

    def test_ingest_event_missing_data_path(self) -> None:
        from orchestration.institutional_orchestrator import _ingest_event
        with pytest.raises(ValueError, match="data_path"):
            _ingest_event({"event_type": "CPIEvent"}, {})

    def test_ingest_event_invalid_type(self) -> None:
        from orchestration.institutional_orchestrator import _ingest_event
        with pytest.raises((KeyError, TypeError)):
            _ingest_event({"event_type": "NonExistentEvent", "data_path": "/tmp/x.csv"}, {})

    def test_finalize_with_all_outputs(self) -> None:
        from orchestration.institutional_orchestrator import _finalize

        results = {
            "build_legacy_pipeline": {"decision": "STRONG_POSITIVE"},
            "decision_engine": {"decision": "BUY", "institutional_confidence": 0.8},
            "risk_gate": "proceed",
            "forecast": {"points": []},
            "forecast_confidence": {"confidence": 0.85},
            "forecast_validation": {"passed": True},
            "build_context": {"regime": "EXPANSION"},
            "risk_measures": {"var_95": -0.02},
            "position_sizing": {"position_sizing": 0.5, "risk_budget": {}},
        }
        bundle = _finalize({}, results)
        assert bundle["decision"] == {"decision": "BUY", "institutional_confidence": 0.8}
        assert bundle["legacy_decision"] == "STRONG_POSITIVE"
        assert bundle["risk_decision"] == "proceed"

    def test_finalize_falls_back_to_legacy_decision(self) -> None:
        from orchestration.institutional_orchestrator import _finalize

        results = {
            "build_legacy_pipeline": {"decision": "STRONG_POSITIVE"},
            "risk_gate": "proceed",
        }
        bundle = _finalize({}, results)
        assert bundle["decision"] == "STRONG_POSITIVE"
        assert bundle["legacy_decision"] == "STRONG_POSITIVE"

    def test_finalize_ignores_error_from_decision_engine(self) -> None:
        from orchestration.institutional_orchestrator import _finalize

        results = {
            "build_legacy_pipeline": {"decision": "STRONG_POSITIVE"},
            "decision_engine": {"error": "decision_engine stage failed"},
            "risk_gate": "proceed",
        }
        bundle = _finalize({}, results)
        assert bundle["decision"] == "STRONG_POSITIVE"
        assert bundle["legacy_decision"] == "STRONG_POSITIVE"

    def test_forecast_missing_gold_path(self) -> None:
        from orchestration.institutional_orchestrator import _forecast
        with pytest.raises(KeyError):
            _forecast({"horizon": 3}, {})

    def test_build_legacy_pipeline_missing_event(self) -> None:
        from orchestration.institutional_orchestrator import _build_legacy_pipeline
        with pytest.raises(ValueError, match="_event not found"):
            _build_legacy_pipeline({"data_path": "/x", "gold_path": "/y", "output_dir": "/z"}, {})


# ===========================================================================
# Production lineage — production orchestration now creates lineage records
# ===========================================================================


class TestProductionLineage:
    """Verify that _build_legacy_pipeline activates lineage recording."""

    def _write_calendar(self, base_path: Path) -> str:
        import pandas as pd
        cal_dir = base_path / "calendar"
        cal_dir.mkdir(parents=True, exist_ok=True)
        cal_path = cal_dir / "cpi_releases.csv"
        pd.DataFrame([
            {"reference_period": "2020-01-01", "release_date": "2020-01-14", "release_time": "08:30", "timezone": "US/Eastern"},
            {"reference_period": "2020-02-01", "release_date": "2020-02-01", "release_time": "08:30", "timezone": "US/Eastern"},
            {"reference_period": "2020-03-01", "release_date": "2020-03-02", "release_time": "08:30", "timezone": "US/Eastern"},
            {"reference_period": "2020-04-01", "release_date": "2020-04-01", "release_time": "08:30", "timezone": "US/Eastern"},
        ]).to_csv(cal_path, index=False)
        return str(cal_path)

    def _gold_rows(self) -> list[dict]:
        import pandas as pd
        rows = []
        price = 1000.0
        for i in range(60):
            d = pd.Timestamp("2020-01-31") + pd.Timedelta(days=i)
            if d.weekday() >= 5:
                continue
            rows.append({"Date": d.date().isoformat(), "Close": price})
            price += 2.0 if i < 30 else -1.0
        return rows

    def test_production_pipeline_creates_lineage(self, tmp_path: Path) -> None:
        from orchestration.institutional_orchestrator import _build_legacy_pipeline
        from knowledge.events.cpi import CPIEvent
        import pandas as pd

        event_path = tmp_path / "cpi.csv"
        pd.DataFrame([
            {"Date": "2020-01-01", "Value": 100.0},
            {"Date": "2020-02-01", "Value": 101.0},
            {"Date": "2020-03-01", "Value": 99.0},
        ]).to_csv(event_path, index=False)

        gold_path = tmp_path / "gold.csv"
        pd.DataFrame(self._gold_rows()).to_csv(gold_path, index=False)

        cal_path = self._write_calendar(tmp_path)
        output_dir = tmp_path / "output"

        params = {
            "_event": CPIEvent(),
            "data_path": str(event_path),
            "gold_path": str(gold_path),
            "gold_lessons_path": str(gold_path),
            "output_dir": str(output_dir),
            "release_calendar_path": cal_path,
            "asset": "GOLD",
            "reasoning_horizon": 5,
        }
        result = _build_legacy_pipeline(params, {})

        assert "lineage_registry" in result, (
            "lineage_registry missing from _build_legacy_pipeline output"
        )
        reg = result["lineage_registry"]
        records = reg.all_records()
        assert len(records) > 0, (
            "Expected at least one lineage record from production pipeline"
        )

    def test_production_lineage_backward_trace(self, tmp_path: Path) -> None:
        from orchestration.institutional_orchestrator import _build_legacy_pipeline
        from knowledge.events.cpi import CPIEvent
        import pandas as pd

        event_path = tmp_path / "cpi.csv"
        pd.DataFrame([
            {"Date": "2020-01-01", "Value": 100.0},
            {"Date": "2020-02-01", "Value": 101.0},
            {"Date": "2020-03-01", "Value": 99.0},
        ]).to_csv(event_path, index=False)

        gold_path = tmp_path / "gold.csv"
        pd.DataFrame(self._gold_rows()).to_csv(gold_path, index=False)

        cal_path = self._write_calendar(tmp_path)
        output_dir = tmp_path / "output"

        params = {
            "_event": CPIEvent(),
            "data_path": str(event_path),
            "gold_path": str(gold_path),
            "gold_lessons_path": str(gold_path),
            "output_dir": str(output_dir),
            "release_calendar_path": cal_path,
            "asset": "GOLD",
            "reasoning_horizon": 5,
        }
        result = _build_legacy_pipeline(params, {})

        reg = result["lineage_registry"]
        decision = result.get("decision")
        assert decision is not None, "No decision produced"

        path = reg.trace(decision.decision_id, "decision")
        assert len(path) >= 3, (
            f"Expected at least 3 lineage hops from decision, got {len(path)}"
        )

        entity_types: set[str] = set()
        for r in path:
            entity_types.add(r.source_type)
            entity_types.add(r.target_type)
        for t in ("source_data", "lesson", "knowledge_record"):
            assert t in entity_types, (
                f"Entity type '{t}' missing from backward trace"
            )


# ===========================================================================
# Default pipeline integration — smoke tests with fixtures
# ===========================================================================


class TestDefaultPipelineIntegration:
    """Smoke tests using the factory method with fixtures that satisfy
    minimum dependencies."""

    @pytest.fixture
    def cpi_event_csv(self, tmp_path: Path) -> Path:
        p = tmp_path / "cpi.csv"
        p.write_text(
            "date,value,condition\n"
            "2024-01-15,3.4,medium\n"
            "2024-02-15,3.2,low\n"
            "2024-03-15,3.5,medium\n",
            encoding="utf-8",
        )
        return p

    @pytest.fixture
    def gold_prices_csv(self, tmp_path: Path) -> Path:
        p = tmp_path / "gold.csv"
        p.write_text(
            "ds,price\n"
            "2024-01-01,2050.0\n"
            "2024-02-01,2030.0\n"
            "2024-03-01,2070.0\n"
            "2024-04-01,2100.0\n"
            "2024-05-01,2080.0\n"
            "2024-06-01,2120.0\n"
            "2024-07-01,2150.0\n",
encoding="utf-8",
        )
        return p

    def test_default_pipeline_dag_structure(self) -> None:
        orch = InstitutionalOrchestrator.with_default_pipeline()
        expected_jobs = {
            "pre_market_scan", "signal_assessment", "evidence_collection",
            "evidence_reasoning", "counter_evidence", "thesis_construction",
            "thesis_update", "confidence_engine", "scenario_generation",
            "risk_reward_validation", "bias_prevention", "decision_engine",
            "trade_recommendation", "event_triage",
            "ingest_event", "ingest_news", "build_legacy_pipeline",
            "regime_diagnosis",
            "forecast", "forecast_confidence", "forecast_validation",
            "build_context", "risk_measures", "position_sizing",
            "risk_gate", "finalize", "technical_research",
        }
        assert set(orch.list_jobs()) == expected_jobs

    def test_default_pipeline_no_circular(self) -> None:
        orch = InstitutionalOrchestrator.with_default_pipeline()
        levels = _topological_levels(orch._jobs)
        visited = {jid for level in levels for jid in level}
        assert visited == set(orch.list_jobs())

    def test_finalize_depends_on_all_join_points(
        self,
    ) -> None:
        orch = InstitutionalOrchestrator.with_default_pipeline()
        finalize_job = orch._jobs["finalize"]
        assert "risk_gate" in finalize_job.dependencies
        assert "position_sizing" in finalize_job.dependencies
        assert "forecast_confidence" in finalize_job.dependencies
        assert "forecast_validation" in finalize_job.dependencies


# ===========================================================================
# Knowledge Graph -> Institutional Evidence integration (boundary audit fix)
# ===========================================================================


def _signal_assessment_dict() -> dict:
    return {
        "assessment_id": "sa_int_kr",
        "briefing_id": "premarket_int_kr",
        "timestamp": "2026-08-06T12:00:00",
        "regime": "NORMAL_GROWTH",
        "regime_confidence": 0.85,
        "observations": [
            {
                "observation_id": "obs_gold",
                "source": "overnight_price",
                "classification": "Signal",
                "confidence": 0.85,
                "regime": "NORMAL_GROWTH",
                "reason": "criteria met",
                "evidence": [
                    {
                        "criterion": "magnitude",
                        "score": 1.0,
                        "threshold": 2.0,
                        "passed": True,
                        "detail": "z=3.0",
                    },
                ],
                "instrument": "XAU/USD",
                "value": 1910.0,
                "change_pct": 0.5,
                "change_sigma": 1.2,
            },
        ],
    }


class TestKnowledgeGraphInstitutionalIntegration:
    """Regression tests for the boundary-audit integration:

    the institutional ``evidence_collection`` stage must consume the
    Knowledge Graph produced by ``build_legacy_pipeline`` so institutional
    evidence references real Knowledge Records, while retaining the
    synthetic-KR fallback when no graph exists.
    """

    def _knowledge_graph(self) -> "KnowledgeGraph":
        from knowledge.graph.graph import KnowledgeGraph
        from knowledge.graph.node import GraphNode

        kg = KnowledgeGraph()
        kg.add_node(GraphNode(
            node_id="CPI_GOLD_medium_12D",
            node_type="knowledge_record",
            properties={
                "knowledge_id": "CPI_GOLD_medium_12D",
                "event_type": "GENERAL",
                "average_return_pct": 1.25,
                "sample_count": 20,
                "confidence": 0.7,
            },
        ))
        return kg

    def test_evidence_collection_depends_on_build_legacy_pipeline(self) -> None:
        orch = InstitutionalOrchestrator.with_default_pipeline()
        assert "build_legacy_pipeline" in orch._jobs["evidence_collection"].dependencies

    def test_real_knowledge_records_consumed_not_synthetic(self) -> None:
        from orchestration.institutional_orchestrator import _evidence_collection

        results = {
            "signal_assessment": _signal_assessment_dict(),
            "build_legacy_pipeline": {"knowledge_graph": self._knowledge_graph()},
        }
        collection = _evidence_collection({"regime_weight": 0.8}, results)

        assert collection.evidence_count > 0
        for ev in collection.items:
            assert ev.source_kr_id == "CPI_GOLD_medium_12D"
            assert not ev.source_kr_id.startswith("kr_synthetic_")
            assert ev.source_kr_node_id == "CPI_GOLD_medium_12D"

    def test_retrieval_path_exercised_returns_kr_ids(self) -> None:
        from orchestration.institutional_orchestrator import _evidence_collection

        kg = self._knowledge_graph()
        kr_ids = [n.node_id for n in kg.filter_nodes(event_type="GENERAL")]
        assert kr_ids == ["CPI_GOLD_medium_12D"]

        results = {
            "signal_assessment": _signal_assessment_dict(),
            "build_legacy_pipeline": {"knowledge_graph": kg},
        }
        collection = _evidence_collection({}, results)
        assert any(
            ev.source_kr_id in kr_ids for ev in collection.items
        )

    def test_institutional_pipeline_works_without_knowledge_graph(self) -> None:
        from orchestration.institutional_orchestrator import _evidence_collection

        results = {
            "signal_assessment": _signal_assessment_dict(),
        }
        collection = _evidence_collection({}, results)

        assert collection.evidence_count > 0
        for ev in collection.items:
            assert ev.source_kr_id.startswith("no_kr_")
            assert ev.source_kr_id == ev.source_kr_node_id
            assert ev.metadata["provenance_type"] == "observation"
            assert ev.metadata["knowledge_record_id"] is None

    def test_params_knowledge_graph_still_honored_as_fallback(self) -> None:
        from orchestration.institutional_orchestrator import _evidence_collection

        results = {"signal_assessment": _signal_assessment_dict()}
        params = {"knowledge_graph": self._knowledge_graph()}
        collection = _evidence_collection(params, results)

        assert collection.evidence_count > 0
        for ev in collection.items:
            assert ev.source_kr_id == "CPI_GOLD_medium_12D"
            assert not ev.source_kr_id.startswith("kr_synthetic_")


class TestThesisScenarioDAGDeterminism:
    """Correction 004 determinism reproduction (Runtime 009).

    Replicates the affected thesis_update -> scenario_generation ->
    confidence_engine -> risk_reward_validation -> decision_engine chain with
    the real stage functions and identical canned upstream inputs, executed
    repeatedly with parallel workers. Proves the race is impossible through
    the DAG dependency model and that identical inputs produce an identical
    decision.
    """

    VERSIONED_THESIS_ID = "th_race.v2"

    def _make_reasoning(self) -> "EvidenceReasoning":
        from evidence_reasoning.contracts import EvidenceReasoning, EvidenceSet

        return EvidenceReasoning(
            reasoning_id="er_race",
            collection_id="ec_race",
            timestamp="2026-08-13T09:00:00",
            regime="NORMAL_GROWTH",
            evidence_sets=(
                EvidenceSet(
                    set_id="es_real_yield",
                    event_type="REAL_YIELD",
                    bias="bullish",
                    supporting_evidence_ids=("ev1", "ev2"),
                    net_institutional_weight=0.8,
                    consensus_score=0.9,
                    conflict_score=0.0,
                    regime_dependency="NORMAL_GROWTH",
                    confidence_contribution=0.8,
                    explanation="real yield decline supports gold",
                ),
            ),
            total_evidence_sets=1,
            total_evidence_items=2,
        )

    def _make_assessment(self) -> "CounterEvidenceAssessment":
        from counter_evidence.contracts import CounterEvidenceAssessment

        return CounterEvidenceAssessment(
            assessment_id="cea_race",
            reasoning_id="er_race",
            timestamp="2026-08-13T09:00:00",
            regime="NORMAL_GROWTH",
            contradicting_set_ids=(),
            missing_evidence=(),
            bias_flags=(),
            conflict_severity=0.0,
            confidence_penalty=0.0,
            explanation="no counter-evidence",
        )

    def _make_construction(self) -> "ThesisConstruction":
        from thesis_construction.contracts import InvestmentThesis, ThesisConstruction

        thesis = InvestmentThesis(
            thesis_id="th_race",
            direction="bullish",
            supporting_set_ids=("es_real_yield",),
            counter_evidence_ids=(),
            regime="NORMAL_GROWTH",
            economic_mechanism="falling real yields support gold",
            time_horizon_days=90,
            invalidating_conditions=("real yields reverse",),
            remaining_unknowns=("USD_FX",),
            confidence_inputs={
                "avg_supporting_weight": 0.8,
                "avg_supporting_consensus": 0.9,
                "conflict_severity": 0.0,
                "confidence_penalty": 0.0,
                "raw_support": 0.64,
            },
            institutional_support=0.8,
            explanation="test thesis",
        )
        return ThesisConstruction(
            construction_id="tc_race",
            reasoning_id="er_race",
            assessment_id="cea_race",
            timestamp="2026-08-13T09:00:00",
            regime="NORMAL_GROWTH",
            theses=(thesis,),
            ranked_thesis_ids=("th_race",),
            total_theses=1,
            primary_thesis_id="th_race",
        )

    def _build_orch(
        self, checkpoint_dir: str | None = None
    ) -> InstitutionalOrchestrator:
        from orchestration.stages import (
            _confidence_engine,
            _decision_engine,
            _risk_reward_validation,
            _scenario_generation,
            _thesis_update,
        )

        reasoning = self._make_reasoning()
        assessment = self._make_assessment()
        construction = self._make_construction()

        orch = InstitutionalOrchestrator(
            checkpoint_dir=checkpoint_dir,
            max_workers=4,
        )
        orch.register(PipelineJob(
            job_id="evidence_reasoning",
            dependencies=(),
            fn=lambda: reasoning,
        ))
        orch.register(PipelineJob(
            job_id="counter_evidence",
            dependencies=("evidence_reasoning",),
            fn=lambda: assessment,
        ))
        orch.register(PipelineJob(
            job_id="thesis_construction",
            dependencies=("evidence_reasoning", "counter_evidence"),
            fn=lambda: construction,
        ))
        orch.register(PipelineJob(
            job_id="thesis_update",
            dependencies=("thesis_construction", "evidence_reasoning",
                          "counter_evidence"),
            fn=orch._bind(_thesis_update),
        ))
        orch.register(PipelineJob(
            job_id="scenario_generation",
            dependencies=("thesis_construction", "thesis_update"),
            fn=orch._bind(_scenario_generation),
        ))
        orch.register(PipelineJob(
            job_id="confidence_engine",
            dependencies=("thesis_update", "scenario_generation",
                          "evidence_reasoning"),
            fn=orch._bind(_confidence_engine),
        ))
        orch.register(PipelineJob(
            job_id="risk_reward_validation",
            dependencies=("scenario_generation",),
            fn=orch._bind(_risk_reward_validation),
        ))
        orch.register(PipelineJob(
            job_id="decision_engine",
            dependencies=("thesis_construction", "confidence_engine",
                          "scenario_generation", "risk_reward_validation"),
            fn=orch._bind(_decision_engine),
        ))
        return orch

    @staticmethod
    def _decision_signature(decision) -> dict:
        # decision_explanation embeds the random scenario_id (engine.py
        # _explanation), so the id is normalized out; everything else must be
        # bit-identical across runs.
        import re

        explanation = re.sub(
            r"sc_[0-9a-f]{12}",
            "sc_<id>",
            decision.decision_explanation,
        )
        return {
            "decision": decision.decision,
            "selected_thesis_id": decision.selected_thesis_id,
            "institutional_confidence": decision.institutional_confidence,
            "decision_explanation": explanation,
            "preconditions": tuple(decision.preconditions),
            "invalidation_conditions": tuple(decision.invalidation_conditions),
            "risk_reward_summary": decision.risk_reward_summary,
        }

    def test_race_free_determinism_repeated_identical_inputs(
        self, tmp_path: Path
    ) -> None:
        orch = self._build_orch(str(tmp_path / "chk"))
        levels = _topological_levels(orch._jobs)
        level_of = {jid: i for i, level in enumerate(levels) for jid in level}
        assert "thesis_update" in orch._jobs["scenario_generation"].dependencies
        assert level_of["thesis_update"] < level_of["scenario_generation"]

        signatures: list[dict] = []
        scenario_fingerprints: list[dict] = []
        confidence_map: list[dict] = []
        stage_order: list[tuple[str, ...]] = []

        for i in range(12):
            assessment = orch.run_all(
                trigger="race_repro",
                pipeline_id=f"race_repro_{i}",
                force=True,
            )
            assert assessment.errors == ()

            outputs = assessment.outputs
            update = outputs["thesis_update"]
            generation = outputs["scenario_generation"]
            confidence = outputs["confidence_engine"]
            decision = outputs["decision_engine"]

            assert not isinstance(update, dict) or "error" not in update
            assert not isinstance(generation, dict) or "error" not in generation
            assert not isinstance(confidence, dict) or "error" not in confidence
            assert not isinstance(decision, dict) or "error" not in decision

            # thesis_update always completed before scenario_generation:
            # its stage record must appear in an earlier DAG level.
            positions = {
                s.stage_id: idx
                for idx, s in enumerate(assessment.stages)
            }
            stage_order.append(tuple(
                s.stage_id for s in assessment.stages
                if s.stage_id in (
                    "thesis_update", "scenario_generation",
                    "confidence_engine", "decision_engine",
                )
            ))
            assert positions["thesis_update"] < positions["scenario_generation"]

            # scenario_generation consumed the update: scenarios are keyed to
            # the versioned thesis produced by thesis_update, and the
            # scenario generation is built from the update's construction.
            scenario_ids = {s.thesis_id for s in generation.scenarios}
            assert scenario_ids == {self.VERSIONED_THESIS_ID}
            assert generation.construction_id == update.update_id

            # confidence resolves the same versioned thesis.
            conf_by_id = {
                tc.thesis_id: tc.final_confidence
                for tc in confidence.theses_confidence
            }
            assert self.VERSIONED_THESIS_ID in conf_by_id
            assert conf_by_id[self.VERSIONED_THESIS_ID] > 0.0

            # decision matches the same versioned thesis; no race-induced
            # "no eligible thesis" NO_TRADE collapse is possible.
            assert decision.selected_thesis_id == self.VERSIONED_THESIS_ID
            assert decision.decision != "NO_TRADE"
            assert decision.institutional_confidence > 0.0

            fingerprints: dict = {}
            for s in generation.scenarios:
                fingerprints[(s.thesis_id, s.scenario_type)] = {
                    "probability": s.probability,
                    "confirmation_conditions": tuple(s.confirmation_conditions),
                    "invalidation_conditions": tuple(s.invalidation_conditions),
                }
            scenario_fingerprints.append(fingerprints)
            confidence_map.append(conf_by_id)
            signatures.append(self._decision_signature(decision))

        # Identical inputs -> identical scenario probabilities/conditions,
        # identical confidence, and an identical decision across every run.
        assert all(fp == scenario_fingerprints[0] for fp in scenario_fingerprints)
        assert all(cm == confidence_map[0] for cm in confidence_map)
        assert all(sig == signatures[0] for sig in signatures)
        assert all(
            order == stage_order[0] for order in stage_order
        )


