from knowledge.cfi.contracts import (
    CentralBankReserveFlowReport,
    ETFFlowMonitor,
    GoldPositioningDashboard,
)
from knowledge.evidence.evidence import Evidence


class CfiEvidenceAdapter:
    def etf_flow_to_evidence(self, flow: ETFFlowMonitor) -> Evidence:
        divergence = " (price/flow divergence)" if flow.price_flow_divergence_flag else ""
        return Evidence(
            evidence_id=f"cfi_etf_{flow.valid_from}",
            source_node_id="cfi_etf_flow_monitor",
            event_type="CFI_ETF",
            condition={"momentum": flow.momentum_assessment},
            horizon_days=28,
            sample_count=len(flow.daily_flows) if flow.daily_flows else 1,
            average_return_pct=0.0,
            confidence=flow.confidence,
            bias=self._momentum_to_bias(flow.momentum_assessment),
            explanation=(
                f"ETF flow momentum: {flow.momentum_assessment}"
                f"{divergence}"
            ),
            metadata={
                "momentum_assessment": flow.momentum_assessment,
                "price_flow_divergence": flow.price_flow_divergence_flag,
                "composition": dict(flow.composition_analysis),
            },
        )

    def cb_reserve_flow_to_evidence(
        self, report: CentralBankReserveFlowReport,
    ) -> Evidence:
        return Evidence(
            evidence_id=f"cfi_cb_reserve_{report.valid_from}",
            source_node_id="cfi_cb_reserve_flow",
            event_type="CFI_CB_RESERVE",
            condition={
                "12m_trend": report.net_official_purchases_12m_trend,
            },
            horizon_days=365,
            sample_count=1,
            average_return_pct=0.0,
            confidence=report.confidence,
            bias=self._cb_trend_to_bias(report.net_official_purchases_12m_trend),
            explanation=(
                f"Central bank net purchases: {report.net_official_purchases_12m:.0f}t "
                f"(12m trend: {report.net_official_purchases_12m_trend})"
            ),
            metadata={
                "net_official_purchases_month": report.net_official_purchases_month,
                "net_official_purchases_12m": report.net_official_purchases_12m,
                "12m_trend": report.net_official_purchases_12m_trend,
                "marginal_buyers": list(report.marginal_buyers),
            },
        )

    def positioning_to_evidence(
        self, dashboard: GoldPositioningDashboard,
    ) -> Evidence:
        return Evidence(
            evidence_id=f"cfi_positioning_{dashboard.valid_from}",
            source_node_id="cfi_gold_positioning",
            event_type="CFI_POSITIONING",
            condition={
                "assessment": dashboard.composite_assessment[:64],
            },
            horizon_days=14,
            sample_count=1,
            average_return_pct=0.0,
            confidence=dashboard.confidence,
            bias="neutral",
            explanation=dashboard.composite_assessment,
            metadata={
                "cot_percentile": dict(dashboard.cot_net_non_commercial),
                "etf_flow": dict(dashboard.etf_flow),
            },
        )

    @staticmethod
    def _momentum_to_bias(momentum: str) -> str:
        if momentum in (
            "accelerating_inflows", "steady_inflows",
        ):
            return "bullish"
        if momentum in (
            "accelerating_outflows", "steady_outflows",
        ):
            return "bearish"
        return "neutral"

    @staticmethod
    def _cb_trend_to_bias(trend: str) -> str:
        if trend == "accelerating":
            return "bullish"
        if trend == "decelerating":
            return "bearish"
        return "neutral"
