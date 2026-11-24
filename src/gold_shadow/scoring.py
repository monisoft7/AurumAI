"""Descriptive paper performance, using only resolved fills for returns."""
from collections import Counter
from statistics import fmean


def metrics(records, clocks):
    resolved = [r["net_r"] for r in records if r["net_r"] is not None]
    wins = sum(r > 0 for r in resolved)
    losses = -sum(min(r, 0) for r in resolved)
    peak = total = drawdown = 0.0
    for r in resolved:
        total += r
        peak = max(peak, total)
        drawdown = max(drawdown, peak - total)
    return {
        "clocks": clocks, "signals": len(records), "signals_per_100_clocks": round(100 * len(records) / clocks, 2) if clocks else None,
        "filled": sum(r["filled"] for r in records), "closed": len(resolved),
        "fill_rate": round(fmean(r["filled"] for r in records), 4) if records else None,
        "win_rate": round(wins / len(resolved), 4) if resolved else None,
        "false_signal_rate_net_loss": round(sum(r < 0 for r in resolved) / len(resolved), 4) if resolved else None,
        "expectancy_net_r": round(fmean(resolved), 4) if resolved else None,
        "profit_factor": round(sum(max(r, 0) for r in resolved) / losses, 4) if losses else None,
        "max_drawdown_r": round(drawdown, 4) if resolved else None,
        "net_r": round(total, 4), "outcomes": dict(Counter(r["status"] for r in records)),
    }
