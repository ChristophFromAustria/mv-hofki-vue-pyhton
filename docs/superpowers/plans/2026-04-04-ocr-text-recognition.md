# OCR Text Recognition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Tesseract OCR to the text masking pipeline stage so detected text regions get their content recognized (enabling "Trio" detection and better text coverage).

**Architecture:** Install tesseract-ocr system package in the devcontainer Dockerfile, add pytesseract Python dependency, extend TextRegionData with a `text` field, and modify `_detect_text_regions` to accept single-character clusters and run OCR on each detected region.

**Tech Stack:** Tesseract OCR, pytesseract, OpenCV, Python 3.12

---

### Task 1: Install Tesseract in devcontainer

**Files:**
- Modify: `.devcontainer/Dockerfile:11-14`
- Modify: `pyproject.toml:6-21`

- [ ] **Step 1: Add tesseract-ocr to Dockerfile**

In `.devcontainer/Dockerfile`, change the system dependencies block from:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*
```

to:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    libcairo2-dev \
    tesseract-ocr \
    tesseract-ocr-deu \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 2: Add pytesseract to pyproject.toml**

In `pyproject.toml`, add `"pytesseract>=0.3,<1",` to the dependencies list, after the `numpy` line:

```toml
dependencies = [
    "fastapi>=0.115,<1",
    "uvicorn[standard]>=0.34,<1",
    "pydantic-settings>=2.0,<3",
    "sqlalchemy[asyncio]>=2.0,<3",
    "aiosqlite>=0.20,<1",
    "alembic>=1.13,<2",
    "python-multipart>=0.0.9,<1",
    "httpx>=0.27,<1",
    "opencv-python-headless>=4.9,<5",
    "numpy>=1.26,<3",
    "pytesseract>=0.3,<1",
    "verovio>=4.0,<7",
    "cairosvg>=2.7,<3",
    "lilypond>=2.24,<3",
    "pypdf>=4.0,<6",
]
```

- [ ] **Step 3: Install pytesseract in current environment**

Run: `pip install "pytesseract>=0.3,<1"`

- [ ] **Step 4: Install tesseract binary in current environment**

Run: `sudo apt-get update && sudo apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-deu`

- [ ] **Step 5: Verify tesseract works**

Run: `python -c "import pytesseract; print(pytesseract.get_tesseract_version())"`
Expected: Version number printed (e.g. `5.3.3`)

- [ ] **Step 6: Commit**

```bash
git add .devcontainer/Dockerfile pyproject.toml
git commit -m "feat: add tesseract-ocr and pytesseract for text recognition"
```

---

### Task 2: Add `text` field to TextRegionData

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/base.py:64-72`
- Test: `tests/backend/test_pipeline_stages.py`

- [ ] **Step 1: Write failing test**

Add to `tests/backend/test_pipeline_stages.py`:

```python
def test_text_region_data_has_text_field():
    from mv_hofki.services.scanner.stages.base import TextRegionData

    # Default is None
    region = TextRegionData(staff_index=0, x=10, y=20, width=50, height=15)
    assert region.text is None

    # Can be set explicitly
    region_with_text = TextRegionData(
        staff_index=0, x=10, y=20, width=50, height=15, text="Trio"
    )
    assert region_with_text.text == "Trio"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_pipeline_stages.py::test_text_region_data_has_text_field -v`
Expected: FAIL with `TypeError: TextRegionData.__init__() got an unexpected keyword argument 'text'`

- [ ] **Step 3: Add text field to TextRegionData**

In `src/backend/mv_hofki/services/scanner/stages/base.py`, change the `TextRegionData` class:

```python
@dataclass
class TextRegionData:
    """Data for a detected text region."""

    staff_index: int
    x: int
    y: int
    width: int
    height: int
    text: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/backend/test_pipeline_stages.py::test_text_region_data_has_text_field -v`
Expected: PASS

- [ ] **Step 5: Run all existing tests to check for regressions**

Run: `python -m pytest tests/backend/test_pipeline_stages.py tests/backend/test_text_masking.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/base.py tests/backend/test_pipeline_stages.py
git commit -m "feat: add text field to TextRegionData for OCR results"
```

