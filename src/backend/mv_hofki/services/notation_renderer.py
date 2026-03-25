"""Render MusicXML and LilyPond notation to PNG images."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
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

    png_bytes: bytes = cairosvg.svg2png(bytestring=svg.encode("utf-8"))
    return _trim_whitespace(png_bytes)


def render_lilypond(token: str) -> bytes:
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
            candidates = list(Path(tmpdir).glob("output*.png"))
            if not candidates:
                raise RuntimeError("LilyPond hat keine PNG-Datei erzeugt")
            png_path = candidates[0]

        return _trim_whitespace(png_path.read_bytes())
