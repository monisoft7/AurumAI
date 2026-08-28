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
    """Sprint 058: news ingestion with explicit failure states.

    Returns ``{status, reason, items, fomc_events, ...}``.  A missing
    dependency or failed feed never silently produces an empty news day:
    ``status='unavailable'`` distinguishes it from ``status='empty'``.
    The FOMC calendar stays a separate channel (``fomc_events``) with its
    own ``fomc_status``.
    """
    import datetime as _dt

    from news.intelligence import run_news_intelligence

    topics = tuple(params.get("news_topics", ("gold", "inflation", "fed")))
    lookback_days = int(params.get("news_lookback_days", 7))
    max_articles = int(params.get("news_max_articles", 20))
    as_of = params.get("news_as_of")
    if as_of is None:
        # No-lookahead gate: an article published after the decision time
        # must never enter the run.  Deterministic callers anchor the clock
        # via ``news_as_of`` (historical replay) or ``_news_now``; live runs
        # gate on the same wall clock that stamps ``ingested_at``.
        as_of = params.get("_news_now") or _dt.datetime.now(_dt.timezone.utc)

    payload = run_news_intelligence(
        topics=topics,
        lookback_days=lookback_days,
        max_articles=max_articles,
        as_of=as_of,
        data_source=params.get("_news_data_source"),
        now=params.get("_news_now"),
        sentiment_analyzer=params.get("_news_sentiment_analyzer"),
    )

    payload["topics"] = list(topics)
    payload["lookback_days"] = lookback_days

    # --- FOMC calendar (separate channel, explicit status) ---------------
    fomc_events: list[dict[str, Any]] = []
    fomc_status = "ok"
    fomc_reason = ""
    try:
        from connectors.fomc_calendar import FOMCCalendarConnector

        fomc = FOMCCalendarConnector(auto_refresh=False)
        anchor = params.get("fomc_as_of")
        anchor_date = (
            _dt.date.fromisoformat(str(anchor))
            if anchor
            else _dt.date.today()
        )
        start = anchor_date - _dt.timedelta(days=lookback_days)
        end = anchor_date + _dt.timedelta(days=90)
        for meeting in fomc.meetings_between(start, end):
            fomc_events.append(
                {
                    "event_type": "FOMC",
                    "start_date": meeting.start_date.isoformat(),
                    "end_date": meeting.end_date.isoformat(),
                    "is_two_day": bool(meeting.is_two_day),
                    "has_press_conference": bool(meeting.has_press_conference),
                    "statement_time": str(meeting.statement_time),
                    "minutes_release_date": meeting.minutes_release_date.isoformat(),
                }
            )
    except Exception as exc:
        fomc_status = "unavailable"
        fomc_reason = f"{type(exc).__name__}: {exc}"

    payload["fomc_events"] = fomc_events
    payload["fomc_status"] = fomc_status
    payload["fomc_reason"] = fomc_reason

    # Sprint 061: additive canonical-fact references (observability only).
    # Never alters classification, status semantics or decision inputs.
    try:
        from knowledge.facts.builders import news_fact_references

        payload["fact_references"] = news_fact_references(payload)
    except Exception as exc:
        payload["fact_references"] = {
            "status": "error",
            "reason": f"{type(exc).__name__}: {exc}",
        }
    return payload


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
        UNAVAILABLE_METHOD_PREFIX,
        RiskMetrics,
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
        # Final Hardening (D-03/D-11): the previous rng-seeded substitution
        # fabricated random "risk metrics" that reached the risk gate.  A
        # degenerate forecast interval distribution is now an explicit
        # unavailable state; the gate treats it as not-acceptable.
        return RiskMetrics(
            var_95=0.0,
            var_99=0.0,
            cvar_95=0.0,
            tail_index=None,
            method=f"{UNAVAILABLE_METHOD_PREFIX}_degenerate_forecast_intervals",
        )

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
    from forecasting.risk_measures import UNAVAILABLE_METHOD_PREFIX

    risk_metrics = results.get("risk_measures")
    context = results.get("build_context")

    regime_label = context.current_regime if context else None
    regime_confidence = context.regime_confidence if context else 0.0
    overlay = RegimeRiskOverlay()
    regime_info = overlay.evaluate(regime_label or "UNKNOWN", regime_confidence)

    var_95 = getattr(risk_metrics, "var_95", None) if risk_metrics else None
    tail_index = getattr(risk_metrics, "tail_index", None) if risk_metrics else None
    method = str(getattr(risk_metrics, "method", "") or "") if risk_metrics else ""
    unavailable = method.startswith(UNAVAILABLE_METHOD_PREFIX)
    budget = UncertaintyBudget()
    if unavailable:
        # Final Hardening (D-03/D-11): with no honest risk input the gate
        # must not treat fabricated numbers as an acceptable budget.  An
        # unavailable state reads as NOT acceptable (delay), never success.
        uncertainty = {
            "acceptable": False,
            "coherence_ok": True,
            "var_ok": False,
            "tail_ok": True,
            "unavailable": True,
        }
    else:
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

    if unavailable:
        from dataclasses import replace as _replace

        gate_result = _replace(
            gate_result,
            reason=(
                f"risk measures unavailable ({method}); gate cannot verify "
                "the uncertainty budget and does not proceed as if healthy"
            ),
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

    composite_data, composite_provenance = (
        CompositeScoreBuilder().build_with_provenance()
    )
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

    payload = diagnosis.to_dict()

    # Final Hardening (D-03): synthetic-input exclusion is surfaced, never
    # silently swallowed -- the payload records which indicators were
    # excluded as synthetic placeholders from the regime composite.
    payload["composite_provenance"] = composite_provenance

    # Sprint 061: additive canonical-fact references (observability only).
    # Gives the macro/regime desk its first durable identity without
    # touching RegimeDiagnosis semantics; explicit as_of keeps it deterministic.
    try:
        from knowledge.facts.builders import regime_fact_references

        payload["fact_references"] = regime_fact_references(
            payload,
            as_of=params.get("regime_as_of") or diagnosis.timestamp[:10],
        )
    except Exception as exc:
        payload["fact_references"] = {
            "status": "error",
            "reason": f"{type(exc).__name__}: {exc}",
        }

    output_dir = params.get("output_dir")
    if output_dir is not None:
        artifact = Path(output_dir) / "regime_diagnosis.json"
        artifact.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return payload


def _news_stage_items(params: dict[str, Any], results: dict[str, Any]) -> list[Any] | None:
    """Resolve news items produced by the ingest_news stage (Sprint 058).

    Returns None when no stage output exists at all (standalone calls,
    legacy checkpoints) so the caller can fall back to internal ingestion.
    A present-but-unavailable/empty payload returns [] -- never re-fetched.
    """
    from news.intelligence import to_pre_market_news_items

    stage = results.get("ingest_news")
    if stage is None:
        return None
    if isinstance(stage, dict) and "items" in stage:
        if stage.get("status") == "ok":
            return to_pre_market_news_items(stage)
        return []
    if isinstance(stage, dict):
        # Legacy checkpoint payload: raw news_items dicts without status.
        return to_pre_market_news_items({"items": stage.get("news_items", [])})
    return []


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
        external_news_items=_news_stage_items(params, results),
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

    Final Hardening (D-11): when stage inputs exist but the snapshot cannot
    be produced, the failure is explicit (``status: unavailable`` + reason)
    instead of a silent ``None``.
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
            "status": "ok",
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
            except Exception as exc:
                snapshot["release_date_status"] = "unavailable"
                snapshot["release_date_reason"] = f"{type(exc).__name__}: {exc}"
        return snapshot
    except Exception as exc:
        return {
            "event_type": "CPI",
            "status": "unavailable",
            "reason": f"{type(exc).__name__}: {exc}",
        }


def _evidence_reasoning(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from evidence_collection.contracts import EvidenceCollection
    from evidence_reasoning.reasoner import EvidenceReasoner
    from evidence_reasoning.historical_analogue import build_historical_analogue

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

    # Correction 025-B: explanation-only historical gold analogue built from
    # the existing current configuration.  None on missing/empty index or no
    # passing match -> reasoning metadata is unchanged and the pipeline
    # continues normally.
    analogue = build_historical_analogue(
        cpi_condition=results.get("build_legacy_pipeline", {}).get(
            "reasoning_condition"
        ),
        regime=(params.get("regime") or (results.get("regime_diagnosis") or {}).get("regime")),
        real_yield_path=params.get("yield_data_path"),
        dxy_path=params.get("dxy_data_path"),
        lookback_days=int(params.get("yield_context_lookback_days", 30)),
        episodes_index_path=episodes_index_path,
    )

    reasoner = EvidenceReasoner()
    reasoning = reasoner.reason(
        collection,
        regime=params.get("regime"),
        historical_analogue=analogue,
    )
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


def _technical_research_context(assessment_payload: Any) -> dict[str, Any] | None:
    """Final Hardening (Group F, D-07): compact non-scoring research context
    from the Technical Research Desk artifact (trend / momentum / structure /
    volatility / confirmations / contradictions).  Research-layer context
    only -- it never feeds weights, confidence, or selection.
    """
    if not isinstance(assessment_payload, dict) or "error" in assessment_payload:
        return None
    metadata = assessment_payload.get("metadata") or {}
    structure = metadata.get("structure") or {}
    return {
        "assessment_id": assessment_payload.get("assessment_id"),
        "as_of": assessment_payload.get("as_of"),
        "timeframe": assessment_payload.get("timeframe"),
        "trend_direction": assessment_payload.get("trend_direction"),
        "momentum_direction": assessment_payload.get("momentum_direction"),
        "structure_state": assessment_payload.get("structure_state"),
        "volatility_state": assessment_payload.get("volatility_state"),
        "bos_flag": structure.get("bos_flag"),
        "supporting_indicators": list(
            assessment_payload.get("supporting_indicators") or ()
        ),
        "conflicting_indicators": list(
            assessment_payload.get("conflicting_indicators") or ()
        ),
        "technical_confidence": assessment_payload.get("technical_confidence"),
    }


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

    # Final Hardening (Group F, D-07): the Technical Research Desk joins the
    # research layer as metadata context on every candidate thesis.
    technical_context = _technical_research_context(
        results.get("technical_research")
    )

    constructor = ThesisConstructor()
    construction = constructor.construct(
        reasoning, assessment, technical_context=technical_context
    )
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


def _construction_from_update(update: Any, original: Any = None) -> Any:
    """Splice the versioned updated primary into the original candidate set.

    The updated thesis is the new version of the previous primary
    (thesis_id carries the version suffix, e.g. th_xxx.v2).  The original
    W8 candidate set is preserved so W9/W12/W13 can still evaluate every
    candidate: the previous primary is replaced by its versioned successor,
    ``primary_thesis_id`` is re-pointed to the versioned id, and
    ``ranked_thesis_ids`` are re-derived with the existing
    institutional-support ranking semantics.

    Falls back to the previous single-thesis reconstruction when the
    original construction is unavailable (None or an error payload), so
    downstream consumers can still resolve confidence and scenarios keyed
    by the versioned thesis_id produced by the update.
    """
    from thesis_construction.contracts import ThesisConstruction

    thesis = update.updated_thesis

    base: ThesisConstruction | None = None
    if isinstance(original, ThesisConstruction):
        base = original
    elif isinstance(original, dict) and original.get("theses"):
        base = ThesisConstruction.from_dict(original)

    spliced: list[Any] = []
    replaced = False
    for t in (base.theses if base is not None else ()):
        if t.thesis_id == update.previous_thesis_id:
            spliced.append(thesis)
            replaced = True
        else:
            spliced.append(t)
    if not replaced:
        spliced.append(thesis)

    ranked_ids = [
        t.thesis_id
        for t in sorted(spliced, key=lambda t: t.institutional_support, reverse=True)
    ]

    if base is not None:
        return ThesisConstruction(
            construction_id=update.update_id,
            reasoning_id=base.reasoning_id,
            assessment_id=base.assessment_id,
            timestamp=update.timestamp,
            regime=base.regime,
            theses=tuple(spliced),
            ranked_thesis_ids=tuple(ranked_ids),
            total_theses=len(spliced),
            primary_thesis_id=thesis.thesis_id,
            metadata=dict(base.metadata),
        )
    return ThesisConstruction(
        construction_id=update.update_id,
        reasoning_id=update.reasoning_id,
        assessment_id=update.assessment_id,
        timestamp=update.timestamp,
        regime=thesis.regime,
        theses=tuple(spliced),
        ranked_thesis_ids=tuple(ranked_ids),
        total_theses=len(spliced),
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
        construction = _construction_from_update(
            update, results.get("thesis_construction")
        )
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
        construction = _construction_from_update(
            update, results.get("thesis_construction")
        )
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
        construction = _construction_from_update(update, construction_data)
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
            primary_review = BiasReview.from_dict(bias_data)
        else:
            primary_review = bias_data

        # Final Hardening (Group A, D-04): gate the decision with the
        # review of the thesis it was actually made on.  Reviews of other
        # candidates are recorded as advisories only.
        reviews_by_thesis: dict[str, BiasReview] = {}
        if isinstance(bias_data, dict):
            raw_map = bias_data.get("reviews_by_thesis")
            if isinstance(raw_map, dict):
                reviews_by_thesis = {
                    str(tid): BiasReview.from_dict(r)
                    for tid, r in raw_map.items()
                    if isinstance(r, dict)
                }
        selected_id = decision.selected_thesis_id
        if reviews_by_thesis:
            review = reviews_by_thesis.get(selected_id)
            others = [r for tid, r in reviews_by_thesis.items() if tid != selected_id]
            if review is None:
                # Selected thesis carries no review entry (legacy checkpoint
                # or single-candidate edge): fall back to the primary review
                # as an advisory so nothing silently disappears.
                review = primary_review
        else:
            review = primary_review
            others = []
        decision = apply_bias_review(decision, review, other_reviews=others)

    return decision


def _bias_prevention(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from thesis_construction.contracts import ThesisConstruction
    from thesis_update.contracts import ThesisUpdate
    from counter_evidence.contracts import CounterEvidenceAssessment
    from confidence_engine.contracts import InstitutionalConfidence
    from bias_prevention.detector import BiasReviewer

    update_data = results.get("thesis_update")
    assessment_data = results.get("counter_evidence")
    confidence_data = results.get("confidence_engine")
    construction_data = results.get("thesis_construction")
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
    primary_review = reviewer.review(update, assessment, confidence)

    # Final Hardening (Group A, D-04): review EVERY candidate so the
    # decision can be gated by the review of the thesis it was actually
    # made on.  The payload keeps the flat primary-review shape (legacy
    # checkpoints/consumers keep working) and adds an additive
    # ``reviews_by_thesis`` map.
    payload = primary_review.to_dict()
    construction: ThesisConstruction | None = None
    if construction_data is not None and not (
        isinstance(construction_data, dict) and "error" in construction_data
    ):
        if isinstance(construction_data, dict):
            construction = ThesisConstruction.from_dict(construction_data)
        else:
            construction = construction_data
    if construction is not None:
        reviews = reviewer.review_candidates(
            construction, update, assessment, confidence
        )
        payload["reviews_by_thesis"] = {
            thesis_id: review.to_dict() for thesis_id, review in reviews.items()
        }
    return payload


def _resolve_atr_context(
    gold_path: str | None, as_of: str | None
) -> tuple[float | None, dict[str, Any] | None]:
    """Final Hardening (Group C, D-01): market-anchored stop/target widths
    need ATR(14) from the run's own gold OHLCV data.

    Reuses the existing technical-desk machinery (validated frame prep +
    deterministic as-of slicing + the pandas-ta-classic engine).  ATR-14
    needs far less history than the desk's full EMA-200 assessment, so the
    engine is applied to the prepared as-of slice with an ATR-appropriate
    minimum of 30 bars.  Returns ``(atr, provenance)``; a None atr with an
    explicit provenance reason means the levels fall back to the labeled
    conviction heuristic -- no volatility number is ever invented.
    """
    import datetime

    import numpy as np
    import pandas as pd

    from technical.desk import TechnicalResearchDesk
    from technical.engine import PandasTaClassicEngine

    if not gold_path:
        return None, {"status": "unavailable", "reason": "no gold_path"}
    effective_as_of = as_of or datetime.date.today().isoformat()
    try:
        frame = TechnicalResearchDesk._prepare_frame(
            pd.read_csv(gold_path)
        )
        sliced = TechnicalResearchDesk._slice_as_of(frame, str(effective_as_of))
        if len(sliced) < 30:
            return None, {
                "status": "unavailable",
                "reason": (
                    f"insufficient history for ATR-14: {len(sliced)} bars "
                    "available, 30 required"
                ),
                "as_of": str(effective_as_of),
            }
        indicators = PandasTaClassicEngine().compute(sliced)
        atr_value = indicators["atr_14"].iloc[-1]
        if atr_value is None or not np.isfinite(float(atr_value)) or float(atr_value) <= 0.0:
            return None, {
                "status": "unavailable",
                "reason": "atr_14 not finite on the as-of slice",
                "as_of": str(effective_as_of),
            }
        atr_value = float(atr_value)
        provenance = {
            "status": "ok",
            "atr_14": round(atr_value, 6),
            "as_of": str(effective_as_of),
            "bar_date": str(sliced.index[-1].date()),
            "bars_used": int(len(sliced)),
            "engine": "pandas_ta_classic:atr_14",
        }
        return atr_value, provenance
    except Exception as exc:
        return None, {
            "status": "unavailable",
            "reason": f"{type(exc).__name__}: {exc}",
            "as_of": str(effective_as_of),
        }


def _trade_recommendation(params: dict[str, Any], results: dict[str, Any]) -> Any:
    from decision_engine.contracts import InstitutionalDecision
    from trade_recommendation.recommender import RecommendationEngine
    from trade_recommendation.reference_price import resolve_reference_price

    decision_data = results.get("decision_engine")
    if decision_data is None:
        return {"error": "no institutional decision data available"}

    if isinstance(decision_data, dict) and "error" in decision_data:
        return {"error": "decision_engine stage failed"}

    if isinstance(decision_data, dict):
        decision = InstitutionalDecision.from_dict(decision_data)
    else:
        decision = decision_data

    # Sprint 057: resolve the reference price end-to-end.  An explicit param
    # always wins; otherwise the latest valid close from the run's own gold
    # data is used.  When neither is available the recommender keeps its
    # relative-anchor behaviour and the fallback is announced in metadata --
    # no price is ever invented.
    reference_price = params.get("reference_price")
    if reference_price is not None:
        reference_provenance: dict[str, Any] | None = {
            "status": "explicit_param",
            "value": float(reference_price),
        }
    else:
        resolved, reason = resolve_reference_price(
            params.get("gold_path"),
            as_of=params.get("reference_as_of"),
        )
        if resolved is not None:
            reference_price = resolved.value
            reference_provenance = {
                "status": "resolved_from_gold_data",
                **resolved.to_dict(),
            }
        else:
            reference_provenance = {
                "status": "unavailable_relative_anchor_fallback",
                "reason": reason,
            }

    engine = RecommendationEngine()
    atr, atr_provenance = _resolve_atr_context(
        params.get("gold_path"),
        params.get("technical_as_of") or params.get("reference_as_of"),
    )
    recommendation = engine.recommend(
        decision,
        instrument=params.get("asset", "XAU/USD"),
        reference_price=reference_price,
        reference_provenance=reference_provenance,
        atr=atr,
        atr_provenance=atr_provenance,
    )

    # Final Hardening (Group D, D-06): the executable recommendation is a
    # first-class run artifact -- entry/stop/target/RR reach the outputs
    # directory alongside the decision instead of dying in memory.
    import json as _json
    from pathlib import Path as _Path

    output_dir = params.get("output_dir")
    if output_dir:
        artifact = _Path(output_dir) / "trade_recommendation.json"
        try:
            artifact.write_text(
                _json.dumps(recommendation.to_dict(), indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError as exc:
            # Final Hardening closure: a failed artifact write is never
            # silent.  The stage's established fail-safe contract is an
            # explicit error payload surfaced through finalize; the
            # in-memory recommendation rides along so no decision data is
            # dropped.  Non-I/O failures are programming errors and
            # propagate to the stage failure channel.
            return {
                "error": (
                    "trade_recommendation.json write failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
                "recommendation": recommendation.to_dict(),
            }
    return recommendation


def _thesis_historical_assessments(
    results: dict[str, Any],
) -> list[dict[str, Any]] | None:
    """Candidate-scoped historical assessments for the finalize artifact.

    Correction 034: observability only.  Resolves the final candidate set
    exactly like the W9/W12/W13 boundary (``_construction_from_update``), so
    the W10-versioned primary is the one exposed.  Each entry wraps the
    verbatim in-memory ``historical_assessment`` -- nothing is recalculated,
    and no synthetic id or timestamp is introduced.  Candidates without a
    historical payload are listed with ``historical_assessment: null``.
    Returns ``None`` when no candidate collection is available, keeping the
    finalize payload byte-identical to before for legacy-only runs.
    """
    from thesis_construction.contracts import ThesisConstruction
    from thesis_update.contracts import ThesisUpdate

    update_data = results.get("thesis_update")
    construction_data = results.get("thesis_construction")
    if update_data is not None and not (
        isinstance(update_data, dict) and "error" in update_data
    ):
        update = (
            ThesisUpdate.from_dict(update_data)
            if isinstance(update_data, dict)
            else update_data
        )
        construction = _construction_from_update(update, construction_data)
    elif construction_data is not None and not (
        isinstance(construction_data, dict) and "error" in construction_data
    ):
        construction = (
            ThesisConstruction.from_dict(construction_data)
            if isinstance(construction_data, dict)
            else construction_data
        )
    else:
        return None

    if not construction.theses:
        return None

    return [
        {
            "thesis_id": thesis.thesis_id,
            "thesis_direction": thesis.direction,
            "historical_assessment": thesis.metadata.get("historical_assessment"),
        }
        for thesis in construction.theses
    ]


def _composite_primitives(results: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Correction 053-A -- per-thesis composite-primitive observability.

    READ-ONLY serialization of values already produced in memory:
    W9 ThesisConfidence breakdown/contributors, W8 thesis fields, W7
    assessment severity/penalty inputs, W12 scenario confidences,
    probabilities, and the risk/reward numbers actually consumed by W13.
    No recalculation, no new formulas, no numeric transformation beyond
    JSON serialization; the only aggregates added are ``positive_score`` /
    ``penalty_score``: positive_score sums value x weight over the verbatim
    positive-contributor rows (the identical arithmetic W9 applies
    internally), and penalty_score sums the already-computed per-row
    penalties.  Additive-only: returns None when
    no candidate construction resolves so legacy finalize payloads stay
    byte-identical.
    """
    from confidence_engine.contracts import InstitutionalConfidence
    from counter_evidence.contracts import CounterEvidenceAssessment
    from risk_reward_validation.contracts import RiskRewardValidation
    from scenario_generation.contracts import ScenarioGeneration
    from thesis_construction.contracts import ThesisConstruction
    from thesis_update.contracts import ThesisUpdate

    update_data = results.get("thesis_update")
    construction_data = results.get("thesis_construction")
    if update_data is not None and isinstance(update_data, dict) and "error" in update_data:
        update_data = None
    if update_data is None and (
        construction_data is None
        or (isinstance(construction_data, dict) and "error" in construction_data)
    ):
        return None

    if update_data is not None:
        update = ThesisUpdate.from_dict(update_data) if isinstance(update_data, dict) else update_data
        construction: ThesisConstruction = _construction_from_update(
            update, construction_data
        )
    elif isinstance(construction_data, ThesisConstruction):
        construction = construction_data
    else:
        construction = ThesisConstruction.from_dict(construction_data)

    confidence_data = results.get("confidence_engine")
    confidence = (
        InstitutionalConfidence.from_dict(confidence_data)
        if isinstance(confidence_data, dict)
        else confidence_data
    )
    counter_data = results.get("counter_evidence")
    assessment = (
        CounterEvidenceAssessment.from_dict(counter_data)
        if isinstance(counter_data, dict)
        else counter_data
    )
    generation_data = results.get("scenario_generation")
    generation = (
        ScenarioGeneration.from_dict(generation_data)
        if isinstance(generation_data, dict)
        else generation_data
    )
    validation_data = results.get("risk_reward_validation")
    validation = (
        RiskRewardValidation.from_dict(validation_data)
        if isinstance(validation_data, dict)
        else validation_data
    )
    decision_data = results.get("decision_engine")
    selected_id = None
    if decision_data is not None and not (
        isinstance(decision_data, dict) and "error" in decision_data
    ):
        if isinstance(decision_data, dict):
            selected_id = decision_data.get("selected_thesis_id")
        else:
            selected_id = decision_data.selected_thesis_id

    tc_by_id = {tc.thesis_id: tc for tc in confidence.theses_confidence} if confidence else {}
    scenarios_by_thesis = generation.scenarios_by_thesis if generation else {}
    validations_by_thesis: dict[str, list] = {}
    if validation is not None:
        gen_by_sid = (
            {s.scenario_id: s for s in generation.scenarios} if generation else {}
        )
        for v in validation.validations:
            s = gen_by_sid.get(v.scenario_id)
            if s is not None:
                validations_by_thesis.setdefault(s.thesis_id, []).append(v)

    entries: list[dict[str, Any]] = []
    for thesis in construction.theses:
        tc = tc_by_id.get(thesis.thesis_id)
        breakdown = dict(tc.confidence_breakdown) if tc is not None else {}
        positive_rows = [dict(c) for c in (tc.positive_contributors if tc else ())]
        negative_rows = [dict(c) for c in (tc.negative_contributors if tc else ())]
        penalty_rows = [dict(c) for c in (tc.confidence_penalties if tc else ())]

        scen_rows = []
        for s in scenarios_by_thesis.get(thesis.thesis_id, ()):
            ci = dict(s.confidence_inputs)
            scen_rows.append(
                {
                    "scenario_type": s.scenario_type,
                    "scenario_probability": s.probability,
                    "expected_direction": s.expected_direction,
                    "time_horizon_days": s.time_horizon_days,
                    "regime_path": tuple(s.regime_path),
                    "scenario_confidence": ci.get("scenario_confidence"),
                    "scenario_confidence_source": ci.get("scenario_confidence_source"),
                    "scenario_confidence_type": ci.get("scenario_confidence_type"),
                    "remaining_uncertainty": ci.get("remaining_uncertainty"),
                    "reliability_category": ci.get("reliability_category"),
                }
            )

        rr_rows = []
        for v in validations_by_thesis.get(thesis.thesis_id, ()):
            rr_rows.append(
                {
                    "validation_status": v.validation_status,
                    "risk_reward_ratio": v.risk_reward_ratio,
                    "expected_reward": v.expected_reward,
                    "expected_risk": v.expected_risk,
                    "maximum_downside": v.maximum_downside,
                    "expected_upside": v.expected_upside,
                    "tail_risk": v.tail_risk,
                    "liquidity_risk": v.liquidity_risk,
                    "regime_risk": v.regime_risk,
                    "volatility_impact": v.volatility_impact,
                    "metadata_probability": v.metadata.get("probability"),
                    "metadata_scenario_label": v.metadata.get("scenario_label"),
                }
            )

        w9_provenance = (
            tc.provenance_chain[-1].created_by if tc and tc.provenance_chain else None
        )
        entries.append(
            {
                "thesis_id": thesis.thesis_id,
                "thesis_direction": thesis.direction,
                "is_selected_in_w13": thesis.thesis_id == selected_id,
                "institutional_support": thesis.institutional_support,
                "final_confidence": tc.final_confidence if tc is not None else None,
                "remaining_uncertainty": (
                    tc.remaining_uncertainty if tc is not None else None
                ),
                "reliability_category": (
                    tc.reliability_category if tc is not None else None
                ),
                "evidence_quality": breakdown.get("evidence_quality"),
                "evidence_consensus": breakdown.get("evidence_consensus"),
                "regime_alignment": breakdown.get("regime_alignment"),
                "source_diversity": breakdown.get("source_diversity"),
                "knowledge_record_quality": breakdown.get("knowledge_record_quality"),
                "counter_evidence_penalty": breakdown.get("counter_evidence"),
                "missing_evidence_penalty": breakdown.get("missing_evidence"),
                "internal_consistency_penalty": breakdown.get("internal_consistency"),
                "positive_score": round(
                    sum(
                        float(r.get("value", 0.0)) * float(r.get("weight", 0.0))
                        for r in positive_rows
                    ),
                    4,
                ),
                "penalty_score": round(
                    sum(float(r.get("penalty", 0.0)) for r in penalty_rows), 4
                ),
                "positive_contributors": positive_rows,
                "negative_contributors": negative_rows,
                "confidence_penalties": penalty_rows,
                "supporting_set_ids": tuple(thesis.supporting_set_ids),
                "supporting_set_count": len(thesis.supporting_set_ids),
                "counter_evidence_ids": tuple(thesis.counter_evidence_ids),
                "contradicting_set_ids": (
                    tuple(assessment.contradicting_set_ids) if assessment else ()
                ),
                "conflict_severity": (
                    assessment.conflict_severity if assessment else None
                ),
                "confidence_penalty": (
                    assessment.confidence_penalty if assessment else None
                ),
                "regime_conflict_flag": (
                    assessment.regime_conflict if assessment else None
                ),
                "bias_flags": (
                    tuple(assessment.bias_flags) if assessment else ()
                ),
                "scenarios": scen_rows,
                "risk_reward_consumed_by_w13": rr_rows,
                "primitive_sources": {
                    "final_confidence": w9_provenance or "W9 ConfidenceEngine",
                    "confidence_breakdown": "W9 ConfidenceComputer via W9 ConfidenceEngine",
                    "institutional_support": "W8 ThesisBuilder._compute_institutional_support",
                    "supporting_set_ids": "W8 ThesisBuilder (W6 evidence sets)",
                    "counter_evidence_and_severity": "W7 CounterEvidenceAssessor",
                    "scenario_fields": "W12 ScenarioGenerator (Correction 052-A labels)",
                    "risk_reward_fields": "W12 RiskRewardValidator (consumed by W13 DecisionEngine)",
                },
            }
        )
    return entries


def _canonical_fact_registry_summary(results: dict[str, Any]) -> dict[str, Any]:
    """Final Hardening (Group F, D-07/D-09): run-scoped CanonicalFactRegistry.

    Every run shares ONE registry instance: the technical desk facts and the
    reference-price close fact are registered into it (with lineage edges),
    so cross-desk same-primitive identity becomes observable live -- e.g.
    the technical desk's close and the 057 reference price converging on the
    same primitive.  Observability only: nothing here scores, votes, or
    alters a decision input.
    """
    try:
        from knowledge.facts.contracts import CanonicalFact
        from knowledge.facts.builders import reference_price_fact
        from knowledge.facts.registry import CanonicalFactRegistry
        from knowledge.integrity.lineage import LineageRegistry

        registry = CanonicalFactRegistry()
        lineage = LineageRegistry()
        sources: list[str] = []

        technical = results.get("technical_research")
        technical_as_of = None
        if isinstance(technical, dict):
            references = technical.get("fact_references") or {}
            technical_as_of = technical.get("as_of")
            for raw_fact in references.get("facts", []):
                try:
                    registry.register(
                        CanonicalFact.from_dict(raw_fact),
                        lineage_registry=lineage,
                    )
                except (KeyError, ValueError):
                    continue
            if references.get("facts"):
                sources.append("technical_research")

        recommendation = results.get("trade_recommendation")
        metadata: dict[str, Any] = {}
        if hasattr(recommendation, "metadata"):
            metadata = dict(recommendation.metadata or {})
        elif isinstance(recommendation, dict):
            metadata = dict(recommendation.get("metadata") or {})
        provenance = metadata.get("reference_price_provenance") or {}
        if (
            isinstance(provenance, dict)
            and provenance.get("status") == "resolved_from_gold_data"
        ):
            fact = reference_price_fact(provenance, as_of=technical_as_of)
            registry.register(fact, lineage_registry=lineage)
            sources.append("reference_price")

        convergence = []
        for fact_id in registry.fact_ids():
            producers = sorted(registry.producers(fact_id))
            if len(producers) > 1:
                values = sorted(
                    {str(observation.value) for observation in registry.get(fact_id)}
                )
                convergence.append(
                    {
                        "fact_id": fact_id,
                        "producers": producers,
                        "values": values,
                        "agreement": len(values) == 1,
                    }
                )

        return {
            "status": "ok",
            "sources": sorted(set(sources)),
            "summary": registry.summary(),
            "cross_producer_convergence": convergence,
            "lineage_edges": len(lineage.all_records()),
        }
    except Exception as exc:
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}"}


def _finalize(params: dict[str, Any], results: dict[str, Any]) -> Any:
    legacy_pipeline = results.get("build_legacy_pipeline", {})
    legacy_decision = legacy_pipeline.get("decision")
    institutional_decision = results.get("decision_engine")
    if isinstance(institutional_decision, dict) and "error" in institutional_decision:
        institutional_decision = None
    payload = {
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
    assessments = _thesis_historical_assessments(results)
    if assessments:
        payload["thesis_historical_assessments"] = assessments
    # Correction 053-A: additive per-thesis composite-primitive observability.
    # Attached only when a candidate construction resolves, keeping legacy
    # finalize payloads byte-identical; values are verbatim in-memory reads.
    primitives = _composite_primitives(results)
    if primitives:
        payload["composite_primitives"] = primitives
    # Sprint 058: additive news-intelligence observability.  Attached only
    # when the ingest_news stage produced output so legacy payloads stay
    # byte-identical; verbatim stage payload (status/reason/items/fomc).
    news_payload = results.get("ingest_news")
    if isinstance(news_payload, dict) and "status" in news_payload:
        payload["news_intelligence"] = news_payload
    # Final Hardening (Group D, D-06): the executable trade recommendation
    # (entry/stop/target, market-anchored risk summary) is part of the
    # finalize contract.  Serialized when the stage produced a valid
    # recommendation; an explicit error payload is surfaced, never dropped.
    recommendation_payload = results.get("trade_recommendation")
    if recommendation_payload is not None:
        if hasattr(recommendation_payload, "to_dict"):
            payload["trade_recommendation"] = recommendation_payload.to_dict()
        elif isinstance(recommendation_payload, dict):
            payload["trade_recommendation"] = recommendation_payload
    # Final Hardening (Group F): run-scoped canonical-fact aggregation.
    facts_summary = _canonical_fact_registry_summary(results)
    if facts_summary.get("status") == "ok":
        payload["canonical_fact_registry"] = facts_summary
    return payload


def _technical_research(params: dict[str, Any], results: dict[str, Any]) -> Any:
    """Independent Technical Research Desk artifact (observability only).

    Computes a deterministic TechnicalAssessment from the run's gold OHLCV
    data and persists it as ``output_dir/technical_assessment.json``.  The
    stage is a deliberate leaf in the pipeline DAG: nothing downstream
    consumes its output, so it cannot influence W13/W14 decisions.
    """
    import datetime
    import json
    from pathlib import Path

    gold_path = params.get("gold_path")
    if not gold_path:
        return {"error": "no gold_path available"}

    try:
        import pandas as pd

        from technical.contracts import SUPPORTED_TIMEFRAMES
        from technical.desk import TechnicalResearchDesk

        timeframe = params.get("technical_timeframe", "D1")
        if timeframe not in SUPPORTED_TIMEFRAMES:
            return {"error": f"unsupported technical timeframe: {timeframe}"}

        frame = pd.read_csv(gold_path)
        as_of = params.get("technical_as_of") or datetime.date.today().isoformat()
        assessment = TechnicalResearchDesk().assess(
            frame,
            as_of=str(as_of),
            timeframe=timeframe,
            asset=params.get("asset", "XAU/USD"),
        )
        payload = assessment.to_dict()

        # Sprint 061: additive canonical-fact references (observability only).
        # The technical desk remains a DAG leaf; nothing downstream consumes
        # these keys and no decision path can observe them.
        try:
            from knowledge.facts.builders import technical_fact_references

            references = technical_fact_references(payload)
            payload["fact_references"] = {
                "status": references.get("status", "ok"),
                "facts": references.get("facts", []),
            }
            payload["desk_provenance"] = references.get("desk_provenance")
        except Exception as exc:
            payload["fact_references"] = {
                "status": "error",
                "reason": f"{type(exc).__name__}: {exc}",
            }

        output_dir = params.get("output_dir")
        if output_dir:
            artifact = Path(output_dir) / "technical_assessment.json"
            artifact.write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        return payload
    except Exception as exc:
        return {"error": f"technical research failed: {exc}"}
