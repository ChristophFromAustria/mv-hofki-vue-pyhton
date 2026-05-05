# Lilypond Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a Lilypond file from detected measure structure that preserves the original system/measure layout, render it to PDF, and display the code + PDF download in the frontend.

**Architecture:** New `lilypond_generator.py` service with pure-logic generator + renderer using the existing `_find_lilypond()` pattern. New API endpoint triggers generation. Frontend button opens a modal showing the code and PDF link.

**Tech Stack:** FastAPI, LilyPond (subprocess), Vue 3

---

### Task 1: Lilypond generator — pure code generation

**Files:**
- Create: `src/backend/mv_hofki/services/lilypond_generator.py`
- Create: `tests/backend/test_lilypond_generator.py`

- [ ] **Step 1: Write the tests**

Create `tests/backend/test_lilypond_generator.py`:

```python
"""Tests for Lilypond code generation from measure data."""

from mv_hofki.services.lilypond_generator import generate_lilypond


def _measures(layout):
    """Helper: build measure dicts from a layout like [(staff, count), ...]."""
    result = []
    global_num = 1
    for staff_index, count in layout:
        for local in range(1, count + 1):
            result.append({
                "staff_index": staff_index,
                "measure_number_in_staff": local,
                "global_measure_number": global_num,
                "x_start": 0,
                "x_end": 100,
            })
            global_num += 1
    return result


def test_basic_structure():
    """Generated code contains version, paper, header, score blocks."""
    measures = _measures([(0, 2)])
    code = generate_lilypond(measures, "Test Stück")
    assert '\\version "2.24.0"' in code
    assert "a5" in code
    assert 'title = "Test Stück"' in code
    assert "\\clef bass" in code
    assert "\\time 2/2" in code


def test_measures_per_system():
    """Each system's measures are separated by \\break."""
    measures = _measures([(0, 3), (1, 2)])
    code = generate_lilypond(measures, "Test")
    # System 0: 3 measures, then break, System 1: 2 measures
    assert "c1 | c1 | c1 |" in code
    assert "\\break" in code
    assert "c1 | c1 |" in code


def test_single_system():
    """Single system produces no \\break."""
    measures = _measures([(0, 4)])
    code = generate_lilypond(measures, "Test")
    assert "\\break" not in code
    assert "c1 | c1 | c1 | c1 |" in code


def test_empty_measures():
    """Empty measures list produces valid but empty score."""
    code = generate_lilypond([], "Empty")
    assert '\\version "2.24.0"' in code
    assert "\\clef bass" in code
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
python -m pytest tests/backend/test_lilypond_generator.py -v
```

- [ ] **Step 3: Implement the generator**

Create `src/backend/mv_hofki/services/lilypond_generator.py`:

```python
"""Generate and render LilyPond files from detected measure data."""

from __future__ import annotations

from collections import defaultdict


def generate_lilypond(measures: list[dict], title: str) -> str:
    """Generate LilyPond source code from detected measures.

    Args:
        measures: List of measure dicts with keys: staff_index,
                  measure_number_in_staff, global_measure_number.
        title: Title for the score header.

    Returns:
        Complete LilyPond source code as a string.
    """
    # Group measures by staff_index, preserving order
    systems: dict[int, list[dict]] = defaultdict(list)
    for m in measures:
        systems[m["staff_index"]].append(m)

    # Sort each system's measures by local number
    for staff_idx in systems:
        systems[staff_idx].sort(key=lambda m: m["measure_number_in_staff"])

    # Build note content: c1 per measure, \break between systems
    staff_indices = sorted(systems.keys())
    content_lines: list[str] = []
    for i, staff_idx in enumerate(staff_indices):
        measure_count = len(systems[staff_idx])
        notes = " | ".join(["c1"] * measure_count) + " |"
        content_lines.append(f"    {notes}")
        if i < len(staff_indices) - 1:
            content_lines.append("    \\break")

    content = "\n".join(content_lines)

    return f'''\\version "2.24.0"

#(set-default-paper-size "a5" 'landscape)

\\paper {{
  top-margin = 1
  bottom-margin = 4
  left-margin = 16
  right-margin = 16
  system-system-spacing.basic-distance = #6
  system-system-spacing.minimum-distance = #5
  system-system-spacing.padding = #0.6
  markup-system-spacing.basic-distance = #6
  top-system-spacing.basic-distance = #6
  last-bottom-spacing.basic-distance = #4
  indent = 0\\mm
  short-indent = 0\\mm
}}

\\header {{
  title = "{title}"
  tagline = ##f
}}

\\score {{
  \\new Staff {{
    \\clef bass
    \\time 2/2
{content}
  }}
  \\layout {{
    #(layout-set-staff-size 17)
    \\context {{
      \\Score
      \\override SpacingSpanner.common-shortest-duration = #(ly:make-moment 1/4)
      \\override SpacingSpanner.spacing-increment = #1.0
      \\omit BarNumber
    }}
  }}
}}
'''
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/backend/test_lilypond_generator.py -v
```

