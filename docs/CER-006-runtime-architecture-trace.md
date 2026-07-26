PS C:\AurumAI\AurumAI> & "C:\Users\THE BLU WALF\.local\bin\claude.exe"
╭─── Claude Code v2.1.218 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│                                  │ Tips for getting started                                                                                                          │
│           Welcome back!          │ Run /init to create a CLAUDE.md file with instructions for Claude                                                                 │
│                                  │ ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────── │
│              ▐▛███▜▌             │ What's new                                                                                                                        │
│             ▝▜█████▛▘            │ Changed `/code-review` to run as a background subagent, so review work no longer fills your conversation and keeps stacked slash… │
│               ▘▘ ▝▝              │ Added screen-reader announcements of deleted text for word and line deletions (`Option+Delete`, `Ctrl+W`, `Cmd+Backspace`, `Ctrl… │
│                                  │ Fixed Windows paths with `\u`-prefixed segments (like `C:\Users\unicorn`) being corrupted into CJK characters in tool inputs, wh… │
│   Opus 4.6 · API Usage Billing   │ /release-notes for more                                                                                                           │
│        C:\AurumAI\AurumAI        │                                                                                                                                   │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯


> You are performing an institutional architecture trace of the AurumAI project.                                                                                                                                                                                                                                                                  Do NOT review code quality.                                                                                                                                                                                                                                                                                                                     Do NOT suggest refactoring.                                                                                                                                                                                                                                                                                                                     Your only objective is to discover hidden architectural relationships.                                                                                                                                                                                                                                                                          Starting from the application entrypoints, reconstruct the COMPLETE runtime execution graph.                                                                                                                                                                                                                                                    For every major subsystem determine:                                                                                                                                                                                                                                                                                                            - who creates it                                                                                                                                                        - who owns it                                                                                                                                                           - who invokes it                                                                                                                                                        - who consumes its outputs                                                                                                                                              - whether it is synchronous or asynchronous                                                                                                                             - whether it is optional or mandatory                                                                                                                                   - whether it is actually reached in production                                                                                                                                                                                                                                                                                                  Produce:                                                                                                                                                                                                                                                                                                                                        1. Runtime execution graph                                                                                                                                              2. Dependency graph                                                                                                                                                     3. Ownership graph                                                                                                                                                      4. Dead execution paths                                                                                                                                                 5. Unreachable capabilities                                                                                                                                             6. Duplicate orchestration paths                                                                                                                                        7. Components that exist but are never consumed                                                                                                                         8. Components that consume data that is never produced                                                                                                                                                                                                                                                                                          Do NOT redesign anything.                                                                                                                                                                                                                                                                                                                       Only trace reality.                                                                                                                                                                                                                                                                                                                             Follow every call until the final InstitutionalDecision is produced.                                                                                                                                                                                                                                                                            If anything cannot be determined, explain exactly what additional files are required.                                                                                 
  Thought for 18s (ctrl+o to expand)

● I'll trace the complete runtime architecture of AurumAI. Let me start by mapping the project structure and identifying all entrypoints.

  Thought for 15s, searched for 3 patterns, listed 2 directories (ctrl+o to expand)

● This is a 256-file codebase across 10+ subsystems. I'll launch a comprehensive multi-agent trace to read every subsystem in parallel and reconstruct the full runtime
  graph.

● Workflow(Trace the complete runtime execution graph of the AurumAI project)
  ⎿  /workflows to view dynamic workflow runs

  Thought for 24s (ctrl+o to expand)

● The architecture trace workflow is running with 20 parallel agents across 4 phases:

  1. Read Entrypoints (3 agents) — scripts, orchestration layer, knowledge core
  2. Read Subsystems (15 agents) — every subsystem module in parallel
  3. Trace Cross-Cutting (5 agents) — InstitutionalDecision flow, Brain ownership, public API surface, dead code, orchestrator paths
  4. Synthesize (1 agent) — combines all findings into the 8-deliverable report

  You can watch live progress with /workflows. I'll deliver the full report once the trace completes.

✻ Waiting for 1 dynamic workflow to finish

● Auto mode lets Claude handle permission prompts automatically — Claude checks each tool call for risky actions and prompt injection before executing. Actions
  Claude identifies as safe are executed, while actions Claude identifies as risky are blocked and Claude may try a different approach. Ideal for long-running
  tasks. Sessions are slightly more expensive. Claude can make mistakes that allow harmful commands to run, it's recommended to only use in isolated
  environments. Shift+Tab to change mode.

● Dynamic workflow "Trace the complete runtime execution graph of the AurumAI project" completed · 1h 30m 30s

  Thought for 12s, read 1 file (ctrl+o to expand)

● The workflow completed (22/24 agents succeeded). Let me read the full report and recover the two failed subsystem traces.

  Thought for 16s, read 1 file (ctrl+o to expand)

● Good — the full report is captured. Two agents failed (knowledge-features, dead-code-trace). Let me fill those gaps directly.

● Agent(Read knowledge/features subsystem)
  ⎿  Initializing…
  ⎿  Error: claude-opus-4-6 is temporarily unavailable, so auto mode cannot determine the safety of Agent right now. Wait briefly and then try this action again. If it      keeps failing, continue with other tasks that don't require this action and come back to it later. Note: reading files, searching code, and other read-only
     operations do not require the classifier and can still be used.

  Searched for 1 pattern, read 8 files (ctrl+o to expand)

● Now let me check who actually calls the feature extractors and verify the events → features integration:

  Thought for 19s, searched for 3 patterns (ctrl+o to expand)

● Now let me verify the terminal output type and check for the actual final decision class:

  Searched for 2 patterns, read 1 file (ctrl+o to expand)

● Good — the terminal output is InstitutionalAssessment, not InstitutionalDecision. The Decision class (from knowledge.decision.decision) is an intermediate artifact
  embedded inside the pipeline. Now I have all the pieces. Let me present the complete architectural trace.

  ---
  AurumAI — Complete Institutional Architecture Trace

  1. RUNTIME EXECUTION GRAPH

  Primary Production Path

  HistoricalReplayEngine.run_all()                    [src/simulation/historical_replay.py]
    → _iter_event_types()                             returns ["CPI","NFP","GDP","INTEREST_RATE","PMI","PPI","FOMC"]
    → _replay_event(event_type, csv_path)             per event type
       → InstitutionalOrchestrator.with_default_pipeline()  [src/orchestration/orchestrator.py]
          → registers 11 PipelineJob objects
       → orchestrator.run_all(trigger, **params)
          → _topological_levels(self._jobs)           [src/orchestration/dag.py]
          → ThreadPoolExecutor per level
          → _execute_job(job_id, pipeline_id, force)
             → CheckpointManager.exists()            [src/orchestration/checkpoints.py]
             → CacheManager.get()                    [src/orchestration/cache.py]
             → job.fn() → _bind(stage_fn)(params, results)

  Stage Execution DAG (topological order):

  LEVEL 0 (parallel, no dependencies):
    ┌─ _ingest_event(params, results)                 [src/orchestration/stages.py]
    │    → EventRegistry.get_or_raise(event_type)     [src/knowledge/events/registry.py]
    │    → event_cls().load_raw(data_path)            [src/knowledge/events/<type>.py]
    │    → event.load_and_extract(data_path)
    │         → FeatureExtractionEngine().process(raw, <TypeExtractor>())
    │              → <TypeExtractor>.extract(raw) → FeatureSet
    │
    └─ _ingest_news(params, results)
         → NewsCollector(topics).collect()            [src/news/news_collector.py]
         → FOMCCalendarConnector().upcoming_meetings() [src/connectors/fomc_calendar.py]

  LEVEL 1 (parallel, depends on LEVEL 0):
    ┌─ _build_legacy_pipeline(params, results)
    │    → PipelineContext(event, paths...)            [src/knowledge/pipeline/context.py]
    │    → InferencePipeline().run(ctx, lineage)      [src/knowledge/pipeline/pipeline.py]
    │       → _stage_build_lessons
    │          → LessonBuilder(config, event).build_and_save()
    │          → YieldContextEnricher.enrich_csv()     (conditional: ctx.yield_data_path)
    │       → _stage_build_knowledge
    │          → LessonSummaryAggregator(config).build_and_save()
    │       → _stage_compare_context                   (conditional: ctx.context_comparison_baseline_path)
    │          → ContextComparisonReport(config).build_and_save()
    │       → _stage_build_graph
    │          → GraphBuilder().build(records) → KnowledgeGraph
    │       → _stage_query_evidence
    │          → EvidenceQuery(graph).matching(...) → EvidenceCollection
    │       → _stage_reason
    │          → ReasoningEngine().reason(evidence, context) → ReasoningChain
    │             → EvidenceWeighter().weigh(evidence) → WeightedAggregate
    │       → _stage_decide
    │          → DecisionEngine().decide(chain, context) → Decision
    │
    └─ _forecast(params, results)
         → MacroForecaster(season_length, freq).forecast(df, h)
            → StatsForecast([AutoARIMA, AutoETS, AutoTheta]).forecast()

  LEVEL 2 (parallel, depends on LEVEL 1):
    ┌─ _forecast_confidence → ForecastConfidenceComputer().compute()
    ├─ _forecast_validation → ForecastValidator().validate()
    ├─ _build_context       → ForecastContextBuilder().build()
    └─ _risk_measures       → compute_var(), compute_cvar(), TailRiskDetector().detect()

  LEVEL 3 (depends on LEVEL 2):
    └─ _position_sizing → VolatilityTargetSizer().compute() + RiskParitySizer().compute()

  LEVEL 4 (depends on LEVEL 3):
    └─ _risk_gate → RegimeRiskOverlay, UncertaintyBudget, DecisionGate().evaluate()

  LEVEL 5 (terminal, depends on all):
    └─ _finalize → pure dict aggregation → InstitutionalAssessment

  Terminal output: InstitutionalAssessment → HistoricalReplayEngine._assessment_to_result() → EventRunResult

  ▎ Note: There is NO class called InstitutionalDecision anywhere in the codebase. The terminal output is InstitutionalAssessment (src/orchestration/models.py:45). The
  ▎ Decision class (src/knowledge/decision/decision.py:29) is an intermediate artifact inside the InferencePipeline.

  Experiment Script Entrypoints

  run_experiment_001.py (NO __main__ guard — runs on import)
    → ExperimentRunner(config).run()
       → ChronologicalOOSEngine.run()
          → _build_training_knowledge() → InstitutionalOrchestrator.with_default_pipeline().run_all()
          → _run_evaluation()           → _EvalReplayEngine.run() → InstitutionalOrchestrator...
       → compute_oos_summary(results)
    → ExperimentRegistry().register(result)
    → ExperimentReportBuilder.build(result)

  run_experiment_002.py (under __main__)
    → EvidenceIsolationExperiment().run()
       → InferencePipeline().run(ctx, lineage) [DIRECT — bypasses orchestrator]
       → EvidenceQuery → ReasoningEngine → DecisionEngine

  run_experiment_003.py (under __main__)
    → InferencePipeline().run(ctx) [DIRECT — two variant runs]

  gate6_validation.py (NO __main__ guard)
    → InferencePipeline().run(ctx, lineage) × 3 [DIRECT]
    → LineageRegistry().trace() + SHA-256 determinism checks

  dxy_capability.py (NO __main__ guard)
    → InferencePipeline().run(ctx) × 4 variants [DIRECT]
    → DXYContextEnricher → LessonSummaryAggregator → ContextComparisonReport

  Data Download Paths (standalone, no production integration)

  download_dxy.py → yfinance.download("DX-Y.NYB") → data/context/dxy/dxy.csv
  download_fomc_calendar.py → requests.get(URL) → data/calendar/fomc_meetings.csv

  ---
  2. DEPENDENCY GRAPH

  Forward Dependencies (A → B means A depends on B)

  src/orchestration/
    → knowledge.events.registry          (stages._ingest_event)
    → knowledge.pipeline                 (stages._build_legacy_pipeline)
    → knowledge.integrity.lineage        (stages._build_legacy_pipeline)
    → knowledge.builders.lesson_builder  (stages._build_legacy_pipeline)
    → news.news_collector                (stages._ingest_news)
    → connectors.fomc_calendar           (stages._ingest_news)
    → forecasting.macro_forecaster       (stages._forecast)
    → forecasting.confidence             (stages._forecast_confidence)
    → forecasting.context                (stages._forecast_confidence, _build_context)
    → forecasting.knowledge              (stages._forecast_confidence)
    → forecasting.provenance             (stages._forecast_confidence)
    → forecasting.registry               (stages._forecast_confidence)
    → forecasting.validation             (stages._forecast_validation)
    → forecasting.risk_measures          (stages._risk_measures)
    → forecasting.position_sizing        (stages._position_sizing)
    → forecasting.risk_budgeting         (stages._position_sizing)
    → forecasting.decision_gate          (stages._risk_gate)
    → knowledge._compat                  (models.InstitutionalAssessment)

  src/simulation/
    → orchestration.InstitutionalOrchestrator  (historical_replay)
    → knowledge._compat                       (experiment_registry)

  src/knowledge/pipeline/
    → knowledge.builders.lesson_builder       (_stage_build_lessons)
    → knowledge.context.yields                (_stage_build_lessons, conditional)
    → knowledge.context.comparison            (_stage_compare_context, conditional)
    → knowledge.lesson_summary                (_stage_build_knowledge)
    → knowledge.graph.builder                 (_stage_build_graph)
    → knowledge.evidence.query                (_stage_query_evidence)
    → knowledge.reasoning.engine              (_stage_reason)
    → knowledge.evidence.weighting            (_stage_reason, indirect via ReasoningEngine)
    → knowledge.decision.engine               (_stage_decide)
    → knowledge.integrity.lineage             (multiple stages)
    → knowledge.events.base                   (PipelineContext.event)

  src/knowledge/reasoning/
    → knowledge.evidence.collection
    → knowledge.evidence.evidence
    → knowledge.evidence.weighting
    → knowledge._compat
    → knowledge.integrity.provenance
    → knowledge.temporal.indexer             (retrieval — DEAD PATH)
    → knowledge.evidence.query               (retrieval — DEAD PATH)

  src/knowledge/decision/
    → knowledge.reasoning.chain
    → knowledge.reasoning.step
    → knowledge._compat
    → knowledge.integrity.provenance

  src/knowledge/evidence/
    → knowledge.graph.graph
    → knowledge._compat
    → knowledge.integrity.provenance

  src/knowledge/graph/
    → networkx
    → knowledge._compat
    → knowledge.integrity.knowledge_record

  src/knowledge/events/ (concrete event types)
    → knowledge.features.engine              (all 7 event constructors)
    → knowledge.features.extractors.*        (all 7 event constructors)
    → knowledge.events.release_calendar      (CPI, base.MacroEvent)
    → connectors.fomc_calendar               (FOMCEvent ClassVar)

  src/forecasting/
    → knowledge._compat
    → statsforecast                          (MacroForecaster, lazy)
    → transformers                           (FOMCSentimentAnalyzer, TYPE_CHECKING)

  src/execution/  → SELF-CONTAINED (no external src/ deps)
  src/technical/  → knowledge.features.extractor (inherits ABC only)
  src/news/       → SELF-CONTAINED
  src/nlp/        → transformers
  src/connectors/ → SELF-CONTAINED

  Cross-module backbone: knowledge._compat

  _compat provides: FrozenDict, freeze_dict, atomic_write_json
  Used by: 20+ modules (reasoning, decision, evidence, graph, forecasting, orchestration, simulation)

  Reverse Dependencies (what depends on each subsystem)

  knowledge._compat          ← 20+ modules
  knowledge.integrity        ← reasoning, decision, evidence, graph, evolution, pipeline
  knowledge.evidence         ← reasoning, pipeline, orchestration(DEAD)
  knowledge.reasoning        ← decision, pipeline, orchestration(DEAD)
  knowledge.decision         ← pipeline, execution(constants only)
  knowledge.graph            ← evidence.query, pipeline
  knowledge.events           ← pipeline, orchestration(stages), builders, brain
  knowledge.features         ← events (all 7 concrete types own extractors)
  forecasting.*              ← orchestration(stages)
  orchestration              ← simulation
  simulation                 ← scripts
  execution                  ← NOTHING
  technical                  ← NOTHING
  knowledge.orchestration    ← NOTHING
  knowledge.learning         ← evolution only (itself DEAD)
  knowledge.evolution        ← NOTHING
  knowledge.expansion        ← NOTHING

  ---
  3. OWNERSHIP GRAPH

  ┌───────────────────┬─────────────────────────────┬─────────────────────────────┬─────────────────────────┬─────────────────────────────┬─────────┬──────────────┐
  │     Component     │         Created By          │          Owned By           │       Invoked By        │     Output Consumed By      │ Sync/As │ Mandatory/Op │
  │                   │                             │                             │                         │                             │   ync   │    tional    │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │                   │                             │                             │                         │                             │ Sync    │              │
  │ InstitutionalOrch │ with_default_pipeline()     │ HistoricalReplayEngine._rep │ HistoricalReplayEngine  │ InstitutionalAssessment →   │ (Thread │ Mandatory    │
  │ estrator          │ classmethod                 │ lay_event (local)           │                         │ _assessment_to_result()     │ Pool    │              │
  │                   │                             │                             │                         │                             │ within) │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ InferencePipeline │ stages._build_legacy_pipeli │ Nobody (stateless,          │ Orchestrator stage OR   │ PipelineResult →            │ Sync    │ Mandatory    │
  │                   │ ne or experiment scripts    │ transient)                  │ direct script call      │ orchestrator results dict   │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ MacroForecaster   │ stages._forecast            │ Nobody (transient)          │ Orchestrator stage      │ dict[str, ForecastResult] → │ Sync    │ Mandatory    │
  │                   │                             │                             │                         │  LEVEL 2 stages             │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ FeatureExtraction │ Each event class            │ Event instance              │ event.load_and_extract( │ FeatureSet → pd.DataFrame   │ Sync    │ Mandatory    │
  │ Engine            │ constructor                 │ (self._extraction_engine)   │ )                       │                             │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ DecisionEngine    │ InferencePipeline._stage_de │ Nobody (stateless)          │ Pipeline, experiments   │ Decision → PipelineResult   │ Sync    │ Mandatory    │
  │                   │ cide                        │                             │                         │                             │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ ReasoningEngine   │ InferencePipeline._stage_re │ Nobody (stateless)          │ Pipeline, experiments   │ ReasoningChain →            │ Sync    │ Mandatory    │
  │                   │ ason                        │                             │                         │ DecisionEngine.decide()     │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ EvidenceQuery     │ InferencePipeline._stage_qu │ Nobody (transient)          │ Pipeline, experiments   │ EvidenceCollection →        │ Sync    │ Mandatory    │
  │                   │ ery_evidence                │                             │                         │ ReasoningEngine.reason()    │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ GraphBuilder      │ InferencePipeline._stage_bu │ Nobody (transient)          │ Pipeline                │ KnowledgeGraph →            │ Sync    │ Mandatory    │
  │                   │ ild_graph                   │                             │                         │ EvidenceQuery constructor   │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ LessonBuilder     │ InferencePipeline._stage_bu │ Nobody (transient)          │ Pipeline                │ DataFrame → CSV →           │ Sync    │ Mandatory    │
  │                   │ ild_lessons                 │                             │                         │ LessonSummaryAggregator     │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │                   │ InstitutionalOrchestrator._ │                             │                         │ Cache hit/miss → skip or    │         │ Optional     │
  │ CacheManager      │ _init__                     │ Orchestrator instance       │ _execute_job            │ run stage                   │ Sync    │ (graceful on │
  │                   │                             │                             │                         │                             │         │  miss)       │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ CheckpointManager │ InstitutionalOrchestrator._ │ Orchestrator instance       │ _execute_job            │ Disk checkpoint → resume    │ Sync    │ Optional     │
  │                   │ _init__                     │                             │                         │                             │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ DecisionGate      │ stages._risk_gate           │ Nobody (transient)          │ Orchestrator stage      │ GateResult → _finalize      │ Sync    │ Mandatory    │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ EvidenceWeighter  │ ReasoningEngine._weigh      │ Nobody (transient)          │ ReasoningEngine         │ WeightedAggregate →         │ Sync    │ Mandatory    │
  │                   │                             │                             │                         │ ReasoningChain              │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ HistoricalReplayE │ run_simulation() or         │ Local var                   │ Scripts                 │ SimulationReport /          │ Sync    │ Mandatory    │
  │ ngine             │ ExperimentRunner            │                             │                         │ EventRunResult              │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ ChronologicalOOSE │ ExperimentRunner.run()      │ ExperimentRunner (local)    │ ExperimentRunner        │ ChronologicalOOSResult      │ Sync    │ Mandatory    │
  │ ngine             │                             │                             │                         │                             │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ ExperimentRegistr │ run_experiment_001.py       │ Script local                │ Script                  │ Persists to data/experiment │ Sync    │ Optional     │
  │ y                 │                             │                             │                         │ s/registry/registry.json    │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ EconomicBrain     │ brain.py __main__ or tests  │ Test/demo local             │ Tests only              │ Knowledge lookup dict       │ Sync    │ DEAD         │
  │                   │ only                        │                             │                         │                             │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ OrchestrationEngi │ NEVER CREATED               │ N/A                         │ Nothing                 │ Would return                │ —       │ DEAD         │
  │ ne                │                             │                             │                         │ OrchestrationReport         │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ ExecutionEngine   │ NEVER CREATED               │ N/A                         │ Nothing                 │ Would return                │ —       │ DEAD         │
  │                   │                             │                             │                         │ ExecutionResult             │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ VirtualPortfolio  │ NEVER CREATED               │ N/A                         │ ExecutionEngine.evaluat │ Would be mutated in-place   │ —       │ DEAD         │
  │                   │                             │                             │ e() expects it          │                             │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ FeedbackApplicato │ NEVER CREATED               │ N/A                         │ Nothing                 │ Would return                │ —       │ DEAD         │
  │ r                 │                             │                             │                         │ list[KnowledgeRecord]       │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ LearningEngine    │ FeedbackApplicator.__init__ │ FeedbackApplicator._engine  │ FeedbackApplicator._bui │ LearningRecord,             │ —       │ DEAD         │
  │                   │  (dead)                     │                             │ ld_feedback             │ KnowledgeFeedback           │         │              │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ MacroRegimeDetect │ NEVER INJECTED              │ Would be ForecastContextBui │ Would be                │ Returns regime labels       │ —       │ Optional,    │
  │ or                │                             │ lder._regime_detector       │ _resolve_regime         │                             │         │ always None  │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ FOMCSentimentAnal │ NEVER INJECTED              │ Would be ForecastContextBui │ Would be                │ Returns sentiment           │ —       │ Optional,    │
  │ yzer              │                             │ lder._fomc_analyzer         │ _resolve_fomc_sentiment │                             │         │ always None  │
  ├───────────────────┼─────────────────────────────┼─────────────────────────────┼─────────────────────────┼─────────────────────────────┼─────────┼──────────────┤
  │ NewsSentimentAnal │ NEVER INJECTED              │ Would be ForecastContextBui │ Would be                │ Returns sentiment           │ —       │ Optional,    │
  │ yzer              │                             │ lder._news_analyzer         │ _resolve_news_sentiment │                             │         │ always None  │
  └───────────────────┴─────────────────────────────┴─────────────────────────────┴─────────────────────────┴─────────────────────────────┴─────────┴──────────────┘

  ---
  4. DEAD EXECUTION PATHS

  ┌──────┬───────────────────────────────────────────────────┬──────────────────────────────────────────────────┬──────────────────────────────────────────────────┐
  │  #   │                       Path                        │                     Location                     │                     Why Dead                     │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.1  │ EconomicBrain.analyze() full context lookup       │ src/knowledge/brain.py                           │ Only reachable from brain.py __main__ and tests. │
  │      │                                                   │                                                  │  No production code imports EconomicBrain.       │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.2  │ ExecutionEngine.evaluate() entire path            │ src/execution/execution_engine.py                │ Never instantiated. execution package has zero   │
  │      │                                                   │                                                  │ production importers.                            │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.3  │ VirtualPortfolio                                  │ src/execution/portfolio.py                       │ No production consumer.                          │
  │      │ buy/sell/short/cover/mark_to_market               │                                                  │                                                  │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.4  │ OrchestrationEngine.analyze() and sub-methods     │ src/knowledge/orchestration/engine.py            │ Never instantiated in any script, pipeline, or   │
  │      │                                                   │                                                  │ test runner.                                     │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.5  │ EvidenceAggregator.merge()                        │ src/knowledge/orchestration/aggregator.py        │ Only reachable through dead                      │
  │      │                                                   │                                                  │ OrchestrationEngine.analyze().                   │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.6  │ LayerPolicy evaluation                            │ src/knowledge/orchestration/policy.py            │ Only called inside dead                          │
  │      │                                                   │                                                  │ OrchestrationEngine.analyze().                   │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.7  │ HistoricalSituationRetriever.retrieve()           │ src/knowledge/reasoning/retrieval.py             │ Only reachable from dead OrchestrationEngine.    │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.8  │ CrossEventAnalyzer.analyze()                      │ src/knowledge/reasoning/cross_event.py           │ Only called from dead                            │
  │      │                                                   │                                                  │ OrchestrationEngine.analyze().                   │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.9  │ FeedbackApplicator.apply() entire evolution loop  │ src/knowledge/evolution/applicator.py            │ Never instantiated from any entrypoint.          │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.10 │ KnowledgeCalibrator.calibrate()                   │ src/knowledge/evolution/knowledge_calibrator.py  │ Only reachable through dead FeedbackApplicator.  │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.11 │ LearningEngine.evaluate(), create_session(),      │ src/knowledge/learning/engine.py                 │ Only reachable through dead FeedbackApplicator.  │
  │      │ generate_feedback()                               │                                                  │                                                  │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.12 │ EventScaffolder.scaffold_all()                    │ src/knowledge/expansion/scaffolder.py            │ Never called from any entrypoint.                │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.13 │ ExpansionLifecycle.audit(), print_lifecycle()     │ src/knowledge/expansion/lifecycle.py             │ Never called from any entrypoint.                │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.14 │ EventValidator.validate_class()                   │ src/knowledge/expansion/validator.py             │ Only called from dead                            │
  │      │                                                   │                                                  │ ExpansionLifecycle.audit().                      │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.15 │ EvidenceRanker all static methods                 │ src/knowledge/evidence/ranker.py                 │ Pipeline uses EvidenceQuery.matching() directly; │
  │      │                                                   │                                                  │  ranker is never called.                         │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.16 │ EvidenceRepository.save()/load()                  │ src/knowledge/evidence/repository.py             │ Evidence consumed in-memory, never persisted.    │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.17 │ ReasoningRepository.save()/load()                 │ src/knowledge/reasoning/repository.py            │ Never called from pipeline or scripts.           │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.18 │ DecisionRepository.save()/load()                  │ src/knowledge/decision/repository.py             │ Never called from pipeline or scripts.           │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.19 │ GraphRepository.save()/load()                     │ src/knowledge/graph/repository.py                │ Never called from pipeline or scripts.           │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.20 │ PipelineRepository.save()                         │ src/knowledge/pipeline/repository.py             │ Never called from InferencePipeline.run().       │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.21 │ PipelineValidator.validate()/is_valid()           │ src/knowledge/pipeline/validator.py              │ Never called from pipeline or entrypoints.       │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.22 │ DecisionValidator.validate()/is_valid()           │ src/knowledge/decision/validator.py              │ Never called from DecisionEngine.                │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.23 │ TechnicalIndicatorExtractor.extract()             │ src/technical/indicators.py                      │ Never imported or used by any pipeline stage.    │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.24 │ MacroRegimeDetector.fit() in forecasting flow     │ src/knowledge/regime/macro_regime_detector.py    │ Accepted as optional param, but never injected   │
  │      │                                                   │                                                  │ by stages.                                       │
  ├──────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
  │ 4.25 │ FOMCSentimentAnalyzer/NewsSentimentAnalyzer in    │ src/nlp/fomc_sentiment.py,                       │ Same pattern: optional param, never injected.    │
  │      │ production                                        │ src/nlp/news_sentiment.py                        │                                                  │
  └──────┴───────────────────────────────────────────────────┴──────────────────────────────────────────────────┴──────────────────────────────────────────────────┘

  ---
  5. UNREACHABLE CAPABILITIES

  ┌──────────────────────────────┬───────────────────────────────────────────────────┬────────────────┬─────────────────────────────────────────────────────────────┐
  │          Capability          │                      Package                      │   File Count   │                           Status                            │
  ├──────────────────────────────┼───────────────────────────────────────────────────┼────────────────┼─────────────────────────────────────────────────────────────┤
  │ Virtual Trading/Execution    │ src/execution/                                    │ 5 files, 13    │ Complete portfolio + slippage + commission + engine. Zero   │
  │                              │                                                   │ exports        │ callers.                                                    │
  ├──────────────────────────────┼───────────────────────────────────────────────────┼────────────────┼─────────────────────────────────────────────────────────────┤
  │ Knowledge Orchestration      │ src/knowledge/orchestration/                      │ 5 files, 4     │ Multi-layer evidence aggregation, policy selection,         │
  │                              │                                                   │ exports        │ conflict detection. Zero callers.                           │
  ├──────────────────────────────┼───────────────────────────────────────────────────┼────────────────┼─────────────────────────────────────────────────────────────┤
  │ Learning Loop                │ src/knowledge/learning/                           │ 5 files, 5     │ Decision evaluation, session aggregation, feedback          │
  │                              │                                                   │ exports        │ generation. Zero callers.                                   │
  ├──────────────────────────────┼───────────────────────────────────────────────────┼────────────────┼─────────────────────────────────────────────────────────────┤
  │ Evolution/Calibration        │ src/knowledge/evolution/                          │ 3 files, 2     │ Feedback application, confidence recalibration, versioned   │
  │                              │                                                   │ exports        │ persistence. Zero callers.                                  │
  ├──────────────────────────────┼───────────────────────────────────────────────────┼────────────────┼─────────────────────────────────────────────────────────────┤
  │ Event Expansion Tooling      │ src/knowledge/expansion/                          │ 4 files, 6     │ Event scaffolding, validation, lifecycle audit. Zero        │
  │                              │                                                   │ exports        │ callers.                                                    │
  ├──────────────────────────────┼───────────────────────────────────────────────────┼────────────────┼─────────────────────────────────────────────────────────────┤
  │ Historical Situation         │ src/knowledge/reasoning/retrieval.py              │ 1 file         │ Similarity-based retrieval. Only reachable from dead        │
  │ Retrieval                    │                                                   │                │ OrchestrationEngine.                                        │
  ├──────────────────────────────┼───────────────────────────────────────────────────┼────────────────┼─────────────────────────────────────────────────────────────┤
  │ Cross-Event Analysis         │ src/knowledge/reasoning/cross_event.py            │ 1 file         │ Pairwise agreement scoring. Only reachable from dead        │
  │                              │                                                   │                │ OrchestrationEngine.                                        │
  ├──────────────────────────────┼───────────────────────────────────────────────────┼────────────────┼─────────────────────────────────────────────────────────────┤
  │ Technical Indicators         │ src/technical/indicators.py                       │ 1 file         │ RSI, MACD, EMA, SMA, Bollinger Bands. Zero imports from     │
  │                              │                                                   │                │ anywhere.                                                   │
  ├──────────────────────────────┼───────────────────────────────────────────────────┼────────────────┼─────────────────────────────────────────────────────────────┤
  │ Evidence Ranking             │ src/knowledge/evidence/ranker.py                  │ 1 file         │ Multi-criteria ranking. Zero callers.                       │
  ├──────────────────────────────┼───────────────────────────────────────────────────┼────────────────┼─────────────────────────────────────────────────────────────┤
  │ All Repository Classes       │ 5 persistence classes                             │ 5 files        │ JSON serialization. Pipeline operates in-memory only. Zero  │
  │                              │                                                   │                │ production callers.                                         │
  ├──────────────────────────────┼───────────────────────────────────────────────────┼────────────────┼─────────────────────────────────────────────────────────────┤
  │ All Validator Classes        │ PipelineValidator, DecisionValidator              │ 2 files        │ Structural validation. Zero production callers.             │
  ├──────────────────────────────┼───────────────────────────────────────────────────┼────────────────┼─────────────────────────────────────────────────────────────┤
  │ NLP Sentiment                │ src/nlp/                                          │ 2 files        │ HuggingFace transformers for FOMC + news. Optional params   │
  │                              │                                                   │                │ never injected.                                             │
  ├──────────────────────────────┼───────────────────────────────────────────────────┼────────────────┼─────────────────────────────────────────────────────────────┤
  │ Macro Regime Detection       │ src/knowledge/regime/                             │ 1 file         │ Markov switching model. Optional param never injected.      │
  ├──────────────────────────────┼───────────────────────────────────────────────────┼────────────────┼─────────────────────────────────────────────────────────────┤
  │ EconomicBrain                │ src/knowledge/brain.py                            │ 1 file         │ Rule-based knowledge lookup. Superseded by                  │
  │                              │                                                   │                │ InferencePipeline.                                          │
  ├──────────────────────────────┼───────────────────────────────────────────────────┼────────────────┼─────────────────────────────────────────────────────────────┤
  │ MacroRegimeFeatureExtractor  │ src/knowledge/features/extractors/macro_regime.py │ 1 file         │ Requires fitted MacroRegimeDetector. No event class uses    │
  │                              │                                                   │                │ it.                                                         │
  └──────────────────────────────┴───────────────────────────────────────────────────┴────────────────┴─────────────────────────────────────────────────────────────┘

  ---
  6. DUPLICATE ORCHESTRATION PATHS

  6.1 Two ways to run the inference pipeline

  ┌──────────┬───────────────────────────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────────┐
  │          │                       Path A (via Orchestrator)                       │                            Path B (Direct)                            │
  ├──────────┼───────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
  │ Entry    │ InstitutionalOrchestrator.run_all() → stages._build_legacy_pipeline() │ Scripts call InferencePipeline().run(ctx) directly                    │
  ├──────────┼───────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
  │ Location │ src/orchestration/stages.py                                           │ run_experiment_002.py, 003.py, gate6_validation.py, dxy_capability.py │
  ├──────────┼───────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
  │ Caching  │ Yes (CacheManager + CheckpointManager)                                │ NO — bypassed entirely                                                │
  ├──────────┼───────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
  │ Context  │ PipelineContext built from orchestrator params dict                   │ PipelineContext built manually with potentially different defaults    │
  ├──────────┼───────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
  │ Risk     │ Inconsistent behavior between orchestrated and direct runs            │                                                                       │
  └──────────┴───────────────────────────────────────────────────────────────────────┴───────────────────────────────────────────────────────────────────────┘

  6.2 Two ways to build knowledge summaries

  ┌────────┬─────────────────────────────────────────────────────────────────┬─────────────────────────────────────┐
  │        │                        Path A (Pipeline)                        │           Path B (Direct)           │
  ├────────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────┤
  │ Via    │ InferencePipeline._stage_build_knowledge()                      │ dxy_capability.py:build_knowledge() │
  ├────────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────┤
  │ Config │ LessonSummaryConfig from ctx.condition_columns                  │ Hardcoded condition tuples          │
  ├────────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────┤
  │ Risk   │ Different condition columns → different summaries for same data │                                     │
  └────────┴─────────────────────────────────────────────────────────────────┴─────────────────────────────────────┘

  6.3 Two ways to build context comparisons

  Path A: InferencePipeline._stage_compare_context() — config from PipelineContext
  Path B: dxy_capability.py:build_comparison() — manually constructed config
  Risk: Different base_condition_columns / context_condition_columns

  6.4 Two context-building invocations in the same pipeline run

  stages._forecast_confidence() and stages._build_context() both create separate ForecastContextBuilder() instances and call .build(). They may produce identical
  results or diverge if input params differ between stages.

  6.5 Decision type constants duplicated

  Location A: src/knowledge/decision/decision.py — canonical constants (DECISION_STRONG_POSITIVE, etc.)
  Location B: src/execution/execution_engine.py:15-20 — independently defined string copies
  Risk: Rename in one location silently breaks the other.

  ---
  7. COMPONENTS THAT EXIST BUT ARE NEVER CONSUMED

  #: 7.1
  Component: Lesson dataclass
  Location: src/knowledge/models/lesson.py
  What It Produces: Structured domain model with 1d/3d/7d/30d horizons
  Why Unused: LessonBuilder produces dict/DataFrame, not Lesson instances. Older model.
  ────────────────────────────────────────
  #: 7.2
  Component: EvidenceCollection.aggregate()
  Location: src/knowledge/evidence/collection.py
  What It Produces: {count, avg_confidence, avg_sample_count, avg_return_pct}
  Why Unused: Neither pipeline nor engine calls .aggregate(). Evidence iterated directly.
  ────────────────────────────────────────
  #: 7.3
  Component: EvidenceCollection.filter()
  Location: src/knowledge/evidence/collection.py
  What It Produces: Filtered collection
  Why Unused: EvidenceQuery.matching() handles all filtering; post-hoc filter never called.
  ────────────────────────────────────────
  #: 7.4
  Component: ReasoningChain.attribution
  Location: src/knowledge/reasoning/chain.py
  What It Produces: Per-event-type contribution percentages
  Why Unused: Populated by ReasoningEngine._build_conclusion() but never read by DecisionEngine.decide(). Computed and discarded.
  ────────────────────────────────────────
  #: 7.5
  Component: InstitutionalAssessment.outputs (10 of 11 keys)
  Location: src/orchestration/models.py
  What It Produces: Full stage output dict
  Why Unused: Only outputs["finalize"] is read by _assessment_to_result(). 10 other stage outputs are stored but never accessed.
  ────────────────────────────────────────
  #: 7.6
  Component: ForecastEvidence + ForecastEvidenceBuilder
  Location: src/forecasting/evidence.py
  What It Produces: Structured evidence from forecast+context+confidence
  Why Unused: stages._forecast_confidence does NOT call ForecastEvidenceBuilder.build(). The step is missing.
  ────────────────────────────────────────
  #: 7.7
  Component: ForecastReasoning.assess()
  Location: src/forecasting/reasoning.py
  What It Produces: ForecastAssessment
  Why Unused: No stage calls it. Forecasting produces forecasts and confidence but never its own reasoning.
  ────────────────────────────────────────
  #: 7.8
  Component: KnowledgeRecord.to_dict()
  Location: src/knowledge/integrity/knowledge_record.py
  What It Produces: Serialized dict
  Why Unused: Serialization done by LessonSummaryAggregator writing raw dicts, not via KnowledgeRecord.
  ────────────────────────────────────────
  #: 7.9
  Component: CausalRepository, TemporalRepository, EconomicRepository
  Location: src/knowledge/causal/, temporal/, economics/
  What It Produces: Persistence
  Why Unused: Only reachable through dead OrchestrationEngine.
  ────────────────────────────────────────
  #: 7.10
  Component: MacroRegimeFeatureExtractor
  Location: src/knowledge/features/extractors/macro_regime.py
  What It Produces: Regime-augmented DataFrame
  Why Unused: No event class instantiates it; requires fitted MacroRegimeDetector that nothing provides.

  ---
  8. COMPONENTS THAT CONSUME DATA NEVER PRODUCED

  #: 8.1
  Consumer: OrchestrationEngine._run_economic()
  Location: src/knowledge/orchestration/engine.py
  What It Needs: ctx.economic_states (list of EconomicState)
  What's Missing: Nothing creates EconomicState or populates OrchestrationContext. EconomicClassifier.classify() exists but is never called.
  ────────────────────────────────────────
  #: 8.2
  Consumer: OrchestrationEngine._run_temporal()
  Location: Same
  What It Needs: ctx.temporal_indexer (populated TemporalIndexer)
  What's Missing: Nothing creates or populates a TemporalIndexer.
  ────────────────────────────────────────
  #: 8.3
  Consumer: OrchestrationEngine._run_causal()
  Location: Same
  What It Needs: ctx.causal_graph (populated CausalGraph)
  What's Missing: Nothing creates a CausalGraph with CausalRelation objects.
  ────────────────────────────────────────
  #: 8.4
  Consumer: FeedbackApplicator.apply()
  Location: src/knowledge/evolution/applicator.py
  What It Needs: Scored EventRunResult with decision_correct, decision_actual_return_pct
  What's Missing: HistoricalReplayEngine does compute these fields, but FeedbackApplicator is never invoked with the results. Data produced, consumer unwired.
  ────────────────────────────────────────
  #: 8.5
  Consumer: ForecastContextBuilder._resolve_regime()
  Location: src/forecasting/context.py
  What It Needs: Fitted MacroRegimeDetector with .regime_labels
  What's Missing: Never injected. Additionally, .fit() requires a DataFrame with composite_score column that nothing produces. Returns "UNKNOWN".
  ────────────────────────────────────────
  #: 8.6
  Consumer: ForecastContextBuilder._resolve_news_sentiment()
  Location: Same
  What It Needs: NewsSentimentAnalyzer
  What's Missing: Never injected. stages._ingest_news collects NewsArticle objects but they're never converted to texts for the analyzer.
  ────────────────────────────────────────
  #: 8.7
  Consumer: ForecastContextBuilder._resolve_fomc_sentiment()
  Location: Same
  What It Needs: FOMCSentimentAnalyzer
  What's Missing: Never injected.
  ────────────────────────────────────────
  #: 8.8
  Consumer: DecisionGate.evaluate() — drawdown_state
  Location: src/forecasting/decision_gate.py
  What It Needs: Drawdown state from DrawdownManager.evaluate()
  What's Missing: stages._risk_gate passes drawdown_state="normal" hardcoded. DrawdownManager is never called.
  ────────────────────────────────────────
  #: 8.9
  Consumer: KellyCap.compute()
  Location: src/forecasting/position_sizing.py
  What It Needs: win_prob, payoff_ratio from historical performance
  What's Missing: stages._position_sizing calls VolatilityTargetSizer and RiskParitySizer but never KellyCap. No code computes win probability.
  ────────────────────────────────────────
  #: 8.10
  Consumer: OrchestrationContext.evidence_query
  Location: src/knowledge/orchestration/context.py
  What It Needs: Pre-built KnowledgeGraph inside EvidenceQuery
  What's Missing: Dead code. Nothing constructs the graph before creating OrchestrationContext.
  ────────────────────────────────────────
  #: 8.11
  Consumer: DXYContextEnricher (pipeline integration)
  Location: src/knowledge/context/dxy.py
  What It Needs: A ctx.dxy_data_path field in PipelineContext
  What's Missing: Field does not exist. PipelineContext has yield_data_path for YieldContextEnricher but no DXY equivalent. DXY only works via direct script invocation.

  ---
  Summary — Architectural Reality

  Active production spine:
  Scripts → simulation.HistoricalReplayEngine / ExperimentRunner
    → orchestration.InstitutionalOrchestrator (11-stage DAG with ThreadPool)
      → knowledge.pipeline.InferencePipeline (7 sequential stages)
        → events → features → lessons → summaries → graph → evidence → reasoning → Decision
      → forecasting.* (forecast → confidence → validation → risk measures → position sizing → risk gate)
    → InstitutionalAssessment

  Code reachability: ~40-50% of defined classes/methods are reachable from production entrypoints. The remainder consists of:
  - 5 fully-built but unwired subsystems (execution, knowledge orchestration, learning, evolution, expansion)
  - 5 repository classes implementing persistence for objects only used in-memory
  - 2 validator classes that are never called
  - 3 NLP/regime capabilities accepted as optional parameters but never injected
  - Technical indicators with zero imports

  Key architectural gap: The knowledge.orchestration.OrchestrationEngine was designed to unify economics, temporal, causal, and core evidence into a single analysis —
  but nothing connects it to InstitutionalOrchestrator or InferencePipeline. The execution package was designed to turn decisions into trades — but nothing connects it
  to _finalize stage output. The learning/evolution loop was designed to feed EventRunResult back into knowledge calibration — HistoricalReplayEngine produces scored
  results, but the feedback applicator is never invoked with them.

✻ Brewed for 1h 40m 15s

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────> 