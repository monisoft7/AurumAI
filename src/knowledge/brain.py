from pathlib import Path
import sys
from typing import TYPE_CHECKING


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge.rules import RULES
from knowledge.memory import Memory

if TYPE_CHECKING:
    from knowledge.events.base import MacroEvent


def _build_registry(
    events: dict[str, type["MacroEvent"]] | None,
    event_registry: dict[str, dict[str, object]] | None,
) -> dict[str, dict[str, object]]:
    """Merge MacroEvent-derived metadata with optional hand-written overrides.

    *events* maps event_type → MacroEvent subclass.  Metadata is read
    from the class itself (knowledge_version, condition_columns).

    *event_registry* is the legacy dict-based format.  When both are
    provided, *events* is authoritative and *event_registry* augments
    it (for event types that don't have a MacroEvent class yet).

    Returns a normalised dict[str, dict] for internal lookup.
    """
    merged: dict[str, dict[str, object]] = {}

    if events is not None:
        for event_type, event_cls in events.items():
            merged[event_type] = {
                "knowledge_version": event_cls.knowledge_version,
                "condition_columns": list(event_cls.condition_columns),
            }

    if event_registry is not None:
        for key, val in event_registry.items():
            if key not in merged:
                merged[key] = dict(val)

    return merged


class EconomicBrain:

    def __init__(
        self,
        memory: Memory | None = None,
        events: dict[str, type["MacroEvent"]] | None = None,
        event_registry: dict[str, dict[str, object]] | None = None,
    ):
        self.memory = memory or Memory()
        self._registry = _build_registry(events, event_registry)

        # Register CPIEvent by default if no events provided
        if not events and "CPI" not in self._registry:
            from knowledge.events.cpi import CPIEvent
            self._registry["CPI"] = {
                "knowledge_version": CPIEvent.knowledge_version,
                "condition_columns": list(CPIEvent.condition_columns),
            }

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
