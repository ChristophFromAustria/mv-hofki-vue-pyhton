"""Global invoice listing routes."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.invoice_overview import InvoiceOverviewResponse
from mv_hofki.services import invoice_overview as invoice_overview_service

router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])


@router.get("", response_model=InvoiceOverviewResponse)
async def list_invoices(
    category: str | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOverviewResponse:
    return await invoice_overview_service.get_list(
        db,
        category=category,
        search=search,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
