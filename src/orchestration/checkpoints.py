from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from knowledge._compat import atomic_write_json


class CheckpointManager:
    def __init__(self, checkpoint_dir: str) -> None:
        self._root = Path(checkpoint_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    def path_for(self, pipeline_id: str, job_id: str) -> Path:
        return self._root / pipeline_id / f"{job_id}.json"

    def exists(self, pipeline_id: str, job_id: str) -> bool:
        return self.path_for(pipeline_id, job_id).exists()

    def write(self, pipeline_id: str, job_id: str, data: dict[str, Any]) -> None:
        p = self.path_for(pipeline_id, job_id)
        atomic_write_json(p, data, default=str)

    def read(self, pipeline_id: str, job_id: str) -> dict[str, Any] | None:
        p = self.path_for(pipeline_id, job_id)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def clear(self, pipeline_id: str) -> None:
        p = self._root / pipeline_id
        if p.exists():
            shutil.rmtree(p)

    def clear_all(self) -> None:
        for child in self._root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
