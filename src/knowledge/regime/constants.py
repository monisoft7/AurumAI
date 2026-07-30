from __future__ import annotations

NORMAL_GROWTH = "NORMAL_GROWTH"
INFLATIONARY = "INFLATIONARY"
STAGFLATIONARY = "STAGFLATIONARY"
DEFLATIONARY_CRISIS = "DEFLATIONARY_CRISIS"
GEOPOLITICAL_STRESS = "GEOPOLITICAL_STRESS"
STRUCTURAL_REGIME_CHANGE = "STRUCTURAL_REGIME_CHANGE"

INSTITUTIONAL_REGIMES = [
    NORMAL_GROWTH,
    INFLATIONARY,
    STAGFLATIONARY,
    DEFLATIONARY_CRISIS,
    GEOPOLITICAL_STRESS,
    STRUCTURAL_REGIME_CHANGE,
]

CANONICAL_REGIME_SET = frozenset(INSTITUTIONAL_REGIMES)

REGIME_LABELS: dict[str, str] = {
    NORMAL_GROWTH: "Normal Growth (Goldilocks)",
    INFLATIONARY: "Inflationary",
    STAGFLATIONARY: "Stagflationary",
    DEFLATIONARY_CRISIS: "Deflationary / Crisis",
    GEOPOLITICAL_STRESS: "Geopolitical Stress",
    STRUCTURAL_REGIME_CHANGE: "Structural Regime Change",
}

REGIME_TEXT_PATTERNS: dict[str, set[str]] = {
    NORMAL_GROWTH: {"normal growth", "normal regime", "goldilocks"},
    INFLATIONARY: {"inflationary", "inflation regime"},
    STAGFLATIONARY: {"stagflationary", "stagflation"},
    DEFLATIONARY_CRISIS: {"deflationary", "deflation", "crisis regime", "liquidity crisis"},
    GEOPOLITICAL_STRESS: {"geopolitical stress", "geopolitical regime"},
    STRUCTURAL_REGIME_CHANGE: {"structural regime change", "regime change", "structural regime"},
}

SUPPLEMENTARY_REGIME_PATTERNS: dict[str, set[str]] = {
    "FISCAL_DOMINANCE": {"fiscal dominance"},
    "CENTRAL_BANK_DRIVEN": {"central bank-driven", "central bank regime"},
    "LIQUIDITY_CRISIS": {"liquidity crisis"},
    "TRANSITION": {"transition regime"},
}

VALID_BIAS_VALUES = frozenset({"bullish", "bearish", "neutral", "mixed"})

VALID_TIER_VALUES = frozenset({"dominant", "secondary", "weaker"})

VALID_TRANSITION_TYPES = frozenset({
    "deterioration", "improvement", "regime_break",
    "recovery_from_break", "none",
})

VALID_SOURCE_TYPES = frozenset({"kr", "evidence", "regime", "thesis", "decision"})

VALID_CALIBRATION_METHODS = frozenset({
    "kb_text", "markov_probability", "composite_weight",
    "empirical", "expert", "consensus",
})

DEFAULT_TRANSITION_THRESHOLD = 0.5
DEFAULT_GPR_THRESHOLD = 150.0
DEFAULT_GRAM_RESIDUAL_THRESHOLD = 2.0
DEFAULT_GRAM_WINDOW = 36
DEFAULT_GRAM_MIN_PERIODS = 12
