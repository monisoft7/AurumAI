from __future__ import annotations

from knowledge.economics.regime import (
    REGIME_HIGH_INFLATION,
    REGIME_LOW_INFLATION,
    REGIME_DEFLATION,
    REGIME_DISINFLATION,
    REGIME_TIGHT_MONETARY,
    REGIME_LOOSE_MONETARY,
    REGIME_RISK_ON,
    REGIME_RISK_OFF,
    REGIME_RECESSION,
    REGIME_EXPANSION,
    REGIME_STAGFLATION,
)
from knowledge.economics.state import EconomicState


_DEFAULT_CONFIG: dict[str, dict[str, float]] = {
    "inflation": {
        "indicator_key": "inflation_cpi_yoy",
        "high_threshold": 3.0,
        "low_positive_threshold": 0.0,
    },
    "monetary": {
        "indicator_key": "interest_rate",
        "neutral_rate": 2.5,
    },
    "growth": {
        "indicator_key": "gdp_growth",
        "expansion_threshold": 2.0,
        "contraction_threshold": 0.0,
    },
    "risk": {
        "risk_indicator_key": "vix",
        "risk_on_threshold": 20.0,
        "risk_off_threshold": 25.0,
    },
    "sentiment": {
        "indicator_key": "consumer_sentiment",
        "risk_on_threshold": 80.0,
        "risk_off_threshold": 60.0,
    },
    "stagflation": {
        "inflation_indicator_key": "inflation_cpi_yoy",
        "growth_indicator_key": "gdp_growth",
        "high_inflation_threshold": 3.0,
        "low_growth_threshold": 1.0,
    },
}


class EconomicClassifier:
    def __init__(self, config: dict[str, dict[str, float]] | None = None):
        self._config = {**_DEFAULT_CONFIG, **(config or {})}

    def classify(self, state: EconomicState) -> tuple[str, ...]:
        regimes: list[str] = []
        indicators = state.indicators

        inf_cfg = self._config.get("inflation", {})
        inf_key = inf_cfg.get("indicator_key", "inflation_cpi_yoy")
        inflation = indicators.get(inf_key)

        if inflation is not None:
            if inflation < inf_cfg.get("low_positive_threshold", 0.0):
                regimes.append(REGIME_DEFLATION)
            elif inflation > inf_cfg.get("high_threshold", 3.0):
                regimes.append(REGIME_HIGH_INFLATION)
            else:
                regimes.append(REGIME_LOW_INFLATION)

        mon_cfg = self._config.get("monetary", {})
        rate_key = mon_cfg.get("indicator_key", "interest_rate")
        rate = indicators.get(rate_key)

        if rate is not None:
            neutral = mon_cfg.get("neutral_rate", 2.5)
            if rate > neutral:
                regimes.append(REGIME_TIGHT_MONETARY)
            elif rate < neutral:
                regimes.append(REGIME_LOOSE_MONETARY)

        growth_cfg = self._config.get("growth", {})
        growth_key = growth_cfg.get("indicator_key", "gdp_growth")
        growth = indicators.get(growth_key)

        if growth is not None:
            if growth >= growth_cfg.get("expansion_threshold", 2.0):
                regimes.append(REGIME_EXPANSION)

        risk_cfg = self._config.get("risk", {})
        risk_key = risk_cfg.get("risk_indicator_key", "vix")
        sent_key = risk_cfg.get("sentiment_indicator_key")
        sent_cfg = self._config.get("sentiment", {})
        sent_indicator_key = sent_cfg.get("indicator_key", "consumer_sentiment")

        vix = indicators.get(risk_key)
        sent = indicators.get(sent_indicator_key)

        if vix is not None:
            if vix < risk_cfg.get("risk_on_threshold", 20.0):
                regimes.append(REGIME_RISK_ON)
            elif vix > risk_cfg.get("risk_off_threshold", 25.0):
                regimes.append(REGIME_RISK_OFF)

        if sent is not None:
            risk_on_sent = sent_cfg.get("risk_on_threshold", 80.0)
            risk_off_sent = sent_cfg.get("risk_off_threshold", 60.0)
            if sent >= risk_on_sent:
                if REGIME_RISK_ON not in regimes:
                    regimes.append(REGIME_RISK_ON)
            elif sent <= risk_off_sent:
                if REGIME_RISK_OFF not in regimes:
                    regimes.append(REGIME_RISK_OFF)

        stag_cfg = self._config.get("stagflation", {})
        stag_inf_key = stag_cfg.get("inflation_indicator_key", inf_key)
        stag_growth_key = stag_cfg.get("growth_indicator_key", growth_key)
        stag_high_inf = stag_cfg.get("high_inflation_threshold", 3.0)
        stag_low_growth = stag_cfg.get("low_growth_threshold", 1.0)

        stag_inflation = indicators.get(stag_inf_key)
        stag_growth = indicators.get(stag_growth_key)

        if stag_inflation is not None and stag_growth is not None:
            if stag_inflation > stag_high_inf and stag_growth < stag_low_growth:
                regimes.append(REGIME_STAGFLATION)

        return tuple(sorted(set(regimes)))

    def classify_sequence(
        self,
        states: list[EconomicState],
    ) -> list[tuple[str, ...]]:
        results: list[tuple[str, ...]] = []
        for i, state in enumerate(states):
            regimes = list(self.classify(state))

            growth_cfg = self._config.get("growth", {})
            growth_key = growth_cfg.get("indicator_key", "gdp_growth")
            growth = state.indicators.get(growth_key)

            if growth is not None and growth < growth_cfg.get("contraction_threshold", 0.0):
                if i >= 1:
                    prev_growth = states[i - 1].indicators.get(growth_key)
                    if prev_growth is not None and prev_growth < 0.0:
                        regimes.append(REGIME_RECESSION)

            inf_cfg = self._config.get("inflation", {})
            inf_key = inf_cfg.get("indicator_key", "inflation_cpi_yoy")
            inflation = state.indicators.get(inf_key)

            if inflation is not None and inflation > 0.0:
                if i >= 1:
                    prev_inflation = states[i - 1].indicators.get(inf_key)
                    if prev_inflation is not None and inflation < prev_inflation:
                        regimes.append(REGIME_DISINFLATION)

            results.append(tuple(sorted(set(regimes))))
        return results

    @property
    def config(self) -> dict[str, dict[str, float]]:
        return dict(self._config)