---

### Task 3: Lower minimum cluster size and raise max char size

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/text_masking.py:95-96,150-156`
- Test: `tests/backend/test_text_masking.py`

- [ ] **Step 1: Write failing test for single large character detection**

Add to `tests/backend/test_text_masking.py`:

```python
def test_text_masking_detects_single_large_symbol():
    """A single large symbol like copyright (©) should be detected."""
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    img = np.full((300, 800), 255, dtype=np.uint8)

    # Staff lines
    for y in [50, 60, 70, 80, 90]:
        img[y : y + 2, 20:780] = 0

    # Single large symbol below staff (>= 0.5 * line_spacing in both dimensions)
    # At line_spacing=10, this is a 7x7 symbol
    cv2.rectangle(img, (400, 120), (407, 127), 0, -1)

    staff = StaffData(
        staff_index=0,
        y_top=20,
        y_bottom=200,
        line_positions=[50, 60, 70, 80, 90],
        line_spacing=10.0,
    )
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    assert len(result.text_regions) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_text_masking.py::test_text_masking_detects_single_large_symbol -v`
Expected: FAIL with `assert 0 >= 1`

- [ ] **Step 3: Update thresholds and cluster logic**

In `src/backend/mv_hofki/services/scanner/stages/text_masking.py`, change line 95:

```python
    max_char_size = line_spacing * 3.0
```

Then replace the cluster-to-region conversion block (starting at line 150 `# Convert clusters with >= 3 characters`) with:

```python
    # Convert qualifying clusters to TextRegionData.
    # Clusters with >= 3 characters are always accepted.
    # Single/double-component clusters are accepted only if each component
    # is large enough (>= 0.5 * line_spacing) to avoid catching note dots.
    min_solo_size = line_spacing * 0.5
    padding = int(line_spacing * 0.3)
    results: list[TextRegionData] = []

    for cluster in clusters:
        if len(cluster) < 3:
            # Accept small clusters only if components are large enough
            all_large = all(
                (b[2] - b[0]) >= min_solo_size and (b[3] - b[1]) >= min_solo_size
                for b in cluster
            )
            if not all_large:
                continue
        cx1 = max(0, min(b[0] for b in cluster) - padding)
        cy1 = max(0, min(b[1] for b in cluster) - padding)
        cx2 = min(rw, max(b[2] for b in cluster) + padding)
        cy2 = min(rh, max(b[3] for b in cluster) + padding)

        results.append(
            TextRegionData(
                staff_index=staff_index,
                x=cx1,
                y=region_top + cy1,
                width=cx2 - cx1,
                height=cy2 - cy1,
            )
        )
```

- [ ] **Step 4: Run new test to verify it passes**

Run: `python -m pytest tests/backend/test_text_masking.py::test_text_masking_detects_single_large_symbol -v`
Expected: PASS

- [ ] **Step 5: Run all text masking tests**

Run: `python -m pytest tests/backend/test_text_masking.py -v`
Expected: all 6 tests PASS (including the existing no-false-positives test)

- [ ] **Step 6: Run linter**

