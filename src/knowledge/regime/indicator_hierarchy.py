from __future__ import annotations

from typing import Any

from knowledge.graph.graph import KnowledgeGraph
from knowledge.regime.constants import (
    CANONICAL_REGIME_SET,
    NORMAL_GROWTH,
    INFLATIONARY,
    STAGFLATIONARY,
    DEFLATIONARY_CRISIS,
    GEOPOLITICAL_STRESS,
    STRUCTURAL_REGIME_CHANGE,
    REGIME_LABELS,
)
from knowledge.regime.contracts import RegimeIndicator, TriggerLevel

REGIME_INDICATORS: dict[str, dict[str, list[dict[str, Any]]]] = {
    "NORMAL_GROWTH": {
        "dominant": [
            {"indicator": "real_yields_10y_tips", "weight": 0.30, "description": "10-year TIPS yield"},
            {"indicator": "dxy", "weight": 0.25, "description": "US Dollar Index"},
            {"indicator": "gold_etf_flows", "weight": 0.15, "description": "Gold ETF flow momentum"},
            {"indicator": "comex_managed_money_zscore", "weight": 0.10, "description": "COMEX managed money positioning"},
        ],
        "secondary": [
            {"indicator": "gold_mining_supply", "weight": 0.05, "description": "Gold mining supply"},
            {"indicator": "fabrication_demand", "weight": 0.05, "description": "Jewelry/industrial fabrication demand"},
        ],
        "weaker": [
            {"indicator": "geopolitical_risk_index", "weight": 0.03, "description": "GPR index"},
            {"indicator": "central_bank_buying", "weight": 0.02, "description": "Central bank net purchases"},
        ],
    },
    "INFLATIONARY": {
        "dominant": [
            {"indicator": "breakeven_inflation_rate", "weight": 0.25, "description": "BEI (breakeven inflation rate)"},
            {"indicator": "us_fiscal_deficit", "weight": 0.20, "description": "US fiscal deficit / GDP"},
            {"indicator": "fed_credibility_proxy", "weight": 0.15, "description": "Fed credibility proxy (SPF dispersion)"},
            {"indicator": "central_bank_buying", "weight": 0.12, "description": "Central bank net purchases"},
        ],
        "secondary": [
            {"indicator": "gold_etf_flows", "weight": 0.08, "description": "Gold ETF flow momentum"},
            {"indicator": "term_premium", "weight": 0.08, "description": "US 10Y term premium (ACM)"},
            {"indicator": "dxy", "weight": 0.05, "description": "US Dollar Index"},
        ],
        "weaker": [
            {"indicator": "real_yields_10y_tips", "weight": 0.03, "description": "Real yields (unstable beta)"},
            {"indicator": "comex_managed_money_zscore", "weight": 0.02, "description": "COMEX positioning (momentum chase)"},
        ],
    },
    "STAGFLATIONARY": {
        "dominant": [
            {"indicator": "real_yields_10y_tips", "weight": 0.25, "description": "Real yields (deeply negative)"},
            {"indicator": "breakeven_inflation_rate", "weight": 0.20, "description": "BEI"},
            {"indicator": "geopolitical_risk_index", "weight": 0.15, "description": "GPR index"},
            {"indicator": "gold_to_copper_ratio", "weight": 0.10, "description": "Gold/copper ratio (stagflation signal)"},
        ],
        "secondary": [
            {"indicator": "gold_to_sp500_ratio", "weight": 0.08, "description": "Gold/S&P 500 ratio"},
            {"indicator": "us_fiscal_deficit", "weight": 0.07, "description": "US fiscal deficit"},
            {"indicator": "central_bank_buying", "weight": 0.05, "description": "Central bank purchases"},
        ],
        "weaker": [
            {"indicator": "gold_etf_flows", "weight": 0.03, "description": "ETF flows (secondary)"},
            {"indicator": "comex_managed_money_zscore", "weight": 0.02, "description": "COMEX positioning (already positioned)"},
        ],
    },
    "DEFLATIONARY_CRISIS": {
        "dominant": [
            {"indicator": "vix", "weight": 0.20, "description": "VIX volatility index"},
            {"indicator": "usd_liquidity_measures", "weight": 0.18, "description": "Swap spreads, FRA-OIS, Fed balance sheet"},
            {"indicator": "gold_forward_rate", "weight": 0.15, "description": "GOFO (gold forward offered rate)"},
            {"indicator": "geopolitical_risk_index", "weight": 0.12, "description": "GPR index"},
        ],
        "secondary": [
            {"indicator": "central_bank_buying", "weight": 0.10, "description": "Central bank purchases"},
            {"indicator": "real_yields_10y_tips", "weight": 0.08, "description": "Real yields (zero bound)"},
        ],
        "weaker": [
            {"indicator": "gold_etf_flows", "weight": 0.05, "description": "ETF flows (liquidated for cash)"},
            {"indicator": "comex_managed_money_zscore", "weight": 0.02, "description": "COMEX positioning (same)"},
        ],
    },
    "GEOPOLITICAL_STRESS": {
        "dominant": [
            {"indicator": "geopolitical_risk_index", "weight": 0.30, "description": "GPR index"},
            {"indicator": "sanctions_data", "weight": 0.20, "description": "IMF/WB sanctions data"},
            {"indicator": "central_bank_buying", "weight": 0.15, "description": "Central bank purchases (sanctions response)"},
        ],
        "secondary": [
            {"indicator": "gold_to_bitcoin_ratio", "weight": 0.10, "description": "Gold/bitcoin ratio (safe haven proxy)"},
            {"indicator": "usd_reserve_status_proxy", "weight": 0.08, "description": "USD reserve currency status proxy"},
        ],
        "weaker": [
            {"indicator": "real_yields_10y_tips", "weight": 0.05, "description": "Real yields"},
            {"indicator": "dxy", "weight": 0.03, "description": "DXY"},
        ],
    },
    "STRUCTURAL_REGIME_CHANGE": {
        "dominant": [
            {"indicator": "gram_residual", "weight": 0.30, "description": "GRAM unexplained variance"},
            {"indicator": "new_candidate_variables", "weight": 0.25, "description": "Novel candidate drivers"},
            {"indicator": "rolling_coefficient_stability", "weight": 0.15, "description": "Rolling coefficient stability tests"},
        ],
        "secondary": [
            {"indicator": "term_premium", "weight": 0.10, "description": "Term premium (replacement driver)"},
            {"indicator": "central_bank_buying", "weight": 0.08, "description": "CB buying (new structural driver)"},
        ],
        "weaker": [
            {"indicator": "real_yields_10y_tips", "weight": 0.03, "description": "Old regime indicators (decayed)"},
            {"indicator": "dxy", "weight": 0.02, "description": "DXY (unreliable in transition)"},
        ],
    },
}

