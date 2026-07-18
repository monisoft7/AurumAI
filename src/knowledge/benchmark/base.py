from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Metric:
    name: str
    value: float
    unit: str = ""
    description: str = ""

    def __float__(self) -> float:
        return self.value


@dataclass(frozen=True)
class BenchmarkResult:
    benchmark_name: str
    metrics: list[Metric]
    num_passed: int = 0
    num_failed: int = 0
    passed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_name": self.benchmark_name,
            "passed": self.passed,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "metrics": [
                {
                    "name": m.name,
                    "value": round(m.value, 6),
                    "unit": m.unit,
                    "description": m.description,
                }
                for m in self.metrics
            ],
        }


@dataclass
class BenchmarkReport:
    suite_name: str
    results: list[BenchmarkResult] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "timestamp": self.timestamp,
            "num_benchmarks": len(self.results),
            "all_passed": all(r.passed for r in self.results),
            "benchmarks": [r.to_dict() for r in self.results],
        }


class BenchmarkSuite:
    def __init__(self, name: str = "aurumai-institutional"):
        self._name = name
        self._benchmarks: list[Benchmark] = []

    def add(self, benchmark: Benchmark) -> None:
        self._benchmarks.append(benchmark)

    @property
    def benchmarks(self) -> list[Benchmark]:
        return list(self._benchmarks)

    def run(self) -> BenchmarkReport:
        report = BenchmarkReport(suite_name=self._name)
        for b in self._benchmarks:
            result = b.run()
            report.results.append(result)
        return report


class Benchmark:
    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def run(self) -> BenchmarkResult:
        raise NotImplementedError

    def _metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        description: str = "",
    ) -> Metric:
        return Metric(
            name=name,
            value=value,
            unit=unit,
            description=description,
        )

    def _result(
        self,
        metrics: list[Metric],
        thresholds: dict[str, tuple[float, str]] | None = None,
    ) -> BenchmarkResult:
        passed = 0
        failed = 0
        for m in metrics:
            if thresholds and m.name in thresholds:
                threshold, direction = thresholds[m.name]
                if direction == "gte":
                    if m.value >= threshold:
                        passed += 1
                    else:
                        failed += 1
                elif direction == "lte":
                    if m.value <= threshold:
                        passed += 1
                    else:
                        failed += 1
                elif direction == "eq":
                    if m.value == threshold:
                        passed += 1
                    else:
                        failed += 1
            else:
                passed += 1

        return BenchmarkResult(
            benchmark_name=self._name,
            metrics=metrics,
            num_passed=passed,
            num_failed=failed,
            passed=failed == 0,
        )
