"""Write a validated draft into the inventory, all or nothing.

The regular item/musician/loan services commit after every call. An import
of dozens of rows must not leave half of them behind when row 17 fails, so
this module builds the ORM objects itself and commits once at the end.
Image files are written before the commit and removed again on failure.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.import_session import ImportSession
from mv_hofki.models.instrument_detail import InstrumentDetail
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.item_image import ItemImage
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.schemas.inventory_item import format_display_nr
from mv_hofki.services import item_image as item_image_service

from .pages import crop
from .resolve import Context, _fold, load_context, validate_draft
from .session import _page_image

ITEM_FIELDS = (
    "label",
    "manufacturer",
    "acquisition_cost",
    "currency_id",
    "owner",
    "notes",
)
DETAIL_FIELDS = (
    "instrument_type_id",
    "serial_nr",
    "construction_year",
    "distributor",
    "container",
    "particularities",
)


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


async def run_import(db: AsyncSession, session: ImportSession) -> dict[str, Any]:
    if session.status == "imported":
        raise HTTPException(status_code=409, detail="Sitzung wurde bereits importiert")
    if session.status in ("analyzing", "importing"):
        raise HTTPException(status_code=409, detail="Sitzung ist gerade in Arbeit")
    if not session.draft_json:
        raise HTTPException(status_code=400, detail="Kein Entwurf vorhanden")

    draft = json.loads(session.draft_json)
    ctx: Context = await load_context(db)
    validation = validate_draft(draft, ctx)
    summary = validation["summary"]
    if summary["blocking"]:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Entwurf enthält {summary['errors']} Fehler "
                "und kann nicht importiert werden"
                if summary["errors"]
                else "Entwurf enthält keine zu importierenden Zeilen"
            ),
        )

    # Claim the session so a double click cannot import twice.
    session.status = "importing"
    await db.commit()

    pages_by_id = {p.id: p for p in session.pages}
    draft_photos = {p.get("key"): p for p in draft.get("photos", [])}
    written_files: list[Path] = []
    result: dict[str, Any] = {"items": [], "musicians": [], "loans": [], "images": []}

    try:
        used_numbers: dict[str, set[int]] = {}
        new_musicians: dict[str, Musician] = {}

        for row in validation["rows"]:
            if row["skip"]:
                continue
            fields = row["fields"]

            prefix = fields["number_prefix"]
            used = used_numbers.setdefault(
                prefix, ctx.used_numbers(prefix) | ctx.retired_numbers(prefix)
            )
            nr = fields.get("inventory_nr")
            if nr is None:
                nr = (max(used) if used else 0) + 1
            used.add(nr)

            item = InventoryItem(
                category="instrument",
                number_prefix=prefix,
                inventory_nr=nr,
                acquisition_date=_date(fields.get("acquisition_date")),
                **{k: fields.get(k) for k in ITEM_FIELDS},
            )
            db.add(item)
            await db.flush()
            db.add(
                InstrumentDetail(
                    item_id=item.id, **{k: fields.get(k) for k in DETAIL_FIELDS}
                )
            )
            result["items"].append(
                {
                    "row_key": row["key"],
                    "item_id": item.id,
                    "inventory_nr": nr,
                    "display_nr": format_display_nr(prefix, nr),
                    "label": item.label,
                }
            )

            # --- musician + loan ---
            musician_id: int | None = None
            m = row["musician"]
            if m["action"] == "existing":
                musician_id = m["musician_id"]
            elif m["action"] == "create":
                key = _fold(f"{m.get('last_name')} {m.get('first_name')}")
                musician = new_musicians.get(key)
                if musician is None:
                    musician = Musician(
                        first_name=m["first_name"],
                        last_name=m["last_name"],
                        is_extern=bool(m.get("is_extern")),
                    )
                    db.add(musician)
                    await db.flush()
                    new_musicians[key] = musician
                    result["musicians"].append(
                        {
                            "musician_id": musician.id,
                            "name": f"{musician.first_name} {musician.last_name}",
                        }
                    )
                musician_id = musician.id

            loan_info = row["loan"]
            if loan_info["action"] == "create" and musician_id is not None:
                loan = Loan(
                    item_id=item.id,
                    musician_id=musician_id,
                    start_date=_date(loan_info["start_date"]),
                    end_date=_date(loan_info.get("end_date")),
                )
                db.add(loan)
                await db.flush()
                result["loans"].append(
                    {
                        "loan_id": loan.id,
                        "item_id": item.id,
                        "musician_id": musician_id,
                        "active": loan.end_date is None,
                    }
                )

            # --- photos ---
            attached = [
                draft_photos[p["key"]]
                for p in validation["photos"]
                if p["action"] == "attach"
                and p["row_key"] == row["key"]
                and p["key"] in draft_photos
            ]
            for i, photo in enumerate(attached):
                page = pages_by_id.get(photo.get("page_id"))
                bbox = photo.get("bbox_2d")
                if page is None or not bbox:
                    continue
                try:
                    png = crop(_page_image(page), bbox)
                except (ValueError, OSError):
                    continue
                filename = f"{uuid.uuid4().hex}.png"
                dest = item_image_service.item_dir(item.id) / filename
                dest.write_bytes(png)
                written_files.append(dest)
                image = ItemImage(
                    item_id=item.id, filename=filename, is_profile=(i == 0)
                )
                db.add(image)
                await db.flush()
                result["images"].append({"item_id": item.id, "image_id": image.id})

        result["counts"] = {
            "items": len(result["items"]),
            "musicians": len(result["musicians"]),
            "loans": len(result["loans"]),
            "images": len(result["images"]),
        }
        session.status = "imported"
        session.import_result_json = json.dumps(result, ensure_ascii=False)
        await db.commit()
    except Exception:
        await db.rollback()
        for f in written_files:
            f.unlink(missing_ok=True)
        session.status = "review"
        await db.commit()
        raise

    await db.refresh(session)
    return result
