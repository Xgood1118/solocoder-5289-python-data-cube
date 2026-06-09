from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.cube_service import cube_service
from app.api.deps import get_current_user
from app.models import CubeQuery, CubeQueryResult, ExportFormat, UserContext

router = APIRouter(prefix="/queries", tags=["queries"])


@router.post("/{cube_name}", response_model=CubeQueryResult)
async def query_cube(
    cube_name: str,
    query: CubeQuery,
    use_cache: bool = True,
    user: UserContext = Depends(get_current_user),
):
    try:
        result = await asyncio.to_thread(
            cube_service.query, cube_name, query, user, use_cache
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{cube_name}/export/{format}")
async def export_query(
    cube_name: str,
    format: ExportFormat,
    query: CubeQuery,
    user: UserContext = Depends(get_current_user),
):
    try:
        suffix_map = {
            ExportFormat.CSV: ".csv",
            ExportFormat.EXCEL: ".xlsx",
            ExportFormat.PARQUET: ".parquet",
        }
        suffix = suffix_map[format]

        tmp_dir = Path(tempfile.gettempdir()) / "olap_exports"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(tmp_dir / f"{cube_name}_{uuid.uuid4().hex}{suffix}")

        await asyncio.to_thread(
            cube_service.export, cube_name, query, format, output_path, user
        )

        filename = f"{cube_name}_export{suffix}"
        return FileResponse(
            path=output_path,
            filename=filename,
            media_type="application/octet-stream",
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
