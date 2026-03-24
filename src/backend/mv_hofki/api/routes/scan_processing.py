"""Scan processing API routes — trigger pipeline and poll status."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.detected_staff import DetectedStaffRead
from mv_hofki.schemas.detected_symbol import DetectedSymbolRead, SymbolCorrectionRequest
from mv_hofki.schemas.sheet_music_scan import ScanStatusRead

router = APIRouter(prefix="/api/v1/scanner", tags=["scanner-processing"])

logger = logging.getLogger(__name__)


@router.post("/scans/{scan_id}/process", response_model=ScanStatusRead)
async def trigger_processing(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Trigger the processing pipeline for a scan.

    This is a placeholder that sets the status to 'processing'.
    The actual pipeline integration will connect the stages to this endpoint.
    """
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    if scan.status not in ("uploaded", "review", "completed"):
        raise HTTPException(status_code=409, detail="Scan wird bereits verarbeitet")

    scan.status = "processing"
    await db.commit()
    await db.refresh(scan)

    # TODO: actual pipeline execution will be added here
    # For now, just set status back to review as placeholder
    scan.status = "review"
    await db.commit()

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

    symbol = await db.get(DetectedSymbol, symbol_id)
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol nicht gefunden")

    symbol.user_corrected_symbol_id = data.symbol_template_id
    symbol.user_verified = True
    await db.commit()
    await db.refresh(symbol)
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
