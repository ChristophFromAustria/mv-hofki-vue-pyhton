"""Import session service: upload, analyse, draft, delete.

Files live in ``data/uploads/imports/<session_id>/`` (served under
``/uploads/imports/...``). Everything is additionally archived via
:mod:`archive` so failed runs remain available as test material.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.core.config import settings
from mv_hofki.models.import_page import ImportPage
from mv_hofki.models.import_session import ImportSession

from . import archive as archive_mod
from .extraction import SYSTEM_PROMPT, PageResult, build_prompt, extract_page
from .llm_client import LlmClient, LlmError
from .pages import (
    DEFAULT_MAX_WIDTH,
    PageImage,
    UnsupportedFileError,
    crop,
    render_image_bytes,
    render_pdf_bytes,
)

log = logging.getLogger(__name__)

IMPORTS_ROOT = Path(settings.PROJECT_ROOT) / "data" / "uploads" / "imports"
UPLOADS_ROOT = Path(settings.PROJECT_ROOT) / "data" / "uploads"

ProgressCallback = Callable[[dict[str, Any]], None]
ExtractFn = Callable[[LlmClient, PageImage], Awaitable[PageResult]]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _session_dir(session_id: int) -> Path:
    return IMPORTS_ROOT / str(session_id)


def image_url(page: ImportPage) -> str:
    """``data/uploads/imports/3/p001.png`` -> ``/uploads/imports/3/p001.png``."""
    rel = Path(page.image_path)
    try:
        rel = rel.relative_to(Path("data") / "uploads")
    except ValueError:
        pass
    return "/uploads/" + rel.as_posix()


def _page_image(page: ImportPage) -> PageImage:
    data = (Path(settings.PROJECT_ROOT) / page.image_path).read_bytes()
    return PageImage(page.page_index, data, page.width, page.height, page.source_name)


def _archive_for(session: ImportSession) -> archive_mod.ImportArchive | None:
    if not session.archive_dir:
        return None
    root = Path(settings.PROJECT_ROOT) / session.archive_dir
    if not root.exists():
        return None
    meta_path = root / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    return archive_mod.ImportArchive(root=root, meta=meta)


def to_read_dict(session: ImportSession) -> dict[str, Any]:
    """Shape an ImportSession for ImportSessionRead."""
    return {
        "id": session.id,
        "title": session.title,
        "status": session.status,
        "model": session.model,
        "page_count": len(session.pages),
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "error": session.error,
        "draft": json.loads(session.draft_json) if session.draft_json else None,
        "import_result": (
            json.loads(session.import_result_json)
            if session.import_result_json
            else None
        ),
        "pages": [
            {
                "id": p.id,
                "page_index": p.page_index,
                "source_name": p.source_name,
                "source_page": p.source_page,
                "image_url": image_url(p),
                "width": p.width,
                "height": p.height,
                "status": p.status,
                "extraction": (
                    json.loads(p.extraction_json) if p.extraction_json else None
                ),
                "error": p.error,
                "duration_seconds": p.duration_seconds,
            }
            for p in session.pages
        ],
    }


def to_summary_dict(session: ImportSession, page_count: int) -> dict[str, Any]:
    return {
        "id": session.id,
        "title": session.title,
        "status": session.status,
        "model": session.model,
        "page_count": page_count,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create(db: AsyncSession, title: str | None) -> ImportSession:
    session = ImportSession(title=title or None, status="uploaded")
    db.add(session)
    await db.flush()
    archive = archive_mod.create_archive(
        title or f"import-{session.id}", root=archive_mod.ARCHIVE_ROOT
    )
    archive.set(import_session_id=session.id)
    session.archive_dir = str(archive.root.relative_to(settings.PROJECT_ROOT))
    await db.commit()
    await db.refresh(session)
    return session


async def get_by_id(db: AsyncSession, session_id: int) -> ImportSession:
    session = await db.get(ImportSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Import-Sitzung nicht gefunden")
    return session


async def get_list(
    db: AsyncSession, *, limit: int = 50, offset: int = 0
) -> tuple[list[tuple[ImportSession, int]], int]:
    total = (
        await db.execute(select(func.count()).select_from(ImportSession))
    ).scalar_one()
    query = (
        select(ImportSession, func.count(ImportPage.id))
        .outerjoin(ImportPage, ImportPage.session_id == ImportSession.id)
        .group_by(ImportSession.id)
        .order_by(ImportSession.created_at.desc(), ImportSession.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(query)).all()
    return [(row[0], row[1]) for row in rows], total


async def delete(db: AsyncSession, session: ImportSession) -> None:
    """Remove the session and its served page images. The archive is kept."""
    session_dir = _session_dir(session.id)
    await db.delete(session)
    await db.commit()
    shutil.rmtree(session_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# upload
# ---------------------------------------------------------------------------


def _render_upload(filename: str, data: bytes, max_width: int) -> list[PageImage]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return render_pdf_bytes(data, filename, max_width)
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
        return [render_image_bytes(data, filename, max_width)]
    raise UnsupportedFileError(
        f"Nicht unterstütztes Dateiformat: {filename} (erlaubt: PDF, PNG, JPG, TIFF)"
    )


async def add_files(
    db: AsyncSession,
    session: ImportSession,
    files: list[tuple[str, bytes]],
    max_width: int = DEFAULT_MAX_WIDTH,
) -> ImportSession:
    if session.status == "analyzing":
        raise HTTPException(
            status_code=409,
            detail="Analyse läuft, Dateien können nicht hinzugefügt werden",
        )
    if session.status == "imported":
        raise HTTPException(status_code=409, detail="Sitzung wurde bereits importiert")

    # Render everything first so a bad file rejects the whole upload cleanly.
    rendered: list[tuple[str, bytes, list[PageImage]]] = []
    for filename, data in files:
        try:
            pages = await asyncio.to_thread(_render_upload, filename, data, max_width)
        except UnsupportedFileError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        rendered.append((filename, data, pages))

    archive = _archive_for(session)
    session_dir = _session_dir(session.id)
    session_dir.mkdir(parents=True, exist_ok=True)
    next_index = len(session.pages)

    for filename, data, pages in rendered:
        if archive:
            archive.add_original(filename, data)
        archived_pages: list[PageImage] = []
        for page in pages:
            file_path = session_dir / f"p{next_index + 1:03d}.png"
            file_path.write_bytes(page.png)
            db.add(
                ImportPage(
                    session_id=session.id,
                    page_index=next_index,
                    source_name=filename,
                    source_page=page.index,
                    image_path=str(file_path.relative_to(settings.PROJECT_ROOT)),
                    width=page.width,
                    height=page.height,
                    status="uploaded",
                )
            )
            archived_pages.append(
                PageImage(next_index, page.png, page.width, page.height, filename)
            )
            next_index += 1
        if archive:
            archive.add_pages(archived_pages)

    if not session.title and rendered:
        session.title = Path(rendered[0][0]).stem[:200]
    if session.status in ("error",):
        session.status = "uploaded"
    await db.commit()
    await db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------


async def analyze(
    db: AsyncSession,
    session: ImportSession,
    client: LlmClient,
    *,
    force: bool = False,
    progress: ProgressCallback | None = None,
    extract: ExtractFn = extract_page,
) -> ImportSession:
    """Run the extraction on every page that has no result yet.

    ``progress`` receives one dict per page (``{"page_index", "status", ...}``).
    On return the session is in ``review`` (at least one page succeeded) or
    ``error`` (nothing succeeded). Pages that already have a result are kept
    unless ``force`` is set.
    """
    if session.status == "analyzing":
        raise HTTPException(status_code=409, detail="Analyse läuft bereits")
    if not session.pages:
        raise HTTPException(status_code=400, detail="Keine Seiten hochgeladen")

    todo = [p for p in session.pages if force or p.status != "done"]
    session.status = "analyzing"
    session.model = client.model
    session.error = None
    for p in todo:
        p.status = "analyzing"
        p.error = None
    await db.commit()

    archive = _archive_for(session)
    if archive and todo:
        first = todo[0]
        archive.set(base_url=client.base_url, model=client.model)
        archive.add_prompt(SYSTEM_PROMPT, build_prompt(first.width, first.height))

    def emit(event: dict[str, Any]) -> None:
        if progress:
            progress(event)

    for page in todo:
        try:
            image = await asyncio.to_thread(_page_image, page)
            result = await extract(client, image)
        except (LlmError, OSError) as e:
            page.status = "error"
            page.error = str(e)
            if archive:
                archive.add_error(page.page_index, str(e))
            log.warning("KI-Import Seite %s fehlgeschlagen: %s", page.page_index, e)
            await db.commit()
            emit({"page_index": page.page_index, "status": "error", "error": str(e)})
            continue

        page.status = "done"
        page.raw_json = json.dumps(result.raw, ensure_ascii=False)
        page.extraction_json = result.extraction.model_dump_json()
        page.duration_seconds = result.duration_seconds
        if archive:
            archive.add_result(
                page.page_index, result.raw, result.usage, result.duration_seconds
            )
        await db.commit()
        emit(
            {
                "page_index": page.page_index,
                "status": "done",
                "page_kind": result.extraction.page_kind,
                "instruments": len(result.extraction.instruments),
                "photos": len(result.extraction.photos),
                "duration_seconds": result.duration_seconds,
            }
        )

    await db.refresh(session)
    done = [p for p in session.pages if p.status == "done"]
    if done:
        session.status = "review"
        if force or not session.draft_json:
            from .draft import build_draft

            session.draft_json = json.dumps(build_draft(done), ensure_ascii=False)
    else:
        session.status = "error"
        session.error = "Keine Seite konnte analysiert werden"
    await db.commit()
    await db.refresh(session)
    return session


async def mark_aborted(db: AsyncSession, session: ImportSession, reason: str) -> None:
    """Connection dropped mid-analysis: leave nothing stuck in 'analyzing'."""
    for p in session.pages:
        if p.status == "analyzing":
            p.status = "error"
            p.error = reason
    done = any(p.status == "done" for p in session.pages)
    session.status = "review" if done else "error"
    session.error = None if done else reason
    await db.commit()


# ---------------------------------------------------------------------------
# draft & crops
# ---------------------------------------------------------------------------


async def update_draft(
    db: AsyncSession, session: ImportSession, draft: dict[str, Any]
) -> ImportSession:
    if session.status == "imported":
        raise HTTPException(status_code=409, detail="Sitzung wurde bereits importiert")
    if session.status == "analyzing":
        raise HTTPException(status_code=409, detail="Analyse läuft")
    session.draft_json = json.dumps(draft, ensure_ascii=False)
    await db.commit()
    await db.refresh(session)
    return session


def crop_page(page: ImportPage, bbox: list[int]) -> bytes:
    try:
        return crop(_page_image(page), bbox)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
