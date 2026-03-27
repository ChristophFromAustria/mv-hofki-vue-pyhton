"""Render MusicXML and LilyPond notation to PNG images."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cairosvg  # type: ignore[import-not-found]
import cv2
import numpy as np
import verovio  # type: ignore[import-not-found]


def _find_lilypond() -> str | None:
    """Find the lilypond binary, checking the PyPI package first."""
    try:
        from lilypond import executable  # type: ignore[import-not-found]

        return str(executable())
    except (ImportError, Exception):
        pass
    return shutil.which("lilypond")


def _trim_whitespace(png_data: bytes, padding: int = 10) -> bytes:
    """Trim white borders from a PNG image, keeping a small padding."""
    arr = np.frombuffer(png_data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img is None:
        return png_data

    # Convert to grayscale for thresholding
    if len(img.shape) == 3 and img.shape[2] == 4:
        # RGBA — use alpha channel: transparent = white
        gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
        alpha = img[:, :, 3]
        # Treat transparent pixels as white
        gray[alpha < 128] = 255
    elif len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # Find non-white pixels
    _, binary = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    coords = cv2.findNonZero(binary)
    if coords is None:
        return png_data

    x, y, w, h = cv2.boundingRect(coords)

    # Add padding
    y1 = max(0, y - padding)
    y2 = min(img.shape[0], y + h + padding)
    x1 = max(0, x - padding)
    x2 = min(img.shape[1], x + w + padding)

    cropped = img[y1:y2, x1:x2]
    _, buf = cv2.imencode(".png", cropped)
    return bytes(buf)


@dataclass
class RenderResult:
    """Result of rendering notation to PNG."""

    png_data: bytes
    height_in_lines: float | None = None
    source_line_spacing: float | None = None


@dataclass
class _StaffAnalysis:
    height_in_lines: float | None = None
    line_spacing: float | None = None


def _analyze_staff(png_data: bytes) -> _StaffAnalysis:
    """Detect staff line spacing and symbol height in a rendered image."""
    arr = np.frombuffer(png_data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img is None:
        return _StaffAnalysis()

    # Handle RGBA: composite onto white background
    if len(img.shape) == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3].astype(float) / 255.0
        bgr = img[:, :, :3].astype(float)
        white = np.full_like(bgr, 255.0)
        composited = bgr * alpha[:, :, None] + white * (1 - alpha[:, :, None])
        gray = cv2.cvtColor(composited.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    elif len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # Horizontal projection to find staff lines
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    projection = np.sum(binary, axis=1).astype(float)

    if projection.max() == 0:
        return _StaffAnalysis()

    threshold = projection.max() * 0.3
    line_rows = np.where(projection > threshold)[0]
    if len(line_rows) < 5:
        return _StaffAnalysis()

    # Group consecutive rows into line centers
    groups: list[list[int]] = []
    current: list[int] = [int(line_rows[0])]
    for r in line_rows[1:]:
        if r - current[-1] <= 3:
            current.append(int(r))
        else:
            groups.append(current)
            current = [int(r)]
    groups.append(current)

    centers = [int(np.mean(g)) for g in groups]
    if len(centers) < 5:
        return _StaffAnalysis()

    # Use first 5 lines as staff
    staff_lines = centers[:5]
    spacings = np.diff(staff_lines)
    line_spacing = float(np.mean(spacings))
    if line_spacing < 2:
        return _StaffAnalysis()

    # Find symbol bounding box height (non-white area)
    height_in_lines = None
    coords = cv2.findNonZero(binary)
    if coords is not None:
        _, _, _, symbol_h = cv2.boundingRect(coords)
        height_in_lines = round(symbol_h / line_spacing, 1)

    return _StaffAnalysis(
        height_in_lines=height_in_lines,
        line_spacing=round(line_spacing, 1),
    )


def render_musicxml(fragment: str) -> RenderResult:
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
            "scale": 100,
            "pageWidth": 800,
            "adjustPageHeight": True,
            "header": "none",
            "footer": "none",
        }
    )
    tk.loadData(doc)
    svg = tk.renderToSVG(1)
    if not svg:
        raise RuntimeError("Verovio konnte kein SVG erzeugen")

    png_bytes: bytes = cairosvg.svg2png(bytestring=svg.encode("utf-8"), scale=2.0)
    analysis = _analyze_staff(png_bytes)
    trimmed = _trim_whitespace(png_bytes)
    return RenderResult(
        png_data=trimmed,
        height_in_lines=analysis.height_in_lines,
        source_line_spacing=analysis.line_spacing,
    )


def render_lilypond(token: str) -> RenderResult:
    """Render a LilyPond token to PNG bytes.

    The token (e.g. "c'4") is wrapped in a minimal LilyPond file.
    Requires the lilypond binary (installed via pip install lilypond).
    """
    if not token or not token.strip():
        raise ValueError("LilyPond-Token darf nicht leer sein")

    lilypond_bin = _find_lilypond()
    if not lilypond_bin:
        raise RuntimeError(
            "LilyPond ist nicht installiert. " "Installieren mit: pip install lilypond"
        )

    # Use a generous paper size so nothing gets clipped —
    # trimming will remove the excess whitespace afterwards
    ly_content = f"""\\version "2.24.0"
\\header {{ tagline = "" }}
\\paper {{
  indent = 0
  paper-width = 80\\mm
  paper-height = 60\\mm
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
                "-dresolution=600",
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
            candidates = list(Path(tmpdir).glob("output*.png"))
            if not candidates:
                stderr = result.stderr.decode(errors="replace")
                hint = ""
                if "zero-duration" in stderr:
                    hint = (
                        " Das Token hat keine Dauer — "
                        "füge z.B. eine unsichtbare Pause hinzu (s1)."
                    )
                raise RuntimeError(f"LilyPond hat keine PNG-Datei erzeugt.{hint}")
            png_path = candidates[0]

        raw = png_path.read_bytes()
        analysis = _analyze_staff(raw)
        trimmed = _trim_whitespace(raw)
        return RenderResult(
            png_data=trimmed,
            height_in_lines=analysis.height_in_lines,
            source_line_spacing=analysis.line_spacing,
        )
