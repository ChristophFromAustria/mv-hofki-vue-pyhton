"""Scan processing API routes — trigger pipeline and poll status."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.detected_measure import DetectedMeasureRead
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
        await scan_service.run_pipeline(
            db,
            actual_project_id,
            actual_part_id,
            scan_id,
        )
    except Exception:
        scan.status = "error"
        await db.commit()
        raise

    await db.refresh(scan)
    return ScanStatusRead(status=scan.status, current_stage=None, progress=1.0)


class PreviewRequest(BaseModel):
    adjustments_json: str | None = None


@router.post("/scans/{scan_id}/preview")
async def preview_preprocessing(
    scan_id: int,
    body: PreviewRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Run only preprocessing and return the processed image path."""
    adjustments = body.adjustments_json if body else None
    path = await scan_service.run_preview(db, scan_id, adjustments_json=adjustments)
    return {"processed_image_path": path}


@router.get("/scans/{scan_id}/process-stream")
async def stream_processing(
    scan_id: int,
    db: AsyncSession = Depends(get_db),
):
    """SSE endpoint: run the pipeline and stream log events in real time.

    Event types:
      - ``log``  — pipeline progress message (data: text)
      - ``done`` — pipeline finished successfully (data: JSON status)
      - ``error``— pipeline failed (data: error message)
    """
    import asyncio
    import json as _json

    from fastapi.responses import StreamingResponse

    from mv_hofki.models.scan_part import ScanPart
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    if scan.status == "processing":
        raise HTTPException(status_code=409, detail="Scan wird bereits verarbeitet")

    part = await db.get(ScanPart, scan.part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Scan-Part nicht gefunden")
    actual_project_id = part.project_id
    actual_part_id = part.id

    scan.status = "processing"
    await db.commit()

    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def log_callback(message: str) -> None:
        """Called from pipeline (possibly in a worker thread)."""
        queue.put_nowait(message)

    async def run_and_signal() -> None:
        try:
            await scan_service.run_pipeline(
                db,
                actual_project_id,
                actual_part_id,
                scan_id,
                log_callback=log_callback,
            )
            queue.put_nowait(None)  # sentinel: success
        except Exception as exc:
            queue.put_nowait(f"__ERROR__:{exc}")

    async def event_generator():
        task = asyncio.create_task(run_and_signal())
        try:
            while True:
                msg = await queue.get()
                if msg is None:
                    await db.refresh(scan)
                    yield (
                        f"event: done\n"
                        f"data: {_json.dumps({'status': scan.status})}\n\n"
                    )
                    break
                if msg.startswith("__ERROR__:"):
                    error_text = msg[len("__ERROR__:") :]
                    scan.status = "error"
                    await db.commit()
                    yield f"event: error\ndata: {error_text}\n\n"
                    break
                yield f"event: log\ndata: {msg}\n\n"
        except asyncio.CancelledError:
            task.cancel()
            # Connection dropped — reset status so it doesn't stay stuck
            scan.status = "error"
            await db.commit()
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/batch-process-stream")
async def batch_process_stream(
    project_id: int | None = None,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """SSE endpoint: run the pipeline on multiple scans sequentially.

    Query params:
      - ``project_id`` — only process scans in this project (all if omitted)
      - ``status_filter`` — only process scans with this status (e.g. "uploaded")

    Event types:
      - ``log``   — progress message (data: text)
      - ``scan``  — starting a new scan (data: JSON with scan info)
      - ``done``  — single scan finished (data: JSON {scan_id, status})
      - ``error`` — single scan failed (data: JSON {scan_id, error})
      - ``batch_done`` — all scans processed (data: JSON {total, ok, failed})
    """
    import asyncio
    import json as _json

    from fastapi.responses import StreamingResponse
    from sqlalchemy import select as sa_select
    from sqlalchemy.orm import joinedload

    from mv_hofki.models.scan_part import ScanPart
    from mv_hofki.models.scan_project import ScanProject
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

    # Build query for scans to process
    query = (
        sa_select(SheetMusicScan)
        .join(ScanPart)
        .join(ScanProject)
        .options(joinedload(SheetMusicScan.part).joinedload(ScanPart.project))
        .order_by(ScanProject.name, ScanPart.part_name, SheetMusicScan.page_number)
    )
    if project_id is not None:
        query = query.where(ScanProject.id == project_id)
    if status_filter:
        query = query.where(SheetMusicScan.status == status_filter)

    result = await db.execute(query)
    scans = list(result.scalars().unique().all())

    if not scans:
        raise HTTPException(status_code=404, detail="Keine Scans gefunden")

    queue: asyncio.Queue[str] = asyncio.Queue()

    async def run_batch() -> None:
        total = len(scans)
        ok_count = 0
        fail_count = 0

        for idx, scan in enumerate(scans, 1):
            part = scan.part
            project = part.project

            scan_label = f"{project.name} / {part.part_name} (Scan {scan.id})"

            scan_info = {
                "scan_id": scan.id,
                "project": project.name,
                "part": part.part_name,
                "index": idx,
                "total": total,
            }
            queue.put_nowait(f"__SCAN__:{_json.dumps(scan_info)}")

            if scan.status == "processing":
                queue.put_nowait(
                    f"  ⏭ {scan_label}: wird bereits verarbeitet, übersprungen"
                )
                fail_count += 1
                continue

            scan.status = "processing"
            await db.commit()

            def make_log_cb(label: str):
                def cb(msg: str) -> None:
                    queue.put_nowait(f"  {msg}")

                return cb

            try:
                await scan_service.run_pipeline(
                    db,
                    project.id,
                    part.id,
                    scan.id,
                    log_callback=make_log_cb(scan_label),
                )
                ok_count += 1
                await db.refresh(scan)
                done_info = {"scan_id": scan.id, "status": scan.status}
                queue.put_nowait(f"__DONE__:{_json.dumps(done_info)}")
            except Exception as exc:
                fail_count += 1
                scan.status = "error"
                await db.commit()
                err_info = {"scan_id": scan.id, "error": str(exc)}
                queue.put_nowait(f"__ERROR__:{_json.dumps(err_info)}")

        batch_info = {
            "total": total,
            "ok": ok_count,
            "failed": fail_count,
        }
        queue.put_nowait(f"__BATCH_DONE__:{_json.dumps(batch_info)}")

    async def event_generator():
        task = asyncio.create_task(run_batch())
        try:
            while True:
                msg = await queue.get()
                if msg.startswith("__SCAN__:"):
                    yield f"event: scan\ndata: {msg[9:]}\n\n"
                elif msg.startswith("__DONE__:"):
                    yield f"event: done\ndata: {msg[9:]}\n\n"
                elif msg.startswith("__ERROR__:"):
                    yield f"event: error\ndata: {msg[10:]}\n\n"
                elif msg.startswith("__BATCH_DONE__:"):
                    yield f"event: batch_done\ndata: {msg[15:]}\n\n"
                    break
                else:
                    yield f"event: log\ndata: {msg}\n\n"
        except asyncio.CancelledError:
            task.cancel()
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/scans/{scan_id}/status", response_model=ScanStatusRead)
async def get_processing_status(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Poll processing status."""
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    return ScanStatusRead(status=scan.status)


@router.put("/scans/{scan_id}/reset-status")
async def reset_scan_status(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Reset a stuck or errored scan back to 'uploaded' so it can be re-processed."""
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    if scan.status not in ("processing", "error"):
        raise HTTPException(
            status_code=400,
            detail=f"Status '{scan.status}' kann nicht zurückgesetzt werden",
        )

    scan.status = "uploaded"
    await db.commit()
    return {"status": "ok", "new_status": "uploaded"}


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


@router.get("/scans/{scan_id}/measures", response_model=list[DetectedMeasureRead])
async def get_detected_measures(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Get all detected measures for a scan."""
    from sqlalchemy import select

    from mv_hofki.models.detected_measure import DetectedMeasure
    from mv_hofki.models.sheet_music_scan import SheetMusicScan

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    result = await db.execute(
        select(DetectedMeasure)
        .where(DetectedMeasure.scan_id == scan_id)
        .order_by(DetectedMeasure.global_measure_number)
    )
    return list(result.scalars().all())


@router.post("/scans/{scan_id}/generate-lilypond")
async def generate_lilypond_endpoint(
    scan_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Generate LilyPond code and PDF from detected measures."""
    import asyncio

    from sqlalchemy import select

    from mv_hofki.core.config import settings
    from mv_hofki.models.detected_measure import DetectedMeasure
    from mv_hofki.models.scan_part import ScanPart
    from mv_hofki.models.sheet_music_scan import SheetMusicScan
    from mv_hofki.services.lilypond_generator import (
        generate_lilypond,
        render_lilypond_to_pdf,
    )

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    result = await db.execute(
        select(DetectedMeasure)
        .where(DetectedMeasure.scan_id == scan_id)
        .order_by(DetectedMeasure.global_measure_number)
    )
    measures = [
        {
            "staff_index": m.staff_index,
            "measure_number_in_staff": m.measure_number_in_staff,
            "global_measure_number": m.global_measure_number,
            "x_start": m.x_start,
            "x_end": m.x_end,
        }
        for m in result.scalars().all()
    ]

    if not measures:
        raise HTTPException(
            status_code=400,
            detail="Keine Takte erkannt — bitte zuerst Analyse durchführen",
        )

    title = (
        scan.original_filename.rsplit(".", 1)[0] if scan.original_filename else "Scan"
    )
    ly_code = generate_lilypond(measures, title)

    part = await db.get(ScanPart, scan.part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Scan-Part nicht gefunden")
    scan_dir = (
        settings.PROJECT_ROOT
        / "data"
        / "scans"
        / str(part.project_id)
        / str(part.id)
        / str(scan_id)
    )

    pdf_path = await asyncio.to_thread(render_lilypond_to_pdf, ly_code, scan_dir)
    ly_path = scan_dir / "generated.ly"

    return {
        "lilypond_code": ly_code,
        "pdf_path": str(pdf_path.relative_to(settings.PROJECT_ROOT)),
        "ly_path": str(ly_path.relative_to(settings.PROJECT_ROOT)),
    }


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
