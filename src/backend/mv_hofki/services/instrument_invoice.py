"""InstrumentInvoice service."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from mv_hofki.core.config import settings
from mv_hofki.models.instrument_invoice import InstrumentInvoice
from mv_hofki.schemas.instrument_invoice import (
    InstrumentInvoiceCreate,
    InstrumentInvoiceUpdate,
)

UPLOAD_DIR = Path(settings.PROJECT_ROOT) / "data" / "uploads" / "invoices"
ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _invoice_dir(instrument_id: int) -> Path:
    d = UPLOAD_DIR / str(instrument_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


async def get_all(session: AsyncSession, instrument_id: int) -> list[InstrumentInvoice]:
    result = await session.execute(
        select(InstrumentInvoice)
        .options(joinedload(InstrumentInvoice.currency))
        .where(InstrumentInvoice.instrument_id == instrument_id)
        .order_by(InstrumentInvoice.date_issued.desc().nulls_last())
    )
    return list(result.unique().scalars().all())


async def get_by_id(
    session: AsyncSession, instrument_id: int, invoice_id: int
) -> InstrumentInvoice:
    result = await session.execute(
        select(InstrumentInvoice)
        .options(joinedload(InstrumentInvoice.currency))
        .where(
            InstrumentInvoice.id == invoice_id,
            InstrumentInvoice.instrument_id == instrument_id,
        )
    )
    invoice = result.unique().scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    return invoice


async def create(
    session: AsyncSession,
    instrument_id: int,
    data: InstrumentInvoiceCreate,
) -> InstrumentInvoice:
    # Auto-assign invoice_nr (per instrument)
    result = await session.execute(
        select(func.max(InstrumentInvoice.invoice_nr)).where(
            InstrumentInvoice.instrument_id == instrument_id
        )
    )
    max_nr = result.scalar_one_or_none() or 0
    invoice = InstrumentInvoice(
        instrument_id=instrument_id,
        invoice_nr=max_nr + 1,
        **data.model_dump(),
    )
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice, attribute_names=["currency"])
    return invoice


async def update(
    session: AsyncSession,
    instrument_id: int,
    invoice_id: int,
    data: InstrumentInvoiceUpdate,
) -> InstrumentInvoice:
    invoice = await get_by_id(session, instrument_id, invoice_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(invoice, key, value)
    await session.commit()
    await session.refresh(invoice, attribute_names=["currency"])
    return invoice


async def upload_file(
    session: AsyncSession,
    instrument_id: int,
    invoice_id: int,
    file: UploadFile,
) -> InstrumentInvoice:
    invoice = await get_by_id(session, instrument_id, invoice_id)

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400, detail="Ungültiger Dateityp (Bild oder PDF)"
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Datei zu groß (max 10 MB)")

    # Delete old file if exists
    if invoice.filename:
        old_path = _invoice_dir(instrument_id) / invoice.filename
        if old_path.exists():
            old_path.unlink()

    ext = Path(file.filename or "file.pdf").suffix or ".pdf"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = _invoice_dir(instrument_id) / filename
    dest.write_bytes(content)

    invoice.filename = filename
    await session.commit()
    await session.refresh(invoice, attribute_names=["currency"])
    return invoice


async def delete_file(
    session: AsyncSession, instrument_id: int, invoice_id: int
) -> InstrumentInvoice:
    invoice = await get_by_id(session, instrument_id, invoice_id)
    if invoice.filename:
        file_path = _invoice_dir(instrument_id) / invoice.filename
        if file_path.exists():
            file_path.unlink()
        invoice.filename = None
        await session.commit()
        await session.refresh(invoice, attribute_names=["currency"])
    return invoice


async def delete(session: AsyncSession, instrument_id: int, invoice_id: int) -> None:
    invoice = await get_by_id(session, instrument_id, invoice_id)
    if invoice.filename:
        file_path = _invoice_dir(instrument_id) / invoice.filename
        if file_path.exists():
            file_path.unlink()
    await session.delete(invoice)
    await session.commit()
