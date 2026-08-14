"""Correction 023: regime-conditioned cross-factor precedence metadata.

Reuses the existing REGIME_INDICATORS hierarchy inside the existing
build_cross_factor_rationale() to add explanation-only adjudication metadata
(regime, dominant_factor, weaker_factor, precedence_reason,
adjudicated_interpretation). It must be:
- deterministic (identical inputs -> identical metadata),
- purely explanatory (no numeric composite or factor signal change),
- faithful to the authored regime hierarchy (no regime inversion, no
  fabricated precedence for unknown regimes or missing factors),
- propagated through ThesisBuilder (W8) and ThesisUpdater (W10).
"""

from dataclasses import replace

import evidence_reasoning.cross_factor_rationale as xfr
from evidence_reasoning.cross_factor_rationale import build_cross_factor_rationale
from thesis_construction.builder import ThesisBuilder
from thesis_update.updater import ThesisUpdater

from test_cross_factor_rationale import (
    _collect_and_reason,
    _fresh_dates,
    _make_assessment_for,
    _make_construction,
    _values,
    _write_series,
)


def _rationale(tmp_path, regime=None):
    ry = tmp_path / "DFII10.csv"
    dx = tmp_path / "dxy.csv"
    _write_series(ry, _fresh_dates(), _values())
    _write_series(dx, _fresh_dates(), [v + 50.0 for v in _values()])
    return build_cross_factor_rationale(ry, dx, regime=regime)


class TestInflationaryAdjudication:
    def test_dxy_outranks_real_yield(self, tmp_path):
        r = _rationale(tmp_path, regime="INFLATIONARY")
        assert r is not None
        assert r["regime"] == "INFLATIONARY"
        assert r["dominant_factor"] == "us_dollar_index"
        assert r["weaker_factor"] == "real_yield_10y"

    def test_precedence_reason_preserves_unstable_beta(self, tmp_path):
        r = _rationale(tmp_path, regime="INFLATIONARY")
        reason = r["precedence_reason"]
        assert "real_yields_10y_tips" in reason
        assert "unstable beta" in reason
        assert "above" in reason
        assert "dxy" in reason

    def test_adjudicated_interpretation_is_regime_conditional(self, tmp_path):
        r = _rationale(tmp_path, regime="INFLATIONARY")
        interp = r["adjudicated_interpretation"]
        assert "INFLATIONARY" in interp
        assert "not reweighted" in interp
        assert "composite numerics are unchanged" in interp
        assert "universal factor importance" in interp
        assert "CPI evidence" in interp


class TestOtherRegimeAdjudication:
    def test_normal_growth_uses_own_hierarchy(self, tmp_path):
        r = _rationale(tmp_path, regime="NORMAL_GROWTH")
        assert r is not None
        assert r["regime"] == "NORMAL_GROWTH"
        # NORMAL_GROWTH: real_yields_10y_tips 0.30 > dxy 0.25 -> inversion vs INFLATIONARY.
        assert r["dominant_factor"] == "real_yield_10y"
        assert r["weaker_factor"] == "us_dollar_index"
        assert "0.30" in r["precedence_reason"]

    def test_distinct_from_inflationary(self, tmp_path):
        inflation = _rationale(tmp_path, regime="INFLATIONARY")
        normal = _rationale(tmp_path, regime="NORMAL_GROWTH")
        assert inflation["dominant_factor"] != normal["dominant_factor"]


class TestMissingFactorOrRegime:
    def test_unknown_regime_omits_adjudication(self, tmp_path):
        r = _rationale(tmp_path, regime="UNKNOWN_REGIME")
        assert r is not None
        assert "dominant_factor" not in r
        assert "weaker_factor" not in r
        assert "precedence_reason" not in r

    def test_no_regime_omits_adjudication(self, tmp_path):
        r = _rationale(tmp_path, regime=None)
        assert r is not None
        assert "dominant_factor" not in r

    def test_missing_factor_no_fabrication(self, tmp_path, monkeypatch):
        # A hierarchy listing only dxy: real yield is absent, so no precedence
        # between the two gold factors may be claimed.
        monkeypatch.setattr(
            xfr,
            "REGIME_INDICATORS",
            {
                "INFLATIONARY": {
                    "dominant": [
                        {"indicator": "dxy", "weight": 0.05,
                         "description": "US Dollar Index"}
                    ]
                }
            },
        )
        r = _rationale(tmp_path, regime="INFLATIONARY")
        assert r is not None
        assert "dominant_factor" not in r
        assert "weaker_factor" not in r
        assert "precedence_reason" not in r


