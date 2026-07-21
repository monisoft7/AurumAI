"""Institutional Experiment Registry.

Permanent, immutable record of every institutional experiment executed
by AurumAI.  File-based, deterministic, zero external dependencies.

Reuses Experiment Framework types — never modifies them.
"""

from __future__ import annotations

import hashlib
import json
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from knowledge._compat import atomic_write_json
from simulation.experiment import (
    ExperimentConfig,
    ExperimentReportBuilder,
    ExperimentResult,
    RunConfig,
)

# ---------------------------------------------------------------------------
# Approval Status
# ---------------------------------------------------------------------------


class ApprovalStatus(Enum):
    """Immutable approval states for experiment records."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"

    def __str__(self) -> str:
        return self.value


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExperimentRecord:
    """Immutable record of a single experiment execution.

    Each record is created once at registration time and never modified.
    Only the *approval_status* and *notes* may be updated later via
    dedicated workflow methods.
    """

    experiment_id: str
    experiment_name: str
    timestamp: str
    git_commit: str
    framework_version: str
    baseline_config: dict[str, Any]
    candidate_config: dict[str, Any]
    cutoff_date: str
    evaluation_horizon: int
    metrics_summary: dict[str, Any] | None = None
    recommendation: str = ""
    approval_status: str = "PENDING"
    notes: str = ""
    tags: tuple[str, ...] = ()
    machine_dict: dict[str, Any] = field(default_factory=dict)
    human_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "experiment_name": self.experiment_name,
            "timestamp": self.timestamp,
            "git_commit": self.git_commit,
            "framework_version": self.framework_version,
            "baseline_config": self.baseline_config,
            "candidate_config": self.candidate_config,
            "cutoff_date": self.cutoff_date,
            "evaluation_horizon": self.evaluation_horizon,
            "metrics_summary": self.metrics_summary,
            "recommendation": self.recommendation,
            "approval_status": self.approval_status,
            "notes": self.notes,
            "tags": list(self.tags),
            "machine_dict": self.machine_dict,
            "human_summary": self.human_summary,
        }


# ---------------------------------------------------------------------------
# Deterministic ID generation
# ---------------------------------------------------------------------------

_FRAMEWORK_VERSION = "0.1.0"


def _compute_experiment_id(
    config: ExperimentConfig,
    git_commit: str,
    framework_version: str = _FRAMEWORK_VERSION,
) -> str:
    """Deterministic SHA-256 experiment ID from configuration alone.

    Same inputs  →  same ID, on any machine, at any time.
    """
    raw = (
        f"{config.experiment_name}|{config.cutoff_date}"
        f"|{config.baseline.name}|{config.baseline.horizon}"
        f"|{config.candidate.name}|{config.candidate.horizon}"
        f"|{git_commit}|{framework_version}"
    )
    return "exp_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Report builder (lightweight — delegates to ExperimentReportBuilder)
# ---------------------------------------------------------------------------


def _build_human_summary(result: ExperimentResult) -> str:
    """Generate the human-readable summary text for a record."""
    report = ExperimentReportBuilder.build(result)
    return report.human_text


def _extract_metrics_summary(result: ExperimentResult) -> dict[str, Any] | None:
    """Extract a concise metrics summary from an experiment result."""
    if result.comparison is None:
        return None
    c = result.comparison
    return {
        "directional_accuracy_delta": c.directional_accuracy_delta,
        "macro_precision_delta": c.macro_precision_delta,
        "macro_recall_delta": c.macro_recall_delta,
        "coverage_delta": c.coverage_delta,
        "abstention_rate_delta": c.abstention_rate_delta,
        "strong_error_rate_delta": c.strong_error_rate_delta,
        "ece_delta": c.ece_delta,
        "total_decisions_changed": c.total_decisions_changed,
        "total_decisions_improved": c.total_decisions_improved,
        "total_decisions_degraded": c.total_decisions_degraded,
    }


def _run_config_to_dict(cfg: RunConfig) -> dict[str, Any]:
    return {
        "name": cfg.name,
        "horizon": cfg.horizon,
        "max_workers": cfg.max_workers,
        "knowledge_dir": str(cfg.knowledge_dir) if cfg.knowledge_dir else None,
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ExperimentRegistry:
    """File-based, deterministic institutional experiment registry.

    Stores all experiment records in a single JSON file at
    *registry_path*.  Thread-safe via atomic writes.

    Usage::

        registry = ExperimentRegistry()
        record = registry.register(result, git_commit="abc123")
        registry.approve(record.experiment_id, "Approved for deployment.")
    """

    def __init__(
        self,
        registry_path: str | Path | None = None,
        framework_version: str = _FRAMEWORK_VERSION,
    ):
        self._path = Path(
            registry_path
            or Path("data") / "experiments" / "registry" / "registry.json"
        )
        self._version = framework_version
        self._records: dict[str, ExperimentRecord] = {}
        self._load()

    # -- persistence ---------------------------------------------------------

    def _load(self) -> None:
        """Load records from disk."""
        if not self._path.exists():
            self._records = {}
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self._records = {}
                for item in data:
                    rec = self._record_from_dict(item)
                    self._records[rec.experiment_id] = rec
            elif isinstance(data, dict):
                self._records = {}
                for item in data.get("records", []):
                    rec = self._record_from_dict(item)
                    self._records[rec.experiment_id] = rec
            else:
                self._records = {}
        except (json.JSONDecodeError, KeyError, TypeError):
            self._records = {}

    def _save(self) -> None:
        """Atomically persist all records to disk."""
        payload = [r.to_dict() for r in self._sorted_records()]
        atomic_write_json(self._path, payload, default=str)

    def _sorted_records(self) -> list[ExperimentRecord]:
        return sorted(
            self._records.values(),
            key=lambda r: r.timestamp,
            reverse=True,
        )

    @staticmethod
    def _record_from_dict(d: dict[str, Any]) -> ExperimentRecord:
        tags = tuple(d.get("tags", []) or [])
        return ExperimentRecord(
            experiment_id=d["experiment_id"],
            experiment_name=d["experiment_name"],
            timestamp=d["timestamp"],
            git_commit=d["git_commit"],
            framework_version=d.get("framework_version", _FRAMEWORK_VERSION),
            baseline_config=d.get("baseline_config", {}),
            candidate_config=d.get("candidate_config", {}),
            cutoff_date=d.get("cutoff_date", ""),
            evaluation_horizon=d.get("evaluation_horizon", 0),
            metrics_summary=d.get("metrics_summary"),
            recommendation=d.get("recommendation", ""),
            approval_status=d.get("approval_status", "PENDING"),
            notes=d.get("notes", ""),
            tags=tags,
            machine_dict=d.get("machine_dict", {}),
            human_summary=d.get("human_summary", ""),
        )

    # -- registration -------------------------------------------------------

    def register(
        self,
        result: ExperimentResult,
        git_commit: str,
        recommendation: str = "",
        notes: str = "",
        tags: tuple[str, ...] = (),
        timestamp: str | None = None,
    ) -> ExperimentRecord:
        """Create and persist an immutable experiment record.

        Parameters
        ----------
        result:
            The ExperimentResult from a completed experiment run.
        git_commit:
            Git commit hash at the time of execution.
        recommendation:
            Free-text recommendation (e.g. "Proceed with candidate").
        notes:
            Free-text notes for this execution.
        tags:
            Optional searchable tags (e.g. ``("cpi", "us10y")``).
        timestamp:
            ISO-8601 timestamp.  Defaults to current UTC time.

        Returns
        -------
        ExperimentRecord
            The newly created record (already persisted).
        """
        experiment_id = _compute_experiment_id(
            result.config, git_commit, self._version
        )

        if experiment_id in self._records:
            return self._records[experiment_id]

        ts = timestamp or datetime.now(timezone.utc).isoformat()

        config = result.config
        horizon = max(config.baseline.horizon, config.candidate.horizon)

        record = ExperimentRecord(
            experiment_id=experiment_id,
            experiment_name=config.experiment_name,
            timestamp=ts,
            git_commit=git_commit,
            framework_version=self._version,
            baseline_config=_run_config_to_dict(config.baseline),
            candidate_config=_run_config_to_dict(config.candidate),
            cutoff_date=config.cutoff_date,
            evaluation_horizon=horizon,
            metrics_summary=_extract_metrics_summary(result),
            recommendation=recommendation,
            approval_status="PENDING",
            notes=notes,
            tags=tags,
            machine_dict=result.to_dict(),
            human_summary=_build_human_summary(result),
        )

        self._records[experiment_id] = record
        self._save()
        return record

    # -- retrieval -----------------------------------------------------------

    def get(self, experiment_id: str) -> ExperimentRecord | None:
        """Retrieve a single record by ID."""
        return self._records.get(experiment_id)

    def list(self) -> list[ExperimentRecord]:
        """Return all records, newest first."""
        return self._sorted_records()

    def latest(self) -> ExperimentRecord | None:
        """Return the most recently registered experiment."""
        sorted_records = self._sorted_records()
        return sorted_records[0] if sorted_records else None

    def latest_approved(self) -> ExperimentRecord | None:
        """Return the most recent APPROVED experiment."""
        approved = [
            r
            for r in self._sorted_records()
            if r.approval_status == "APPROVED"
        ]
        return approved[0] if approved else None

    # -- search --------------------------------------------------------------

    def find_by_name(self, name: str) -> list[ExperimentRecord]:
        """Find all records with the given experiment name."""
        return [
            r for r in self._sorted_records() if r.experiment_name == name
        ]

    def find_by_tag(self, tag: str) -> list[ExperimentRecord]:
        """Find all records containing the given tag."""
        return [
            r for r in self._sorted_records() if tag in r.tags
        ]

    def find_by_commit(self, commit: str) -> list[ExperimentRecord]:
        """Find all records created at the given git commit."""
        return [
            r for r in self._sorted_records() if r.git_commit == commit
        ]

    def compare_two(
        self,
        id_a: str,
        id_b: str,
    ) -> dict[str, Any]:
        """Produce a side-by-side comparison of two records.

        Returns
        -------
        dict
            Machine-readable comparison with shared fields and deltas.
        """
        a = self.get(id_a)
        b = self.get(id_b)
        if a is None or b is None:
            missing = "a" if a is None else "b"
            return {"error": f"Record {missing} not found"}

        def _delta(
            va: float | None, vb: float | None
        ) -> float | None:
            if va is not None and vb is not None:
                return vb - va
            return None

        a_summary = a.metrics_summary or {}
        b_summary = b.metrics_summary or {}

        return {
            "id_a": id_a,
            "id_b": id_b,
            "name_a": a.experiment_name,
            "name_b": b.experiment_name,
            "cutoff_a": a.cutoff_date,
            "cutoff_b": b.cutoff_date,
            "horizon_a": a.evaluation_horizon,
            "horizon_b": b.evaluation_horizon,
            "timestamp_a": a.timestamp,
            "timestamp_b": b.timestamp,
            "approval_a": a.approval_status,
            "approval_b": b.approval_status,
            "baseline_a": a.baseline_config.get("name", ""),
            "baseline_b": b.baseline_config.get("name", ""),
            "candidate_a": a.candidate_config.get("name", ""),
            "candidate_b": b.candidate_config.get("name", ""),
            "directional_accuracy_delta": _delta(
                a_summary.get("directional_accuracy_delta"),
                b_summary.get("directional_accuracy_delta"),
            ),
            "ece_delta": _delta(
                a_summary.get("ece_delta"),
                b_summary.get("ece_delta"),
            ),
            "total_decisions_changed_a": a_summary.get("total_decisions_changed", 0),
            "total_decisions_changed_b": b_summary.get("total_decisions_changed", 0),
        }

    # -- approval workflow ---------------------------------------------------

    def _update_status(
        self,
        experiment_id: str,
        new_status: str,
        notes: str = "",
    ) -> ExperimentRecord | None:
        """Internal: set approval status and append notes."""
        record = self.get(experiment_id)
        if record is None:
            return None

        # Build updated notes — append, never overwrite
        updated_notes = record.notes
        if notes:
            ts = datetime.now(timezone.utc).isoformat()
            prefix = f"[{ts}] {new_status}: "
            if updated_notes:
                updated_notes += "\n" + prefix + notes
            else:
                updated_notes = prefix + notes

        updated = ExperimentRecord(
            experiment_id=record.experiment_id,
            experiment_name=record.experiment_name,
            timestamp=record.timestamp,
            git_commit=record.git_commit,
            framework_version=record.framework_version,
            baseline_config=record.baseline_config,
            candidate_config=record.candidate_config,
            cutoff_date=record.cutoff_date,
            evaluation_horizon=record.evaluation_horizon,
            metrics_summary=record.metrics_summary,
            recommendation=record.recommendation,
            approval_status=new_status,
            notes=updated_notes,
            tags=record.tags,
            machine_dict=record.machine_dict,
            human_summary=record.human_summary,
        )
        self._records[experiment_id] = updated
        self._save()
        return updated

    def approve(
        self, experiment_id: str, notes: str = ""
    ) -> ExperimentRecord | None:
        """Mark an experiment as APPROVED."""
        return self._update_status(experiment_id, "APPROVED", notes)

    def reject(
        self, experiment_id: str, notes: str = ""
    ) -> ExperimentRecord | None:
        """Mark an experiment as REJECTED."""
        return self._update_status(experiment_id, "REJECTED", notes)

    def supersede(
        self, experiment_id: str, notes: str = ""
    ) -> ExperimentRecord | None:
        """Mark an experiment as SUPERSEDED (replaced by a later one)."""
        return self._update_status(experiment_id, "SUPERSEDED", notes)

    # -- reporting -----------------------------------------------------------

    def summary_text(self) -> str:
        """Human-readable summary of the entire registry."""
        records = self._sorted_records()
        lines: list[str] = []
        _w = lines.append

        _w("=" * 72)
        _w(f"  Experiment Registry Summary")
        _w(f"  Total experiments: {len(records)}")
        _w(f"  Registry path:     {self._path}")
        _w("=" * 72)

        for i, r in enumerate(records, 1):
            _w("")
            _w(f"  [{i}] {r.experiment_name}")
            _w(f"       ID:      {r.experiment_id}")
            _w(f"       Date:    {r.timestamp[:19]}")
            _w(f"       Cutoff:  {r.cutoff_date}")
            _w(f"       Horizon: {r.evaluation_horizon} weeks")
            _w(f"       Status:  {r.approval_status}")
            _w(f"       Tags:    {', '.join(r.tags) if r.tags else '(none)'}")
            if r.recommendation:
                _w(f"       Rec:     {r.recommendation}")

        _w("")
        _w("=" * 72)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Machine-readable registry dump."""
        return {
            "registry_path": str(self._path),
            "framework_version": self._version,
            "experiment_count": len(self._records),
            "records": [r.to_dict() for r in self._sorted_records()],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)
