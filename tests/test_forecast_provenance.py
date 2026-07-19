import hashlib
import subprocess

import pandas as pd
import pytest

from forecasting.provenance import ForecastProvenance


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_data() -> pd.DataFrame:
    return pd.DataFrame({"ds": pd.date_range("2020-01-01", periods=3, freq="ME"), "y": [100.0, 102.0, 101.0]})


@pytest.fixture
def provenance() -> ForecastProvenance:
    return ForecastProvenance(
        source="MacroForecaster::AutoARIMA",
        model_version="AutoARIMA_v1",
        training_window="all",
        registry_version="registry_v3",
        git_commit="a1b2c3d4e5f6",
        data_hash="e4f5a6b7c8d9",
        created_at="2026-07-18T12:00:00Z",
    )


# ---------------------------------------------------------------------------
# Construction & immutability
# ---------------------------------------------------------------------------


class TestConstruction:

    def test_frozen_dataclass(self, provenance: ForecastProvenance) -> None:
        with pytest.raises(AttributeError):
            provenance.source = "other"  # type: ignore[misc]

    def test_all_fields_present(self, provenance: ForecastProvenance) -> None:
        assert provenance.source == "MacroForecaster::AutoARIMA"
        assert provenance.model_version == "AutoARIMA_v1"
        assert provenance.training_window == "all"
        assert provenance.registry_version == "registry_v3"
        assert provenance.git_commit == "a1b2c3d4e5f6"
        assert provenance.data_hash == "e4f5a6b7c8d9"
        assert provenance.created_at == "2026-07-18T12:00:00Z"


# ---------------------------------------------------------------------------
# git_commit resolution
# ---------------------------------------------------------------------------


class TestResolveGitCommit:

    def test_returns_commit_hash(self) -> None:
        commit = ForecastProvenance.resolve_git_commit()
        assert isinstance(commit, str)
        assert len(commit) > 0

    def test_returns_known_hash_in_git_repo(self) -> None:
        commit = ForecastProvenance.resolve_git_commit()
        expected = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, timeout=5
            )
            .decode("ascii")
            .strip()
        )
        assert commit == expected

    def test_fallback_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _mock_failure(*args: object, **kwargs: object) -> None:
            raise FileNotFoundError("git not found")

        monkeypatch.setattr(subprocess, "check_output", _mock_failure)
        assert ForecastProvenance.resolve_git_commit() == "unknown"


# ---------------------------------------------------------------------------
# data_hash computation
# ---------------------------------------------------------------------------


class TestComputeDataHash:

    def test_returns_hex_string(self, sample_data: pd.DataFrame) -> None:
        h = ForecastProvenance.compute_data_hash(sample_data)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest
        int(h, 16)  # valid hex

    def test_deterministic(self, sample_data: pd.DataFrame) -> None:
        h1 = ForecastProvenance.compute_data_hash(sample_data)
        h2 = ForecastProvenance.compute_data_hash(sample_data)
        assert h1 == h2

    def test_different_data_different_hash(self) -> None:
        d1 = pd.DataFrame({"ds": ["2020-01-01"], "y": [100.0]})
        d2 = pd.DataFrame({"ds": ["2020-01-01"], "y": [101.0]})
        h1 = ForecastProvenance.compute_data_hash(d1)
        h2 = ForecastProvenance.compute_data_hash(d2)
        assert h1 != h2

    def test_column_order_independent(self) -> None:
        d1 = pd.DataFrame({"a": [1], "b": [2]})
        d2 = pd.DataFrame({"b": [2], "a": [1]})
        h1 = ForecastProvenance.compute_data_hash(d1)
        h2 = ForecastProvenance.compute_data_hash(d2)
        assert h1 == h2

    def test_matches_direct_sha256(self, sample_data: pd.DataFrame) -> None:
        canonical = sample_data.sort_index(axis=1)
        for col in canonical.select_dtypes(include="datetime64").columns:
            canonical[col] = canonical[col].astype(str)
        expected = hashlib.sha256(
            canonical.to_csv(index=False).encode("utf-8")
        ).hexdigest()
        assert ForecastProvenance.compute_data_hash(sample_data) == expected


# ---------------------------------------------------------------------------
# Serialization: to_dict
# ---------------------------------------------------------------------------


class TestToDict:

    def test_returns_dict_with_all_keys(self, provenance: ForecastProvenance) -> None:
        d = provenance.to_dict()
        assert isinstance(d, dict)
        expected_keys = {
            "source", "model_version", "training_window",
            "registry_version", "git_commit", "data_hash", "created_at",
        }
        assert set(d) == expected_keys

    def test_values_match_fields(self, provenance: ForecastProvenance) -> None:
        d = provenance.to_dict()
        assert d["source"] == provenance.source
        assert d["model_version"] == provenance.model_version
        assert d["training_window"] == provenance.training_window
        assert d["registry_version"] == provenance.registry_version
        assert d["git_commit"] == provenance.git_commit
        assert d["data_hash"] == provenance.data_hash
        assert d["created_at"] == provenance.created_at


# ---------------------------------------------------------------------------
# Serialization: from_dict round-trip
# ---------------------------------------------------------------------------


class TestFromDict:

    def test_round_trip(self, provenance: ForecastProvenance) -> None:
        d = provenance.to_dict()
        restored = ForecastProvenance.from_dict(d)
        assert restored == provenance

    def test_from_dict_all_fields(self) -> None:
        data = {
            "source": "AutoETS_v2",
            "model_version": "AutoETS_v2",
            "training_window": "36M",
            "registry_version": "registry_v5",
            "git_commit": "abc123",
            "data_hash": "deadbeef",
            "created_at": "2026-07-18T00:00:00Z",
        }
        p = ForecastProvenance.from_dict(data)
        assert p.source == "AutoETS_v2"
        assert p.model_version == "AutoETS_v2"
        assert p.training_window == "36M"
        assert p.registry_version == "registry_v5"
        assert p.git_commit == "abc123"
        assert p.data_hash == "deadbeef"
        assert p.created_at == "2026-07-18T00:00:00Z"

    def test_from_dict_string_coercion(self) -> None:
        data = {
            "source": 123,
            "model_version": True,
            "training_window": None,
            "registry_version": 4.5,
            "git_commit": b"bytes",
            "data_hash": 0,
            "created_at": 42,
        }
        p = ForecastProvenance.from_dict(data)
        assert isinstance(p.source, str)
        assert isinstance(p.model_version, str)
        assert isinstance(p.training_window, str)
        assert isinstance(p.registry_version, str)
        assert isinstance(p.git_commit, str)
        assert isinstance(p.data_hash, str)
        assert isinstance(p.created_at, str)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:

    def test_empty_data_hash(self) -> None:
        empty = pd.DataFrame({"ds": pd.Series(dtype="datetime64[ns]"), "y": pd.Series(dtype="float64")})
        h = ForecastProvenance.compute_data_hash(empty)
        assert isinstance(h, str)
        assert len(h) == 64

    def test_single_row_data(self) -> None:
        single = pd.DataFrame({"ds": ["2024-01-01"], "y": [150.0]})
        h = ForecastProvenance.compute_data_hash(single)
        assert isinstance(h, str)
        assert len(h) == 64

    def test_data_hash_with_datetime_col(self) -> None:
        df = pd.DataFrame({"ds": pd.to_datetime(["2024-01-01", "2024-02-01"]), "y": [1.0, 2.0]})
        h = ForecastProvenance.compute_data_hash(df)
        assert isinstance(h, str)
        assert len(h) == 64
