from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class MacroEvent(ABC):
    """A macroeconomic event type that plugs into the Knowledge Engine.

    Every concrete event (CPI, NFP, FOMC, PPI, PMI, GDP, DXY, Yields …)
    implements this interface so the LessonBuilder, Knowledge Builder, and
    Brain can operate on it without knowing its internal details.
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

    @abstractmethod
    def load_and_extract(self, path: Path) -> pd.DataFrame:
        """Load raw event data from *path* and return a DataFrame that
        includes at least a ``Date`` column plus every column listed in
        *condition_columns* together with any other feature columns
        the event wishes to attach to its lessons.

        Must raise ``ValueError`` with a descriptive message if required
        columns are missing from the source data.
        """

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
