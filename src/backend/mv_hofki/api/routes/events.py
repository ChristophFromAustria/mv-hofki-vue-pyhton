"""Event log API (Protokoll, Verlauf, Dashboard)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi_filter import FilterDepends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.api.routes._listing import page_response
from mv_hofki.filters.base import PageParams, fetch_page
from mv_hofki.filters.event import EventFilter
from mv_hofki.models.event import Event
from mv_hofki.schemas.event import EventRead
from mv_hofki.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("", response_model=PaginatedResponse[EventRead])
async def list_events(
    flt: EventFilter = FilterDepends(EventFilter),
    page: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    lp = await fetch_page(db, flt, select(Event), page)
    return page_response(lp, page, [EventRead.model_validate(e) for e in lp.rows])


@router.get("/actors", response_model=list[str | None])
async def list_actors(db: AsyncSession = Depends(get_db)):
    """Everyone who appears in the log (None = unknown), for the person filter."""
    result = await db.execute(select(Event.actor).distinct().order_by(Event.actor))
    return list(result.scalars())
