from datetime import date as date_type

from knowledge.temporal.state import TemporalState
from knowledge.temporal.indexer import TemporalIndexer
from knowledge.temporal.period import TimePeriod
from knowledge.evidence.evidence import Evidence


class TemporalEvidenceAdapter:
    def state_to_evidence(self, state: TemporalState) -> Evidence:
        return Evidence(
            evidence_id=f"tmp_{state.state_id}",
            source_node_id=f"temporal_{state.source_type}_{state.source_id}",
            event_type="TEMPORAL",
            condition={"source_type": state.source_type, "date": state.date},
            horizon_days=0,
            sample_count=1,
            average_return_pct=0.0,
            confidence=1.0,
            bias="neutral",
            explanation=(
                f"{state.source_type.capitalize()} '{state.source_id}' "
                f"at date {state.date}"
            ),
            metadata={
                "temporal_state_id": state.state_id,
                "date": state.date,
                "source_type": state.source_type,
                "source_id": state.source_id,
                "tags": list(state.tags),
                "original_metadata": dict(state.metadata),
            },
        )

    def indexer_to_evidence(
        self,
        indexer: TemporalIndexer,
        max_entries: int = 100,
    ) -> list[Evidence]:
        result: list[Evidence] = []
        for state in indexer._ensure_sorted():
            if len(result) >= max_entries:
                break
            result.append(self.state_to_evidence(state))
        return result

    def query_to_evidence(
        self,
        states: list[TemporalState],
    ) -> list[Evidence]:
        return [self.state_to_evidence(s) for s in states]

    @staticmethod
    def period_summary_evidence(
        period: TimePeriod,
        states: list[TemporalState],
    ) -> Evidence:
        source_types: dict[str, int] = {}
        for s in states:
            source_types[s.source_type] = source_types.get(s.source_type, 0) + 1

        date_range_str = f"{period.start_date} to {period.end_date}"
        summary = (
            f"Period '{period.label or period.period_id}' "
            f"({date_range_str}): {len(states)} temporal entries "
            f"across {len(source_types)} source types"
        )
        return Evidence(
            evidence_id=f"tmp_period_{period.period_id}",
            source_node_id=f"temporal_period_{period.period_id}",
            event_type="TEMPORAL_PERIOD",
            condition={"period_id": period.period_id},
            horizon_days=0,
            sample_count=len(states),
            average_return_pct=0.0,
            confidence=1.0,
            bias="neutral",
            explanation=summary,
            metadata={
                "period_id": period.period_id,
                "start_date": period.start_date,
                "end_date": period.end_date,
                "entry_count": len(states),
                "source_type_breakdown": source_types,
            },
        )

    @staticmethod
    def date_range_evidence(
        indexer: TemporalIndexer,
        label: str = "temporal snapshot",
    ) -> Evidence:
        dr = indexer.date_range()
        if dr is None:
            return Evidence(
                evidence_id="tmp_empty_range",
                source_node_id="temporal_range",
                event_type="TEMPORAL_RANGE",
                condition={},
                horizon_days=0,
                sample_count=0,
                average_return_pct=0.0,
                confidence=1.0,
                bias="neutral",
                explanation="No temporal entries indexed.",
                metadata={"label": label, "entry_count": 0},
            )
        return Evidence(
            evidence_id=f"tmp_range_{dr[0]}_{dr[1]}",
            source_node_id="temporal_range",
            event_type="TEMPORAL_RANGE",
            condition={"earliest": dr[0], "latest": dr[1]},
            horizon_days=0,
            sample_count=indexer.entry_count(),
            average_return_pct=0.0,
            confidence=1.0,
            bias="neutral",
            explanation=(
                f"Temporal range: {dr[0]} to {dr[1]} "
                f"({indexer.entry_count()} entries)"
            ),
            metadata={
                "label": label,
                "earliest_date": dr[0],
                "latest_date": dr[1],
                "entry_count": indexer.entry_count(),
            },
        )
