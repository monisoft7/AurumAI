"""Tests for the economic validation layer."""

from __future__ import annotations

import pytest

from simulation.economic import compute_economic_summary, _economic_return
from simulation.models import EventRunResult, EconomicSummary


def _r(
    decision: str | None,
    correct: bool | None,
    actual_return: float | None,
    date: str = "2024-01-15",
) -> EventRunResult:
    """Minimal EventRunResult factory for economic tests."""
    return EventRunResult(
        event_type="CPI",
        event_date_min=date,
        event_date_max=date,
        event_count=1,
        success=True,
        execution_time_ms=0.0,
        cache_hits=0,
        checkpoints_used=0,
        decision=decision,
        decision_correct=correct,
        decision_actual_return_pct=actual_return,
    )


# ===========================================================================
# _economic_return
# ===========================================================================


def test_economic_return_correct_positive() -> None:
    """Gold up 2%, prediction correct → +2.0%."""
    r = _r("POSITIVE", True, 2.0)
    assert _economic_return(r) == 2.0


def test_economic_return_incorrect_positive() -> None:
    """Gold up 2%, prediction wrong → -2.0%."""
    r = _r("POSITIVE", False, 2.0)
    assert _economic_return(r) == -2.0


def test_economic_return_correct_negative() -> None:
    """Gold down 2%, prediction correct → +2.0%."""
    r = _r("NEGATIVE", True, -2.0)
    assert _economic_return(r) == 2.0


def test_economic_return_incorrect_negative() -> None:
    """Gold down 2%, prediction wrong → -2.0%."""
    r = _r("NEGATIVE", False, -2.0)
    assert _economic_return(r) == -2.0


def test_economic_return_neutral_flat() -> None:
    """Gold flat (0.05%), NEUTRAL correct → +0.05%."""
    r = _r("NEUTRAL", True, 0.05)
    assert _economic_return(r) == 0.05


def test_economic_return_none_returns_zero() -> None:
    """Events with no correctness or return produce 0.0."""
    assert _economic_return(_r(None, None, None)) == 0.0
    assert _economic_return(_r("POSITIVE", None, 2.0)) == 0.0
    assert _economic_return(_r("POSITIVE", True, None)) == 0.0


# ===========================================================================
# compute_economic_summary
# ===========================================================================


def test_empty_results() -> None:
    s = compute_economic_summary(())
    assert s.total_scored == 0
    assert s.correct_count == 0
    assert s.incorrect_count == 0
    assert s.positive_expected_value is None


def test_all_correct() -> None:
    results = (
        _r("POSITIVE", True, 1.0),
        _r("POSITIVE", True, 2.0),
        _r("NEGATIVE", True, -1.5),
    )
    s = compute_economic_summary(results)
    assert s.total_scored == 3
    assert s.correct_count == 3
    assert s.incorrect_count == 0
    assert s.avg_return_correct_pct == pytest.approx((1.0 + 2.0 + 1.5) / 3.0)
    assert s.avg_return_incorrect_pct is None
    assert s.profit_factor is None  # no losses → no division
    assert s.positive_expected_value is True


def test_all_incorrect() -> None:
    results = (
        _r("POSITIVE", False, 1.0),
        _r("NEGATIVE", False, -2.0),
    )
    s = compute_economic_summary(results)
    assert s.total_scored == 2
    assert s.correct_count == 0
    assert s.incorrect_count == 2
    assert s.avg_return_correct_pct is None
    assert s.avg_return_incorrect_pct == pytest.approx((-1.0 + -2.0) / 2.0)
    assert s.positive_expected_value is False


def test_mixed_results() -> None:
    """3 correct (2.0, 1.0, 1.5) + 1 incorrect (-2.5)."""
    results = (
        _r("POSITIVE", True, 2.0),
        _r("POSITIVE", True, 1.0),
        _r("NEGATIVE", True, -1.5),
        _r("POSITIVE", False, 2.5),
    )
    s = compute_economic_summary(results)
    assert s.total_scored == 4
    assert s.correct_count == 3
    assert s.incorrect_count == 1

    # Average return per correct: (2.0 + 1.0 + 1.5) / 3 = 1.5
    assert s.avg_return_correct_pct == pytest.approx(1.5)
    # Average return per incorrect: -2.5 (single)
    assert s.avg_return_incorrect_pct == pytest.approx(-2.5)

    # Expectancy = (3/4 * (2+1+1.5)/3) - (1/4 * 2.5)
    #           = 0.75 * 1.5 - 0.25 * 2.5
    #           = 1.125 - 0.625 = 0.5
    assert s.expectancy_pct == pytest.approx(0.5)

    # Profit factor = (2.0 + 1.0 + 1.5) / 2.5 = 4.5 / 2.5 = 1.8
    assert s.profit_factor == pytest.approx(1.8)

    # Payoff ratio = avg_win(2.0, 1.0, 1.5) / avg_loss(2.5)
    #              = 1.5 / 2.5 = 0.6
    assert s.payoff_ratio == pytest.approx(0.6)

    assert s.positive_expected_value is True


