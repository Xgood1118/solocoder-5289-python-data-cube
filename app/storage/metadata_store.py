from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.models import (
    CubeInfo,
    DimensionSchema,
    MeasureSchema,
)
from app.storage.metadata_db import (
    CubeMetadata,
    DataSource,
    PermissionRule,
    QueryLog,
    get_session,
)


class MetadataStore:
    @staticmethod
    def list_cubes() -> list[CubeInfo]:
        with get_session() as session:
            cubes = session.query(CubeMetadata).all()
            return [
                CubeInfo(
                    name=c.name,
                    description=c.description,
                    dimensions=json.loads(c.dimensions),
                    measures=json.loads(c.measures),
                    row_count=c.row_count,
                    last_refreshed=c.last_refreshed.isoformat() if c.last_refreshed else None,
                )
                for c in cubes
            ]

    @staticmethod
    def get_cube(name: str) -> CubeInfo | None:
        with get_session() as session:
            c = session.query(CubeMetadata).filter_by(name=name).first()
            if not c:
                return None
            return CubeInfo(
                name=c.name,
                description=c.description,
                dimensions=json.loads(c.dimensions),
                measures=json.loads(c.measures),
                row_count=c.row_count,
                last_refreshed=c.last_refreshed.isoformat() if c.last_refreshed else None,
            )

    @staticmethod
    def get_cube_fact_table(name: str) -> str | None:
        with get_session() as session:
            c = session.query(CubeMetadata).filter_by(name=name).first()
            return c.fact_table if c else None

    @staticmethod
    def get_cube_dimension_tables(name: str) -> dict[str, str]:
        with get_session() as session:
            c = session.query(CubeMetadata).filter_by(name=name).first()
            if not c or not c.dimension_tables:
                return {}
            return json.loads(c.dimension_tables)

    @staticmethod
    def create_cube(
        name: str,
        fact_table: str,
        dimensions: list[DimensionSchema],
        measures: list[MeasureSchema],
        description: str | None = None,
        dimension_tables: dict[str, str] | None = None,
    ) -> CubeInfo:
        with get_session() as session:
            dims_json = json.dumps([d.model_dump() for d in dimensions])
            measures_json = json.dumps([m.model_dump() for m in measures])
            dim_tables_json = json.dumps(dimension_tables or {})

            cube = CubeMetadata(
                name=name,
                description=description,
                fact_table=fact_table,
                dimensions=dims_json,
                measures=measures_json,
                dimension_tables=dim_tables_json,
            )
            session.add(cube)
            session.commit()
            session.refresh(cube)
            return CubeInfo(
                name=cube.name,
                description=cube.description,
                dimensions=dimensions,
                measures=measures,
                row_count=0,
                last_refreshed=None,
            )

    @staticmethod
    def update_cube_stats(name: str, row_count: int) -> None:
        with get_session() as session:
            c = session.query(CubeMetadata).filter_by(name=name).first()
            if c:
                c.row_count = row_count
                c.last_refreshed = datetime.now(timezone.utc)
                session.commit()

    @staticmethod
    def delete_cube(name: str) -> bool:
        with get_session() as session:
            c = session.query(CubeMetadata).filter_by(name=name).first()
            if c:
                session.delete(c)
                session.commit()
                return True
            return False

    @staticmethod
    def log_query(
        cube_name: str,
        query_json: str,
        duration_ms: int,
        row_count: int,
        from_cache: bool = False,
        query_hash: str | None = None,
        user_id: str | None = None,
    ) -> None:
        with get_session() as session:
            log = QueryLog(
                cube_name=cube_name,
                query_hash=query_hash,
                query_json=query_json,
                duration_ms=duration_ms,
                row_count=row_count,
                from_cache=1 if from_cache else 0,
                user_id=user_id,
            )
            session.add(log)
            session.commit()

    @staticmethod
    def get_query_stats(cube_name: str | None = None, days: int = 7) -> dict[str, Any]:
        from sqlalchemy import func

        with get_session() as session:
            query = session.query(
                func.count(QueryLog.id).label("total_queries"),
                func.avg(QueryLog.duration_ms).label("avg_duration_ms"),
                func.sum(QueryLog.from_cache).label("cached_queries"),
            )
            if cube_name:
                query = query.filter(QueryLog.cube_name == cube_name)
            result = query.first()
            total = result.total_queries or 0
            cached = result.cached_queries or 0
            return {
                "total_queries": total,
                "avg_duration_ms": round(result.avg_duration_ms or 0, 2),
                "cache_hits": cached,
                "cache_hit_rate": round(cached / total, 4) if total > 0 else 0.0,
            }

    @staticmethod
    def get_permission_rules(role: str, cube_name: str) -> list[PermissionRule]:
        with get_session() as session:
            return (
                session.query(PermissionRule)
                .filter_by(role=role, cube_name=cube_name)
                .all()
            )

    @staticmethod
    def add_permission_rule(
        role: str,
        cube_name: str,
        dimension: str,
        condition_type: str,
        condition_value: str | None = None,
    ) -> PermissionRule:
        with get_session() as session:
            rule = PermissionRule(
                role=role,
                cube_name=cube_name,
                dimension=dimension,
                condition_type=condition_type,
                condition_value=condition_value,
            )
            session.add(rule)
            session.commit()
            session.refresh(rule)
            return rule


metadata_store = MetadataStore()
