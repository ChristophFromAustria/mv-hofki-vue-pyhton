"""SymbolTemplate and SymbolVariant CRUD service."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field

import cv2
import numpy as np
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.core.config import settings
from mv_hofki.models.symbol_template import SymbolTemplate
from mv_hofki.models.symbol_variant import SymbolVariant
from mv_hofki.schemas.symbol_template import SymbolTemplateCreate, SymbolTemplateUpdate
from mv_hofki.services.notation_renderer import _trim_whitespace


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


async def get_categories(session: AsyncSession) -> list[dict]:
    """Return all distinct categories in use with their template counts."""
    query = (
        select(SymbolTemplate.category, func.count(SymbolTemplate.id))
        .group_by(SymbolTemplate.category)
        .order_by(SymbolTemplate.category)
    )
    result = await session.execute(query)
    return [{"category": cat, "count": count} for cat, count in result.all()]


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


async def find_or_create_template(
    session: AsyncSession,
    *,
    name: str,
    category: str,
    musicxml_element: str | None = None,
) -> SymbolTemplate:
    """Find an existing template by name, or create a new one."""
    existing = await session.execute(
        select(SymbolTemplate).where(SymbolTemplate.name == name)
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found

    template = SymbolTemplate(
        category=category,
        name=name,
        display_name=name,
        musicxml_element=musicxml_element,
        is_seed=False,
    )
    session.add(template)
    await session.flush()
    return template


async def save_rendered_variant(
    session: AsyncSession,
    template_id: int,
    png_data: bytes,
    source: str,
    height_in_lines: float | None = None,
    source_line_spacing: float = 0.0,
) -> SymbolTemplate:
    """Save rendered PNG bytes as a new variant for the given template."""
    import uuid

    if not source_line_spacing or source_line_spacing <= 5:
        raise HTTPException(
            status_code=400,
            detail="source_line_spacing ist erforderlich und muss > 5 sein",
        )

    # Auto-crop whitespace from the template image
    png_data = _trim_whitespace(png_data)

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
        source_line_spacing=source_line_spacing,
    )
    session.add(variant)
    await session.commit()
    await session.refresh(template)
    return template


# ── Tight cropping of variant images ─────────────────────────────────────


@dataclass
class TightenResult:
    checked: int = 0
    cropped: int = 0
    unchanged: int = 0
    skipped: list[str] = field(default_factory=list)


def tight_symbol_bbox(
    img: np.ndarray, *, threshold: int = 128, line_fill: float = 0.75
) -> tuple[int, int, int, int] | None:
    """Bounding box (x, y, w, h) of the symbol's ink, ignoring staff lines.

    Rows that are inked almost across the full width are staff lines (or
    ledger lines) and must not define the box, otherwise a variant with a
    lot of empty staff above or below the symbol would never get tighter.
    Thick full-width runs (a note head in a very tight crop) are kept.
    """
    gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    dark = np.asarray(gray < threshold, dtype=np.uint8)
    h, w = dark.shape
    row_counts = [int(v) for v in np.asarray(dark.sum(axis=1)).tolist()]
    max_line_rows = max(3, int(round(0.08 * h)))
    keep_rows = [True] * h
    r = 0
    while r < h:
        if row_counts[r] >= line_fill * w:
            start = r
            while r < h and row_counts[r] >= line_fill * w:
                r += 1
            if r - start <= max_line_rows:
                for rr in range(max(0, start - 1), min(h, r + 1)):
                    keep_rows[rr] = False
        else:
            r += 1
    mask = dark.copy()
    for rr, keep in enumerate(keep_rows):
        if not keep:
            mask[rr, :] = 0
    ys = [i for i, v in enumerate(np.asarray(mask.sum(axis=1)).tolist()) if v > 0]
    xs = [i for i, v in enumerate(np.asarray(mask.sum(axis=0)).tolist()) if v > 0]
    if not ys or not xs:
        return None
    return xs[0], ys[0], xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1


async def tighten_all_variants(
    session: AsyncSession,
    *,
    categories: tuple[str, ...] = ("note", "rest"),
    padding: int = 1,
) -> TightenResult:
    """Crop every variant image of the given categories to its ink.

    The point is consistency: when every note variant ends exactly at the
    note head, the head sits at a fixed offset from the box edge and the
    pitch derived from a detection box is reliable. ``height_in_lines`` is
    recomputed from the new height. The original file is kept once under
    ``data/symbol_library/_backup/``.
    """
    result = TightenResult()
    rows = await session.execute(
        select(SymbolVariant, SymbolTemplate.category, SymbolTemplate.display_name)
        .join(SymbolTemplate, SymbolTemplate.id == SymbolVariant.template_id)
        .where(SymbolTemplate.category.in_(categories))
    )
    backup_root = settings.PROJECT_ROOT / "data" / "symbol_library" / "_backup"
    for variant, _category, display_name in rows.all():
        result.checked += 1
        path = settings.PROJECT_ROOT / variant.image_path
        img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if img is None:
            result.skipped.append(f"{display_name} #{variant.id}: Bild fehlt")
            continue
        bbox = tight_symbol_bbox(img)
        if bbox is None:
            result.skipped.append(f"{display_name} #{variant.id}: keine Tinte")
            continue
        x, y, w, h = bbox
        h_img, w_img = img.shape[:2]
        x0, y0 = max(0, x - padding), max(0, y - padding)
        x1, y1 = min(w_img, x + w + padding), min(h_img, y + h + padding)
        if (x0, y0, x1, y1) == (0, 0, w_img, h_img):
            result.unchanged += 1
            continue
        backup = backup_root / str(variant.template_id) / path.name
        if not backup.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
        cv2.imwrite(str(path), img[y0:y1, x0:x1])
        if variant.source_line_spacing and variant.source_line_spacing > 0:
            variant.height_in_lines = round((y1 - y0) / variant.source_line_spacing, 1)
        result.cropped += 1
    await session.commit()
    return result
