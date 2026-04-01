"""SheetMusicScan CRUD + upload service."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.core.config import settings
from mv_hofki.models.sheet_music_scan import SheetMusicScan
from mv_hofki.schemas.sheet_music_scan import SheetMusicScanUpdate
from mv_hofki.services import scan_part as part_service

if TYPE_CHECKING:
    from mv_hofki.schemas.scanner_config import ScannerConfigUpdate

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
    config_overrides: ScannerConfigUpdate | None = None,
    log_callback: Callable[[str], None] | None = None,
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
    from mv_hofki.services.scanner.stages.post_matching import PostMatchingStage
    from mv_hofki.services.scanner.stages.preprocess import PreprocessStage
    from mv_hofki.services.scanner.stages.staff_removal import StaffRemovalStage
    from mv_hofki.services.scanner.stages.stave_detection import StaveDetectionStage
    from mv_hofki.services.scanner.stages.template_matching import TemplateMatchingStage
    from mv_hofki.services.scanner_config import get_effective_config

    scan = await get_by_id(session, project_id, part_id, scan_id)
    img_path = settings.PROJECT_ROOT / scan.image_path
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise HTTPException(status_code=400, detail="Bild konnte nicht geladen werden")

    # Load variants with valid scaling info (source_line_spacing > 0)
    result = await session.execute(
        sa_select(SymbolVariant).where(
            SymbolVariant.source_line_spacing.isnot(None),
            SymbolVariant.source_line_spacing > 0,
        )
    )
    variants = list(result.scalars().all())

    variant_images = []
    variant_template_ids = []
    variant_heights = []
    variant_line_spacings = []
    for v in variants:
        v_path = settings.PROJECT_ROOT / v.image_path
        v_img = cv2.imread(str(v_path), cv2.IMREAD_GRAYSCALE)
        if v_img is not None:
            variant_images.append(v_img)
            variant_template_ids.append(v.template_id)
            variant_heights.append(v.height_in_lines or 4.0)
            variant_line_spacings.append(v.source_line_spacing)

    from mv_hofki.models.symbol_template import SymbolTemplate

    # Build template_id → display_name mapping for post-matching filters
    tmpl_result = await session.execute(sa_select(SymbolTemplate))
    all_templates = list(tmpl_result.scalars().all())
    template_display_names = {t.id: t.display_name for t in all_templates}

    # Load global scanner config, merge any per-request overrides
    config = await get_effective_config(session, overrides=config_overrides)

    # Merge scan-level preprocessing adjustments into pipeline config
    adjustments = json.loads(scan.adjustments_json) if scan.adjustments_json else {}
    preprocessing = adjustments.get("preprocessing", {})
    for key in (
        "brightness",
        "contrast",
        "threshold",
        "rotation",
        "morphology_kernel_size",
    ):
        if key in preprocessing:
            config[key] = preprocessing[key]

    from mv_hofki.services.scanner.stages.dewarp import DewarpStage

    stages = [
        PreprocessStage(),
        StaveDetectionStage(),
    ]

    if config.get("dewarp_enabled", False):
        stages.append(DewarpStage())

    if config.get("staff_removal_before_matching", False):
        stages.append(StaffRemovalStage())

    stages.append(
        TemplateMatchingStage(
            variant_images=variant_images,
            variant_template_ids=variant_template_ids,
            variant_heights=variant_heights,
            variant_line_spacings=variant_line_spacings,
            template_display_names=template_display_names,
        ),
    )

    stages.append(PostMatchingStage())

    import asyncio

    if log_callback:
        log_callback(f"Bild geladen ({img.shape[1]}x{img.shape[0]} px)")
        log_callback(f"{len(variant_images)} Vorlagen geladen")

    ctx = PipelineContext(image=img, config=config, log_callback=log_callback)
    pipeline = Pipeline(stages=stages)
    # Run CPU-heavy pipeline in a thread to avoid blocking the async event loop
    ctx = await asyncio.to_thread(pipeline.run, ctx)

    if log_callback:
        log_callback(
            f"Pipeline abgeschlossen: {len(ctx.staves)} Systeme, "
            f"{len(ctx.symbols)} Symbole erkannt"
        )
        log_callback("Ergebnisse werden gespeichert...")

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
            line_thickness=staff_data.line_thickness,
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
                and sym_data.confidence >= config.get("auto_verify_confidence", 0.85),
                alternatives_json=alternatives_json,
                filtered=sym_data.filtered,
                filter_reason=sym_data.filter_reason,
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


async def run_preview(
    session: AsyncSession,
    scan_id: int,
    adjustments_json: str | None = None,
) -> str:
    """Run only preprocessing and return the processed image path.

    Saves the adjustments and the resulting binary image but does NOT
    run stave detection, template matching, or any later pipeline stages.
    """
    import json

    import cv2

    from mv_hofki.models.scan_part import ScanPart
    from mv_hofki.services.scanner.stages.base import PipelineContext
    from mv_hofki.services.scanner.stages.preprocess import PreprocessStage
    from mv_hofki.services.scanner_config import get_effective_config

    scan = await session.get(SheetMusicScan, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    # Persist adjustments
    if adjustments_json is not None:
        scan.adjustments_json = adjustments_json

    img_path = settings.PROJECT_ROOT / scan.image_path
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise HTTPException(status_code=400, detail="Bild konnte nicht geladen werden")

    # Build config: global defaults + scan-level preprocessing overrides
    config = await get_effective_config(session)
    adjustments = json.loads(scan.adjustments_json) if scan.adjustments_json else {}
    preprocessing = adjustments.get("preprocessing", {})
    for key in (
        "brightness",
        "contrast",
        "threshold",
        "rotation",
        "morphology_kernel_size",
    ):
        if key in preprocessing:
            config[key] = preprocessing[key]

    ctx = PipelineContext(image=img, config=config)
    ctx = PreprocessStage().process(ctx)

    # Resolve scan directory
    part = await session.get(ScanPart, scan.part_id)
    if part is None:
        raise HTTPException(status_code=404, detail="Scan-Part nicht gefunden")
    scan_dir = _scan_dir(part.project_id, part.id, scan.id)
    scan_dir.mkdir(parents=True, exist_ok=True)

    processed_path = scan_dir / "processed.png"
    if ctx.processed_image is not None:
        cv2.imwrite(str(processed_path), ctx.processed_image)
    scan.processed_image_path = str(processed_path.relative_to(settings.PROJECT_ROOT))

    await session.commit()
    return scan.processed_image_path
