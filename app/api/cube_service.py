from __future__ import annotations

import json
import time
from typing import Any

import polars as pl

from app.cache.query_cache import QueryCache, query_cache
from app.engine.olap_engine import OLAPEngine, olap_engine
from app.models import (
    CubeInfo,
    CubeQuery,
    CubeQueryResult,
    DimensionSchema,
    ExportFormat,
    MeasureSchema,
    UserContext,
)
from app.permissions.permission_manager import permission_manager
from app.storage.metadata_store import metadata_store


class CubeService:
    def __init__(
        self,
        engine: OLAPEngine | None = None,
        cache: QueryCache | None = None,
    ):
        self.engine = engine or olap_engine
        self.cache = cache or query_cache

    def list_cubes(self) -> list[CubeInfo]:
        return metadata_store.list_cubes()

    def get_cube(self, name: str) -> CubeInfo | None:
        return metadata_store.get_cube(name)

    def create_cube(
        self,
        name: str,
        fact_table: str,
        dimensions: list[DimensionSchema],
        measures: list[MeasureSchema],
        description: str | None = None,
        dimension_tables: dict[str, str] | None = None,
    ) -> CubeInfo:
        return metadata_store.create_cube(
            name=name,
            fact_table=fact_table,
            dimensions=dimensions,
            measures=measures,
            description=description,
            dimension_tables=dimension_tables,
        )

    def delete_cube(self, name: str) -> bool:
        result = metadata_store.delete_cube(name)
        if result:
            self.cache.invalidate_cube(name)
        return result

    def query(
        self,
        cube_name: str,
        query: CubeQuery,
        user: UserContext,
        use_cache: bool = True,
    ) -> CubeQueryResult:
        if not permission_manager.check_dimension_access(
            user, cube_name, query.dimensions
        ):
            raise PermissionError("Insufficient dimension access")

        if query.measures and not permission_manager.check_measure_access(
            user, cube_name, query.measures
        ):
            raise PermissionError("Insufficient measure access")

        extra_filters = permission_manager.get_filters(user, cube_name)

        extra_key = f"user:{user.role}:{user.region or ''}:{user.org_id or ''}"
        cache_key = self.cache._make_key(cube_name, query, extra=extra_key)

        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                result = CubeQueryResult(**cached)
                result.from_cache = True
                self._log_query(cube_name, query, result, user, cache_key)
                return result

        result = self.engine.query(
            cube_name,
            query,
            extra_filters=extra_filters,
        )

        if use_cache:
            self.cache.set(cache_key, result.model_dump())

        self._log_query(cube_name, query, result, user, cache_key)

        return result

    def _log_query(
        self,
        cube_name: str,
        query: CubeQuery,
        result: CubeQueryResult,
        user: UserContext,
        cache_key: str,
    ) -> None:
        try:
            metadata_store.log_query(
                cube_name=cube_name,
                query_json=query.model_dump_json(),
                duration_ms=int(result.query_time_ms),
                row_count=result.row_count,
                from_cache=result.from_cache,
                query_hash=cache_key[:32],
                user_id=user.user_id,
            )
        except Exception:
            pass

    def export(
        self,
        cube_name: str,
        query: CubeQuery,
        format: ExportFormat,
        output_path: str,
        user: UserContext,
    ) -> str:
        extra_filters = permission_manager.get_filters(user, cube_name)
        return self.engine.export(
            cube_name,
            query,
            format.value,
            output_path,
            extra_filters=extra_filters,
        )

    def get_dimension_values(
        self, cube_name: str, dimension_name: str
    ) -> list[Any]:
        return self.engine.get_dimension_values(cube_name, dimension_name)

    def invalidate_cache(self, cube_name: str | None = None) -> dict[str, Any]:
        if cube_name:
            count = self.cache.invalidate_cube(cube_name)
            return {"cube": cube_name, "invalidated_keys": count}
        else:
            size_before = self.cache.size
            self.cache.invalidate_all()
            return {"invalidated_keys": size_before}

    def get_cache_stats(self) -> dict[str, Any]:
        return self.cache.stats

    def get_query_stats(self, cube_name: str | None = None, days: int = 7) -> dict[str, Any]:
        return metadata_store.get_query_stats(cube_name=cube_name, days=days)

    def load_data(
        self,
        cube_name: str,
        df: "pl.DataFrame",
        mode: str = "overwrite",
    ) -> dict[str, Any]:
        row_count = self.engine.refresh_cube(cube_name, df, mode=mode)
        self.cache.invalidate_cube(cube_name)
        return {"cube": cube_name, "row_count": row_count, "mode": mode}


cube_service = CubeService()
