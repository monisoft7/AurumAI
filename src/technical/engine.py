"""Technical computation engine abstraction.

The rest of AurumAI depends only on the ``TechnicalEngine`` protocol and on
the standardized indicator column names defined here.  The concrete engine
(pandas-ta-classic today, TA-Lib or anything else tomorrow) is swappable
without touching any caller.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import numpy as np
import pandas as pd

from technical.contracts import TechnicalDependencyError

# Standardized output columns -- these are the ONLY names allowed to escape
# the adapter.  Library-native column names never leave this module.
ENGINE_COLUMNS: tuple[str, ...] = (
    "ema_20",
    "ema_50",
    "ema_200",
    "rsi_14",
    "macd_line",
    "macd_signal_line",
    "macd_hist",
    "atr_14",
    "adx_14",
    "dmp_14",
    "dmn_14",
    "bb_lower",
    "bb_middle",
    "bb_upper",
    "bb_width",
    "roc_9",
)

REQUIRED_OHLC = ("high", "low", "close")


@runtime_checkable
class TechnicalEngine(Protocol):
    """Any indicator computation backend usable by the research desk."""

    name: str

    def compute(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        """Return one column per ``ENGINE_COLUMNS`` entry for ``ohlcv``."""
        ...


@dataclass(frozen=True)
class EngineInfo:
    name: str
    library_version: str


def _library_version() -> str:
    try:
        from importlib.metadata import version

        return version("pandas-ta-classic")
    except Exception:
        return "unknown"


def _force_native(fn: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Pin the library's pure-python implementation when it exposes a switch.

    pandas-ta-classic auto-uses TA-Lib's C backend for some indicators when
    that optional binary is installed.  Pinning the native path keeps results
    deterministic across machines with different optional dependencies.
    """
    try:
        if "talib" in inspect.signature(fn).parameters:
            kwargs.setdefault("talib", False)
    except (TypeError, ValueError):
        pass
    return kwargs


class PandasTaClassicEngine:
    """Adapter around pandas-ta-classic.

    Pure-python, MIT licensed, actively maintained fork of pandas-ta with an
    in-repo oracle test-suite against TA-Lib.  Import is lazy so the desk can
    degrade explicitly (TechnicalDependencyError) when the extra is absent.
    """

    def __init__(self) -> None:
        self.name = "pandas_ta_classic"
        self._ta = None

    @property
    def ta(self) -> Any:
        if self._ta is None:
            try:
                import pandas_ta_classic as ta
            except ImportError as exc:
                raise TechnicalDependencyError(
                    "pandas-ta-classic is not installed. Install the technical "
                    "extra: pip install aurumai[technical]  "
                    f"(underlying import error: {exc})"
                ) from exc
            self._ta = ta
        return self._ta

    def info(self) -> EngineInfo:
        return EngineInfo(name=self.name, library_version=_library_version())

    def compute(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        ta = self.ta
        high = ohlcv["high"]
        low = ohlcv["low"]
        close = ohlcv["close"]

        out = pd.DataFrame(index=ohlcv.index)

        out["ema_20"] = ta.ema(close, **_force_native(ta.ema, {"length": 20}))
        out["ema_50"] = ta.ema(close, **_force_native(ta.ema, {"length": 50}))
        out["ema_200"] = ta.ema(close, **_force_native(ta.ema, {"length": 200}))

        rsi_kwargs = _force_native(ta.rsi, {"length": 14})
        out["rsi_14"] = ta.rsi(close, **rsi_kwargs)

        macd_kwargs = _force_native(
            ta.macd, {"close": close, "fast": 12, "slow": 26, "signal": 9}
        )
        macd = ta.macd(**macd_kwargs)
        if not isinstance(macd, pd.DataFrame):
            raise TechnicalDependencyError(
                "unexpected macd payload from pandas-ta-classic"
            )
        out["macd_line"] = macd.iloc[:, 0]
        out["macd_hist"] = macd.iloc[:, 1]
        out["macd_signal_line"] = macd.iloc[:, 2]

        atr_kwargs = _force_native(
            ta.atr, {"high": high, "low": low, "close": close, "length": 14}
        )
        atr_series = ta.atr(**atr_kwargs)
        atr_values = (
            atr_series.iloc[:, 0]
            if isinstance(atr_series, pd.DataFrame)
            else atr_series
        )
        out["atr_14"] = atr_values

        adx_kwargs = _force_native(
            ta.adx, {"high": high, "low": low, "close": close, "length": 14}
        )
        adx = ta.adx(**adx_kwargs)
        if isinstance(adx, pd.DataFrame) and len(adx.columns) >= 3:
            out["adx_14"] = adx.iloc[:, 0]
            out["dmp_14"] = adx.iloc[:, 1]
            out["dmn_14"] = adx.iloc[:, 2]
        else:
            out["adx_14"] = np.nan
            out["dmp_14"] = np.nan
            out["dmn_14"] = np.nan

        bb_kwargs = _force_native(
            ta.bbands, {"close": close, "length": 20, "std": 2.0}
        )
        bb = ta.bbands(**bb_kwargs)
        if isinstance(bb, pd.DataFrame) and len(bb.columns) >= 3:
            out["bb_lower"] = bb.iloc[:, 0]
            out["bb_middle"] = bb.iloc[:, 1]
            out["bb_upper"] = bb.iloc[:, 2]
        else:
            out["bb_lower"] = np.nan
            out["bb_middle"] = np.nan
            out["bb_upper"] = np.nan
        out["bb_width"] = (out["bb_upper"] - out["bb_lower"]) / out["bb_middle"]

        roc_kwargs = _force_native(ta.roc, {"close": close, "length": 9})
        roc_series = ta.roc(**roc_kwargs)
        roc_values = (
            roc_series.iloc[:, 0] if isinstance(roc_series, pd.DataFrame) else roc_series
        )
        out["roc_9"] = roc_values

        missing = [c for c in ENGINE_COLUMNS if c not in out.columns]
        if missing:
            raise TechnicalDependencyError(
                f"engine failed to produce columns: {missing}"
            )
        return out[list(ENGINE_COLUMNS)]
