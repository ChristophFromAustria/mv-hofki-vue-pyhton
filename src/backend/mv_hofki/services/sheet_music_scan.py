"""SheetMusicScan CRUD + upload service."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.core.config import settings
from mv_hofki.models.sheet_music_scan import SheetMusicScan
from mv_hofki.schemas.sheet_music_scan import SheetMusicScanUpdate
from mv_hofki.services import scan_part as part_service

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/tiff"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

_SCANS_ROOT = settings.PROJECT_ROOT / "data" / "scans"


def _scan_dir(project_id: int, part_id: int, scan_id: int) -> Path:
    return _SCANS_ROOT / str(project_id) / str(part_id) / str(scan_id)


async def get_list(
    session: AsyncSession, project_id: int, part_id: int
) -> list[SheetMusicScan]:
    await part_service.get_by_id(session, project_id, part_id)
    query = (
        select(SheetMusicScan)
        .where(SheetMusicScan.part_id == part_id)
        .order_by(SheetMusicScan.page_number)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_by_id(
    session: AsyncSession, project_id: int, part_id: int, scan_id: int
) -> SheetMusicScan:
    scan = await session.get(SheetMusicScan, scan_id)
    if not scan or scan.part_id != part_id:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")
    await part_service.get_by_id(session, project_id, part_id)
    return scan


async def upload(
    session: AsyncSession,
    project_id: int,
    part_id: int,
    file: UploadFile,
) -> SheetMusicScan:
    await part_service.get_by_id(session, project_id, part_id)

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Ungültiger Dateityp: {file.content_type}. Erlaubt: PNG, JPEG, TIFF"
            ),
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Datei zu groß (max. 50 MB)")

    # Determine next page number
    count_result = await session.execute(
        select(func.count()).where(SheetMusicScan.part_id == part_id)
    )
    page_number = count_result.scalar_one() + 1

    # Create DB record first to get ID
    ext = Path(file.filename or "upload.png").suffix or ".png"
    scan = SheetMusicScan(
        part_id=part_id,
        page_number=page_number,
        original_filename=file.filename or "upload.png",
        image_path="",  # placeholder, updated after save
        status="uploaded",
    )
    session.add(scan)
    await session.flush()

    # Save file
    scan_directory = _scan_dir(project_id, part_id, scan.id)
    scan_directory.mkdir(parents=True, exist_ok=True)
    filename = f"original{ext}"
    file_path = scan_directory / filename
    file_path.write_bytes(content)

    scan.image_path = str(file_path.relative_to(settings.PROJECT_ROOT))
    await session.commit()
    await session.refresh(scan)
    return scan


async def update(
    session: AsyncSession,
    project_id: int,
    part_id: int,
    scan_id: int,
    data: SheetMusicScanUpdate,
) -> SheetMusicScan:
    scan = await get_by_id(session, project_id, part_id, scan_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(scan, key, value)
    await session.commit()
    await session.refresh(scan)
    return scan


async def delete(
    session: AsyncSession, project_id: int, part_id: int, scan_id: int
) -> None:
    scan = await get_by_id(session, project_id, part_id, scan_id)
    scan_directory = _scan_dir(project_id, part_id, scan_id)
    if scan_directory.exists():
        shutil.rmtree(scan_directory)
    await session.delete(scan)
    await session.commit()
