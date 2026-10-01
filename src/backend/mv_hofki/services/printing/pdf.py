"""Building blocks for the PDFs: HTML/CSS laid out by PyMuPDF's Story,
DM Sans embedded, QR codes, and a footer with page numbers."""

from __future__ import annotations

import html
import io
from datetime import date
from pathlib import Path

import pymupdf
import segno

from mv_hofki.core.config import settings

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"

# Colours of the light theme (style.css); paper is always light.
TEXT = "#1b2735"
MUTED = "#5b6b7f"
BORDER = "#d5dce5"

BASE_CSS = f"""
@font-face {{ font-family: dm; src: url(DMSans-Regular.ttf); }}
@font-face {{ font-family: dm; src: url(DMSans-Medium.ttf); font-weight: 500; }}
@font-face {{ font-family: dm; src: url(DMSans-Bold.ttf); font-weight: bold; }}
@font-face {{ font-family: dm; src: url(DMSans-Italic.ttf); font-style: italic; }}
* {{ font-family: dm; }}
/* MuPDF gives body a default margin; the page margins are set by PdfDocument. */
html, body {{ margin: 0; padding: 0; }}
body {{ font-size: 9.5pt; color: {TEXT}; line-height: 1.35; }}
h1 {{ font-size: 17pt; font-weight: bold; margin: 0 0 2pt 0; }}
h2 {{ font-size: 11pt; font-weight: bold; margin: 14pt 0 4pt 0; }}
p {{ margin: 0 0 4pt 0; }}
.muted {{ color: {MUTED}; }}
.small {{ font-size: 8.5pt; }}
table {{ border-collapse: collapse; }}
td, th {{ padding: 2.5pt 5pt; text-align: left; vertical-align: top;
          border-bottom: 0.5pt solid {BORDER}; }}
th {{ color: {MUTED}; font-weight: normal; }}
td.num, th.num {{ text-align: right; }}
"""

MM = 72 / 25.4  # points per millimetre
MARGIN_MM = 15
# Width of the text area on A4 portrait with MARGIN_MM margins, in pt.
CONTENT_WIDTH = int(595 - 2 * MARGIN_MM * MM)


CELL_PADDING = 10  # left + right padding of td/th in BASE_CSS, in pt


def col(width_pt: float) -> str:
    """Style for a table cell of exactly width_pt (padding included) — MuPDF
    lays out tables by these, not by width attributes or percentages."""
    return f'style="width: {width_pt - CELL_PADDING:.0f}pt"'


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def text_block(value: str | None) -> str:
    """Multi-line text (notes) as HTML, line breaks kept."""
    lines = (value or "").strip().splitlines()
    return "<br/>".join(esc(line) for line in lines)


def de_date(value: date | str | None) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    return value.strftime("%d.%m.%Y")


def de_money(amount: float | None, currency: str | None = None) -> str:
    if amount is None:
        return ""
    text = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return f"{text} {currency}".strip() if currency else text


def item_url(item_id: int) -> str:
    """What a QR code points to: stable even if the inventory number changes."""
    return f"{settings.PUBLIC_URL.rstrip('/')}/inventar/{item_id}"


def qr_png(data: str, scale: int = 8) -> bytes:
    buf = io.BytesIO()
    segno.make(data, error="m").save(buf, kind="png", scale=scale, border=1)
    return buf.getvalue()


def shrink_image(path: Path, max_px: int = 800) -> tuple[bytes, int, int] | None:
    """A photo as (JPEG, width, height) of at most about max_px on the long
    side, to keep PDFs small."""
    try:
        pix = pymupdf.Pixmap(str(path))
    except Exception:  # missing or unreadable file: leave the photo out
        return None
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    if pix.n > 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    longest = max(pix.width, pix.height)
    factor = 1
    while longest // (factor * 2) >= max_px:
        factor *= 2
    if factor > 1:
        pix.shrink(factor.bit_length() - 1)
    data: bytes = pix.tobytes("jpg", jpg_quality=75)
    return data, pix.width, pix.height


class PdfDocument:
    """Pages from HTML stories; each add_story() starts on a new page."""

    def __init__(self, landscape: bool = False, margin_mm: float = MARGIN_MM) -> None:
        self.mediabox = pymupdf.paper_rect("a4-l" if landscape else "a4")
        m = margin_mm * MM
        # Room at the bottom for the footer.
        self.where = self.mediabox + (m, m, -m, -(m + 8))
        self._out = io.BytesIO()
        self._writer = pymupdf.DocumentWriter(self._out)

    def add_story(
        self, body: str, css: str = "", files: dict[str, bytes] | None = None
    ) -> None:
        archive = pymupdf.Archive(str(FONT_DIR))
        for name, data in (files or {}).items():
            archive.add((data, name))
        story = pymupdf.Story(html=body, user_css=BASE_CSS + css, archive=archive)
        more = 1
        while more:
            device = self._writer.begin_page(self.mediabox)
            more, _ = story.place(self.where)
            story.draw(device)
            self._writer.end_page()

    def finish(self, footer: str) -> bytes:
        """Close the document and add "<footer> · Seite n von m" to every page."""
        self._writer.close()
        doc = pymupdf.open("pdf", self._out.getvalue())
        total = doc.page_count
        font = str(FONT_DIR / "DMSans-Regular.ttf")
        for number, page in enumerate(doc, start=1):
            page.insert_font(fontname="dm", fontfile=font)
            rect = page.rect
            y = rect.height - 10 * MM
            text = f"{footer} · Seite {number} von {total}"
            page.insert_text(
                (15 * MM, y), text, fontname="dm", fontsize=7.5, color=(0.36, 0.42, 0.5)
            )
        data: bytes = doc.tobytes(garbage=3, deflate=True)
        doc.close()
        return data


def footer_text() -> str:
    return f"MV Hofkirchen · Stand {date.today().strftime('%d.%m.%Y')}"
