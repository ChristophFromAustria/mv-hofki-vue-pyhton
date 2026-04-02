# Crop Marks + PNG Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add crop marks to generated PDFs and a PNG preview with crop overlay in the LilyPond modal.

**Architecture:** Backend extends the render function to add crop marks via pypdf content streams and generate a PNG via a second lilypond call. Frontend modal gets tabs for preview (PNG + SVG overlay) and code view.

**Tech Stack:** pypdf (PDF manipulation), LilyPond (PNG rendering), Vue 3 (SVG overlay)

---

### Task 1: Add crop marks to PDF

**Files:**
- Modify: `src/backend/mv_hofki/services/lilypond_generator.py:150-164`
- Create: `tests/backend/test_crop_marks.py`

- [ ] **Step 1: Write the test**

Create `tests/backend/test_crop_marks.py`:

```python
"""Tests for crop mark generation."""

from mv_hofki.services.lilypond_generator import add_crop_marks_to_pdf


def test_crop_marks_content_stream():
    """add_crop_marks_to_pdf should produce valid PDF content stream with line operators."""
    # The function returns raw PDF content stream bytes for a single page
    content = add_crop_marks_to_pdf(
        page_width_mm=210.0,
        page_height_mm=148.0,
        crop_width_mm=165.0,
        crop_height_mm=123.0,
    )
    decoded = content.decode("latin-1")
    # Should contain line drawing operators
    assert " m " in decoded or " m\n" in decoded  # moveto
    assert " l " in decoded or " l\n" in decoded  # lineto
    assert "S" in decoded  # stroke
    assert "w" in decoded  # line width


def test_crop_marks_centered():
    """Crop marks should be centered on the page."""
    content = add_crop_marks_to_pdf(
        page_width_mm=210.0,
        page_height_mm=148.0,
        crop_width_mm=165.0,
        crop_height_mm=123.0,
    )
    decoded = content.decode("latin-1")
    # The left offset is (210-165)/2 = 22.5mm = 63.78pt
    # Should appear somewhere in the content stream
    assert "63" in decoded  # approximate left offset in points
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
python -m pytest tests/backend/test_crop_marks.py -v
```

- [ ] **Step 3: Implement `add_crop_marks_to_pdf`**

In `src/backend/mv_hofki/services/lilypond_generator.py`, add before `render_lilypond_to_pdf`:

```python
# Crop mark constants
_CROP_WIDTH_MM = 165.0
_CROP_HEIGHT_MM = 123.0
_A5_WIDTH_MM = 210.0
_A5_HEIGHT_MM = 148.0
_MARK_LENGTH_MM = 5.0
_MM_TO_PT = 72.0 / 25.4  # 1mm = 2.8346pt


def add_crop_marks_to_pdf(
    page_width_mm: float = _A5_WIDTH_MM,
    page_height_mm: float = _A5_HEIGHT_MM,
    crop_width_mm: float = _CROP_WIDTH_MM,
    crop_height_mm: float = _CROP_HEIGHT_MM,
    mark_length_mm: float = _MARK_LENGTH_MM,
) -> bytes:
    """Generate PDF content stream bytes for L-shaped crop marks.

    The crop rectangle is centered on the page. Returns raw PDF drawing
    operators that can be merged onto a page.
    """
    pt = _MM_TO_PT
    # Crop rectangle bounds in points
    left = (page_width_mm - crop_width_mm) / 2.0 * pt
    bottom = (page_height_mm - crop_height_mm) / 2.0 * pt
    right = left + crop_width_mm * pt
    top = bottom + crop_height_mm * pt
    ml = mark_length_mm * pt  # mark length in points

    lines = [
        "q",  # save graphics state
        "0.3 w",  # line width 0.3pt
        "0 0 0 RG",  # black stroke color
    ]

    # Four L-shaped corner marks
    corners = [
        # top-left: horizontal right + vertical down
        (left, top, left + ml, top, left, top, left, top - ml),
        # top-right: horizontal left + vertical down
        (right, top, right - ml, top, right, top, right, top - ml),
        # bottom-left: horizontal right + vertical up
        (left, bottom, left + ml, bottom, left, bottom, left, bottom + ml),
        # bottom-right: horizontal left + vertical up
        (right, bottom, right - ml, bottom, right, bottom, right, bottom + ml),
    ]

    for hx1, hy1, hx2, hy2, vx1, vy1, vx2, vy2 in corners:
        # Horizontal line
        lines.append(f"{hx1:.2f} {hy1:.2f} m {hx2:.2f} {hy2:.2f} l S")
        # Vertical line
        lines.append(f"{vx1:.2f} {vy1:.2f} m {vx2:.2f} {vy2:.2f} l S")

    lines.append("Q")  # restore graphics state
    return "\n".join(lines).encode("latin-1")
```

