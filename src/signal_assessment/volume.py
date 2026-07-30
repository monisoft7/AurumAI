from __future__ import annotations

from signal_assessment.contracts import CriterionScore

VOLUME_THRESHOLD: float = 0.5
OI_THRESHOLD_PCT: float = 5.0
ETF_FLOW_THRESHOLD_PCT: float = 1.0


class VolumeFlowConfirmator:
    """Evaluates criterion 5 (volume/flow confirmation) from Meth. §7.

    Checks whether the price move is accompanied by volume spike,
    open interest change, or ETF flow.
    """

    @staticmethod
    def evaluate(
        change_sigma: float = 0.0,
        volume_change_pct: float | None = None,
        open_interest_change_pct: float | None = None,
        etf_flow_change_pct: float | None = None,
        etf_flow_momentum: str = "",
    ) -> CriterionScore:
        confirms: list[bool] = []
        details: list[str] = []

        if volume_change_pct is not None:
            volume_confirmed = volume_change_pct > VOLUME_THRESHOLD * 100
            if volume_change_pct > 50:
                details.append(f"volume surge {volume_change_pct:+.0f}%")
                confirms.append(True)
            elif volume_change_pct > 20:
                details.append(f"volume elevated {volume_change_pct:+.0f}%")
                confirms.append(True)
            else:
                details.append(f"volume normal {volume_change_pct:+.0f}%")
                confirms.append(False)

        if open_interest_change_pct is not None and abs(open_interest_change_pct) > 0.01:
            oi_confirmed = abs(open_interest_change_pct) > OI_THRESHOLD_PCT
            direction = "rising" if open_interest_change_pct > 0 else "falling"
            if oi_confirmed:
                details.append(f"OI {direction} {abs(open_interest_change_pct):.1f}%")
                confirms.append(True)
            else:
                details.append(f"OI {direction} {abs(open_interest_change_pct):.1f}% (below threshold)")

        if etf_flow_change_pct is not None and abs(etf_flow_change_pct) > 0.01:
            etf_confirmed = abs(etf_flow_change_pct) > ETF_FLOW_THRESHOLD_PCT
            direction = "accumulating" if etf_flow_change_pct > 0 else "distributing"
            if etf_confirmed:
                details.append(f"ETF {direction} {etf_flow_change_pct:+.1f}%")
                confirms.append(True)
            else:
                details.append(f"ETF {direction} {etf_flow_change_pct:+.1f}% (below threshold)")

        if etf_flow_momentum and etf_flow_momentum != "stable":
            details.append(f"ETF momentum: {etf_flow_momentum}")
            confirms.append(etf_flow_momentum in ("accumulating", "distributing"))

        if not confirms:
            return CriterionScore(
                criterion="volume_flow",
                score=0.0,
                threshold=VOLUME_THRESHOLD,
                passed=False,
                detail="no volume/flow data available",
            )

        score = sum(1 for c in confirms if c) / len(confirms)
        passed = score >= VOLUME_THRESHOLD
        return CriterionScore(
            criterion="volume_flow",
            score=round(score, 4),
            threshold=VOLUME_THRESHOLD,
            passed=passed,
            detail="; ".join(details),
        )
