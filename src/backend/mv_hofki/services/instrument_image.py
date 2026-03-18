"""InstrumentImage service."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.core.config import settings
from mv_hofki.models.instrument_image import InstrumentImage

UPLOAD_DIR = Path(settings.PROJECT_ROOT) / "data" / "uploads" / "instruments"
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _instrument_dir(instrument_id: int) -> Path:
    d = UPLOAD_DIR / str(instrument_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


async def get_all(session: AsyncSession, instrument_id: int) -> list[InstrumentImage]:
    result = await session.execute(
        select(InstrumentImage)
        .where(InstrumentImage.instrument_id == instrument_id)
        .order_by(InstrumentImage.is_profile.desc(), InstrumentImage.created_at)
    )
    return list(result.scalars().all())


async def upload(
    session: AsyncSession, instrument_id: int, file: UploadFile
) -> InstrumentImage:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Ungültiger Dateityp")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Datei zu groß (max 10 MB)")

    ext = Path(file.filename or "image.jpg").suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = _instrument_dir(instrument_id) / filename
    dest.write_bytes(content)

    # If this is the first image, make it the profile
    existing = await get_all(session, instrument_id)
    is_profile = len(existing) == 0

    image = InstrumentImage(
        instrument_id=instrument_id,
        filename=filename,
        is_profile=is_profile,
    )
    session.add(image)
    await session.commit()
    await session.refresh(image)
    return image


async def set_profile(
    session: AsyncSession, instrument_id: int, image_id: int
) -> InstrumentImage:
    # Unset all profile flags for this instrument
    await session.execute(
        update(InstrumentImage)
        .where(InstrumentImage.instrument_id == instrument_id)
        .values(is_profile=False)
    )
    image = await session.get(InstrumentImage, image_id)
    if not image or image.instrument_id != instrument_id:
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")
    image.is_profile = True
    await session.commit()
    await session.refresh(image)
    return image


async def delete(session: AsyncSession, instrument_id: int, image_id: int) -> None:
    image = await session.get(InstrumentImage, image_id)
    if not image or image.instrument_id != instrument_id:
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")

    # Delete file
    file_path = _instrument_dir(instrument_id) / image.filename
    if file_path.exists():
        file_path.unlink()

    was_profile = image.is_profile
    await session.delete(image)
    await session.commit()

    # If deleted image was profile, promote next image
    if was_profile:
        remaining = await get_all(session, instrument_id)
        if remaining:
            remaining[0].is_profile = True
            await session.commit()
