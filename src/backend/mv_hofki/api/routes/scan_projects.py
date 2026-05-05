"""ScanProject API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.pagination import PaginatedResponse
from mv_hofki.schemas.scan_project import (
    ScanProjectCreate,
    ScanProjectRead,
    ScanProjectUpdate,
)
from mv_hofki.services import scan_project as project_service

router = APIRouter(prefix="/api/v1/scanner/projects", tags=["scanner"])


@router.get("", response_model=PaginatedResponse[ScanProjectRead])
async def list_projects(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    items, total = await project_service.get_list(
        db, limit=limit, offset=offset, search=search
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=ScanProjectRead, status_code=201)
async def create_project(data: ScanProjectCreate, db: AsyncSession = Depends(get_db)):
    return await project_service.create(db, data)


@router.get("/{project_id}", response_model=ScanProjectRead)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    return await project_service.get_by_id(db, project_id)


@router.put("/{project_id}", response_model=ScanProjectRead)
async def update_project(
    project_id: int, data: ScanProjectUpdate, db: AsyncSession = Depends(get_db)
):
    return await project_service.update(db, project_id, data)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    await project_service.delete(db, project_id)
    return Response(status_code=204)
