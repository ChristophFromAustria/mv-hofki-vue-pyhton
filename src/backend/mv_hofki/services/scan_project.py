"""ScanProject CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scan_part import ScanPart
from mv_hofki.models.scan_project import ScanProject
from mv_hofki.models.sheet_music_scan import SheetMusicScan
from mv_hofki.schemas.scan_project import ScanProjectCreate, ScanProjectUpdate


async def get_list(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
) -> tuple[list, int]:
    count_query = select(func.count()).select_from(ScanProject)

    if search:
        pattern = f"%{search}%"
        count_query = count_query.where(ScanProject.name.ilike(pattern))

    total = (await session.execute(count_query)).scalar_one()

    # Build query with aggregated stats
    query = (
        select(
            ScanProject,
            func.count(func.distinct(ScanPart.id)).label("part_count"),
            func.count(SheetMusicScan.id).label("scan_count"),
            func.sum(case((SheetMusicScan.status == "uploaded", 1), else_=0)).label(
                "status_uploaded"
            ),
            func.sum(case((SheetMusicScan.status == "review", 1), else_=0)).label(
                "status_review"
            ),
            func.sum(case((SheetMusicScan.status == "processing", 1), else_=0)).label(
                "status_processing"
            ),
            func.sum(case((SheetMusicScan.status == "error", 1), else_=0)).label(
                "status_error"
            ),
        )
        .outerjoin(ScanPart, ScanPart.project_id == ScanProject.id)
        .outerjoin(SheetMusicScan, SheetMusicScan.part_id == ScanPart.id)
        .group_by(ScanProject.id)
    )

    if search:
        pattern = f"%{search}%"
        query = query.where(ScanProject.name.ilike(pattern))

    query = query.order_by(ScanProject.updated_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(query)).all()

    items = []
    for row in rows:
        project = row[0]
        project.part_count = row.part_count or 0
        project.scan_count = row.scan_count or 0
        project.status_uploaded = row.status_uploaded or 0
        project.status_review = row.status_review or 0
        project.status_processing = row.status_processing or 0
        project.status_error = row.status_error or 0
        items.append(project)

    return items, total


async def get_by_id(session: AsyncSession, project_id: int) -> ScanProject:
    project = await session.get(ScanProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Scan-Projekt nicht gefunden")
    return project


async def create(session: AsyncSession, data: ScanProjectCreate) -> ScanProject:
    project = ScanProject(**data.model_dump())
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def update(
    session: AsyncSession, project_id: int, data: ScanProjectUpdate
) -> ScanProject:
    project = await get_by_id(session, project_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    await session.commit()
    await session.refresh(project)
    return project


async def delete(session: AsyncSession, project_id: int) -> None:
    project = await get_by_id(session, project_id)
    await session.delete(project)
    await session.commit()
