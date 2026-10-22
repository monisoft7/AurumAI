"""Validated, append-only daily gold history provider.

Maintains the local gold OHLCV history (``data/history/gold/gold.csv``) used by
the forecast pipeline. Implements the ``GOLD_DATA_PROVIDER_V1`` design:

  - default source: yfinance ``GC=F`` futures;
  - optional separate spot source: Twelve Data ``XAU/USD`` daily OHLC;
  - forward-only merge: existing rows are never modified or dropped;
  - never shrink: a truncated or shorter remote payload never truncates the file;
  - validation: schema, chronology, duplicate dates, missing dates, invalid prices,
    non-shrink, continuity;
  - atomic commit via a sibling temp file + ``os.replace``;
  - fail-safe: on any failure the previous dataset is preserved and the caller
    (the runtime entry point) continues with the existing data.

Each configured source writes its own CSV path (plus a sibling backup on
successful refresh). The caller must never reuse the futures CSV path for spot.
"""

from __future__ import annotations

import datetime
import logging
import os
import json
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

LOG = logging.getLogger("aurumai.gold_provider")

DEFAULT_GOLD_CSV = "data/history/gold/gold.csv"
GOLD_TICKER = "GC=F"
SOURCE_LABEL = f"yfinance:{GOLD_TICKER}"
SPOT_SOURCE_LABEL = "twelvedata:XAU/USD"
SPOT_API_KEY_ENV = "TWELVE_DATA_API_KEY"
SCHEMA_COLUMNS = ("Date", "Close", "High", "Low", "Open", "Volume")
PRICE_COLUMNS = ("Close", "High", "Low", "Open")


@dataclass(frozen=True)
class GoldRefreshReport:
    status: str
    rows_before: int
    rows_after: int
    rows_added: int
    last_date_before: str | None
    last_date_after: str | None
    source: str
    timestamp: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "rows_before": self.rows_before,
            "rows_after": self.rows_after,
            "rows_added": self.rows_added,
            "last_date_before": self.last_date_before,
            "last_date_after": self.last_date_after,
            "source": self.source,
            "timestamp": self.timestamp,
            "message": self.message,
        }


