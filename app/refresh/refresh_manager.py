from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.cache.query_cache import query_cache
from app.engine.olap_engine import olap_engine
from app.storage.metadata_store import metadata_store
from app.storage.parquet_store import parquet_store

logger = logging.getLogger(__name__)


class RefreshManager:
    def __init__(self):
        self.scheduler: BackgroundScheduler | None = None
        self._handlers: dict[str, Callable] = {}

    def start(self) -> None:
        if not settings.enable_auto_refresh:
            logger.info("Auto refresh is disabled")
            return

        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self._refresh_all_cubes,
            trigger=IntervalTrigger(minutes=settings.refresh_interval_minutes),
            id="refresh_all_cubes",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info(
            f"Refresh scheduler started with interval of {settings.refresh_interval_minutes} minutes"
        )

    def stop(self) -> None:
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None
            logger.info("Refresh scheduler stopped")

    def register_refresh_handler(self, cube_name: str, handler: Callable) -> None:
        self._handlers[cube_name] = handler

    async def refresh_cube(self, cube_name: str, mode: str = "full") -> dict[str, Any]:
        handler = self._handlers.get(cube_name)
        if handler:
            if asyncio.iscoroutinefunction(handler):
                await handler(mode=mode)
            else:
                handler(mode=mode)
        else:
            row_count = parquet_store.row_count(cube_name)
            metadata_store.update_cube_stats(cube_name, row_count)

        query_cache.invalidate_cube(cube_name)

        cube_info = metadata_store.get_cube(cube_name)
        return {
            "cube": cube_name,
            "mode": mode,
            "row_count": cube_info.row_count if cube_info else 0,
            "last_refreshed": cube_info.last_refreshed if cube_info else None,
            "cache_invalidated": True,
        }

    def _refresh_all_cubes(self) -> None:
        try:
            cubes = metadata_store.list_cubes()
            for cube in cubes:
                try:
                    row_count = parquet_store.row_count(cube.name)
                    metadata_store.update_cube_stats(cube.name, row_count)
                    query_cache.invalidate_cube(cube.name)
                    logger.info(f"Refreshed cube: {cube.name} ({row_count} rows)")
                except Exception as e:
                    logger.error(f"Error refreshing cube {cube.name}: {e}")
        except Exception as e:
            logger.error(f"Error in refresh job: {e}")

    def get_scheduler_status(self) -> dict[str, Any]:
        return {
            "running": self.scheduler is not None and self.scheduler.running,
            "interval_minutes": settings.refresh_interval_minutes,
            "enabled": settings.enable_auto_refresh,
        }


refresh_manager = RefreshManager()
