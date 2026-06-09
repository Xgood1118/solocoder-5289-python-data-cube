from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class DimensionType(str, Enum):
    TIME = "time"
    GEO = "geo"
    PRODUCT = "product"
    CUSTOMER = "customer"
    CHANNEL = "channel"


class MeasureType(str, Enum):
    SUM = "sum"
    COUNT = "count"
    AVG = "avg"
    DISTINCT_COUNT = "distinct_count"
    MIN = "min"
    MAX = "max"


class TimeGranularity(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class FilterOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    LIKE = "like"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class DimensionSchema(BaseModel):
    name: str
    type: DimensionType
    description: str | None = None
    hierarchies: list[str] | None = None
    column: str


class MeasureSchema(BaseModel):
    name: str
    type: MeasureType
    description: str | None = None
    column: str
    agg: MeasureType


class FilterCondition(BaseModel):
    column: str
    operator: FilterOperator
    value: Any = None
    values: list[Any] | None = None


class SortSpec(BaseModel):
    column: str
    order: SortOrder = SortOrder.DESC


class CubeQuery(BaseModel):
    dimensions: list[str] = Field(default_factory=list)
    measures: list[str] = Field(default_factory=list)
    filters: list[FilterCondition] = Field(default_factory=list)
    sort: list[SortSpec] = Field(default_factory=list)
    pivot: str | None = None
    time_granularity: TimeGranularity | None = None
    limit: int | None = None
    offset: int = 0


class CubeQueryResult(BaseModel):
    data: list[dict[str, Any]]
    columns: list[str]
    row_count: int
    query_time_ms: float
    from_cache: bool = False


class CubeInfo(BaseModel):
    name: str
    description: str | None = None
    dimensions: list[DimensionSchema]
    measures: list[MeasureSchema]
    row_count: int | None = None
    last_refreshed: str | None = None


class ExportFormat(str, Enum):
    CSV = "csv"
    EXCEL = "excel"
    PARQUET = "parquet"


class Role(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    ANALYST = "analyst"
    VIEWER = "viewer"


class UserContext(BaseModel):
    user_id: str
    role: Role
    org_id: str | None = None
    region: str | None = None
    allowed_dimensions: list[str] | None = None
    allowed_measures: list[str] | None = None
