"""Symbol library API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.pagination import PaginatedResponse
from mv_hofki.schemas.symbol_template import (
    SymbolTemplateCreate,
    SymbolTemplateRead,
    SymbolTemplateUpdate,
    TemplateCaptureRequest,
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


@router.post("/templates/capture", response_model=SymbolTemplateRead, status_code=201)
async def capture_template(
    data: TemplateCaptureRequest, db: AsyncSession = Depends(get_db)
):
    return await lib_service.capture_template(
        db,
        scan_id=data.scan_id,
        x=data.x,
        y=data.y,
        width=data.width,
        height=data.height,
        template_id=data.template_id,
        name=data.name,
        category=data.category,
        musicxml_element=data.musicxml_element,
        height_in_lines=data.height_in_lines,
    )


@router.post(
    "/templates/{template_id}/render-musicxml",
    response_model=SymbolTemplateRead,
)
async def render_musicxml_endpoint(
    template_id: int, db: AsyncSession = Depends(get_db)
):
    """Render the template's MusicXML to a PNG variant."""
    from fastapi import HTTPException

    from mv_hofki.services.notation_renderer import render_musicxml

    template = await lib_service.get_template_by_id(db, template_id)
    if not template.musicxml_element:
        raise HTTPException(status_code=400, detail="Kein MusicXML-Element vorhanden")
    png_data = render_musicxml(template.musicxml_element)
    return await lib_service.save_rendered_variant(
        db, template_id, png_data, source="rendered_musicxml"
    )


@router.post(
    "/templates/{template_id}/render-lilypond",
    response_model=SymbolTemplateRead,
)
async def render_lilypond_endpoint(
    template_id: int, db: AsyncSession = Depends(get_db)
):
    """Render the template's LilyPond token to a PNG variant."""
    from fastapi import HTTPException

    from mv_hofki.services.notation_renderer import render_lilypond

    template = await lib_service.get_template_by_id(db, template_id)
    if not template.lilypond_token:
        raise HTTPException(status_code=400, detail="Kein LilyPond-Token vorhanden")
    png_data = render_lilypond(template.lilypond_token)
    return await lib_service.save_rendered_variant(
        db, template_id, png_data, source="rendered_lilypond"
    )
