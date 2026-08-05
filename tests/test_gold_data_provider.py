from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from connectors.gold_data_provider import GoldDataProvider, SCHEMA_COLUMNS


def _frame(dates: list[str], closes: list[float] | None = None) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for i, date in enumerate(dates):
        close = closes[i] if closes is not None else 100.0 + i
        rows.append({
            "Date": date,
            "Open": close,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": 1000,
        })
    return pd.DataFrame(rows, columns=list(SCHEMA_COLUMNS))


def _write_local(path: Path, dates: list[str], closes: list[float] | None = None) -> None:
    _frame(dates, closes).to_csv(path, index=False)


def _remote_dates(local: pd.DataFrame, extra: list[str]) -> list[str]:
    return list(local["Date"]) + extra


def test_successful_update(tmp_path: Path) -> None:
    path = tmp_path / "gold.csv"
    _write_local(path, ["2025-12-29", "2025-12-30", "2025-12-31"])
    remote = _frame([
        "2025-12-29", "2025-12-30", "2025-12-31", "2026-01-02", "2026-01-05",
    ])

    report = GoldDataProvider(path=path, fetcher=lambda: remote).refresh()

    assert report.status == "ok"
    assert report.rows_before == 3
    assert report.rows_after == 5
    assert report.rows_added == 2
    assert report.last_date_before == "2025-12-31"
    assert report.last_date_after == "2026-01-05"

    written = pd.read_csv(path)
    assert len(written) == 5
    assert list(written["Date"]) == [
        "2025-12-29", "2025-12-30", "2025-12-31", "2026-01-02", "2026-01-05",
    ]
    assert path.with_name(path.name + ".bak").exists()
    bak = pd.read_csv(path.with_name(path.name + ".bak"))
    assert len(bak) == 3


def test_no_new_market_data(tmp_path: Path) -> None:
    path = tmp_path / "gold.csv"
    dates = ["2025-12-29", "2025-12-30", "2025-12-31"]
    _write_local(path, dates)
    before = path.read_bytes()
    remote = _frame(dates)

    report = GoldDataProvider(path=path, fetcher=lambda: remote).refresh()

    assert report.status == "ok"
    assert report.rows_added == 0
    assert report.rows_after == report.rows_before
    assert report.last_date_after == "2025-12-31"
    assert path.read_bytes() == before


def test_duplicate_dates_in_remote_deduped(tmp_path: Path) -> None:
    path = tmp_path / "gold.csv"
    _write_local(path, ["2025-12-30", "2025-12-31"])
    remote = pd.concat([
        _frame(["2025-12-30", "2025-12-31", "2026-01-02"]),
        _frame(["2026-01-02"]),
    ], ignore_index=True)

    report = GoldDataProvider(path=path, fetcher=lambda: remote).refresh()

    assert report.status == "ok"
    assert report.rows_added == 1
    written = pd.read_csv(path)
    assert len(written) == 3
    assert not written["Date"].duplicated().any()


def test_truncated_download_never_shrinks(tmp_path: Path) -> None:
    path = tmp_path / "gold.csv"
    dates = ["2025-12-29", "2025-12-30", "2025-12-31", "2026-01-02", "2026-01-05"]
    _write_local(path, dates)
    before = path.read_bytes()
    remote = _frame(dates[:2])

    report = GoldDataProvider(path=path, fetcher=lambda: remote).refresh()

    assert report.status == "ok"
    assert report.rows_added == 0
    assert report.rows_before == 5
    assert report.rows_after == 5
    assert report.last_date_after == "2026-01-05"
    assert path.read_bytes() == before


def test_network_failure_keeps_dataset(tmp_path: Path) -> None:
    path = tmp_path / "gold.csv"
    dates = ["2025-12-29", "2025-12-30", "2025-12-31"]
    _write_local(path, dates)
    before = path.read_bytes()

    def _boom() -> pd.DataFrame:
        raise RuntimeError("network down")

    report = GoldDataProvider(path=path, fetcher=_boom).refresh()

    assert report.status == "skipped"
    assert report.rows_before == report.rows_after
    assert report.rows_added == 0
    assert path.read_bytes() == before


def test_empty_payload_skips_and_keeps_dataset(tmp_path: Path) -> None:
    path = tmp_path / "gold.csv"
    dates = ["2025-12-29", "2025-12-30", "2025-12-31"]
    _write_local(path, dates)
    before = path.read_bytes()

    report = GoldDataProvider(path=path, fetcher=lambda: pd.DataFrame()).refresh()

    assert report.status == "skipped"
    assert path.read_bytes() == before


def test_validation_failure_keeps_dataset(tmp_path: Path) -> None:
    path = tmp_path / "gold.csv"
    _write_local(path, ["2025-12-29", "2025-12-30", "2025-12-31"])
    before = path.read_bytes()

    invalid = _frame(["2025-12-29", "2025-12-30", "2025-12-31", "2026-01-02"])
    invalid.loc[invalid["Date"] == "2026-01-02", "High"] = 1.0  # High < Close

    report = GoldDataProvider(path=path, fetcher=lambda: invalid).refresh()

    assert report.status == "failed"
    assert report.rows_added == 0
    assert report.rows_after == report.rows_before
    assert path.read_bytes() == before
    assert not path.with_name(path.name + ".tmp").exists()


def test_bootstrap_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "gold.csv"
    assert not path.exists()

    remote = _frame(["2025-12-30", "2025-12-31", "2026-01-02"])

    report = GoldDataProvider(path=path, fetcher=lambda: remote).refresh()

    assert report.status == "ok"
    assert report.rows_before == 0
    assert report.rows_after == 3
    written = pd.read_csv(path)
    assert len(written) == 3
    assert written["Date"].is_monotonic_increasing


def test_pre_start_remote_rows_never_prepended(tmp_path: Path) -> None:
    path = tmp_path / "gold.csv"
    _write_local(path, ["2015-01-02", "2015-01-05", "2015-01-06"])
    before = path.read_bytes()
    remote = _frame([
        "2000-08-30", "2000-08-31", "2015-01-02", "2015-01-05",
        "2015-01-06", "2015-01-07",
    ])

    report = GoldDataProvider(path=path, fetcher=lambda: remote).refresh()

    assert report.status == "ok"
    assert report.rows_added == 1
    written = pd.read_csv(path)
    assert list(written["Date"]) == [
        "2015-01-02", "2015-01-05", "2015-01-06", "2015-01-07",
    ]
    assert written["Date"].iloc[0] == "2015-01-02"


def test_internal_gap_backfill(tmp_path: Path) -> None:
    path = tmp_path / "gold.csv"
    _write_local(path, ["2015-01-02", "2015-01-05"])
    remote = _frame([
        "2015-01-02", "2015-01-05", "2015-01-06", "2026-01-02",
    ])

    report = GoldDataProvider(path=path, fetcher=lambda: remote).refresh()

    assert report.status == "ok"
    assert report.rows_added == 2
    written = pd.read_csv(path)
    assert list(written["Date"]) == [
        "2015-01-02", "2015-01-05", "2015-01-06", "2026-01-02",
    ]


def test_report_to_dict(tmp_path: Path) -> None:
    path = tmp_path / "gold.csv"
    _write_local(path, ["2025-12-31"])
    report = GoldDataProvider(
        path=path, fetcher=lambda: _frame(["2025-12-31", "2026-01-02"]),
    ).refresh()

    payload = report.to_dict()

    assert payload["status"] == "ok"
    assert payload["rows_before"] == 1
    assert payload["rows_after"] == 2
    assert payload["last_date_after"] == "2026-01-02"
    assert payload["source"].startswith("yfinance:")
