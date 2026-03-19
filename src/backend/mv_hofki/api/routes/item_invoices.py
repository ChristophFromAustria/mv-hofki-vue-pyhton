"""ItemInvoice API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.item_invoice import (
    ItemInvoiceCreate,
    ItemInvoiceRead,
    ItemInvoiceUpdate,
)
from mv_hofki.services import item_invoice as invoice_service

router = APIRouter(
    prefix="/api/v1/items/{item_id}/invoices",
    tags=["item-invoices"],
)


def _to_read(inv) -> ItemInvoiceRead:
    file_url = None
    if inv.filename:
        file_url = f"/uploads/invoices/{inv.item_id}/{inv.filename}"
    return ItemInvoiceRead(
        id=inv.id,
        invoice_nr=inv.invoice_nr,
        item_id=inv.item_id,
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


@router.get("", response_model=list[ItemInvoiceRead])
async def list_invoices(item_id: int, db: AsyncSession = Depends(get_db)):
    invoices = await invoice_service.get_all(db, item_id)
    return [_to_read(inv) for inv in invoices]


@router.get("/{invoice_id}", response_model=ItemInvoiceRead)
async def get_invoice(
    item_id: int,
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
):
    return _to_read(await invoice_service.get_by_id(db, item_id, invoice_id))


@router.post("", response_model=ItemInvoiceRead, status_code=201)
async def create_invoice(
    item_id: int,
    data: ItemInvoiceCreate,
    db: AsyncSession = Depends(get_db),
):
    return _to_read(await invoice_service.create(db, item_id, data))


@router.put("/{invoice_id}", response_model=ItemInvoiceRead)
async def update_invoice(
    item_id: int,
    invoice_id: int,
    data: ItemInvoiceUpdate,
    db: AsyncSession = Depends(get_db),
):
    return _to_read(await invoice_service.update(db, item_id, invoice_id, data))


@router.post(
    "/{invoice_id}/file",
    response_model=ItemInvoiceRead,
)
async def upload_invoice_file(
    item_id: int,
    invoice_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    return _to_read(await invoice_service.upload_file(db, item_id, invoice_id, file))


@router.delete("/{invoice_id}/file", response_model=ItemInvoiceRead)
async def delete_invoice_file(
    item_id: int,
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
):
    return _to_read(await invoice_service.delete_file(db, item_id, invoice_id))


@router.delete("/{invoice_id}", status_code=204)
async def delete_invoice(
    item_id: int,
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
):
    await invoice_service.delete(db, item_id, invoice_id)
    return Response(status_code=204)
