from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from knowledge._compat import FrozenDict, freeze_dict

import pandas as pd

from forecasting.provenance import ForecastProvenance

if TYPE_CHECKING:
    from forecasting.context import ForecastContext, ForecastContextBuilder
    from forecasting.macro_forecaster import MacroForecaster
    from forecasting.models import ForecastResult
    from forecasting.registry import ForecastModelSpec, ForecastRegistry


@dataclass(frozen=True)
class ForecastPackage:
    target_variable: str
    context: ForecastContext
    results: dict[str, "ForecastResult"]
    provenance: ForecastProvenance
    model_specs: tuple["ForecastModelSpec", ...]
    horizon: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "results", freeze_dict(self.results))

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_variable": self.target_variable,
            "context": self.context.to_dict(),
            "results": {
                name: {
                    "model_name": r.model_name,
                    "confidence_level": r.confidence_level,
                    "points": [{"ds": p.ds, "y": p.y, "y_lo": p.y_lo, "y_hi": p.y_hi} for p in r.points],
                    "metadata": dict(r.metadata),
                }
                for name, r in self.results.items()
            },
            "provenance": self.provenance.to_dict(),
            "model_specs": [
                {
                    "name": s.name,
                    "model_cls": s.model_cls.__name__,
                    "model_kwargs": dict(s.model_kwargs),
                    "target_variable": s.target_variable,
                    "freq": s.freq,
                    "default_horizon": s.default_horizon,
                    "max_horizon": s.max_horizon,
                    "training_window": s.training_window,
                    "validation_strategy": s.validation_strategy,
                    "validation_split": s.validation_split,
                    "approval_status": s.approval_status,
                    "description": s.description,
                }
                for s in self.model_specs
            ],
            "horizon": self.horizon,
        }


class ForecastKnowledge:
    def __init__(
        self,
        registry: type["ForecastRegistry"] | None = None,
        context_builder: "ForecastContextBuilder | None" = None,
        forecaster: "MacroForecaster | None" = None,
    ) -> None:
        from forecasting.context import ForecastContextBuilder
        from forecasting.macro_forecaster import MacroForecaster
        from forecasting.registry import ForecastRegistry

        self._registry = registry or ForecastRegistry
        self._context_builder = context_builder or ForecastContextBuilder()
        self._forecaster = forecaster or MacroForecaster()

    def forecast(
        self,
        target_variable: str,
        training_data: pd.DataFrame,
        horizon: int = 12,
        event_summaries: list[Any] | None = None,
        news_texts: list[str] | None = None,
        fomc_texts: list[str] | None = None,
        *,
        model_names: list[str] | None = None,
    ) -> ForecastPackage:
        if not {"ds", "y"}.issubset(training_data.columns):
            raise ValueError("training_data must contain columns 'ds' and 'y'")

        context = self._context_builder.build(
            source_variable=target_variable,
            training_data=training_data,
            event_summaries=event_summaries,
            news_texts=news_texts,
            fomc_texts=fomc_texts,
        )

        specs = self._select_model_specs(target_variable, model_names)

        results = self._run_forecasts(training_data, specs, horizon)

        provenance = self._build_provenance(target_variable, training_data)

        return ForecastPackage(
            target_variable=target_variable,
            context=context,
            results=results,
            provenance=provenance,
            model_specs=tuple(specs),
            horizon=horizon,
        )

    def _select_model_specs(
        self,
        target_variable: str,
        model_names: list[str] | None = None,
    ) -> list["ForecastModelSpec"]:
        all_specs = self._registry.for_target(target_variable)
        if model_names:
            selected = [s for s in all_specs if s.name in model_names]
            return selected
        return [s for s in all_specs if s.approval_status == "approved"]

    def _run_forecasts(
        self,
        training_data: pd.DataFrame,
        specs: list["ForecastModelSpec"],
        horizon: int,
    ) -> dict[str, "ForecastResult"]:
        if not specs:
            return {}

        models = self._build_model_instances(specs)
        if not models:
            return {}

        from forecasting.macro_forecaster import MacroForecaster

        forecaster = MacroForecaster(
            season_length=12,
            freq=specs[0].freq if specs else "ME",
            models=models,
        )
        results = forecaster.forecast(training_data, h=horizon)
        return results

    @staticmethod
    def _build_model_instances(specs: list["ForecastModelSpec"]) -> list[Any]:
        instances: list[Any] = []
        for spec in specs:
            try:
                inst = spec.model_cls(**spec.model_kwargs)
                instances.append(inst)
            except Exception:
                continue
        return instances

    @staticmethod
    def _build_provenance(
        target_variable: str,
        training_data: pd.DataFrame,
    ) -> ForecastProvenance:
        from forecasting.registry import ForecastRegistry

        return ForecastProvenance(
            source=target_variable,
            model_version=str(ForecastRegistry.version()),
            training_window=f"{len(training_data)} obs",
            registry_version=str(ForecastRegistry.version()),
            git_commit=ForecastProvenance.resolve_git_commit(),
            data_hash=ForecastProvenance.compute_data_hash(training_data),
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
