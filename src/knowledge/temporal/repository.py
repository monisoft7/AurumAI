import json
from pathlib import Path
from typing import Any

from knowledge.temporal.context import TimeContext
from knowledge.temporal.period import TimePeriod
from knowledge.temporal.state import TemporalState
from knowledge.temporal.indexer import TemporalIndexer


class TemporalRepository:
    def save_index(self, indexer: TemporalIndexer, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "context": {
                "calendar": indexer.context.calendar,
                "timezone": indexer.context.timezone,
                "frequency": indexer.context.frequency,
                "business_calendar": indexer.context.business_calendar,
                "metadata": indexer.context.metadata,
            },
            "entries": [
                {
                    "state_id": s.state_id,
                    "date": s.date,
                    "source_type": s.source_type,
                    "source_id": s.source_id,
                    "tags": list(s.tags),
                    "metadata": s.metadata,
                }
                for s in indexer._ensure_sorted()
            ],
        }
        path.write_text(json.dumps(payload, indent=2))

    def load_index(self, path: Path) -> TemporalIndexer:
        payload = json.loads(path.read_text())
        ctx_data = payload.get("context", {})
        context = TimeContext(
            calendar=ctx_data.get("calendar", "calendar"),
            timezone=ctx_data.get("timezone", "UTC"),
            frequency=ctx_data.get("frequency", "daily"),
            business_calendar=ctx_data.get("business_calendar"),
            metadata=ctx_data.get("metadata", {}),
        )
        indexer = TemporalIndexer(context)
        for e in payload.get("entries", []):
            state = TemporalState(
                state_id=e["state_id"],
                date=e.get("date", ""),
                source_type=e.get("source_type", ""),
                source_id=e.get("source_id", ""),
                tags=tuple(e.get("tags", [])),
                metadata=e.get("metadata", {}),
            )
            indexer.index(state)
        return indexer

    def save_period(self, period: TimePeriod, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "period_id": period.period_id,
            "start_date": period.start_date,
            "end_date": period.end_date,
            "period_type": period.period_type,
            "inclusive_start": period.inclusive_start,
            "inclusive_end": period.inclusive_end,
            "label": period.label,
            "metadata": period.metadata,
        }
        path.write_text(json.dumps(payload, indent=2))

    def load_period(self, path: Path) -> TimePeriod:
        payload = json.loads(path.read_text())
        return TimePeriod(
            period_id=payload["period_id"],
            start_date=payload.get("start_date", ""),
            end_date=payload.get("end_date", ""),
            period_type=payload.get("period_type", "custom"),
            inclusive_start=payload.get("inclusive_start", True),
            inclusive_end=payload.get("inclusive_end", True),
            label=payload.get("label", ""),
            metadata=payload.get("metadata", {}),
        )
