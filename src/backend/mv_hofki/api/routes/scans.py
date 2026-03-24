"""SheetMusicScan API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.sheet_music_scan import SheetMusicScanRead, SheetMusicScanUpdate
from mv_hofki.services import sheet_music_scan as scan_service

router = APIRouter(
    prefix="/api/v1/scanner/projects/{project_id}/parts/{part_id}/scans",
    tags=["scanner"],
)


@router.get("", response_model=list[SheetMusicScanRead])
async def list_scans(project_id: int, part_id: int, db: AsyncSession = Depends(get_db)):
    return await scan_service.get_list(db, project_id, part_id)


@router.post("", response_model=SheetMusicScanRead, status_code=201)
async def upload_scan(
    project_id: int,
    part_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    return await scan_service.upload(db, project_id, part_id, file)


@router.get("/{scan_id}", response_model=SheetMusicScanRead)
async def get_scan(
    project_id: int, part_id: int, scan_id: int, db: AsyncSession = Depends(get_db)
):
    return await scan_service.get_by_id(db, project_id, part_id, scan_id)


@router.put("/{scan_id}", response_model=SheetMusicScanRead)
async def update_scan(
    project_id: int,
    part_id: int,
    scan_id: int,
    data: SheetMusicScanUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await scan_service.update(db, project_id, part_id, scan_id, data)


@router.delete("/{scan_id}", status_code=204)
async def delete_scan(
    project_id: int, part_id: int, scan_id: int, db: AsyncSession = Depends(get_db)
):
    await scan_service.delete(db, project_id, part_id, scan_id)
    return Response(status_code=204)
