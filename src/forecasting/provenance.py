from __future__ import annotations

import datetime
import hashlib
import subprocess
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ForecastProvenance:
    source: str
    model_version: str
    training_window: str
    registry_version: str
    git_commit: str
    data_hash: str
    created_at: str

    @staticmethod
    def resolve_git_commit() -> str:
        try:
            return (
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
                .decode("ascii")
                .strip()
            )
        except Exception:
            return "unknown"

    @staticmethod
    def compute_data_hash(data: pd.DataFrame) -> str:
        canonical = data.copy()
        for col in canonical.select_dtypes(include="datetime64").columns:
            canonical[col] = canonical[col].astype(str)
        canonical = canonical.sort_index(axis=1)
        csv_bytes = canonical.to_csv(index=False).encode("utf-8")
        return hashlib.sha256(csv_bytes).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "model_version": self.model_version,
            "training_window": self.training_window,
            "registry_version": self.registry_version,
            "git_commit": self.git_commit,
            "data_hash": self.data_hash,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ForecastProvenance:
        return cls(
            source=str(data["source"]),
            model_version=str(data["model_version"]),
            training_window=str(data["training_window"]),
            registry_version=str(data["registry_version"]),
            git_commit=str(data["git_commit"]),
            data_hash=str(data["data_hash"]),
            created_at=str(data["created_at"]),
        )
