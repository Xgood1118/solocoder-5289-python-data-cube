from __future__ import annotations

import asyncio
import io

import polars as pl
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.cube_service import cube_service
from app.api.deps import get_current_user
from app.models import (
    CreateCubeRequest,
    CubeInfo,
    DimensionSchema,
    MeasureSchema,
    Role,
    UserContext,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _check_admin(user: UserContext) -> None:
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")


@router.post("/cubes", response_model=CubeInfo)
async def create_cube(
    request: CreateCubeRequest,
    user: UserContext = Depends(get_current_user),
):
    _check_admin(user)

    existing = await asyncio.to_thread(cube_service.get_cube, request.name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Cube '{request.name}' already exists",
        )

    fact_table = request.fact_table or request.name

    try:
        cube = await asyncio.to_thread(
            cube_service.create_cube,
            name=request.name,
            fact_table=fact_table,
            dimensions=request.dimensions,
            measures=request.measures,
            description=request.description,
            dimension_tables=request.dimension_tables,
        )
        return cube
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cubes/{cube_name}/load")
async def load_data(
    cube_name: str,
    file: UploadFile = File(...),
    mode: str = Form(default="overwrite"),
    user: UserContext = Depends(get_current_user),
):
    _check_admin(user)

    if mode not in ("overwrite", "append"):
        raise HTTPException(status_code=400, detail="Mode must be 'overwrite' or 'append'")

    try:
        content = await file.read()
        buf = io.BytesIO(content)

        if file.filename and file.filename.endswith(".parquet"):
            df = pl.read_parquet(buf)
        elif file.filename and file.filename.endswith(".csv"):
            df = pl.read_csv(buf)
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Use .csv or .parquet",
            )

        result = await asyncio.to_thread(cube_service.load_data, cube_name, df, mode)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cubes/{cube_name}")
async def delete_cube(
    cube_name: str,
    user: UserContext = Depends(get_current_user),
):
    _check_admin(user)
    success = await asyncio.to_thread(cube_service.delete_cube, cube_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Cube '{cube_name}' not found")
    return {"message": f"Cube '{cube_name}' deleted"}


@router.post("/cubes/{cube_name}/cache/invalidate")
async def invalidate_cache(
    cube_name: str,
    user: UserContext = Depends(get_current_user),
):
    _check_admin(user)
    result = await asyncio.to_thread(cube_service.invalidate_cache, cube_name)
    return result


@router.get("/cache/stats")
async def cache_stats(user: UserContext = Depends(get_current_user)):
    _check_admin(user)
    return await asyncio.to_thread(cube_service.get_cache_stats)


@router.get("/query/stats")
async def query_stats(
    cube_name: str | None = None,
    days: int = 7,
    user: UserContext = Depends(get_current_user),
):
    _check_admin(user)
    return await asyncio.to_thread(cube_service.get_query_stats, cube_name, days)
