"""Turn an uploaded PDF or image into page PNGs of bounded width.

The model reports bounding boxes in pixel coordinates of the image it was
given, so every downstream consumer must work with these rendered pages
(not the original file). ``PageImage.width``/``height`` are therefore
part of the contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pymupdf

DEFAULT_MAX_WIDTH = 1600
PDF_SUFFIXES = {".pdf"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


class UnsupportedFileError(ValueError):
    pass


@dataclass
class PageImage:
    index: int  # 0-based within the source file
    png: bytes
    width: int
    height: int
    source_name: str

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height


def _encode_png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("PNG-Kodierung fehlgeschlagen")
    return buf.tobytes()


def _fit_width(img: np.ndarray, max_width: int) -> np.ndarray:
    h, w = img.shape[:2]
    if w <= max_width:
        return img
    scale = max_width / w
    return cv2.resize(
        img, (max_width, max(1, round(h * scale))), interpolation=cv2.INTER_AREA
    )


def render_image_bytes(
    data: bytes, source_name: str, max_width: int = DEFAULT_MAX_WIDTH
) -> PageImage:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise UnsupportedFileError(f"Bild konnte nicht gelesen werden: {source_name}")
    img = _fit_width(img, max_width)
    h, w = img.shape[:2]
    return PageImage(0, _encode_png(img), w, h, source_name)


def render_pdf_bytes(
    data: bytes,
    source_name: str,
    max_width: int = DEFAULT_MAX_WIDTH,
    pages: list[int] | None = None,
) -> list[PageImage]:
    """Rasterise each PDF page so that its width is ``max_width`` pixels.

    Scanned PDFs are usually a single full-page image; rendering the page
    (instead of extracting the embedded image) also handles PDFs that mix
    printed text with images.
    """
    out: list[PageImage] = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            if pages is not None and i not in pages:
                continue
            page_width_pt = page.rect.width or 1
            zoom = max_width / page_width_pt
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            img: np.ndarray = np.reshape(
                np.frombuffer(pix.samples, dtype=np.uint8),
                (pix.height, pix.width, pix.n),
            )
            if pix.n == 3:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            elif pix.n == 1:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            img = _fit_width(img, max_width)
            h, w = img.shape[:2]
            out.append(PageImage(i, _encode_png(img), w, h, source_name))
    return out


def render_file(
    path: Path, max_width: int = DEFAULT_MAX_WIDTH, pages: list[int] | None = None
) -> list[PageImage]:
    suffix = path.suffix.lower()
    data = path.read_bytes()
    if suffix in PDF_SUFFIXES:
        return render_pdf_bytes(data, path.name, max_width, pages)
    if suffix in IMAGE_SUFFIXES:
        return [render_image_bytes(data, path.name, max_width)]
    raise UnsupportedFileError(f"Nicht unterstütztes Dateiformat: {path.name}")


def crop(page: PageImage, bbox: list[int] | tuple[int, int, int, int]) -> bytes:
    """Cut ``[x1, y1, x2, y2]`` (clamped to the page) out of a page, as PNG."""
    img = cv2.imdecode(np.frombuffer(page.png, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Seitenbild konnte nicht dekodiert werden")
    x1, y1, x2, y2 = bbox
    x1, x2 = sorted((max(0, x1), min(page.width, x2)))
    y1, y2 = sorted((max(0, y1), min(page.height, y2)))
    if x2 - x1 < 2 or y2 - y1 < 2:
        raise ValueError(f"Leerer Ausschnitt: {bbox}")
    return _encode_png(img[y1:y2, x1:x2])