Run: `pre-commit run --files src/backend/mv_hofki/services/scanner/stages/text_masking.py`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/text_masking.py tests/backend/test_text_masking.py
git commit -m "feat: detect single large symbols and raise max char size to 3x"
```

---

### Task 4: Add OCR to TextMaskingStage

**Files:**
- Modify: `src/backend/mv_hofki/services/scanner/stages/text_masking.py:1-58`
- Test: `tests/backend/test_text_masking.py`

- [ ] **Step 1: Write failing test for OCR text field**

Add to `tests/backend/test_text_masking.py`:

```python
def test_text_masking_runs_ocr_on_regions(monkeypatch):
    """OCR should populate region.text with recognized content."""
    from mv_hofki.services.scanner.stages import text_masking
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    # Mock pytesseract to avoid requiring tesseract binary in tests
    monkeypatch.setattr(
        text_masking, "_ocr_region", lambda _binary, _region: "cresc."
    )

    img, staff = _make_staff_with_text_below()
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    assert len(result.text_regions) >= 1
    assert result.text_regions[0].text == "cresc."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_text_masking.py::test_text_masking_runs_ocr_on_regions -v`
Expected: FAIL (either `_ocr_region` not found or `text` is still None)

- [ ] **Step 3: Add OCR integration to TextMaskingStage**

In `src/backend/mv_hofki/services/scanner/stages/text_masking.py`, add the import at the top (after `import numpy as np`):

```python
import pytesseract
```

Add the `_ocr_region` function after the class (before `_detect_text_regions`):

```python
def _ocr_region(binary: np.ndarray, region: TextRegionData) -> str | None:
    """Run Tesseract OCR on a text region and return recognized text."""
    y1 = region.y
    y2 = region.y + region.height
    x1 = region.x
    x2 = region.x + region.width

    snippet = binary[y1:y2, x1:x2]
    # Invert: tesseract expects black text on white background
    snippet = cv2.bitwise_not(snippet)

    text = pytesseract.image_to_string(
        snippet, lang="deu", config="--psm 7"
    ).strip()
    return text if text else None
```

Then in the `process()` method, insert OCR between region detection and masking. Change the block starting at `# Assign each region to the nearest staff` to:

```python
        # Assign each region to the nearest staff
        staff_centers = [
            (s.staff_index, float(np.mean(s.line_positions))) for s in staves
        ]
        for region in raw_regions:
            region_center_y = region.y + region.height / 2
            closest_idx = min(
                staff_centers, key=lambda sc: abs(sc[1] - region_center_y)
            )[0]
            region.staff_index = closest_idx
            region.text = _ocr_region(binary, region)
            ctx.text_regions.append(region)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/backend/test_text_masking.py::test_text_masking_runs_ocr_on_regions -v`
Expected: PASS

- [ ] **Step 5: Write test for Trio detection**

Add to `tests/backend/test_text_masking.py`:

```python
def test_text_masking_detects_trio(monkeypatch):
    """Trio text should be recognized and stored in region.text."""
    from mv_hofki.services.scanner.stages import text_masking
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    monkeypatch.setattr(
        text_masking, "_ocr_region", lambda _binary, _region: "Trio"
    )

    img, staff = _make_staff_with_text_below()
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    trio_regions = [r for r in result.text_regions if r.text == "Trio"]
    assert len(trio_regions) >= 1
    assert trio_regions[0].staff_index == 0
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/backend/test_text_masking.py::test_text_masking_detects_trio -v`
Expected: PASS

- [ ] **Step 7: Run all text masking tests**

Run: `python -m pytest tests/backend/test_text_masking.py -v`
Expected: all 8 tests PASS

- [ ] **Step 8: Run linter**

Run: `pre-commit run --files src/backend/mv_hofki/services/scanner/stages/text_masking.py`
Expected: all pass

- [ ] **Step 9: Commit**

```bash
git add src/backend/mv_hofki/services/scanner/stages/text_masking.py tests/backend/test_text_masking.py
git commit -m "feat: add Tesseract OCR to TextMaskingStage for text recognition"
```

---

### Task 5: Manual verification with "47er Regimentsmarsch - Tuba 1"

**Files:** none (manual test via UI)

- [ ] **Step 1: Restart the backend server**

Run: `tmux send-keys -t server C-c && sleep 1 && tmux send-keys -t server 'PYTHONPATH=src/backend python -m uvicorn mv_hofki.api.app:app --host 0.0.0.0 --port 8000 --reload' Enter`

- [ ] **Step 2: Run a scan on "47er Regimentsmarsch - Tuba 1" via the UI**

Open the application, navigate to the scan, and trigger a re-scan.

- [ ] **Step 3: Verify results**

Check in the UI:
1. `processed.png` shows white-masked areas where text was
2. Copyright symbol at bottom is masked
3. "bearb. Hans Kliment jr." text is masked
4. Hairpin detection reports exactly 4 Crescendo/Decrescendo
5. Text regions include one with `text == "Trio"` (check server logs for `Text-Maskierung:` line)
