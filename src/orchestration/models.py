from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict


@dataclass(frozen=True)
class CheckpointResult:
    passed: bool
    notes: str
    severity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "notes": self.notes,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class StageRecord:
    stage_id: str
    status: str
    duration_ms: float
    error: str | None = None
    checkpoint: CheckpointResult | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "stage_id": self.stage_id,
            "status": self.status,
            "duration_ms": self.duration_ms,
        }
        if self.error is not None:
            d["error"] = self.error
        if self.checkpoint is not None:
            d["checkpoint"] = self.checkpoint.to_dict()
        return d


@dataclass(frozen=True)
class InstitutionalAssessment:
    pipeline_id: str
    trigger: str
    timestamp: str
    stages: tuple[StageRecord, ...]
    cache_hits: int
    wall_time_ms: float
    outputs: dict[str, Any] = field(default_factory=lambda: FrozenDict())
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "outputs", freeze_dict(self.outputs))

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "trigger": self.trigger,
            "timestamp": self.timestamp,
            "stages": [s.to_dict() for s in self.stages],
            "cache_hits": self.cache_hits,
            "wall_time_ms": self.wall_time_ms,
            "stages_completed": [s.stage_id for s in self.stages if s.status != "failed"],
            "errors": list(self.errors),
        }
