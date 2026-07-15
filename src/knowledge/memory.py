import json
from pathlib import Path
from typing import Any


class Memory:

    def __init__(self, path: Path | str = "data/memory/memory.json"):

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():

            self.path.write_text("{}")

    def load(self) -> dict[str, Any]:

        return json.loads(self.path.read_text())

    def save(self, data: dict[str, Any]) -> None:

        self.path.write_text(json.dumps(data, indent=4, sort_keys=True))

    def add(self, key: str, value: Any) -> None:

        data = self.load()

        data[key] = value

        self.save(data)

    def set_namespace(self, namespace: str, value: Any) -> None:
        data = self.load()
        data[namespace] = value
        self.save(data)
