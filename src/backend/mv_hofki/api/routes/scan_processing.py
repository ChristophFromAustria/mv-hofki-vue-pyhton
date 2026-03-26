"""Scan processing API routes — trigger pipeline and poll status."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.detected_staff import DetectedStaffRead
from mv_hofki.schemas.detected_symbol import DetectedSymbolRead, SymbolCorrectionRequest
from mv_hofki.schemas.scanner_config import ScannerConfigUpdate
from mv_hofki.schemas.sheet_music_scan import ScanStatusRead
from mv_hofki.services import sheet_music_scan as scan_service

router = APIRouter(prefix="/api/v1/scanner", tags=["scanner-processing"])

logger = logging.getLogger(__name__)


@router.post("/scans/{scan_id}/process", response_model=ScanStatusRead)
async def trigger_processing(
    scan_id: int,
    config_overrides: ScannerConfigUpdate | None = None,
    project_id: int | None = None,
    part_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Trigger the processing pipeline for a scan."""
    from mv_hofki.models.scan_part import ScanPart
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    if scan.status == "processing":
        raise HTTPException(status_code=409, detail="Scan wird bereits verarbeitet")

    # Resolve project_id and part_id from scan
    part = await db.get(ScanPart, scan.part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Scan-Part nicht gefunden")
    actual_project_id = part.project_id
    actual_part_id = part.id

    scan.status = "processing"
    await db.commit()

    try:
        await scan_service.run_pipeline(
            db,
            actual_project_id,
            actual_part_id,
            scan_id,
            config_overrides=config_overrides,
        )
    except Exception:
        scan.status = "uploaded"
        await db.commit()
        raise

    await db.refresh(scan)
    return ScanStatusRead(status=scan.status, current_stage=None, progress=1.0)


@router.get("/scans/{scan_id}/status", response_model=ScanStatusRead)
async def get_processing_status(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Poll processing status."""
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    return ScanStatusRead(status=scan.status)


@router.get("/scans/{scan_id}/staves", response_model=list[DetectedStaffRead])
async def get_detected_staves(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Get all detected staves for a scan."""
    from sqlalchemy import select

    from mv_hofki.models.detected_staff import DetectedStaff
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    result = await db.execute(
        select(DetectedStaff)
        .where(DetectedStaff.scan_id == scan_id)
        .order_by(DetectedStaff.staff_index)
    )
    return list(result.scalars().all())


@router.get("/scans/{scan_id}/symbols", response_model=list[DetectedSymbolRead])
async def get_detected_symbols(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Get all detected symbols for a scan, including alternative matches."""
    import json

    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from mv_hofki.models.detected_staff import DetectedStaff
    from mv_hofki.models.detected_symbol import DetectedSymbol
    from mv_hofki.models.sheet_music_scan import SheetMusicScan
    from mv_hofki.models.symbol_template import SymbolTemplate
    from mv_hofki.schemas.detected_symbol import AlternativeMatch

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    result = await db.execute(
        select(DetectedSymbol)
        .join(DetectedStaff)
        .where(DetectedStaff.scan_id == scan_id)
        .options(
            joinedload(DetectedSymbol.matched_symbol),
            joinedload(DetectedSymbol.corrected_symbol),
        )
        .order_by(DetectedSymbol.sequence_order)
    )
    symbols = list(result.scalars().unique().all())

    # Collect all template IDs referenced in alternatives
    alt_template_ids: set[int] = set()
    for sym in symbols:
        if sym.alternatives_json:
            try:
                for tid, _conf in json.loads(sym.alternatives_json):
                    alt_template_ids.add(tid)
            except (json.JSONDecodeError, ValueError):
                pass

    # Resolve template names in bulk
    template_names: dict[int, str] = {}
    if alt_template_ids:
        tpl_result = await db.execute(
            select(SymbolTemplate.id, SymbolTemplate.display_name).where(
                SymbolTemplate.id.in_(alt_template_ids)
            )
        )
        template_names = {row[0]: row[1] for row in tpl_result.all()}

    # Build response with resolved alternatives
    out = []
    for sym in symbols:
        data = DetectedSymbolRead.model_validate(sym)
        if sym.alternatives_json:
            try:
                raw = json.loads(sym.alternatives_json)
                data.alternatives = [
                    AlternativeMatch(
                        template_id=tid,
                        confidence=conf,
                        display_name=template_names.get(tid),
                    )
                    for tid, conf in raw
                ]
            except (json.JSONDecodeError, ValueError):
                pass
        out.append(data)
    return out


@router.put("/symbols/{symbol_id}/correct")
async def correct_symbol(
    symbol_id: int,
    data: SymbolCorrectionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Correct a symbol's match — sets user_corrected_symbol_id and user_verified."""
    from mv_hofki.models.detected_staff import DetectedStaff
    from mv_hofki.models.detected_symbol import DetectedSymbol
    from mv_hofki.models.symbol_variant import SymbolVariant

    symbol = await db.get(DetectedSymbol, symbol_id)
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol nicht gefunden")

    symbol.user_corrected_symbol_id = data.symbol_template_id
    symbol.user_verified = True

    # Feedback loop: add snippet as new variant of the corrected template
    if symbol.snippet_path:
        staff = await db.get(DetectedStaff, symbol.staff_id)
        source_line_spacing = staff.line_spacing if staff else 0.0

        if source_line_spacing > 5:
            variant = SymbolVariant(
                template_id=data.symbol_template_id,
                image_path=symbol.snippet_path,
                source="user_correction",
                source_line_spacing=source_line_spacing,
            )
            db.add(variant)
        else:
            logger.warning(
                "Skipping variant creation for symbol %d: "
                "source_line_spacing=%.1f is too low",
                symbol_id,
                source_line_spacing,
            )

    await db.commit()
    return {"status": "ok"}


@router.put("/symbols/{symbol_id}/verify")
async def verify_symbol(symbol_id: int, db: AsyncSession = Depends(get_db)):
    """Confirm a symbol's automatic match as correct."""
    from mv_hofki.models.detected_symbol import DetectedSymbol

    symbol = await db.get(DetectedSymbol, symbol_id)
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol nicht gefunden")

    symbol.user_verified = True
    await db.commit()
    return {"status": "ok"}