class TestNumericInvariance:
    NUMERIC = ("composite_bias", "composite_strength",
               "composite_confidence", "signal_dispersion", "explanation")

    def test_adjudication_leaves_composite_and_factors_unchanged(self, tmp_path):
        plain = _rationale(tmp_path, regime=None)
        rich = _rationale(tmp_path, regime="INFLATIONARY")
        assert plain is not None and rich is not None
        for key in self.NUMERIC:
            assert plain[key] == rich[key]
        assert plain["factors"] == rich["factors"]
        for factor in rich["factors"]:
            assert factor["status"] == "current"


class TestThesisPropagation:
    def test_reasoner_metadata_contains_adjudication(self):
        reasoning = _collect_and_reason()
        rationale = reasoning.metadata["factor_rationale"]
        assert rationale["regime"] == "NORMAL_GROWTH"
        assert rationale["dominant_factor"] == "real_yield_10y"
        assert "precedence_reason" in rationale

    def test_builder_includes_adjudication_in_explanation(self):
        reasoning = _collect_and_reason()
        supporting = list(reasoning.evidence_sets)
        assessment = _make_assessment_for(reasoning, supporting[0].set_id)
        thesis = ThesisBuilder().build_thesis(
            "bullish", reasoning, assessment,
            [s.set_id for s in supporting], [],
        )
        assert "regime=NORMAL_GROWTH" in thesis.explanation
        assert "dominant_factor=real_yield_10y" in thesis.explanation
        assert "adjudicated_interpretation=" in thesis.explanation

    def test_updater_preserves_adjudication(self):
        reasoning = _collect_and_reason()
        supporting = list(reasoning.evidence_sets)
        assessment = _make_assessment_for(reasoning, supporting[0].set_id)
        thesis = ThesisBuilder().build_thesis(
            "bullish", reasoning, assessment,
            [s.set_id for s in supporting], [],
        )
        update = ThesisUpdater().update(
            _make_construction(
                thesis, reasoning.reasoning_id, assessment.assessment_id
            ),
            reasoning,
            assessment,
        )
        explanation = update.updated_thesis.explanation
        assert "regime=NORMAL_GROWTH" in explanation
        assert "dominant_factor=real_yield_10y" in explanation

    def test_without_factor_rationale_no_adjudication(self):
        reasoning = _collect_and_reason()
        plain = replace(
            reasoning,
            metadata={
                k: v for k, v in reasoning.metadata.items()
                if k != "factor_rationale"
            },
        )
        supporting = list(reasoning.evidence_sets)
        assessment = _make_assessment_for(reasoning, supporting[0].set_id)
        thesis = ThesisBuilder().build_thesis(
            "bullish", plain, assessment,
            [s.set_id for s in supporting], [],
        )
        assert "dominant_factor=" not in thesis.explanation


class TestDeterminismSerialization:
    def test_repeated_inputs_identical(self, tmp_path):
        a = _rationale(tmp_path, regime="INFLATIONARY")
        b = _rationale(tmp_path, regime="INFLATIONARY")
        assert a == b

    def test_roundtrip_preserves_adjudication(self, tmp_path):
        import json as _json

        from evidence_reasoning.contracts import EvidenceReasoning

        reasoning = _collect_and_reason()
        raw = _json.dumps(reasoning.to_dict())
        restored = EvidenceReasoning.from_dict(_json.loads(raw))
        assert restored.metadata["factor_rationale"] == (
            reasoning.metadata["factor_rationale"]
        )
        assert restored.metadata["factor_rationale"]["regime"] == "NORMAL_GROWTH"