class GoldDataProvider:
    """Refreshes the local gold history from a market-data source.

    A ``fetcher`` callable (``() -> pd.DataFrame``) can be injected for tests;
    the default fetcher downloads ``GC=F`` full history from yfinance.
    """

    def __init__(
        self,
        path: str | Path = DEFAULT_GOLD_CSV,
        fetcher: Callable[[], pd.DataFrame] | None = None,
        logger: logging.Logger | None = None,
        source: str = SOURCE_LABEL,
    ) -> None:
        self._path = Path(path)
        self._fetcher = fetcher
        self._log = logger or LOG
        self._source = source

    # ------------------------------------------------------------------ public

    def refresh(self) -> GoldRefreshReport:
        """Refresh the local gold history. Never raises; never loses data.

        Status values: ``ok`` (committed or already current), ``skipped``
        (remote unavailable/empty; previous dataset preserved), ``failed``
        (validation or commit failure; previous dataset preserved).
        """
        try:
            return self._refresh()
        except Exception as exc:  # pragma: no cover - last-resort guard
            self._log.error(
                "gold provider: unexpected refresh failure (%s); "
                "keeping existing dataset", exc,
            )
            return GoldRefreshReport(
                status="failed",
                rows_before=0,
                rows_after=0,
                rows_added=0,
                last_date_before=None,
                last_date_after=None,
                source=self._source,
                timestamp=_utc_now_iso(),
                message=f"unexpected failure: {exc}",
            )

    # ------------------------------------------------------------------ steps

    def _refresh(self) -> GoldRefreshReport:
        timestamp = _utc_now_iso()

        local, load_error = self._load_local()
        if load_error is not None:
            self._log.error("gold provider: %s; keeping existing dataset", load_error)
            return GoldRefreshReport(
                status="failed", rows_before=0, rows_after=0, rows_added=0,
                last_date_before=None, last_date_after=None, source=self._source,
                timestamp=timestamp, message=load_error,
            )

        rows_before = 0 if local is None else len(local)
        first_before = (
            None if local is None or len(local) == 0
            else self._date_str(local["Date"].iloc[0])
        )
        last_before = (
            None if local is None or len(local) == 0
            else self._date_str(local["Date"].iloc[-1])
        )

        try:
            remote = self._fetch_remote()
        except Exception as exc:
            message = f"fetch failed: {exc}"
            self._log.warning("gold provider: %s; keeping existing dataset", message)
            return self._preserved(timestamp, "skipped", rows_before,
                                    last_before, message)

        try:
            remote = self._normalize(remote)
            # A daily futures bar can be revised until its session closes.
            # The exchange session calendar is not recorded here, so use the
            # conservative UTC-date boundary for the default live feed.
            if self._fetcher is None:
                today_utc = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
                remote = remote.loc[remote["Date"] < today_utc].reset_index(drop=True)
        except Exception as exc:
            message = f"remote payload invalid: {exc}"
            self._log.warning("gold provider: %s; keeping existing dataset", message)
            return self._preserved(timestamp, "skipped", rows_before,
                                    last_before, message)

        if len(remote) == 0:
            message = "empty remote payload; nothing to merge"
            self._log.warning("gold provider: %s; keeping existing dataset", message)
            return self._preserved(timestamp, "skipped", rows_before,
                                    last_before, message)

        if local is None or len(local) == 0:
            merged = remote.reset_index(drop=True)
            rows_added = len(merged)
        else:
            local_norm = self._normalize(local)
            merged, rows_added = self._merge(local_norm, remote)

        errors = self._validate(merged, rows_before, first_before, last_before)
        if errors:
            message = "validation failed: " + "; ".join(errors)
            self._log.error("gold provider: %s; keeping existing dataset", message)
            return self._preserved(timestamp, "failed", rows_before,
                                    last_before, message)

        rows_after = len(merged)
        last_after = self._date_str(merged["Date"].iloc[-1])

        if rows_added == 0:
            self._log.info(
                "gold provider: no new market data (rows %d, last %s)",
                rows_after, last_after,
            )
            return GoldRefreshReport(
                status="ok", rows_before=rows_before, rows_after=rows_after,
                rows_added=0, last_date_before=last_before,
                last_date_after=last_after, source=self._source,
                timestamp=timestamp, message="already current",
            )

        try:
            self._commit(merged)
        except Exception as exc:
            message = f"atomic commit failed: {exc}"
            self._log.error("gold provider: %s; keeping existing dataset", message)
            return self._preserved(timestamp, "failed", rows_before,
                                    last_before, message)

        self._log.info(
            "gold provider: refreshed %s rows %d -> %d (+%d), last date %s -> %s",
            self._path, rows_before, rows_after, rows_added, last_before, last_after,
        )
        return GoldRefreshReport(
            status="ok", rows_before=rows_before, rows_after=rows_after,
            rows_added=rows_added, last_date_before=last_before,
            last_date_after=last_after, source=self._source,
            timestamp=timestamp, message="refreshed",
        )

    # ------------------------------------------------------------------ pieces

    def _preserved(
        self,
        timestamp: str,
        status: str,
        rows_before: int,
        last_before: str | None,
        message: str,
    ) -> GoldRefreshReport:
        return GoldRefreshReport(
            status=status, rows_before=rows_before, rows_after=rows_before,
            rows_added=0, last_date_before=last_before,
            last_date_after=last_before, source=self._source,
            timestamp=timestamp, message=message,
        )

    def _load_local(self) -> tuple[pd.DataFrame | None, str | None]:
        if not self._path.exists():
            return None, None
        try:
            df = pd.read_csv(self._path)
        except Exception as exc:
            return None, f"local history unreadable ({self._path}): {exc}"
        return df, None

    def _fetch_remote(self) -> pd.DataFrame:
        if self._fetcher is not None:
            return self._fetcher()
        import yfinance as yf

        data = yf.download(
            GOLD_TICKER, period="max", progress=False, auto_adjust=True,
        )
        if data is None:
            return pd.DataFrame()
        if hasattr(data.columns, "droplevel"):
            try:
                data = data.droplevel(1, axis=1)
            except Exception:
                pass
        return data

    @classmethod
    def _normalize(cls, frame: pd.DataFrame) -> pd.DataFrame:
        if frame is None or len(frame) == 0:
            return pd.DataFrame(columns=list(SCHEMA_COLUMNS))
        df = frame.copy()
        if "Date" not in df.columns:
            if isinstance(df.index, pd.DatetimeIndex):
                df = df.reset_index()
            elif df.index.name:
                df = df.reset_index(names=df.index.name)
            else:
                raise ValueError("frame has no Date column or datetime index")
        missing = [c for c in PRICE_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"frame missing required columns: {missing}")
        if "Volume" not in df.columns:
            df["Volume"] = np.nan
        df = df[list(SCHEMA_COLUMNS)].copy()
        df["Date"] = df["Date"].map(cls._date_str)
        for col in PRICE_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")
        df = df.sort_values("Date")
        df = df.drop_duplicates(subset="Date", keep="first")
        return df.reset_index(drop=True)

    @staticmethod
    def _date_str(value: Any) -> str:
        if isinstance(value, pd.Timestamp):
            return value.date().isoformat()
        if isinstance(value, datetime.datetime):
            return value.date().isoformat()
        if isinstance(value, datetime.date):
            return value.isoformat()
        return str(value)[:10]

    @staticmethod
    def _merge(
        local: pd.DataFrame,
        remote: pd.DataFrame,
    ) -> tuple[pd.DataFrame, int]:
        """Append new dates and finalize the previous latest bar on rollover.

        A changed last local row is accepted only when the remote feed also
        contains a later completed date. Older committed rows stay frozen.
        """
        local_min = str(local["Date"].iloc[0])
        local_max = str(local["Date"].iloc[-1])
        local_dates = set(local["Date"])
        forward = remote["Date"] > local_max
        gaps = (
            (remote["Date"] >= local_min)
            & (remote["Date"] < local_max)
            & (~remote["Date"].isin(local_dates))
        )
        added = remote[forward | gaps]
        if len(added) == 0:
            return local.reset_index(drop=True), 0
        # The former latest row may have been provisional when first stored.
        # Reconcile it only after a newer daily bar proves rollover.
        replacement = remote.loc[remote["Date"] == local_max]
        if not replacement.empty and bool(forward.any()):
            base = local.loc[local["Date"] != local_max]
            merged = pd.concat([base, replacement, added], ignore_index=True)
        else:
            merged = pd.concat([local, added], ignore_index=True)
        merged = merged.sort_values("Date")
        merged = merged.drop_duplicates(subset="Date", keep="first")
        return merged.reset_index(drop=True), len(added)

    @classmethod
    def _validate(
        cls,
        merged: pd.DataFrame,
        rows_before: int,
        first_before: str | None,
        last_before: str | None,
    ) -> list[str]:
        errors: list[str] = []

        if list(merged.columns) != list(SCHEMA_COLUMNS):
            errors.append(
                f"schema mismatch: got {list(merged.columns)}, "
                f"expected {list(SCHEMA_COLUMNS)}"
            )
        if merged.empty:
            errors.append("merged frame is empty")
            return errors

        dates = pd.to_datetime(merged["Date"], errors="coerce")
        if merged["Date"].isna().any() or dates.isna().any():
            errors.append("missing or unparseable dates present")
        else:
            if dates.duplicated().any():
                errors.append("duplicate dates present")
            if not dates.is_monotonic_increasing:
                errors.append("dates out of chronological order")

        for col in PRICE_COLUMNS:
            values = merged[col]
            if values.isna().any():
                errors.append(f"{col} contains missing values")
            if not np.isfinite(values.to_numpy(dtype="float64")).all():
                errors.append(f"{col} contains non-finite values")

        prices = merged[list(PRICE_COLUMNS)]
        if (prices <= 0).any().any():
            errors.append("non-positive prices present")
        if (merged["High"] < merged[["Open", "Close"]].max(axis=1)).any():
            errors.append("High below Open/Close")
        if (merged["Low"] > merged[["Open", "Close"]].min(axis=1)).any():
            errors.append("Low above Open/Close")

        if rows_before > 0:
            if len(merged) < rows_before:
                errors.append(f"dataset shrank: {len(merged)} < {rows_before}")
            merged_dates = set(merged["Date"])
            if last_before is not None and last_before not in merged_dates:
                errors.append(f"prior last date {last_before} missing after merge")
            if first_before is not None and merged["Date"].iloc[0] != first_before:
                errors.append(f"first date changed: {merged['Date'].iloc[0]} != {first_before}")
            if last_before is not None and merged["Date"].iloc[-1] < last_before:
                errors.append(f"last date moved backward from {last_before}")

        return errors

    def _commit(self, frame: pd.DataFrame) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        frame.to_csv(tmp, index=False)
        try:
            if self._path.exists():
                backup = self._path.with_name(self._path.name + ".bak")
                backup.write_text(
                    self._path.read_text(encoding="utf-8"), encoding="utf-8",
                )
            os.replace(tmp, self._path)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def refresh_gold_data(
    path: str | Path = DEFAULT_GOLD_CSV,
    logger: logging.Logger | None = None,
    provider: str = "yfinance_futures",
) -> GoldRefreshReport:
    """Convenience entry point for the runtime entry scripts."""
    if provider == "yfinance_futures":
        return GoldDataProvider(path=path, logger=logger).refresh()
    if provider == "twelvedata_spot":
        if Path(path).name != "xauusd_spot.csv":
            raise ValueError("spot provider requires a dedicated xauusd_spot.csv path")
        return GoldDataProvider(
            path=path, fetcher=fetch_twelvedata_spot_history,
            logger=logger, source=SPOT_SOURCE_LABEL,
        ).refresh()
    raise ValueError(f"unsupported gold provider: {provider}")


