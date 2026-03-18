"""InstrumentImage API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.instrument_image import InstrumentImageRead
from mv_hofki.services import instrument_image as image_service

router = APIRouter(
    prefix="/api/v1/instruments/{instrument_id}/images",
    tags=["instrument-images"],
)


def _image_to_read(image) -> InstrumentImageRead:
    return InstrumentImageRead(
        id=image.id,
        instrument_id=image.instrument_id,
        filename=image.filename,
        is_profile=image.is_profile,
        created_at=image.created_at,
        url=f"/uploads/instruments/{image.instrument_id}/{image.filename}",
    )


@router.get("", response_model=list[InstrumentImageRead])
async def list_images(instrument_id: int, db: AsyncSession = Depends(get_db)):
    images = await image_service.get_all(db, instrument_id)
    return [_image_to_read(img) for img in images]


@router.post("", response_model=InstrumentImageRead, status_code=201)
async def upload_image(
    instrument_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    image = await image_service.upload(db, instrument_id, file)
    return _image_to_read(image)


@router.put("/{image_id}/profile", response_model=InstrumentImageRead)
async def set_profile_image(
    instrument_id: int, image_id: int, db: AsyncSession = Depends(get_db)
):
    image = await image_service.set_profile(db, instrument_id, image_id)
    return _image_to_read(image)


@router.delete("/{image_id}", status_code=204)
async def delete_image(
    instrument_id: int, image_id: int, db: AsyncSession = Depends(get_db)
):
    await image_service.delete(db, instrument_id, image_id)
    return Response(status_code=204)
