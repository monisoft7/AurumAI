"""Institutional Experiment Framework.

Generic comparison framework for running controlled institutional
experiments.  Reuses ChronologicalOOSEngine, OOSSummary, and the
existing decision evaluation policy.

Experiments are configurations, not implementations.
"""

from __future__ import annotations

import dataclasses
import json
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from simulation.economic import (
    compute_economic_summary,
    format_economic_summary,
)
from simulation.historical_replay import (
    ChronologicalOOSEngine,
    ChronologicalOOSResult,
    EventRunResult,
    OOSSummary,
    compute_oos_summary,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunConfig:
    """Configuration for a single experiment arm (baseline or candidate).

    Attributes
    ----------
    name:
        Human-readable label for this arm.
    horizon:
        Forecast horizon in weeks.
    max_workers:
        Parallelism for the underlying pipeline.
    knowledge_dir:
        Directory for training knowledge (lessons).  If *None* a
        temp directory inside the experiment output dir is used.
    """

    name: str
    horizon: int = 12
    max_workers: int = 4
    knowledge_dir: str | Path | None = None
    yield_data_path: str | Path | None = None


@dataclass(frozen=True)
class ExperimentConfig:
    """Top-level experiment configuration.

    Attributes
    ----------
    experiment_name:
        Unique name for this experiment.
    description:
        Free-text description of what is being compared.
    baseline:
        The reference (control) arm configuration.
    candidate:
        The treatment (experimental) arm configuration.
    cutoff_date:
        Shared chronological split date — all events strictly before
        *cutoff_date* are training, all on/after are evaluation.
    """

    experiment_name: str
    cutoff_date: str
    baseline: RunConfig = field(default_factory=lambda: RunConfig(name="baseline"))
    candidate: RunConfig = field(default_factory=lambda: RunConfig(name="candidate"))
    description: str = ""


# ---------------------------------------------------------------------------
# Comparison models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionComparison:
    """Per-event-type decision comparison between baseline and candidate.

    Attributes
    ----------
    event_type:
        Event type key (e.g. ``"CPI"``, ``"US10Y"``).
    total_events:
        Number of evaluation events for this type.
    decisions_changed:
        How many evaluation events had a different decision between
        baseline and candidate.
    decisions_improved:
        Of those changed, how many went from incorrect to correct.
    decisions_degraded:
        Of those changed, how many went from correct to incorrect.
    baseline_correct:
        Number of correct decisions in the baseline arm.
    candidate_correct:
        Number of correct decisions in the candidate arm.
    """

    event_type: str
    total_events: int
    decisions_changed: int
    decisions_improved: int
    decisions_degraded: int
    baseline_correct: int
    candidate_correct: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "total_events": self.total_events,
            "decisions_changed": self.decisions_changed,
            "decisions_improved": self.decisions_improved,
            "decisions_degraded": self.decisions_degraded,
            "baseline_correct": self.baseline_correct,
            "candidate_correct": self.candidate_correct,
        }


@dataclass(frozen=True)
class ComparisonMetrics:
    """Delta metrics comparing candidate to baseline.

    All ``*_delta`` fields are ``candidate - baseline`` so positive
    values favour the candidate.
    """

    directional_accuracy_delta: float | None = None
    macro_precision_delta: float | None = None
    macro_recall_delta: float | None = None
    coverage_delta: float | None = None
    abstention_rate_delta: float | None = None
    strong_error_rate_delta: float | None = None
    ece_delta: float | None = None

    decision_comparisons: tuple[DecisionComparison, ...] = ()
    total_decisions_changed: int = 0
    total_decisions_improved: int = 0
    total_decisions_degraded: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "directional_accuracy_delta": self.directional_accuracy_delta,
            "macro_precision_delta": self.macro_precision_delta,
            "macro_recall_delta": self.macro_recall_delta,
            "coverage_delta": self.coverage_delta,
            "abstention_rate_delta": self.abstention_rate_delta,
            "strong_error_rate_delta": self.strong_error_rate_delta,
            "ece_delta": self.ece_delta,
            "decision_comparisons": [d.to_dict() for d in self.decision_comparisons],
            "total_decisions_changed": self.total_decisions_changed,
            "total_decisions_improved": self.total_decisions_improved,
            "total_decisions_degraded": self.total_decisions_degraded,
        }