- [ ] **Step 4: Apply crop marks in `render_lilypond_to_pdf`**

In the same file, update `render_lilypond_to_pdf`. Replace the rotation block (lines 150-162):

```python
    # Rotate PDF 90° for landscape A5 viewing
    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore[import-not-found]

        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        for page in reader.pages:
            page.rotate(90)
            writer.add_page(page)
        with open(pdf_path, "wb") as f:
            writer.write(f)
    except ImportError:
        pass  # pypdf not available — skip rotation
```

With:

```python
    # Rotate PDF 90° and add crop marks
    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore[import-not-found]
        from pypdf.generic import DecodedStreamObject, NameObject

        reader = PdfReader(pdf_path)
        writer = PdfWriter()

        # Build crop mark overlay content stream
        crop_stream = add_crop_marks_to_pdf()

        for page in reader.pages:
            page.rotate(90)

            # Get rotated page dimensions in points
            box = page.mediabox
            pw_pt = float(box.width)
            ph_pt = float(box.height)
            pw_mm = pw_pt / _MM_TO_PT
            ph_mm = ph_pt / _MM_TO_PT

            # Generate crop marks for actual page size
            marks = add_crop_marks_to_pdf(
                page_width_mm=pw_mm, page_height_mm=ph_mm
            )

            # Create overlay page with crop marks
            overlay_writer = PdfWriter()
            overlay_page = overlay_writer.add_blank_page(
                width=pw_pt, height=ph_pt
            )
            # Inject the content stream
            stream_obj = DecodedStreamObject()
            stream_obj.set_data(marks)
            overlay_page[NameObject("/Contents")] = stream_obj

            # Merge overlay onto the rotated page
            page.merge_page(overlay_page)
            writer.add_page(page)

        with open(pdf_path, "wb") as f:
            writer.write(f)
    except ImportError:
        pass  # pypdf not available — skip rotation and crop marks
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/backend/test_crop_marks.py tests/backend/test_lilypond_generator.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/lilypond_generator.py tests/backend/test_crop_marks.py
git commit -m "feat: add crop marks to generated PDF for 165x123mm cut area"
```

---

### Task 2: Add PNG generation to renderer

**Files:**
- Modify: `src/backend/mv_hofki/services/lilypond_generator.py`
- Modify: `src/backend/mv_hofki/api/routes/scan_processing.py:454-461`

- [ ] **Step 1: Rename and extend the render function**

In `src/backend/mv_hofki/services/lilypond_generator.py`, rename `render_lilypond_to_pdf` to `render_lilypond` and add PNG generation. Replace the function signature and the initial lilypond call:

```python
def render_lilypond(ly_content: str, output_dir: Path) -> dict:
    """Write a .ly file, render to PDF (with crop marks) and PNG.

    Args:
        ly_content: Complete LilyPond source code.
        output_dir: Directory to write generated files into.

    Returns:
        Dict with keys: pdf_path (Path), png_paths (list[Path]).

    Raises:
        RuntimeError: If LilyPond is not installed or compilation fails.
    """
    lilypond_bin = _find_lilypond()
    if not lilypond_bin:
        raise RuntimeError(
            "LilyPond ist nicht installiert. Installieren mit: pip install lilypond"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    ly_path = output_dir / "generated.ly"
    ly_path.write_text(ly_content, encoding="utf-8")

    output_stem = output_dir / "generated"

    # Render PDF
    result = subprocess.run(
        [lilypond_bin, f"--output={output_stem}", str(ly_path)],
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        raise RuntimeError(f"LilyPond-Fehler: {stderr[:500]}")

    pdf_path = output_stem.with_suffix(".pdf")
    if not pdf_path.exists():
        raise RuntimeError("LilyPond hat keine PDF-Datei erzeugt")

    # Render PNG (separate call with --png)
    png_result = subprocess.run(
        [
            lilypond_bin,
            "--png",
            "-dresolution=150",
            f"--output={output_stem}",
            str(ly_path),
        ],
        capture_output=True,
        timeout=60,
    )
    # Collect PNG files (single page: generated.png, multi: generated-page1.png etc.)
    png_paths: list[Path] = []
    single_png = output_stem.with_suffix(".png")
    if single_png.exists():
        png_paths.append(single_png)
    else:
        for p in sorted(output_dir.glob("generated-page*.png")):
            png_paths.append(p)
```

Then keep the existing rotation + crop marks block (from Task 1), and change the return:

```python
    return {"pdf_path": pdf_path, "png_paths": png_paths}
```

