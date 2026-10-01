"""Labels: QR code + inventory number + "MV Hofkirchen" (and the logo).

Drawn directly with PyMuPDF (not via HTML) so every label sits exactly where
the sheet or roll expects it. A layout is either a roll (one label per page,
the page is the label) or an A4 sheet of columns × rows with page margins and
gaps; there are presets for common formats and custom sizes in mm.
"""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf
from fastapi import HTTPException

from .pdf import FONT_DIR, LOGO, MM, item_url, qr_png

ORG = "MV Hofkirchen"
A4_W, A4_H = 210.0, 297.0


@dataclass(frozen=True)
class Layout:
    """All sizes in mm. cols/rows 0 = roll (the page is one label)."""

    width: float
    height: float
    cols: int = 0
    rows: int = 0
    margin_left: float = 0
    margin_top: float = 0
    gap_x: float = 0
    gap_y: float = 0

    @property
    def is_sheet(self) -> bool:
        return self.cols > 0 and self.rows > 0

    @property
    def per_page(self) -> int:
        return self.cols * self.rows if self.is_sheet else 1


# Presets shown in the print dialog (keys are used by the frontend too).
PRESETS: dict[str, tuple[str, Layout]] = {
    "roll-62x29": (
        "Etikettenrolle 62 × 29 mm (z. B. Brother DK-11209)",
        Layout(62, 29),
    ),
    "roll-54x25": ("Etikettenrolle 54 × 25 mm (z. B. Dymo 11352)", Layout(54, 25)),
    "a4-70x37": (
        "A4-Bogen 70 × 37 mm, 3 × 8 (z. B. Avery Zweckform 3474)",
        Layout(70, 37, cols=3, rows=8, margin_top=0.5),
    ),
    "a4-63x38": (
        "A4-Bogen 63,5 × 38,1 mm, 3 × 7 (z. B. Avery L7160)",
        Layout(
            63.5, 38.1, cols=3, rows=7, margin_left=7.2, margin_top=15.15, gap_x=2.54
        ),
    ),
    "a4-48x25": (
        "A4-Bogen 48,5 × 25,4 mm, 4 × 11 (z. B. Avery Zweckform 3657)",
        Layout(48.5, 25.4, cols=4, rows=11, margin_left=8, margin_top=21.5),
    ),
}


def custom_layout(
    width: float,
    height: float,
    cols: int,
    rows: int,
    margin_left: float,
    margin_top: float,
    gap_x: float,
    gap_y: float,
) -> Layout:
    """A layout from the dialog's "Eigene Maße"; checked to fit on A4."""
    layout = Layout(width, height, cols, rows, margin_left, margin_top, gap_x, gap_y)
    if not (15 <= width <= 210 and 10 <= height <= 297):
        raise HTTPException(
            status_code=422,
            detail="Etikett: Breite 15–210 mm, Höhe 10–297 mm",
        )
    if layout.is_sheet:
        used_w = margin_left + cols * width + (cols - 1) * gap_x
        used_h = margin_top + rows * height + (rows - 1) * gap_y
        if used_w > A4_W + 0.5 or used_h > A4_H + 0.5:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Die Etiketten passen nicht auf A4 "
                    f"({used_w:.1f} × {used_h:.1f} mm statt höchstens 210 × 297 mm)"
                ),
            )
    return layout


@dataclass(frozen=True)
class LabelItem:
    id: int
    display_nr: str


def _label_rects(
    layout: Layout, count: int, start: int
) -> list[tuple[int, pymupdf.Rect]]:
    """(page index, rect in pt) for count labels, leaving the first start-1
    positions of the first sheet empty."""
    out = []
    if not layout.is_sheet:
        rect = pymupdf.Rect(0, 0, layout.width * MM, layout.height * MM)
        return [(i, rect) for i in range(count)]
    for n in range(start - 1, start - 1 + count):
        page, pos = divmod(n, layout.per_page)
        row, col = divmod(pos, layout.cols)
        x = layout.margin_left + col * (layout.width + layout.gap_x)
        y = layout.margin_top + row * (layout.height + layout.gap_y)
        out.append(
            (
                page,
                pymupdf.Rect(
                    x * MM, y * MM, (x + layout.width) * MM, (y + layout.height) * MM
                ),
            )
        )
    return out


