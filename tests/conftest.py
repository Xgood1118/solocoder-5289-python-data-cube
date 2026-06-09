import os
import sys
import tempfile
from pathlib import Path

import pytest
import polars as pl

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def sample_data():
    from app.data_generator import generate_sales_data

    return generate_sales_data(num_rows=1000, seed=42)


@pytest.fixture(scope="session")
def sample_dimensions():
    from app.data_generator import get_dimension_schemas
    from app.models import DimensionSchema

    return [DimensionSchema(**d) for d in get_dimension_schemas()]


@pytest.fixture(scope="session")
def sample_measures():
    from app.data_generator import get_measure_schemas
    from app.models import MeasureSchema

    return [MeasureSchema(**m) for m in get_measure_schemas()]


@pytest.fixture
def temp_parquet_dir(tmp_path):
    return str(tmp_path / "parquet")


@pytest.fixture
def setup_cube(sample_data, sample_dimensions, sample_measures, tmp_path):
    from app.config import settings
    from app.storage.parquet_store import ParquetStore
    from app.storage.metadata_db import init_db
    from app.storage.metadata_store import metadata_store

    import os
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test.db"

    parquet_dir = str(tmp_path / "parquet")
    store = ParquetStore(base_dir=parquet_dir)
    store.overwrite("sales", sample_data)

    from app.storage import metadata_db as mdb
    mdb._engine = None
    mdb._SessionLocal = None

    init_db()

    existing = metadata_store.get_cube("sales")
    if existing:
        metadata_store.delete_cube("sales")

    cube = metadata_store.create_cube(
        name="sales",
        fact_table="sales",
        dimensions=sample_dimensions,
        measures=sample_measures,
        description="Test sales cube",
    )
    metadata_store.update_cube_stats("sales", len(sample_data))

    return {
        "cube_name": "sales",
        "parquet_dir": parquet_dir,
        "row_count": len(sample_data),
    }
