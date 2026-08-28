"""Final Hardening — Groups C & D: Real Risk and Execution Surfacing.

Group C (D-01): execution levels are market-anchored -- stop 1.5 x ATR(14),
target 3.0 x ATR(14) from the reference price -- with explicit fallback and
provenance when ATR is unavailable.  A market reward/risk ratio derived from
the actual levels is surfaced next to the conviction-based W12 ratio.

Group D (D-06): the recommendation reaches the finalize payload and the run
artifact directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decision_engine.contracts import InstitutionalDecision  # noqa: E402
from trade_recommendation.recommender import (  # noqa: E402
    ATR_STOP_MULTIPLE,
    ATR_TARGET_MULTIPLE,
    RecommendationEngine,
)


def _buy_decision(confidence: float = 0.7) -> InstitutionalDecision:
    return InstitutionalDecision(
        decision_id="dec_c",
        decision="BUY",
        selected_thesis_id="th_x",
        selected_scenario_id="sc_x",
        institutional_confidence=confidence,
        risk_reward_summary={
            "status": "acceptable",
            "expected_reward": 0.3,
            "expected_risk": 0.1,
            "risk_reward_ratio": 0.5,
            "maximum_downside": 0.2,
            "expected_upside": 0.8,
            "liquidity_risk": 0.1,
        },
        decision_explanation="test",
    )


def _sell_decision() -> InstitutionalDecision:
    return InstitutionalDecision(
        decision_id="dec_s",
        decision="SELL",
        selected_thesis_id="th_x",
        selected_scenario_id="sc_x",
        institutional_confidence=0.7,
        risk_reward_summary={
            "status": "acceptable",
            "risk_reward_ratio": 0.5,
            "liquidity_risk": 0.1,
        },
        decision_explanation="test",
    )


# ---------------------------------------------------------------------------
# ATR-based levels
# ---------------------------------------------------------------------------


class TestATRLevels:
    def test_buy_levels_are_atr_derived(self):
        reference = 2000.0
        atr = 20.0
        rec = RecommendationEngine().recommend(
            _buy_decision(), reference_price=reference, atr=atr
        )
        stop_expected = round(2000.0 * (1.0 - ATR_STOP_MULTIPLE * 20.0 / 2000.0), 2)
        target_expected = round(
            2000.0 * (1.0 + ATR_TARGET_MULTIPLE * 20.0 / 2000.0), 2
        )
        assert rec.stop_loss == f"{stop_expected:.2f}"
        assert rec.take_profit_2 == f"{target_expected:.2f}"
        assert rec.metadata["levels_basis"] == "atr"

    def test_market_reward_risk_ratio_is_two_to_one(self):
        rec = RecommendationEngine().recommend(
            _buy_decision(), reference_price=2000.0, atr=20.0
        )
        summary = rec.metadata["market_risk_summary"]
        assert summary["basis"] == "atr"
        assert summary["market_reward_risk_ratio"] == pytest.approx(2.0, abs=0.02)
        assert summary["risk_per_unit"] == pytest.approx(30.0, abs=0.5)
        assert summary["reward_per_unit"] == pytest.approx(60.0, abs=1.0)

    def test_sell_levels_mirrored(self):
        rec = RecommendationEngine().recommend(
            _sell_decision(), reference_price=2000.0, atr=20.0
        )
        summary = rec.metadata["market_risk_summary"]
        assert float(rec.stop_loss) > 2000.0
        assert float(rec.take_profit_2) < 2000.0
        assert summary["market_reward_risk_ratio"] == pytest.approx(2.0, abs=0.02)

    def test_atr_unavailable_falls_back_and_is_labeled(self):
        rec = RecommendationEngine().recommend(
            _buy_decision(), reference_price=2000.0, atr=None
        )
        assert rec.metadata["levels_basis"] == "conviction_heuristic_fallback"
        assert "market_risk_summary" not in rec.metadata

    def test_atr_provenance_recorded(self):
        provenance = {"status": "ok", "atr_14": 20.0, "as_of": "2026-01-01"}
        rec = RecommendationEngine().recommend(
            _buy_decision(),
            reference_price=2000.0,
            atr=20.0,
            atr_provenance=provenance,
        )
        assert rec.metadata["atr_provenance"]["status"] == "ok"
        assert rec.metadata["atr_provenance"]["as_of"] == "2026-01-01"

    def test_no_trade_carries_no_levels(self):
        decision = InstitutionalDecision(
            decision_id="dec_nt",
            decision="NO_TRADE",
            selected_thesis_id="",
            selected_scenario_id="",
            institutional_confidence=0.0,
            risk_reward_summary={},
            decision_explanation="test",
        )
        rec = RecommendationEngine().recommend(
            decision, reference_price=2000.0, atr=20.0
        )
        assert rec.stop_loss == ""
        assert rec.metadata["levels_basis"] == "not_applicable_no_levels"


# ---------------------------------------------------------------------------
# stage-level ATR resolution (real gold file, deterministic as-of)
# ---------------------------------------------------------------------------


class TestStageATRContext:
    def test_resolves_atr_from_gold_path(self, tmp_path):
        from orchestration.stages import _resolve_atr_context

        rows = [
            "Date,Close,High,Low,Open,Volume",
        ]
        price = 2000.0
        import datetime as dt

        day = dt.date(2026, 1, 1)
        for i in range(60):
            day = day + dt.timedelta(days=1)
            price = price + (1.0 if i % 2 == 0 else -1.7)
            rows.append(
                f"{day.isoformat()},{price:.2f},{price + 4:.2f},"
                f"{price - 4:.2f},{price:.2f},1000"
            )
        gold = tmp_path / "gold.csv"
        gold.write_text("\n".join(rows) + "\n", encoding="utf-8")

        atr, provenance = _resolve_atr_context(
            str(gold), as_of=day.isoformat()
        )
        assert atr is not None and atr > 0
        assert provenance["status"] == "ok"
        assert provenance["as_of"] == day.isoformat()
        assert provenance["engine"] == "pandas_ta_classic:atr_14"

    def test_unavailable_when_no_history(self, tmp_path):
        from orchestration.stages import _resolve_atr_context

        gold = tmp_path / "gold.csv"
        gold.write_text(
            "Date,Close,High,Low,Open,Volume\n"
            "2026-01-01,2000.0,2004,1996,2000,10\n",
            encoding="utf-8",
        )
        atr, provenance = _resolve_atr_context(str(gold), as_of="2026-01-01")
        assert atr is None
        assert provenance["status"] == "unavailable"

    def test_unavailable_without_gold_path(self):
        from orchestration.stages import _resolve_atr_context

        atr, provenance = _resolve_atr_context(None, as_of="2026-01-01")
        assert atr is None
        assert provenance["status"] == "unavailable"


# ---------------------------------------------------------------------------
# Group D: execution surfacing
# ---------------------------------------------------------------------------


class TestExecutionSurfacing:
    def test_finalize_includes_trade_recommendation(self):
        from orchestration.stages import _finalize
        from trade_recommendation.contracts import (
            InstitutionalTradeRecommendation,
        )

        class _Rec(InstitutionalTradeRecommendation):
            pass

        rec = RecommendationEngine().recommend(
            _buy_decision(), reference_price=2000.0, atr=20.0
        )
        payload = _finalize(
            {},
            {
                "build_legacy_pipeline": {},
                "decision_engine": {"decision": "NO_TRADE"},
                "trade_recommendation": rec,
            },
        )
        assert "trade_recommendation" in payload
        surfaced = payload["trade_recommendation"]
        assert surfaced["recommendation_action"] == "BUY"
        assert surfaced["metadata"]["market_risk_summary"]["basis"] == "atr"

    def test_trade_recommendation_artifact_written(self, tmp_path):
        from orchestration.stages import _trade_recommendation
        import json

        decision = _buy_decision()
        params = {
            "output_dir": str(tmp_path),
            "reference_price": 2000.0,
            "gold_path": None,
        }
        rec = _trade_recommendation(params, {"decision_engine": decision})
        artifact = tmp_path / "trade_recommendation.json"
        assert artifact.is_file()
        data = json.loads(artifact.read_text(encoding="utf-8"))
        assert data["recommendation_action"] == "BUY"
        assert rec.metadata["levels_basis"] == "conviction_heuristic_fallback"

    def test_report_includes_execution_levels(self):
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location(
            "aurumai_generate_institutional_report_test",
            ROOT / "scripts" / "generate_institutional_report.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        except SystemExit:
            pass

        finalize = {
            "decision": {
                "risk_reward_summary": {"risk_reward_ratio": 0.5},
                "decision": "BUY",
            },
            "trade_recommendation": RecommendationEngine()
            .recommend(_buy_decision(), reference_price=2000.0, atr=20.0)
            .to_dict(),
        }
        sections = module.build_sections({"finalize": finalize})
        execution = [s for s in sections if s.title == "Execution Levels"]
        assert execution, "report must include an Execution Levels section"
        assert "ATR-anchored levels" in execution[0].md
        assert "conviction proxy (W12)" in execution[0].md
