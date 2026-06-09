from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def client(setup_cube, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.storage.parquet_store import ParquetStore
    from app.engine.olap_engine import olap_engine
    from app.api.cube_service import cube_service
    from app.cache.query_cache import QueryCache
    from app.storage import metadata_db
    from app.config import settings

    db_path = tmp_path / "test.db"
    settings.database_url = f"sqlite:///{db_path}"

    metadata_db._engine = None
    metadata_db._SessionLocal = None
    metadata_db.init_db()

    from app.data_generator import get_dimension_schemas, get_measure_schemas
    from app.models import DimensionSchema, MeasureSchema
    from app.storage.metadata_store import metadata_store

    dimensions = [DimensionSchema(**d) for d in get_dimension_schemas()]
    measures = [MeasureSchema(**m) for m in get_measure_schemas()]

    existing = metadata_store.get_cube("sales")
    if existing:
        metadata_store.delete_cube("sales")

    metadata_store.create_cube(
        name="sales",
        fact_table="sales",
        dimensions=dimensions,
        measures=measures,
        description="Test sales cube",
    )
    metadata_store.update_cube_stats("sales", 1000)

    olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])
    cube_service.engine = olap_engine
    cube_service.cache = QueryCache(max_size=10, ttl_seconds=60)

    app = create_app()
    return TestClient(app)


class TestCubeAPI:
    def test_list_cubes(self, client):
        response = client.get("/api/v1/cubes", headers={"x-role": "admin"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == "sales"

    def test_get_cube(self, client):
        response = client.get("/api/v1/cubes/sales", headers={"x-role": "admin"})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "sales"
        assert "dimensions" in data
        assert "measures" in data

    def test_get_cube_not_found(self, client):
        response = client.get(
            "/api/v1/cubes/nonexistent", headers={"x-role": "admin"}
        )
        assert response.status_code == 404

    def test_list_dimensions(self, client):
        response = client.get(
            "/api/v1/cubes/sales/dimensions", headers={"x-role": "admin"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_list_measures(self, client):
        response = client.get(
            "/api/v1/cubes/sales/measures", headers={"x-role": "admin"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_dimension_values(self, client):
        response = client.get(
            "/api/v1/cubes/sales/dimensions/region/values",
            headers={"x-role": "admin"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "dimension" in data
        assert "values" in data
        assert len(data["values"]) == 5


class TestQueryAPI:
    def test_query_basic(self, client):
        response = client.post(
            "/api/v1/queries/sales",
            json={
                "dimensions": ["region"],
                "measures": ["sales_amount", "order_count"],
            },
            headers={"x-role": "admin"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["row_count"] == 5
        assert "data" in data
        assert "columns" in data
        assert "query_time_ms" in data
        assert data["from_cache"] is False

    def test_query_with_filters(self, client):
        response = client.post(
            "/api/v1/queries/sales",
            json={
                "dimensions": ["region"],
                "measures": ["sales_amount"],
                "filters": [
                    {"column": "region", "operator": "eq", "value": "East"}
                ],
            },
            headers={"x-role": "admin"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["row_count"] == 1
        assert data["data"][0]["region"] == "East"

    def test_query_with_sort(self, client):
        response = client.post(
            "/api/v1/queries/sales",
            json={
                "dimensions": ["region"],
                "measures": ["sales_amount"],
                "sort": [{"column": "sales_amount", "order": "desc"}],
            },
            headers={"x-role": "admin"},
        )
        assert response.status_code == 200
        data = response.json()
        amounts = [row["sales_amount"] for row in data["data"]]
        assert amounts == sorted(amounts, reverse=True)

    def test_query_with_limit(self, client):
        response = client.post(
            "/api/v1/queries/sales",
            json={
                "dimensions": ["product"],
                "measures": ["sales_amount"],
                "sort": [{"column": "sales_amount", "order": "desc"}],
                "limit": 3,
            },
            headers={"x-role": "admin"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["row_count"] == 3

    def test_query_with_time_granularity(self, client):
        response = client.post(
            "/api/v1/queries/sales",
            json={
                "dimensions": ["order_date"],
                "measures": ["sales_amount"],
                "time_granularity": "month",
            },
            headers={"x-role": "admin"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["row_count"] >= 1

    def test_query_cache(self, client):
        response1 = client.post(
            "/api/v1/queries/sales?use_cache=true",
            json={"dimensions": ["region"], "measures": ["sales_amount"]},
            headers={"x-role": "admin"},
        )
        assert response1.status_code == 200
        assert response1.json()["from_cache"] is False

        response2 = client.post(
            "/api/v1/queries/sales?use_cache=true",
            json={"dimensions": ["region"], "measures": ["sales_amount"]},
            headers={"x-role": "admin"},
        )
        assert response2.status_code == 200
        assert response2.json()["from_cache"] is True

    def test_query_invalid_dimension(self, client):
        response = client.post(
            "/api/v1/queries/sales",
            json={
                "dimensions": ["nonexistent"],
                "measures": ["sales_amount"],
            },
            headers={"x-role": "admin"},
        )
        assert response.status_code == 400

    def test_export_csv(self, client):
        response = client.post(
            "/api/v1/queries/sales/export/csv",
            json={
                "dimensions": ["region"],
                "measures": ["sales_amount"],
            },
            headers={"x-role": "admin"},
        )
        assert response.status_code == 200
        assert "content-disposition" in response.headers
        assert response.headers["content-type"].startswith("application/")

    def test_export_parquet(self, client):
        response = client.post(
            "/api/v1/queries/sales/export/parquet",
            json={
                "dimensions": ["region"],
                "measures": ["sales_amount"],
            },
            headers={"x-role": "admin"},
        )
        assert response.status_code == 200


class TestAdminAPI:
    def test_cache_stats(self, client):
        response = client.get(
            "/api/v1/admin/cache/stats", headers={"x-role": "admin"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "hits" in data
        assert "misses" in data
        assert "hit_rate" in data

    def test_cache_stats_not_admin(self, client):
        response = client.get(
            "/api/v1/admin/cache/stats", headers={"x-role": "viewer"}
        )
        assert response.status_code == 403

    def test_invalidate_cache(self, client):
        response = client.post(
            "/api/v1/admin/cubes/sales/cache/invalidate",
            headers={"x-role": "admin"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "cube" in data
        assert "invalidated_keys" in data

    def test_invalid_role(self, client):
        response = client.get(
            "/api/v1/cubes", headers={"x-role": "invalid_role"}
        )
        assert response.status_code == 400

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
