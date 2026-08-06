# W2 Restoration — Implementation Design (v1)

Reuses the existing architecture only. No redesign, no contract change, no
decision/confidence/threshold/score-formula change. Analysis algorithms are
reused as-is; only the orchestration glue and one policy-lacing (regime_weight
source) are added.

---

## 1. Files to modify

| File | Change |
|---|---|
| `src/orchestration/stages.py` | Add new stage `_regime_diagnosis(params, results)`; edit three reads: `_pre_market_scan` (regime source), `_signal_assessment` (regime re-stamp), `_evidence_collection` (regime_weight source). |
| `src/orchestration/orchestrator.py` | Register `regime_diagnosis` job; change `pre_market_scan` dependencies `()` -> `("regime_diagnosis",)`. |
| `tests/test_institutional_orchestrator.py` | Update the two hard-coded DAG/stage-set assertions (the level-0 contents and the 25-job set) to include `regime_diagnosis`. |
| `tests/test_regime_diagnosis_stage.py` | New test module (see section 9). |

No changes to `knowledge/regime/*`, `signal_assessment/*`,
`evidence_collection/collector.py`, any contract, `KnowledgeRecord`,
`KnowledgeGraph`, `run.py`, `runtime_config.json`, or the decision/confidence
engines.

## 2. New orchestration stage

`regime_diagnosis` (stage fn `_regime_diagnosis`), registered like its peers:
`PipelineJob(job_id="regime_diagnosis", dependencies=("build_legacy_pipeline",),
fn=orch._bind(_regime_diagnosis), cache_ttl=1800, checkpoint=True)`.

Behavior (all computation reused — see section 6):

1. `composite = CompositeScoreBuilder().build()`.
2. `detector = InstitutionalRegimeDetector(random_state=42).fit(composite)`.
3. `diag = detector.diagnose(float(composite["composite_score"].iloc[-1]))`.
4. `kg = results.get("build_legacy_pipeline", {}).get("knowledge_graph")`;
   `hier = IndicatorHierarchyGenerator().generate(diag.regime,
   include_krs=True, graph=kg)`.
5. Compose a full `RegimeDiagnosis` = `diag` fields + populated
   `indicator_hierarchy` (from `hier["indicators"]`) +
   `trigger_levels` (from `hier["trigger_levels"]`); `cross_asset_consistency={}`.
6. `RegimeDiagnosis.validate()`; write artifact
   `{params["output_dir"]}/regime_diagnosis.json`; return `diag.to_dict()`.

## 3. Exact DAG dependencies

- New: `regime_diagnosis` -> dependencies `("build_legacy_pipeline",)`.
- Changed: `pre_market_scan` dependencies `()` -> `("regime_diagnosis",)`.
- Unchanged: `signal_assessment` `("pre_market_scan",)`; `event_triage`
  `("signal_assessment",)`; `evidence_collection`
  `("event_triage","build_legacy_pipeline")`; all others untouched.

Consumers read `results["regime_diagnosis"]` transitively (all three sit
downstream of `pre_market_scan`). Topological consequence: `pre_market_scan`
leaves level 0; `ingest_event`/`ingest_news` remain roots; no cycles.

## 4. Exact runtime inputs

- Macro composite DataFrame via `CompositeScoreBuilder().build()` from the repo
  CSVs `data/economic/{CPIAUCSL,PPIACO,PMI,UNRATE,PAYEMS}.csv`.
- `knowledge_graph` from `results["build_legacy_pipeline"]["knowledge_graph"]`.
- `params["output_dir"]` (existing param).

Not new inputs: GPR series (stage uses `diagnose` default `gpr_value=0.0`),
GRAM residual (default `gram_residual_value=0.0`), regime passed by caller,
`event_type`. `random_state=42` fixed.

## 5. Exact runtime outputs / propagation

- `results["regime_diagnosis"]` = `RegimeDiagnosis.to_dict()` (full Contract 2
  object: regime, label, confidence, probabilities x6, in_transition,
  transition_type, previous_regime, timestamp, transition_confidence,
  regime_duration_days, gram_residual, gram_trend, indicator_hierarchy,
  trigger_levels).
- Artifact file `{output_dir}/regime_diagnosis.json`.
- Propagation (downstream stages consume W2 outputs):
  - `_pre_market_scan`: `briefing.regime` / `briefing.regime_confidence` from
    diagnosis when present.
  - `_signal_assessment`: `SignalAssessment.regime` / `regime_confidence`
    re-stamped from diagnosis when present.
  - `_evidence_collection`: `regime_weight` = `diagnosis.confidence` (falls
    back to existing `params["regime_weight"]` default `0.8` when absent).
