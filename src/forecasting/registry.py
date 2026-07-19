from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class DuplicateRegistrationError(Exception):
    """Raised when attempting to register a ForecastModelSpec whose
    *name* is already registered in this registry."""


@dataclass(frozen=True)
class ForecastModelSpec:
    name: str
    model_cls: type
    model_kwargs: dict[str, Any]
    target_variable: str
    freq: str
    default_horizon: int
    max_horizon: int
    training_window: str
    validation_strategy: str
    validation_split: float
    approval_status: str
    approved_by: str | None
    approval_date: str | None
    description: str


class ForecastRegistry:
    """Lightweight registry for ``ForecastModelSpec`` instances.

    Maps *name* string -> ForecastModelSpec.
    Follows the same design philosophy as ``EventRegistry``.
    """

    _specs: dict[str, ForecastModelSpec] = {}
    _version: int = 0

    @classmethod
    def register(
        cls,
        spec: ForecastModelSpec,
        *,
        replace: bool = False,
    ) -> None:
        if not isinstance(spec, ForecastModelSpec):
            raise TypeError(
                f"{type(spec).__name__} is not a ForecastModelSpec"
            )

        if not spec.name or not isinstance(spec.name, str):
            raise ValueError(
                f"spec.name must be a non-empty string, got {spec.name!r}"
            )

        if not replace and spec.name in cls._specs:
            raise DuplicateRegistrationError(
                f"Model {spec.name!r} is already registered. "
                "Use replace=True to override."
            )

        cls._specs[spec.name] = spec
        cls._version += 1

    @classmethod
    def get(cls, name: str) -> ForecastModelSpec | None:
        return cls._specs.get(name)

    @classmethod
    def list(cls) -> list[str]:
        return sorted(cls._specs.keys())

    @classmethod
    def clear(cls) -> None:
        cls._specs.clear()
        cls._version += 1

    @classmethod
    def _reset(cls) -> None:
        """Reset registry to initial empty state (for testing)."""
        cls._specs.clear()
        cls._version = 0

    @classmethod
    def is_registered(cls, name: str) -> bool:
        return name in cls._specs

    @classmethod
    def for_target(cls, target: str) -> list[ForecastModelSpec]:
        return sorted(
            (s for s in cls._specs.values() if s.target_variable == target),
            key=lambda s: s.name,
        )

    @classmethod
    def approved_only(cls) -> list[ForecastModelSpec]:
        return sorted(
            (s for s in cls._specs.values() if s.approval_status == "approved"),
            key=lambda s: s.name,
        )

    @classmethod
    def version(cls) -> int:
        """Current registry version. Incremented on every mutation."""
        return cls._version
