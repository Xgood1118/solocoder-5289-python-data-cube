from __future__ import annotations

from typing import Any

import polars as pl

from app.models import Role, UserContext
from app.storage.metadata_store import metadata_store


class PermissionManager:
    def __init__(self):
        pass

    def get_filters(
        self, user: UserContext, cube_name: str
    ) -> list[pl.Expr]:
        filters: list[pl.Expr] = []

        if user.role == Role.ADMIN:
            return filters

        rules = metadata_store.get_permission_rules(user.role.value, cube_name)
        for rule in rules:
            col = pl.col(rule.dimension)
            cond_type = rule.condition_type
            value = rule.condition_value

            match cond_type:
                case "eq":
                    filters.append(col == value)
                case "in":
                    if value:
                        vals = value.split(",") if value else []
                        filters.append(col.is_in(vals))
                case "like":
                    pattern = str(value).replace("%", ".*").replace("_", ".")
                    filters.append(col.str.contains(pattern))
                case "not_null":
                    filters.append(col.is_not_null())
                case _:
                    pass

        if user.region and self._dimension_exists(cube_name, "region"):
            filters.append(pl.col("region") == user.region)

        if user.org_id and self._dimension_exists(cube_name, "org_id"):
            filters.append(pl.col("org_id") == user.org_id)

        return filters

    def _dimension_exists(self, cube_name: str, dim_name: str) -> bool:
        cube_info = metadata_store.get_cube(cube_name)
        if not cube_info:
            return False
        return any(d.name == dim_name for d in cube_info.dimensions)

    def check_dimension_access(
        self, user: UserContext, cube_name: str, dimensions: list[str]
    ) -> bool:
        if user.role == Role.ADMIN:
            return True
        if user.allowed_dimensions is None:
            return True
        return all(d in user.allowed_dimensions for d in dimensions)

    def check_measure_access(
        self, user: UserContext, cube_name: str, measures: list[str]
    ) -> bool:
        if user.role == Role.ADMIN:
            return True
        if user.allowed_measures is None:
            return True
        return all(m in user.allowed_measures for m in measures)


permission_manager = PermissionManager()
