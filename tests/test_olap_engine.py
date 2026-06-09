from __future__ import annotations

import pytest

from app.models import (
    CubeQuery,
    FilterCondition,
    FilterOperator,
    SortOrder,
    SortSpec,
    TimeGranularity,
)


class TestOLAPEngine:
    def test_basic_aggregation(self, setup_cube):
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        query = CubeQuery(
            dimensions=["region"],
            measures=["sales_amount", "order_count"],
        )
        result = olap_engine.query("sales", query)
        assert result.row_count == 5
        assert "region" in result.columns
        assert "sales_amount" in result.columns
        assert "order_count" in result.columns

    def test_multi_dimension_aggregation(self, setup_cube):
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        query = CubeQuery(
            dimensions=["region", "channel"],
            measures=["sales_amount"],
        )
        result = olap_engine.query("sales", query)
        assert result.row_count > 0
        assert "region" in result.columns
        assert "channel" in result.columns

    def test_filter(self, setup_cube):
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        query = CubeQuery(
            dimensions=["region"],
            measures=["sales_amount"],
            filters=[
                FilterCondition(
                    column="region", operator=FilterOperator.EQ, value="East"
                )
            ],
        )
        result = olap_engine.query("sales", query)
        assert result.row_count == 1
        assert result.data[0]["region"] == "East"

    def test_sort_desc(self, setup_cube):
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        query = CubeQuery(
            dimensions=["region"],
            measures=["sales_amount"],
            sort=[SortSpec(column="sales_amount", order=SortOrder.DESC)],
        )
        result = olap_engine.query("sales", query)
        amounts = [row["sales_amount"] for row in result.data]
        assert amounts == sorted(amounts, reverse=True)

    def test_sort_asc(self, setup_cube):
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        query = CubeQuery(
            dimensions=["region"],
            measures=["sales_amount"],
            sort=[SortSpec(column="sales_amount", order=SortOrder.ASC)],
        )
        result = olap_engine.query("sales", query)
        amounts = [row["sales_amount"] for row in result.data]
        assert amounts == sorted(amounts)

    def test_limit(self, setup_cube):
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        query = CubeQuery(
            dimensions=["product"],
            measures=["sales_amount"],
            sort=[SortSpec(column="sales_amount", order=SortOrder.DESC)],
            limit=3,
        )
        result = olap_engine.query("sales", query)
        assert result.row_count == 3

    def test_time_granularity_year(self, setup_cube):
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        query = CubeQuery(
            dimensions=["order_date"],
            measures=["sales_amount"],
            time_granularity=TimeGranularity.YEAR,
        )
        result = olap_engine.query("sales", query)
        assert result.row_count >= 1

    def test_time_granularity_month(self, setup_cube):
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        query = CubeQuery(
            dimensions=["order_date"],
            measures=["sales_amount"],
            time_granularity=TimeGranularity.MONTH,
        )
        result = olap_engine.query("sales", query)
        assert result.row_count >= 1

    def test_no_dimensions(self, setup_cube):
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        query = CubeQuery(
            dimensions=[],
            measures=["sales_amount", "order_count"],
        )
        result = olap_engine.query("sales", query)
        assert result.row_count == 1
        assert "sales_amount" in result.columns
        assert "order_count" in result.columns

    def test_unknown_dimension_raises(self, setup_cube):
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        query = CubeQuery(
            dimensions=["nonexistent"],
            measures=["sales_amount"],
        )
        with pytest.raises(ValueError, match="Unknown dimension"):
            olap_engine.query("sales", query)

    def test_unknown_measure_raises(self, setup_cube):
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        query = CubeQuery(
            dimensions=["region"],
            measures=["nonexistent"],
        )
        with pytest.raises(ValueError, match="Unknown measure"):
            olap_engine.query("sales", query)

    def test_get_dimension_values(self, setup_cube):
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        values = olap_engine.get_dimension_values("sales", "region")
        assert len(values) == 5
        assert "East" in values
        assert "West" in values

    def test_export_csv(self, setup_cube, tmp_path):
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        query = CubeQuery(
            dimensions=["region"],
            measures=["sales_amount"],
        )
        output_path = str(tmp_path / "test_export.csv")
        path = olap_engine.export("sales", query, "csv", output_path)
        assert path == output_path
        import os

        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0

    def test_export_parquet(self, setup_cube, tmp_path):
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        query = CubeQuery(
            dimensions=["region"],
            measures=["sales_amount"],
        )
        output_path = str(tmp_path / "test_export.parquet")
        path = olap_engine.export("sales", query, "parquet", output_path)
        assert path == output_path
        import os

        assert os.path.exists(output_path)

    def test_rollup_time(self, setup_cube):
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        query_day = CubeQuery(
            dimensions=["order_date"],
            measures=["sales_amount"],
            time_granularity=TimeGranularity.DAY,
        )
        result_day = olap_engine.query("sales", query_day)

        query_month = CubeQuery(
            dimensions=["order_date"],
            measures=["sales_amount"],
            time_granularity=TimeGranularity.MONTH,
        )
        result_month = olap_engine.query("sales", query_month)

        assert result_month.row_count < result_day.row_count
