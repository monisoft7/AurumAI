import pytest

from forecasting.registry import (
    DuplicateRegistrationError,
    ForecastModelSpec,
    ForecastRegistry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(
    name: str = "test_v1",
    target: str = "CPI",
    status: str = "approved",
) -> ForecastModelSpec:
    return ForecastModelSpec(
        name=name,
        model_cls=str,
        model_kwargs={"season_length": 12},
        target_variable=target,
        freq="ME",
        default_horizon=12,
        max_horizon=24,
        training_window="all",
        validation_strategy="expanding_window",
        validation_split=0.2,
        approval_status=status,
        approved_by="system",
        approval_date="2026-07-18",
        description=f"{name} spec",
    )


@pytest.fixture(autouse=True)
def _fresh_registry() -> None:
    ForecastRegistry._reset()


# ---------------------------------------------------------------------------
# ForecastModelSpec
# ---------------------------------------------------------------------------


class TestForecastModelSpec:

    def test_frozen_dataclass(self) -> None:
        spec = _make_spec()
        with pytest.raises(AttributeError):
            spec.name = "other"  # type: ignore[misc]

    def test_all_fields(self) -> None:
        spec = _make_spec()
        assert spec.name == "test_v1"
        assert spec.model_cls is str
        assert spec.model_kwargs == {"season_length": 12}
        assert spec.target_variable == "CPI"
        assert spec.freq == "ME"
        assert spec.default_horizon == 12
        assert spec.max_horizon == 24
        assert spec.training_window == "all"
        assert spec.validation_strategy == "expanding_window"
        assert spec.validation_split == 0.2
        assert spec.approval_status == "approved"
        assert spec.approved_by == "system"
        assert spec.approval_date == "2026-07-18"
        assert spec.description == "test_v1 spec"

    def test_str_fields_accept_none(self) -> None:
        spec = ForecastModelSpec(
            name="unreviewed",
            model_cls=str,
            model_kwargs={},
            target_variable="GOLD",
            freq="ME",
            default_horizon=6,
            max_horizon=12,
            training_window="all",
            validation_strategy="fixed_window",
            validation_split=0.3,
            approval_status="draft",
            approved_by=None,
            approval_date=None,
            description="Unreviewed spec",
        )
        assert spec.approved_by is None
        assert spec.approval_date is None


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegister:

    def test_register_spec(self) -> None:
        spec = _make_spec()
        ForecastRegistry.register(spec)
        assert ForecastRegistry.is_registered("test_v1")

    def test_register_rejects_non_spec(self) -> None:
        with pytest.raises(TypeError, match="not a ForecastModelSpec"):
            ForecastRegistry.register("not_a_spec")  # type: ignore[arg-type]

    def test_register_rejects_empty_name(self) -> None:
        spec = _make_spec(name="")
        with pytest.raises(ValueError, match="non-empty string"):
            ForecastRegistry.register(spec)

    def test_register_rejects_none_name(self) -> None:
        spec = _make_spec(name="x")
        spec2 = ForecastModelSpec(
            name="",
            model_cls=spec.model_cls,
            model_kwargs=spec.model_kwargs,
            target_variable=spec.target_variable,
            freq=spec.freq,
            default_horizon=spec.default_horizon,
            max_horizon=spec.max_horizon,
            training_window=spec.training_window,
            validation_strategy=spec.validation_strategy,
            validation_split=spec.validation_split,
            approval_status=spec.approval_status,
            approved_by=spec.approved_by,
            approval_date=spec.approval_date,
            description=spec.description,
        )
        with pytest.raises(ValueError, match="non-empty string"):
            ForecastRegistry.register(spec2)

    def test_register_multiple_specs(self) -> None:
        ForecastRegistry.register(_make_spec(name="v1"))
        ForecastRegistry.register(_make_spec(name="v2"))
        assert ForecastRegistry.list() == ["v1", "v2"]


# ---------------------------------------------------------------------------
# Duplicate prevention
# ---------------------------------------------------------------------------


class TestDuplicatePrevention:

    def test_duplicate_raises_error(self) -> None:
        ForecastRegistry.register(_make_spec(name="dup"))
        with pytest.raises(DuplicateRegistrationError, match="dup"):
            ForecastRegistry.register(_make_spec(name="dup"))

    def test_duplicate_with_replace(self) -> None:
        spec_a = _make_spec(name="dup", target="CPI")
        spec_b = _make_spec(name="dup", target="NFP")
        ForecastRegistry.register(spec_a)
        ForecastRegistry.register(spec_b, replace=True)
        assert ForecastRegistry.get("dup").target_variable == "NFP"

    def test_duplicate_error_message(self) -> None:
        ForecastRegistry.register(_make_spec(name="my_model"))
        with pytest.raises(DuplicateRegistrationError) as exc:
            ForecastRegistry.register(_make_spec(name="my_model"))
        assert "my_model" in str(exc.value)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


class TestGet:

    def test_get_returns_spec(self) -> None:
        spec = _make_spec(name="gold_v1")
        ForecastRegistry.register(spec)
        assert ForecastRegistry.get("gold_v1") is spec

    def test_get_returns_none_for_unknown(self) -> None:
        assert ForecastRegistry.get("nonexistent") is None


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


class TestList:

    def test_list_empty(self) -> None:
        assert ForecastRegistry.list() == []

    def test_list_sorted(self) -> None:
        ForecastRegistry.register(_make_spec(name="z"))
        ForecastRegistry.register(_make_spec(name="a"))
        ForecastRegistry.register(_make_spec(name="m"))
        assert ForecastRegistry.list() == ["a", "m", "z"]


# ---------------------------------------------------------------------------
# is_registered
# ---------------------------------------------------------------------------


class TestIsRegistered:

    def test_true_when_registered(self) -> None:
        ForecastRegistry.register(_make_spec(name="cpi_v2"))
        assert ForecastRegistry.is_registered("cpi_v2")

    def test_false_when_not_registered(self) -> None:
        assert not ForecastRegistry.is_registered("nonexistent")


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------


class TestClear:

    def test_clears_all(self) -> None:
        ForecastRegistry.register(_make_spec(name="a"))
        ForecastRegistry.register(_make_spec(name="b"))
        ForecastRegistry.clear()
        assert ForecastRegistry.list() == []

    def test_is_idempotent(self) -> None:
        ForecastRegistry.clear()
        ForecastRegistry.clear()
        assert ForecastRegistry.list() == []


# ---------------------------------------------------------------------------
# for_target
# ---------------------------------------------------------------------------


class TestForTarget:

    def test_returns_matching_specs(self) -> None:
        ForecastRegistry.register(_make_spec(name="cpi_v1", target="CPI"))
        ForecastRegistry.register(_make_spec(name="nfp_v1", target="NFP"))
        ForecastRegistry.register(_make_spec(name="cpi_v2", target="CPI"))
        results = ForecastRegistry.for_target("CPI")
        assert [s.name for s in results] == ["cpi_v1", "cpi_v2"]

    def test_empty_when_no_match(self) -> None:
        ForecastRegistry.register(_make_spec(name="cpi_v1", target="CPI"))
        assert ForecastRegistry.for_target("NFP") == []

    def test_sorted_by_name(self) -> None:
        ForecastRegistry.register(_make_spec(name="z_cpi", target="CPI"))
        ForecastRegistry.register(_make_spec(name="a_cpi", target="CPI"))
        assert [s.name for s in ForecastRegistry.for_target("CPI")] == ["a_cpi", "z_cpi"]


# ---------------------------------------------------------------------------
# approved_only
# ---------------------------------------------------------------------------


class TestApprovedOnly:

    def test_returns_approved_only(self) -> None:
        ForecastRegistry.register(_make_spec(name="v1", status="approved"))
        ForecastRegistry.register(_make_spec(name="v2", status="draft"))
        ForecastRegistry.register(_make_spec(name="v3", status="deprecated"))
        results = ForecastRegistry.approved_only()
        assert [s.name for s in results] == ["v1"]

    def test_empty_when_no_approved(self) -> None:
        ForecastRegistry.register(_make_spec(name="draft_v1", status="draft"))
        assert ForecastRegistry.approved_only() == []

    def test_sorted_by_name(self) -> None:
        ForecastRegistry.register(_make_spec(name="z_approved", status="approved"))
        ForecastRegistry.register(_make_spec(name="a_approved", status="approved"))
        assert [s.name for s in ForecastRegistry.approved_only()] == ["a_approved", "z_approved"]


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


class TestVersion:

    def test_starts_at_zero(self) -> None:
        assert ForecastRegistry.version() == 0

    def test_increments_on_register(self) -> None:
        v0 = ForecastRegistry.version()
        ForecastRegistry.register(_make_spec(name="v1"))
        assert ForecastRegistry.version() == v0 + 1
        ForecastRegistry.register(_make_spec(name="v2"))
        assert ForecastRegistry.version() == v0 + 2

    def test_increments_on_clear(self) -> None:
        ForecastRegistry._reset()
        ForecastRegistry.register(_make_spec(name="v1"))
        v_before = ForecastRegistry.version()
        ForecastRegistry.clear()
        assert ForecastRegistry.version() == v_before + 1

    def test_reset_returns_to_zero(self) -> None:
        ForecastRegistry.register(_make_spec(name="v1"))
        ForecastRegistry._reset()
        assert ForecastRegistry.version() == 0
        assert ForecastRegistry.list() == []

    def test_does_not_increment_on_replace(self) -> None:
        ForecastRegistry.register(_make_spec(name="dup"))
        v1 = ForecastRegistry.version()
        ForecastRegistry.register(_make_spec(name="dup"), replace=True)
        assert ForecastRegistry.version() == v1 + 1  # still increments (content changed)
