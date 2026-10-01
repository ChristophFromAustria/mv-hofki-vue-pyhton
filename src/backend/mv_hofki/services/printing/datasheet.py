"""Data sheets: one A4 page (or more) per item, sections chosen by the user."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.db.soft_delete import with_deleted
from mv_hofki.models.item_image import ItemImage
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.schemas.inventory_item import RETIRE_REASONS
from mv_hofki.services import inventory_item as item_service
from mv_hofki.services import item_invoice as invoice_service
from mv_hofki.services.item_image import image_file

from .pdf import (
    CONTENT_WIDTH,
    MM,
    PdfDocument,
    col,
    de_date,
    de_money,
    esc,
    footer_text,
    item_url,
    qr_png,
    shrink_image,
    text_block,
)


def g(obj: Any, key: str) -> Any:
    """A value of a dict, a model or an ORM row alike (get_by_id mixes them)."""
    if obj is None:
        return None
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


# Sections the user can choose (the header and master data are always there).
SECTIONS = ("photo", "loan", "loan_history", "invoices", "notes")

# The master data shown per category, in this order; empty values are left out.
Row = tuple[str, Callable[[dict[str, Any]], Any]]


def _money(i: dict[str, Any]) -> str:
    return de_money(i.get("acquisition_cost"), g(i.get("currency"), "abbreviation"))


def _qty(i: dict[str, Any]) -> str:
    q = i.get("quantity") or 1
    return f"{q} Stück" if q != 1 else ""


COMMON_END: list[Row] = [
    ("Eigentümer", lambda i: i.get("owner")),
    ("Anschaffungsdatum", lambda i: de_date(i.get("acquisition_date"))),
    ("Anschaffungskosten", _money),
    ("Lagerort", lambda i: i.get("storage_location")),
]

MASTER_DATA: dict[str, list[Row]] = {
    "instrument": [
        ("Typ", lambda i: g(i.get("instrument_type"), "label")),
        ("Menge", _qty),
        ("Hersteller", lambda i: i.get("manufacturer")),
        ("Seriennummer", lambda i: i.get("serial_nr")),
        ("Baujahr", lambda i: i.get("construction_year")),
        ("Händler", lambda i: i.get("distributor")),
        ("Behältnis", lambda i: i.get("container")),
        *COMMON_END,
        ("Besonderheiten", lambda i: i.get("particularities")),
    ],
    "clothing": [
        ("Typ", lambda i: g(i.get("clothing_type"), "label")),
        ("Menge", _qty),
        ("Größe", lambda i: i.get("size")),
        ("Geschlecht", lambda i: i.get("gender")),
        ("Hersteller", lambda i: i.get("manufacturer")),
        *COMMON_END,
    ],
    "sheet_music": [
        ("Komponist", lambda i: i.get("composer")),
        ("Arrangeur", lambda i: i.get("arranger")),
        ("Schwierigkeitsgrad", lambda i: i.get("difficulty")),
        ("Gattung", lambda i: g(i.get("genre"), "label")),
        ("Menge", _qty),
        *COMMON_END,
    ],
    "general_item": [
        (
            "Kategorien",
            lambda i: ", ".join(g(c, "label") for c in i.get("categories") or []),
        ),
        ("Menge", _qty),
        ("Hersteller", lambda i: i.get("manufacturer")),
        *COMMON_END,
    ],
}

# Column widths in pt; the content is CONTENT_WIDTH wide (A4, 15 mm margins).
KEY_W = 120
VALUE_W = CONTENT_WIDTH - KEY_W
QR_SIZE = int(26 * MM)
# The QR cell: the code, right-aligned, with a little air to its left.
QR_W = QR_SIZE + 10
# The profile photo (top left) is as high as the QR code, at most this wide.
PHOTO_MAX_W = CONTENT_WIDTH - QR_W - 20

CSS = """
.head td { border: none; padding: 0; }
.status { margin-top: 3pt; }
.kv th { width: 120pt; }
.head-text { margin-top: 8pt; }
"""


def _status(item: dict[str, Any]) -> str:
    if item.get("retired_at"):
        reason = RETIRE_REASONS.get(item.get("retired_reason") or "", "")
        return f"Ausgeschieden am {de_date(item['retired_at'])} · {reason}"
    loan = item.get("active_loan")
    if loan:
        return (
            f"Ausgeliehen an {g(loan, 'musician_name')} "
            f"seit {de_date(g(loan, 'start_date'))}"
        )
    return "Verfügbar"


def _master_rows(item: dict[str, Any]) -> str:
    rows = []
    for label, get in MASTER_DATA.get(item["category"], []):
        value = get(item)
        if value in (None, ""):
            continue
        rows.append(
            f"<tr><th {col(KEY_W)}>{esc(label)}</th>"
            f"<td {col(VALUE_W)}>{text_block(str(value))}</td></tr>"
        )
    return f'<table class="kv">{"".join(rows)}</table>' if rows else ""


def _loan_section(item: dict[str, Any]) -> str:
    loan = item.get("active_loan")
    if not loan:
        return "<h2>Aktuelle Ausleihe</h2><p class='muted'>Nicht ausgeliehen.</p>"
    rows = [
        ("Ausgeliehen an", g(loan, "musician_name")),
        ("Seit", de_date(g(loan, "start_date"))),
        ("Rückgabe geplant", de_date(g(loan, "due_date"))),
        ("Notiz", g(loan, "notes")),
    ]
    cells = "".join(
        f"<tr><th {col(KEY_W)}>{esc(k)}</th>"
        f"<td {col(VALUE_W)}>{text_block(str(v))}</td></tr>"
        for k, v in rows
        if v
    )
    return f'<h2>Aktuelle Ausleihe</h2><table class="kv">{cells}</table>'


def _history_section(loans: list[tuple[Loan, Musician]]) -> str:
    if not loans:
        return "<h2>Leihhistorie</h2><p class='muted'>Noch nie ausgeliehen.</p>"
    rows = "".join(
        "<tr>"
        f'<td {col(160)}>{esc(m.first_name)} {esc(m.last_name)}</td>'
        f'<td {col(65)}>{de_date(loan.start_date)}</td>'
        f'<td {col(65)}>{de_date(loan.end_date) or "—"}</td>'
        f'<td {col(CONTENT_WIDTH - 290)}>{text_block(loan.notes)}</td>'
        "</tr>"
        for loan, m in loans
    )
    return (
        "<h2>Leihhistorie</h2><table>"
        "<tr><th>Musiker</th><th>Von</th><th>Bis</th><th>Notiz</th></tr>"
        f"{rows}</table>"
    )


def _invoice_section(invoices: list[Any]) -> str:
    if not invoices:
        return "<h2>Rechnungen</h2><p class='muted'>Keine Rechnungen.</p>"
    rows = "".join(
        "<tr>"
        f"<td {col(65)}>{de_date(inv.date_issued)}</td>"
        f"<td {col(200)}>{esc(inv.title)}</td>"
        f"<td {col(CONTENT_WIDTH - 355)}>{esc(inv.invoice_issuer)}</td>"
        f'<td class="num" {col(90)}>'
        f"{de_money(inv.amount, g(inv.currency, 'abbreviation'))}</td>"
        "</tr>"
        for inv in invoices
    )
    return (
        "<h2>Rechnungen</h2><table>"
        "<tr><th>Datum</th><th>Bezeichnung</th><th>Aussteller</th>"
        '<th class="num">Betrag</th></tr>'
        f"{rows}</table>"
    )


async def _loans(session: AsyncSession, item_id: int) -> list[tuple[Loan, Musician]]:
    # Loans of musicians in the trash belong to the item's history too.
    result = await session.execute(
        with_deleted(
            select(Loan, Musician)
            .join(Musician, Musician.id == Loan.musician_id)
            .where(Loan.item_id == item_id)
            .order_by(Loan.start_date.desc(), Loan.id.desc())
        )
    )
    return [(loan, m) for loan, m in result.all()]


async def _profile_photo(
    session: AsyncSession, item_id: int
) -> tuple[bytes, int, int] | None:
    image = await session.scalar(
        select(ItemImage).where(
            ItemImage.item_id == item_id, ItemImage.is_profile.is_(True)
        )
    )
    # Printed only QR-high (~26 mm): 600 px are plenty.
    return shrink_image(image_file(image), max_px=600) if image else None


def _head(item: dict[str, Any], photo: tuple[bytes, int, int] | None) -> str:
    """Number, label and status; the QR code top right. With a photo, the
    photo takes the top left (as high as the QR code) and the text follows
    below the two."""
    qr = (
        f'<td style="width: {QR_W}pt; text-align: right">'
        f'<img src="qr.png" width="{QR_SIZE}" height="{QR_SIZE}"/></td>'
    )
    text = (
        f'<p class="muted">{esc(item["display_nr"])}</p>'
        f"<h1>{esc(item['label'])}</h1>"
        f'<p class="status">{esc(_status(item))}</p>'
    )
    left = CONTENT_WIDTH - QR_W
    if photo is None:
        # The head table has no cell padding (CSS), so plain widths.
        return (
            f'<table class="head"><tr><td style="width: {left}pt">{text}</td>'
            f"{qr}</tr></table>"
        )
    _, px_w, px_h = photo
    height = QR_SIZE
    width = min(PHOTO_MAX_W, round(height * px_w / px_h))
    if width == PHOTO_MAX_W:  # very wide photo: keep the aspect ratio
        height = round(width * px_h / px_w)
    return (
        f'<table class="head"><tr><td style="width: {left}pt">'
        f'<img src="photo.jpg" width="{width}" height="{height}"/></td>'
        f"{qr}</tr></table>"
        f'<div class="head-text">{text}</div>'
    )


async def add_datasheet(
    session: AsyncSession, pdf: PdfDocument, item_id: int, sections: set[str]
) -> None:
    item = await item_service.get_by_id(session, item_id)
    files = {"qr.png": qr_png(item_url(item_id))}
    photo = await _profile_photo(session, item_id) if "photo" in sections else None
    if photo is not None:
        files["photo.jpg"] = photo[0]
    parts = [_head(item, photo)]
    if item.get("retired_at") and item.get("retired_notes"):
        parts.append(f'<p class="muted">{text_block(item["retired_notes"])}</p>')
    parts.append("<h2>Stammdaten</h2>" + _master_rows(item))
    if "loan" in sections and item["category"] != "sheet_music":
        parts.append(_loan_section(item))
    if "loan_history" in sections and item["category"] != "sheet_music":
        parts.append(_history_section(await _loans(session, item_id)))
    if "invoices" in sections:
        parts.append(_invoice_section(await invoice_service.get_all(session, item_id)))
    if "notes" in sections and item.get("notes"):
        parts.append(f"<h2>Notizen</h2><p>{text_block(item['notes'])}</p>")
    pdf.add_story("".join(parts), CSS, files)


async def render(
    session: AsyncSession, item_ids: list[int], sections: set[str]
) -> bytes:
    pdf = PdfDocument()
    for item_id in item_ids:
        await add_datasheet(session, pdf, item_id, sections)
    return pdf.finish(footer_text())
