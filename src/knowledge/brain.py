from pathlib import Path
import sys


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge.rules import RULES
from knowledge.memory import Memory


class EconomicBrain:

    def __init__(self, memory: Memory | None = None):
        self.memory = memory or Memory()

    def analyze(self, event, context=None):
        context = context or {}
        if event == "CPI" and context:
            return self._analyze_cpi(context)

        return RULES.get(event, "Unknown Event")

    def _analyze_cpi(self, context):
        cpi_pressure = context.get("cpi_pressure")
        horizon_days = int(context.get("horizon_days", 20))

        if not cpi_pressure:
            return {
                "status": "missing_context",
                "event_type": "CPI",
                "missing": ["cpi_pressure"],
            }

        memory = self.memory.load()
        summary = memory.get("cpi_gold_summary_v1")
        if not summary:
            return {
                "status": "missing_knowledge",
                "event_type": "CPI",
                "required_knowledge": "cpi_gold_summary_v1",
            }

        for record in summary.get("records", []):
            condition = record.get("condition", {})
            if (
                condition.get("cpi_pressure") == cpi_pressure
                and int(record.get("horizon_days")) == horizon_days
            ):
                return {
                    "status": "knowledge_found",
                    "event_type": "CPI",
                    "asset": "GOLD",
                    "knowledge_id": record["knowledge_id"],
                    "horizon_days": horizon_days,
                    "sample_count": record["sample_count"],
                    "bias": record["bias"],
                    "confidence": record["confidence"],
                    "positive_return_rate_pct": record["positive_return_rate_pct"],
                    "average_return_pct": record["average_return_pct"],
                    "explanation": record["explanation"],
                }

        return {
            "status": "knowledge_not_found",
            "event_type": "CPI",
            "cpi_pressure": cpi_pressure,
            "horizon_days": horizon_days,
        }


if __name__ == "__main__":

    brain = EconomicBrain()

    print(
        brain.analyze(
            "CPI",
            {
                "cpi_pressure": "inflation_pressure_up",
                "horizon_days": 20,
            },
        )
    )

    print(brain.analyze("NFP"))