Expected: all 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/lilypond_generator.py tests/backend/test_lilypond_generator.py
git commit -m "feat: add Lilypond code generator from measure structure"
```

---

### Task 2: Lilypond renderer + API endpoint

**Files:**
- Modify: `src/backend/mv_hofki/services/lilypond_generator.py`
- Modify: `src/backend/mv_hofki/api/routes/scan_processing.py`

- [ ] **Step 1: Add render function**

Add to `src/backend/mv_hofki/services/lilypond_generator.py`:

```python
import shutil
import subprocess
from pathlib import Path


def _find_lilypond() -> str | None:
    """Find the lilypond binary, checking the PyPI package first."""
    try:
        from lilypond import executable  # type: ignore[import-not-found]

        return str(executable())
    except (ImportError, Exception):
        pass
    return shutil.which("lilypond")


def render_lilypond_to_pdf(ly_content: str, output_dir: Path) -> Path:
    """Write a .ly file and render it to PDF using LilyPond.

    Args:
        ly_content: Complete LilyPond source code.
        output_dir: Directory to write generated.ly and generated.pdf into.

    Returns:
        Path to the generated PDF file.

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

    return pdf_path
```

- [ ] **Step 2: Add API endpoint**

In `src/backend/mv_hofki/api/routes/scan_processing.py`, add after the measures endpoint:

```python
@router.post("/scans/{scan_id}/generate-lilypond")
async def generate_lilypond_endpoint(
    scan_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Generate LilyPond code and PDF from detected measures."""
    from sqlalchemy import select

    from mv_hofki.core.config import settings
    from mv_hofki.models.detected_measure import DetectedMeasure
    from mv_hofki.models.scan_part import ScanPart
    from mv_hofki.models.sheet_music_scan import SheetMusicScan
    from mv_hofki.services.lilypond_generator import (
        generate_lilypond,
        render_lilypond_to_pdf,
    )

    scan = await db.get(SheetMusicScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan nicht gefunden")

    result = await db.execute(
        select(DetectedMeasure)
        .where(DetectedMeasure.scan_id == scan_id)
        .order_by(DetectedMeasure.global_measure_number)
    )
    measures = [
        {
            "staff_index": m.staff_index,
            "measure_number_in_staff": m.measure_number_in_staff,
            "global_measure_number": m.global_measure_number,
            "x_start": m.x_start,
            "x_end": m.x_end,
        }
        for m in result.scalars().all()
    ]

    if not measures:
        raise HTTPException(
            status_code=400,
            detail="Keine Takte erkannt — bitte zuerst Analyse durchführen",
        )

    title = scan.original_filename.rsplit(".", 1)[0] if scan.original_filename else "Scan"
    ly_code = generate_lilypond(measures, title)

    part = await db.get(ScanPart, scan.part_id)
    scan_dir = settings.PROJECT_ROOT / "data" / "scans" / str(part.project_id) / str(part.id) / str(scan_id)

    import asyncio

    pdf_path = await asyncio.to_thread(render_lilypond_to_pdf, ly_code, scan_dir)
    ly_path = scan_dir / "generated.ly"

    return {
        "lilypond_code": ly_code,
        "pdf_path": str(pdf_path.relative_to(settings.PROJECT_ROOT)),
        "ly_path": str(ly_path.relative_to(settings.PROJECT_ROOT)),
    }
```

- [ ] **Step 3: Test manually**

```bash
server-restart
sleep 4
curl -s -X POST http://localhost:8000/api/v1/scanner/scans/5/generate-lilypond | python -m json.tool | head -5
```

Expected: JSON with `lilypond_code`, `pdf_path`, `ly_path`.

- [ ] **Step 4: Commit**

```bash
git add src/backend/mv_hofki/services/lilypond_generator.py src/backend/mv_hofki/api/routes/scan_processing.py
git commit -m "feat: add Lilypond renderer and generation API endpoint"
```

---

### Task 3: Frontend — LilypondModal component

**Files:**
- Create: `src/frontend/src/components/LilypondModal.vue`

- [ ] **Step 1: Create the modal component**

Create `src/frontend/src/components/LilypondModal.vue`:

```vue
<script setup>
defineProps({
  open: { type: Boolean, default: false },
  lilypondCode: { type: String, default: "" },
  pdfPath: { type: String, default: null },
});

const emit = defineEmits(["close"]);

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");

function pdfUrl(path) {
  if (!path) return null;
  const relative = path.replace(/^data\/scans\//, "");
  return `${BASE}/scans/${relative}`;
}
</script>

<template>
  <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
    <div class="modal modal-lilypond">
      <div class="modal-header">
        <h2>LilyPond-Code</h2>
        <button class="close-btn" title="Schließen" @click="emit('close')">✕</button>
      </div>

      <div class="modal-body">
        <pre class="ly-code">{{ lilypondCode }}</pre>
      </div>

      <div class="modal-footer">
        <a
          v-if="pdfPath"
          :href="pdfUrl(pdfPath)"
          target="_blank"
          class="btn btn-primary"
        >
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
  max-width: 700px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem 0.75rem;
  border-bottom: 1px solid var(--color-border);
}

.modal-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.close-btn {
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
git commit -m "feat: add LilypondModal component for code display and PDF download"
```

---

### Task 4: Frontend — Wire button and modal into ScanEditorPage

**Files:**
- Modify: `src/frontend/src/pages/ScanEditorPage.vue`

- [ ] **Step 1: Add import, refs, and handler**

Add import at the top (near other component imports):
```js
import LilypondModal from "../components/LilypondModal.vue";
```

Add refs (near other refs):
```js
const showLilypond = ref(false);
const lilypondCode = ref("");
const lilypondPdfPath = ref(null);
const lilypondLoading = ref(false);
```

Add handler function (near other action handlers):
```js
async function generateLilypond() {
  if (lilypondLoading.value) return;
  lilypondLoading.value = true;
  try {
    const result = await post(`/scanner/scans/${props.scanId}/generate-lilypond`);
    lilypondCode.value = result.lilypond_code;
    lilypondPdfPath.value = result.pdf_path;
    showLilypond.value = true;
  } catch (e) {
    statusMessage.value = `LilyPond-Fehler: ${e.message}`;
  } finally {
    lilypondLoading.value = false;
  }
}
```

- [ ] **Step 2: Add button in toolbar**

Find the config button (the one with `@click="showConfig = true"`, around line 559). Add BEFORE it:

```html
            <button
              class="btn btn-sm"
              :disabled="!measures.length || lilypondLoading"
              @click="generateLilypond"
            >
              {{ lilypondLoading ? "Generiert..." : "LilyPond" }}
            </button>
```

- [ ] **Step 3: Add modal to template**

Find the existing modals at the bottom of the template (ScannerConfigModal, AnalysisLogModal). Add after them:

```html
    <!-- LilyPond modal -->
    <LilypondModal
      :open="showLilypond"
      :lilypond-code="lilypondCode"
      :pdf-path="lilypondPdfPath"
      @close="showLilypond = false"
    />
```

- [ ] **Step 4: Verify build**

```bash
cd /workspaces/mv_hofki/src/frontend && npx vite build
```

- [ ] **Step 5: Commit**

```bash
cd /workspaces/mv_hofki
git add src/frontend/src/pages/ScanEditorPage.vue
git commit -m "feat: wire LilyPond generation button and modal into scan editor"
```

---

### Task 5: Full verification

- [ ] **Step 1: Run all backend tests**

```bash
python -m pytest tests/backend/ -v --tb=short
```

Expected: all pass (except pre-existing failures).

- [ ] **Step 2: Run pre-commit**

```bash
pre-commit run --all-files
```

- [ ] **Step 3: Manual E2E test**

1. Open a scan that has been analyzed (with measures detected)
2. Click "LilyPond" button in toolbar
3. Modal opens with LilyPond code showing:
   - `\version "2.24.0"`, `\clef bass`, `\time 2/2`
   - `c1` notes for each measure
   - `\break` between systems
4. Click "PDF öffnen" — PDF opens in new tab showing the rendered score
5. Verify the number of systems and measures per system matches the scan's measure detection
6. Button is disabled when no measures exist (un-analyzed scan)
