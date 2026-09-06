"""KI-Import sessions: upload, analysis stream, draft, delete."""

import io
import json

import cv2
import numpy as np
import pymupdf
import pytest

from mv_hofki.services.ai_import import archive as archive_mod
from mv_hofki.services.ai_import import session as session_service
from mv_hofki.services.ai_import.extraction import PageExtraction, PageResult
from mv_hofki.services.ai_import.llm_client import LlmError


@pytest.fixture(autouse=True)
def storage_roots(tmp_path, monkeypatch):
    """Keep uploads and archives of the tests out of data/."""
    monkeypatch.setattr(session_service, "IMPORTS_ROOT", tmp_path / "imports")
    monkeypatch.setattr(archive_mod, "ARCHIVE_ROOT", tmp_path / "archive")
    # image_path is stored relative to PROJECT_ROOT; point that at tmp too
    monkeypatch.setattr(session_service.settings, "PROJECT_ROOT", tmp_path)
    return tmp_path


def _png(width=1000, height=600) -> bytes:
    img = np.full((height, width, 3), 235, np.uint8)
    cv2.rectangle(img, (100, 100), (400, 500), (50, 50, 90), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _pdf(n=2) -> bytes:
    doc = pymupdf.open()
    for i in range(n):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"Seite {i + 1}", fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


def _extraction(nr="12", photos=True) -> dict:
    return {
        "page_kind": "mixed",
        "instruments": [
            {
                "inventory_nr": nr,
                "instrument_type": "Trompete Bb",
                "label": None,
                "manufacturer": "Yamaha",
                "model": None,
                "serial_nr": "123",
                "construction_year": 2009,
                "acquisition_date": None,
                "acquisition_cost": None,
                "distributor": None,
                "container": None,
                "particularities": None,
                "owner": None,
                "loan": None,
                "source_text": "12 Trompete",
                "confidence": "high",
                "bbox_2d": [0, 0, 1000, 100],
            }
        ],
        "photos": (
            [
                {
                    "caption": f"Nr. {nr}",
                    "inventory_nr": nr,
                    "bbox_2d": [100, 100, 400, 500],
                }
            ]
            if photos
            else []
        ),
        "remarks": None,
    }


def _fake_extract(extraction=None, fail_indices=()):
    async def extract(client, page):
        if page.index in fail_indices:
            raise LlmError("Modell antwortet nicht")
        ex = extraction or _extraction()
        return PageResult(
            source_name=page.source_name,
            page_index=page.index,
            width=page.width,
            height=page.height,
            extraction=PageExtraction.model_validate(ex),
            raw=ex,
            usage={"total_tokens": 42},
            duration_seconds=1.5,
        )

    return extract


def _sse_events(text: str) -> list[tuple[str, str]]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in lines:
            events.append((lines["event"], lines.get("data", "")))
    return events


async def _session_with_files(client, files):
    resp = await client.post("/api/v1/import/sessions", json={"title": "Inventar 1998"})
    assert resp.status_code == 201, resp.text
    sid = resp.json()["id"]
    resp = await client.post(f"/api/v1/import/sessions/{sid}/files", files=files)
    assert resp.status_code == 200, resp.text
    return sid, resp.json()


# --- create / upload --------------------------------------------------------


async def test_create_session_has_archive_dir(client, storage_roots):
    resp = await client.post("/api/v1/import/sessions", json={"title": "Test"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "uploaded"
    assert body["pages"] == []
    assert body["page_count"] == 0
    archives = list((storage_roots / "archive").iterdir())
    assert len(archives) == 1
    meta = json.loads((archives[0] / "meta.json").read_text())
    assert meta["import_session_id"] == body["id"]


async def test_create_session_without_body(client):
    resp = await client.post("/api/v1/import/sessions")
    assert resp.status_code == 201
    assert resp.json()["title"] is None


async def test_upload_pdf_and_image_creates_pages(client, storage_roots):
    sid, body = await _session_with_files(
        client,
        [
            ("files", ("liste.pdf", io.BytesIO(_pdf(2)), "application/pdf")),
            ("files", ("fotos.PNG", io.BytesIO(_png(3200, 2000)), "image/png")),
        ],
    )
    pages = body["pages"]
    assert [p["page_index"] for p in pages] == [0, 1, 2]
    assert [p["source_name"] for p in pages] == ["liste.pdf", "liste.pdf", "fotos.PNG"]
    assert [p["source_page"] for p in pages] == [0, 1, 0]
    assert pages[2]["width"] == 1600 and pages[2]["height"] == 1000
    assert all(p["status"] == "uploaded" for p in pages)
    assert pages[0]["image_url"] == f"/uploads/imports/{sid}/p001.png"
    assert body["page_count"] == 3

    # served files exist
    for n in (1, 2, 3):
        assert (storage_roots / "imports" / str(sid) / f"p{n:03d}.png").exists()

    # archive holds originals and pages
    archive = next((storage_roots / "archive").iterdir())
    assert (archive / "original" / "liste.pdf").exists()
    assert (archive / "original" / "fotos.PNG").exists()
    assert sorted(p.name for p in (archive / "pages").iterdir()) == [
        "p01.png",
        "p02.png",
        "p03.png",
    ]


async def test_upload_second_batch_continues_numbering(client):
    sid, _ = await _session_with_files(
        client, [("files", ("a.png", io.BytesIO(_png()), "image/png"))]
    )
    resp = await client.post(
        f"/api/v1/import/sessions/{sid}/files",
        files=[("files", ("b.png", io.BytesIO(_png()), "image/png"))],
    )
    assert resp.status_code == 200
    assert [p["page_index"] for p in resp.json()["pages"]] == [0, 1]
    assert resp.json()["pages"][1]["image_url"].endswith("/p002.png")


async def test_upload_unsupported_type_rejected(client, storage_roots):
    resp = await client.post("/api/v1/import/sessions")
    sid = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/import/sessions/{sid}/files",
        files=[
            ("files", ("ok.png", io.BytesIO(_png()), "image/png")),
            ("files", ("nope.docx", io.BytesIO(b"x"), "application/octet-stream")),
        ],
    )
    assert resp.status_code == 400
    assert "nope.docx" in resp.json()["detail"]
    # nothing of the batch was kept
    resp = await client.get(f"/api/v1/import/sessions/{sid}")
    assert resp.json()["pages"] == []


async def test_title_defaults_to_first_filename(client):
    resp = await client.post("/api/v1/import/sessions")
    sid = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/import/sessions/{sid}/files",
        files=[("files", ("Inventar Blech.png", io.BytesIO(_png()), "image/png"))],
    )
    assert resp.json()["title"] == "Inventar Blech"


# --- analysis -----------------------------------------------------------------


async def test_analyze_stream_success(client, monkeypatch, storage_roots):
    sid, _ = await _session_with_files(
        client, [("files", ("liste.pdf", io.BytesIO(_pdf(2)), "application/pdf"))]
    )

    # analyze() binds extract_page as a default argument; wrap the service
    # function the route calls and inject the fake extractor.
    orig_analyze = session_service.analyze

    async def analyze_with_fake(db, session, llm, **kw):
        kw["extract"] = _fake_extract()
        return await orig_analyze(db, session, llm, **kw)

    monkeypatch.setattr(session_service, "analyze", analyze_with_fake)

    resp = await client.get(f"/api/v1/import/sessions/{sid}/analyze-stream")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _sse_events(resp.text)
    kinds = [e for e, _ in events]
    assert kinds == ["page", "page", "done"]
    first = json.loads(events[0][1])
    assert first == {
        "page_index": 0,
        "status": "done",
        "page_kind": "mixed",
        "instruments": 1,
        "photos": 1,
        "duration_seconds": 1.5,
    }
    assert json.loads(events[2][1]) == {"status": "review"}

    resp = await client.get(f"/api/v1/import/sessions/{sid}")
    body = resp.json()
    assert body["status"] == "review"
    assert all(p["status"] == "done" for p in body["pages"])
    assert body["pages"][0]["extraction"]["instruments"][0]["manufacturer"] == "Yamaha"
    # the fake extractor returns boxes as given; 0..1000 -> px conversion is
    # covered in test_ai_import_extraction
    assert body["pages"][0]["extraction"]["photos"][0]["bbox_2d"] == [
        100,
        100,
        400,
        500,
    ]

    draft = body["draft"]
    assert draft["version"] == 1
    assert [r["key"] for r in draft["instruments"]] == ["p0-i0", "p1-i0"]
    assert draft["instruments"][0]["page_id"] == body["pages"][0]["id"]
    # photo auto-assigned to the row with the same inventory number on its page
    assert [p["row_key"] for p in draft["photos"]] == ["p0-i0", "p1-i0"]

    # archive got raw answers and the prompt
    archive = next((storage_roots / "archive").iterdir())
    assert (archive / "raw" / "p01.json").exists()
    assert (archive / "raw" / "p02.json").exists()
    assert (archive / "prompt.txt").exists()
    meta = json.loads((archive / "meta.json").read_text())
    assert meta["results"][0]["usage"] == {"total_tokens": 42}


async def test_analyze_partial_failure_keeps_review(client, monkeypatch, storage_roots):
    orig_analyze = session_service.analyze

    async def analyze_with_fake(db, session, llm, **kw):
        kw["extract"] = _fake_extract(fail_indices={1})
        return await orig_analyze(db, session, llm, **kw)

    monkeypatch.setattr(session_service, "analyze", analyze_with_fake)
    sid, _ = await _session_with_files(
        client, [("files", ("liste.pdf", io.BytesIO(_pdf(2)), "application/pdf"))]
    )
    resp = await client.get(f"/api/v1/import/sessions/{sid}/analyze-stream")
    events = _sse_events(resp.text)
    assert json.loads(events[1][1]) == {
        "page_index": 1,
        "status": "error",
        "error": "Modell antwortet nicht",
    }
    body = (await client.get(f"/api/v1/import/sessions/{sid}")).json()
    assert body["status"] == "review"
    assert [p["status"] for p in body["pages"]] == ["done", "error"]
    assert body["pages"][1]["error"] == "Modell antwortet nicht"
    assert len(body["draft"]["instruments"]) == 1
    archive = next((storage_roots / "archive").iterdir())
    assert (archive / "raw" / "p02.error.txt").read_text() == "Modell antwortet nicht"

    # second run only retries the failed page and keeps the draft
    async def analyze_ok(db, session, llm, **kw):
        kw["extract"] = _fake_extract()
        return await orig_analyze(db, session, llm, **kw)

    monkeypatch.setattr(session_service, "analyze", analyze_ok)
    resp = await client.get(f"/api/v1/import/sessions/{sid}/analyze-stream")
    events = _sse_events(resp.text)
    assert [e for e, _ in events] == ["page", "done"]
    assert json.loads(events[0][1])["page_index"] == 1
    body = (await client.get(f"/api/v1/import/sessions/{sid}")).json()
    assert [p["status"] for p in body["pages"]] == ["done", "done"]
    assert len(body["draft"]["instruments"]) == 1  # not rebuilt without force


async def test_analyze_total_failure_is_error(client, monkeypatch):
    orig_analyze = session_service.analyze

    async def analyze_fail(db, session, llm, **kw):
        kw["extract"] = _fake_extract(fail_indices={0})
        return await orig_analyze(db, session, llm, **kw)

    monkeypatch.setattr(session_service, "analyze", analyze_fail)
    sid, _ = await _session_with_files(
        client, [("files", ("a.png", io.BytesIO(_png()), "image/png"))]
    )
    resp = await client.get(f"/api/v1/import/sessions/{sid}/analyze-stream")
    events = _sse_events(resp.text)
    assert json.loads(events[-1][1]) == {"status": "error"}
    body = (await client.get(f"/api/v1/import/sessions/{sid}")).json()
    assert body["status"] == "error"
    assert body["error"] == "Keine Seite konnte analysiert werden"


async def test_analyze_without_pages_reports_error_event(client):
    resp = await client.post("/api/v1/import/sessions")
    sid = resp.json()["id"]
    resp = await client.get(f"/api/v1/import/sessions/{sid}/analyze-stream")
    events = _sse_events(resp.text)
    assert events == [("error", "Keine Seiten hochgeladen")]


# --- draft / crop / list / delete -----------------------------------------------


async def test_update_draft(client):
    sid, _ = await _session_with_files(
        client, [("files", ("a.png", io.BytesIO(_png()), "image/png"))]
    )
    draft = {
        "version": 1,
        "instruments": [{"key": "x", "manufacturer": "Melton"}],
        "photos": [],
    }
    resp = await client.put(
        f"/api/v1/import/sessions/{sid}/draft", json={"draft": draft}
    )
    assert resp.status_code == 200
    assert resp.json()["draft"] == draft
    resp = await client.get(f"/api/v1/import/sessions/{sid}")
    assert resp.json()["draft"] == draft


async def test_crop_endpoint_returns_png(client):
    sid, body = await _session_with_files(
        client, [("files", ("a.png", io.BytesIO(_png()), "image/png"))]
    )
    pid = body["pages"][0]["id"]
    resp = await client.get(
        f"/api/v1/import/sessions/{sid}/pages/{pid}/crop",
        params={"x1": 100, "y1": 100, "x2": 400, "y2": 500},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    img = cv2.imdecode(np.frombuffer(resp.content, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape[:2] == (400, 300)

    resp = await client.get(
        f"/api/v1/import/sessions/{sid}/pages/{pid}/crop",
        params={"x1": 10, "y1": 10, "x2": 10, "y2": 10},
    )
    assert resp.status_code == 400


async def test_list_sessions(client):
    await _session_with_files(
        client, [("files", ("a.png", io.BytesIO(_png()), "image/png"))]
    )
    await client.post("/api/v1/import/sessions", json={"title": "Leer"})
    resp = await client.get("/api/v1/import/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    by_title = {s["title"]: s for s in body["items"]}
    assert by_title["Inventar 1998"]["page_count"] == 1
    assert by_title["Leer"]["page_count"] == 0


async def test_delete_session_removes_pages_but_keeps_archive(client, storage_roots):
    sid, _ = await _session_with_files(
        client, [("files", ("a.png", io.BytesIO(_png()), "image/png"))]
    )
    assert (storage_roots / "imports" / str(sid)).exists()
    resp = await client.delete(f"/api/v1/import/sessions/{sid}")
    assert resp.status_code == 204
    assert not (storage_roots / "imports" / str(sid)).exists()
    assert len(list((storage_roots / "archive").iterdir())) == 1
    resp = await client.get(f"/api/v1/import/sessions/{sid}")
    assert resp.status_code == 404


async def test_unknown_session_404(client):
    assert (await client.get("/api/v1/import/sessions/999")).status_code == 404
    assert (await client.delete("/api/v1/import/sessions/999")).status_code == 404
