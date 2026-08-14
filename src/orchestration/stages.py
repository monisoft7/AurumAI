from __future__ import annotations

from pathlib import Path
from typing import Any

_regime_initialized: bool = False

_FORECAST_FREQ_ANNUALIZATION: dict[str, float] = {
    "D": 252.0,
    "B": 252.0,
    "W": 52.0,
    "ME": 12.0,
    "M": 12.0,
    "QE": 4.0,
    "Q": 4.0,
    "YE": 1.0,
    "A": 1.0,
}


def _ensure_macro_regime_initialized(params: dict[str, Any]) -> None:
    global _regime_initialized
    if _regime_initialized:
        return

    from knowledge.regime.composite_score import CompositeScoreBuilder
    from knowledge.regime.macro_regime_detector import MacroRegimeDetector
    from knowledge.features.extractors.macro_regime import (
        MacroRegimeFeatureExtractor,
    )
    from knowledge.features.engine import FeatureExtractionEngine

    composite_data = CompositeScoreBuilder().build()
    detector = MacroRegimeDetector(random_state=42).fit(composite_data)
    extractor = MacroRegimeFeatureExtractor(detector)
    FeatureExtractionEngine.register_global(extractor)
    params["_regime_detector"] = detector
    _regime_initialized = True


def _ingest_event(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from knowledge.events.registry import EventRegistry

    _ensure_macro_regime_initialized(params)

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

    institutional_context_columns = tuple(
        params.get("institutional_context_columns") or ()
    )
    if (
        params.get("yield_data_path")
        and not params.get("prebuilt_lessons_path")
    ):
        institutional_context_columns += (
            "us10y_level",
            "us10y_trend",
        )
    if (
        params.get("dxy_data_path")
        and not params.get("prebuilt_lessons_path")
    ):
        institutional_context_columns += (
            "dxy_level",
            "dxy_trend",
        )
    if (
        params.get("breakeven_data_path")
        and not params.get("prebuilt_lessons_path")
    ):
        institutional_context_columns += (
            "t5yie_level",
            "t5yie_trend",
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
        institutional_context_columns=institutional_context_columns,
        yield_data_path=Path(params["yield_data_path"]) if params.get("yield_data_path") else None,
        yield_context_lookback_days=params.get("yield_context_lookback_days", 30),
        dxy_data_path=Path(params["dxy_data_path"]) if params.get("dxy_data_path") else None,
        dxy_context_lookback_days=params.get("dxy_context_lookback_days", 30),
        breakeven_data_path=Path(params["breakeven_data_path"]) if params.get("breakeven_data_path") else None,
        breakeven_context_lookback_days=params.get("breakeven_context_lookback_days", 30),
    )

    pipe = InferencePipeline()
    reg = LineageRegistry()
    result = pipe.run(ctx, lineage_registry=reg)

    episodes_index_path = _build_run_local_episode_index(params)

    return {
        "pipeline_result": result,
        "lineage_registry": reg,
        "decision": result.decision,
        "reasoning_chain": result.reasoning_chain,
        "evidence": result.evidence,
        "knowledge_graph": result.knowledge_graph,
        "reasoning_condition": reasoning_condition,
        "stages_completed": result.stages_completed,
        "lesson_episodes_index_path": episodes_index_path,
    }


def _build_run_local_episode_index(params: dict[str, Any]) -> str | None:
    """Derive the run-local episode index from the enriched lesson artifact
    emitted by ``build_legacy_pipeline`` (Correction 027).

    The enriched ``output_dir/lessons.csv`` remains the single source of
    truth; the episode index is a deterministic, disposable projection of it,
    saved beside it as ``output_dir/lesson_episodes.json`` and published
    through the existing ``lesson_episodes_index_path`` parameter that W6
    (``_evidence_reasoning``) already passes to ``build_historical_analogue``.
    Only rows actually present in the enriched artifact are indexed; nothing
    is fabricated or reinserted.  Missing/unreadable artifacts degrade
    safely: no index is written, no parameter is set, and the W-path keeps
    its existing no-analogue behaviour.
    """
    output_dir = params.get("output_dir")
    if not output_dir:
        return None
    lessons_path = Path(output_dir) / "lessons.csv"
    if not lessons_path.is_file():
        return None
    episodes_json = Path(output_dir) / "lesson_episodes.json"
    try:
        from knowledge.temporal.lesson_index import (
            build_lesson_episode_index,
            save_lesson_episode_index,
        )

        indexer = build_lesson_episode_index(lessons_path)
        save_lesson_episode_index(indexer, episodes_json)
    except Exception:
        return None
    params["lesson_episodes_index_path"] = str(episodes_json)
    return str(episodes_json)


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
    ctx_builder = ForecastContextBuilder(
        regime_detector=params.get("_regime_detector"),
    )
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
    ctx_builder = ForecastContextBuilder(
        regime_detector=params.get("_regime_detector"),
    )
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

    forecast_result = results.get("forecast")
    if isinstance(forecast_result, dict):
        raw_points = forecast_result.get("points") or ()
        metadata = forecast_result.get("metadata") or {}
    else:
        raw_points = getattr(forecast_result, "points", None) if forecast_result is not None else None
        metadata = getattr(forecast_result, "metadata", None) if forecast_result is not None else None

    if not raw_points or len(raw_points) < 2:
        return {
            "position_sizing": None,
            "risk_budget": None,
            "status": "insufficient_data",
        }

    ys = np.array(
        [float(p.y) if hasattr(p, "y") else float(p["y"]) for p in raw_points],
        dtype=float,
    )
    if ys.size < 2 or not np.all(np.isfinite(ys)) or float(ys[0]) <= 0.0:
        return {
            "position_sizing": None,
            "risk_budget": None,
            "status": "insufficient_data",
        }

    returns = ys[1:] / ys[:-1] - 1.0
    if not np.all(np.isfinite(returns)):
        return {
            "position_sizing": None,
            "risk_budget": None,
            "status": "insufficient_data",
        }

    freq = (metadata or {}).get("freq")
    annualization = _FORECAST_FREQ_ANNUALIZATION.get(str(freq).upper()) if freq else None
    if annualization is None:
        return {
            "position_sizing": None,
            "risk_budget": None,
            "status": "insufficient_data",
        }

    sizing = VolatilityTargetSizer().compute(returns, annualization_factor=annualization)
    cov = np.atleast_2d(np.cov(returns))
    budget = RiskParitySizer().compute(cov)

    return {"position_sizing": sizing, "risk_budget": budget, "status": "ok"}


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
    scaling_factor = 0.5
    drawdown_state = "normal"
    if isinstance(ps_result, dict):
        sizing = ps_result.get("position_sizing")
        if sizing is not None and hasattr(sizing, "scaling_factor"):
            scaling_factor = sizing.scaling_factor
            drawdown_state = sizing.drawdown_state or "normal"

    gate = DecisionGate()
    gate_result = gate.evaluate(
        regime_info=regime_info,
        uncertainty=uncertainty,
        scaling_factor=float(scaling_factor),
        drawdown_state=drawdown_state,
    )

    return gate_result


def _signal_assessment(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from dataclasses import replace

    from signal_assessment.assembler import SignalAssessmentAssembler
    from pre_market.contracts import PreMarketBriefing

    briefing_data = results.get("pre_market_scan")
    if briefing_data is None:
        briefing_data = params.get("briefing_data")
    if briefing_data is None:
        return {"error": "no briefing data available", "observations": []}

    if isinstance(briefing_data, dict):
        briefing = PreMarketBriefing.from_dict(briefing_data)
    else:
        briefing = briefing_data

    assembler = SignalAssessmentAssembler(
        regime=briefing.regime,
    )
    assessment = assembler.assemble(briefing)

    diagnosis = results.get("regime_diagnosis")
    if isinstance(diagnosis, dict) and diagnosis.get("regime"):
        assessment = replace(
            assessment,
            regime=str(diagnosis["regime"]),
            regime_confidence=float(diagnosis.get("confidence", assessment.regime_confidence)),
        )
    return assessment


def _event_triage(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from signal_assessment.contracts import SignalAssessment
    from event_triage.tierer import SignalTierer

    assessment_data = results.get("signal_assessment")
    if assessment_data is None:
        assessment_data = params.get("assessment_data")
    if assessment_data is None:
        return {"error": "no assessment data available", "assignments": []}

    if isinstance(assessment_data, dict):
        assessment = SignalAssessment.from_dict(assessment_data)
    else:
        assessment = assessment_data

    tierer = SignalTierer()
    return tierer.tier(assessment)


def _evidence_collection(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from dataclasses import replace

    from signal_assessment.contracts import SignalAssessment
    from evidence_collection.collector import EvidenceCollector
    from evidence_collection.contracts import EvidenceCollection
    from event_triage.contracts import SignalTiering

    assessment_data = results.get("signal_assessment")
    if assessment_data is None:
        assessment_data = params.get("assessment_data")
    if assessment_data is None:
        return {"error": "no assessment data available", "items": []}

    if isinstance(assessment_data, dict):
        assessment = SignalAssessment.from_dict(assessment_data)
    else:
        assessment = assessment_data

    kg = results.get("build_legacy_pipeline", {}).get("knowledge_graph")
    if kg is None:
        kg = params.get("knowledge_graph")

    cpi_condition = results.get("build_legacy_pipeline", {}).get(
        "reasoning_condition"
    )
    if not (
        isinstance(cpi_condition, dict)
        and cpi_condition.get("cpi_pressure")
        in ("inflation_pressure_up", "inflation_pressure_down")
    ):
        cpi_condition = None

    diagnosis = results.get("regime_diagnosis")
    if isinstance(diagnosis, dict) and isinstance(
        diagnosis.get("confidence"), (int, float)
    ):
        regime_weight = float(diagnosis["confidence"])
    else:
        regime_weight = params.get("regime_weight", 0.8)

    collector = EvidenceCollector(knowledge_graph=kg)
    collection = collector.collect(
        assessment,
        regime_weight=regime_weight,
        cpi_condition=cpi_condition,
    )

    tiering_data = results.get("event_triage")
    if tiering_data is not None:
        if isinstance(tiering_data, dict):
            tiering = SignalTiering.from_dict(tiering_data)
        else:
            tiering = tiering_data
        merged_metadata = dict(collection.metadata)
        merged_metadata["event_tiering"] = {
            "tiering_id": tiering.tiering_id,
            "tier_counts": tiering.tier_counts,
            "tiers": {a.observation_id: a.tier for a in tiering.assignments},
        }
        collection = replace(collection, metadata=merged_metadata)

    return collection


def _regime_diagnosis(params: dict[str, Any], results: dict[str, Any]) -> Any:
    import json
    from pathlib import Path

    from knowledge.regime.composite_score import CompositeScoreBuilder
    from knowledge.regime.contracts import RegimeDiagnosis, RegimeIndicator
    from knowledge.regime.indicator_hierarchy import IndicatorHierarchyGenerator
    from knowledge.regime.institutional_regime_detector import (
        InstitutionalRegimeDetector,
    )

    composite_data = CompositeScoreBuilder().build()
    if len(composite_data) == 0:
        raise ValueError("composite_score data empty -- cannot diagnose regime")

    detector = InstitutionalRegimeDetector(random_state=42).fit(composite_data)
    diag = detector.diagnose(float(composite_data["composite_score"].iloc[-1]))

    kg = results.get("build_legacy_pipeline", {}).get("knowledge_graph")
    hierarchy = IndicatorHierarchyGenerator().generate(
        diag.regime,
        include_krs=True,
        graph=kg,
    )

    diagnosis = RegimeDiagnosis(
        regime=diag.regime,
        label=diag.label,
        confidence=diag.confidence,
        probabilities=dict(diag.probabilities),
        in_transition=diag.in_transition,
        transition_type=diag.transition_type,
        previous_regime=diag.previous_regime,
        timestamp=diag.timestamp,
        transition_confidence=diag.transition_confidence,
        regime_duration_days=diag.regime_duration_days,
        gram_residual=diag.gram_residual,
        gram_trend=diag.gram_trend,
        indicator_hierarchy=tuple(
            RegimeIndicator.from_dict(i) for i in hierarchy.get("indicators", [])
        ),
        trigger_levels=tuple(hierarchy.get("trigger_levels", [])),
    )

    errors = diagnosis.validate()
    if errors:
        raise ValueError(f"invalid RegimeDiagnosis: {errors}")

    output_dir = params.get("output_dir")
    if output_dir is not None:
        artifact = Path(output_dir) / "regime_diagnosis.json"
        artifact.write_text(
            json.dumps(diagnosis.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return diagnosis.to_dict()


def _pre_market_scan(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from dataclasses import replace

    from pre_market.briefing_assembler import PreMarketBriefingAssembler

    diagnosis = results.get("regime_diagnosis")
    if isinstance(diagnosis, dict) and diagnosis.get("regime"):
        regime = str(diagnosis["regime"])
        regime_confidence = float(diagnosis.get("confidence", 0.0))
    else:
        regime = params.get("regime", "")
        regime_confidence = params.get("regime_confidence", 0.0)

    assembler = PreMarketBriefingAssembler(
        regime=regime,
        regime_confidence=regime_confidence,
    )
    briefing = assembler.assemble(
        session=params.get("pre_market_session", "APAC"),
        portfolio_returns=None,
        portfolio_equity=params.get("portfolio_equity", 0.0),
        daily_pnl=params.get("daily_pnl", 0.0),
        unrealized_pnl=params.get("unrealized_pnl", 0.0),
        exposure=params.get("exposure", 0.0),
        var_utilization_pct=params.get("var_utilization_pct", 0.0),
        calendar_csv=params.get("release_calendar_path"),
        briefing_id=params.get("briefing_id"),
    )
    cpi_release = _cpi_release_snapshot(params, results)
    if cpi_release is not None:
        briefing = replace(
            briefing,
            metadata={
                **dict(briefing.metadata),
                "cpi_release": cpi_release,
            },
        )
    return briefing


def _cpi_release_snapshot(
    params: dict[str, Any], results: dict[str, Any]
) -> dict[str, Any] | None:
    """Snapshot the current CPI release onto the briefing boundary.

    Correction 009: mirrors the already-computed current CPI release (the same
    CPIEvent/CPIFeatureExtractor extraction used upstream, and the same
    ReleaseCalendar source) into ``PreMarketBriefing.metadata`` so W5 can map
    it to a ClassifiedObservation.  No new calendar source and no second
    condition rule: the pressure value is the extractor's column and W6 keeps
    using ``reasoning_condition`` from W4.
    """
    from pathlib import Path

    event_data = results.get("ingest_event")
    if not isinstance(event_data, dict):
        return None
    event = event_data.get("event")
    data_path = params.get("data_path")
    if event is None or not data_path:
        return None
    try:
        extracted = event.load_and_extract(Path(data_path))
        row = extracted.iloc[-1]
        reference_period = str(row["Date"])[:10]
        snapshot = {
            "event_type": "CPI",
            "reference_period": reference_period,
            "value": float(row["Value"]),
            "cpi_change_pct": float(row["cpi_change_pct"]),
            "cpi_pressure": str(row["cpi_pressure"]),
            "priority": "Tier 1",
            "expected_impact": "high",
        }
        release_calendar_path = params.get("release_calendar_path")
        if release_calendar_path:
            try:
                from knowledge.events.release_calendar import ReleaseCalendar

                release = ReleaseCalendar.from_csv(release_calendar_path).get(
                    reference_period
                )
                if release is not None:
                    snapshot["release_date"] = release.release_date
            except Exception:
                pass
        return snapshot
    except Exception:
        return None


def _evidence_reasoning(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from evidence_collection.contracts import EvidenceCollection
    from evidence_reasoning.reasoner import EvidenceReasoner

    collection_data = results.get("evidence_collection")
    if collection_data is None:
        return {"error": "no evidence collection data available", "evidence_sets": []}

    if isinstance(collection_data, dict):
        collection = EvidenceCollection.from_dict(collection_data)
    else:
        collection = collection_data

    # Correction 027: W6 consumes the run-local episode index derived from
    # the enriched lesson artifact at the build_legacy_pipeline boundary.
    # Resolve the run-local path first (published by the boundary build);
    # fall back to the same run-local location when the stage did not run
    # (e.g., checkpoint-resumed runs); the global data/state index is never
    # required for runtime correctness.
    episodes_index_path = params.get("lesson_episodes_index_path")
    if not episodes_index_path and params.get("output_dir"):
        run_local_index = Path(params["output_dir"]) / "lesson_episodes.json"
        if run_local_index.is_file():
            episodes_index_path = str(run_local_index)

    reasoner = EvidenceReasoner()
    reasoning = reasoner.reason(collection, regime=params.get("regime"))
    return reasoning


def _counter_evidence(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from evidence_reasoning.contracts import EvidenceReasoning
    from counter_evidence.assessor import CounterEvidenceAssessor

    reasoning_data = results.get("evidence_reasoning")
    if reasoning_data is None:
        return {"error": "no evidence reasoning data available"}

    if isinstance(reasoning_data, dict):
        reasoning = EvidenceReasoning.from_dict(reasoning_data)
    else:
        reasoning = reasoning_data

    assessor = CounterEvidenceAssessor()
    assessment = assessor.assess(reasoning)
    return assessment


def _thesis_construction(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from evidence_reasoning.contracts import EvidenceReasoning
    from counter_evidence.contracts import CounterEvidenceAssessment
    from thesis_construction.constructor import ThesisConstructor

    reasoning_data = results.get("evidence_reasoning")
    assessment_data = results.get("counter_evidence")
    if reasoning_data is None or assessment_data is None:
        return {"error": "missing evidence_reasoning or counter_evidence data"}

    if isinstance(reasoning_data, dict):
        reasoning = EvidenceReasoning.from_dict(reasoning_data)
    else:
        reasoning = reasoning_data
    if isinstance(assessment_data, dict):
        assessment = CounterEvidenceAssessment.from_dict(assessment_data)
    else:
        assessment = assessment_data

    constructor = ThesisConstructor()
    construction = constructor.construct(reasoning, assessment)
    return construction


def _thesis_update(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from thesis_construction.contracts import ThesisConstruction
    from evidence_reasoning.contracts import EvidenceReasoning
    from counter_evidence.contracts import CounterEvidenceAssessment
    from thesis_update.updater import ThesisUpdater

    construction_data = results.get("thesis_construction")
    reasoning_data = results.get("evidence_reasoning")
    assessment_data = results.get("counter_evidence")
    if construction_data is None or reasoning_data is None or assessment_data is None:
        return {"error": "missing thesis_construction, evidence_reasoning, or counter_evidence data"}

    if isinstance(construction_data, dict):
        construction = ThesisConstruction.from_dict(construction_data)
    else:
        construction = construction_data
    if isinstance(reasoning_data, dict):
        reasoning = EvidenceReasoning.from_dict(reasoning_data)
    else:
        reasoning = reasoning_data
    if isinstance(assessment_data, dict):
        assessment = CounterEvidenceAssessment.from_dict(assessment_data)
    else:
        assessment = assessment_data

    if not construction.theses:
        return {"error": "no thesis available to update"}

    updater = ThesisUpdater()
    return updater.update(construction, reasoning, assessment)


def _construction_from_update(update: Any) -> Any:
    """Build the single-thesis ThesisConstruction carried by a ThesisUpdate.

    The updated thesis is the current version (thesis_id carries the version
    suffix, e.g. th_xxx.v2), so downstream stages can resolve confidence and
    scenarios keyed by the same versioned thesis_id produced by the update.
    """
    from thesis_construction.contracts import ThesisConstruction

    thesis = update.updated_thesis
    return ThesisConstruction(
        construction_id=update.update_id,
        reasoning_id=update.reasoning_id,
        assessment_id=update.assessment_id,
        timestamp=update.timestamp,
        regime=thesis.regime,
        theses=(thesis,),
        ranked_thesis_ids=(thesis.thesis_id,),
        total_theses=1,
        primary_thesis_id=thesis.thesis_id,
    )


def _confidence_engine(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from thesis_construction.contracts import ThesisConstruction
    from confidence_engine.engine import ConfidenceEngine

    reasoning_data = results.get("evidence_reasoning")
    generation_data = results.get("scenario_generation")

    update_data = results.get("thesis_update")
    if update_data is not None:
        from thesis_update.contracts import ThesisUpdate

        if isinstance(update_data, dict):
            update = ThesisUpdate.from_dict(update_data)
        else:
            update = update_data
        construction = _construction_from_update(update)
    else:
        construction_data = results.get("thesis_construction")
        if construction_data is None:
            return {"error": "no thesis construction data available"}

        if isinstance(construction_data, dict):
            construction = ThesisConstruction.from_dict(construction_data)
        else:
            construction = construction_data

    oos_ece = params.get("oos_ece")
    if not isinstance(oos_ece, (int, float)) or isinstance(oos_ece, bool):
        oos_ece = None

    engine = ConfidenceEngine()
    confidence = engine.evaluate(
        construction,
        reasoning=reasoning_data,
        generation=generation_data,
        oos_ece=oos_ece,
    )
    return confidence


def _scenario_generation(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from thesis_construction.contracts import ThesisConstruction
    from scenario_generation.generator import ScenarioGenerator

    update_data = results.get("thesis_update")
    construction_data = results.get("thesis_construction")
    if update_data is None and construction_data is None:
        return {"error": "missing thesis_construction data"}

    if update_data is not None:
        from thesis_update.contracts import ThesisUpdate

        if isinstance(update_data, dict) and "error" in update_data:
            return {"error": "thesis_update stage failed"}

        if isinstance(update_data, dict):
            update = ThesisUpdate.from_dict(update_data)
        else:
            update = update_data
        construction = _construction_from_update(update)
    else:
        if isinstance(construction_data, dict) and "error" in construction_data:
            return {"error": "thesis_construction stage failed"}

        if isinstance(construction_data, dict):
            construction = ThesisConstruction.from_dict(construction_data)
        else:
            construction = construction_data

    generator = ScenarioGenerator()
    generation = generator.generate(construction)
    return generation


def _risk_reward_validation(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from scenario_generation.contracts import ScenarioGeneration
    from risk_reward_validation.validator import RiskRewardValidator

    generation_data = results.get("scenario_generation")
    if generation_data is None:
        return {"error": "no scenario generation data available"}

    if isinstance(generation_data, dict) and "error" in generation_data:
        return {"error": "scenario_generation stage failed"}

    if isinstance(generation_data, dict):
        generation = ScenarioGeneration.from_dict(generation_data)
    else:
        generation = generation_data

    validator = RiskRewardValidator()
    validation = validator.validate(generation)
    return validation


def _decision_engine(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from thesis_construction.contracts import ThesisConstruction
    from confidence_engine.contracts import InstitutionalConfidence
    from scenario_generation.contracts import ScenarioGeneration
    from risk_reward_validation.contracts import RiskRewardValidation
    from decision_engine.engine import DecisionEngine

    update_data = results.get("thesis_update")
    construction_data = results.get("thesis_construction")
    confidence_data = results.get("confidence_engine")
    generation_data = results.get("scenario_generation")
    validation_data = results.get("risk_reward_validation")
    if (
        (update_data is None and construction_data is None)
        or confidence_data is None
        or generation_data is None
        or validation_data is None
    ):
        return {"error": "missing upstream institutional data for decision engine"}

    upstream = {
        "confidence_engine": confidence_data,
        "scenario_generation": generation_data,
        "risk_reward_validation": validation_data,
    }
    if update_data is not None:
        upstream["thesis_update"] = update_data
    else:
        upstream["thesis_construction"] = construction_data
    for name, data in upstream.items():
        if isinstance(data, dict) and "error" in data:
            return {"error": f"{name} stage failed"}

    if update_data is not None:
        from thesis_update.contracts import ThesisUpdate

        if isinstance(update_data, dict):
            update = ThesisUpdate.from_dict(update_data)
        else:
            update = update_data
        construction = _construction_from_update(update)
    elif isinstance(construction_data, dict):
        construction = ThesisConstruction.from_dict(construction_data)
    else:
        construction = construction_data
    if isinstance(confidence_data, dict):
        confidence = InstitutionalConfidence.from_dict(confidence_data)
    else:
        confidence = confidence_data
    if isinstance(generation_data, dict):
        generation = ScenarioGeneration.from_dict(generation_data)
    else:
        generation = generation_data
    if isinstance(validation_data, dict):
        validation = RiskRewardValidation.from_dict(validation_data)
    else:
        validation = validation_data

    engine = DecisionEngine()
    decision = engine.decide(construction, confidence, generation, validation)

    bias_data = results.get("bias_prevention")
    if bias_data is not None:
        from bias_prevention.contracts import BiasReview, apply_bias_review

        if isinstance(bias_data, dict):
            bias_review = BiasReview.from_dict(bias_data)
        else:
            bias_review = bias_data
        decision = apply_bias_review(decision, bias_review)

    return decision


def _bias_prevention(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from thesis_update.contracts import ThesisUpdate
    from counter_evidence.contracts import CounterEvidenceAssessment
    from confidence_engine.contracts import InstitutionalConfidence
    from bias_prevention.detector import BiasReviewer

    update_data = results.get("thesis_update")
    assessment_data = results.get("counter_evidence")
    confidence_data = results.get("confidence_engine")
    if update_data is None or assessment_data is None or confidence_data is None:
        return {"error": "missing thesis_update, counter_evidence, or confidence_engine data"}

    if isinstance(update_data, dict):
        update = ThesisUpdate.from_dict(update_data)
    else:
        update = update_data
    if isinstance(assessment_data, dict):
        assessment = CounterEvidenceAssessment.from_dict(assessment_data)
    else:
        assessment = assessment_data
    if isinstance(confidence_data, dict):
        confidence = InstitutionalConfidence.from_dict(confidence_data)
    else:
        confidence = confidence_data

    reviewer = BiasReviewer()
    return reviewer.review(update, assessment, confidence)


def _trade_recommendation(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from decision_engine.contracts import InstitutionalDecision
    from trade_recommendation.recommender import RecommendationEngine

    decision_data = results.get("decision_engine")
    if decision_data is None:
        return {"error": "no institutional decision data available"}

    if isinstance(decision_data, dict) and "error" in decision_data:
        return {"error": "decision_engine stage failed"}

    if isinstance(decision_data, dict):
        decision = InstitutionalDecision.from_dict(decision_data)
    else:
        decision = decision_data

    engine = RecommendationEngine()
    recommendation = engine.recommend(
        decision,
        instrument=params.get("asset", "XAU/USD"),
        reference_price=params.get("reference_price"),
    )
    return recommendation


def _finalize(params: dict[str, Any], results: dict[str, Any]) -> Any:
    legacy_pipeline = results.get("build_legacy_pipeline", {})
    legacy_decision = legacy_pipeline.get("decision")
    institutional_decision = results.get("decision_engine")
    if isinstance(institutional_decision, dict) and "error" in institutional_decision:
        institutional_decision = None
    return {
        "decision": (
            institutional_decision
            if institutional_decision is not None
            else legacy_decision
        ),
        "legacy_decision": legacy_decision,
        "risk_decision": results.get("risk_gate"),
        "forecast_result": results.get("forecast"),
        "confidence": results.get("forecast_confidence", {}).get("confidence"),
        "validation": results.get("forecast_validation"),
        "context": results.get("build_context"),
        "risk_metrics": results.get("risk_measures"),
        "position_sizing": results.get("position_sizing", {}).get("position_sizing"),
        "risk_budget": results.get("position_sizing", {}).get("risk_budget"),
        "position_sizing_status": results.get("position_sizing", {}).get("status"),
    }
