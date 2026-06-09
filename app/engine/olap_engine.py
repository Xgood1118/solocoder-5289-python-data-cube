from __future__ import annotations

import json
import time
from typing import Any

import polars as pl

from app.config import settings
from app.engine.filter_builder import (
    apply_time_granularity,
    build_filter_expressions,
    combine_filters,
)
from app.models import (
    CubeQuery,
    CubeQueryResult,
    DimensionSchema,
    MeasureSchema,
    MeasureType,
    SortOrder,
    SortSpec,
    TimeGranularity,
)
from app.storage.parquet_store import parquet_store
from app.storage.metadata_store import metadata_store


class OLAPEngine:
    def __init__(self):
        self.store = parquet_store

    def _build_measure_expr(self, measure: MeasureSchema) -> pl.Expr:
        col = measure.column
        name = measure.name
        agg_type = measure.agg

        match agg_type:
            case MeasureType.SUM:
                return pl.sum(col).alias(name)
            case MeasureType.COUNT:
                return pl.count(col).alias(name)
            case MeasureType.AVG:
                return pl.mean(col).alias(name)
            case MeasureType.DISTINCT_COUNT:
                return pl.n_unique(col).alias(name)
            case MeasureType.MIN:
                return pl.min(col).alias(name)
            case MeasureType.MAX:
                return pl.max(col).alias(name)
            case _:
                raise ValueError(f"Unsupported aggregation: {agg_type}")

    def _resolve_dimensions(
        self,
        query: CubeQuery,
        dim_schemas: list[DimensionSchema],
    ) -> tuple[list[str], list[pl.Expr]]:
        dim_names = query.dimensions
        dim_map = {d.name: d for d in dim_schemas}

        select_cols: list[str] = []
        exprs: list[pl.Expr] = []

        for dim_name in dim_names:
            if dim_name not in dim_map:
                raise ValueError(f"Unknown dimension: {dim_name}")
            dim = dim_map[dim_name]
            select_cols.append(dim.name)
            exprs.append(pl.col(dim.column).alias(dim.name))

        return select_cols, exprs

    def _resolve_measures(
        self,
        measure_names: list[str],
        measure_schemas: list[MeasureSchema],
    ) -> list[pl.Expr]:
        measure_map = {m.name: m for m in measure_schemas}
        exprs: list[pl.Expr] = []
        for name in measure_names:
            if name not in measure_map:
                raise ValueError(f"Unknown measure: {name}")
            exprs.append(self._build_measure_expr(measure_map[name]))
        return exprs

    def _get_cube_schemas(
        self, cube_name: str
    ) -> tuple[str, list[DimensionSchema], list[MeasureSchema], dict[str, str]]:
        cube_info = metadata_store.get_cube(cube_name)
        if not cube_info:
            raise ValueError(f"Cube not found: {cube_name}")

        fact_table = metadata_store.get_cube_fact_table(cube_name) or cube_name
        dim_tables = metadata_store.get_cube_dimension_tables(cube_name)
        return fact_table, cube_info.dimensions, cube_info.measures, dim_tables

    def query(
        self,
        cube_name: str,
        query: CubeQuery,
        extra_filters: list[pl.Expr] | None = None,
    ) -> CubeQueryResult:
        start = time.time()

        fact_table, dim_schemas, measure_schemas, dim_tables = self._get_cube_schemas(
            cube_name
        )

        lf = self.store.scan(fact_table)

        dim_names = query.dimensions
        measure_names = query.measures or [m.name for m in measure_schemas]

        dim_map = {d.name: d for d in dim_schemas}
        for dim_name in dim_names:
            if dim_name not in dim_map:
                raise ValueError(f"Unknown dimension: {dim_name}")

        all_filters = build_filter_expressions(query.filters)
        if extra_filters:
            all_filters.extend(extra_filters)

        if all_filters:
            filter_expr = combine_filters(all_filters)
            if filter_expr is not None:
                lf = lf.filter(filter_expr)

        time_dim = None
        for dim in dim_schemas:
            if dim.type.value == "time":
                time_dim = dim
                break

        if query.time_granularity and time_dim:
            lf = apply_time_granularity(
                lf, time_dim.column, query.time_granularity.value, time_dim.name
            )
            group_cols = query.dimensions
        else:
            group_cols = []
            for dim in dim_schemas:
                if dim.name in dim_names:
                    group_cols.append(dim.name)
                    if dim.name != dim.column:
                        lf = lf.with_columns(pl.col(dim.column).alias(dim.name))

        if not group_cols:
            measure_exprs = self._resolve_measures(measure_names, measure_schemas)
            lf = lf.select(measure_exprs)
        else:
            measure_exprs = self._resolve_measures(measure_names, measure_schemas)
            lf = lf.group_by(group_cols).agg(measure_exprs)

        if query.pivot and query.pivot in dim_names and len(dim_names) >= 2:
            measure_for_pivot = measure_names[0] if measure_names else None
            if measure_for_pivot:
                idx_cols = [d for d in dim_names if d != query.pivot]
                df = lf.collect()
                df = df.pivot(
                    index=idx_cols,
                    columns=query.pivot,
                    values=measure_for_pivot,
                    aggregate_function="first",
                )
                lf = df.lazy()

        if query.sort:
            sort_cols = [s.column for s in query.sort]
            descending = [s.order == SortOrder.DESC for s in query.sort]
            lf = lf.sort(sort_cols, descending=descending)

        if query.limit is not None:
            lf = lf.slice(query.offset, query.limit)
        elif query.offset > 0:
            lf = lf.slice(query.offset)

        df = lf.collect()

        query_time_ms = (time.time() - start) * 1000

        return CubeQueryResult(
            data=df.to_dicts(),
            columns=df.columns,
            row_count=len(df),
            query_time_ms=round(query_time_ms, 2),
            from_cache=False,
        )

    def export(
        self,
        cube_name: str,
        query: CubeQuery,
        format: str,
        output_path: str,
        extra_filters: list[pl.Expr] | None = None,
    ) -> str:
        fact_table, dim_schemas, measure_schemas, dim_tables = self._get_cube_schemas(
            cube_name
        )

        result = self.query(cube_name, query, extra_filters=extra_filters)
        df = pl.DataFrame(result.data)

        match format.lower():
            case "csv":
                df.write_csv(output_path)
            case "parquet":
                df.write_parquet(output_path)
            case "excel":
                df.write_excel(output_path)
            case _:
                raise ValueError(f"Unsupported export format: {format}")

        return output_path

    def get_dimension_values(
        self, cube_name: str, dimension_name: str
    ) -> list[Any]:
        fact_table, dim_schemas, measure_schemas, dim_tables = self._get_cube_schemas(
            cube_name
        )

        dim_map = {d.name: d for d in dim_schemas}
        if dimension_name not in dim_map:
            raise ValueError(f"Unknown dimension: {dimension_name}")

        dim = dim_map[dimension_name]
        lf = self.store.scan(fact_table)
        values = (
            lf.select(pl.col(dim.column))
            .unique()
            .sort(dim.column)
            .collect()
            .to_series()
            .to_list()
        )
        return values

    def refresh_cube(
        self,
        cube_name: str,
        df: pl.DataFrame,
        mode: str = "overwrite",
    ) -> int:
        fact_table = metadata_store.get_cube_fact_table(cube_name) or cube_name

        if mode == "overwrite":
            self.store.overwrite(fact_table, df)
        elif mode == "append":
            self.store.append(fact_table, df)
        else:
            raise ValueError(f"Unsupported refresh mode: {mode}")

        row_count = self.store.row_count(fact_table)
        metadata_store.update_cube_stats(cube_name, row_count)
        return row_count


olap_engine = OLAPEngine()
