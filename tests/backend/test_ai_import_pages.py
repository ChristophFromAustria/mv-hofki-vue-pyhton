"""Rendering of uploaded files into bounded-width page images."""

from pathlib import Path

import cv2
import numpy as np
import pymupdf
import pytest

from mv_hofki.services.ai_import.pages import (
    PageImage,
    UnsupportedFileError,
    crop,
    render_file,
    render_image_bytes,
    render_pdf_bytes,
)


def _png(width: int, height: int) -> bytes:
    img = np.full((height, width, 3), 240, np.uint8)
    cv2.rectangle(img, (10, 10), (width - 10, height - 10), (0, 0, 0), 2)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _pdf(n_pages: int, width_pt: float = 595, height_pt: float = 842) -> bytes:
    doc = pymupdf.open()
    for i in range(n_pages):
        page = doc.new_page(width=width_pt, height=height_pt)
        page.insert_text((72, 72), f"Inventar Seite {i + 1}", fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


def test_wide_image_is_scaled_to_max_width():
    page = render_image_bytes(_png(3200, 2400), "scan.png", max_width=1600)
    assert (page.width, page.height) == (1600, 1200)
    assert page.index == 0
    assert page.source_name == "scan.png"
    decoded = cv2.imdecode(np.frombuffer(page.png, np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape[:2] == (1200, 1600)


def test_small_image_is_not_upscaled():
    page = render_image_bytes(_png(800, 600), "small.jpg", max_width=1600)
    assert (page.width, page.height) == (800, 600)


def test_pdf_pages_render_at_max_width():
    pages = render_pdf_bytes(_pdf(3), "doc.pdf", max_width=1200)
    assert [p.index for p in pages] == [0, 1, 2]
    for p in pages:
        assert p.width == 1200
        # A4 aspect ratio 842/595
        assert abs(p.height - round(1200 * 842 / 595)) <= 2


def test_pdf_page_selection():
    pages = render_pdf_bytes(_pdf(4), "doc.pdf", max_width=400, pages=[0, 2])
    assert [p.index for p in pages] == [0, 2]


def test_render_file_dispatches_on_suffix(tmp_path: Path):
    (tmp_path / "a.PNG").write_bytes(_png(100, 50))
    (tmp_path / "b.pdf").write_bytes(_pdf(2))
    (tmp_path / "c.docx").write_bytes(b"nope")

    assert len(render_file(tmp_path / "a.PNG")) == 1
    assert len(render_file(tmp_path / "b.pdf")) == 2
    with pytest.raises(UnsupportedFileError):
        render_file(tmp_path / "c.docx")


def test_unreadable_image_raises():
    with pytest.raises(UnsupportedFileError):
        render_image_bytes(b"not an image", "x.png")


def test_crop_is_clamped_to_page():
    page = render_image_bytes(_png(400, 300), "p.png")
    out = crop(page, [350, 250, 999, 999])
    img = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape[:2] == (50, 50)


def test_crop_rejects_empty_box():
    page = PageImage(0, _png(100, 100), 100, 100, "p.png")
    with pytest.raises(ValueError):
        crop(page, [10, 10, 10, 50])
