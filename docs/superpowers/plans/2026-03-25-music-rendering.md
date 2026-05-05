# Music Notation Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backend rendering of MusicXML (via Verovio) and LilyPond notation into PNG variant images for symbol templates.

**Architecture:** A new `notation_renderer.py` service with two pure functions (`render_musicxml`, `render_lilypond`) that return PNG bytes. Two new POST routes call these and save results as variants using the existing pattern. Frontend adds render buttons in the template edit modal.

**Tech Stack:** verovio (PyPI), lilypond (PyPI), cairosvg (PyPI), FastAPI, Vue 3

**Spec:** `docs/superpowers/specs/2026-03-25-music-rendering-design.md`

---

### Task 1: Install dependencies

**Files:**
- Modify: `pyproject.toml` — add verovio, cairosvg, lilypond to dependencies

- [ ] **Step 1: Add dependencies to pyproject.toml**

In `pyproject.toml`, add to the `dependencies` list:

```toml
    "verovio>=4.0,<7",
    "cairosvg>=2.7,<3",
```

Note: `lilypond` PyPI package requires system libraries that may not be available in all environments. Instead of adding it as a hard dependency, install it separately and handle its absence gracefully.

- [ ] **Step 2: Install packages**

```bash
pip install verovio cairosvg lilypond
```

- [ ] **Step 3: Verify imports work**

```bash
PYTHONPATH=src/backend python -c "import verovio; print('verovio', verovio.getVersion())"
PYTHONPATH=src/backend python -c "import cairosvg; print('cairosvg OK')"
python -c "import shutil; print(shutil.which('lilypond'))"
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add verovio and cairosvg dependencies for notation rendering"
```

---

### Task 2: Create notation renderer service

**Files:**
- Create: `src/backend/mv_hofki/services/notation_renderer.py`
- Test: `tests/backend/test_notation_renderer.py`

- [ ] **Step 1: Write tests**

Create `tests/backend/test_notation_renderer.py`:

```python
"""Tests for notation rendering service."""

import pytest

from mv_hofki.services.notation_renderer import render_musicxml, render_lilypond


@pytest.mark.asyncio
async def test_render_musicxml_returns_png():
    """MusicXML fragment renders to PNG bytes."""
    fragment = '<note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>quarter</type></note>'
    result = render_musicxml(fragment)
    assert isinstance(result, bytes)
    assert len(result) > 100
    # PNG magic bytes
    assert result[:4] == b"\x89PNG"


@pytest.mark.asyncio
async def test_render_musicxml_empty_raises():
    """Empty fragment raises ValueError."""
    with pytest.raises(ValueError, match="leer"):
        render_musicxml("")


@pytest.mark.asyncio
async def test_render_lilypond_returns_png():
    """LilyPond token renders to PNG bytes."""
    lilypond_bin = __import__("shutil").which("lilypond")
    if not lilypond_bin:
        pytest.skip("lilypond not installed")
    token = "c'4"
    result = render_lilypond(token)
    assert isinstance(result, bytes)
    assert len(result) > 100
    assert result[:4] == b"\x89PNG"


@pytest.mark.asyncio
async def test_render_lilypond_empty_raises():
    """Empty token raises ValueError."""
    with pytest.raises(ValueError, match="leer"):
        render_lilypond("")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backend/test_notation_renderer.py -v`
Expected: FAIL (ImportError — module not found)

- [ ] **Step 3: Implement the renderer**

Create `src/backend/mv_hofki/services/notation_renderer.py`:

