from __future__ import annotations

from typing import Any

from pre_market.contracts import AnomalyFlag, OvernightPriceChange

TEMPLATE_VIOLATIONS: list[dict[str, Any]] = [
    {
        "name": "gold_dxy_co_move",
        "description": "Gold and DXY moving in same direction (negative correlation expected)",
        "pair": ("XAU/USD", "DXY"),
        "expected_divergence": True,
    },
    {
        "name": "gold_real_yield_divergence",
        "description": "Gold and real yields moving in same direction (negative correlation expected)",
        "pair": ("XAU/USD", "US10Y Real Yield"),
        "expected_divergence": True,
    },
    {
        "name": "gold_equity_correlation_shift",
        "description": "Gold and equities correlation regime shift detected",
        "pair": ("XAU/USD", "S&P 500 Futures"),
        "expected_divergence": False,
    },
]


class AnomalyDetectionEngine:
    """Flags anomalous market conditions from overnight price changes.

    Detects 2-sigma moves, template violations (e.g. gold/real-yield
    co-move), and diverging signals across instruments.
    """

    SIGMA_THRESHOLD: float = 2.0
    HIGH_SIGMA_THRESHOLD: float = 3.0

    def detect(
        self,
        overnight_changes: list[OvernightPriceChange],
    ) -> list[AnomalyFlag]:
        flags: list[AnomalyFlag] = []

        changes_by_instrument: dict[str, OvernightPriceChange] = {}
        for c in overnight_changes:
            changes_by_instrument[c.instrument] = c

        for c in overnight_changes:
            if abs(c.change_sigma) >= self.HIGH_SIGMA_THRESHOLD:
                flags.append(AnomalyFlag(
                    anomaly_type="high_sigma_move",
                    severity="high",
                    instrument=c.instrument,
                    description=f"{c.instrument} moved {c.change_sigma:.1f}sigma ({c.change_pct:+.2f}%)",
                    value=float(c.change_sigma),
                    threshold=float(self.HIGH_SIGMA_THRESHOLD),
                ))
            elif abs(c.change_sigma) >= self.SIGMA_THRESHOLD:
                flags.append(AnomalyFlag(
                    anomaly_type="two_sigma_move",
                    severity="medium",
                    instrument=c.instrument,
                    description=f"{c.instrument} moved {c.change_sigma:.1f}sigma ({c.change_pct:+.2f}%)",
                    value=float(c.change_sigma),
                    threshold=float(self.SIGMA_THRESHOLD),
                ))

        for template in TEMPLATE_VIOLATIONS:
            left = changes_by_instrument.get(template["pair"][0])
            right = changes_by_instrument.get(template["pair"][1])
            if left is None or right is None:
                continue
            left_sign = 1 if left.change_pct > 0 else -1
            right_sign = 1 if right.change_pct > 0 else -1
            same_direction = left_sign == right_sign
            if template["expected_divergence"] and same_direction:
                flags.append(AnomalyFlag(
                    anomaly_type="template_violation",
                    severity="high",
                    instrument=template["pair"][0],
                    description=template["description"],
                    value=round(abs(left.change_pct - right.change_pct), 4),
                    threshold=0.0,
                ))
            elif not template["expected_divergence"] and not same_direction:
                flags.append(AnomalyFlag(
                    anomaly_type="correlation_regime_shift",
                    severity="medium",
                    instrument=template["pair"][0],
                    description=template["description"],
                    value=round(abs(left.change_pct - right.change_pct), 4),
                    threshold=0.0,
                ))

        return flags
