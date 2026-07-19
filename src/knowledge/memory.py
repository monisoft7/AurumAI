import json
from pathlib import Path
from typing import Any

from knowledge._compat import locked_write_json, atomic_write_json


class Memory:

    def __init__(self, path: Path | str = "data/memory/memory.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():
            atomic_write_json(self.path, {})

    def load(self) -> dict[str, Any]:
        return json.loads(self.path.read_text())

    def save(self, data: dict[str, Any]) -> None:
        locked_write_json(self.path, data)

    def add(self, key: str, value: Any) -> None:
        data = self.load()
        data[key] = value
        self.save(data)

    def set_namespace(self, namespace: str, value: Any) -> None:
        data = self.load()
        data[namespace] = value
        self.save(data)
