from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.admin_routes import router as admin_router
from app.api.cube_routes import router as cube_router
from app.api.query_routes import router as query_router
from app.config import settings
from app.refresh.refresh_manager import refresh_manager
from app.storage.metadata_db import init_db

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting OLAP Cube API...")
    init_db()
    logger.info("Database initialized")

    if settings.enable_auto_refresh:
        refresh_manager.start()
        logger.info("Refresh scheduler started")

    yield

    refresh_manager.stop()
    logger.info("OLAP Cube API shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Polars-powered OLAP Cube Backend API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.include_router(cube_router, prefix="/api/v1")
    app.include_router(query_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "app": settings.app_name}

    return app


app = create_app()
