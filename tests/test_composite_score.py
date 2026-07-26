from pathlib import Path

import pandas as pd

from knowledge.regime.composite_score import CompositeScoreBuilder


def _write_indicator_csv(dir_path: Path, filename: str, dates: list[str], values: list[float]) -> Path:
    path = dir_path / filename
    df = pd.DataFrame({"Date": pd.to_datetime(dates), "Value": values})
    df.to_csv(path, index=False)
    return path


def test_build_returns_expected_columns(tmp_path: Path) -> None:
    dates = pd.date_range("2000-01-01", periods=180, freq="ME").strftime("%Y-%m-%d").tolist()
    rng = __import__("numpy").random.default_rng(42)
    _write_indicator_csv(tmp_path, "CPIAUCSL.csv", dates, (100.0 + rng.normal(0, 2, len(dates))).tolist())
    _write_indicator_csv(tmp_path, "PPIACO.csv", dates, (50.0 + rng.normal(0, 2, len(dates))).tolist())
    _write_indicator_csv(tmp_path, "PMI.csv", dates[-60:], (52.0 + rng.normal(0, 3, 60)).tolist())
    _write_indicator_csv(tmp_path, "UNRATE.csv", dates, (5.0 + rng.normal(0, 0.5, len(dates))).tolist())
    _write_indicator_csv(tmp_path, "PAYEMS.csv", dates, (100000.0 + rng.normal(0, 1000, len(dates))).tolist())

    builder = CompositeScoreBuilder(tmp_path)
    result = builder.build()

    assert list(result.columns) == ["Date", "composite_score"]
    assert len(result) > 0
    assert result["composite_score"].dtype == "float64"
    assert not result["composite_score"].isna().any()


def test_build_deterministic(tmp_path: Path) -> None:
    dates = [f"{y}-01-01" for y in range(2000, 2020)]
    _write_indicator_csv(tmp_path, "CPIAUCSL.csv", dates, [100.0 + i * 0.5 for i in range(len(dates))])
    _write_indicator_csv(tmp_path, "UNRATE.csv", dates, [5.0] * len(dates))

    builder = CompositeScoreBuilder(tmp_path)
    r1 = builder.build()
    r2 = builder.build()

    pd.testing.assert_frame_equal(r1, r2)


def test_build_empty_when_no_files(tmp_path: Path) -> None:
    builder = CompositeScoreBuilder(tmp_path)
    result = builder.build()
    assert list(result.columns) == ["Date", "composite_score"]
    assert len(result) == 0


def test_build_partial_data(tmp_path: Path) -> None:
    dates = [f"{y}-01-01" for y in range(2000, 2020)]
    _write_indicator_csv(tmp_path, "CPIAUCSL.csv", dates, [100.0 + i * 0.5 for i in range(len(dates))])

    builder = CompositeScoreBuilder(tmp_path)
    result = builder.build()
    assert len(result) > 0
    assert "composite_score" in result.columns


def test_build_z_score_produces_zero_mean(tmp_path: Path) -> None:
    rng = __import__("numpy").random.default_rng(42)
    dates = pd.date_range("2000-01-01", periods=180, freq="ME").strftime("%Y-%m-%d").tolist()
    _write_indicator_csv(tmp_path, "CPIAUCSL.csv", dates, (100.0 + rng.normal(0, 3, len(dates))).tolist())
    _write_indicator_csv(tmp_path, "UNRATE.csv", dates, (5.0 + rng.normal(0, 0.5, len(dates))).tolist())

    builder = CompositeScoreBuilder(tmp_path)
    result = builder.build()

    assert abs(result["composite_score"].mean()) < 0.15
    assert result["composite_score"].std() > 0.3  # non-trivial variation


def test_cpi_pct_change_compounded(tmp_path: Path) -> None:
    dates = [f"{y}-01-01" for y in range(2000, 2020)]
    values = [100.0 * (1.02 ** i) for i in range(len(dates))]
    _write_indicator_csv(tmp_path, "CPIAUCSL.csv", dates, values)
    _write_indicator_csv(tmp_path, "UNRATE.csv", dates, [5.0] * len(dates))

    builder = CompositeScoreBuilder(tmp_path)
    result = builder.build()
    assert len(result) > 0
    assert not result["composite_score"].isna().any()
