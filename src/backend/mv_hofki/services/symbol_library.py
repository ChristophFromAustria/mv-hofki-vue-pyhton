"""SymbolTemplate and SymbolVariant CRUD service."""

from __future__ import annotations

import shutil

import cv2
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.core.config import settings
from mv_hofki.models.sheet_music_scan import SheetMusicScan
from mv_hofki.models.symbol_template import SymbolTemplate
from mv_hofki.models.symbol_variant import SymbolVariant
from mv_hofki.schemas.symbol_template import SymbolTemplateCreate, SymbolTemplateUpdate


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


async def update_template(
    session: AsyncSession, template_id: int, data: SymbolTemplateUpdate
) -> SymbolTemplate:
    template = await get_template_by_id(session, template_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(template, key, value)
    await session.commit()
    await session.refresh(template)
    return template


async def delete_template(session: AsyncSession, template_id: int) -> None:
    template = await get_template_by_id(session, template_id)
    variant_dir = settings.PROJECT_ROOT / "data" / "symbol_library" / str(template_id)
    if variant_dir.exists():
        shutil.rmtree(variant_dir)
    await session.delete(template)
    await session.commit()


async def delete_variant(
    session: AsyncSession, template_id: int, variant_id: int
) -> None:
    await get_template_by_id(session, template_id)
    variant = await session.get(SymbolVariant, variant_id)
    if not variant or variant.template_id != template_id:
        raise HTTPException(status_code=404, detail="Variante nicht gefunden")
    file_path = settings.PROJECT_ROOT / variant.image_path
    if file_path.exists():
        file_path.unlink()
    await session.delete(variant)
    await session.commit()


async def crop_variant(
    session: AsyncSession,
    template_id: int,
    variant_id: int,
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    """Crop a variant image in-place."""
    await get_template_by_id(session, template_id)
    variant = await session.get(SymbolVariant, variant_id)
    if not variant or variant.template_id != template_id:
        raise HTTPException(status_code=404, detail="Variante nicht gefunden")

    file_path = settings.PROJECT_ROOT / variant.image_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Bilddatei nicht gefunden")

    img = cv2.imread(str(file_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise HTTPException(status_code=400, detail="Bild konnte nicht geladen werden")

    # Clamp coordinates
    y2 = min(img.shape[0], y + height)
    x2 = min(img.shape[1], x + width)
    cropped = img[max(0, y) : y2, max(0, x) : x2]
    if cropped.size == 0:
        raise HTTPException(status_code=400, detail="Ungültiger Ausschnitt")

    cv2.imwrite(str(file_path), cropped)


async def save_rendered_variant(
    session: AsyncSession,
    template_id: int,
    png_data: bytes,
    source: str,
    height_in_lines: float | None = None,
) -> SymbolTemplate:
    """Save rendered PNG bytes as a new variant for the given template."""
    import uuid

    template = await get_template_by_id(session, template_id)
    variant_dir = settings.PROJECT_ROOT / "data" / "symbol_library" / str(template_id)
    variant_dir.mkdir(parents=True, exist_ok=True)

    variant_filename = f"{uuid.uuid4().hex}.png"
    variant_path = variant_dir / variant_filename
    variant_path.write_bytes(png_data)

    variant = SymbolVariant(
        template_id=template_id,
        image_path=str(variant_path.relative_to(settings.PROJECT_ROOT)),
        source=source,
        height_in_lines=height_in_lines,
    )
    session.add(variant)
    await session.commit()
    await session.refresh(template)
    return template


async def capture_template(
    session: AsyncSession,
    *,
    scan_id: int,
    x: int,
    y: int,
    width: int,
    height: int,
    template_id: int | None = None,
    name: str | None = None,
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

    # Find existing template or create new one
    template: SymbolTemplate
    if template_id is not None:
        template = await get_template_by_id(session, template_id)
    else:
        existing = await session.execute(
            select(SymbolTemplate).where(SymbolTemplate.name == name)
        )
        found = existing.scalar_one_or_none()
        if found is not None:
            template = found
        else:
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
