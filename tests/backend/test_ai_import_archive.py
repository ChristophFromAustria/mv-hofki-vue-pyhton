"""Upload archive: everything the KI-Import sees is kept on disk."""

import json
from datetime import datetime
from pathlib import Path

from mv_hofki.services.ai_import.archive import create_archive
from mv_hofki.services.ai_import.pages import PageImage


def test_archive_layout(tmp_path: Path):
    now = datetime(2026, 9, 6, 14, 30, 0)
    archive = create_archive("Inventar 1998 (Kopie).pdf", root=tmp_path, now=now)
    assert archive.root.name == "20260906-143000_inventar-1998-kopie"

    archive.add_original("Inventar 1998 (Kopie).pdf", b"%PDF-1.4 fake")
    archive.add_pages(
        [
            PageImage(0, b"png0", 1600, 2200, "Inventar 1998 (Kopie).pdf"),
            PageImage(1, b"png1", 1600, 2200, "Inventar 1998 (Kopie).pdf"),
        ]
    )
    archive.add_prompt("system", "user")
    archive.add_result(0, {"page_kind": "other"}, {"total_tokens": 12}, 3.5)
    archive.add_error(1, "HTTP 500")
    archive.set(model="qwen-vl")

    assert (
        archive.root / "original" / "Inventar 1998 (Kopie).pdf"
    ).read_bytes() == b"%PDF-1.4 fake"
    assert (archive.root / "pages" / "p01.png").read_bytes() == b"png0"
    assert (archive.root / "pages" / "p02.png").read_bytes() == b"png1"
    assert (archive.root / "raw" / "p01.json").exists()
    assert (archive.root / "raw" / "p02.error.txt").read_text() == "HTTP 500"
    assert "### system" in (archive.root / "prompt.txt").read_text()

    meta = json.loads((archive.root / "meta.json").read_text())
    assert meta["source_name"] == "Inventar 1998 (Kopie).pdf"
    assert meta["model"] == "qwen-vl"
    assert meta["originals"][0]["bytes"] == 13
    assert len(meta["originals"][0]["sha256"]) == 64
    assert [p["file"] for p in meta["pages"]] == ["p01.png", "p02.png"]
    assert meta["results"][0]["ok"] is True
    assert meta["results"][0]["usage"] == {"total_tokens": 12}
    assert meta["results"][1] == {"index": 1, "ok": False, "error": "HTTP 500"}
    assert meta["prompt_sha256"]


def test_archive_names_do_not_collide(tmp_path: Path):
    now = datetime(2026, 9, 6, 14, 30, 0)
    a = create_archive("scan.jpg", root=tmp_path, now=now)
    b = create_archive("scan.jpg", root=tmp_path, now=now)
    assert a.root != b.root
    assert b.root.name.endswith("-2")
