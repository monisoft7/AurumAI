from __future__ import annotations

import threading
import time
from typing import Any

_CacheValue = tuple[float, Any]


class CacheManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[str, _CacheValue] = {}
        self._hit_count = 0

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires, value = item
            if expires is not None and time.monotonic() > expires:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expires = None if ttl is None else time.monotonic() + ttl
        with self._lock:
            self._store[key] = (expires, value)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear_expired(self) -> int:
        now = time.monotonic()
        removed = 0
        with self._lock:
            for k in list(self._store.keys()):
                expires, _ = self._store[k]
                if expires is not None and now > expires:
                    del self._store[k]
                    removed += 1
        return removed

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)

    def inc_hit(self) -> None:
        self._hit_count += 1

    @property
    def hits(self) -> int:
        return self._hit_count
