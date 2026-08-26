"""Reference price resolution for the W14 recommendation boundary.

Resolves the latest *valid* XAU/USD close available at run time from the
run's own committed gold data.  Pure function of the data file (+ optional
as-of bound): no network, no hard-coded prices, no invention.  When no
valid price can be resolved the caller receives ``(None, reason)`` and must
announce the relative-anchor fallback instead of fabricating a price.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReferencePrice:
    """A resolved absolute reference price plus its provenance."""

    value: float
    method: str
    source_path: str
    source_data_hash: str
    bar_date: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "method": self.method,
            "source_path": self.source_path,
            "source_data_hash": self.source_data_hash,
            "bar_date": self.bar_date,
        }


def _find_column(columns: list[str], canonical: str) -> str | None:
    lowered = {str(c).strip().lower(): c for c in columns}
    return lowered.get(canonical)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_reference_price(
    gold_path: str | None,
    as_of: str | None = None,
) -> tuple[ReferencePrice | None, str]:
    """Return ``(ReferencePrice, "")`` or ``(None, reason)``.

    ``as_of`` bounds the search historically: the latest valid close at or
    before the given timestamp is used, so historical replays stay as-of safe.
    This function never raises: any failure degrades to an explicit reason.
    """
    if not gold_path:
        return None, "gold_path_not_set"
    path = Path(gold_path)
    if not path.is_file():
        return None, f"gold_path_not_found: {gold_path}"

    try:
        import pandas as pd

        try:
            frame = pd.read_csv(path)
        except Exception:
            return None, f"gold_csv_unreadable: {path.name}"

        date_col = _find_column(list(frame.columns), "date")
        close_col = _find_column(list(frame.columns), "close")
        if close_col is None:
            return None, "missing_close_column"
        if date_col is None:
            return None, "missing_date_column"

        dates = pd.to_datetime(frame[date_col], errors="coerce")
        closes = pd.to_numeric(frame[close_col], errors="coerce")
        valid = dates.notna() & closes.notna()
        frame = pd.DataFrame(
            {"bar_date": dates[valid], "bar_close": closes[valid]}
        ).sort_values("bar_date")

        if as_of is not None:
            try:
                boundary = pd.Timestamp(str(as_of))
                if boundary.tzinfo is not None:
                    boundary = boundary.tz_convert(None)
            except (ValueError, TypeError):
                return None, f"unparseable_as_of: {as_of}"
            index = (
                frame["bar_date"].dt.tz_localize(None)
                if frame["bar_date"].dt.tz is not None
                else frame["bar_date"]
            )
            frame = frame.loc[index <= boundary]

        if frame.empty:
            return None, "no_valid_rows"

        # Latest *valid* close: scan backwards past any non-finite or
        # non-positive leftovers rather than inventing a substitute.
        for row in frame.iloc[::-1].itertuples(index=False):
            value = float(row.bar_close)
            if value != value or value in (float("inf"), float("-inf")):
                continue
            if value <= 0.0:
                continue
            bar_date = pd.Timestamp(row.bar_date).isoformat()
            provenance = ReferencePrice(
                value=value,
                method="last_valid_close",
                source_path=str(path),
                source_data_hash=_file_sha256(path),
                bar_date=bar_date,
            )
            return provenance, ""

        return None, "no_valid_positive_close"
    except Exception as exc:  # pragma: no cover - absolute fail-safe boundary
        return None, f"reference_price_resolution_failed: {exc}"
