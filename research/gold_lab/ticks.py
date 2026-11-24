"""Chronological executable-side tick settlement, shared by audit and forward paper orders."""

import numpy as np


def settle(times, bids, asks, start, plan, until, slip=0.10):
    """Milliseconds in UTC. A long enters on ask and exits on bid. Missing path stays unknown."""
    # A late limit fill may need the first executable quote just past hour five.
    stop_at = min(until, start + 5 * 3600000 + 300001)
    left, right = times.searchsorted([start, stop_at], side="left")
    t, b, a = times[left:right], bids[left:right], asks[left:right]
    side = 1 if plan.action.startswith("BUY") else -1
    entry = a if side == 1 else -b
    exit_side = b if side == 1 else -a
    failure = np.flatnonzero(np.diff(t, prepend=start) > 300000)
    gap = int(t[failure[0]]) if len(failure) else None

    def observed(end):
        if gap is not None and gap <= end:
            return False
        j = t.searchsorted(end, side="right")
        return end - (t[j - 1] if j else start) <= 300000

    expiry = start + 3600000
    eligible = t.searchsorted(expiry)
    if plan.action.endswith("LIMIT"):
        hit = np.flatnonzero(entry[:eligible] <= side * plan.entry)
        idx = int(hit[0]) if len(hit) else None
    elif plan.action.endswith("NOW"):
        idx = 0 if eligible else None
    else:
        raise ValueError("unsupported research order")
    if idx is None:
        end = min(until, expiry)
        status = "expired" if until >= expiry else "pending"
        return {
            "status": status if observed(end) else "unobserved",
            "net_r": None,
            "filled": False,
            "end": int(end),
        }
    fill_time = int(t[idx])
    if not observed(fill_time):
        return {
            "status": "unobserved",
            "net_r": None,
            "filled": False,
            "end": fill_time,
        }
    fill = float(entry[idx]) + (slip if plan.action.endswith("NOW") else 0.0)
    entry_details = {"fill_ms": fill_time, "fill_price": side * fill}
    deadline = fill_time + 4 * 3600000
    before = int(t.searchsorted(deadline))
    quotes = exit_side[idx:before]
    hit = np.flatnonzero((quotes <= side * plan.stop) | (quotes >= side * plan.target))
    if len(hit):
        j = idx + int(hit[0])
        end = int(t[j])
        target = exit_side[j] >= side * plan.target
        status, price = (
            ("target", side * plan.target) if target else ("stop", exit_side[j] - slip)
        )
    elif before < len(t):
        end = int(t[before])
        status, price = "timeout", exit_side[before] - slip
    else:
        end = min(until, deadline)
        # At timeout wait for the next executable quote; a long outage censors it.
        status = "pending" if until - deadline <= 300000 else "unobserved"
        return {
            "status": status if observed(end) else "unobserved",
            "net_r": None,
            "filled": True,
            "end": int(end),
            **entry_details,
        }
    status = status if observed(end) else "unobserved"
    return {
        "status": status,
        "net_r": float((price - fill) / abs(plan.entry - plan.stop))
        if status != "unobserved"
        else None,
        "filled": True,
        "end": end,
        "exit_price": float(side * price) if status != "unobserved" else None,
        **entry_details,
    }
