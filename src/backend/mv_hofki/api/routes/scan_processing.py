"""Scan processing API routes — trigger pipeline and poll status."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.detected_staff import DetectedStaffRead
from mv_hofki.schemas.detected_symbol import DetectedSymbolRead, SymbolCorrectionRequest
from mv_hofki.schemas.sheet_music_scan import ScanStatusRead
from mv_hofki.services import sheet_music_scan as scan_service

router = APIRouter(prefix="/api/v1/scanner", tags=["scanner-processing"])

logger = logging.getLogger(__name__)


@router.post("/scans/{scan_id}/process", response_model=ScanStatusRead)
async def trigger_processing(
    scan_id: int,
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
        await scan_service.run_pipeline(db, actual_project_id, actual_part_id, scan_id)
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
    """Get all detected symbols for a scan."""
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from mv_hofki.models.detected_staff import DetectedStaff
    from mv_hofki.models.detected_symbol import DetectedSymbol
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

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
    return list(result.scalars().unique().all())


@router.put("/symbols/{symbol_id}/correct")
async def correct_symbol(
    symbol_id: int,
    data: SymbolCorrectionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Correct a symbol's match — sets user_corrected_symbol_id and user_verified."""
    from mv_hofki.models.detected_symbol import DetectedSymbol
    from mv_hofki.models.symbol_variant import SymbolVariant

    symbol = await db.get(DetectedSymbol, symbol_id)
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol nicht gefunden")

    symbol.user_corrected_symbol_id = data.symbol_template_id
    symbol.user_verified = True

    # Feedback loop: add snippet as new variant of the corrected template
    if symbol.snippet_path:
        variant = SymbolVariant(
            template_id=data.symbol_template_id,
            image_path=symbol.snippet_path,
            source="user_correction",
        )
        db.add(variant)

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
