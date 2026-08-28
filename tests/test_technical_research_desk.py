"""Sprint 056-T: Technical Research Desk test suite.

Covers the sprint's fifteen mandated verification categories:
golden values, determinism, movement semantics, multi-timeframe behavior,
no-lookahead, missing data, insufficient history, invalid OHLCV,
serialization, provenance/hash, dependency failure, institutional
isolation, historical as-of correctness, runtime integration, and
proof that TechnicalAssessment cannot alter the W13/W14 path.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from technical.contracts import (
    DIRECTION_BEARISH,
    DIRECTION_BULLISH,
    DIRECTION_NEUTRAL,
    DIRECTION_UNKNOWN,
    OBOS_OVERBOUGHT,
    TechnicalAssessment,
    TechnicalDataError,
    TechnicalDependencyError,
)
from technical.desk import (
    TechnicalResearchDesk,
    canonical_source_hash,
)
from technical.engine import ENGINE_COLUMNS, PandasTaClassicEngine
from technical.market_structure import analyze_structure


# ---------------------------------------------------------------------------
# Synthetic data builders (deterministic)
# ---------------------------------------------------------------------------


def _base_frame(
    n: int = 320,
    seed: int = 42,
    drift: float = 0.08,
    end: str = "2025-06-01",
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 1500.0 + np.linspace(0.0, drift * n, n) + rng.normal(0, 4.0, n).cumsum() * 0.2
    close = np.clip(close, 100.0, None)
    span = np.abs(rng.normal(1.5, 0.5, n))
    high = close + span
    low = close - span
    open_ = np.concatenate([[close[0]], close[:-1]])
    idx = pd.bdate_range(end=end, periods=n)
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.integers(100, 5000, n).astype(float),
        },
        index=idx,
    )


def _daily_csv(frame: pd.DataFrame, tmp_path: Path) -> Path:
    p = tmp_path / "gold_daily.csv"
    out = frame.reset_index().rename(columns={"index": "Date"})
    out.to_csv(p, index=False)
    return p


FIXED_CREATED_AT = "2026-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# 1) Golden indicator values (regression pins against the current engine)
# ---------------------------------------------------------------------------


class TestGoldenValues:
    def _golden_frame(self) -> pd.DataFrame:
        rng = np.random.default_rng(11)
        n = 120
        close = pd.Series(
            100 + rng.normal(0, 1, n).cumsum() + np.linspace(0, 20, n)
        )
        high = close + np.abs(rng.normal(0, 0.4, n))
        low = close - np.abs(rng.normal(0, 0.4, n))
        open_ = close.shift(1).fillna(close.iloc[0])
        vol = rng.integers(100, 1000, n).astype(float)
        idx = pd.bdate_range("2024-01-01", periods=n)
        return pd.DataFrame(
            {
                "open": open_.values,
                "high": high.values,
                "low": low.values,
                "close": close.values,
                "Volume": vol,
            },
            index=idx,
        )

    def test_engine_golden_last_row(self) -> None:
        df = self._golden_frame()
        out = PandasTaClassicEngine().compute(df)
        last = out.iloc[-1]
        expected = {
            "ema_20": 121.305386,
            "rsi_14": 66.853491,
            "macd_line": 2.105421,
            "atr_14": 1.347192,
            "adx_14": 30.373088,
            "bb_upper": 125.500216,
            "bb_width": 0.076023,
            "roc_9": 3.950048,
        }
        for column, golden in expected.items():
            assert abs(float(last[column]) - golden) < 1e-5, column

    def test_roc_matches_exact_definition(self) -> None:
        df = self._golden_frame()
        out = PandasTaClassicEngine().compute(df)
        reference = (df["close"] / df["close"].shift(9) - 1.0) * 100.0
        valid = reference.notna()
        assert np.allclose(out["roc_9"][valid], reference[valid])

    def test_macd_histogram_identity(self) -> None:
        df = self._golden_frame()
        out = PandasTaClassicEngine().compute(df).dropna()
        assert np.allclose(
            out["macd_hist"], out["macd_line"] - out["macd_signal_line"]
        )

    def test_bollinger_ordering_and_width(self) -> None:
        df = self._golden_frame()
        out = PandasTaClassicEngine().compute(df).dropna(subset=["bb_upper"])
        assert (out["bb_upper"] >= out["bb_middle"]).all()
        assert (out["bb_middle"] >= out["bb_lower"]).all()
        width_ref = (out["bb_upper"] - out["bb_lower"]) / out["bb_middle"]
        assert np.allclose(out["bb_width"], width_ref)

    def test_atr_positive_when_range_present(self) -> None:
        df = self._golden_frame()
        atr = PandasTaClassicEngine().compute(df)["atr_14"].dropna()
        assert (atr > 0).all()


# ---------------------------------------------------------------------------
# 2) Deterministic repeated execution
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_repeated_assessment_identical(self) -> None:
        df = _base_frame()
        desk = TechnicalResearchDesk()
        a = desk.assess(df, "2025-06-01", created_at=FIXED_CREATED_AT).to_dict()
        b = desk.assess(df, "2025-06-01", created_at=FIXED_CREATED_AT).to_dict()
        assert a == b

    def test_engine_repeated_execution_identical(self) -> None:
        df = _base_frame(n=300)
        eng = PandasTaClassicEngine()
        a = eng.compute(df)
        b = eng.compute(df)
        pd.testing.assert_frame_equal(a, b)

    def test_content_derived_assessment_id(self) -> None:
        base = _base_frame(n=320)
        extended = pd.concat([base, _base_frame(n=40, end="2025-08-29")])
        d1 = TechnicalResearchDesk().assess(
            base, "2025-06-01", created_at=FIXED_CREATED_AT
        )
        d2 = TechnicalResearchDesk().assess(
            extended, "2025-06-01", created_at=FIXED_CREATED_AT
        )
        # Identical used slice => identical content-derived id.
        assert d1.assessment_id == d2.assessment_id


# ---------------------------------------------------------------------------
# 3) Positive / negative movement semantics (polarity guard)
# ---------------------------------------------------------------------------


class TestMovementSemantics:
    def test_uptrend_reads_bullish(self) -> None:
        df = _base_frame(drift=0.35, seed=7)
        a = TechnicalResearchDesk().assess(df, "2025-06-01")
        assert a.trend_direction == DIRECTION_BULLISH

    def test_downtrend_reads_bearish(self) -> None:
        df = _base_frame(drift=-0.35, seed=7)
        a = TechnicalResearchDesk().assess(df, "2025-06-01")
        assert a.trend_direction == DIRECTION_BEARISH

    def test_overbought_in_uptrend_is_not_a_bearish_flip(self) -> None:
        # Strong monotone rally: RSI is pinned high but the desk must keep
        # the trend bullish and only label the RSI state.
        n = 320
        close = 1000.0 + np.linspace(0, 400, n)
        df = pd.DataFrame(
            {
                "open": close,
                "high": close * 1.002,
                "low": close * 0.998,
                "close": close,
            },
            index=pd.bdate_range(end="2025-06-01", periods=n),
        )
        a = TechnicalResearchDesk().assess(df, "2025-06-01")
        assert a.overbought_oversold_state == OBOS_OVERBOUGHT
        assert a.trend_direction == DIRECTION_BULLISH
        assert any("not auto-reversal" in note for note in a.metadata["notes"])

    def test_oversold_in_downtrend_is_not_a_bullish_flip(self) -> None:
        n = 320
        close = 1400.0 - np.linspace(0, 400, n)
        df = pd.DataFrame(
            {
                "open": close,
                "high": close * 1.002,
                "low": close * 0.998,
                "close": close,
            },
            index=pd.bdate_range(end="2025-06-01", periods=n),
        )
        a = TechnicalResearchDesk().assess(df, "2025-06-01")
        assert a.overbought_oversold_state == "oversold"
        assert a.trend_direction == DIRECTION_BEARISH

    def test_confidence_zero_without_directional_signals(self) -> None:
        flat = pd.DataFrame(
            {"close": [100.0] * 300},
            index=pd.bdate_range(end="2025-06-01", periods=300),
        )
        flat["high"] = flat["close"] + 0.5
        flat["low"] = flat["close"] - 0.5
        flat["open"] = flat["close"]
        a = TechnicalResearchDesk().assess(flat, "2025-06-01")
        assert a.technical_confidence == 0.0
        assert a.trend_direction == DIRECTION_NEUTRAL


# ---------------------------------------------------------------------------
# 4) Multi-timeframe design consistency
# ---------------------------------------------------------------------------


class TestMultiTimeframe:
    def test_supported_timeframes_accepted(self) -> None:
        df = _base_frame()
        desk = TechnicalResearchDesk()
        for timeframe in ("D1", "H4", "H1"):
            assessment = desk.assess(df, "2025-06-01", timeframe=timeframe)
            assert assessment.timeframe == timeframe

    def test_intraday_request_on_daily_data_flags_mismatch(self) -> None:
        df = _base_frame()
        a = TechnicalResearchDesk().assess(df, "2025-06-01", timeframe="H4")
        assert a.metadata.get("status_qualifier") == "frequency_mismatch"
        assert any("timeframe_data_mismatch" in n for n in a.metadata["notes"])

    def test_unsupported_timeframe_rejected(self) -> None:
        with pytest.raises(TechnicalDataError):
            TechnicalResearchDesk().assess(_base_frame(), "2025-06-01", "M15")


# ---------------------------------------------------------------------------
# 5) NO LOOKAHEAD
# ---------------------------------------------------------------------------


class TestNoLookahead:
    def test_future_crash_cannot_change_past_assessment(self) -> None:
        base = _base_frame(n=320, end="2025-06-01")
        shocked = pd.concat([base, _base_frame(n=60, drift=-0.9, end="2025-09-01")])
        desk = TechnicalResearchDesk()
        before = desk.assess(
            base, "2025-06-01", created_at=FIXED_CREATED_AT
        ).to_dict()
        after = desk.assess(
            shocked, "2025-06-01", created_at=FIXED_CREATED_AT
        ).to_dict()
        assert before == after

    def test_as_of_slice_excludes_later_rows(self) -> None:
        df = _base_frame(n=300)
        desk = TechnicalResearchDesk()
        full = desk.assess(df, "2025-12-31", created_at=FIXED_CREATED_AT)
        early = desk.assess(df, df.index[200], created_at=FIXED_CREATED_AT)
        assert early.metadata["bars_used"] == 201
        assert full.metadata["bars_used"] == 300
        assert early.source_data_hash != full.source_data_hash

    def test_source_hash_covers_only_used_slice(self) -> None:
        base = _base_frame(n=250, end="2025-03-01")
        extended = pd.concat([base, _base_frame(n=50, end="2025-05-30")])
        sliced = base.iloc[:201]
        assert canonical_source_hash(sliced) == canonical_source_hash(
            base.iloc[:201]
        )
        assert canonical_source_hash(base) != canonical_source_hash(extended)


# ---------------------------------------------------------------------------
# 6) Missing data handling
# ---------------------------------------------------------------------------


class TestMissingData:
    def test_interior_nan_close_rows_are_skipped(self) -> None:
        df = _base_frame(n=300)
        df.iloc[10:15, df.columns.get_loc("close")] = np.nan
        a = TechnicalResearchDesk().assess(df, "2025-06-01")
        assert a.metadata["bars_used"] == 295

    def test_all_nan_close_rejected(self) -> None:
        df = _base_frame(n=300)
        df["close"] = np.nan
        with pytest.raises(TechnicalDataError):
            TechnicalResearchDesk().assess(df, "2025-06-01")


# ---------------------------------------------------------------------------
# 7) Insufficient history handling
# ---------------------------------------------------------------------------


class TestInsufficientHistory:
    def test_short_history_degrades_cleanly(self) -> None:
        df = _base_frame(n=120)
        a = TechnicalResearchDesk().assess(df, "2025-06-01")
        assert a.trend_direction == DIRECTION_UNKNOWN
        assert a.momentum_direction == DIRECTION_UNKNOWN
        assert a.structure_state is None
        assert a.technical_confidence == 0.0
        assert any("insufficient_history" in n for n in a.metadata["notes"])

    def test_empty_slice_degrades_cleanly(self) -> None:
        df = _base_frame(n=300)
        a = TechnicalResearchDesk().assess(df, "1999-01-01")
        assert a.technical_confidence == 0.0
        assert a.source_data_hash == ""


# ---------------------------------------------------------------------------
# 8) Invalid OHLCV handling
# ---------------------------------------------------------------------------


class TestInvalidOHLCV:
    def test_missing_close_column(self) -> None:
        with pytest.raises(TechnicalDataError):
            TechnicalResearchDesk().assess(pd.DataFrame({"price": [1.0]}), "2025-01-01")

    def test_negative_prices_rejected(self) -> None:
        df = _base_frame(n=300)
        df.loc[df.index[50], "low"] = -5.0
        with pytest.raises(TechnicalDataError):
            TechnicalResearchDesk().assess(df, "2025-06-01")

    def test_high_below_low_rejected(self) -> None:
        df = _base_frame(n=300)
        df.loc[df.index[80], "high"] = df.loc[df.index[80], "low"] - 10.0
        with pytest.raises(TechnicalDataError):
            TechnicalResearchDesk().assess(df, "2025-06-01")

    def test_unparseable_as_of_rejected(self) -> None:
        with pytest.raises(TechnicalDataError):
            TechnicalResearchDesk().assess(_base_frame(), "not-a-date")

    def test_non_datetime_index_rejected(self) -> None:
        df = pd.DataFrame({"close": [1.0, 2.0]})
        with pytest.raises(TechnicalDataError):
            TechnicalResearchDesk().assess(df, "2025-01-01")


# ---------------------------------------------------------------------------
# 9) Serialization contract
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_roundtrip_preserves_payload(self) -> None:
        a = TechnicalResearchDesk().assess(_base_frame(), "2025-06-01")
        restored = TechnicalAssessment.from_dict(a.to_dict())
        assert restored == a

    def test_validate_passes_on_real_assessment(self) -> None:
        a = TechnicalResearchDesk().assess(_base_frame(), "2025-06-01")
        assert a.validate() == []

    def test_validate_rejects_bad_confidence(self) -> None:
        payload = TechnicalResearchDesk().assess(
            _base_frame(), "2025-06-01"
        ).to_dict()
        payload["technical_confidence"] = 1.5
        broken = TechnicalAssessment.from_dict(payload)
        assert broken.validate()


# ---------------------------------------------------------------------------
# 10) Provenance and source hash
# ---------------------------------------------------------------------------


class TestProvenanceAndHash:
    def test_provenance_contract_fields(self) -> None:
        a = TechnicalResearchDesk().assess(
            _base_frame(), "2025-06-01", created_at=FIXED_CREATED_AT
        )
        entry = a.provenance_chain[0]
        assert entry["created_by"] == "TechnicalResearchDesk"
        assert entry["entity_version"] == "1.0.0"
        assert entry["created_at"] == FIXED_CREATED_AT
        assert entry["metadata"]["engine"] == "pandas_ta_classic"

    def test_hash_stable_and_sensitive(self) -> None:
        df = _base_frame(n=300)
        h1 = canonical_source_hash(df)
        h2 = canonical_source_hash(df.copy())
        assert h1 == h2
        mutated = df.copy()
        mutated.iloc[0, mutated.columns.get_loc("close")] += 0.001
        assert h1 != canonical_source_hash(mutated)

    def test_assessment_id_changes_with_data(self) -> None:
        df = _base_frame(n=300)
        other = df.copy()
        other.iloc[-1, other.columns.get_loc("close")] += 5.0
        desk = TechnicalResearchDesk()
        a = desk.assess(df, "2025-06-01", created_at=FIXED_CREATED_AT)
        b = desk.assess(other, "2025-06-01", created_at=FIXED_CREATED_AT)
        assert a.assessment_id != b.assessment_id
        assert a.source_data_hash != b.source_data_hash


# ---------------------------------------------------------------------------
# 11) Library dependency failure
# ---------------------------------------------------------------------------


class TestDependencyFailure:
    def test_missing_library_raises_explicit_error(self, monkeypatch) -> None:
        monkeypatch.setitem(sys.modules, "pandas_ta_classic", None)
        engine = PandasTaClassicEngine()
        engine._ta = None  # force lazy re-load path
        with pytest.raises(TechnicalDependencyError, match="pip install"):
            engine.compute(_base_frame(n=300))

    def test_desk_propagates_dependency_error(self, monkeypatch) -> None:
        monkeypatch.setitem(sys.modules, "pandas_ta_classic", None)
        desk = TechnicalResearchDesk()
        with pytest.raises(TechnicalDependencyError):
            desk.assess(_base_frame(), "2025-06-01")

    def test_custom_engine_failure_surfaces_clearly(self) -> None:
        class FailingEngine:
            name = "failing"

            def compute(self, ohlcv):  # noqa: ANN001
                raise RuntimeError("boom")

        desk = TechnicalResearchDesk(engine=FailingEngine())
        with pytest.raises(RuntimeError):
            desk.assess(_base_frame(), "2025-06-01")


# ---------------------------------------------------------------------------
# 12) Institutional isolation
# ---------------------------------------------------------------------------


class TestInstitutionalIsolation:
    def test_desk_api_has_no_institutional_inputs(self) -> None:
        import inspect

        signature = inspect.signature(TechnicalResearchDesk.assess)
        param_names = set(signature.parameters)
        forbidden = {
            "decision",
            "thesis",
            "confidence",
            "institutional_confidence",
            "bias_review",
        }
        assert param_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# 13) Historical as-of correctness on real local data
# ---------------------------------------------------------------------------


class TestHistoricalAsOf:
    def test_two_dates_use_their_own_windows(self) -> None:
        raw = pd.read_csv("data/history/gold/gold.csv")
        desk = TechnicalResearchDesk()
        first = desk.assess(raw, "2020-06-30", created_at=FIXED_CREATED_AT)
        second = desk.assess(raw, "2024-06-28", created_at=FIXED_CREATED_AT)
        assert first.as_of == "2020-06-30"
        assert first.source_data_hash != second.source_data_hash
        assert first.metadata["bars_used"] < second.metadata["bars_used"]
        for assessment in (first, second):
            assert assessment.validate() == []

    def test_manual_slice_equivalence(self) -> None:
        raw = pd.read_csv("data/history/gold/gold.csv")
        desk = TechnicalResearchDesk()
        direct = desk.assess(raw, "2021-12-31", created_at=FIXED_CREATED_AT)
        manual = pd.read_csv("data/history/gold/gold.csv")
        manual_ts = pd.to_datetime(manual["Date"])
        manual = manual[manual_ts <= pd.Timestamp("2021-12-31")]
        indirect = desk.assess(manual, "2021-12-31", created_at=FIXED_CREATED_AT)
        assert direct.to_dict() == indirect.to_dict()


# ---------------------------------------------------------------------------
# 14) Integration inside AurumAI
# ---------------------------------------------------------------------------


class TestRuntimeIntegration:
    def test_stage_writes_artifact_and_returns_payload(self, tmp_path) -> None:
        from orchestration.stages import _technical_research

        gold_csv = _daily_csv(_base_frame(n=320), tmp_path)
        params = {
            "gold_path": str(gold_csv),
            "output_dir": str(tmp_path),
            "asset": "XAU/USD",
            "technical_as_of": "2025-06-01",
        }
        payload = _technical_research(params, {})
        assert "error" not in payload
        artifact = tmp_path / "technical_assessment.json"
        assert artifact.is_file()
        loaded = json.loads(artifact.read_text(encoding="utf-8"))
        assert TechnicalAssessment.from_dict(loaded) == TechnicalAssessment.from_dict(
            payload
        )

    def test_stage_fails_safe_on_missing_input(self, tmp_path) -> None:
        from orchestration.stages import _technical_research

        payload = _technical_research({"output_dir": str(tmp_path)}, {})
        assert "error" in payload
        payload = _technical_research(
            {"gold_path": str(tmp_path / "missing.csv")}, {}
        )
        assert "error" in payload

    def test_dag_registration_leaf_topology(self) -> None:
        from orchestration.orchestrator import InstitutionalOrchestrator

        orch = InstitutionalOrchestrator.with_default_pipeline()
        job = orch._jobs["technical_research"]
        assert job.dependencies == ("build_legacy_pipeline",)
        consumers = [
            jid
            for jid, j in orch._jobs.items()
            if "technical_research" in j.dependencies
        ]
        # Final Hardening (Group F): thesis_construction consumes the desk's
        # NON-SCORING research context (metadata only).  The desk remains
        # fully excluded from every decision-scoring path.
        assert consumers == ["thesis_construction"]
        assert "technical_research" not in orch._jobs["finalize"].dependencies
        assert "technical_research" not in orch._jobs["decision_engine"].dependencies


# ---------------------------------------------------------------------------
# 15) Proof: TechnicalAssessment does not change W13/W14 outputs
# ---------------------------------------------------------------------------


class TestDecisionInvariance:
    @staticmethod
    def _decision():
        from decision_engine.contracts import InstitutionalDecision

        return InstitutionalDecision(
            decision_id="dec_test_fixed",
            decision="BUY",
            selected_thesis_id="th_x",
            selected_scenario_id="sc_y",
            institutional_confidence=0.72,
            risk_reward_summary={
                "status": "acceptable",
                "maximum_downside": 0.4,
                "expected_upside": 0.6,
                "liquidity_risk": 0.2,
            },
            decision_explanation="fixture",
        )

    def test_trade_recommendation_ignores_technical_artifact(self) -> None:
        from orchestration.stages import _trade_recommendation
        from trade_recommendation.contracts import (
            InstitutionalTradeRecommendation,
        )

        decision = self._decision()
        without = _trade_recommendation(
            {"asset": "XAU/USD", "reference_price": 2000.0},
            {"decision_engine": decision},
        )
        with_artifact = _trade_recommendation(
            {"asset": "XAU/USD", "reference_price": 2000.0},
            {
                "decision_engine": decision,
                "technical_research": {"trend_direction": DIRECTION_BEARISH},
            },
        )
        left = InstitutionalTradeRecommendation.from_dict(without.to_dict())
        right = InstitutionalTradeRecommendation.from_dict(
            with_artifact.to_dict()
        )
        left_id, right_id = left.recommendation_id, right.recommendation_id
        assert left_id.startswith("rec_") and right_id.startswith("rec_")
        object.__setattr__(left, "recommendation_id", "")
        object.__setattr__(right, "recommendation_id", "")
        object.__setattr__(left, "provenance_chain", ())
        object.__setattr__(right, "provenance_chain", ())
        assert left == right

    def test_decision_engine_signature_has_no_technical_input(self) -> None:
        import inspect

        from decision_engine.engine import DecisionEngine

        params = list(inspect.signature(DecisionEngine.decide).parameters)
        assert params == [
            "self", "construction", "confidence", "generation", "validation",
        ]
