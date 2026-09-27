"""Global invoice listing routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi_filter import FilterDepends
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.filters.base import PageParams
from mv_hofki.filters.invoice import InvoiceFilter
from mv_hofki.schemas.invoice_overview import InvoiceOverviewResponse
from mv_hofki.services import invoice_overview as invoice_overview_service

router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])


@router.get("", response_model=InvoiceOverviewResponse)
async def list_invoices(
    flt: InvoiceFilter = FilterDepends(InvoiceFilter),
    page: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOverviewResponse:
    return await invoice_overview_service.get_list(db, flt, page)
