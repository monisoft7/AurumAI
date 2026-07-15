from __future__ import annotations

from datetime import date as date_type, timedelta

from knowledge.temporal.state import TemporalState
from knowledge.temporal.period import TimePeriod
from knowledge.temporal.context import TimeContext


class TemporalIndexer:
    def __init__(self, context: TimeContext | None = None):
        self._context = context or TimeContext()
        self._entries: dict[str, list[TemporalState]] = {}
        self._all_sorted: list[TemporalState] = []
        self._dirty = True

    def index(self, state: TemporalState) -> None:
        self._entries.setdefault(state.date, []).append(state)
        self._dirty = True

    def index_many(self, states: list[TemporalState]) -> None:
        for s in states:
            self._entries.setdefault(s.date, []).append(s)
        self._dirty = True

    def _ensure_sorted(self) -> list[TemporalState]:
        if self._dirty:
            result: list[TemporalState] = []
            for date_str in sorted(self._entries):
                group = sorted(self._entries[date_str], key=lambda s: (s.source_type, s.source_id))
                result.extend(group)
            self._all_sorted = result
            self._dirty = False
        return self._all_sorted

    @property
    def context(self) -> TimeContext:
        return self._context

    def query_by_date(self, date: str) -> list[TemporalState]:
        return list(self._entries.get(date, []))

    def query_by_period(self, period: TimePeriod) -> list[TemporalState]:
        results: list[TemporalState] = []
        start = period.start_date
        end = period.end_date
        for ts in self._ensure_sorted():
            if period.inclusive_start and ts.date < start:
                continue
            if not period.inclusive_start and ts.date <= start:
                continue
            if period.inclusive_end and ts.date > end:
                continue
            if not period.inclusive_end and ts.date >= end:
                continue
            results.append(ts)
        return results

    def rolling_window(self, end_date: str, window_days: int) -> list[TemporalState]:
        results: list[TemporalState] = []
        try:
            end = date_type.fromisoformat(end_date)
            start = end - timedelta(days=window_days)
            start_str = start.isoformat()
        except (ValueError, TypeError):
            return results
        for ts in self._ensure_sorted():
            if start_str <= ts.date <= end_date:
                results.append(ts)
        return results

    def nearest_date(
        self,
        target: str,
        direction: str = "nearest",
    ) -> list[TemporalState]:
        all_states = self._ensure_sorted()
        if not all_states:
            return []

        target_dt = _parse_date(target)
        if target_dt is None:
            return []

        candidates: list[tuple[int, list[TemporalState]]] = []

        after_idx = _bisect_dates(all_states, target)
        if after_idx > 0:
            prev_idx = after_idx - 1
            prev_date = _parse_date(all_states[prev_idx].date)
            if prev_date is not None:
                diff = abs((target_dt - prev_date).days)
                group = _collect_same_date(all_states, prev_idx)
                candidates.append((diff, group))

        if after_idx < len(all_states):
            next_date = _parse_date(all_states[after_idx].date)
            if next_date is not None:
                diff = abs((target_dt - next_date).days)
                if next_date == target_dt:
                    diff = 0
                group = _collect_same_date(all_states, after_idx)
                candidates.append((diff, group))

        if direction == "before":
            candidates = [c for c in candidates if _parse_date(c[1][0].date) <= target_dt]
        elif direction == "after":
            candidates = [c for c in candidates if _parse_date(c[1][0].date) >= target_dt]
        elif direction == "exact":
            candidates = [c for c in candidates if _parse_date(c[1][0].date) == target_dt]

        if not candidates:
            return []

        min_diff = min(c[0] for c in candidates)
        best = [c[1] for c in candidates if c[0] == min_diff]
        if not best:
            return []
        return best[0]

    def date_range(self) -> tuple[str, str] | None:
        all_states = self._ensure_sorted()
        if not all_states:
            return None
        return all_states[0].date, all_states[-1].date

    def clear(self) -> None:
        self._entries.clear()
        self._all_sorted.clear()
        self._dirty = True

    def entry_count(self) -> int:
        return len(self._ensure_sorted())

    def source_type_count(self, source_type: str) -> int:
        return sum(1 for s in self._ensure_sorted() if s.source_type == source_type)


def _parse_date(d: str) -> date_type | None:
    try:
        return date_type.fromisoformat(d)
    except (ValueError, TypeError):
        return None


def _bisect_dates(states: list[TemporalState], target: str) -> int:
    lo, hi = 0, len(states)
    while lo < hi:
        mid = (lo + hi) // 2
        if states[mid].date < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _collect_same_date(states: list[TemporalState], idx: int) -> list[TemporalState]:
    d = states[idx].date
    result: list[TemporalState] = [states[idx]]
    i = idx - 1
    while i >= 0 and states[i].date == d:
        result.insert(0, states[i])
        i -= 1
    i = idx + 1
    while i < len(states) and states[i].date == d:
        result.append(states[i])
        i += 1
    return result
