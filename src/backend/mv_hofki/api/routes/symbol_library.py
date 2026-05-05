"""Symbol library API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.pagination import PaginatedResponse
from mv_hofki.schemas.symbol_template import (
    SymbolTemplateCreate,
    SymbolTemplateRead,
    SymbolTemplateUpdate,
    VariantCropRequest,
)
from mv_hofki.schemas.symbol_variant import SymbolVariantRead
from mv_hofki.services import symbol_library as lib_service

router = APIRouter(prefix="/api/v1/scanner/library", tags=["scanner-library"])


@router.get("/templates", response_model=PaginatedResponse[SymbolTemplateRead])
async def list_templates(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    items, total = await lib_service.get_templates(
        db, limit=limit, offset=offset, category=category
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/templates", response_model=SymbolTemplateRead, status_code=201)
async def create_template(
    data: SymbolTemplateCreate, db: AsyncSession = Depends(get_db)
):
    return await lib_service.create_template(db, data)


@router.get("/templates/{template_id}", response_model=SymbolTemplateRead)
async def get_template(template_id: int, db: AsyncSession = Depends(get_db)):
    return await lib_service.get_template_by_id(db, template_id)


@router.get(
    "/templates/{template_id}/variants",
    response_model=list[SymbolVariantRead],
)
async def list_variants(template_id: int, db: AsyncSession = Depends(get_db)):
    return await lib_service.get_variants(db, template_id)


@router.put("/templates/{template_id}", response_model=SymbolTemplateRead)
async def update_template(
    template_id: int,
    data: SymbolTemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await lib_service.update_template(db, template_id, data)


@router.delete("/templates/{template_id}")
async def delete_template(template_id: int, db: AsyncSession = Depends(get_db)):
    await lib_service.delete_template(db, template_id)
    return {"status": "ok"}


@router.delete("/templates/{template_id}/variants/{variant_id}")
async def delete_variant(
    template_id: int, variant_id: int, db: AsyncSession = Depends(get_db)
):
    await lib_service.delete_variant(db, template_id, variant_id)
    return {"status": "ok"}


@router.post("/templates/{template_id}/variants/{variant_id}/crop")
async def crop_variant(
    template_id: int,
    variant_id: int,
    data: VariantCropRequest,
    db: AsyncSession = Depends(get_db),
):
    await lib_service.crop_variant(
        db, template_id, variant_id, data.x, data.y, data.width, data.height
    )
    return {"status": "ok"}


@router.post(
    "/templates/{template_id}/variants/upload",
    response_model=SymbolTemplateRead,
    status_code=201,
)
async def upload_variant(
    template_id: int,
    file: UploadFile,
    source_line_spacing: float = Form(...),
    source: str = Form("cropped"),
    height_in_lines: float | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload an image file as a new variant for the given template."""
    from fastapi import HTTPException

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Leere Datei")
    return await lib_service.save_rendered_variant(
        db,
        template_id,
        content,
        source=source,
        height_in_lines=height_in_lines,
        source_line_spacing=source_line_spacing,
    )


@router.post(
    "/templates/upload-new",
    response_model=SymbolTemplateRead,
    status_code=201,
)
async def upload_variant_new_template(
    file: UploadFile,
    source_line_spacing: float = Form(...),
    name: str = Form(...),
    category: str = Form(...),
    source: str = Form("user_capture"),
    height_in_lines: float | None = Form(None),
    musicxml_element: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload an image as the first variant of a new template (created inline)."""
    from fastapi import HTTPException

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Leere Datei")

    template = await lib_service.find_or_create_template(
        db,
        name=name,
        category=category,
        musicxml_element=musicxml_element,
    )
    return await lib_service.save_rendered_variant(
        db,
        template.id,
        content,
        source=source,
        height_in_lines=height_in_lines,
        source_line_spacing=source_line_spacing,
    )


class RenderRequest(BaseModel):
    code: str | None = None


@router.post(
    "/templates/{template_id}/render-musicxml",
    response_model=SymbolTemplateRead,
)
async def render_musicxml_endpoint(
    template_id: int,
    body: RenderRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Render MusicXML to a PNG variant.

    Uses body.code if provided, else the template's stored field.
    """
    from fastapi import HTTPException

    from mv_hofki.services.notation_renderer import render_musicxml

    template = await lib_service.get_template_by_id(db, template_id)
    code = (body.code if body and body.code else None) or template.musicxml_element
    if not code:
        raise HTTPException(status_code=400, detail="Kein MusicXML-Element vorhanden")
    result = render_musicxml(code)
    return await lib_service.save_rendered_variant(
        db,
        template_id,
        result.png_data,
        source="rendered_musicxml",
        height_in_lines=result.height_in_lines,
        source_line_spacing=result.source_line_spacing or 0,
    )


@router.post(
    "/templates/{template_id}/render-lilypond",
    response_model=SymbolTemplateRead,
)
async def render_lilypond_endpoint(
    template_id: int,
    body: RenderRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Render LilyPond to a PNG variant.

    Uses body.code if provided, else the template's stored field.
    """
    from fastapi import HTTPException

    from mv_hofki.services.notation_renderer import render_lilypond

    template = await lib_service.get_template_by_id(db, template_id)
    code = (body.code if body and body.code else None) or template.lilypond_token
    if not code:
        raise HTTPException(status_code=400, detail="Kein LilyPond-Token vorhanden")
    result = render_lilypond(code)
    return await lib_service.save_rendered_variant(
        db,
        template_id,
        result.png_data,
        source="rendered_lilypond",
        height_in_lines=result.height_in_lines,
        source_line_spacing=result.source_line_spacing or 0,
    )
