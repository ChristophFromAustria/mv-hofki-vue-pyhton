"""ScanPart API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.scan_part import ScanPartCreate, ScanPartRead, ScanPartUpdate
from mv_hofki.services import scan_part as part_service

router = APIRouter(
    prefix="/api/v1/scanner/projects/{project_id}/parts", tags=["scanner"]
)


@router.get("", response_model=list[ScanPartRead])
async def list_parts(project_id: int, db: AsyncSession = Depends(get_db)):
    return await part_service.get_list(db, project_id)


@router.post("", response_model=ScanPartRead, status_code=201)
async def create_part(
    project_id: int, data: ScanPartCreate, db: AsyncSession = Depends(get_db)
):
    return await part_service.create(db, project_id, data)


@router.get("/{part_id}", response_model=ScanPartRead)
async def get_part(project_id: int, part_id: int, db: AsyncSession = Depends(get_db)):
    return await part_service.get_by_id(db, project_id, part_id)


@router.put("/{part_id}", response_model=ScanPartRead)
async def update_part(
    project_id: int,
    part_id: int,
    data: ScanPartUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await part_service.update(db, project_id, part_id, data)


@router.delete("/{part_id}", status_code=204)
async def delete_part(
    project_id: int, part_id: int, db: AsyncSession = Depends(get_db)
):
    await part_service.delete(db, project_id, part_id)
    return Response(status_code=204)
