"""Sprint 057: reference price end-to-end repair tests.

Verifies that the production trade recommendation consumes a real, latest
valid XAU/USD close resolved from the run's own gold data, that absolute
levels respect BUY/SELL ordering, that the relative-anchor fallback is
explicit and safe when no price exists, and that the institutional decision
path (action/confidence/RR) is numerically untouched.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from decision_engine.contracts import InstitutionalDecision
from orchestration.stages import _trade_recommendation
from trade_recommendation.contracts import InstitutionalTradeRecommendation
from trade_recommendation.reference_price import resolve_reference_price


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _decision(action: str = "BUY") -> InstitutionalDecision:
    return InstitutionalDecision(
        decision_id=f"dec_057_{action.lower()}",
        decision=action,
        selected_thesis_id="th_057",
        selected_scenario_id="sc_057",
        institutional_confidence=0.68,
        risk_reward_summary={
            "status": "acceptable",
            "maximum_downside": 0.4,
            "expected_upside": 0.6,
            "liquidity_risk": 0.2,
            "risk_reward_ratio": 1.1,
        },
        decision_explanation="sprint 057 fixture",
    )


def _gold_csv(tmp_path: Path, closes: list[float] | None = None,
              trailing_nan: bool = False) -> Path:
    if closes is None:
        closes = [2000.0 + 5.0 * i for i in range(40)]
    rows = [{"Date": f"2025-0{1 + i // 28}-{1 + i % 28:02d}", "Close": c}
            for i, c in enumerate(closes)]
    if trailing_nan:
        rows.append({"Date": "2025-03-05", "Close": None})
    frame = pd.DataFrame(rows)
    path = tmp_path / "gold.csv"
    frame.to_csv(path, index=False)
    return path


def _run_stage(decision: InstitutionalDecision, params: dict):
    return _trade_recommendation(dict(params), {"decision_engine": decision})


def _level_float(text: str) -> float:
    return float(str(text))


@pytest.fixture
def buy_decision() -> InstitutionalDecision:
    return _decision("BUY")


@pytest.fixture
def sell_decision() -> InstitutionalDecision:
    return _decision("SELL")


# ---------------------------------------------------------------------------
# 1) End-to-end arrival of the resolved price
# ---------------------------------------------------------------------------


class TestEndToEndArrival:
    def test_stage_resolves_price_without_explicit_param(
        self, tmp_path, buy_decision
    ) -> None:
        csv_path = _gold_csv(tmp_path)
        rec = _run_stage(buy_decision, {"asset": "XAU/USD", "gold_path": str(csv_path)})
        provenance = rec.metadata["reference_price_provenance"]
        assert provenance["status"] == "resolved_from_gold_data"
        assert rec.metadata["reference_price"] == pytest.approx(2195.0)

    def test_explicit_param_still_wins(self, tmp_path, buy_decision) -> None:
        csv_path = _gold_csv(tmp_path)
        rec = _run_stage(buy_decision, {
            "asset": "XAU/USD",
            "gold_path": str(csv_path),
            "reference_price": 1234.5,
        })
        assert rec.metadata["reference_price"] == 1234.5
        assert rec.metadata["reference_price_provenance"]["status"] == "explicit_param"


# ---------------------------------------------------------------------------
# 2) / 3) Absolute levels from the real price (BUY and SELL)
# ---------------------------------------------------------------------------


class TestAbsoluteLevels:
    def test_buy_levels_match_formula_from_real_price(self, tmp_path, buy_decision) -> None:
        csv_path = _gold_csv(tmp_path)
        price = 2195.0
        stop_pct = round(0.5 + 1.5 * 0.4, 2)          # maximum_downside = 0.4
        upside_pct = round(0.75 + 2.25 * 0.6, 2)      # expected_upside  = 0.6
        tp1_pct = round(0.5 * upside_pct, 2)
        rec = _run_stage(buy_decision, {"asset": "XAU/USD", "gold_path": str(csv_path)})
        # The recommender formats every level to exactly two decimals; the
        # precise contract is the formatted string of the computed level.
        assert rec.stop_loss == f"{price * (1 - stop_pct / 100):.2f}"
        assert rec.take_profit_1 == f"{price * (1 + tp1_pct / 100):.2f}"
        assert rec.take_profit_2 == f"{price * (1 + upside_pct / 100):.2f}"
        low, high = (_level_float(x) for x in rec.entry_zone)
        assert low == pytest.approx(price, abs=0.005)
        assert high == pytest.approx(price * (1 + 0.25 / 100), abs=0.005)

    def test_sell_levels_match_formula_from_real_price(self, tmp_path, sell_decision) -> None:
        csv_path = _gold_csv(tmp_path)
        price = 2195.0
        stop_pct = round(0.5 + 1.5 * 0.4, 2)
        upside_pct = round(0.75 + 2.25 * 0.6, 2)
        tp1_pct = round(0.5 * upside_pct, 2)
        rec = _run_stage(sell_decision, {"asset": "XAU/USD", "gold_path": str(csv_path)})
        assert rec.stop_loss == f"{price * (1 + stop_pct / 100):.2f}"
        assert rec.take_profit_1 == f"{price * (1 - tp1_pct / 100):.2f}"
        assert rec.take_profit_2 == f"{price * (1 - upside_pct / 100):.2f}"


# ---------------------------------------------------------------------------
# 4) Price-level ordering invariants
# ---------------------------------------------------------------------------


class TestLevelOrdering:
    def test_buy_stop_below_entry_below_targets(self, tmp_path, buy_decision) -> None:
        csv_path = _gold_csv(tmp_path)
        rec = _run_stage(buy_decision, {"asset": "XAU/USD", "gold_path": str(csv_path)})
        entry_low, entry_high = (_level_float(x) for x in rec.entry_zone)
        stop = _level_float(rec.stop_loss)
        tp1, tp2 = _level_float(rec.take_profit_1), _level_float(rec.take_profit_2)
        assert stop < entry_low <= entry_high < tp1 < tp2

    def test_sell_targets_below_entry_below_stop(self, tmp_path, sell_decision) -> None:
        csv_path = _gold_csv(tmp_path)
        rec = _run_stage(sell_decision, {"asset": "XAU/USD", "gold_path": str(csv_path)})
        entry_low, entry_high = (_level_float(x) for x in rec.entry_zone)
        stop = _level_float(rec.stop_loss)
        tp1, tp2 = _level_float(rec.take_profit_1), _level_float(rec.take_profit_2)
        assert tp2 < tp1 < entry_low <= entry_high < stop


# ---------------------------------------------------------------------------
# 5) Relative-field regression guard
# ---------------------------------------------------------------------------


class TestRelativeFieldsRegression:
    def test_risk_pct_and_holding_days_formulas_unchanged(
        self, tmp_path, buy_decision
    ) -> None:
        csv_path = _gold_csv(tmp_path)
        rec = _run_stage(buy_decision, {"asset": "XAU/USD", "gold_path": str(csv_path)})
        expected_risk = min(round(0.25 + 1.0 * 0.68, 2), 2.0)
        expected_days = max(30, round(120 - 90.0 * 0.2))
        assert rec.risk_pct == expected_risk
        assert rec.expected_holding_days == expected_days

    def test_anchor_mode_still_relative_when_unavailable(self, buy_decision) -> None:
        rec = _run_stage(buy_decision, {"asset": "XAU/USD"})
        assert all(x.startswith("anchor") for x in rec.entry_zone)
        assert rec.stop_loss.startswith("anchor")
        provenance = rec.metadata["reference_price_provenance"]
        assert provenance["status"] == "unavailable_relative_anchor_fallback"
        assert provenance["reason"] == "gold_path_not_set"
        assert rec.metadata["reference_price"] is None


# ---------------------------------------------------------------------------
# 6) Missing-price behavior: explicit, announced, never invented
# ---------------------------------------------------------------------------


class TestMissingPriceSafety:
    def test_missing_file_falls_back_with_reason(self, tmp_path, sell_decision) -> None:
        rec = _run_stage(sell_decision, {
            "asset": "XAU/USD",
            "gold_path": str(tmp_path / "nope.csv"),
        })
        assert rec.metadata["reference_price_provenance"]["reason"].startswith(
            "gold_path_not_found"
        )
        assert rec.metadata["reference_price"] is None

    def test_wrong_columns_degrade_cleanly(self, tmp_path, buy_decision) -> None:
        path = tmp_path / "odd.csv"
        pd.DataFrame({"ds": ["2025-01-01"], "price": [2000.0]}).to_csv(path, index=False)
        rec = _run_stage(buy_decision, {"asset": "XAU/USD", "gold_path": str(path)})
        provenance = rec.metadata["reference_price_provenance"]
        assert provenance["status"] == "unavailable_relative_anchor_fallback"

    def test_all_nan_closes_never_invent_a_price(self, tmp_path, buy_decision) -> None:
        path = tmp_path / "nan.csv"
        pd.DataFrame({
            "Date": ["2025-01-01", "2025-01-02"],
            "Close": [float("nan"), None],
        }).to_csv(path, index=False)
        value, reason = resolve_reference_price(str(path))
        assert value is None
        assert reason == "no_valid_rows"
        rec = _run_stage(buy_decision, {"asset": "XAU/USD", "gold_path": str(path)})
        assert rec.metadata["reference_price"] is None

    def test_resolver_never_raises_on_garbage_input(self, tmp_path) -> None:
        garbage = tmp_path / "garbage.csv"
        garbage.write_bytes(b"\xff\xfe not a csv \x00\x01")
        value, reason = resolve_reference_price(str(garbage))
        assert value is None
        assert reason  # explicit reason string, never an exception


# ---------------------------------------------------------------------------
# 7) Deterministic repeat
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_repeated_runs_identical_after_id_neutralization(
        self, tmp_path, buy_decision
    ) -> None:
        csv_path = _gold_csv(tmp_path)
        params = {"asset": "XAU/USD", "gold_path": str(csv_path)}
        first = _run_stage(buy_decision, params)
        second = _run_stage(buy_decision, params)
        left = InstitutionalTradeRecommendation.from_dict(first.to_dict())
        right = InstitutionalTradeRecommendation.from_dict(second.to_dict())
        for rec in (left, right):
            object.__setattr__(rec, "recommendation_id", "")
            object.__setattr__(rec, "provenance_chain", ())
        assert left == right


# ---------------------------------------------------------------------------
# 8) Provenance / hash integrity
# ---------------------------------------------------------------------------


class TestProvenanceAndHash:
    def test_provenance_fields_complete_and_correct(self, tmp_path, buy_decision) -> None:
        csv_path = _gold_csv(tmp_path)
        rec = _run_stage(buy_decision, {"asset": "XAU/USD", "gold_path": str(csv_path)})
        provenance = rec.metadata["reference_price_provenance"]
        assert provenance["method"] == "last_valid_close"
        assert provenance["source_path"] == str(csv_path)
        assert provenance["source_data_hash"] == hashlib.sha256(
            csv_path.read_bytes()
        ).hexdigest()
        # Last valid bar wins; trailing NaN close is skipped.
        assert provenance["bar_date"].startswith(pd.Timestamp("2025-02-12").date().isoformat())
        assert provenance["value"] == pytest.approx(2195.0)

    def test_hash_changes_when_data_changes(self, tmp_path, buy_decision) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        first_csv = _gold_csv(dir_a)
        second_csv = _gold_csv(dir_b, closes=[2100.0 + 5.0 * i for i in range(40)])
        params_first = {"asset": "XAU/USD", "gold_path": str(first_csv)}
        params_second = {"asset": "XAU/USD", "gold_path": str(second_csv)}
        rec_first = _run_stage(buy_decision, params_first)
        rec_second = _run_stage(buy_decision, params_second)
        h1 = rec_first.metadata["reference_price_provenance"]["source_data_hash"]
        h2 = rec_second.metadata["reference_price_provenance"]["source_data_hash"]
        assert h1 != h2


# ---------------------------------------------------------------------------
# 9) Historical as-of safety
# ---------------------------------------------------------------------------


class TestAsOfSafety:
    def test_resolver_honors_as_of_bound(self, tmp_path) -> None:
        csv_path = _gold_csv(tmp_path)
        value, _ = resolve_reference_price(str(csv_path), as_of="2025-01-15")
        assert value is not None
        assert value.bar_date[:10] <= "2025-01-15"
        assert value.value < 2195.0

    def test_stage_honors_reference_as_of_param(self, tmp_path, sell_decision) -> None:
        csv_path = _gold_csv(tmp_path)
        rec = _run_stage(sell_decision, {
            "asset": "XAU/USD",
            "gold_path": str(csv_path),
            "reference_as_of": "2025-01-10",
        })
        provenance = rec.metadata["reference_price_provenance"]
        assert provenance["bar_date"][:10] <= "2025-01-10"
        assert rec.metadata["reference_price"] == pytest.approx(provenance["value"])

    def test_as_of_before_all_data_is_announced_not_fabricated(
        self, tmp_path, buy_decision
    ) -> None:
        csv_path = _gold_csv(tmp_path)
        rec = _run_stage(buy_decision, {
            "asset": "XAU/USD",
            "gold_path": str(csv_path),
            "reference_as_of": "1999-01-01",
        })
        provenance = rec.metadata["reference_price_provenance"]
        assert provenance["status"] == "unavailable_relative_anchor_fallback"
        assert rec.metadata["reference_price"] is None


# ---------------------------------------------------------------------------
# 10) Decision / confidence / RR invariance
# ---------------------------------------------------------------------------


class TestDecisionInvariance:
    def test_institutional_fields_identical_across_price_modes(
        self, tmp_path
    ) -> None:
        csv_path = _gold_csv(tmp_path)
        decision = _decision("BUY")

        with_price = _run_stage(decision, {
            "asset": "XAU/USD", "gold_path": str(csv_path),
        })
        without_price = _run_stage(decision, {"asset": "XAU/USD"})

        assert with_price.recommendation_action == without_price.recommendation_action
        assert with_price.confidence == without_price.confidence
        assert with_price.decision_id == without_price.decision_id
        assert with_price.decision_summary == without_price.decision_summary
        assert with_price.risk_pct == without_price.risk_pct
        assert (
            with_price.expected_holding_days == without_price.expected_holding_days
        )
        assert (
            with_price.major_supporting_evidence
            == without_price.major_supporting_evidence
        )
        # The ONLY intended difference: absolute vs anchor level strings.
        assert with_price.stop_loss != without_price.stop_loss
        assert with_price.metadata["selected_thesis_id"] == (
            without_price.metadata["selected_thesis_id"]
        )

    def test_resolver_is_pure_function_of_inputs(self, tmp_path) -> None:
        csv_path = _gold_csv(tmp_path)
        a = resolve_reference_price(str(csv_path))
        b = resolve_reference_price(str(csv_path))
        assert a[0].to_dict() == b[0].to_dict()