- No change to `finalize`/decision engine outputs; delta (if any) is
  downstream-only.

## 6. Existing components reused (unchanged)

- `CompositeScoreBuilder().build()` — `knowledge/regime/composite_score.py`.
- `InstitutionalRegimeDetector(random_state=42).fit(composite_data)` +
  `.diagnose(composite_score, gpr_value=0.0, gram_residual_value=0.0)` —
  `knowledge/regime/institutional_regime_detector.py`.
- `RegimeDiagnosis`, `RegimeIndicator`, `TriggerLevel` (+ `to_dict` /
  `from_dict` / `validate`) — `knowledge/regime/contracts.py`.
- `IndicatorHierarchyGenerator.generate(regime, include_krs=True, graph=kg)` —
  `knowledge/regime/indicator_hierarchy.py` (internally
  `_query_kr_ids_by_regime(graph, regime)`; nil-tolerant when `graph=None`).
- Constants `CANONICAL_REGIME_SET`, `REGIME_LABELS`, thresholds —
  `knowledge/regime/constants.py`.
- Orchestration framework `PipelineJob`, `.register`, `_bind` — unchanged
  semantics; artifact-write pattern from the legacy stages.

## 7. Genuinely new code

Only glue (no new analysis/algorithm):

1. `_regime_diagnosis(params, results)` — composition + persist.
2. `orchestrator.py` registration + the single deps edit.
3. Three additive `results["regime_diagnosis"]` reads inside existing stage
   functions (with fallback to current behavior/defaults: `""`/`0.0` regime,
   `0.8` regime_weight).
4. The mapping rule `regime_weight := diagnosis.confidence` (deterministic,
   in `[0,1]`).
5. NOT implemented (explicitly out of scope, no existing module): KR
   activation/deactivation semantics, GPR connector, term-premium connector,
   cross-asset consistency, any new market-intelligence capability.

Note: the statistical KG nodes carry no `regimes` property, so
`_query_kr_ids_by_regime` typically returns `[]`; the hierarchy is still
produced. The KR-mapping edge stays inert until an institutional KB graph with
`regime_dependence` is wired in (separate concern, out of scope).

## 8. Backward compatibility

- All new reads use `results.get("regime_diagnosis")` with fallbacks to today's
  defaults, so every standalone stage invocation behaves identically without
  the new key.
- No Contract 1/2/3/4 schema changes; `RegimeDiagnosis` already carries every
  required field.
- Breaking test-impact only: the hard-coded job-set/level-0 assertions in
  `test_institutional_orchestrator.py` (section 9).

## 9. Regression tests

New `tests/test_regime_diagnosis_stage.py` (headless; data from repo CSVs):

- `test_stage_emits_valid_regime_diagnosis` — `RegimeDiagnosis.validate()`
  empty; regime in `CANONICAL_REGIME_SET`; probabilities sum ~= 1;
  `confidence == max(probabilities)`.
- `test_stage_populates_hierarchy_and_trigger_levels` — `indicator_hierarchy`
  and `trigger_levels` non-empty; works with absent graph.
- `test_stage_writes_regime_artifact` — `{output_dir}/regime_diagnosis.json`
  written and restored via `from_dict`.
- `test_stage_fallback_without_graph` — no `build_legacy_pipeline` result:
  still succeeds.

Updated `tests/test_institutional_orchestrator.py`:

- `test_14_job_dag_structure` -> assert `regime_diagnosis` in the DAG, that
  `pre_market_scan` no longer is a root, and `ingest_event`/`ingest_news`
  remain roots.
- 25-job set assertions (the `expected` job sets in the full-pipeline and DAG
  tests) -> add `"regime_diagnosis"`.

## 10. Real runtime validation plan

1. `python run.py --no-refresh` -> expect 26 stages, all ok.
2. Read artifact `regime_diagnosis.json`: validate(); regime in canonical 6;
   probabilities ~ 1.0; confidence == max(probabilities).
3. Propagation: `Evidence.regime == diagnosis.regime` and
   `regime_weight == diagnosis.confidence` in the run's EvidenceCollection.
4. Before/after vs last runtime (`runtime/run_registry.jsonl` last entry +
   prior run `finalize.json`): record `institutional_confidence`,
   `evidence_quality`, and `decision` (delta expected where the diagnosed
   confidence differs from the previous constant 0.8).
5. Rerun the affected suites (section 9). Report regressions if any.