def _fit_size(font: pymupdf.Font, text: str, width: float, start: float) -> float:
    """The largest font size <= start at which text fits into width."""
    size = start
    while size > 4 and font.text_length(text, fontsize=size) > width:
        size -= 0.5
    return size


def _draw_label(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    item: LabelItem,
    *,
    bold: pymupdf.Font,
    regular: pymupdf.Font,
    logo: dict[str, int] | None,
    frame: bool,
) -> None:
    """logo: None = no logo; else {"xref": …} filled on the first label, so
    the image is embedded once and reused."""
    pad = min(rect.height, rect.width) * 0.08
    inner = rect + (pad, pad, -pad, -pad)
    # QR code: a square on the left, as high as the label allows.
    qr_side = min(inner.height, inner.width * 0.5)
    qr = pymupdf.Rect(inner.x0, inner.y0, inner.x0 + qr_side, inner.y0 + qr_side)
    qr.y0 += (inner.height - qr_side) / 2
    qr.y1 = qr.y0 + qr_side
    page.insert_image(qr, stream=qr_png(item_url(item.id), scale=6))

    # Right of it: inventory number large, organisation (and logo) small.
    text = pymupdf.Rect(qr.x1 + pad, inner.y0, inner.x1, inner.y1)
    org_size = max(5.0, min(8.0, rect.height * 0.16))
    nr_size = _fit_size(
        bold, item.display_nr, text.width, min(22.0, rect.height * 0.42)
    )

    writer = pymupdf.TextWriter(page.rect)
    nr_y = text.y0 + text.height * 0.5 + nr_size * 0.35
    writer.append((text.x0, nr_y), item.display_nr, font=bold, fontsize=nr_size)

    org_x = text.x0
    org_y = text.y1 - org_size * 0.25
    if logo is not None:
        side = min(text.height * 0.38, org_size * 2.6)
        box = pymupdf.Rect(text.x0, text.y1 - side, text.x0 + side, text.y1)
        if "xref" in logo:
            page.insert_image(box, xref=logo["xref"])
        else:
            logo["xref"] = page.insert_image(box, filename=str(LOGO))
        org_x = box.x1 + pad * 0.5
        org_y = box.y1 - (side - org_size) / 2 - org_size * 0.2
    org = _fit_size(regular, ORG, text.x1 - org_x, org_size)
    writer.append((org_x, org_y), ORG, font=regular, fontsize=org)
    writer.write_text(page, color=(0.106, 0.153, 0.208))
    if frame:
        page.draw_rect(rect, color=(0.6, 0.65, 0.7), width=0.3)


def render(
    items: list[LabelItem],
    layout: Layout,
    *,
    start: int = 1,
    logo: bool = True,
    frame: bool = False,
) -> bytes:
    if layout.is_sheet and not 1 <= start <= layout.per_page:
        raise HTTPException(
            status_code=422,
            detail=f"„Beginnen bei“: 1 bis {layout.per_page}",
        )
    doc = pymupdf.open()
    bold = pymupdf.Font(fontfile=str(FONT_DIR / "DMSans-Bold.ttf"))
    regular = pymupdf.Font(fontfile=str(FONT_DIR / "DMSans-Regular.ttf"))
    page_rect = (
        pymupdf.paper_rect("a4")
        if layout.is_sheet
        else pymupdf.Rect(0, 0, layout.width * MM, layout.height * MM)
    )
    pages: dict[int, pymupdf.Page] = {}
    logo_ref: dict[str, int] | None = {} if logo else None
    for item, (page_index, rect) in zip(
        items, _label_rects(layout, len(items), start if layout.is_sheet else 1)
    ):
        page = pages.get(page_index)
        if page is None:
            page = doc.new_page(width=page_rect.width, height=page_rect.height)
            pages[page_index] = page
        _draw_label(
            page,
            rect,
            item,
            bold=bold,
            regular=regular,
            logo=logo_ref,
            frame=frame,
        )
    data: bytes = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return data