# ---------------------------------------------------------------------------
# Experiment Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExperimentResult:
    """Complete result of a single experiment run.

    Attributes
    ----------
    config:
        The experiment configuration used.
    baseline_result:
        ChronologicalOOSResult for the baseline arm.
    candidate_result:
        ChronologicalOOSResult for the candidate arm.
    comparison:
        Computed comparison metrics, or *None* if not yet computed.
    """

    config: ExperimentConfig
    baseline_result: ChronologicalOOSResult
    candidate_result: ChronologicalOOSResult
    comparison: ComparisonMetrics | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "experiment_name": self.config.experiment_name,
            "cutoff_date": self.config.cutoff_date,
            "baseline": {
                "name": self.config.baseline.name,
                "summary": (
                    self.baseline_result.summary.to_dict()
                    if self.baseline_result.summary
                    else None
                ),
                "evaluation_events": len(self.baseline_result.evaluation_results),
            },
            "candidate": {
                "name": self.config.candidate.name,
                "summary": (
                    self.candidate_result.summary.to_dict()
                    if self.candidate_result.summary
                    else None
                ),
                "evaluation_events": len(self.candidate_result.evaluation_results),
            },
        }
        if self.comparison is not None:
            d["comparison"] = self.comparison.to_dict()
        return d


# ---------------------------------------------------------------------------
# Comparator
# ---------------------------------------------------------------------------


class ExperimentComparator:
    """Pure comparison logic — no side effects."""

    @staticmethod
    def compare(
        baseline: ChronologicalOOSResult,
        candidate: ChronologicalOOSResult,
    ) -> ComparisonMetrics:
        """Compute delta metrics between candidate and baseline."""
        b_summary = baseline.summary
        c_summary = candidate.summary

        def _delta(
            b_val: float | None, c_val: float | None
        ) -> float | None:
            if b_val is not None and c_val is not None:
                return c_val - b_val
            return None

        decision_comps = ExperimentComparator._compare_decisions(
            baseline.evaluation_results, candidate.evaluation_results
        )
        total_changed = sum(d.decisions_changed for d in decision_comps)
        total_improved = sum(d.decisions_improved for d in decision_comps)
        total_degraded = sum(d.decisions_degraded for d in decision_comps)

        return ComparisonMetrics(
            directional_accuracy_delta=_delta(
                b_summary.directional_accuracy if b_summary else None,
                c_summary.directional_accuracy if c_summary else None,
            ),
            macro_precision_delta=_delta(
                b_summary.macro_precision if b_summary else None,
                c_summary.macro_precision if c_summary else None,
            ),
            macro_recall_delta=_delta(
                b_summary.macro_recall if b_summary else None,
                c_summary.macro_recall if c_summary else None,
            ),
            coverage_delta=_delta(
                b_summary.coverage if b_summary else None,
                c_summary.coverage if c_summary else None,
            ),
            abstention_rate_delta=_delta(
                b_summary.abstention_rate if b_summary else None,
                c_summary.abstention_rate if c_summary else None,
            ),
            strong_error_rate_delta=_delta(
                b_summary.strong_error_rate if b_summary else None,
                c_summary.strong_error_rate if c_summary else None,
            ),
            ece_delta=_delta(
                b_summary.ece if b_summary else None,
                c_summary.ece if c_summary else None,
            ),
            decision_comparisons=decision_comps,
            total_decisions_changed=total_changed,
            total_decisions_improved=total_improved,
            total_decisions_degraded=total_degraded,
        )

    @staticmethod
    def _compare_decisions(
        baseline_results: tuple[EventRunResult, ...],
        candidate_results: tuple[EventRunResult, ...],
    ) -> tuple[DecisionComparison, ...]:
        """Align evaluation results by event type and compare decisions.

        Handles multiple results per event type (e.g. one per CPI
        release) by aligning and comparing them in order.
        """

        types = sorted(
            set(r.event_type for r in baseline_results)
            | set(r.event_type for r in candidate_results)
        )
        comparisons: list[DecisionComparison] = []

        for event_type in types:
            b_list = [r for r in baseline_results if r.event_type == event_type]
            c_list = [r for r in candidate_results if r.event_type == event_type]

            total = min(len(b_list), len(c_list))
            if total == 0:
                continue

            changed = sum(
                1 for i in range(total)
                if b_list[i].decision != c_list[i].decision
            )
            improved = sum(
                1 for i in range(total)
                if (b_list[i].decision_correct is False)
                and (c_list[i].decision_correct is True)
            )
            degraded = sum(
                1 for i in range(total)
                if (b_list[i].decision_correct is True)
                and (c_list[i].decision_correct is False)
            )
            b_correct = sum(
                1 for i in range(total)
                if b_list[i].decision_correct is True
            )
            c_correct = sum(
                1 for i in range(total)
                if c_list[i].decision_correct is True
            )

            comparisons.append(
                DecisionComparison(
                    event_type=event_type,
                    total_events=total,
                    decisions_changed=changed,
                    decisions_improved=improved,
                    decisions_degraded=degraded,
                    baseline_correct=b_correct,
                    candidate_correct=c_correct,
                )
            )

        return tuple(comparisons)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class ExperimentRunner:
    """Executes both arms of an experiment under identical conditions.

    Composition over modification — delegates to ChronologicalOOSEngine.
    """

    def __init__(
        self,
        config: ExperimentConfig,
        data_dir: str | Path,
        gold_path: str | Path,
        checkpoint_dir: str | None = None,
        output_dir: str | Path | None = None,
    ):
        self._config = config
        self._data_dir = Path(data_dir)
        self._gold_path = Path(gold_path)
        self._checkpoint_dir = checkpoint_dir
        self._output_dir = (
            Path(output_dir) if output_dir else Path(data_dir) / "experiments"
        )

    def run(self) -> ExperimentResult:
        """Execute baseline and candidate then compute comparison."""
        exp_dir = self._output_dir / self._config.experiment_name
        exp_dir.mkdir(parents=True, exist_ok=True)

        # -- baseline -------------------------------------------------------
        b_knowledge = (
            Path(self._config.baseline.knowledge_dir)
            if self._config.baseline.knowledge_dir
            else exp_dir / "knowledge" / self._config.baseline.name
        )
        b_engine = ChronologicalOOSEngine(
            cutoff_date=self._config.cutoff_date,
            data_dir=self._data_dir,
            gold_path=self._gold_path,
            checkpoint_dir=self._checkpoint_dir,
            max_workers=self._config.baseline.max_workers,
            horizon=self._config.baseline.horizon,
            knowledge_dir=b_knowledge,
            yield_data_path=self._config.baseline.yield_data_path,
        )
        baseline_result = b_engine.run()

        # -- candidate ------------------------------------------------------
        c_knowledge = (
            Path(self._config.candidate.knowledge_dir)
            if self._config.candidate.knowledge_dir
            else exp_dir / "knowledge" / self._config.candidate.name
        )
        c_engine = ChronologicalOOSEngine(
            cutoff_date=self._config.cutoff_date,
            data_dir=self._data_dir,
            gold_path=self._gold_path,
            checkpoint_dir=self._checkpoint_dir,
            max_workers=self._config.candidate.max_workers,
            horizon=self._config.candidate.horizon,
            knowledge_dir=c_knowledge,
            yield_data_path=self._config.candidate.yield_data_path,
        )
        candidate_result = c_engine.run()

        # -- comparison -----------------------------------------------------
        comparison = ExperimentComparator.compare(
            baseline_result, candidate_result
        )

        return ExperimentResult(
            config=self._config,
            baseline_result=baseline_result,
            candidate_result=candidate_result,
            comparison=comparison,
        )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


