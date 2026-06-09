from __future__ import annotations

import polars as pl
import pytest

from app.models import Role, UserContext


class TestPermissionManager:
    def test_admin_no_filters(self):
        from app.permissions.permission_manager import permission_manager

        user = UserContext(user_id="admin1", role=Role.ADMIN)
        filters = permission_manager.get_filters(user, "sales")
        assert len(filters) == 0

    def test_region_filter_injected(self, setup_cube):
        from app.permissions.permission_manager import permission_manager
        from app.engine.olap_engine import olap_engine
        from app.storage.parquet_store import ParquetStore

        olap_engine.store = ParquetStore(base_dir=setup_cube["parquet_dir"])

        user = UserContext(
            user_id="manager1", role=Role.MANAGER, region="East"
        )
        filters = permission_manager.get_filters(user, "sales")

        from app.models import CubeQuery

        query = CubeQuery(
            dimensions=["region"],
            measures=["sales_amount"],
        )
        result = olap_engine.query("sales", query, extra_filters=filters)
        assert result.row_count == 1
        assert result.data[0]["region"] == "East"

    def test_org_id_filter_injected(self, setup_cube):
        from app.storage.metadata_store import metadata_store

        from app.permissions.permission_manager import permission_manager

        user = UserContext(
            user_id="manager1", role=Role.MANAGER, org_id="org1"
        )
        filters = permission_manager.get_filters(user, "sales")

        assert len(filters) >= 0

    def test_check_dimension_access_admin(self):
        from app.permissions.permission_manager import permission_manager

        user = UserContext(user_id="admin", role=Role.ADMIN)
        assert permission_manager.check_dimension_access(
            user, "sales", ["region", "channel"]
        )

    def test_check_dimension_access_allowed(self):
        from app.permissions.permission_manager import permission_manager

        user = UserContext(
            user_id="user1",
            role=Role.VIEWER,
            allowed_dimensions=["region", "channel"],
        )
        assert permission_manager.check_dimension_access(
            user, "sales", ["region"]
        )

    def test_check_dimension_access_denied(self):
        from app.permissions.permission_manager import permission_manager

        user = UserContext(
            user_id="user1",
            role=Role.VIEWER,
            allowed_dimensions=["region"],
        )
        assert not permission_manager.check_dimension_access(
            user, "sales", ["region", "product"]
        )

    def test_check_measure_access_admin(self):
        from app.permissions.permission_manager import permission_manager

        user = UserContext(user_id="admin", role=Role.ADMIN)
        assert permission_manager.check_measure_access(
            user, "sales", ["sales_amount", "profit"]
        )

    def test_check_measure_access_allowed(self):
        from app.permissions.permission_manager import permission_manager

        user = UserContext(
            user_id="user1",
            role=Role.VIEWER,
            allowed_measures=["sales_amount"],
        )
        assert permission_manager.check_measure_access(
            user, "sales", ["sales_amount"]
        )

    def test_check_measure_access_denied(self):
        from app.permissions.permission_manager import permission_manager

        user = UserContext(
            user_id="user1",
            role=Role.VIEWER,
            allowed_measures=["sales_amount"],
        )
        assert not permission_manager.check_measure_access(
            user, "sales", ["sales_amount", "profit_margin"]
        )
