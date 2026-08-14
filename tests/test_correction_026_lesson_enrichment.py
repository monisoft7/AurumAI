"""Correction 026: canonical lesson enrichment at the artifact boundary.

Focused tests:

1. canonical enrichment uses the existing runtime composition
   (LessonBuilder + YieldContextEnricher + DXYContextEnricher +
   existing global MacroRegimeFeatureExtractor registration)
2. explicit output_path prevents destructive in-place ambiguity
3. lesson_id set preservation
4. event_date set preservation
5. enrichment columns present
6. no missing DFII10/DXY values across the supported lesson range
7. deterministic rebuild
8. unexplained row drift blocks replacement
9. existing lesson return statistics unchanged
10. regime mapping unchanged
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from knowledge.builders.lesson_builder import (
    DEFAULT_DXY_DATA_PATH,
    DEFAULT_YIELD_DATA_PATH,
    LessonBuilder,
    LessonBuilderConfig,
    build_canonical_lesson_artifact,
    compare_lesson_identity_sets,
    replace_canonical_after_gate,
)
from knowledge.context.dxy import DXYContextEnricher
from knowledge.context.yields import YieldContextEnricher
from knowledge.features.engine import FeatureExtractionEngine
from knowledge.features.extractors.macro_regime import MacroRegimeFeatureExtractor
from knowledge.regime.institutional_regime_detector import ECONOMIC_REGIME_LABELS
from knowledge.regime.macro_regime_detector import (
    CONTRACTION,
    EXPANSION,
    LATE_CYCLE,
    RECOVERY,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def write_gold(path: Path, start: str = "2020-01-02") -> None:
    rows: list[dict[str, object]] = []
    date = pd.Timestamp(start)
    close = 1000.0
    for _ in range(160):
        rows.append({"Date": date.date().isoformat(), "Close": round(close, 2)})
        date += pd.Timedelta(days=1)
        close += 10.0
    write_csv(path, rows)


def build_institutional_calendar(base_path: Path) -> Path:
    cal_path = base_path / "calendar" / "cpi_releases.csv"
    write_csv(
        cal_path,
        [
            {
                "reference_period": "2020-01-01",
                "release_date": "2020-02-13",
                "release_time": "08:30",
                "timezone": "US/Eastern",
            },
            {
                "reference_period": "2020-02-01",
                "release_date": "2020-03-12",
                "release_time": "08:30",
                "timezone": "US/Eastern",
            },
            {
                "reference_period": "2020-03-01",
                "release_date": "2020-04-10",
                "release_time": "08:30",
                "timezone": "US/Eastern",
            },
        ],
    )
    return cal_path


def toy_sources(base_path: Path) -> dict[str, Path]:
    cpi_path = base_path / "economic" / "CPIAUCSL.csv"
    gold_path = base_path / "history" / "gold.csv"
    yield_path = base_path / "economic" / "DFII10.csv"
    dxy_path = base_path / "context" / "dxy" / "dxy.csv"

    write_csv(
        cpi_path,
        [
            {"Date": "2019-12-01", "Value": 99.0},
            {"Date": "2020-01-01", "Value": 100.0},
            {"Date": "2020-02-01", "Value": 101.0},
            {"Date": "2020-03-01", "Value": 102.0},
        ],
    )
    write_gold(gold_path, start="2019-12-02")
    write_csv(
        yield_path,
        [
            {"Date": "2019-12-01", "Value": 1.50},
            {"Date": "2020-01-02", "Value": 1.60},
            {"Date": "2020-02-03", "Value": 1.70},
            {"Date": "2020-03-01", "Value": 1.90},
        ],
    )
    write_csv(
        dxy_path,
        [
            {"Date": "2019-12-01", "Value": 101.5},
            {"Date": "2020-01-02", "Value": 101.0},
            {"Date": "2020-02-03", "Value": 100.5},
            {"Date": "2020-03-01", "Value": 99.0},
        ],
    )
    return {
        "cpi": cpi_path,
        "gold": gold_path,
        "yield": yield_path,
        "dxy": dxy_path,
    }


@pytest.fixture
def toy(tmp_path: Path) -> dict[str, Path]:
    return toy_sources(tmp_path)


def canonical_config(toy: dict[str, Path], output: Path) -> LessonBuilderConfig:
    return LessonBuilderConfig(
        event_data_path=toy["cpi"],
        gold_path=toy["gold"],
        output_path=output,
        release_calendar_path=str(build_institutional_calendar(output.parent)),
    )


# ── 1 / 2. composition reuse and output-path safety ────────────────────────


class TestCanonicalComposition:
    def test_reuses_existing_runtime_composition(
        self, toy: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called: dict[str, int] = {}
        ycfg = []
        dcfg = []

        def spy_register(extractor) -> None:
            called["register_global"] = called.get("register_global", 0) + 1
            assert isinstance(extractor, MacroRegimeFeatureExtractor)

        def spy_yield(self, lessons_path, output_path=None, _d=None):
            called["yield_enrich"] = called.get("yield_enrich", 0) + 1
            ycfg.append((self.config.yield_path, self.config.lookback_days))
            return _d

        def spy_dxy(self, lessons_path, output_path=None, _d=None):
            called["dxy_enrich"] = called.get("dxy_enrich", 0) + 1
            dcfg.append((self.config.dxy_path, self.config.lookback_days))
            return _d

        monkeypatch.setattr(FeatureExtractionEngine, "register_global", spy_register)
        monkeypatch.setattr(YieldContextEnricher, "enrich_csv", spy_yield)
        monkeypatch.setattr(DXYContextEnricher, "enrich_csv", spy_dxy)

        out = toy["cpi"].parent / "lessons.csv"
        build_canonical_lesson_artifact(
            canonical_config(toy, out),
            yield_data_path=toy["yield"],
            dxy_data_path=toy["dxy"],
        )

        assert called.get("register_global") == 1
        assert called.get("yield_enrich") == 1
        assert called.get("dxy_enrich") == 1
        assert ycfg == [(toy["yield"], 30)]
        assert dcfg == [(toy["dxy"], 30)]

    def test_explicit_output_path_prevents_inplace_ambiguity(
        self, toy: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ycalls = []
        dcalls = []

        def spy_yield(self, lessons_path, output_path=None):
            ycalls.append((Path(lessons_path), output_path))
            return YieldContextEnricher.enrich(self, pd.read_csv(lessons_path))

        def spy_dxy(self, lessons_path, output_path=None):
            dcalls.append((Path(lessons_path), output_path))
            return DXYContextEnricher.enrich(self, pd.read_csv(lessons_path))

        monkeypatch.setattr(YieldContextEnricher, "enrich_csv", spy_yield)
        monkeypatch.setattr(DXYContextEnricher, "enrich_csv", spy_dxy)

        out = toy["cpi"].parent / "lessons.csv"
        build_canonical_lesson_artifact(
            canonical_config(toy, out),
            yield_data_path=toy["yield"],
            dxy_data_path=toy["dxy"],
        )
        for (p, output_path) in ycalls + dcalls:
            assert output_path is not None
            assert p == out
            assert output_path == out


# ── 3 / 4 / 5. preservation and enrichment columns (toy build) ─────────────


class TestCanonicalArtifact:
    def _build(self, toy: dict[str, Path]) -> pd.DataFrame:
        out = toy["cpi"].parent / "lessons_enriched.csv"
        return build_canonical_lesson_artifact(
            canonical_config(toy, out),
            yield_data_path=toy["yield"],
            dxy_data_path=toy["dxy"],
        )

    def test_lesson_id_set_preserved_vs_plain_build(
        self, toy: dict[str, Path]
    ) -> None:
        plain = LessonBuilderConfig(
            event_data_path=toy["cpi"],
            gold_path=toy["gold"],
            output_path=toy["cpi"].parent / "lessons_plain.csv",
            release_calendar_path=str(
                build_institutional_calendar(toy["cpi"].parent)
            ),
        )
        plain_df = LessonBuilder(plain).build_and_save()
        enriched = self._build(toy)
        assert set(enriched["lesson_id"]) == set(plain_df["lesson_id"])

    def test_event_date_set_preserved(self, toy: dict[str, Path]) -> None:
        enriched = self._build(toy)
        assert enriched["event_date"].astype(str).tolist() == sorted(
            enriched["event_date"].astype(str).tolist()
        )
        assert enriched["lesson_id"].str.contains("CPI_GOLD_").all()

    def test_enrichment_columns_present(self, toy: dict[str, Path]) -> None:
        enriched = self._build(toy)
        for column in (
            "cpi_pressure",
            "us10y_level",
            "us10y_trend",
            "dxy_level",
            "dxy_trend",
            "macro_regime",
        ):
            assert column in enriched.columns
        assert enriched["us10y_trend"].isin(
            {"yields_rising", "yields_falling", "yields_flat"}
        ).all()
        assert enriched["dxy_trend"].isin(
            {"dxy_rising", "dxy_falling", "dxy_flat"}
        ).all()
        assert enriched["macro_regime"].isin(
            {EXPANSION, LATE_CYCLE, RECOVERY, CONTRACTION}
        ).all()

    def test_existing_lesson_return_statistics_unchanged(
        self, toy: dict[str, Path]
    ) -> None:
        plain = LessonBuilderConfig(
            event_data_path=toy["cpi"],
            gold_path=toy["gold"],
            output_path=toy["cpi"].parent / "lessons_plain.csv",
            release_calendar_path=str(
                build_institutional_calendar(toy["cpi"].parent)
            ),
        )
        plain_df = LessonBuilder(plain).build_and_save().sort_values("lesson_id")
        enriched = self._build(toy).sort_values("lesson_id")

        stale_columns = [
            c for c in plain_df.columns if c not in enriched.columns
        ]
        assert not stale_columns
        preserved = [
            c
            for c in enriched.columns
            if c
            not in {
                "us10y_value_at_event",
                "us10y_value_lookback",
                "us10y_change_bps",
                "us10y_level",
                "us10y_trend",
                "dxy_value_at_event",
                "dxy_value_lookback",
                "dxy_change",
                "dxy_level",
                "dxy_trend",
            }
        ]
        shared = [
            c for c in preserved if c in plain_df.columns
        ]
        for column in shared:
            assert enriched[column].astype(str).tolist() == (
                plain_df[column].astype(str).tolist()
            ), f"column drifted: {column}"


# ── 7. determinism ─────────────────────────────────────────────────────────


class TestDeterminism:
    def test_deterministic_rebuild(self, tmp_path: Path) -> None:
        a = toy_sources(tmp_path / "a")
        b = toy_sources(tmp_path / "b")
        build_a = build_canonical_lesson_artifact(
            canonical_config(a, a["cpi"].parent / "lessons.csv"),
            yield_data_path=a["yield"],
            dxy_data_path=a["dxy"],
        )
        build_b = build_canonical_lesson_artifact(
            canonical_config(b, b["cpi"].parent / "lessons.csv"),
            yield_data_path=b["yield"],
            dxy_data_path=b["dxy"],
        )
        # source_artifact_path embeds the tmp root; everything else must be
        # byte-identical across rebuilds.
        rows_a = [dict(r) for r in build_a.to_dict("records")]
        rows_b = [dict(r) for r in build_b.to_dict("records")]
        for rows in (rows_a, rows_b):
            for row in rows:
                row.pop("source_artifact_path", None)
        assert rows_a == rows_b


# ── 8 / 3 / 4. identity gate ───────────────────────────────────────────────


class TestReplacementGate:
    def _artifacts(
        self, tmp_path: Path
    ) -> tuple[Path, Path, Path]:
        current = tmp_path / "current.csv"
        candidate = tmp_path / "candidate.csv"
        other = tmp_path / "other.csv"
        write_csv(
            current,
            [
                {"lesson_id": "CPI_GOLD_2020-01-01", "event_date": "2020-01-01"},
                {"lesson_id": "CPI_GOLD_2020-02-01", "event_date": "2020-02-01"},
            ],
        )
        write_csv(
            candidate,
            [
                {"lesson_id": "CPI_GOLD_2020-01-01", "event_date": "2020-01-01"},
                {"lesson_id": "CPI_GOLD_2020-02-01", "event_date": "2020-02-01"},
            ],
        )
        write_csv(
            other,
            [
                {"lesson_id": "CPI_GOLD_2020-01-01", "event_date": "2020-01-01"},
                {"lesson_id": "CPI_GOLD_2020-02-01", "event_date": "2020-02-01"},
                {"lesson_id": "CPI_GOLD_2020-03-01", "event_date": "2020-03-01"},
            ],
        )
        return current, candidate, other

    def test_identical_sets_replace(self, tmp_path: Path) -> None:
        current, candidate, _ = self._artifacts(tmp_path)
        report = replace_canonical_after_gate(current, candidate)
        assert report["identity_set_match"] is True
        assert report["replaced"] is True
        assert report["added_lesson_ids"] == []
        assert report["removed_lesson_ids"] == []
        assert len(report["unchanged_lesson_ids"]) == 2

    def test_unexplained_row_drift_blocks_replacement(
        self, tmp_path: Path
    ) -> None:
        current, _, candidate = self._artifacts(tmp_path)
        before = current.read_bytes()
        report = replace_canonical_after_gate(current, candidate)
        assert report["identity_set_match"] is False
        assert report["replaced"] is False
        assert report["added_lesson_ids"] == ["CPI_GOLD_2020-03-01"]
        assert current.read_bytes() == before

    def test_removed_row_blocks_replacement(self, tmp_path: Path) -> None:
        current = tmp_path / "current.csv"
        candidate = tmp_path / "candidate.csv"
        write_csv(
            current,
            [
                {"lesson_id": "A", "event_date": "2020-01-01"},
                {"lesson_id": "B", "event_date": "2020-02-01"},
            ],
        )
        write_csv(
            candidate,
            [{"lesson_id": "A", "event_date": "2020-01-01"}],
        )
        report = replace_canonical_after_gate(current, candidate)
        assert report["removed_lesson_ids"] == ["B"]
        assert report["replaced"] is False

    def test_event_date_drift_blocks_replacement(self, tmp_path: Path) -> None:
        current = tmp_path / "current.csv"
        candidate = tmp_path / "candidate.csv"
        write_csv(
            current,
            [{"lesson_id": "A", "event_date": "2020-01-01"}],
        )
        write_csv(
            candidate,
            [{"lesson_id": "A", "event_date": "2020-02-01"}],
        )
        report = replace_canonical_after_gate(current, candidate)
        assert report["event_date_drift_lesson_ids"] == ["A"]
        assert report["replaced"] is False


# ── 6 / 10. real-data coverage and regime mapping ──────────────────────────


def test_no_missing_trend_values_across_supported_range(tmp_path: Path) -> None:
    config = LessonBuilderConfig(
        event_data_path=REPO_ROOT / "data" / "economic" / "CPIAUCSL.csv",
        gold_path=REPO_ROOT / "data" / "history" / "gold" / "gold.csv",
        output_path=tmp_path / "lessons_enriched.csv",
        release_calendar_path=str(
            REPO_ROOT / "data" / "calendar" / "cpi_releases.csv"
        ),
    )
    enriched = build_canonical_lesson_artifact(
        config,
        yield_data_path=DEFAULT_YIELD_DATA_PATH,
        dxy_data_path=DEFAULT_DXY_DATA_PATH,
    )
    assert len(enriched) >= 100
    assert not enriched["us10y_trend"].astype(str).str.startswith("missing").any()
    assert not enriched["dxy_trend"].astype(str).str.startswith("missing").any()
    assert not enriched["macro_regime"].astype(str).isin(
        {"UNKNOWN", "nan"}
    ).any()


def test_regime_mapping_unchanged() -> None:
    assert ECONOMIC_REGIME_LABELS == {
        EXPANSION: "NORMAL_GROWTH",
        LATE_CYCLE: "INFLATIONARY",
        RECOVERY: "STAGFLATIONARY",
        CONTRACTION: "DEFLATIONARY_CRISIS",
    }
    from knowledge.temporal.lesson_index import row_to_lesson_state

    import pandas as pd

    state = row_to_lesson_state(
        pd.Series(
            {
                "lesson_id": "CPI_GOLD_2020-01-01",
                "event_date": "2020-01-01",
                "cpi_pressure": "inflation_pressure_up",
                "macro_regime": LATE_CYCLE,
            }
        )
    )
    assert state.metadata["regime"] == "INFLATIONARY"