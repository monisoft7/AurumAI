from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class PipelineJob:
    job_id: str
    dependencies: tuple[str, ...]
    fn: Callable[[], Any]
    cache_ttl: int | None = None
    checkpoint: bool = False
