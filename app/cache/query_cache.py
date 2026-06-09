from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from threading import Lock
from typing import Any

from app.config import settings
from app.models import CubeQuery, CubeQueryResult


class QueryCache:
    def __init__(self, max_size: int | None = None, ttl_seconds: int | None = None):
        self.max_size = max_size or settings.cache_max_size
        self.ttl = ttl_seconds or settings.cache_ttl_seconds
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(cube_name: str, query: CubeQuery, extra: str = "") -> str:
        query_dict = query.model_dump()
        raw = json.dumps(
            {"cube": cube_name, "query": query_dict, "extra": extra},
            sort_keys=True,
            default=str,
        )
        hash_hex = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"{cube_name}:{hash_hex}"

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            value, timestamp = self._cache[key]
            if time.time() - timestamp > self.ttl:
                del self._cache[key]
                self._misses += 1
                return None
            self._cache.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, time.time())
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def invalidate_all(self) -> None:
        with self._lock:
            self._cache.clear()

    def invalidate_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [k for k in self._cache if k.startswith(prefix)]
            for k in keys:
                del self._cache[k]
            return len(keys)

    def invalidate_cube(self, cube_name: str) -> int:
        return self.invalidate_prefix(cube_name + ":")

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    @property
    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 4) if total > 0 else 0.0,
            }

    def reset_stats(self) -> None:
        with self._lock:
            self._hits = 0
            self._misses = 0


query_cache = QueryCache()
