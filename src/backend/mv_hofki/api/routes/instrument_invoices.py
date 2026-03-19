"""InstrumentInvoice API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.instrument_invoice import (
    InstrumentInvoiceCreate,
    InstrumentInvoiceRead,
    InstrumentInvoiceUpdate,
)
from mv_hofki.services import instrument_invoice as invoice_service

router = APIRouter(
    prefix="/api/v1/instruments/{instrument_id}/invoices",
    tags=["instrument-invoices"],
)


def _to_read(inv) -> InstrumentInvoiceRead:
    file_url = None
    if inv.filename:
        file_url = f"/uploads/invoices/{inv.instrument_id}/{inv.filename}"
    return InstrumentInvoiceRead(
        id=inv.id,
        invoice_nr=inv.invoice_nr,
        instrument_id=inv.instrument_id,
        title=inv.title,
        amount=inv.amount,
        currency_id=inv.currency_id,
        date_issued=inv.date_issued,
        description=inv.description,
        invoice_issuer=inv.invoice_issuer,
        issuer_address=inv.issuer_address,
        filename=inv.filename,
        file_url=file_url,
        created_at=inv.created_at,
        currency=inv.currency,
    )


@router.get("", response_model=list[InstrumentInvoiceRead])
async def list_invoices(instrument_id: int, db: AsyncSession = Depends(get_db)):
    invoices = await invoice_service.get_all(db, instrument_id)
    return [_to_read(inv) for inv in invoices]


@router.get("/{invoice_id}", response_model=InstrumentInvoiceRead)
async def get_invoice(
    instrument_id: int,
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
):
    return _to_read(await invoice_service.get_by_id(db, instrument_id, invoice_id))


@router.post("", response_model=InstrumentInvoiceRead, status_code=201)
async def create_invoice(
    instrument_id: int,
    data: InstrumentInvoiceCreate,
    db: AsyncSession = Depends(get_db),
):
    return _to_read(await invoice_service.create(db, instrument_id, data))


@router.put("/{invoice_id}", response_model=InstrumentInvoiceRead)
async def update_invoice(
    instrument_id: int,
    invoice_id: int,
    data: InstrumentInvoiceUpdate,
    db: AsyncSession = Depends(get_db),
):
    return _to_read(await invoice_service.update(db, instrument_id, invoice_id, data))


@router.post(
    "/{invoice_id}/file",
    response_model=InstrumentInvoiceRead,
)
async def upload_invoice_file(
    instrument_id: int,
    invoice_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    return _to_read(
        await invoice_service.upload_file(db, instrument_id, invoice_id, file)
    )


@router.delete("/{invoice_id}/file", response_model=InstrumentInvoiceRead)
async def delete_invoice_file(
    instrument_id: int,
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
):
    return _to_read(await invoice_service.delete_file(db, instrument_id, invoice_id))


@router.delete("/{invoice_id}", status_code=204)
async def delete_invoice(
    instrument_id: int,
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
):
    await invoice_service.delete(db, instrument_id, invoice_id)
    return Response(status_code=204)
