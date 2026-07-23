from __future__ import annotations

from typing import Any


def _ingest_event(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from knowledge.events.registry import EventRegistry

    event_type = params.get("event_type", "CPIEvent")
    data_path = params.get("data_path")
    if data_path is None:
        raise ValueError("params must include 'data_path'")
    event_cls = EventRegistry.get(event_type)
    event = event_cls()
    raw = event.load_raw(data_path)
    params["_event"] = event
    return {"event_type": event_type, "event": event, "raw_data": raw}


def _ingest_news(params: dict[str, Any], results: dict[str, Any]) -> Any:
    topics = params.get("news_topics", ("gold", "inflation", "fed"))
    lookback_days = params.get("news_lookback_days", 7)

    news_items: list[dict[str, Any]] = []
    fomc_events: list[dict[str, Any]] = []

    try:
        from news.collector import NewsCollector

        collector = NewsCollector()
        news_items = [dict(r) for r in collector.collect(topics=topics, max_age_days=lookback_days)]
    except ImportError:
        pass

    try:
        from connectors.fomc_calendar import FOMCCalendarConnector

        fomc = FOMCCalendarConnector()
        fomc_events = [dict(r) for r in fomc.fetch()]
    except (ImportError, AttributeError):
        pass

    return {"news_items": news_items, "fomc_events": fomc_events}


def _build_legacy_pipeline(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from knowledge.integrity.lineage import LineageRegistry
    from knowledge.pipeline.pipeline import InferencePipeline
    from knowledge.pipeline.context import PipelineContext

    event = params.get("_event")
    if event is None:
        raise ValueError("_event not found -- ingest_event must complete first")

    from pathlib import Path

    reasoning_condition = params.get("reasoning_condition")

    if (
        reasoning_condition is None
        and params.get("release_calendar_path") is not None
    ):
        try:
            extracted = event.load_and_extract(Path(params["data_path"]))
            if len(extracted) > 0:
                reasoning_condition = event.build_reasoning_condition(
                    extracted.iloc[-1]
                )
        except Exception:
            reasoning_condition = None

    lesson_builder = None
    if params.get("release_calendar_path") is None:
        from knowledge.builders.lesson_builder import (
            LegacyLessonBuilder,
            LessonBuilderConfig,
        )
        lesson_builder = LegacyLessonBuilder(
            config=LessonBuilderConfig(
                event_data_path=Path(params["data_path"]),
        gold_path=Path(params.get("gold_lessons_path", params["gold_path"])),
                output_path=Path(params["output_dir"]) / "lessons.csv",
            ),
            event=event,
        )

    ctx = PipelineContext(
        event=event,
        event_data_path=Path(params["data_path"]),
        gold_path=Path(params["gold_path"]),
        output_dir=Path(params["output_dir"]),
        query=params.get("query", ""),
        asset=params.get("asset", "XAU/USD"),
        release_calendar_path=params.get("release_calendar_path"),
        condition_columns=tuple(
            getattr(event, "condition_columns", ("condition",))
        ),
        lesson_builder=lesson_builder,
        prebuilt_lessons_path=params.get("prebuilt_lessons_path"),
        reasoning_horizon=params.get("reasoning_horizon"),
        reasoning_condition=reasoning_condition,
        min_evidence_count=params.get("min_evidence_count", 1),
        yield_data_path=Path(params["yield_data_path"]) if params.get("yield_data_path") else None,
        yield_context_lookback_days=params.get("yield_context_lookback_days", 30),
    )

    pipe = InferencePipeline()
    reg = LineageRegistry()
    result = pipe.run(ctx, lineage_registry=reg)

    return {
        "pipeline_result": result,
        "lineage_registry": reg,
        "decision": result.decision,
        "reasoning_chain": result.reasoning_chain,
        "evidence": result.evidence,
        "knowledge_graph": result.knowledge_graph,
        "stages_completed": result.stages_completed,
    }


def _forecast(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from forecasting.macro_forecaster import MacroForecaster
    import pandas as pd

    gold_path = params["gold_path"]
    horizon = params.get("horizon", 12)

    df = pd.read_csv(gold_path, parse_dates=["Date"])
    if "ds" not in df.columns:
        ds_col = df.select_dtypes(include=["datetime64"]).columns
        if len(ds_col) > 0:
            df = df.rename(columns={ds_col[0]: "ds"})
    if "y" not in df.columns and "Close" in df.columns:
        df["y"] = df["Close"]

    forecaster = MacroForecaster()
    model_results = forecaster.forecast(df, h=horizon)

    if isinstance(model_results, dict):
        primary = next(iter(model_results.values()))
        return primary

    return model_results


def _forecast_confidence(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from forecasting.confidence import ForecastConfidenceComputer
    from forecasting.knowledge import ForecastPackage
    from forecasting.context import ForecastContextBuilder
    from forecasting.provenance import ForecastProvenance
    from forecasting.registry import ForecastRegistry
    import datetime as _dt
    import pandas as pd

    forecast_result = results.get("forecast")
    if forecast_result is None:
        raise ValueError("'forecast' stage must complete first")

    gold_df = pd.read_csv(params["gold_path"])
    ctx_builder = ForecastContextBuilder()
    context = ctx_builder.build(
        forecast_result.model_name if hasattr(forecast_result, "model_name") else str(forecast_result),
        gold_df,
    )

    model_name = forecast_result.model_name if hasattr(forecast_result, "model_name") else "default"
    specs = ForecastRegistry.for_target(str(params.get("asset", "XAU/USD")))
    provenance = ForecastProvenance(
        source=str(params.get("asset", "XAU/USD")),
        model_version=str(ForecastRegistry.version()),
        training_window=f"{len(gold_df)} obs",
        registry_version=str(ForecastRegistry.version()),
        git_commit=ForecastProvenance.resolve_git_commit(),
        data_hash=ForecastProvenance.compute_data_hash(gold_df),
        created_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
    )

    pkg = ForecastPackage(
        target_variable=str(params.get("asset", "XAU/USD")),
        context=context,
        results={model_name: forecast_result},
        provenance=provenance,
        model_specs=tuple(specs) if specs else (),
        horizon=int(params.get("horizon", 12)),
    )

    computer = ForecastConfidenceComputer()
    confidence = computer.compute(pkg, context)

    return {"confidence": confidence, "context": context}


def _forecast_validation(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from forecasting.validation import ForecastValidator
    import pandas as pd

    forecast_result = results.get("forecast")
    if forecast_result is None:
        raise ValueError("'forecast' stage must complete first")

    validator = ForecastValidator()
    df = pd.read_csv(params["gold_path"])
    forecast_results = {}
    if hasattr(forecast_result, "model_name"):
        forecast_results[forecast_result.model_name] = forecast_result
    report = validator.validate(df, forecast_results, strategy="walk_forward", horizon=1)

    return report


def _build_context(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from forecasting.context import ForecastContextBuilder
    import pandas as pd

    forecast_result = results.get("forecast")
    if forecast_result is None:
        raise ValueError("'forecast' stage must complete first")

    gold_df = pd.read_csv(params["gold_path"])
    ctx_builder = ForecastContextBuilder()
    context = ctx_builder.build(
        forecast_result.model_name if hasattr(forecast_result, "model_name") else str(forecast_result),
        gold_df,
    )

    return context


def _risk_measures(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from forecasting.risk_measures import (
        compute_var,
        compute_cvar,
        TailRiskDetector,
    )
    import numpy as np

    forecast_result = results.get("forecast")
    if forecast_result is None:
        raise ValueError("'forecast' stage must complete first")

    points = forecast_result.points
    residuals = np.array([p.y_hi - p.y_lo for p in points])
    if len(residuals) == 0 or residuals.std() < 1e-12:
        residuals = np.random.default_rng(42).normal(0, 1, 252)

    var_95 = compute_var(residuals, 0.95)
    var_99 = compute_var(residuals, 0.99)
    cvar_95 = compute_cvar(residuals, 0.95)

    detector = TailRiskDetector()
    tail_result = detector.detect(residuals)
    tail_index = tail_result.get("tail_index")

    from forecasting.risk_measures import RiskMetrics

    metrics = RiskMetrics(
        var_95=float(var_95),
        var_99=float(var_99),
        cvar_95=float(cvar_95),
        tail_index=tail_index,
        method="historical",
    )

    return metrics


def _position_sizing(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from forecasting.position_sizing import VolatilityTargetSizer
    from forecasting.risk_budgeting import RiskParitySizer
    import numpy as np

    risk_metrics = results.get("risk_measures")

    vol_sizer = VolatilityTargetSizer()
    np_rng = np.random.default_rng(42)
    returns = np_rng.normal(0.005, 0.02, 252)

    sizing = vol_sizer.compute(returns)

    rp_sizer = RiskParitySizer()
    cov = np.array([[0.0004, 0.0001], [0.0001, 0.0003]])
    budget = rp_sizer.compute(cov)

    return {"position_sizing": sizing, "risk_budget": budget}


def _risk_gate(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from forecasting.decision_gate import DecisionGate, RegimeRiskOverlay, UncertaintyBudget

    risk_metrics = results.get("risk_measures")
    context = results.get("build_context")

    regime_label = context.current_regime if context else None
    regime_confidence = context.regime_confidence if context else 0.0
    overlay = RegimeRiskOverlay()
    regime_info = overlay.evaluate(regime_label or "UNKNOWN", regime_confidence)

    var_95 = getattr(risk_metrics, "var_95", None) if risk_metrics else None
    tail_index = getattr(risk_metrics, "tail_index", None) if risk_metrics else None
    budget = UncertaintyBudget()
    uncertainty = budget.evaluate(
        context_coherence=0.5,
        var_95=var_95 or -0.05,
        tail_index=tail_index,
    )

    ps_result = results.get("position_sizing", {})
    if isinstance(ps_result, dict):
        scaling_factor = ps_result.get("position_sizing", 0.5)
        if hasattr(scaling_factor, "scaling_factor"):
            scaling_factor = scaling_factor.scaling_factor
    else:
        scaling_factor = 0.5

    drawdown_state = "normal"

    gate = DecisionGate()
    gate_result = gate.evaluate(
        regime_info=regime_info,
        uncertainty=uncertainty,
        scaling_factor=float(scaling_factor),
        drawdown_state=drawdown_state,
    )

    return gate_result


def _finalize(params: dict[str, Any], results: dict[str, Any]) -> Any:
    return {
        "decision": results.get("build_legacy_pipeline", {}).get("decision"),
        "risk_decision": results.get("risk_gate"),
        "forecast_result": results.get("forecast"),
        "confidence": results.get("forecast_confidence", {}).get("confidence"),
        "validation": results.get("forecast_validation"),
        "context": results.get("build_context"),
        "risk_metrics": results.get("risk_measures"),
        "position_sizing": results.get("position_sizing", {}).get("position_sizing"),
        "risk_budget": results.get("position_sizing", {}).get("risk_budget"),
    }
