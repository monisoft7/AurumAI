from __future__ import annotations

import hashlib
import json
from typing import Any

from orchestration.jobs import PipelineJob


def _topological_levels(jobs: dict[str, PipelineJob]) -> list[list[str]]:
    in_degree: dict[str, int] = {}
    for jid, job in jobs.items():
        in_degree.setdefault(jid, 0)
        for dep in job.dependencies:
            in_degree[jid] = in_degree.get(jid, 0) + 1

    levels: list[list[str]] = []
    remaining = set(jobs.keys())

    while remaining:
        ready = [jid for jid in remaining if in_degree.get(jid, 0) == 0]
        if not ready:
            cycle = ", ".join(sorted(remaining))
            raise ValueError(f"Circular dependency detected among: {cycle}")
        levels.append(ready)
        for jid in ready:
            remaining.remove(jid)
            for other in remaining:
                if jid in jobs[other].dependencies:
                    in_degree[other] = in_degree.get(other, 0) - 1

    return levels


def _cache_key(job_id: str, **params: Any) -> str:
    raw = json.dumps({"job_id": job_id, **params}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()
