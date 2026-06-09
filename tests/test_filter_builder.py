from __future__ import annotations

import polars as pl
import pytest

from app.engine.filter_builder import (
    apply_time_granularity,
    build_filter_expression,
    build_filter_expressions,
    combine_filters,
)
from app.models import FilterCondition, FilterOperator


class TestFilterBuilder:
    def test_eq_operator(self):
        cond = FilterCondition(column="region", operator=FilterOperator.EQ, value="East")
        expr = build_filter_expression(cond)
        df = pl.DataFrame({"region": ["East", "West", "North"]})
        result = df.filter(expr)
        assert len(result) == 1
        assert result["region"][0] == "East"

    def test_gt_operator(self):
        cond = FilterCondition(column="amount", operator=FilterOperator.GT, value=100)
        expr = build_filter_expression(cond)
        df = pl.DataFrame({"amount": [50, 100, 150, 200]})
        result = df.filter(expr)
        assert len(result) == 2
        assert result["amount"].to_list() == [150, 200]

    def test_lt_operator(self):
        cond = FilterCondition(column="amount", operator=FilterOperator.LT, value=100)
        expr = build_filter_expression(cond)
        df = pl.DataFrame({"amount": [50, 100, 150]})
        result = df.filter(expr)
        assert len(result) == 1
        assert result["amount"][0] == 50

    def test_in_operator(self):
        cond = FilterCondition(
            column="region", operator=FilterOperator.IN, values=["East", "West"]
        )
        expr = build_filter_expression(cond)
        df = pl.DataFrame({"region": ["East", "West", "North", "South"]})
        result = df.filter(expr)
        assert len(result) == 2

    def test_between_operator(self):
        cond = FilterCondition(
            column="amount", operator=FilterOperator.BETWEEN, values=[100, 200]
        )
        expr = build_filter_expression(cond)
        df = pl.DataFrame({"amount": [50, 100, 150, 200, 250]})
        result = df.filter(expr)
        assert len(result) == 3

    def test_like_operator(self):
        cond = FilterCondition(column="name", operator=FilterOperator.LIKE, value="%test%")
        expr = build_filter_expression(cond)
        df = pl.DataFrame({"name": ["test1", "hello", "atestb", "xyz"]})
        result = df.filter(expr)
        assert len(result) == 2

    def test_is_null_operator(self):
        cond = FilterCondition(column="value", operator=FilterOperator.IS_NULL)
        expr = build_filter_expression(cond)
        df = pl.DataFrame({"value": [1, None, 3, None]})
        result = df.filter(expr)
        assert len(result) == 2

    def test_build_multiple_expressions(self):
        conditions = [
            FilterCondition(column="region", operator=FilterOperator.EQ, value="East"),
            FilterCondition(column="amount", operator=FilterOperator.GT, value=100),
        ]
        exprs = build_filter_expressions(conditions)
        assert len(exprs) == 2

    def test_combine_filters_and(self):
        conditions = [
            FilterCondition(column="region", operator=FilterOperator.EQ, value="East"),
            FilterCondition(column="amount", operator=FilterOperator.GT, value=100),
        ]
        exprs = build_filter_expressions(conditions)
        combined = combine_filters(exprs, mode="and")
        df = pl.DataFrame(
            {
                "region": ["East", "East", "West", "West"],
                "amount": [50, 150, 50, 150],
            }
        )
        result = df.filter(combined)
        assert len(result) == 1
        assert result["region"][0] == "East"
        assert result["amount"][0] == 150

    def test_combine_filters_or(self):
        conditions = [
            FilterCondition(column="region", operator=FilterOperator.EQ, value="East"),
            FilterCondition(column="region", operator=FilterOperator.EQ, value="West"),
        ]
        exprs = build_filter_expressions(conditions)
        combined = combine_filters(exprs, mode="or")
        df = pl.DataFrame({"region": ["East", "West", "North"]})
        result = df.filter(combined)
        assert len(result) == 2

    def test_time_granularity_year(self):
        df = pl.DataFrame(
            {"date": pl.date_range(date(2024, 1, 1), date(2024, 12, 31), "1mo", eager=True)}
        )
        lf = df.lazy()
        result = apply_time_granularity(lf, "date", "year").collect()
        assert "date" in result.columns
        assert result["date"].dtype == pl.Int32

    def test_time_granularity_month(self):
        df = pl.DataFrame(
            {"date": pl.date_range(date(2024, 1, 1), date(2024, 3, 1), "1mo", eager=True)}
        )
        lf = df.lazy()
        result = apply_time_granularity(lf, "date", "month").collect()
        assert "date" in result.columns
        assert result["date"].dtype == pl.Utf8


from datetime import date