REGIME_TRIGGER_LEVELS: dict[str, list[dict[str, Any]]] = {
    "NORMAL_GROWTH": [
        {"condition": "CPI > 3% for 2 consecutive months", "target": "INFLATIONARY"},
        {"condition": "GDP < 1% for 2 quarters", "target": "STAGFLATIONARY"},
    ],
    "INFLATIONARY": [
        {"condition": "GDP < 0% + CPI > 4%", "target": "STAGFLATIONARY"},
        {"condition": "CPI < 2% for 3 months", "target": "NORMAL_GROWTH"},
    ],
    "STAGFLATIONARY": [
        {"condition": "GDP < -2% + CPI < 2%", "target": "DEFLATIONARY_CRISIS"},
        {"condition": "CPI < 3% + policy response credible", "target": "INFLATIONARY"},
    ],
    "DEFLATIONARY_CRISIS": [
        {"condition": "CB intervention restores liquidity", "target": "NORMAL_GROWTH"},
        {"condition": "GPR > 200", "target": "GEOPOLITICAL_STRESS"},
    ],
    "GEOPOLITICAL_STRESS": [
        {"condition": "GPR < 100 for 3 months", "target": "NORMAL_GROWTH"},
    ],
    "STRUCTURAL_REGIME_CHANGE": [
        {"condition": "GRAM residual < 1 sigma for 6 months", "target": "NORMAL_GROWTH"},
        {"condition": "New model R-squared > 70% stable", "target": "NORMAL_GROWTH"},
    ],
}


def _query_kr_ids_by_regime(graph: KnowledgeGraph, regime: str) -> list[str]:
    if regime not in CANONICAL_REGIME_SET:
        return []
    node_ids: set[str] = set()
    for node in graph.get_all_nodes():
        regimes = node.properties.get("regimes", [])
        if isinstance(regimes, list) and regime in regimes:
            node_ids.add(node.node_id)
    return sorted(node_ids)


class IndicatorHierarchyGenerator:
    """Generates the ordered indicator hierarchy for a diagnosed regime.

    Matches Meth. §9 specifications: for each regime, outputs the
    ordered list of dominant -> secondary -> weaker indicators with
    associated Knowledge Records sourced from the KnowledgeGraph.
    """

    def generate(
        self,
        regime: str,
        include_krs: bool = True,
        graph: KnowledgeGraph | None = None,
    ) -> dict[str, Any]:
        if regime not in REGIME_INDICATORS:
            return {
                "regime": regime,
                "error": f"Unknown regime: {regime}",
                "indicators": [],
            }

        hierarchy = REGIME_INDICATORS[regime]

        kr_ids: list[str] = []
        if include_krs:
            if graph is not None:
                kr_ids = _query_kr_ids_by_regime(graph, regime)

        indicators: list[RegimeIndicator] = []
        for tier in ("dominant", "secondary", "weaker"):
            for ind in hierarchy.get(tier, []):
                indicators.append(RegimeIndicator(
                    indicator=str(ind["indicator"]),
                    weight=float(ind["weight"]),
                    description=str(ind.get("description", "")),
                    tier=tier,
                    associated_kr_ids=tuple(kr_ids),
                ))

        trigger_levels = [
            TriggerLevel(
                indicator=regime,
                condition=str(t["condition"]),
                target=str(t["target"]),
            )
            for t in REGIME_TRIGGER_LEVELS.get(regime, [])
        ]

        indicator_dicts = [i.to_dict() for i in indicators]
        for d, ri in zip(indicator_dicts, indicators):
            d["associated_krs"] = list(ri.associated_kr_ids)

        return {
            "regime": regime,
            "label": self._label(regime),
            "indicators": indicator_dicts,
            "dominant_count": len(hierarchy.get("dominant", [])),
            "secondary_count": len(hierarchy.get("secondary", [])),
            "weaker_count": len(hierarchy.get("weaker", [])),
            "associated_krs": kr_ids,
            "trigger_levels": trigger_levels,
        }

    def generate_all(
        self,
        include_krs: bool = True,
        graph: KnowledgeGraph | None = None,
    ) -> dict[str, dict[str, Any]]:
        return {
            regime: self.generate(regime, include_krs=include_krs, graph=graph)
            for regime in REGIME_INDICATORS
        }

    def get_trigger_levels(self, regime: str) -> list[TriggerLevel]:
        return [
            TriggerLevel(
                indicator=regime,
                condition=str(t["condition"]),
                target=str(t["target"]),
            )
            for t in REGIME_TRIGGER_LEVELS.get(regime, [])
        ]

    @staticmethod
    def _label(regime: str) -> str:
        return REGIME_LABELS.get(regime, regime)
