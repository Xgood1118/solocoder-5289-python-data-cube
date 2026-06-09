from __future__ import annotations

import pytest

from app.models import CubeQuery, Role, UserContext


class TestCubeService:
    def test_list_cubes(self, setup_cube):
        from app.api.cube_service import cube_service

        cubes = cube_service.list_cubes()
        assert len(cubes) >= 1
        assert any(c.name == "sales" for c in cubes)

    def test_get_cube(self, setup_cube):
        from app.api.cube_service import cube_service

        cube = cube_service.get_cube("sales")
        assert cube is not None
        assert cube.name == "sales"
        assert len(cube.dimensions) > 0
        assert len(cube.measures) > 0

    def test_query_basic(self, setup_cube):
        from app.api.cube_service import cube_service
        from app.storage.parquet_store import ParquetStore
        from app.engine.olap_engine import olap_engine

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])
        cube_service.engine = olap_engine

        user = UserContext(user_id="test", role=Role.ADMIN)
        query = CubeQuery(dimensions=["region"], measures=["sales_amount"])

        result = cube_service.query("sales", query, user)
        assert result.row_count == 5
        assert result.from_cache is False

    def test_query_with_cache(self, setup_cube):
        from app.api.cube_service import cube_service
        from app.storage.parquet_store import ParquetStore
        from app.engine.olap_engine import olap_engine
        from app.cache.query_cache import QueryCache

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])
        cube_service.engine = olap_engine
        cube_service.cache = QueryCache(max_size=10, ttl_seconds=60)

        user = UserContext(user_id="test", role=Role.ADMIN)
        query = CubeQuery(dimensions=["region"], measures=["sales_amount"])

        result1 = cube_service.query("sales", query, user, use_cache=True)
        assert result1.from_cache is False

        result2 = cube_service.query("sales", query, user, use_cache=True)
        assert result2.from_cache is True
        assert result2.data == result1.data

    def test_query_no_cache(self, setup_cube):
        from app.api.cube_service import cube_service
        from app.storage.parquet_store import ParquetStore
        from app.engine.olap_engine import olap_engine
        from app.cache.query_cache import QueryCache

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])
        cube_service.engine = olap_engine
        cube_service.cache = QueryCache(max_size=10, ttl_seconds=60)

        user = UserContext(user_id="test", role=Role.ADMIN)
        query = CubeQuery(dimensions=["region"], measures=["sales_amount"])

        result1 = cube_service.query("sales", query, user, use_cache=True)
        result2 = cube_service.query("sales", query, user, use_cache=False)

        assert result2.from_cache is False

    def test_invalidate_cache(self, setup_cube):
        from app.api.cube_service import cube_service
        from app.storage.parquet_store import ParquetStore
        from app.engine.olap_engine import olap_engine
        from app.cache.query_cache import QueryCache

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])
        cube_service.engine = olap_engine
        cube_service.cache = QueryCache(max_size=10, ttl_seconds=60)

        user = UserContext(user_id="test", role=Role.ADMIN)
        query = CubeQuery(dimensions=["region"], measures=["sales_amount"])

        cube_service.query("sales", query, user, use_cache=True)
        assert cube_service.cache.size > 0

        cube_service.invalidate_cache("sales")
        assert cube_service.cache.size == 0

    def test_get_cache_stats(self, setup_cube):
        from app.api.cube_service import cube_service
        from app.storage.parquet_store import ParquetStore
        from app.engine.olap_engine import olap_engine
        from app.cache.query_cache import QueryCache

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])
        cube_service.engine = olap_engine
        cube_service.cache = QueryCache(max_size=10, ttl_seconds=60)

        user = UserContext(user_id="test", role=Role.ADMIN)
        query = CubeQuery(dimensions=["region"], measures=["sales_amount"])

        cube_service.query("sales", query, user, use_cache=True)
        cube_service.query("sales", query, user, use_cache=True)

        stats = cube_service.get_cache_stats()
        assert stats["hits"] >= 0
        assert "hit_rate" in stats
