from __future__ import annotations

import datetime
import os
import tempfile
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from orchestration.cache import CacheManager
from orchestration.checkpoints import CheckpointManager
from orchestration.dag import _cache_key, _topological_levels
from orchestration.jobs import PipelineJob
from orchestration.models import CheckpointResult, InstitutionalAssessment, StageRecord

from orchestration.stages import (
    _build_context,
    _build_legacy_pipeline,
    _finalize,
    _forecast,
    _forecast_confidence,
    _forecast_validation,
    _ingest_event,
    _ingest_news,
    _position_sizing,
    _risk_gate,
    _risk_measures,
)

StageFn = Callable[..., Any]


class InstitutionalOrchestrator:
    def __init__(
        self,
        checkpoint_dir: str | None = None,
        max_workers: int = 4,
    ) -> None:
        if checkpoint_dir is None:
            checkpoint_dir = os.path.join(
                tempfile.gettempdir(), "aurumai_checkpoints"
            )
        self._checkpoints = CheckpointManager(checkpoint_dir)
        self._cache = CacheManager()
        self._max_workers = max_workers
        self._jobs: dict[str, PipelineJob] = OrderedDict()
        self._results: dict[str, Any] = {}
        self._stage_records: list[StageRecord] = []
        self._params: dict[str, Any] = {}
        self._lock = threading.Lock()

    def register(self, job: PipelineJob) -> None:
        if job.job_id in self._jobs:
            raise ValueError(f"Job {job.job_id!r} already registered")
        self._jobs[job.job_id] = job

    @property
    def registered_count(self) -> int:
        return len(self._jobs)

    def list_jobs(self) -> list[str]:
        return list(self._jobs.keys())

    @property
    def params(self) -> dict[str, Any]:
        return self._params

    def _bind(self, fn: StageFn) -> Callable[[], Any]:
        def wrapper() -> Any:
            return fn(self._params, self._results)
        return wrapper

    def run_all(
        self,
        trigger: str = "manual",
        pipeline_id: str | None = None,
        force: bool = False,
        **params: Any,
    ) -> InstitutionalAssessment:
        if not self._jobs:
            raise RuntimeError("No jobs registered")

        if pipeline_id is None:
            pipeline_id = (
                f"pipe_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            )

        self._results.clear()
        self._stage_records.clear()
        self._params = params
        wall_t0 = time.monotonic()
        errors: list[str] = []
        cache_hits = 0

        levels = _topological_levels(self._jobs)
        for level in levels:
            futures: dict[Any, str] = {}
            n_workers = min(len(level), self._max_workers)
            with ThreadPoolExecutor(max_workers=n_workers) as pool:
                for jid in level:
                    future = pool.submit(
                        self._execute_job, jid, pipeline_id, force,
                    )
                    futures[future] = jid

                for future in as_completed(futures):
                    jid = futures[future]
                    try:
                        record = future.result()
                    except Exception as exc:
                        record = StageRecord(
                            stage_id=jid,
                            status="failed",
                            duration_ms=0.0,
                            error=str(exc),
                        )
                    self._stage_records.append(record)
                    if record.status == "failed":
                        errors.append(f"{jid}: {record.error}")
                    elif record.status == "cached":
                        cache_hits += 1

        wall_time_ms = (time.monotonic() - wall_t0) * 1000.0

        return InstitutionalAssessment(
            pipeline_id=pipeline_id,
            trigger=trigger,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            stages=tuple(self._stage_records),
            cache_hits=cache_hits,
            wall_time_ms=wall_time_ms,
            outputs=dict(self._results),
            errors=tuple(errors),
        )

    def _execute_job(
        self,
        job_id: str,
        pipeline_id: str,
        force: bool,
    ) -> StageRecord:
        job = self._jobs[job_id]
        t0 = time.perf_counter()

        if not force and job.checkpoint:
            cp = self._checkpoints.read(pipeline_id, job_id)
            if cp is not None:
                self._results[job_id] = cp.get("output")
                elapsed = (time.perf_counter() - t0) * 1000.0
                return StageRecord(
                    stage_id=job_id,
                    status="ok",
                    duration_ms=elapsed,
                    checkpoint=CheckpointResult(
                        passed=True,
                        notes="Resumed from checkpoint",
                        severity="info",
                    ),
                )

        ck = _cache_key(job_id, **self._params)
        if not force and job.cache_ttl is not None:
            cached = self._cache.get(ck)
            if cached is not None:
                self._results[job_id] = cached
                elapsed = (time.perf_counter() - t0) * 1000.0
                self._cache.inc_hit()
                return StageRecord(
                    stage_id=job_id,
                    status="cached",
                    duration_ms=elapsed,
                )

        exception: Exception | None = None
        output: Any = None
        try:
            output = job.fn()
        except Exception as exc:
            exception = exc

        elapsed = (time.perf_counter() - t0) * 1000.0
        if exception is not None:
            return StageRecord(
                stage_id=job_id,
                status="failed",
                duration_ms=elapsed,
                error=str(exception),
            )

        if job.cache_ttl is not None:
            self._cache.set(ck, output, ttl=job.cache_ttl)

        if job.checkpoint:
            self._checkpoints.write(
                pipeline_id,
                job_id,
                {
                    "output": output,
                    "pipeline_id": pipeline_id,
                    "job_id": job_id,
                    "timestamp": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                },
            )

        self._results[job_id] = output
        return StageRecord(stage_id=job_id, status="ok", duration_ms=elapsed)

    @classmethod
    def with_default_pipeline(
        cls,
        checkpoint_dir: str | None = None,
        max_workers: int = 4,
    ) -> InstitutionalOrchestrator:
        orch = cls(checkpoint_dir=checkpoint_dir, max_workers=max_workers)

        orch.register(PipelineJob(
            job_id="ingest_event",
            dependencies=(),
            fn=orch._bind(_ingest_event),
            cache_ttl=600,
            checkpoint=True,
        ))

        orch.register(PipelineJob(
            job_id="ingest_news",
            dependencies=(),
            fn=orch._bind(_ingest_news),
            cache_ttl=300,
            checkpoint=True,
        ))

        orch.register(PipelineJob(
            job_id="build_legacy_pipeline",
            dependencies=("ingest_event",),
            fn=orch._bind(_build_legacy_pipeline),
            cache_ttl=600,
            checkpoint=True,
        ))

        orch.register(PipelineJob(
            job_id="forecast",
            dependencies=("ingest_event",),
            fn=orch._bind(_forecast),
            cache_ttl=600,
            checkpoint=True,
        ))

        orch.register(PipelineJob(
            job_id="forecast_confidence",
            dependencies=("forecast",),
            fn=orch._bind(_forecast_confidence),
            cache_ttl=600,
            checkpoint=True,
        ))

        orch.register(PipelineJob(
            job_id="forecast_validation",
            dependencies=("forecast",),
            fn=orch._bind(_forecast_validation),
            cache_ttl=None,
            checkpoint=True,
        ))

        orch.register(PipelineJob(
            job_id="build_context",
            dependencies=("forecast", "ingest_news"),
            fn=orch._bind(_build_context),
            cache_ttl=600,
            checkpoint=True,
        ))

        orch.register(PipelineJob(
            job_id="risk_measures",
            dependencies=("forecast",),
            fn=orch._bind(_risk_measures),
            cache_ttl=300,
            checkpoint=True,
        ))

        orch.register(PipelineJob(
            job_id="position_sizing",
            dependencies=("risk_measures",),
            fn=orch._bind(_position_sizing),
            cache_ttl=300,
            checkpoint=True,
        ))

        orch.register(PipelineJob(
            job_id="risk_gate",
            dependencies=("build_context", "build_legacy_pipeline", "risk_measures"),
            fn=orch._bind(_risk_gate),
            cache_ttl=120,
            checkpoint=True,
        ))

        orch.register(PipelineJob(
            job_id="finalize",
            dependencies=("risk_gate", "position_sizing", "forecast_confidence",
                          "forecast_validation"),
            fn=orch._bind(_finalize),
            cache_ttl=None,
            checkpoint=True,
        ))

        return orch
