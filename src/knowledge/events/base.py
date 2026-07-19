from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from knowledge.events.release_calendar import ReleaseCalendar


@dataclass(frozen=True)
class StandardEventMetadata:
    """Optional institutional metadata for a MacroEvent.

    Every future MacroEvent implementation should provide these fields to
    standardize economic calendar representation across all event types.
    Existing implementations that predate this standard (e.g., CPIEvent)
    return None from the metadata property; new implementations SHOULD
    return a populated instance.

    Fields follow the de facto industry schema used by TradingEconomics,
    OpenBB EconomicCalendar, and similar economic calendar data providers.

    Parameters
    ----------
    country:
        ISO country code or name. Example: ``"US"``.
    currency:
        ISO 4217 currency code. Example: ``"USD"``.
    unit:
        Measurement unit. Example: ``"percent"``, ``"index"``, ``"points"``.
    importance:
        Market impact level. 1 = low, 2 = medium, 3 = high.
    source:
        Publishing authority. Example: ``"Bureau of Labor Statistics"``.
    reference_period_type:
        Frequency of the data. Example: ``"monthly"``, ``"quarterly"``,
        ``"annual"``.
    """

    country: str | None = None
    currency: str | None = None
    unit: str | None = None
    importance: int | None = None
    source: str | None = None
    reference_period_type: str | None = None


class MacroEvent(ABC):
    """A macroeconomic event type that plugs into the Knowledge Engine.

    Every concrete event (CPI, NFP, FOMC, PPI, PMI, GDP, DXY, Yields …)
    implements this interface so the LessonBuilder, Knowledge Builder, and
    Brain can operate on it without knowing its internal details.

    New implementations SHOULD also override *metadata* to declare the
    standard economic calendar fields documented in StandardEventMetadata.
    """

    @property
    @abstractmethod
    def event_type(self) -> str:
        """Short identifier used as a column value in every lesson.
        Example: 'CPI', 'NFP', 'FOMC'."""

    @property
    @abstractmethod
    def lesson_version(self) -> str:
        """Version string written into every lesson this event produces.
        Example: 'cpi_gold_v1'."""

    @property
    @abstractmethod
    def condition_columns(self) -> list[str]:
        """Column names the Knowledge Builder uses to group lessons into
        knowledge records.  Each column becomes a dimension in the
        condition dict and the knowledge_id suffix.
        Example for CPI: ['cpi_pressure']."""

    @property
    @abstractmethod
    def knowledge_version(self) -> str:
        """Knowledge version namespace used by Memory and the Brain.
        This is the key under which knowledge records are stored.
        Example: 'cpi_gold_summary_v1'."""

    @property
    def metadata(self) -> StandardEventMetadata | None:
        """Optional standard economic event metadata.

        Returns None by default for backward compatibility with event types
        that predate this standard. New implementations SHOULD return a
        StandardEventMetadata instance describing the event's fixed
        institutional properties (country, currency, unit, importance,
        source, reference_period_type).
        """
        return None

    @abstractmethod
    def load_and_extract(self, path: Path) -> pd.DataFrame:
        """Load raw event data from *path* and return a DataFrame that
        includes at least a ``Date`` column plus every column listed in
        *condition_columns* together with any other feature columns
        the event wishes to attach to its lessons.

        Must raise ``ValueError`` with a descriptive message if required
        columns are missing from the source data.
        """

    def load_and_extract_with_calendar(
        self,
        path: Path,
        release_calendar: ReleaseCalendar | None = None,
    ) -> pd.DataFrame:
        """Load event data and enrich with release/vintage metadata.

        When *release_calendar* is provided, adds ``release_timestamp``,
        ``reference_period``, and ``release_timezone`` columns. Raises
        ``ValueError`` if any row's reference period is missing from the
        calendar.

        The default implementation calls ``load_and_extract(path)`` and
        enriches the result. Subclasses may override for efficiency.
        """
        df = self.load_and_extract(path)
        if release_calendar is None:
            return df
        return self._enrich_with_calendar(df, release_calendar)

    def _enrich_with_calendar(
        self,
        df: pd.DataFrame,
        calendar: ReleaseCalendar,
    ) -> pd.DataFrame:
        df = df.copy()
        ref_col = "reference_period"
        if ref_col not in df.columns:
            df[ref_col] = df["Date"].dt.strftime("%Y-%m-%d")

        matched: list[int] = []
        timestamps: list[Any] = []
        for idx, (_, row) in enumerate(df.iterrows()):
            ref = str(row[ref_col])
            rec = calendar.get(ref)
            if rec is not None:
                matched.append(idx)
                timestamps.append(rec.release_timestamp_et)

        if not matched:
            raise ValueError(
                "Release calendar matched zero reference periods"
            )

        df = df.iloc[matched].copy()
        df["release_timestamp"] = timestamps
        df["release_timezone"] = "US/Eastern"
        return df

    @abstractmethod
    def build_lesson_fields(
        self, event_row: pd.Series, anchor_date: str
    ) -> dict[str, object]:
        """Return event-specific fields for a single lesson.

        *event_row* is one row of the DataFrame returned by
        *load_and_extract*.  *anchor_date* is the ISO date of the first
        asset trading session on or after the event date.

        The returned dict is merged into the lesson alongside generic
        fields (asset returns, directions, etc.).
        """

    @abstractmethod
    def lesson_text(self, lesson: dict[str, object]) -> str:
        """Generate a human-readable explanation for this lesson.

        *lesson* is the complete lesson dict (event fields + generic
        fields) so the implementation can reference whichever columns
        it needs.
        """
