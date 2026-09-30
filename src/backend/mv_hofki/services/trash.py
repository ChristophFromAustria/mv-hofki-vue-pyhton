"""Papierkorb: list, restore and purge trashed rows; empty it after 90 days.

Deleting moves a row to the trash (``deleted_at``, see db/soft_delete.py);
this module is the only place that deletes for good. Purging a musician also
removes their (returned) loans; purging an item removes its images,
invoices, loans and upload folders and retires its inventory number.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.db.soft_delete import utcnow, with_deleted
from mv_hofki.models.clothing_type import ClothingType
from mv_hofki.models.currency import Currency
from mv_hofki.models.event import Event
from mv_hofki.models.general_item_category import GeneralItemCategory
from mv_hofki.models.general_item_category import general_item_category_links as links
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.item_image import ItemImage
from mv_hofki.models.item_invoice import ItemInvoice
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.models.register import Register, musician_registers
from mv_hofki.models.sheet_music_genre import SheetMusicGenre
from mv_hofki.schemas.inventory_item import format_display_nr
from mv_hofki.services import audit
from mv_hofki.services import inventory_item as item_service

log = logging.getLogger(__name__)

PURGE_AFTER = timedelta(days=90)


async def _item_label(session: AsyncSession, item_id: int) -> str:
    item = await session.get(
        InventoryItem, item_id, execution_options={"include_deleted": True}
    )
    if item is None:
        return f"Gegenstand {item_id}"
    return f"{format_display_nr(item.number_prefix, item.inventory_nr)} {item.label}"


# --- purging (returns files to remove after commit) -------------------------


async def _purge_item(session: AsyncSession, obj: Any) -> list[Path]:
    return await item_service.purge_item(session, obj)


async def _purge_musician(session: AsyncSession, obj: Any) -> list[Path]:
    await session.execute(sa_delete(Loan).where(Loan.musician_id == obj.id))
    await session.execute(
        sa_delete(musician_registers).where(musician_registers.c.musician_id == obj.id)
    )
    await session.delete(obj)
    return []


async def _purge_invoice(session: AsyncSession, obj: Any) -> list[Path]:
    from mv_hofki.services.item_invoice import invoice_file

    path = invoice_file(obj)
    await session.delete(obj)
    return [path] if path else []


async def _purge_image(session: AsyncSession, obj: Any) -> list[Path]:
    from mv_hofki.services.item_image import image_file

    path = image_file(obj)
    await session.delete(obj)
    return [path]


async def _purge_category(session: AsyncSession, obj: Any) -> list[Path]:
    await session.execute(sa_delete(links).where(links.c.category_id == obj.id))
    await session.delete(obj)
    return []


async def _purge_plain(session: AsyncSession, obj: Any) -> list[Path]:
    await session.delete(obj)
    return []


# --- what can be in the trash -----------------------------------------------


@dataclass(frozen=True)
class Kind:
    key: str  # also the event log's entity_type
    label: str  # "Gegenstand", "Musiker", …
    model: Any
    title: Callable[[AsyncSession, Any], Awaitable[str]]
    purge: Callable[[AsyncSession, Any], Awaitable[list[Path]]]
    # The item a row belongs to (invoices, images), shown as context.
    item_id: Callable[[Any], int | None] = lambda obj: None


async def _title_item(s: AsyncSession, o: Any) -> str:
    return f"{format_display_nr(o.number_prefix, o.inventory_nr)} {o.label}"


async def _title_musician(s: AsyncSession, o: Any) -> str:
    return f"{o.first_name} {o.last_name}"


async def _title_invoice(s: AsyncSession, o: Any) -> str:
    return f"Rechnung „{o.title}“"


async def _title_image(s: AsyncSession, o: Any) -> str:
    return o.caption or "Bild"


async def _title_label(s: AsyncSession, o: Any) -> str:
    return str(o.label)


async def _title_currency(s: AsyncSession, o: Any) -> str:
    return f"{o.label} ({o.abbreviation})"


KINDS: dict[str, Kind] = {
    k.key: k
    for k in (
        Kind("item", "Gegenstand", InventoryItem, _title_item, _purge_item),
        Kind("musician", "Musiker", Musician, _title_musician, _purge_musician),
        Kind(
            "invoice",
            "Rechnung",
            ItemInvoice,
            _title_invoice,
            _purge_invoice,
            item_id=lambda o: o.item_id,
        ),
        Kind(
            "image",
            "Bild",
            ItemImage,
            _title_image,
            _purge_image,
            item_id=lambda o: o.item_id,
        ),
        Kind(
            "instrument_type",
            "Instrumententyp",
            InstrumentType,
            _title_label,
            _purge_plain,
        ),
        Kind("clothing_type", "Kleidungstyp", ClothingType, _title_label, _purge_plain),
        Kind("register", "Register", Register, _title_label, _purge_plain),
        Kind(
            "general_item_category",
            "Kategorie",
            GeneralItemCategory,
            _title_label,
            _purge_category,
        ),
        Kind(
            "sheet_music_genre", "Gattung", SheetMusicGenre, _title_label, _purge_plain
        ),
        Kind("currency", "Währung", Currency, _title_currency, _purge_plain),
    )
}
# Purge order: rows that belong to an item before the item, master data last.
PURGE_ORDER = (
    "image",
    "invoice",
    "item",
    "musician",
    "instrument_type",
    "clothing_type",
    "register",
    "general_item_category",
    "sheet_music_genre",
    "currency",
)


def _kind(key: str) -> Kind:
    kind = KINDS.get(key)
    if kind is None:
        raise HTTPException(status_code=404, detail=f"Unbekannte Art: {key}")
    return kind


async def _trashed(session: AsyncSession, kind: Kind, obj_id: int) -> Any:
    obj = await session.scalar(
        with_deleted(
            select(kind.model).where(
                kind.model.id == obj_id, kind.model.deleted_at.is_not(None)
            )
        )
    )
    if obj is None:
        raise HTTPException(status_code=404, detail="Nicht im Papierkorb")
    return obj


# --- public API ---------------------------------------------------------------


async def list_trash(session: AsyncSession) -> list[dict[str, Any]]:
    """Everything in the trash, newest first, with who deleted it."""
    entries: list[dict[str, Any]] = []
    for kind in KINDS.values():
        rows = (
            await session.execute(
                with_deleted(
                    select(kind.model).where(kind.model.deleted_at.is_not(None))
                )
            )
        ).scalars()
        for obj in rows:
            item_id = kind.item_id(obj)
            entries.append(
                {
                    "kind": kind.key,
                    "kind_label": kind.label,
                    "id": obj.id,
                    "label": await kind.title(session, obj),
                    "context": await _item_label(session, item_id)
                    if item_id is not None
                    else None,
                    "deleted_at": obj.deleted_at,
                    "purge_at": obj.deleted_at + PURGE_AFTER,
                    "deleted_by": None,
                }
            )
    # Who: the latest "trashed" event of each entry.
    if entries:
        trashed = await session.execute(
            select(Event.entity_type, Event.entity_id, Event.actor, Event.source)
            .where(Event.action == "trashed")
            .order_by(Event.at, Event.id)
        )
        by = {
            (t, i): (a or (None if s == "web" else s)) for t, i, a, s in trashed.all()
        }
        for e in entries:
            e["deleted_by"] = by.get((e["kind"], e["id"]))
    entries.sort(key=lambda e: e["deleted_at"], reverse=True)
    return entries


async def restore(session: AsyncSession, kind_key: str, obj_id: int) -> None:
    kind = _kind(kind_key)
    obj = await _trashed(session, kind, obj_id)
    obj.deleted_at = None
    await session.commit()


async def purge(session: AsyncSession, kind_key: str, obj_id: int) -> None:
    kind = _kind(kind_key)
    obj = await _trashed(session, kind, obj_id)
    files = await kind.purge(session, obj)
    await session.commit()
    item_service.remove_paths(files)


async def purge_expired(session: AsyncSession, now: datetime | None = None) -> int:
    """Delete for good what has been in the trash longer than PURGE_AFTER."""
    cutoff = (now or utcnow()) - PURGE_AFTER
    files: list[Path] = []
    count = 0
    for key in PURGE_ORDER:
        kind = KINDS[key]
        rows = (
            await session.execute(
                with_deleted(
                    select(kind.model).where(
                        kind.model.deleted_at.is_not(None),
                        kind.model.deleted_at < cutoff,
                    )
                )
            )
        ).scalars()
        for obj in list(rows):
            files += await kind.purge(session, obj)
            count += 1
    await session.commit()
    item_service.remove_paths(files)
    return count


async def count_trash(session: AsyncSession) -> int:
    total = 0
    for kind in KINDS.values():
        total += (
            await session.scalar(
                with_deleted(
                    select(func.count()).where(kind.model.deleted_at.is_not(None))
                )
            )
            or 0
        )
    return total


async def run_daily_purge(session_factory: Any) -> None:
    """Background task: empty expired trash now and then once a day."""
    while True:
        try:
            with audit.audit_context(source="system"):
                async with session_factory() as session:
                    purged = await purge_expired(session)
            if purged:
                log.info("Papierkorb: %d Einträge nach 90 Tagen gelöscht", purged)
        except Exception:  # pragma: no cover - keep the task alive
            log.exception("Papierkorb konnte nicht geleert werden")
        await asyncio.sleep(24 * 60 * 60)
