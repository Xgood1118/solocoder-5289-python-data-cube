from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import polars as pl

from app.config import settings


class ParquetStore:
    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or settings.parquet_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _table_path(self, table_name: str) -> Path:
        return self.base_dir / f"{table_name}.parquet"

    def exists(self, table_name: str) -> bool:
        return self._table_path(table_name).exists()

    def scan(self, table_name: str) -> pl.LazyFrame:
        path = self._table_path(table_name)
        return pl.scan_parquet(path)

    def read(self, table_name: str) -> pl.DataFrame:
        path = self._table_path(table_name)
        return pl.read_parquet(path)

    def write(self, table_name: str, df: pl.DataFrame | pl.LazyFrame) -> None:
        path = self._table_path(table_name)
        if isinstance(df, pl.LazyFrame):
            df.sink_parquet(path)
        else:
            df.write_parquet(path)

    def append(self, table_name: str, df: pl.DataFrame | pl.LazyFrame) -> None:
        if not self.exists(table_name):
            self.write(table_name, df)
            return
        existing = self.scan(table_name)
        if isinstance(df, pl.DataFrame):
            df = df.lazy()
        combined = pl.concat([existing, df], how="vertical")
        self.write(table_name, combined)

    def overwrite(self, table_name: str, df: pl.DataFrame | pl.LazyFrame) -> None:
        self.write(table_name, df)

    def delete(self, table_name: str) -> None:
        path = self._table_path(table_name)
        if path.exists():
            path.unlink()

    def list_tables(self) -> list[str]:
        return [
            f.stem
            for f in self.base_dir.glob("*.parquet")
            if f.is_file()
        ]

    def row_count(self, table_name: str) -> int:
        if not self.exists(table_name):
            return 0
        return self.scan(table_name).select(pl.len()).collect().item()

    def schema(self, table_name: str) -> dict[str, pl.DataType]:
        if not self.exists(table_name):
            return {}
        lf = self.scan(table_name)
        return dict(zip(lf.columns, lf.dtypes))


parquet_store = ParquetStore()
