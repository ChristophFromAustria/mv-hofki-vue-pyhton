"""SheetMusicScan CRUD + upload service."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.core.config import settings
from mv_hofki.models.sheet_music_scan import SheetMusicScan
from mv_hofki.schemas.sheet_music_scan import SheetMusicScanUpdate
from mv_hofki.services import scan_part as part_service

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/tiff"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

_SCANS_ROOT = settings.PROJECT_ROOT / "data" / "scans"


def _scan_dir(project_id: int, part_id: int, scan_id: int) -> Path:
    return _SCANS_ROOT / str(project_id) / str(part_id) / str(scan_id)


async def get_list(
    session: AsyncSession, project_id: int, part_id: int
) -> list[SheetMusicScan]:
    await part_service.get_by_id(session, project_id, part_id)
    query = (
        select(SheetMusicScan)
        .where(SheetMusicScan.part_id == part_id)
        .order_by(SheetMusicScan.page_number)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_by_id(
    session: AsyncSession, project_id: int, part_id: int, scan_id: int
) -> SheetMusicScan:
    scan = await session.get(SheetMusicScan, scan_id)
    if not scan or scan.part_id != part_id:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")
    await part_service.get_by_id(session, project_id, part_id)
    return scan


async def upload(
    session: AsyncSession,
    project_id: int,
    part_id: int,
    file: UploadFile,
) -> SheetMusicScan:
    await part_service.get_by_id(session, project_id, part_id)

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Ungültiger Dateityp: {file.content_type}. Erlaubt: PNG, JPEG, TIFF"
            ),
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Datei zu groß (max. 50 MB)")

    # Determine next page number
    count_result = await session.execute(
        select(func.count()).where(SheetMusicScan.part_id == part_id)
    )
    page_number = count_result.scalar_one() + 1

    # Create DB record first to get ID
    ext = Path(file.filename or "upload.png").suffix or ".png"
    scan = SheetMusicScan(
        part_id=part_id,
        page_number=page_number,
        original_filename=file.filename or "upload.png",
        image_path="",  # placeholder, updated after save
        status="uploaded",
    )
    session.add(scan)
    await session.flush()

    # Save file
    scan_directory = _scan_dir(project_id, part_id, scan.id)
    scan_directory.mkdir(parents=True, exist_ok=True)
    filename = f"original{ext}"
    file_path = scan_directory / filename
    file_path.write_bytes(content)

    scan.image_path = str(file_path.relative_to(settings.PROJECT_ROOT))
    await session.commit()
    await session.refresh(scan)
    return scan


async def update(
    session: AsyncSession,
    project_id: int,
    part_id: int,
    scan_id: int,
    data: SheetMusicScanUpdate,
) -> SheetMusicScan:
    scan = await get_by_id(session, project_id, part_id, scan_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(scan, key, value)
    await session.commit()
    await session.refresh(scan)
    return scan


async def delete(
    session: AsyncSession, project_id: int, part_id: int, scan_id: int
) -> None:
    scan = await get_by_id(session, project_id, part_id, scan_id)
    scan_directory = _scan_dir(project_id, part_id, scan_id)
    if scan_directory.exists():
        shutil.rmtree(scan_directory)
    await session.delete(scan)
    await session.commit()


async def run_pipeline(
    session: AsyncSession,
    project_id: int,
    part_id: int,
    scan_id: int,
) -> None:
    import json

    import cv2
    from sqlalchemy import delete as sa_delete
    from sqlalchemy import select as sa_select

    from mv_hofki.models.detected_staff import DetectedStaff
    from mv_hofki.models.detected_symbol import DetectedSymbol
    from mv_hofki.models.symbol_variant import SymbolVariant
    from mv_hofki.services.scanner.pipeline import Pipeline
    from mv_hofki.services.scanner.stages.base import PipelineContext
    from mv_hofki.services.scanner.stages.preprocess import PreprocessStage
    from mv_hofki.services.scanner.stages.stave_detection import StaveDetectionStage
    from mv_hofki.services.scanner.stages.template_matching import TemplateMatchingStage

    scan = await get_by_id(session, project_id, part_id, scan_id)
    img_path = settings.PROJECT_ROOT / scan.image_path
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise HTTPException(status_code=400, detail="Bild konnte nicht geladen werden")

    # Load symbol library variants that have height_in_lines (user-captured templates)
    result = await session.execute(
        sa_select(SymbolVariant).where(SymbolVariant.height_in_lines.isnot(None))
    )
    variants = list(result.scalars().all())

    variant_images = []
    variant_template_ids = []
    variant_heights = []
    for v in variants:
        v_path = settings.PROJECT_ROOT / v.image_path
        v_img = cv2.imread(str(v_path), cv2.IMREAD_GRAYSCALE)
        if v_img is not None and v.height_in_lines is not None:
            variant_images.append(v_img)
            variant_template_ids.append(v.template_id)
            variant_heights.append(v.height_in_lines)

    # Pass the user's threshold into the pipeline config
    adjustments = json.loads(scan.adjustments_json) if scan.adjustments_json else {}
    config = json.loads(scan.pipeline_config_json) if scan.pipeline_config_json else {}
    if "threshold" in adjustments:
        config["threshold"] = adjustments["threshold"]

    stages = [
        PreprocessStage(),
        StaveDetectionStage(),
        TemplateMatchingStage(
            variant_images=variant_images,
            variant_template_ids=variant_template_ids,
            variant_heights=variant_heights,
            confidence_threshold=config.get("confidence_threshold", 0.6),
        ),
    ]

    ctx = PipelineContext(image=img, config=config)
    pipeline = Pipeline(stages=stages)
    ctx = pipeline.run(ctx)

    # Clear previous detection results
    staff_ids_q = sa_select(DetectedStaff.id).where(DetectedStaff.scan_id == scan_id)
    await session.execute(
        sa_delete(DetectedSymbol).where(DetectedSymbol.staff_id.in_(staff_ids_q))
    )
    await session.execute(
        sa_delete(DetectedStaff).where(DetectedStaff.scan_id == scan_id)
    )

    # Persist detected staves
    snippet_dir = _scan_dir(project_id, part_id, scan_id) / "snippets"
    snippet_dir.mkdir(parents=True, exist_ok=True)

    for staff_data in ctx.staves:
        staff = DetectedStaff(
            scan_id=scan_id,
            staff_index=staff_data.staff_index,
            y_top=staff_data.y_top,
            y_bottom=staff_data.y_bottom,
            line_positions_json=json.dumps(staff_data.line_positions),
            line_spacing=staff_data.line_spacing,
            clef=staff_data.clef,
            key_signature=staff_data.key_signature,
            time_signature=staff_data.time_signature,
        )
        session.add(staff)
        await session.flush()

        # Persist symbols for this staff
        for sym_data in ctx.symbols:
            if sym_data.staff_index != staff_data.staff_index:
                continue

            snippet_path = None
            if sym_data.snippet is not None:
                snippet_filename = f"{sym_data.sequence_order}.png"
                snippet_file = snippet_dir / snippet_filename
                cv2.imwrite(str(snippet_file), sym_data.snippet)
                snippet_path = str(snippet_file.relative_to(settings.PROJECT_ROOT))

            alternatives_json = None
            if sym_data.alternatives:
                alternatives_json = json.dumps(sym_data.alternatives)

            symbol = DetectedSymbol(
                staff_id=staff.id,
                x=sym_data.x,
                y=sym_data.y,
                width=sym_data.width,
                height=sym_data.height,
                snippet_path=snippet_path,
                position_on_staff=sym_data.position_on_staff,
                sequence_order=sym_data.sequence_order,
                matched_symbol_id=sym_data.matched_template_id,
                confidence=sym_data.confidence,
                user_verified=sym_data.confidence is not None
                and sym_data.confidence >= 0.85,
                alternatives_json=alternatives_json,
            )
            session.add(symbol)

    # Save processed image
    if ctx.processed_image is not None:
        processed_path = _scan_dir(project_id, part_id, scan_id) / "processed.png"
        cv2.imwrite(str(processed_path), ctx.processed_image)
        scan.processed_image_path = str(
            processed_path.relative_to(settings.PROJECT_ROOT)
        )

    scan.status = "review"
    await session.commit()
