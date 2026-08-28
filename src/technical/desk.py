"""Technical Research Desk.

Produces an independent :class:`TechnicalAssessment` for one instrument on
one timeframe as of one timestamp.  The desk is a research/observability
component only: its output is never consumed by the institutional decision
path, and nothing here reads or writes institutional state.

No-lookahead contract: every assessment is computed exclusively from bars
whose timestamp is ``<= as_of``.  The as-of slice is taken before any
indicator computation, the source hash covers exactly that slice, and no
centered window, future normalization, or full-history scaling is used.
"""

from __future__ import annotations

import datetime
import hashlib
from typing import Any

import numpy as np
import pandas as pd

from technical.contracts import (
    DIRECTION_BEARISH,
    DIRECTION_BULLISH,
    DIRECTION_NEUTRAL,
    DIRECTION_UNKNOWN,
    OBOS_OVERBOUGHT,
    OBOS_OVERSOLD,
    SUPPORTED_TIMEFRAMES,
    VOLATILITY_CONTRACTING,
    VOLATILITY_EXPANDING,
    VOLATILITY_NORMAL,
    MIN_BARS_BY_TIMEFRAME,
    TechnicalAssessment,
    TechnicalDataError,
)
from technical.engine import PandasTaClassicEngine, TechnicalEngine
from technical.market_structure import DEFAULT_PIVOT_WINDOW, analyze_structure

# --- Deterministic interpretation constants -------------------------------
# Trend regime gate: below this ADX the market is treated as range-bound and
# EMA stacking alone is not promoted to a directional trend call.
TREND_ADX_MIN = 20.0
# Momentum needs a majority of the three votes (macd_hist sign, roc sign,
# macd line position relative to zero).
MOMENTUM_VOTE_COUNT = 3
MOMENTUM_MAJORITY = 2
# Bollinger-band-width percentile bounds for the volatility state, measured
# over a trailing one-year window ending at the assessment bar.
VOLATILITY_WINDOW = 252
VOLATILITY_EXPANDING_PCTL = 0.80
VOLATILITY_CONTRACTING_PCTL = 0.20
# Classic RSI extremes label the state only; they are deliberately excluded
# from every directional vote (polarity guard -- Correction 051 lesson).
RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0

# Confidence weights over the three directional dimensions.
CONF_WEIGHT_TREND = 1.0
AGREEMENT_STRENGTH_ADX_DIVISOR = 50.0
AGREEMENT_STRENGTH_FLOOR = 0.5

EXPECTED_BAR_DELTA: dict[str, pd.Timedelta] = {
    "D1": pd.Timedelta(days=1),
    "H4": pd.Timedelta(hours=4),
    "H1": pd.Timedelta(hours=1),
}
# Median observed bar spacing may exceed the nominal delta (weekends/holidays
# on daily data) but must stay within this multiple to count as matching.
FREQUENCY_TOLERANCE_MULTIPLE = 4.0

REQUIRED_COLUMNS = ("close",)
OPTIONAL_OHLC_COLUMNS = ("high", "low")


def canonical_source_hash(df: pd.DataFrame) -> str:
    """SHA-256 over a canonical CSV serialization of exactly the used rows."""
    canonical = df.copy()
    for col in canonical.select_dtypes(include="datetime64").columns:
        canonical[col] = canonical[col].astype(str)
    canonical = canonical.sort_index(axis=1)
    csv_bytes = canonical.to_csv(index=True).encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


