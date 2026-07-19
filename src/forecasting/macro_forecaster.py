from __future__ import annotations

import re
from typing import Any

import pandas as pd

from forecasting.models import ForecastPoint, ForecastResult

_DEFAULT_SEASON_LENGTH = 12
_DEFAULT_FREQ = "ME"
_DEFAULT_H = 12


class MacroForecaster:
    def __init__(
        self,
        season_length: int = _DEFAULT_SEASON_LENGTH,
        freq: str = _DEFAULT_FREQ,
        models: list | None = None,
    ) -> None:
        self._season_length = season_length
        self._freq = freq
        self._models = models if models is not None else self._default_models()

    @staticmethod
    def _default_models() -> list:
        try:
            from statsforecast.models import AutoARIMA, AutoETS, AutoTheta
        except ImportError:
            raise ImportError(
                "The 'statsforecast' library is required for MacroForecaster. "
                "Install it with: pip install statsforecast"
            )
        return [
            AutoARIMA(season_length=_DEFAULT_SEASON_LENGTH),
            AutoETS(season_length=_DEFAULT_SEASON_LENGTH, model="ZZZ"),
            AutoTheta(season_length=_DEFAULT_SEASON_LENGTH),
        ]

    @property
    def model_names(self) -> list[str]:
        return [m.alias for m in self._models]

    def _column_re(self) -> re.Pattern:
        level = 95
        return re.compile(
            rf"^(?P<model>.+?)(?:-lo-{level}|-hi-{level})?$"
        )

    def _parse_model_cols(self, df: pd.DataFrame) -> dict[str, dict[str, float | None]]:
        level = 95
        model_cols: dict[str, dict[str, float | None]] = {}
        col_pattern = re.compile(
            rf"^(?P<model>.+?)(?:-(?P<bound>lo|hi)-{level})?$"
        )
        for col in df.columns:
            if col in ("unique_id", "ds"):
                continue
            m = col_pattern.match(col)
            if not m:
                continue
            model_name = m.group("model")
            bound = m.group("bound")
            if model_name not in model_cols:
                model_cols[model_name] = {"y": None, "y_lo": None, "y_hi": None}
            if bound is None:
                model_cols[model_name]["y"] = col
            elif bound == "lo":
                model_cols[model_name]["y_lo"] = col
            elif bound == "hi":
                model_cols[model_name]["y_hi"] = col
        return model_cols

    def forecast(
        self,
        data: pd.DataFrame,
        h: int = _DEFAULT_H,
    ) -> dict[str, ForecastResult]:
        if not {"ds", "y"}.issubset(data.columns):
            raise ValueError(
                "data must contain columns 'ds' (datetime) and 'y' (float)"
            )

        try:
            from statsforecast import StatsForecast
        except ImportError:
            raise ImportError(
                "The 'statsforecast' library is required for MacroForecaster. "
                "Install it with: pip install statsforecast"
            )

        clean = data[["ds", "y"]].copy()
        clean["unique_id"] = "macro"

        sf = StatsForecast(
            models=self._models,
            freq=self._freq,
            n_jobs=1,
            verbose=False,
        )
        sf.fit(df=clean)
        fcst = sf.predict(h=h, level=[95])

        model_map = self._parse_model_cols(fcst)
        results: dict[str, ForecastResult] = {}

        for model_name, cols in model_map.items():
            points: list[ForecastPoint] = []
            for _, row in fcst.iterrows():
                ds_str = str(row["ds"])
                if pd.isna(row["ds"]):
                    continue
                y_val = row[cols["y"]] if cols["y"] else float("nan")
                y_lo_val = row[cols["y_lo"]] if cols["y_lo"] else float("nan")
                y_hi_val = row[cols["y_hi"]] if cols["y_hi"] else float("nan")
                points.append(
                    ForecastPoint(
                        ds=ds_str,
                        y=float(y_val),
                        y_lo=float(y_lo_val),
                        y_hi=float(y_hi_val),
                    )
                )

            results[model_name] = ForecastResult(
                model_name=model_name,
                confidence_level=0.95,
                points=tuple(points),
                metadata={
                    "season_length": self._season_length,
                    "freq": self._freq,
                    "h": h,
                    "n_obs": len(clean),
                },
            )

        return results
