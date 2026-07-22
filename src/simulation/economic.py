"""Economic validation layer for AurumAI.

Pure functions that compute economic value metrics from scored
``EventRunResult`` objects.

All metrics assume a normalized position size of 1 with no
leverage, commissions, slippage, or execution costs.

This is NOT a trading engine.
This is NOT an execution system.
This is NOT a backtester.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median, mean
from typing import Any

from simulation.models import EventRunResult, EconomicSummary, EconomicReturnStats


def _economic_return(r: EventRunResult) -> float:
    """Signed economic return for one scored event.

    A correct directional bet captures the absolute gold move as profit.
    An incorrect directional bet loses the absolute gold move.
    """
    if r.decision_correct is None or r.decision_actual_return_pct is None:
        return 0.0
    raw = r.decision_actual_return_pct
    return abs(raw) if r.decision_correct else -abs(raw)


def compute_economic_summary(results: tuple[EventRunResult, ...]) -> EconomicSummary:
    """Evaluate the economic quality of every scored decision.

    Parameters
    ----------
    results:
        |EventRunResult| objects — typically from ``ChronologicalOOSResult.evaluation_results``.

    Returns
    -------
    EconomicSummary
        All economic metrics.  Empty if no scored events exist.
    """
    # -- filter to events that have both correctness and actual return ----------
    scored = [
        r for r in results
        if r.decision_correct is not None
        and r.decision_actual_return_pct is not None
    ]

    if not scored:
        return EconomicSummary(total_scored=0, correct_count=0, incorrect_count=0)

    # -- compute economic returns -----------------------------------------------
    correct_rets: list[float] = []
    incorrect_rets: list[float] = []
    eco_rets: list[float] = []

    for r in scored:
        er = _economic_return(r)
        eco_rets.append(er)
        if r.decision_correct:
            correct_rets.append(er)
        else:
            incorrect_rets.append(er)

    n_correct = len(correct_rets)
    n_incorrect = len(incorrect_rets)

    avg_correct = mean(correct_rets) if correct_rets else None
    avg_incorrect = mean(incorrect_rets) if incorrect_rets else None

    # -- Expected Value (Expectancy) --------------------------------------------
    win_rate = n_correct / len(scored)
    loss_rate = n_incorrect / len(scored)
    wins = [e for e in eco_rets if e > 0]
    losses = [e for e in eco_rets if e < 0]
    avg_win = mean(wins) if wins else 0.0
    avg_loss = abs(mean(losses)) if losses else 0.0
    expectancy = win_rate * avg_win - loss_rate * avg_loss

    # -- Profit Factor ----------------------------------------------------------
    pos_sum = sum(e for e in eco_rets if e > 0)
    neg_sum = abs(sum(e for e in eco_rets if e < 0))
    profit_factor = pos_sum / neg_sum if neg_sum > 0 else None

    # -- Payoff Ratio -----------------------------------------------------------
    mean_win = mean(wins) if wins else None
    mean_loss_val = abs(mean(losses)) if losses else None
    payoff_ratio = (
        mean_win / mean_loss_val
        if mean_win is not None and mean_loss_val is not None and mean_loss_val > 0
        else None
    )

    # -- Consecutive wins / losses (chronological order) ------------------------
    sorted_scored = sorted(scored, key=lambda r: r.event_date_min)

    max_cw = 0
    max_cl = 0
    cur_w = 0
    cur_l = 0
    for r in sorted_scored:
        if r.decision_correct:
            cur_w += 1
            cur_l = 0
            max_cw = max(max_cw, cur_w)
        else:
            cur_l += 1
            cur_w = 0
            max_cl = max(max_cl, cur_l)

    # -- Return distribution ----------------------------------------------------
    ret_min = min(eco_rets) if eco_rets else None
    ret_median = median(eco_rets) if eco_rets else None
    ret_mean = mean(eco_rets) if eco_rets else None
    ret_max = max(eco_rets) if eco_rets else None

    # -- Return by decision type ------------------------------------------------
    by_type: dict[str, list[float]] = defaultdict(list)
    by_type_correct: dict[str, list[bool]] = defaultdict(list)
    for r in scored:
        decision = r.decision or "NO_DECISION"
        by_type[decision].append(_economic_return(r))
        by_type_correct[decision].append(r.decision_correct)

    return_by_dt: dict[str, EconomicReturnStats] = {}
    for dt in sorted(by_type):
        rets = by_type[dt]
        masks = by_type_correct[dt]
        c = sum(masks)
        inc = len(masks) - c
        return_by_dt[dt] = EconomicReturnStats(
            count=len(rets),
            correct_count=c,
            incorrect_count=inc,
            total_return_pct=sum(rets),
            mean_return_pct=mean(rets) if rets else None,
            min_return_pct=min(rets) if rets else None,
            max_return_pct=max(rets) if rets else None,
        )

    # -- Positive expected value? -----------------------------------------------
    positive_ev = expectancy > 0 if expectancy is not None else None

    return EconomicSummary(
        total_scored=len(scored),
        correct_count=n_correct,
        incorrect_count=n_incorrect,
        avg_return_correct_pct=avg_correct,
        avg_return_incorrect_pct=avg_incorrect,
        expectancy_pct=expectancy,
        profit_factor=profit_factor,
        payoff_ratio=payoff_ratio,
        max_consecutive_wins=max_cw,
        max_consecutive_losses=max_cl,
        return_min_pct=ret_min,
        return_median_pct=ret_median,
        return_mean_pct=ret_mean,
        return_max_pct=ret_max,
        return_by_decision_type=return_by_dt or None,
        positive_expected_value=positive_ev,
    )


def format_economic_summary(summary: EconomicSummary, title: str = "Economic Validation") -> str:
    """Human-readable rendering of an ``EconomicSummary``."""
    lines: list[str] = []
    _w = lines.append

    _w(f"  --- {title} ---")
    _w(f"  Scored events:      {summary.total_scored}")
    _w(f"  Correct:            {summary.correct_count}")
    _w(f"  Incorrect:          {summary.incorrect_count}")

    _w("")
    _w(f"  Avg return/correct:   {_pct(summary.avg_return_correct_pct)}")
    _w(f"  Avg return/incorrect: {_pct(summary.avg_return_incorrect_pct)}")
    _w(f"  Expectancy:           {_pct(summary.expectancy_pct)}")
    _w(f"  Profit factor:        {_fmt(summary.profit_factor)}")
    _w(f"  Payoff ratio:         {_fmt(summary.payoff_ratio)}")

    _w("")
    _w(f"  Max consec. wins:   {summary.max_consecutive_wins}")
    _w(f"  Max consec. losses: {summary.max_consecutive_losses}")

    _w("")
    _w(f"  Return distribution ({_pct(summary.return_min_pct)} / "
       f"{_pct(summary.return_median_pct)} / "
       f"{_pct(summary.return_mean_pct)} / "
       f"{_pct(summary.return_max_pct)})")
    _w(f"    (min / median / mean / max)")

    if summary.return_by_decision_type:
        _w("")
        _w("  Return by decision type:")
        _w(f"    {'Decision':<20} {'Count':>6} {'Correct':>8} {'Wrong':>6}"
           f" {'Total':>10} {'Mean':>10}")
        _w("    " + "-" * 60)
        for dt, stats in summary.return_by_decision_type.items():
            _w(f"    {dt:<20} {stats.count:>6} {stats.correct_count:>8}"
               f" {stats.incorrect_count:>6}"
               f" {_pct(stats.total_return_pct):>10}"
               f" {_pct(stats.mean_return_pct):>10}")

    _w("")
    verdict = "YES" if summary.positive_expected_value else "NO"
    _w(f"  Positive expected value: {verdict}")

    return "\n".join(lines)


def _pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val:+.2f}%" if abs(val) > 0.0001 else "0.00%"


def _fmt(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val:.4f}"
