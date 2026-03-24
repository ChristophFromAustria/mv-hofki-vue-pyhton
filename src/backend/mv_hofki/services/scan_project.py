"""ScanProject CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scan_project import ScanProject
from mv_hofki.schemas.scan_project import ScanProjectCreate, ScanProjectUpdate


async def get_list(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
) -> tuple[list[ScanProject], int]:
    query = select(ScanProject)
    count_query = select(func.count()).select_from(ScanProject)

    if search:
        pattern = f"%{search}%"
        search_filter = ScanProject.name.ilike(pattern)
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = (await session.execute(count_query)).scalar_one()
    query = query.order_by(ScanProject.updated_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars().all()), total


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
