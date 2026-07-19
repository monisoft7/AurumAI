from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class FrozenDict(dict):
    """An immutable dict that is JSON-serializable and preserves dict API."""

    def __setitem__(self, key: Any, value: Any) -> None:
        raise TypeError("FrozenDict is immutable")

    def __delitem__(self, key: Any) -> None:
        raise TypeError("FrozenDict is immutable")

    def clear(self) -> None:
        raise TypeError("FrozenDict is immutable")

    def pop(self, key: Any, default: Any = None) -> Any:
        raise TypeError("FrozenDict is immutable")

    def popitem(self) -> tuple[Any, Any]:
        raise TypeError("FrozenDict is immutable")

    def update(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("FrozenDict is immutable")

    def __copy__(self) -> FrozenDict:
        return FrozenDict(self)

    def copy(self) -> FrozenDict:
        return FrozenDict(self)


def freeze_dict(d: dict[str, Any] | None = None) -> FrozenDict:
    if d is None or isinstance(d, FrozenDict):
        return d or FrozenDict()
    return FrozenDict(dict(d))


def atomic_write_json(path: Path, payload: Any, indent: int = 2, default: Any | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    kwargs: dict[str, Any] = {"indent": indent}
    if default is not None:
        kwargs["default"] = default
    data = json.dumps(payload, **kwargs)
    tmp_path.write_text(data, encoding="utf-8")
    tmp_path.replace(path)


def locked_write_json(path: Path, payload: Any, indent: int = 2, default: Any | None = None) -> None:
    """Locked variant — falls back to atomic write on unsupported platforms."""
    atomic_write_json(path, payload, indent=indent, default=default)
