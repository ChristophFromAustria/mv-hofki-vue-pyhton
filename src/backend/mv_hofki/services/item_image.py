"""ItemImage service."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.core.config import settings
from mv_hofki.models.item_image import ItemImage

UPLOAD_DIR = Path(settings.PROJECT_ROOT) / "data" / "uploads" / "images"
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _item_dir(item_id: int) -> Path:
    d = UPLOAD_DIR / str(item_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


async def get_all(session: AsyncSession, item_id: int) -> list[ItemImage]:
    result = await session.execute(
        select(ItemImage)
        .where(ItemImage.item_id == item_id)
        .order_by(ItemImage.is_profile.desc(), ItemImage.created_at)
    )
    return list(result.scalars().all())


async def upload(session: AsyncSession, item_id: int, file: UploadFile) -> ItemImage:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Ungültiger Dateityp")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Datei zu groß (max 10 MB)")

    ext = Path(file.filename or "image.jpg").suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = _item_dir(item_id) / filename
    dest.write_bytes(content)

    # If this is the first image, make it the profile
    existing = await get_all(session, item_id)
    is_profile = len(existing) == 0

    image = ItemImage(
        item_id=item_id,
        filename=filename,
        is_profile=is_profile,
    )
    session.add(image)
    await session.commit()
    await session.refresh(image)
    return image


async def set_profile(session: AsyncSession, item_id: int, image_id: int) -> ItemImage:
    # Unset all profile flags for this item
    await session.execute(
        update(ItemImage).where(ItemImage.item_id == item_id).values(is_profile=False)
    )
    image = await session.get(ItemImage, image_id)
    if not image or image.item_id != item_id:
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")
    image.is_profile = True
    await session.commit()
    await session.refresh(image)
    return image


async def delete(session: AsyncSession, item_id: int, image_id: int) -> None:
    image = await session.get(ItemImage, image_id)
    if not image or image.item_id != item_id:
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")

    # Delete file
    file_path = _item_dir(item_id) / image.filename
    if file_path.exists():
        file_path.unlink()

    was_profile = image.is_profile
    await session.delete(image)
    await session.commit()

    # If deleted image was profile, promote next image
    if was_profile:
        remaining = await get_all(session, item_id)
        if remaining:
            remaining[0].is_profile = True
            await session.commit()
