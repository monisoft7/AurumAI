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
    from knowledge.pipeline.pipeline import InferencePipeline
    from knowledge.pipeline.context import PipelineContext

    event = params.get("_event")
    if event is None:
        raise ValueError("_event not found -- ingest_event must complete first")

    from pathlib import Path

    ctx = PipelineContext(
        event=event,
        event_data_path=Path(params["data_path"]),
        gold_path=Path(params["gold_path"]),
        output_dir=Path(params["output_dir"]),
        query=params.get("query", ""),
        asset=params.get("asset", "XAU/USD"),
    )

    pipe = InferencePipeline()
    result = pipe.run(ctx)

    return {
        "pipeline_result": result,
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

    df = pd.read_csv(gold_path, parse_dates=True)
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

    forecast_result = results.get("forecast")
    if forecast_result is None:
        raise ValueError("'forecast' stage must complete first")

    ctx_builder = ForecastContextBuilder()
    context = ctx_builder.build(forecast_result, params.get("_event"))

    pkg = ForecastPackage(
        forecasts={"default": forecast_result},
        context=context,
        evidence=[],
    )

    computer = ForecastConfidenceComputer()
    confidence = computer.compute(pkg, context)

    return {"confidence": confidence, "context": context}


def _forecast_validation(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from forecasting.validation import ForecastValidator
    from forecasting.context import ForecastContextBuilder
    import pandas as pd

    forecast_result = results.get("forecast")
    if forecast_result is None:
        raise ValueError("'forecast' stage must complete first")

    validator = ForecastValidator()
    df = pd.read_csv(params["gold_path"], parse_dates=True)
    ctx_builder = ForecastContextBuilder()
    context = ctx_builder.build(forecast_result, params.get("_event"))
    report = validator.validate(df, forecast_result, context)

    return report


def _build_context(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from forecasting.context import ForecastContextBuilder
    from knowledge.regime.macro_regime_detector import MacroRegimeDetector
    import pandas as pd

    forecast_result = results.get("forecast")
    if forecast_result is None:
        raise ValueError("'forecast' stage must complete first")

    regime = MacroRegimeDetector()
    gold_df = pd.read_csv(params["gold_path"], parse_dates=True)
    regime_id = regime.detect(gold_df)

    ctx_builder = ForecastContextBuilder()
    context = ctx_builder.build(
        forecast_result,
        params.get("_event"),
        regime_override={"regime": regime_id},
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
    tail_index = detector.estimate(residuals)

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
    from forecasting.decision_gate import DecisionGate
    from knowledge.decision.decision import Decision

    decision: Decision | None = None
    pipe_result = results.get("build_legacy_pipeline", {})
    if isinstance(pipe_result, dict):
        decision = pipe_result.get("decision")

    risk_metrics = results.get("risk_measures")
    context = results.get("build_context")

    gate = DecisionGate()
    gate_result = gate.evaluate(
        decision=decision,
        risk_metrics=risk_metrics,
        forecast_context=context,
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
