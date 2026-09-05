"""Tests for rendering user-edited LilyPond code."""

from pathlib import Path

import pytest

from mv_hofki.models.scan_part import ScanPart
from mv_hofki.models.scan_project import ScanProject
from mv_hofki.models.sheet_music_scan import SheetMusicScan

MINIMAL_LY = '\\version "2.24.0"\n\\score { \\new Staff { c4 d4 e4 f4 | } }\n'


@pytest.fixture
async def scan_id(db_session):
    project = ScanProject(name="Test")
    db_session.add(project)
    await db_session.flush()
    part = ScanPart(project_id=project.id, part_name="Tuba", part_order=1)
    db_session.add(part)
    await db_session.flush()
    scan = SheetMusicScan(
        part_id=part.id,
        page_number=1,
        original_filename="x.png",
        image_path="data/scans/x.png",
        status="uploaded",
    )
    db_session.add(scan)
    await db_session.commit()
    return scan.id


@pytest.mark.asyncio
async def test_render_lilypond_writes_files(client, scan_id, monkeypatch, tmp_path):
    from mv_hofki.core.config import settings
    from mv_hofki.services import lilypond_generator

    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path)
    captured = {}

    def fake_render(code: str, output_dir: Path) -> dict:
        output_dir.mkdir(parents=True, exist_ok=True)
        captured["code"] = code
        captured["dir"] = output_dir
        (output_dir / "generated.ly").write_text(code)
        pdf = output_dir / "generated.pdf"
        pdf.write_bytes(b"%PDF")
        png = output_dir / "generated.png"
        png.write_bytes(b"png")
        return {"pdf_path": pdf, "png_paths": [png]}

    monkeypatch.setattr(lilypond_generator, "render_lilypond", fake_render)

    resp = await client.post(
        f"/api/v1/scanner/scans/{scan_id}/render-lilypond",
        json={"lilypond_code": MINIMAL_LY},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert captured["code"] == MINIMAL_LY
    assert body["lilypond_code"] == MINIMAL_LY
    assert body["pdf_path"].endswith("generated.pdf")
    assert body["png_paths"] == [f"data/scans/1/1/{scan_id}/generated.png"]
    assert body["warnings"] == []


@pytest.mark.asyncio
async def test_render_lilypond_rejects_code_without_score(client, scan_id):
    resp = await client.post(
        f"/api/v1/scanner/scans/{scan_id}/render-lilypond",
        json={"lilypond_code": "c4 d4"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_render_lilypond_reports_lilypond_errors(
    client, scan_id, monkeypatch, tmp_path
):
    from mv_hofki.core.config import settings
    from mv_hofki.services import lilypond_generator

    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path)

    def failing(code: str, output_dir: Path) -> dict:
        raise RuntimeError("LilyPond-Fehler: syntax error")

    monkeypatch.setattr(lilypond_generator, "render_lilypond", failing)
    resp = await client.post(
        f"/api/v1/scanner/scans/{scan_id}/render-lilypond",
        json={"lilypond_code": MINIMAL_LY},
    )
    assert resp.status_code == 422
    assert "syntax error" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_render_lilypond_unknown_scan(client):
    resp = await client.post(
        "/api/v1/scanner/scans/9999/render-lilypond",
        json={"lilypond_code": MINIMAL_LY},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_edited_version_is_stored_and_reused(
    client, scan_id, monkeypatch, tmp_path
):
    from mv_hofki.core.config import settings
    from mv_hofki.services import lilypond_generator

    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path)
    calls: list[str] = []

    def fake_render(code: str, output_dir: Path) -> dict:
        output_dir.mkdir(parents=True, exist_ok=True)
        calls.append(code)
        pdf = output_dir / "generated.pdf"
        pdf.write_bytes(b"%PDF")
        return {"pdf_path": pdf, "png_paths": []}

    monkeypatch.setattr(lilypond_generator, "render_lilypond", fake_render)

    resp = await client.post(
        f"/api/v1/scanner/scans/{scan_id}/render-lilypond",
        json={"lilypond_code": MINIMAL_LY},
    )
    assert resp.status_code == 200
    assert resp.json()["source"] == "edited"
    assert resp.json()["edited_at"]

    # generate-lilypond now returns the edited version instead of analysing
    resp = await client.post(f"/api/v1/scanner/scans/{scan_id}/generate-lilypond")
    assert resp.status_code == 200, resp.text
    assert resp.json()["source"] == "edited"
    assert resp.json()["lilypond_code"] == MINIMAL_LY
    assert calls == [MINIMAL_LY, MINIMAL_LY]

    # reset discards the edit; without measures the analysis path answers 400
    resp = await client.post(
        f"/api/v1/scanner/scans/{scan_id}/generate-lilypond?reset=true"
    )
    assert resp.status_code == 400
    resp = await client.post(f"/api/v1/scanner/scans/{scan_id}/generate-lilypond")
    assert resp.status_code == 400
