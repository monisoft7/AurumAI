from pathlib import Path
import sys


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge.rules import RULES
from knowledge.memory import Memory


_DEFAULT_EVENT_REGISTRY: dict[str, dict[str, object]] = {
    "CPI": {
        "knowledge_version": "cpi_gold_summary_v1",
        "condition_columns": ["cpi_pressure"],
    },
}


class EconomicBrain:

    def __init__(
        self,
        memory: Memory | None = None,
        event_registry: dict[str, dict[str, object]] | None = None,
    ):
        self.memory = memory or Memory()
        self._registry = {**_DEFAULT_EVENT_REGISTRY, **(event_registry or {})}

    def analyze(self, event, context=None):
        context = context or {}

        if not context:
            return RULES.get(event, "Unknown Event")

        event_config = self._registry.get(event)
        if not event_config:
            return RULES.get(event, "Unknown Event")

        condition_columns = event_config.get("condition_columns", [])
        missing = [col for col in condition_columns if context.get(col) is None]
        if missing:
            return {
                "status": "missing_context",
                "event_type": event,
                "missing": missing,
            }

        return self._analyze_event(event, context, event_config)

    def _analyze_event(self, event, context, event_config):
        knowledge_version = event_config.get("knowledge_version")
        horizon_days = int(context.get("horizon_days", 20))

        memory = self.memory.load()
        summary = memory.get(knowledge_version)
        if not summary:
            return {
                "status": "missing_knowledge",
                "event_type": event,
                "required_knowledge": knowledge_version,
            }

        for record in summary.get("records", []):
            condition = record.get("condition", {})
            match = all(
                str(context.get(k)) == str(v)
                for k, v in condition.items()
            )
            if match and int(record.get("horizon_days")) == horizon_days:
                return {
                    "status": "knowledge_found",
                    "event_type": event,
                    "asset": record.get("asset", "GOLD"),
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
            "event_type": event,
            **context,
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
