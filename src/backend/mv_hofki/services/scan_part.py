"""ScanPart CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scan_part import ScanPart
from mv_hofki.schemas.scan_part import ScanPartCreate, ScanPartUpdate
from mv_hofki.services import scan_project as project_service


async def get_list(session: AsyncSession, project_id: int) -> list[ScanPart]:
    await project_service.get_by_id(session, project_id)
    query = (
        select(ScanPart)
        .where(ScanPart.project_id == project_id)
        .order_by(ScanPart.part_order)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, project_id: int, part_id: int) -> ScanPart:
    part = await session.get(ScanPart, part_id)
    if not part or part.project_id != project_id:
        raise HTTPException(status_code=404, detail="Stimme nicht gefunden")
    return part


async def create(
    session: AsyncSession, project_id: int, data: ScanPartCreate
) -> ScanPart:
    await project_service.get_by_id(session, project_id)
    part = ScanPart(project_id=project_id, **data.model_dump())
    session.add(part)
    await session.commit()
    await session.refresh(part)
    return part


async def update(
    session: AsyncSession, project_id: int, part_id: int, data: ScanPartUpdate
) -> ScanPart:
    part = await get_by_id(session, project_id, part_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(part, key, value)
    await session.commit()
    await session.refresh(part)
    return part


async def delete(session: AsyncSession, project_id: int, part_id: int) -> None:
    part = await get_by_id(session, project_id, part_id)
    await session.delete(part)
    await session.commit()