class ExperimentReportBuilder:
    """Build human-readable and machine-readable reports."""

    @staticmethod
    def build(result: ExperimentResult) -> "ExperimentReport":
        human = ExperimentReportBuilder._build_human(result)
        machine = result.to_dict()
        return ExperimentReport(result=result, human_text=human, machine_dict=machine)

    @staticmethod
    def _build_human(result: ExperimentResult) -> str:
        cfg = result.config
        b = result.baseline_result
        c = result.candidate_result
        comp = result.comparison

        lines: list[str] = []
        _w = lines.append

        _w(f"{'=' * 72}")
        _w(f"  Experiment: {cfg.experiment_name}")
        _w(f"  Description: {cfg.description or '(none)'}")
        _w(f"  Cutoff:      {cfg.cutoff_date}")
        _w(f"{'=' * 72}")

        # -- Baseline summary -----------------------------------------------
        _w("")
        _w(f"  --- Baseline: {cfg.baseline.name} ---")
        _w(f"  Horizon:        {cfg.baseline.horizon} weeks")
        _w(f"  Max workers:    {cfg.baseline.max_workers}")
        if b.summary:
            s = b.summary
            _w(f"  Total events:   {s.total_events}")
            _w(f"  Scored events:  {s.scored_events}")
            _w(f"  Abstained:      {s.abstained_events}")
            _w(f"  Directional Acc: {_pct(s.directional_accuracy)}")
            _w(f"  Macro Precision: {_pct(s.macro_precision)}")
            _w(f"  Macro Recall:    {_pct(s.macro_recall)}")
            _w(f"  Coverage:        {_pct(s.coverage)}")
            _w(f"  Abstention Rate: {_pct(s.abstention_rate)}")
            _w(f"  Strong Error:    {_pct(s.strong_error_rate)}")
            _w(f"  ECE:             {_pct(s.ece)}")

        # -- Candidate summary ----------------------------------------------
        _w("")
        _w(f"  --- Candidate: {cfg.candidate.name} ---")
        _w(f"  Horizon:        {cfg.candidate.horizon} weeks")
        _w(f"  Max workers:    {cfg.candidate.max_workers}")
        if c.summary:
            s = c.summary
            _w(f"  Total events:   {s.total_events}")
            _w(f"  Scored events:  {s.scored_events}")
            _w(f"  Abstained:      {s.abstained_events}")
            _w(f"  Directional Acc: {_pct(s.directional_accuracy)}")
            _w(f"  Macro Precision: {_pct(s.macro_precision)}")
            _w(f"  Macro Recall:    {_pct(s.macro_recall)}")
            _w(f"  Coverage:        {_pct(s.coverage)}")
            _w(f"  Abstention Rate: {_pct(s.abstention_rate)}")
            _w(f"  Strong Error:    {_pct(s.strong_error_rate)}")
            _w(f"  ECE:             {_pct(s.ece)}")

        # -- Delta comparison -----------------------------------------------
        _w("")
        _w("  --- Comparison (candidate - baseline) ---")
        if comp:
            _w(f"  Directional Acc Δ: {_sdelta(comp.directional_accuracy_delta)}")
            _w(f"  Macro Precision Δ: {_sdelta(comp.macro_precision_delta)}")
            _w(f"  Macro Recall Δ:    {_sdelta(comp.macro_recall_delta)}")
            _w(f"  Coverage Δ:        {_sdelta(comp.coverage_delta)}")
            _w(f"  Abstention Rate Δ: {_sdelta(comp.abstention_rate_delta)}")
            _w(f"  Strong Error Δ:    {_sdelta(comp.strong_error_rate_delta)}")
            _w(f"  ECE Δ:             {_sdelta(comp.ece_delta)}")
            _w("")
            _w(f"  Decisions changed:  {comp.total_decisions_changed}")
            _w(f"  Decisions improved: {comp.total_decisions_improved}")
            _w(f"  Decisions degraded: {comp.total_decisions_degraded}")
            if comp.decision_comparisons:
                _w("")
                _w("  Per-event-type decision comparison:")
                _w(
                    f"    {'Type':<20} {'Total':>6} {'Chngd':>6}"
                    f" {'Imprv':>6} {'Degrd':>6} {'B_Corr':>6} {'C_Corr':>6}"
                )
                _w("    " + "-" * 62)
                for dc in comp.decision_comparisons:
                    _w(
                        f"    {dc.event_type:<20} {dc.total_events:>6}"
                        f" {dc.decisions_changed:>6} {dc.decisions_improved:>6}"
                        f" {dc.decisions_degraded:>6} {dc.baseline_correct:>6}"
                        f" {dc.candidate_correct:>6}"
                    )

        # -- Economic Validation --------------------------------------------
        if b.summary:
            _w("")
            eco_b = compute_economic_summary(b.evaluation_results)
            _w(format_economic_summary(eco_b, title="Economic Validation (Baseline)"))
        if c.summary:
            _w("")
            eco_c = compute_economic_summary(c.evaluation_results)
            _w(format_economic_summary(eco_c, title="Economic Validation (Candidate)"))

        # -- Errors ---------------------------------------------------------
        if b.errors or c.errors:
            _w("")
            _w("  --- Errors ---")
            for e in b.errors:
                _w(f"  [baseline] {e}")
            for e in c.errors:
                _w(f"  [candidate] {e}")

        _w("")
        _w(f"{'=' * 72}")
        return "\n".join(lines)


@dataclass(frozen=True)
class ExperimentReport:
    """Human-readable text and machine-readable dict."""

    result: ExperimentResult
    human_text: str
    machine_dict: dict[str, Any]

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.machine_dict, indent=indent, default=str)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val:.2%}"


def _sdelta(val: float | None) -> str:
    if val is None:
        return "N/A"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.2%}"
