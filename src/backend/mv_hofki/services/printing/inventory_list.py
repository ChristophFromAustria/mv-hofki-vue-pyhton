"""Inventory list: a landscape table of the items a list shows, columns chosen
by the user, grouped like the list, with counts and optional cost totals."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.filters.base import PageParams
from mv_hofki.filters.inventory_item import CATEGORY_LABELS, ItemFilter
from mv_hofki.models.clothing_type import ClothingType
from mv_hofki.models.general_item_category import GeneralItemCategory
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.sheet_music_genre import SheetMusicGenre
from mv_hofki.schemas.inventory_item import RETIRE_REASONS
from mv_hofki.services import inventory_item as item_service

from .datasheet import g
from .pdf import (
    CELL_PADDING,
    MARGIN_MM,
    MM,
    PdfDocument,
    de_date,
    de_money,
    esc,
    footer_text,
)

# Text width of A4 landscape with the usual margins, in pt.
WIDTH = int(842 - 2 * MARGIN_MM * MM)


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    weight: float  # share of the table width
    value: Callable[[dict[str, Any]], Any]
    numeric: bool = False


def _status(i: dict[str, Any]) -> str:
    if i.get("retired_at"):
        return (
            f"Ausgeschieden ({RETIRE_REASONS.get(i.get('retired_reason') or '', '')})"
        )
    loan = i.get("active_loan")
    if not loan:
        return "Verfügbar"
    due = g(loan, "due_date")
    if due and due < date.today():
        return "Überfällig"
    return "Ausgeliehen"


def _cost(i: dict[str, Any]) -> str:
    return de_money(i.get("acquisition_cost"), g(i.get("currency"), "abbreviation"))


def _type(i: dict[str, Any]) -> Any:
    for key in ("instrument_type", "clothing_type", "genre"):
        if i.get(key) is not None:
            return g(i[key], "label")
    return ", ".join(g(c, "label") for c in i.get("categories") or [])


COLUMNS: dict[str, Column] = {
    c.key: c
    for c in (
        Column("label", "Bezeichnung", 3, lambda i: i.get("label")),
        Column("type", "Typ / Gattung / Kategorien", 2.2, _type),
        Column("manufacturer", "Hersteller", 1.8, lambda i: i.get("manufacturer")),
        Column("serial_nr", "Seriennummer", 1.5, lambda i: i.get("serial_nr")),
        Column(
            "construction_year",
            "Baujahr",
            0.8,
            lambda i: i.get("construction_year"),
            numeric=True,
        ),
        Column("size", "Größe", 0.8, lambda i: i.get("size")),
        Column("gender", "Geschlecht", 1, lambda i: i.get("gender")),
        Column("composer", "Komponist", 1.8, lambda i: i.get("composer")),
        Column("arranger", "Arrangeur", 1.6, lambda i: i.get("arranger")),
        Column("quantity", "Menge", 0.6, lambda i: i.get("quantity"), numeric=True),
        Column("owner", "Eigentümer", 1.6, lambda i: i.get("owner")),
        Column(
            "storage_location", "Lagerort", 1.8, lambda i: i.get("storage_location")
        ),
        Column(
            "acquisition_date",
            "Angeschafft",
            0.9,
            lambda i: de_date(i.get("acquisition_date")),
        ),
        Column("acquisition_cost", "Kosten", 1.5, _cost, numeric=True),
        Column("status", "Status", 1.4, _status),
        Column(
            "borrower",
            "Ausgeliehen an",
            1.6,
            lambda i: g(i.get("active_loan"), "musician_name"),
        ),
    )
}
NR = Column("display_nr", "Inv.-Nr.", 0.9, lambda i: i.get("display_nr"))

# Which columns exist per category (the dialog offers these).
CATEGORY_COLUMNS = {
    "instrument": [
        "label", "type", "manufacturer", "serial_nr", "construction_year",
        "quantity", "owner", "acquisition_date", "acquisition_cost", "status",
        "borrower",
    ],
    "clothing": [
        "label", "type", "size", "gender", "manufacturer", "quantity", "owner",
        "acquisition_date", "acquisition_cost", "status", "borrower",
    ],
    "sheet_music": [
        "label", "composer", "arranger", "type", "quantity", "storage_location",
        "owner", "acquisition_date", "acquisition_cost",
    ],
    "general_item": [
        "label", "type", "manufacturer", "quantity", "storage_location", "owner",
        "acquisition_date", "acquisition_cost", "status", "borrower",
    ],
}  # fmt: skip

# The type column is called what it holds in each category.
TYPE_LABELS = {
    "instrument": "Typ",
    "clothing": "Typ",
    "sheet_music": "Gattung",
    "general_item": "Kategorien",
}


def column_label(category: str, key: str) -> str:
    if key == "type":
        return TYPE_LABELS.get(category, COLUMNS[key].label)
    return COLUMNS[key].label


CSS = """
body { font-size: 8pt; }
h1 { font-size: 14pt; }
td, th { padding: 2pt 5pt; }
th { font-size: 7.5pt; }
tr.group td { font-weight: bold; padding-top: 8pt; border-bottom: 0.8pt solid #9aa8b8; }
tr.total td { font-weight: bold; border-bottom: none; padding-top: 6pt; }
.filters { margin-bottom: 8pt; }
"""

MAX_ROWS = 300


async def _filter_summary(session: AsyncSession, flt: ItemFilter) -> str:
    """The active filters in words, so the paper says what it covers."""
    parts: list[str] = []
    if flt.search:
        parts.append(f"Suche „{flt.search}“")

    async def names(model: Any, ids: list[int] | None) -> str | None:
        if not ids:
            return None
        rows = await session.execute(select(model.label).where(model.id.in_(ids)))
        return ", ".join(sorted(rows.scalars()))

    for label, model, ids in (
        ("Typ", InstrumentType, flt.instrument_type_id__in),
        ("Typ", ClothingType, flt.clothing_type_id__in),
        ("Gattung", SheetMusicGenre, flt.genre_id__in),
        ("Kategorie", GeneralItemCategory, flt.category_id__in),
    ):
        text = await names(model, ids)
        if text:
            parts.append(f"{label}: {text}")
    if flt.without_category:
        parts.append("ohne Kategorie")
    if flt.status:
        parts.append(
            "Status: "
            + {"verfuegbar": "Verfügbar", "verliehen": "Ausgeliehen"}[flt.status]
        )
    for label, value in (
        ("Eigentümer", flt.owner),
        ("Größe", flt.size),
        ("Geschlecht", flt.gender),
        ("Schwierigkeitsgrad", flt.difficulty),
        ("Lagerort enthält", flt.storage_location__ilike),
    ):
        if value:
            parts.append(f"{label}: {value}")
    if flt.construction_year__gte or flt.construction_year__lte:
        low = flt.construction_year__gte or "…"
        high = flt.construction_year__lte or "…"
        parts.append(f"Baujahr {low}–{high}")
    stock = {
        "aktiv": "im Bestand",
        "ausgeschieden": "nur ausgeschiedene",
        "alle": "Bestand und ausgeschiedene",
    }
    parts.append(stock[flt.bestand])
    return " · ".join(parts)


async def render(
    session: AsyncSession,
    *,
    category: str,
    flt: ItemFilter,
    columns: list[str],
    totals: bool,
) -> bytes:
    allowed = CATEGORY_COLUMNS.get(category)
    if allowed is None:
        raise HTTPException(status_code=400, detail=f"Ungültige Kategorie: {category}")
    chosen = [COLUMNS[k] for k in allowed if k in columns] or [COLUMNS["label"]]
    cols = [NR, *chosen]

    summary = await _filter_summary(session, flt)
    page = await item_service.get_list(
        session,
        category=category,
        flt=flt,
        page=PageParams(limit=MAX_ROWS + 1, offset=0),
    )
    if not page.rows:
        raise HTTPException(
            status_code=422, detail="Keine Gegenstände für diese Filter"
        )
    if page.total > MAX_ROWS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{page.total} Zeilen – höchstens {MAX_ROWS} auf einmal. "
                "Bitte die Liste weiter filtern."
            ),
        )

    scale = WIDTH / sum(c.weight for c in cols)
    widths = [c.weight * scale for c in cols]

    def cell(c: Column, w: float, content: str, tag: str = "td") -> str:
        cls = ' class="num"' if c.numeric else ""
        return f'<{tag}{cls} style="width: {w - CELL_PADDING:.0f}pt">{content}</{tag}>'

    head = (
        "<tr>"
        + "".join(
            cell(
                c,
                w,
                esc(column_label(category, c.key) if c is not NR else c.label),
                "th",
            )
            for c, w in zip(cols, widths)
        )
        + "</tr>"
    )
    group_counts = {gr["key"]: gr["count"] for gr in page.groups or []}
    body: list[str] = []
    group_rows: set[int] = set()
    current_group: str | None = None
    for n, item in enumerate(page.rows):
        if page.row_groups is not None:
            key, label = page.row_groups[n]
            if key != current_group:
                current_group = key
                count = group_counts.get(key, "")
                group_rows.add(len(body))
                body.append(
                    f'<tr class="group"><td colspan="{len(cols)}">'
                    f"{esc(label)} ({count})</td></tr>"
                )
        body.append(
            "<tr>"
            + "".join(
                cell(c, w, esc(c.value(item) if c.value(item) is not None else ""))
                for c, w in zip(cols, widths)
            )
            + "</tr>"
        )

    total_line = (
        f"{page.item_total} {'Gegenstand' if page.item_total == 1 else 'Gegenstände'}"
    )
    if totals:
        sums: dict[str, float] = defaultdict(float)
        seen: set[int] = set()
        for item in page.rows:  # an item can be in several groups: count once
            if item["id"] in seen or item.get("acquisition_cost") is None:
                continue
            seen.add(item["id"])
            sums[g(item.get("currency"), "abbreviation") or ""] += item[
                "acquisition_cost"
            ]
        if sums:
            total_line += " · Anschaffungskosten: " + ", ".join(
                de_money(v, k or None) for k, v in sorted(sums.items())
            )
    body.append(
        f'<tr class="total"><td colspan="{len(cols)}">{esc(total_line)}</td></tr>'
    )

    pdf = PdfDocument(landscape=True)
    title = f"Inventarliste {CATEGORY_LABELS.get(category, category)}"
    pdf.add_table(
        f'<h1>{esc(title)}</h1><p class="muted filters">{esc(summary)}</p>',
        head,
        body,
        CSS,
        keep_with_next=group_rows,
    )
    return pdf.finish(footer_text())
