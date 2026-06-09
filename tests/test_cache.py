from __future__ import annotations

import time

import pytest

from app.cache.query_cache import QueryCache
from app.models import CubeQuery


class TestQueryCache:
    def test_set_and_get(self):
        cache = QueryCache(max_size=10, ttl_seconds=60)
        query = CubeQuery(dimensions=["region"], measures=["sales"])
        key = cache._make_key("sales", query)
        value = {"data": [1, 2, 3]}

        cache.set(key, value)
        result = cache.get(key)

        assert result == value
        assert cache.size == 1

    def test_get_miss(self):
        cache = QueryCache(max_size=10, ttl_seconds=60)
        result = cache.get("nonexistent_key")
        assert result is None

    def test_ttl_expiry(self):
        cache = QueryCache(max_size=10, ttl_seconds=1)
        key = "test_key"
        cache.set(key, "value")

        assert cache.get(key) == "value"
        time.sleep(1.1)
        assert cache.get(key) is None

    def test_lru_eviction(self):
        cache = QueryCache(max_size=3, ttl_seconds=60)
        for i in range(5):
            cache.set(f"key_{i}", f"value_{i}")

        assert cache.size == 3
        assert cache.get("key_0") is None
        assert cache.get("key_1") is None
        assert cache.get("key_2") is not None
        assert cache.get("key_3") is not None
        assert cache.get("key_4") is not None

    def test_invalidate(self):
        cache = QueryCache(max_size=10, ttl_seconds=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.invalidate("key1")
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_invalidate_all(self):
        cache = QueryCache(max_size=10, ttl_seconds=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.invalidate_all()
        assert cache.size == 0

    def test_invalidate_prefix(self):
        cache = QueryCache(max_size=10, ttl_seconds=60)
        cache.set("sales:key1", "value1")
        cache.set("sales:key2", "value2")
        cache.set("users:key1", "value3")

        count = cache.invalidate_prefix("sales:")
        assert count == 2
        assert cache.size == 1
        assert cache.get("users:key1") == "value3"

    def test_invalidate_cube(self):
        cache = QueryCache(max_size=10, ttl_seconds=60)
        cache.set("sales:abc123", "value1")
        cache.set("sales:def456", "value2")
        cache.set("users:xyz789", "value3")

        count = cache.invalidate_cube("sales")
        assert count == 2
        assert cache.size == 1

    def test_hit_miss_stats(self):
        cache = QueryCache(max_size=10, ttl_seconds=60)
        cache.set("key1", "value1")

        cache.get("key1")
        cache.get("key1")
        cache.get("nonexistent")

        stats = cache.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert abs(stats["hit_rate"] - 2 / 3) < 0.001

    def test_make_key_consistent(self):
        cache = QueryCache()
        query1 = CubeQuery(dimensions=["region"], measures=["sales_amount"])
        query2 = CubeQuery(measures=["sales_amount"], dimensions=["region"])

        key1 = cache._make_key("sales", query1)
        key2 = cache._make_key("sales", query2)

        assert key1 == key2

    def test_make_key_different(self):
        cache = QueryCache()
        query1 = CubeQuery(dimensions=["region"], measures=["sales_amount"])
        query2 = CubeQuery(dimensions=["channel"], measures=["sales_amount"])

        key1 = cache._make_key("sales", query1)
        key2 = cache._make_key("sales", query2)

        assert key1 != key2

    def test_reset_stats(self):
        cache = QueryCache(max_size=10, ttl_seconds=60)
        cache.set("key1", "value1")
        cache.get("key1")
        cache.get("nonexistent")

        cache.reset_stats()
        stats = cache.stats
        assert stats["hits"] == 0
        assert stats["misses"] == 0
