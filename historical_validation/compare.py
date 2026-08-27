"""Historical Validation Run 001 -- cross-variant comparison utilities.

Since the boundary correction, variant EXECUTION lives in
``historical_validation.pure_path`` (the pure historical inference chain --
no orchestrator, no W3 pre-market, no fetchers, no writes).  This module
keeps the shared serialization / numeric-leaf / cross-variant comparison
contract used by the focused tests and the pilot runner.
"""

from __future__ import annotations

import re
from typing import Any

from .pure_path import (  # re-exported for existing consumers
    HISTORICAL_METADATA_KEYS,
    _serialize,
    numeric_leaves,
    run_variant,
)
from .spec import TRACE_ID

__all__ = [
    "TRACE_ID",
    "HISTORICAL_METADATA_KEYS",
    "numeric_leaves",
    "numeric_leaf_comparison",
    "run_variant",
    "compare_variants",
]

# uuid-derived identity tokens (th_/er_/ec_/tc_...) differ BETWEEN runs but
# never carry meaning; normalize them so numeric comparison keys are stable.
_VOLATILE_ID_TOKEN = re.compile(r"\b[a-z]{2}_[0-9a-f]{8,}\b")


def _normalized_leaves(leaves: dict[str, float]) -> dict[str, float]:
    return {
        _VOLATILE_ID_TOKEN.sub("<id>", path): value
        for path, value in leaves.items()
    }


def numeric_leaf_comparison(payload: Any) -> dict[str, float]:
    """Numeric leaves with uuid-derived identity tokens normalized away.

    Identity tokens (th_/er_/... + hex) differ BETWEEN runs without carrying
    meaning; normalization keeps the measured values comparable by stable
    path.
    """
    return _normalized_leaves(numeric_leaves(payload))


def compare_variants(full: dict[str, Any], no_history: dict[str, Any]) -> dict[str, Any]:
    """Empirically diff the two variants; nothing is assumed."""

    def _strip_volatile(payload: dict[str, Any]) -> dict[str, Any]:
        cleaned = dict(payload)
        cleaned.pop("serialized_outputs", None)
        return cleaned

    full_nums = _normalized_leaves(numeric_leaves(full["serialized_outputs"]))
    nohist_nums = _normalized_leaves(
        numeric_leaves(no_history["serialized_outputs"])
    )

    differing_paths = sorted(
        {
            path
            for path in set(full_nums) | set(nohist_nums)
            if full_nums.get(path) != nohist_nums.get(path)
        }
    )
    full_only = sorted(set(full_nums) - set(nohist_nums))
    nohist_only = sorted(set(nohist_nums) - set(full_nums))

    thesis_changed = (
        full["selected_thesis_direction"] != no_history["selected_thesis_direction"]
        or full["evaluated_thesis_directions"]
        != no_history["evaluated_thesis_directions"]
        or full["institutional_support_by_direction"]
        != no_history["institutional_support_by_direction"]
        or full["confidence_payload_summary"]
        != no_history["confidence_payload_summary"]
    )
    confidence_changed = (
        full["institutional_confidence"] != no_history["institutional_confidence"]
        or full["confidence_payload_summary"]
        != no_history["confidence_payload_summary"]
    )
    composite_changed = differing_paths != [] or full_only != [] or nohist_only != []
    decision_changed = (
        full["decision"] != no_history["decision"]
        or full["decision_risk_reward_summary"] != no_history["decision_risk_reward_summary"]
    )

    return {
        "trace_id": TRACE_ID,
        "history_changed_thesis": thesis_changed,
        "history_changed_confidence": confidence_changed,
        "history_changed_composite": composite_changed,
        "history_changed_decision": decision_changed,
        "numeric_leaf_count_full": len(full_nums),
        "numeric_leaf_count_no_history": len(nohist_nums),
        "numeric_diff_paths": differing_paths[:50],
        "numeric_only_in_full": full_only[:50],
        "numeric_only_in_no_history": nohist_only[:50],
        "full_summary": _strip_volatile(full),
        "no_history_summary": _strip_volatile(no_history),
    }
