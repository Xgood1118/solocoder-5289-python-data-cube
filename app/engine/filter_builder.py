from __future__ import annotations

from typing import Any

import polars as pl

from app.models import FilterCondition, FilterOperator


def build_filter_expression(condition: FilterCondition) -> pl.Expr:
    col = pl.col(condition.column)
    op = condition.operator
    val = condition.value
    vals = condition.values

    match op:
        case FilterOperator.EQ:
            return col == val
        case FilterOperator.NE:
            return col != val
        case FilterOperator.GT:
            return col > val
        case FilterOperator.GTE:
            return col >= val
        case FilterOperator.LT:
            return col < val
        case FilterOperator.LTE:
            return col <= val
        case FilterOperator.IN:
            return col.is_in(vals if vals is not None else [val])
        case FilterOperator.NOT_IN:
            return ~col.is_in(vals if vals is not None else [val])
        case FilterOperator.BETWEEN:
            if vals is None or len(vals) < 2:
                raise ValueError("BETWEEN operator requires two values")
            return col.is_between(vals[0], vals[1])
        case FilterOperator.LIKE:
            pattern = str(val).replace("%", ".*").replace("_", ".")
            return col.str.contains(pattern)
        case FilterOperator.IS_NULL:
            return col.is_null()
        case FilterOperator.IS_NOT_NULL:
            return col.is_not_null()
        case _:
            raise ValueError(f"Unsupported operator: {op}")


def build_filter_expressions(conditions: list[FilterCondition]) -> list[pl.Expr]:
    return [build_filter_expression(c) for c in conditions]


def combine_filters(expressions: list[pl.Expr], mode: str = "and") -> pl.Expr | None:
    if not expressions:
        return None
    if len(expressions) == 1:
        return expressions[0]
    if mode == "and":
        result = expressions[0]
        for expr in expressions[1:]:
            result = result & expr
        return result
    elif mode == "or":
        result = expressions[0]
        for expr in expressions[1:]:
            result = result | expr
        return result
    else:
        raise ValueError(f"Unsupported combine mode: {mode}")


def apply_time_granularity(
    df: pl.LazyFrame,
    time_column: str,
    granularity: str,
    output_alias: str | None = None,
) -> pl.LazyFrame:
    alias = output_alias or time_column
    match granularity:
        case "year":
            expr = pl.col(time_column).dt.year().alias(alias)
        case "quarter":
            expr = pl.col(time_column).dt.year().cast(pl.Utf8).str.concat(
                ["Q", pl.col(time_column).dt.quarter().cast(pl.Utf8)]
            ).alias(alias)
        case "month":
            expr = pl.col(time_column).dt.strftime("%Y-%m").alias(alias)
        case "week":
            expr = pl.col(time_column).dt.strftime("%Y-W%U").alias(alias)
        case "day":
            expr = pl.col(time_column).dt.strftime("%Y-%m-%d").alias(alias)
        case _:
            raise ValueError(f"Unsupported granularity: {granularity}")

    return df.with_columns([expr])