- [ ] **Step 2: Update the API endpoint**

In `src/backend/mv_hofki/api/routes/scan_processing.py`, update the import and call. Change:

```python
    from mv_hofki.services.lilypond_generator import (
        generate_lilypond,
        render_lilypond_to_pdf,
    )
```

To:

```python
    from mv_hofki.services.lilypond_generator import (
        generate_lilypond,
        render_lilypond,
    )
```

Change the render call and return (around line 454-461):

```python
    pdf_path = await asyncio.to_thread(render_lilypond_to_pdf, ly_code, scan_dir)
    ly_path = scan_dir / "generated.ly"

    return {
        "lilypond_code": ly_code,
        "pdf_path": str(pdf_path.relative_to(settings.PROJECT_ROOT)),
        "ly_path": str(ly_path.relative_to(settings.PROJECT_ROOT)),
    }
```

To:

```python
    render_result = await asyncio.to_thread(render_lilypond, ly_code, scan_dir)
    ly_path = scan_dir / "generated.ly"

    return {
        "lilypond_code": ly_code,
        "pdf_path": str(render_result["pdf_path"].relative_to(settings.PROJECT_ROOT)),
        "ly_path": str(ly_path.relative_to(settings.PROJECT_ROOT)),
        "png_paths": [
            str(p.relative_to(settings.PROJECT_ROOT))
            for p in render_result["png_paths"]
        ],
    }
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/backend/test_lilypond_generator.py tests/backend/test_crop_marks.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/backend/mv_hofki/services/lilypond_generator.py src/backend/mv_hofki/api/routes/scan_processing.py
git commit -m "feat: add PNG rendering and extend API response with png_paths"
```

---

### Task 3: Rewrite LilypondModal with tabs and PNG preview

**Files:**
- Modify: `src/frontend/src/components/LilypondModal.vue`

- [ ] **Step 1: Rewrite the component**

Replace the entire file `src/frontend/src/components/LilypondModal.vue`:

```vue
<script setup>
import { ref, computed } from "vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  lilypondCode: { type: String, default: "" },
  pdfPath: { type: String, default: null },
  pngPaths: { type: Array, default: () => [] },
});

const emit = defineEmits(["close"]);

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");
const activeTab = ref("preview");

// PNG preview dimensions (loaded from image)
const pngWidth = ref(0);
const pngHeight = ref(0);

function assetUrl(path) {
  if (!path) return null;
  const relative = path.replace(/^data\/scans\//, "");
  return `${BASE}/scans/${relative}`;
}

const previewUrl = computed(() => {
  if (!props.pngPaths.length) return null;
  return assetUrl(props.pngPaths[0]);
});

function onPngLoad(e) {
  pngWidth.value = e.target.naturalWidth;
  pngHeight.value = e.target.naturalHeight;
}

// Crop overlay: 165/210 of width, 123/148 of height, centered
const cropRect = computed(() => {
  if (!pngWidth.value || !pngHeight.value) return null;
  const ratioX = 165.0 / 210.0;
  const ratioY = 123.0 / 148.0;
  const w = pngWidth.value * ratioX;
  const h = pngHeight.value * ratioY;
  const x = (pngWidth.value - w) / 2;
  const y = (pngHeight.value - h) / 2;
  return { x, y, w, h };
});
</script>

<template>
  <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
    <div class="modal modal-lilypond">
      <div class="modal-header">
        <h2>LilyPond</h2>
        <div class="tab-bar">
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'preview' }"
            @click="activeTab = 'preview'"
          >
            Vorschau
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'code' }"
            @click="activeTab = 'code'"
          >
            Code
          </button>
        </div>
        <button class="close-btn" title="Schließen" @click="emit('close')">✕</button>
      </div>

      <div class="modal-body">
        <!-- Preview tab -->
        <div v-if="activeTab === 'preview'" class="preview-container">
          <div v-if="previewUrl" class="preview-wrap">
            <img
              :src="previewUrl"
              alt="Vorschau"
              class="preview-img"
              @load="onPngLoad"
            />
            <svg
              v-if="cropRect"
              class="crop-overlay"
              :viewBox="`0 0 ${pngWidth} ${pngHeight}`"
              preserveAspectRatio="xMidYMid meet"
            >
              <rect
                :x="cropRect.x"
                :y="cropRect.y"
                :width="cropRect.w"
                :height="cropRect.h"
                fill="none"
                stroke="#06b6d4"
                stroke-width="2"
                stroke-dasharray="8 4"
                opacity="0.8"
              />
            </svg>
          </div>
          <div v-else class="preview-empty">
            Keine Vorschau verfügbar
          </div>
        </div>

        <!-- Code tab -->
        <div v-if="activeTab === 'code'">
          <pre class="ly-code">{{ lilypondCode }}</pre>
        </div>
      </div>

      <div class="modal-footer">
        <a v-if="pdfPath" :href="assetUrl(pdfPath)" target="_blank" class="btn btn-primary">
          PDF öffnen
        </a>
        <button class="btn" @click="emit('close')">Schließen</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: var(--color-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 550;
}

.modal-lilypond {
  background: var(--color-bg);
  border-radius: var(--radius);
  width: 100%;
  max-width: 800px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.5rem 0.75rem;
  border-bottom: 1px solid var(--color-border);
}

.modal-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.tab-bar {
  display: flex;
  gap: 0.25rem;
}

.tab-btn {
  padding: 0.3rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg-soft);
  color: var(--color-muted);
  font-size: 0.85rem;
  cursor: pointer;
}

.tab-btn.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

.close-btn {
  margin-left: auto;
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  color: var(--color-muted);
  padding: 0.25rem;
  line-height: 1;
}

.close-btn:hover {
  color: var(--color-text);
}

.modal-body {
  padding: 1rem 1.5rem;
  overflow-y: auto;
  flex: 1;
}

.preview-container {
  display: flex;
  justify-content: center;
}

.preview-wrap {
  position: relative;
  display: inline-block;
}

.preview-img {
  max-width: 100%;
  max-height: 65vh;
  display: block;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.crop-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.preview-empty {
  text-align: center;
  padding: 3rem;
  color: var(--color-muted);
}

.ly-code {
  background: #1a1a2e;
  color: #e0e0e0;
  padding: 1rem;
  border-radius: var(--radius);
  font-family: "Fira Code", "Cascadia Code", monospace;
  font-size: 0.8rem;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre;
  margin: 0;
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border-top: 1px solid var(--color-border);
}
</style>
```

