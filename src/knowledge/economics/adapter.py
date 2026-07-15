from knowledge.economics.regime import EconomicRegime
from knowledge.economics.state import EconomicState
from knowledge.evidence.evidence import Evidence


class EconomicEvidenceAdapter:
    def regime_to_evidence(self, regime: EconomicRegime) -> Evidence:
        regime_label = regime.label or regime.regime_type
        return Evidence(
            evidence_id=f"econ_{regime.regime_id}",
            source_node_id=f"econ_regime_{regime.regime_type}",
            event_type="ECONOMIC",
            condition={"regime": regime.regime_type},
            horizon_days=0,
            sample_count=1,
            average_return_pct=0.0,
            confidence=regime.confidence,
            bias="neutral",
            explanation=(
                f"Economic regime '{regime_label}' active from {regime.start_date}"
                + (f" to {regime.end_date}" if regime.end_date else " (ongoing)")
                + f": {regime.description}"
            ),
            metadata={
                "regime_id": regime.regime_id,
                "regime_type": regime.regime_type,
                "start_date": regime.start_date,
                "end_date": regime.end_date,
                "indicators": regime.indicators,
            },
        )

    def regimes_at_date(
        self,
        date: str,
        states: list[EconomicState],
    ) -> list[EconomicRegime]:
        matched = [s for s in states if s.date == date]
        regimes: list[EconomicRegime] = []
        seen: set[str] = set()
        for state in matched:
            for rid in state.regime_ids:
                if rid not in seen:
                    regimes.append(
                        EconomicRegime(
                            regime_id=f"econ_{rid}_{date}",
                            regime_type=rid,
                            label=rid.title(),
                            description=f"Economic regime: {rid}",
                            start_date=date,
                            confidence=1.0,
                        )
                    )
                    seen.add(rid)
        return regimes

    def nearest_state(
        self,
        date: str,
        states: list[EconomicState],
    ) -> EconomicState | None:
        if not states:
            return None
        target = date
        best = min(
            states,
            key=lambda s: abs(self._date_diff(s.date, target)),
        )
        return best

    @staticmethod
    def _date_diff(a: str, b: str) -> int:
        try:
            from datetime import date as date_type
            da = date_type.fromisoformat(a)
            db = date_type.fromisoformat(b)
            return abs((da - db).days)
        except (ValueError, TypeError):
            return abs(len(a) - len(b))
