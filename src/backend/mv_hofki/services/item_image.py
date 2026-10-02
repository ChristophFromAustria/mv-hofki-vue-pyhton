"""ItemImage service."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.core.config import settings
from mv_hofki.db.soft_delete import utcnow
from mv_hofki.models.item_image import ItemImage

UPLOAD_DIR = Path(settings.PROJECT_ROOT) / "data" / "uploads" / "images"
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def item_dir(item_id: int) -> Path:
    d = UPLOAD_DIR / str(item_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


_item_dir = item_dir


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


async def _own_image(session: AsyncSession, item_id: int, image_id: int) -> ItemImage:
    image = await session.get(ItemImage, image_id)
    if not image or image.item_id != item_id:
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")
    return image


async def replace_file(
    session: AsyncSession, item_id: int, image_id: int, file: UploadFile
) -> ItemImage:
    """Store an edited version of an image under a new name (so browsers
    don't show a cached old one). The first edit keeps the original file;
    later edits replace only the previous edited file."""
    image = await _own_image(session, item_id, image_id)
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Ungültiger Dateityp")
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Datei zu groß (max 10 MB)")
    ext = {"image/png": ".png", "image/webp": ".webp"}.get(file.content_type, ".jpg")
    new_name = f"{uuid.uuid4().hex}{ext}"
    (_item_dir(item_id) / new_name).write_bytes(content)
    previous: str | None = image.filename
    if image.original_filename is None:
        image.original_filename = previous
        previous = None  # the original stays
    image.filename = new_name
    await session.commit()
    if previous:
        (UPLOAD_DIR / str(item_id) / previous).unlink(missing_ok=True)
    await session.refresh(image)
    return image


async def restore_original(
    session: AsyncSession, item_id: int, image_id: int
) -> ItemImage:
    """Back to the untouched upload; the edited file is removed."""
    image = await _own_image(session, item_id, image_id)
    if image.original_filename is None:
        raise HTTPException(status_code=409, detail="Bild ist nicht bearbeitet")
    edited = image.filename
    image.filename = image.original_filename
    image.original_filename = None
    await session.commit()
    (UPLOAD_DIR / str(item_id) / edited).unlink(missing_ok=True)
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

    # To the trash; the file stays until the image is deleted for good.
    was_profile = image.is_profile
    image.deleted_at = utcnow()
    image.is_profile = False
    await session.commit()

    # If deleted image was profile, promote next image
    if was_profile:
        remaining = await get_all(session, item_id)
        if remaining:
            remaining[0].is_profile = True
            await session.commit()


def image_file(image: ItemImage) -> Path:
    return UPLOAD_DIR / str(image.item_id) / image.filename


def image_files(image: ItemImage) -> list[Path]:
    """The shown file and, for an edited image, the kept original."""
    files = [image_file(image)]
    if image.original_filename:
        files.append(UPLOAD_DIR / str(image.item_id) / image.original_filename)
    return files