```python
"""Render MusicXML and LilyPond notation to PNG images."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import cairosvg
import verovio


def render_musicxml(fragment: str) -> bytes:
    """Render a MusicXML fragment to PNG bytes.

    The fragment should be a <note>, <rest>, or similar element.
    It is wrapped in a minimal <score-partwise> document.
    """
    if not fragment or not fragment.strip():
        raise ValueError("MusicXML-Fragment darf nicht leer sein")

    doc = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC
  "-//Recordare//DTD MusicXML 4.0 Partwise//EN"
  "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name/></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      {fragment}
    </measure>
  </part>
</score-partwise>"""

    tk = verovio.toolkit()
    tk.setOptions(
        {
            "scale": 40,
            "adjustPageHeight": True,
            "adjustPageWidth": True,
            "border": 10,
            "header": "none",
            "footer": "none",
        }
    )
    tk.loadData(doc)
    svg = tk.renderToSVG(1)
    if not svg:
        raise RuntimeError("Verovio konnte kein SVG erzeugen")

    png_bytes = cairosvg.svg2png(bytestring=svg.encode("utf-8"))
    return png_bytes


def render_lilypond(token: str) -> bytes:
    """Render a LilyPond token to PNG bytes.

    The token (e.g. "c'4") is wrapped in a minimal LilyPond file.
    Requires the `lilypond` binary to be installed.
    """
    if not token or not token.strip():
        raise ValueError("LilyPond-Token darf nicht leer sein")

    lilypond_bin = shutil.which("lilypond")
    if not lilypond_bin:
        raise RuntimeError(
            "LilyPond ist nicht installiert. "
            "Installieren mit: pip install lilypond"
        )

    ly_content = f"""\\version "2.24.0"
\\header {{ tagline = "" }}
\\paper {{
  indent = 0
  paper-width = 30\\mm
  paper-height = 20\\mm
}}
{{ {token} }}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        ly_path = Path(tmpdir) / "input.ly"
        ly_path.write_text(ly_content)

        result = subprocess.run(
            [
                lilypond_bin,
                "--png",
                "-dresolution=300",
                f"--output={tmpdir}/output",
                str(ly_path),
            ],
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace")
            raise RuntimeError(f"LilyPond-Fehler: {stderr[:500]}")

        # LilyPond outputs output.png (or output-page1.png for multi-page)
        png_path = Path(tmpdir) / "output.png"
        if not png_path.exists():
            # Try the page-numbered variant
            candidates = list(Path(tmpdir).glob("output*.png"))
            if not candidates:
                raise RuntimeError("LilyPond hat keine PNG-Datei erzeugt")
            png_path = candidates[0]

        return png_path.read_bytes()
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/backend/test_notation_renderer.py -v`
Expected: All PASS (LilyPond test may skip if binary not found)

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/notation_renderer.py \
  tests/backend/test_notation_renderer.py
git commit -m "feat(scanner): add MusicXML and LilyPond notation renderer service"
```

---

### Task 3: Add render API endpoints

**Files:**
- Modify: `src/backend/mv_hofki/api/routes/symbol_library.py` — add two POST routes
- Modify: `src/backend/mv_hofki/services/symbol_library.py` — add `save_rendered_variant` helper
- Test: `tests/backend/test_symbol_library.py` — add render endpoint tests

- [ ] **Step 1: Add `save_rendered_variant` helper to symbol_library service**

In `src/backend/mv_hofki/services/symbol_library.py`, add after `delete_variant`:

```python
async def save_rendered_variant(
    session: AsyncSession,
    template_id: int,
    png_data: bytes,
    source: str,
) -> SymbolTemplate:
    """Save rendered PNG bytes as a new variant for the given template."""
    import uuid

    template = await get_template_by_id(session, template_id)
    variant_dir = settings.PROJECT_ROOT / "data" / "symbol_library" / str(template_id)
    variant_dir.mkdir(parents=True, exist_ok=True)

    variant_filename = f"{uuid.uuid4().hex}.png"
    variant_path = variant_dir / variant_filename
    variant_path.write_bytes(png_data)

    variant = SymbolVariant(
        template_id=template_id,
        image_path=str(variant_path.relative_to(settings.PROJECT_ROOT)),
        source=source,
    )
    session.add(variant)
    await session.commit()
    await session.refresh(template)
    return template
```

- [ ] **Step 2: Add render routes**

In `src/backend/mv_hofki/api/routes/symbol_library.py`, add at the bottom:

```python
@router.post(
    "/templates/{template_id}/render-musicxml",
    response_model=SymbolTemplateRead,
)
async def render_musicxml(template_id: int, db: AsyncSession = Depends(get_db)):
    """Render the template's MusicXML to a PNG variant."""
    from mv_hofki.services.notation_renderer import render_musicxml as do_render

    template = await lib_service.get_template_by_id(db, template_id)
    if not template.musicxml_element:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400, detail="Kein MusicXML-Element vorhanden"
        )
    png_data = do_render(template.musicxml_element)
    return await lib_service.save_rendered_variant(
        db, template_id, png_data, source="rendered_musicxml"
    )


@router.post(
    "/templates/{template_id}/render-lilypond",
    response_model=SymbolTemplateRead,
)
async def render_lilypond(template_id: int, db: AsyncSession = Depends(get_db)):
    """Render the template's LilyPond token to a PNG variant."""
    from mv_hofki.services.notation_renderer import render_lilypond as do_render

    template = await lib_service.get_template_by_id(db, template_id)
    if not template.lilypond_token:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400, detail="Kein LilyPond-Token vorhanden"
        )
    png_data = do_render(template.lilypond_token)
    return await lib_service.save_rendered_variant(
        db, template_id, png_data, source="rendered_lilypond"
    )
