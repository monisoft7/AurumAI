import json
from pathlib import Path
from typing import Any

from knowledge._compat import atomic_write_json

from knowledge.economics.regime import EconomicRegime
from knowledge.economics.state import EconomicState
from knowledge.economics.cycle import EconomicCycle


class EconomicRepository:
    def save_regime(self, regime: EconomicRegime, path: Path) -> None:
        payload = {
            "regime_id": regime.regime_id,
            "regime_type": regime.regime_type,
            "label": regime.label,
            "description": regime.description,
            "start_date": regime.start_date,
            "end_date": regime.end_date,
            "confidence": regime.confidence,
            "indicators": regime.indicators,
            "metadata": regime.metadata,
        }
        atomic_write_json(path, payload)

    def load_regime(self, path: Path) -> EconomicRegime:
        payload = json.loads(path.read_text())
        return EconomicRegime(
            regime_id=payload["regime_id"],
            regime_type=payload["regime_type"],
            label=payload.get("label", ""),
            description=payload.get("description", ""),
            start_date=payload.get("start_date", ""),
            end_date=payload.get("end_date"),
            confidence=payload.get("confidence", 0.0),
            indicators=payload.get("indicators", {}),
            metadata=payload.get("metadata", {}),
        )

    def save_state(self, state: EconomicState, path: Path) -> None:
        payload: dict[str, Any] = {
            "state_id": state.state_id,
            "date": state.date,
            "indicators": state.indicators,
            "regime_ids": list(state.regime_ids),
            "metadata": state.metadata,
        }
        atomic_write_json(path, payload)

    def load_state(self, path: Path) -> EconomicState:
        payload = json.loads(path.read_text())
        return EconomicState(
            state_id=payload["state_id"],
            date=payload.get("date", ""),
            indicators=payload.get("indicators", {}),
            regime_ids=tuple(payload.get("regime_ids", [])),
            metadata=payload.get("metadata", {}),
        )

    def save_cycle(self, cycle: EconomicCycle, path: Path) -> None:
        payload: dict[str, Any] = {
            "cycle_id": cycle.cycle_id,
            "start_date": cycle.start_date,
            "end_date": cycle.end_date,
            "regime_ids": list(cycle.regime_ids),
            "transitions": list(cycle.transitions),
            "metadata": cycle.metadata,
            "states": [
                {
                    "state_id": s.state_id,
                    "date": s.date,
                    "indicators": s.indicators,
                    "regime_ids": list(s.regime_ids),
                    "metadata": s.metadata,
                }
                for s in cycle.states
            ],
        }
        atomic_write_json(path, payload)

    def load_cycle(self, path: Path) -> EconomicCycle:
        payload = json.loads(path.read_text())
        states = [
            EconomicState(
                state_id=s["state_id"],
                date=s.get("date", ""),
                indicators=s.get("indicators", {}),
                regime_ids=tuple(s.get("regime_ids", [])),
                metadata=s.get("metadata", {}),
            )
            for s in payload.get("states", [])
        ]
        return EconomicCycle(
            cycle_id=payload["cycle_id"],
            states=tuple(states),
            start_date=payload.get("start_date", ""),
            end_date=payload.get("end_date"),
            regime_ids=tuple(payload.get("regime_ids", [])),
            transitions=tuple(tuple(t) for t in payload.get("transitions", [])),
            metadata=payload.get("metadata", {}),
        )
