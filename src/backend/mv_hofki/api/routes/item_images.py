"""ItemImage API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.item_image import ItemImageRead
from mv_hofki.services import item_image as image_service

router = APIRouter(
    prefix="/api/v1/items/{item_id}/images",
    tags=["item-images"],
)


def _image_to_read(image) -> ItemImageRead:
    return ItemImageRead(
        id=image.id,
        item_id=image.item_id,
        filename=image.filename,
        is_profile=image.is_profile,
        created_at=image.created_at,
        url=f"/uploads/images/{image.item_id}/{image.filename}",
    )


@router.get("", response_model=list[ItemImageRead])
async def list_images(item_id: int, db: AsyncSession = Depends(get_db)):
    images = await image_service.get_all(db, item_id)
    return [_image_to_read(img) for img in images]


@router.post("", response_model=ItemImageRead, status_code=201)
async def upload_image(
    item_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    image = await image_service.upload(db, item_id, file)
    return _image_to_read(image)


@router.put("/{image_id}/profile", response_model=ItemImageRead)
async def set_profile_image(
    item_id: int, image_id: int, db: AsyncSession = Depends(get_db)
):
    image = await image_service.set_profile(db, item_id, image_id)
    return _image_to_read(image)


@router.delete("/{image_id}", status_code=204)
async def delete_image(item_id: int, image_id: int, db: AsyncSession = Depends(get_db)):
    await image_service.delete(db, item_id, image_id)
    return Response(status_code=204)
