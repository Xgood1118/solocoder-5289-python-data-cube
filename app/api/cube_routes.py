from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.cube_service import cube_service
from app.api.deps import get_current_user
from app.models import CubeInfo, UserContext

router = APIRouter(prefix="/cubes", tags=["cubes"])


@router.get("", response_model=list[CubeInfo])
async def list_cubes(user: UserContext = Depends(get_current_user)):
    return await asyncio.to_thread(cube_service.list_cubes)


@router.get("/{cube_name}", response_model=CubeInfo)
async def get_cube(
    cube_name: str,
    user: UserContext = Depends(get_current_user),
):
    cube = await asyncio.to_thread(cube_service.get_cube, cube_name)
    if not cube:
        raise HTTPException(status_code=404, detail=f"Cube '{cube_name}' not found")
    return cube


@router.get("/{cube_name}/dimensions")
async def list_dimensions(
    cube_name: str,
    user: UserContext = Depends(get_current_user),
):
    cube = await asyncio.to_thread(cube_service.get_cube, cube_name)
    if not cube:
        raise HTTPException(status_code=404, detail=f"Cube '{cube_name}' not found")
    return cube.dimensions


@router.get("/{cube_name}/measures")
async def list_measures(
    cube_name: str,
    user: UserContext = Depends(get_current_user),
):
    cube = await asyncio.to_thread(cube_service.get_cube, cube_name)
    if not cube:
        raise HTTPException(status_code=404, detail=f"Cube '{cube_name}' not found")
    return cube.measures


@router.get("/{cube_name}/dimensions/{dim_name}/values")
async def get_dimension_values(
    cube_name: str,
    dim_name: str,
    user: UserContext = Depends(get_current_user),
):
    cube = await asyncio.to_thread(cube_service.get_cube, cube_name)
    if not cube:
        raise HTTPException(status_code=404, detail=f"Cube '{cube_name}' not found")

    if not any(d.name == dim_name for d in cube.dimensions):
        raise HTTPException(
            status_code=404,
            detail=f"Dimension '{dim_name}' not found in cube '{cube_name}'",
        )

    values = await asyncio.to_thread(
        cube_service.get_dimension_values, cube_name, dim_name
    )
    return {"dimension": dim_name, "values": values}
