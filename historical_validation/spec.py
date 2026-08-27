"""Trace 044-B cohort specification constants.

Historical Validation Run 001 freezes the cohort definition to the EXACT
25-episode set defined by Trace 044-B:

    * sort episodes chronologically by ``event_date``
    * total episodes = 137
    * positions = ``round(137 * i / 26)`` for ``i = 1..25``
    * no random sampling

These values are documented provenance for the cohort and are intentionally
module-level constants so the selection algorithm cannot drift.
"""

from __future__ import annotations

TRACE_ID = "044-B"

TOTAL_EPISODES = 137
COHORT_SIZE = 25
POSITION_DENOMINATOR = 26  # round(TOTAL_EPISODES * i / POSITION_DENOMINATOR), i = 1..COHORT_SIZE

POSITIONS: tuple[int, ...] = tuple(
    round(TOTAL_EPISODES * i / POSITION_DENOMINATOR) for i in range(1, COHORT_SIZE + 1)
)

EVENT_DATE_SORT_KEY = "event_date"

# ---------------------------------------------------------------------------
# Baseline pinning (Sprint 064-A)
#
# POSITIONS define the canonical Trace 044-B selection ALGORITHM, but they
# are content-blind: any corpus growth silently re-maps mid-cohort positions
# to different episodes.  FROZEN_COHORT_IDS is the CONTENT WITNESS of the
# Run-001 baseline: position-derived selection must reproduce it exactly.
#
# A deliberate baseline upgrade must update this tuple AND
# ``baseline_manifest.json`` together (the guard fails loudly; nothing is
# upgraded automatically).
# ---------------------------------------------------------------------------

BASELINE_ID = "run001-trace044b-v1"

FROZEN_COHORT_IDS: tuple[str, ...] = (
    "CPI_GOLD_2015-06-01",
    "CPI_GOLD_2015-12-01",
    "CPI_GOLD_2016-05-01",
    "CPI_GOLD_2016-10-01",
    "CPI_GOLD_2017-03-01",
    "CPI_GOLD_2017-09-01",
    "CPI_GOLD_2018-02-01",
    "CPI_GOLD_2018-07-01",
    "CPI_GOLD_2018-12-01",
    "CPI_GOLD_2019-06-01",
    "CPI_GOLD_2019-11-01",
    "CPI_GOLD_2020-04-01",
    "CPI_GOLD_2020-09-01",
    "CPI_GOLD_2021-03-01",
    "CPI_GOLD_2021-08-01",
    "CPI_GOLD_2022-01-01",
    "CPI_GOLD_2022-07-01",
    "CPI_GOLD_2022-12-01",
    "CPI_GOLD_2023-05-01",
    "CPI_GOLD_2023-10-01",
    "CPI_GOLD_2024-04-01",
    "CPI_GOLD_2024-09-01",
    "CPI_GOLD_2025-02-01",
    "CPI_GOLD_2025-07-01",
    "CPI_GOLD_2026-02-01",
)
