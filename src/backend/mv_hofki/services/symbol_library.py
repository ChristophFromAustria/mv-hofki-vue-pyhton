"""SymbolTemplate and SymbolVariant CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.symbol_template import SymbolTemplate
from mv_hofki.models.symbol_variant import SymbolVariant
from mv_hofki.schemas.symbol_template import SymbolTemplateCreate


async def get_templates(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    category: str | None = None,
) -> tuple[list[SymbolTemplate], int]:
    query = select(SymbolTemplate)
    count_query = select(func.count()).select_from(SymbolTemplate)

    if category:
        query = query.where(SymbolTemplate.category == category)
        count_query = count_query.where(SymbolTemplate.category == category)

    total = (await session.execute(count_query)).scalar_one()
    query = (
        query.order_by(SymbolTemplate.category, SymbolTemplate.name)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(query)
    return list(result.scalars().all()), total


async def get_template_by_id(session: AsyncSession, template_id: int) -> SymbolTemplate:
    template = await session.get(SymbolTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Symbol-Vorlage nicht gefunden")
    return template


async def create_template(
    session: AsyncSession, data: SymbolTemplateCreate
) -> SymbolTemplate:
    template = SymbolTemplate(**data.model_dump())
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


async def get_variants(session: AsyncSession, template_id: int) -> list[SymbolVariant]:
    await get_template_by_id(session, template_id)
    query = (
        select(SymbolVariant)
        .where(SymbolVariant.template_id == template_id)
        .order_by(SymbolVariant.usage_count.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())