```

Note: the `from fastapi import HTTPException` inside the function body is to avoid shadowing the module-level import that may already exist. Check the file — if `HTTPException` is already imported at the top, use it directly and remove the local import.

- [ ] **Step 3: Write tests**

In `tests/backend/test_symbol_library.py`, add:

```python
@pytest.mark.asyncio
async def test_render_musicxml_creates_variant(client):
    """Render MusicXML should create a variant."""
    resp = await client.post("/api/v1/scanner/library/templates", json={
        "category": "note",
        "name": "test_render_xml",
        "display_name": "Test Render XML",
        "musicxml_element": '<note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>quarter</type></note>',
    })
    assert resp.status_code == 201
    tid = resp.json()["id"]

    resp = await client.post(f"/api/v1/scanner/library/templates/{tid}/render-musicxml")
    assert resp.status_code == 200
    assert resp.json()["variant_count"] >= 1

    # Check variant was created
    resp = await client.get(f"/api/v1/scanner/library/templates/{tid}/variants")
    variants = resp.json()
    assert any(v["source"] == "rendered_musicxml" for v in variants)


@pytest.mark.asyncio
async def test_render_musicxml_no_element_returns_400(client):
    """Render MusicXML without element should return 400."""
    resp = await client.post("/api/v1/scanner/library/templates", json={
        "category": "note",
        "name": "test_render_empty",
        "display_name": "Test Render Empty",
    })
    tid = resp.json()["id"]

    resp = await client.post(f"/api/v1/scanner/library/templates/{tid}/render-musicxml")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_render_lilypond_no_token_returns_400(client):
    """Render LilyPond without token should return 400."""
    resp = await client.post("/api/v1/scanner/library/templates", json={
        "category": "note",
        "name": "test_render_ly_empty",
        "display_name": "Test Render LY Empty",
    })
    tid = resp.json()["id"]

    resp = await client.post(f"/api/v1/scanner/library/templates/{tid}/render-lilypond")
    assert resp.status_code == 400
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/backend/test_symbol_library.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/symbol_library.py \
  src/backend/mv_hofki/api/routes/symbol_library.py \
  tests/backend/test_symbol_library.py
git commit -m "feat(scanner): add render-musicxml and render-lilypond API endpoints"
```

---

### Task 4: Frontend — Add render buttons in edit modal

**Files:**
- Modify: `src/frontend/src/pages/SymbolLibraryPage.vue` — add render buttons and handlers

- [ ] **Step 1: Add rendering state refs**

In `src/frontend/src/pages/SymbolLibraryPage.vue`, add after the existing refs (after `const deleteVariantTarget = ref(null);`):

```javascript
const rendering = ref(null); // "musicxml" | "lilypond" | null
```

- [ ] **Step 2: Add render functions**

Add after the `variantImageUrl` function:

```javascript
async function renderMusicxml() {
  if (!editingTemplate.value) return;
  rendering.value = "musicxml";
  try {
    await post(`/scanner/library/templates/${editingTemplate.value.id}/render-musicxml`);
    variants.value = await get(`/scanner/library/templates/${editingTemplate.value.id}/variants`);
    await fetchTemplates();
  } catch (e) {
    alert(`MusicXML-Rendering fehlgeschlagen: ${e.message}`);
  } finally {
    rendering.value = null;
  }
}

async function renderLilypond() {
  if (!editingTemplate.value) return;
  rendering.value = "lilypond";
  try {
    await post(`/scanner/library/templates/${editingTemplate.value.id}/render-lilypond`);
    variants.value = await get(`/scanner/library/templates/${editingTemplate.value.id}/variants`);
    await fetchTemplates();
  } catch (e) {
    alert(`LilyPond-Rendering fehlgeschlagen: ${e.message}`);
  } finally {
    rendering.value = null;
  }
}
```

- [ ] **Step 3: Add render buttons to the edit modal template**

In the edit modal, after the LilyPond Token `</label>` and before the `<!-- Variants -->` section, add:

```html
        <!-- Render actions -->
        <div class="render-actions">
          <button
            class="btn btn-sm btn-secondary"
            :disabled="!editForm.musicxml_element.trim() || rendering !== null"
            @click="renderMusicxml"
          >
            {{ rendering === "musicxml" ? "Rendere..." : "MusicXML rendern" }}
          </button>
          <button
            class="btn btn-sm btn-secondary"
            :disabled="!editForm.lilypond_token.trim() || rendering !== null"
            @click="renderLilypond"
          >
            {{ rendering === "lilypond" ? "Rendere..." : "LilyPond rendern" }}
          </button>
        </div>
```

- [ ] **Step 4: Add CSS**

Add to the `<style scoped>` section:

```css
.render-actions {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
```

- [ ] **Step 5: Build frontend**

Run: `cd src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/pages/SymbolLibraryPage.vue
git commit -m "feat(scanner): add MusicXML and LilyPond render buttons to template editor"
```

---

### Task 5: Verify — Full test suite and lint

- [ ] **Step 1: Run all backend tests**

Run: `python -m pytest tests/backend/ -v`
Expected: All scanner/library tests pass

- [ ] **Step 2: Run pre-commit linters**

Run: `pre-commit run --all-files`
Expected: All pass

- [ ] **Step 3: Build frontend**

Run: `cd src/frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 4: Final commit if linters changed anything**

```bash
git add -u && git commit -m "style: fix lint issues"
```
