"""SymbolTemplate and SymbolVariant CRUD service."""

from __future__ import annotations

import cv2
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.core.config import settings
from mv_hofki.models.sheet_music_scan import SheetMusicScan
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


async def capture_template(
    session: AsyncSession,
    *,
    scan_id: int,
    x: int,
    y: int,
    width: int,
    height: int,
    name: str,
    category: str,
    musicxml_element: str | None,
    height_in_lines: float,
) -> SymbolTemplate:
    """Capture a template from a scan region."""
    import json
    import uuid

    scan = await session.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    # Load the scan image
    img_path = settings.PROJECT_ROOT / scan.image_path
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise HTTPException(status_code=400, detail="Bild konnte nicht geladen werden")

    # Apply threshold if stored in adjustments
    adjustments = json.loads(scan.adjustments_json) if scan.adjustments_json else {}
    threshold_val = adjustments.get("threshold")
    if threshold_val is not None:
        _, img = cv2.threshold(img, int(threshold_val), 255, cv2.THRESH_BINARY)

    # Crop the region
    crop = img[y : y + height, x : x + width]
    if crop.size == 0:
        raise HTTPException(status_code=400, detail="Ungültiger Ausschnitt")

    # Create or find template
    existing = await session.execute(
        select(SymbolTemplate).where(SymbolTemplate.name == name)
    )
    template = existing.scalar_one_or_none()
    if template is None:
        template = SymbolTemplate(
            category=category,
            name=name,
            display_name=name,
            musicxml_element=musicxml_element,
            is_seed=False,
        )
        session.add(template)
        await session.flush()

    # Save variant image
    variant_dir = settings.PROJECT_ROOT / "data" / "symbol_library" / str(template.id)
    variant_dir.mkdir(parents=True, exist_ok=True)

    variant_filename = f"{uuid.uuid4().hex}.png"
    variant_path = variant_dir / variant_filename
    cv2.imwrite(str(variant_path), crop)

    variant = SymbolVariant(
        template_id=template.id,
        image_path=str(variant_path.relative_to(settings.PROJECT_ROOT)),
        source="user_capture",
        height_in_lines=height_in_lines,
    )
    session.add(variant)
    await session.commit()
    await session.refresh(template)
    return template
