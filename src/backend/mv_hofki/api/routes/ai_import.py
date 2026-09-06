"""KI-Import API: sessions, uploads, analysis stream, draft."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.ai_import import (
    ImportDraftUpdate,
    ImportSessionCreate,
    ImportSessionRead,
    ImportSessionSummary,
)
from mv_hofki.schemas.pagination import PaginatedResponse
from mv_hofki.services.ai_import import session as session_service
from mv_hofki.services.ai_import.llm_client import LlmClient

router = APIRouter(prefix="/api/v1/import", tags=["ki-import"])


@router.get("/sessions", response_model=PaginatedResponse[ImportSessionSummary])
async def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await session_service.get_list(db, limit=limit, offset=offset)
    items = [session_service.to_summary_dict(s, n) for s, n in rows]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/sessions", response_model=ImportSessionRead, status_code=201)
async def create_session(
    data: ImportSessionCreate | None = None, db: AsyncSession = Depends(get_db)
):
    session = await session_service.create(db, data.title if data else None)
    return session_service.to_read_dict(session)


@router.get("/sessions/{session_id}", response_model=ImportSessionRead)
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)):
    session = await session_service.get_by_id(db, session_id)
    return await session_service.read_with_validation(db, session)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: int, db: AsyncSession = Depends(get_db)):
    session = await session_service.get_by_id(db, session_id)
    await session_service.delete(db, session)
    return Response(status_code=204)


@router.post("/sessions/{session_id}/files", response_model=ImportSessionRead)
async def upload_files(
    session_id: int,
    files: list[UploadFile],
    db: AsyncSession = Depends(get_db),
):
    session = await session_service.get_by_id(db, session_id)
    payload: list[tuple[str, bytes]] = []
    for f in files:
        payload.append((f.filename or "upload", await f.read()))
    session = await session_service.add_files(db, session, payload)
    return session_service.to_read_dict(session)


@router.put("/sessions/{session_id}/draft", response_model=ImportSessionRead)
async def update_draft(
    session_id: int, body: ImportDraftUpdate, db: AsyncSession = Depends(get_db)
):
    session = await session_service.get_by_id(db, session_id)
    session = await session_service.update_draft(db, session, body.draft)
    return await session_service.read_with_validation(db, session)


@router.get("/sessions/{session_id}/pages/{page_id}/crop")
async def crop_page(
    session_id: int,
    page_id: int,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    db: AsyncSession = Depends(get_db),
):
    """Cut a rectangle (page pixels) out of a page image; used for photo previews."""
    session = await session_service.get_by_id(db, session_id)
    page = next((p for p in session.pages if p.id == page_id), None)
    if page is None:
        return Response(status_code=404, content="Seite nicht gefunden")
    png = await asyncio.to_thread(session_service.crop_page, page, [x1, y1, x2, y2])
    return Response(content=png, media_type="image/png")


@router.get("/sessions/{session_id}/analyze-stream")
async def analyze_stream(
    session_id: int,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """SSE: analyse every pending page and report progress.

    Events:
      - ``page``  — one page finished (JSON: page_index, status, counts or error)
      - ``done``  — analysis finished (JSON: session status, page_count)
      - ``error`` — analysis could not run (text)
    """
    session = await session_service.get_by_id(db, session_id)
    client = LlmClient()
    queue: asyncio.Queue[tuple[str, Any] | None] = asyncio.Queue()

    def progress(event: dict[str, Any]) -> None:
        queue.put_nowait(("page", event))

    async def run() -> None:
        try:
            await session_service.analyze(
                db, session, client, force=force, progress=progress
            )
            queue.put_nowait(("done", {"status": session.status}))
        except Exception as exc:  # noqa: BLE001 — reported to the client
            detail = getattr(exc, "detail", None) or str(exc)
            queue.put_nowait(("error", detail))
        finally:
            queue.put_nowait(None)

    async def event_generator():
        task = asyncio.create_task(run())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                event, data = item
                payload = data if isinstance(data, str) else json.dumps(data)
                yield f"event: {event}\ndata: {payload}\n\n"
        except asyncio.CancelledError:
            task.cancel()
            await session_service.mark_aborted(
                db, session, "Verbindung während der Analyse abgebrochen"
            )
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