class TechnicalResearchDesk:
    """Independent technical research desk over OHLCV data."""

    def __init__(
        self,
        engine: TechnicalEngine | None = None,
        pivot_window: int = DEFAULT_PIVOT_WINDOW,
    ) -> None:
        self._engine = engine if engine is not None else PandasTaClassicEngine()
        self._pivot_window = pivot_window

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assess(
        self,
        ohlcv: pd.DataFrame,
        as_of: str,
        timeframe: str = "D1",
        asset: str = "XAU/USD",
        created_at: str | None = None,
    ) -> TechnicalAssessment:
        if timeframe not in SUPPORTED_TIMEFRAMES:
            raise TechnicalDataError(f"unsupported timeframe: {timeframe}")
        as_of = str(as_of)

        frame = self._prepare_frame(ohlcv)
        sliced = self._slice_as_of(frame, as_of)

        notes: list[str] = []
        min_bars = MIN_BARS_BY_TIMEFRAME[timeframe]

        frequency_state = self._check_frequency(sliced, timeframe)
        if frequency_state is not None:
            notes.append(frequency_state)

        if len(sliced) < min_bars:
            return self._degraded_assessment(
                sliced=sliced,
                as_of=as_of,
                timeframe=timeframe,
                asset=asset,
                reason=(
                    f"insufficient_history: {len(sliced)} bars available, "
                    f"{min_bars} required for {timeframe}"
                ),
                notes=notes + ["insufficient_history"],
                created_at=created_at,
            )

        indicators = self._engine.compute(sliced)
        last = indicators.iloc[-1]
        close_last = float(sliced["close"].iloc[-1])

        structure = analyze_structure(sliced["close"], self._pivot_window)

        trend_direction = self._interpret_trend(last, close_last, notes)
        momentum_direction = self._interpret_momentum(last)
        volatility_state = self._interpret_volatility(indicators["bb_width"])
        obos_state = self._interpret_rsi(float(last["rsi_14"]))

        net_direction = self._net_direction(
            trend_direction, momentum_direction, structure.structure_state
        )
        supporting, conflicting = self._agreement_lists(
            net_direction,
            {
                "trend_ema_stack_adx": trend_direction,
                "momentum_macd_roc": momentum_direction,
                f"market_structure_{structure.structure_state}"
                if structure.structure_state
                else "market_structure": self._structure_direction(
                    structure.structure_state
                ),
            },
        )

        confidence = self._confidence(
            trend_direction, momentum_direction,
            self._structure_direction(structure.structure_state),
            float(last["adx_14"]),
        )

        if obos_state == OBOS_OVERBOUGHT and trend_direction == DIRECTION_BULLISH:
            notes.append("overbought_in_uptrend: strength context, not auto-reversal")
        elif obos_state == OBOS_OVERSOLD and trend_direction == DIRECTION_BEARISH:
            notes.append("oversold_in_downtrend: weakness context, not auto-reversal")
        if structure.bos_flag:
            notes.append(f"structure_event: {structure.bos_flag}")

        data_hash = canonical_source_hash(sliced)
        assessment_id = "tech_" + hashlib.sha256(
            "|".join([asset, timeframe, as_of, data_hash]).encode("utf-8")
        ).hexdigest()[:12]

        provenance_entry = {
            "created_at": created_at
            or datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "created_by": "TechnicalResearchDesk",
            "entity_version": "1.0.0",
            "metadata": {
                "engine": getattr(self._engine, "name", str(type(self._engine))),
                "library_version": self._engine_info_version(),
                "pivot_window": self._pivot_window,
            },
        }

        metadata: dict[str, Any] = {
            "notes": notes,
            "indicator_snapshot": {
                "close": _finite_or_none(close_last),
                "ema_20": _finite_or_none(last["ema_20"]),
                "ema_50": _finite_or_none(last["ema_50"]),
                "ema_200": _finite_or_none(last["ema_200"]),
                "rsi_14": _finite_or_none(last["rsi_14"]),
                "macd_hist": _finite_or_none(last["macd_hist"]),
                "atr_14": _finite_or_none(last["atr_14"]),
                "adx_14": _finite_or_none(last["adx_14"]),
                "roc_9": _finite_or_none(last["roc_9"]),
            },
            "structure": {
                "bos_flag": structure.bos_flag,
                "last_swing_high": structure.last_swing_high,
                "last_swing_low": structure.last_swing_low,
                "pivot_high_count": structure.pivot_high_count,
                "pivot_low_count": structure.pivot_low_count,
            },
            "bars_used": int(len(sliced)),
        }
        if frequency_state is not None:
            metadata["status_qualifier"] = "frequency_mismatch"

        return TechnicalAssessment(
            assessment_id=assessment_id,
            asset=asset,
            as_of=as_of,
            timeframe=timeframe,
            trend_direction=trend_direction,
            momentum_direction=momentum_direction,
            volatility_state=volatility_state,
            overbought_oversold_state=obos_state,
            structure_state=structure.structure_state,
            technical_confidence=confidence,
            supporting_indicators=tuple(supporting),
            conflicting_indicators=tuple(conflicting),
            source_data_hash=data_hash,
            provenance_chain=(provenance_entry,),
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Data preparation / validation
    # ------------------------------------------------------------------

    # Canonical lower-case names accepted from heterogeneous data providers.
    _COLUMN_ALIASES = {
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "adj close": "adj_close",
    }

    @classmethod
    def _prepare_frame(cls, ohlcv: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(ohlcv, pd.DataFrame):
            raise TechnicalDataError("ohlcv must be a pandas DataFrame")

        frame = ohlcv.copy()
        rename = {
            col: cls._COLUMN_ALIASES[str(col).strip().lower()]
            for col in frame.columns
            if str(col).strip().lower() in cls._COLUMN_ALIASES
            and col != cls._COLUMN_ALIASES[str(col).strip().lower()]
        }
        if rename:
            frame = frame.rename(columns=rename)

        missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
        if missing:
            raise TechnicalDataError(f"missing required columns: {missing}")
        engine_needs = [c for c in ("high", "low") if c not in frame.columns]
        if engine_needs:
            raise TechnicalDataError(
                f"engine requires OHLC data; missing columns: {engine_needs}"
            )

        date_column = None
        for candidate in ("Date", "date"):
            if candidate in frame.columns:
                date_column = candidate
                break

        if date_column is not None:
            frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
            if frame[date_column].isna().all():
                raise TechnicalDataError("Date column could not be parsed")
            frame = frame.sort_values(date_column).set_index(date_column)
        elif not isinstance(frame.index, pd.DatetimeIndex):
            raise TechnicalDataError(
                "data must carry a 'Date' column or a DatetimeIndex"
            )
        else:
            frame = frame.sort_index()

        numeric_cols = [c for c in REQUIRED_COLUMNS + OPTIONAL_OHLC_COLUMNS
                        if c in frame.columns]
        for col in numeric_cols:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")

        finite_close = np.isfinite(frame["close"].to_numpy(dtype=float))
        frame = frame.loc[finite_close]
        if frame.empty:
            raise TechnicalDataError("no finite close values")

        for col in ("open", "high", "low"):
            if col not in frame.columns:
                continue
            vals = frame[col].to_numpy(dtype=float)
            finite_vals = vals[np.isfinite(vals)]
            if len(finite_vals) and (finite_vals <= 0).any():
                raise TechnicalDataError(
                    f"invalid non-positive prices in column '{col}'"
                )
        h = frame["high"].to_numpy(dtype=float)
        l = frame["low"].to_numpy(dtype=float)
        both = np.isfinite(h) & np.isfinite(l)
        if (h[both] < l[both]).any():
            raise TechnicalDataError("high < low violations detected")

        return frame

    @staticmethod
    def _slice_as_of(frame: pd.DataFrame, as_of: str) -> pd.DataFrame:
        try:
            boundary = pd.Timestamp(as_of)
        except (ValueError, TypeError) as exc:
            raise TechnicalDataError(f"unparseable as_of: {as_of!r}") from exc
        if boundary.tzinfo is not None:
            boundary = boundary.tz_convert(None)
        normalized = frame.index.tz_localize(None) if frame.index.tz is not None else frame.index
        mask = normalized <= boundary
        return frame.loc[mask]

    @staticmethod
    def _check_frequency(sliced: pd.DataFrame, timeframe: str) -> str | None:
        if len(sliced) < 10 or timeframe not in EXPECTED_BAR_DELTA:
            return None
        deltas = pd.Series(sliced.index).diff().dropna()
        median_delta = deltas.median()
        expected = EXPECTED_BAR_DELTA[timeframe]
        if pd.isna(median_delta):
            return None
        if median_delta > expected * FREQUENCY_TOLERANCE_MULTIPLE or (
            median_delta < expected / FREQUENCY_TOLERANCE_MULTIPLE
        ):
            return (
                f"timeframe_data_mismatch: requested {timeframe} but observed "
                f"median bar spacing {median_delta}; assessment computed on "
                "provided bars without resampling"
            )
        return None

    # ------------------------------------------------------------------
    # Deterministic interpretation (polarity-safe)
    # ------------------------------------------------------------------

    @staticmethod
    def _interpret_trend(last: pd.Series, close: float, notes: list[str]) -> str:
        del close
        ema20 = last["ema_20"]
        ema50 = last["ema_50"]
        ema200 = last["ema_200"]
        adx = last["adx_14"]
        if any(not np.isfinite(v) for v in (ema20, ema50, ema200)):
            return DIRECTION_UNKNOWN
        bull_stack = int(ema20 > ema50) + int(ema50 > ema200)
        bear_stack = int(ema20 < ema50) + int(ema50 < ema200)
        adx_known = bool(np.isfinite(adx))
        if adx_known and adx < TREND_ADX_MIN:
            if max(bull_stack, bear_stack) == 2:
                notes.append(
                    f"range_regime: adx={adx:.1f}<{TREND_ADX_MIN:.0f} suppresses "
                    "EMA stack into a neutral trend reading"
                )
            return DIRECTION_NEUTRAL
        if bull_stack == 2:
            return DIRECTION_BULLISH
        if bear_stack == 2:
            return DIRECTION_BEARISH
        return DIRECTION_NEUTRAL

    @staticmethod
    def _interpret_momentum(last: pd.Series) -> str:
        # Zero is an abstention, never a bearish vote: counting it as a
        # negative sign produced phantom bearish momentum on flat markets.
        votes = 0
        counted = 0
        for value in (last["macd_hist"], last["roc_9"], last["macd_line"]):
            if not np.isfinite(value) or value == 0.0:
                continue
            counted += 1
            votes += 1 if value > 0 else -1
        if counted < 2:
            return DIRECTION_UNKNOWN
        if votes >= MOMENTUM_MAJORITY:
            return DIRECTION_BULLISH
        if votes <= -MOMENTUM_MAJORITY:
            return DIRECTION_BEARISH
        return DIRECTION_NEUTRAL

    @staticmethod
    def _interpret_volatility(bb_width: pd.Series) -> str:
        widths = bb_width.dropna()
        if len(widths) < 30:
            return DIRECTION_UNKNOWN
        window = widths.iloc[-min(len(widths), VOLATILITY_WINDOW):]
        current = float(window.iloc[-1])
        percentile = float((window <= current).mean())
        if percentile >= VOLATILITY_EXPANDING_PCTL:
            return VOLATILITY_EXPANDING
        if percentile <= VOLATILITY_CONTRACTING_PCTL:
            return VOLATILITY_CONTRACTING
        return VOLATILITY_NORMAL

    @staticmethod
    def _interpret_rsi(rsi_value: float) -> str:
        if not np.isfinite(rsi_value):
            return DIRECTION_UNKNOWN
        if rsi_value >= RSI_OVERBOUGHT:
            return OBOS_OVERBOUGHT
        if rsi_value <= RSI_OVERSOLD:
            return OBOS_OVERSOLD
        return DIRECTION_NEUTRAL

    @staticmethod
    def _structure_direction(structure_state: str | None) -> str:
        if structure_state == "uptrend":
            return DIRECTION_BULLISH
        if structure_state == "downtrend":
            return DIRECTION_BEARISH
        return DIRECTION_NEUTRAL

    @staticmethod
    def _net_direction(*directions: str | None) -> str:
        valid = [d for d in directions if d in (DIRECTION_BULLISH, DIRECTION_BEARISH)]
        bulls = valid.count(DIRECTION_BULLISH)
        bears = valid.count(DIRECTION_BEARISH)
        if bulls > bears:
            return DIRECTION_BULLISH
        if bears > bulls:
            return DIRECTION_BEARISH
        return DIRECTION_NEUTRAL

    @staticmethod
    def _agreement_lists(
        net_direction: str,
        named_directions: dict[str, str],
    ) -> tuple[list[str], list[str]]:
        supporting: list[str] = []
        conflicting: list[str] = []
        if net_direction not in (DIRECTION_BULLISH, DIRECTION_BEARISH):
            return supporting, conflicting
        for name, direction in named_directions.items():
            if direction == net_direction:
                supporting.append(name)
            elif direction in (DIRECTION_BULLISH, DIRECTION_BEARISH):
                conflicting.append(name)
        return supporting, conflicting

    @staticmethod
    def _confidence(*directions_and_adx: Any) -> float:
        *directions, adx = directions_and_adx
        valid = [d for d in directions if d in (DIRECTION_BULLISH, DIRECTION_BEARISH)]
        if not valid:
            return 0.0
        bulls = valid.count(DIRECTION_BULLISH)
        bears = valid.count(DIRECTION_BEARISH)
        agreement = max(bulls, bears) / len(valid)
        strength = AGREEMENT_STRENGTH_FLOOR
        if isinstance(adx, float) and np.isfinite(adx) and adx > 0:
            strength = float(
                np.clip(adx / AGREEMENT_STRENGTH_ADX_DIVISOR,
                        AGREEMENT_STRENGTH_FLOOR, 1.0)
            )
        return round(agreement * strength, 4)

    # ------------------------------------------------------------------
    # Degraded path & helpers
    # ------------------------------------------------------------------

    def _degraded_assessment(
        self,
        *,
        sliced: pd.DataFrame,
        as_of: str,
        timeframe: str,
        asset: str,
        reason: str,
        notes: list[str],
        created_at: str | None,
    ) -> TechnicalAssessment:
        data_hash = canonical_source_hash(sliced) if len(sliced) else ""
        assessment_id = "tech_" + hashlib.sha256(
            "|".join([asset, timeframe, as_of, data_hash]).encode("utf-8")
        ).hexdigest()[:12]
        provenance_entry = {
            "created_at": created_at
            or datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "created_by": "TechnicalResearchDesk",
            "entity_version": "1.0.0",
            "metadata": {
                "engine": getattr(self._engine, "name", str(type(self._engine))),
                "library_version": self._engine_info_version(),
            },
        }
        return TechnicalAssessment(
            assessment_id=assessment_id,
            asset=asset,
            as_of=as_of,
            timeframe=timeframe,
            trend_direction=DIRECTION_UNKNOWN,
            momentum_direction=DIRECTION_UNKNOWN,
            volatility_state=DIRECTION_UNKNOWN,
            overbought_oversold_state=DIRECTION_UNKNOWN,
            structure_state=None,
            technical_confidence=0.0,
            supporting_indicators=(),
            conflicting_indicators=(),
            source_data_hash=data_hash,
            provenance_chain=(provenance_entry,),
            metadata={"notes": [reason, *notes], "bars_used": int(len(sliced))},
        )

    def _engine_info_version(self) -> str:
        info_fn = getattr(self._engine, "info", None)
        if callable(info_fn):
            try:
                return info_fn().library_version
            except Exception:
                return "unknown"
        return "unknown"


def _finite_or_none(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if np.isfinite(numeric) else None
