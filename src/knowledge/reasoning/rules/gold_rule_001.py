"""
Gold Rule 001: Real Yield × DXY Composite Assessment.

Institutional reasoning rule that combines US 10-Year Real Yield
and US Dollar Index (DXY) FactorSignals into a single gold assessment.

Logic:
  - Both Bullish  → Strong Bullish Gold (reinforced confidence)
  - Both Bearish  → Strong Bearish Gold (reinforced confidence)
  - Conflict      → Mixed (reduced confidence)

This is the reference implementation for all future institutional rules.
Every rule must produce an InstitutionalAssessment and be invokable
via a standalone apply() function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.factors.contracts import (
    BIAS_BEARISH,
    BIAS_BULLISH,
    FactorSignal,
)
from knowledge.integrity.provenance import Provenance


# ── Assessment Bias ───────────────────────────────────────────────────

ASSESSMENT_STRONG_BULLISH = "strong_bullish"
ASSESSMENT_STRONG_BEARISH = "strong_bearish"
ASSESSMENT_MIXED = "mixed"

VALID_ASSESSMENT_BIASES = frozenset({
    ASSESSMENT_STRONG_BULLISH,
    ASSESSMENT_STRONG_BEARISH,
    ASSESSMENT_MIXED,
})


# ── Contract ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class InstitutionalAssessment:
    """Result of applying an institutional reasoning rule.

    Combines one or more FactorSignals into a composite assessment
    of gold's directional outlook with quantified conviction.

    Fields:
        assessment_id: Unique identifier for this assessment.
        rule_id: Identifies which rule produced this (e.g. "gold_rule_001").
        observation_date: The date this assessment applies to.
        composite_bias: Net assessment (strong_bullish / strong_bearish / mixed).
        composite_strength: Magnitude -1.0 to +1.0.
        composite_confidence: 0–1 confidence based on input agreement.
        signal_dispersion: 0–1 measure of disagreement among input signals
            (0 = perfect agreement, 1 = maximum conflict).
        input_signals: The FactorSignal instances that were assessed.
        explanation: Human-readable reasoning trace.
        provenance: Who created this and when.
        metadata: Extensible key-value store for future fields.
    """
    assessment_id: str
    rule_id: str
    observation_date: str
    composite_bias: str
    composite_strength: float
    composite_confidence: float
    signal_dispersion: float
    input_signals: tuple[FactorSignal, ...] = ()
    explanation: str = ""
    provenance: Provenance | None = None
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_signals", tuple(self.input_signals))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))
        if self.composite_bias not in VALID_ASSESSMENT_BIASES:
            msg = (
                f"Invalid composite_bias: {self.composite_bias!r}. "
                f"Valid: {sorted(VALID_ASSESSMENT_BIASES)}"
            )
            raise ValueError(msg)


# ── Rule ──────────────────────────────────────────────────────────────


def apply(real_yield: FactorSignal, dxy: FactorSignal) -> InstitutionalAssessment:
    """Apply Gold Rule 001: Real Yield × DXY composite assessment.

    Pure deterministic function. No AI, no ML, no LLM, no probability model.

    Args:
        real_yield: FactorSignal for US 10-Year Real Yield (factor_id="real_yield_10y").
        dxy: FactorSignal for US Dollar Index (factor_id="us_dollar_index").

    Returns:
        InstitutionalAssessment with composite bias, strength, confidence.

    Raises:
        TypeError: If either input is not a FactorSignal.
    """
    _validate_inputs(real_yield, dxy)

    ry_bias = real_yield.influence_bias
    dxy_bias = dxy.influence_bias
    ry_strength = real_yield.influence_strength
    dxy_strength = dxy.influence_strength
    ry_conf = real_yield.confidence
    dxy_conf = dxy.confidence

    both_bullish = ry_bias == BIAS_BULLISH and dxy_bias == BIAS_BULLISH
    both_bearish = ry_bias == BIAS_BEARISH and dxy_bias == BIAS_BEARISH

    if both_bullish:
        composite_bias = ASSESSMENT_STRONG_BULLISH
        composite_strength = (ry_strength + dxy_strength) / 2.0
        composite_confidence = max(ry_conf, dxy_conf)
        signal_dispersion = 0.0
        explanation = _build_explanation(
            "Both factors are bullish on gold.",
            ry_bias, ry_strength, ry_conf,
            dxy_bias, dxy_strength, dxy_conf,
            composite_strength, composite_confidence,
            "both indicate upward pressure — reinforcing the bullish case",
        )
    elif both_bearish:
        composite_bias = ASSESSMENT_STRONG_BEARISH
        composite_strength = (ry_strength + dxy_strength) / 2.0
        composite_confidence = max(ry_conf, dxy_conf)
        signal_dispersion = 0.0
        explanation = _build_explanation(
            "Both factors are bearish on gold.",
            ry_bias, ry_strength, ry_conf,
            dxy_bias, dxy_strength, dxy_conf,
            composite_strength, composite_confidence,
            "both indicate downward pressure — reinforcing the bearish case",
        )
    else:
        composite_bias = ASSESSMENT_MIXED
        composite_strength = (ry_strength + dxy_strength) / 2.0
        composite_confidence = ((ry_conf + dxy_conf) / 2.0) * 0.5
        signal_dispersion = abs(ry_strength - dxy_strength) / 2.0
        explanation = _build_explanation(
            "Factors are in conflict.",
            ry_bias, ry_strength, ry_conf,
            dxy_bias, dxy_strength, dxy_conf,
            composite_strength, composite_confidence,
            "are sending opposing signals — reducing conviction",
        )

    obs_date = _latest_date(real_yield.observation_date, dxy.observation_date)
    assessment_id = f"{obs_date}_{'x'.join(sorted([real_yield.factor_id, dxy.factor_id]))}"

    return InstitutionalAssessment(
        assessment_id=assessment_id,
        rule_id="gold_rule_001",
        observation_date=obs_date,
        composite_bias=composite_bias,
        composite_strength=round(composite_strength, 4),
        composite_confidence=round(composite_confidence, 4),
        signal_dispersion=round(signal_dispersion, 4),
        input_signals=(real_yield, dxy),
        explanation=explanation,
        provenance=Provenance(
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="gold_rule_001.v1",
            entity_version="1.0.0",
        ),
    )


# ── Internal helpers ──────────────────────────────────────────────────


def _validate_inputs(*signals: Any) -> None:
    for s in signals:
        if not isinstance(s, FactorSignal):
            raise TypeError(
                f"Expected FactorSignal, got {type(s).__name__}. "
                "Institutional rules require FactorSignal inputs."
            )


def _latest_date(d1: str, d2: str) -> str:
    return max(d1, d2) if d1 and d2 else (d1 or d2)


def _build_explanation(
    header: str,
    ry_bias: str, ry_strength: float, ry_conf: float,
    dxy_bias: str, dxy_strength: float, dxy_conf: float,
    composite_strength: float, composite_confidence: float,
    detail: str,
) -> str:
    return (
        f"{header} "
        f"Real Yield (bias={ry_bias}, strength={ry_strength:+.4f}, confidence={ry_conf:.4f}) and "
        f"DXY (bias={dxy_bias}, strength={dxy_strength:+.4f}, confidence={dxy_conf:.4f}) "
        f"{detail} "
        f"(composite strength={composite_strength:+.4f}, confidence={composite_confidence:.4f})."
    )