def fetch_twelvedata_spot_history(*, now: datetime.datetime | None = None) -> pd.DataFrame:
    """Fetch completed daily XAU/USD bars; credentials never enter the report."""
    key = os.environ.get(SPOT_API_KEY_ENV, "").strip()
    if not key:
        raise RuntimeError(f"{SPOT_API_KEY_ENV} is missing")
    as_of = now or datetime.datetime.now(datetime.timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError("spot history clock must be timezone-aware")
    yesterday = as_of.astimezone(datetime.timezone.utc).date() - datetime.timedelta(days=1)
    params = urllib.parse.urlencode({
        "symbol": "XAU/USD", "interval": "1day", "start_date": "2015-01-01",
        # A date-only end_date is interpreted at midnight and excludes that
        # day's bar. Include the full previous UTC day, never today's open bar.
        "end_date": f"{yesterday.isoformat()} 23:59:59", "outputsize": 5000,
        "apikey": key,
    })
    request = urllib.request.Request(
        f"https://api.twelvedata.com/time_series?{params}",
        headers={"User-Agent": "AurumAI/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Twelve Data HTTP {exc.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("Twelve Data connection unavailable") from None
    except Exception:
        # urllib errors may contain the URL and its API key.
        raise RuntimeError("Twelve Data request failed") from None
    if not isinstance(payload, dict) or payload.get("status") == "error":
        raise RuntimeError("Twelve Data returned an error or invalid payload")
    meta = payload.get("meta")
    if not isinstance(meta, dict) or str(meta.get("symbol", "")).upper() != "XAU/USD":
        raise RuntimeError("Twelve Data instrument did not match XAU/USD")
    values = payload.get("values")
    if not isinstance(values, list) or not values:
        raise RuntimeError("Twelve Data returned no daily bars")
    frame = pd.DataFrame(values).rename(columns={
        "datetime": "Date", "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume",
    })
    if "Date" not in frame or pd.to_datetime(frame["Date"], errors="coerce").isna().any():
        raise RuntimeError("Twelve Data returned invalid bar dates")
    if (pd.to_datetime(frame["Date"]).dt.date > yesterday).any():
        raise RuntimeError("Twelve Data returned an unfinished daily bar")
    return frame