- [ ] **Step 2: Verify build**

```bash
cd /workspaces/mv_hofki/src/frontend && npx vite build
```

- [ ] **Step 3: Commit**

```bash
cd /workspaces/mv_hofki
git add src/frontend/src/components/LilypondModal.vue
git commit -m "feat: rewrite LilypondModal with preview tab and crop overlay"
```

---

### Task 4: Wire new props in ScanEditorPage

**Files:**
- Modify: `src/frontend/src/pages/ScanEditorPage.vue`

- [ ] **Step 1: Add pngPaths ref and update handler**

In `src/frontend/src/pages/ScanEditorPage.vue`:

Add ref (near the other lilypond refs, around line 49):
```js
const lilypondPngPaths = ref([]);
```

Update the `generateLilypond` handler (around line 230-233). Change:
```js
    const result = await post(`/scanner/scans/${props.scanId}/generate-lilypond`);
    lilypondCode.value = result.lilypond_code;
    lilypondPdfPath.value = result.pdf_path;
    showLilypond.value = true;
```

To:
```js
    const result = await post(`/scanner/scans/${props.scanId}/generate-lilypond`);
    lilypondCode.value = result.lilypond_code;
    lilypondPdfPath.value = result.pdf_path;
    lilypondPngPaths.value = result.png_paths || [];
    showLilypond.value = true;
```

- [ ] **Step 2: Pass pngPaths to LilypondModal**

Find the `<LilypondModal` tag (around line 723-726). Add the new prop:

```html
    <LilypondModal
      :open="showLilypond"
      :lilypond-code="lilypondCode"
      :pdf-path="lilypondPdfPath"
      :png-paths="lilypondPngPaths"
      @close="showLilypond = false"
    />
```

- [ ] **Step 3: Verify build**

```bash
cd /workspaces/mv_hofki/src/frontend && npx vite build
```

- [ ] **Step 4: Commit**

```bash
cd /workspaces/mv_hofki
git add src/frontend/src/pages/ScanEditorPage.vue
git commit -m "feat: pass PNG paths to LilypondModal for preview"
```

---

### Task 5: Full verification

- [ ] **Step 1: Run all backend tests**

```bash
python -m pytest tests/backend/ -v --tb=short
```

- [ ] **Step 2: Run pre-commit**

```bash
pre-commit run --all-files
```

- [ ] **Step 3: Manual E2E test**

1. Open a scan with measures, click "LilyPond"
2. Modal opens on "Vorschau" tab — PNG preview with dashed cyan crop rectangle centered
3. Switch to "Code" tab — Lilypond code visible
4. Click "PDF öffnen" — PDF has L-shaped crop marks at the 4 corners of the 165×123mm area
5. Verify crop marks appear on all pages (if multi-page)
