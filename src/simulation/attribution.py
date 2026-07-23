from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulation.models import EventRunResult


@dataclass(frozen=True)
class AttributionPerformanceRecord:
    event_type: str
    appearances: int
    weighted_contribution: float
    correct_count: int
    incorrect_count: int
    weighted_accuracy: float
    avg_contribution: float


@dataclass(frozen=True)
class AttributionPerformanceReport:
    records: tuple[AttributionPerformanceRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "records": [
                {
                    "event_type": r.event_type,
                    "appearances": r.appearances,
                    "weighted_contribution": round(r.weighted_contribution, 6),
                    "correct_count": r.correct_count,
                    "incorrect_count": r.incorrect_count,
                    "weighted_accuracy": round(r.weighted_accuracy, 6),
                    "avg_contribution": round(r.avg_contribution, 6),
                }
                for r in self.records
            ]
        }

    def format_table(self) -> str:
        lines = [
            f"{'Event':<20} {'Accuracy':>12} {'Avg Contribution':>18}",
            f"{'-----':<20} {'--------':>12} {'----------------':>18}",
        ]
        for r in self.records:
            acc = f"{r.weighted_accuracy * 100:.1f}%"
            avg = f"{r.avg_contribution * 100:.0f}%"
            lines.append(f"{r.event_type:<20} {acc:>12} {avg:>18}")
        return "\n".join(lines)


class AttributionPerformanceAggregator:
    """Pure aggregation of per-experiment attribution data.

    Takes a sequence of |EventRunResult| objects (each with
    ``decision_correct`` and ``attribution`` populated) and computes
    per-event-type performance statistics.
    """

    def aggregate(
        self, results: tuple[EventRunResult, ...]
    ) -> AttributionPerformanceReport:
        scored = [r for r in results if r.decision_correct is not None and r.attribution]

        by_type: dict[str, dict[str, float | int]] = {}
        for r in scored:
            for et, contrib in r.attribution.items():
                entry = by_type.setdefault(et, {
                    "appearances": 0,
                    "weighted_contribution": 0.0,
                    "correct_weight": 0.0,
                    "total_weight": 0.0,
                })
                entry["appearances"] += 1
                entry["weighted_contribution"] += contrib
                entry["total_weight"] += contrib
                if r.decision_correct:
                    entry["correct_weight"] += contrib

        records: list[AttributionPerformanceRecord] = []
        for et in sorted(by_type.keys()):
            entry = by_type[et]
            apps = entry["appearances"]
            wc = entry["weighted_contribution"]
            tw = entry["total_weight"]
            cw = entry["correct_weight"]
            correct_count = sum(
                1 for r in scored if r.decision_correct and et in r.attribution
            )
            incorrect_count = apps - correct_count
            weighted_acc = cw / tw if tw > 0 else 0.0
            avg_contrib = wc / apps if apps > 0 else 0.0

            records.append(AttributionPerformanceRecord(
                event_type=et,
                appearances=apps,
                weighted_contribution=wc,
                correct_count=correct_count,
                incorrect_count=incorrect_count,
                weighted_accuracy=weighted_acc,
                avg_contribution=avg_contrib,
            ))

        records.sort(key=lambda r: r.avg_contribution, reverse=True)

        return AttributionPerformanceReport(records=tuple(records))