def test_consecutive_streaks() -> None:
    """Chronological order: win, win, loss, win, loss, loss, loss."""
    results = (
        _r("POSITIVE", True, 1.0, date="2024-01-01"),
        _r("POSITIVE", True, 0.5, date="2024-02-01"),
        _r("POSITIVE", False, 2.0, date="2024-03-01"),
        _r("POSITIVE", True, 1.0, date="2024-04-01"),
        _r("POSITIVE", False, 1.0, date="2024-05-01"),
        _r("POSITIVE", False, 0.5, date="2024-06-01"),
        _r("POSITIVE", False, 1.5, date="2024-07-01"),
    )
    s = compute_economic_summary(results)
    assert s.max_consecutive_wins == 2
    assert s.max_consecutive_losses == 3


def test_return_distribution() -> None:
    """Returns: 2.0, -2.0, 1.0, -1.0 → min=-2.0, median=0.0, mean=0.0, max=2.0"""
    results = (
        _r("POSITIVE", True, 2.0),
        _r("POSITIVE", False, 2.0),
        _r("POSITIVE", True, 1.0),
        _r("POSITIVE", False, 1.0),
    )
    s = compute_economic_summary(results)
    assert s.return_min_pct == pytest.approx(-2.0)
    assert s.return_median_pct == pytest.approx(0.0)
    assert s.return_mean_pct == pytest.approx(0.0)
    assert s.return_max_pct == pytest.approx(2.0)


def test_return_by_decision_type() -> None:
    """POSITIVE: 2 correct, 1 incorrect. NEGATIVE: 1 correct."""
    results = (
        _r("POSITIVE", True, 1.0),
        _r("POSITIVE", True, 2.0),
        _r("POSITIVE", False, 3.0),
        _r("NEGATIVE", True, -1.5),
    )
    s = compute_economic_summary(results)
    assert s.return_by_decision_type is not None

    pos = s.return_by_decision_type.get("POSITIVE")
    assert pos is not None
    assert pos.count == 3
    assert pos.correct_count == 2
    assert pos.incorrect_count == 1
    assert pos.total_return_pct == pytest.approx(1.0 + 2.0 + (-3.0))
    assert pos.mean_return_pct == pytest.approx((1.0 + 2.0 - 3.0) / 3.0)

    neg = s.return_by_decision_type.get("NEGATIVE")
    assert neg is not None
    assert neg.count == 1
    assert neg.correct_count == 1
    assert neg.incorrect_count == 0
    assert neg.total_return_pct == pytest.approx(1.5)


def test_non_scored_filtered_out() -> None:
    """Events without decision_correct or actual_return are excluded."""
    results = (
        _r("POSITIVE", True, 1.0),
        _r("POSITIVE", None, None),  # insufficient evidence
        _r(None, None, None),  # no decision
    )
    s = compute_economic_summary(results)
    assert s.total_scored == 1
    assert s.correct_count == 1


def test_all_neutral_zero_economic_impact() -> None:
    """NEUTRAL correctly predicting tiny moves → tiny returns."""
    results = (
        _r("NEUTRAL", True, 0.05),
        _r("NEUTRAL", True, -0.03),
    )
    s = compute_economic_summary(results)
    assert s.total_scored == 2
    assert s.correct_count == 2
    assert s.avg_return_correct_pct == pytest.approx((0.05 + 0.03) / 2.0)
    assert s.expectancy_pct == pytest.approx((0.05 + 0.03) / 2.0)  # 100% win rate


def test_to_dict_roundtrip() -> None:
    results = (
        _r("POSITIVE", True, 1.0),
        _r("POSITIVE", False, 2.0),
    )
    s = compute_economic_summary(results)
    d = s.to_dict()
    assert isinstance(d, dict)
    assert d["total_scored"] == 2
    assert d["correct_count"] == 1
    assert d["incorrect_count"] == 1
    assert d["positive_expected_value"] is not None
    assert isinstance(d["max_consecutive_wins"], int)


# ===========================================================================
# Edge cases
# ===========================================================================


def test_single_event() -> None:
    s = compute_economic_summary((_r("POSITIVE", True, 0.5),))
    assert s.total_scored == 1
    assert s.correct_count == 1
    assert s.max_consecutive_wins == 1
    assert s.max_consecutive_losses == 0
    assert s.profit_factor is None  # no losses


def test_perfect_alternation() -> None:
    """Win, loss, win, loss — max streaks of 1."""
    results = tuple(
        _r("POSITIVE", i % 2 == 0, 1.0, date=f"2024-{m:02d}-01")
        for i, m in enumerate(range(1, 9))
    )
    s = compute_economic_summary(results)
    assert s.max_consecutive_wins == 1
    assert s.max_consecutive_losses == 1
