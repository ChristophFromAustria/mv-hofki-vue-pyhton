"""Render MusicXML and LilyPond notation to PNG images."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import cairosvg  # type: ignore[import-not-found]
import verovio  # type: ignore[import-not-found]


def _find_lilypond() -> str | None:
    """Find the lilypond binary, checking the PyPI package first."""
    try:
        from lilypond import executable  # type: ignore[import-not-found]

        return str(executable())
    except (ImportError, Exception):
        pass
    return shutil.which("lilypond")


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
    return png_bytes


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
            candidates = list(Path(tmpdir).glob("output*.png"))
            if not candidates:
                raise RuntimeError("LilyPond hat keine PNG-Datei erzeugt")
            png_path = candidates[0]

        return png_path.read_bytes()
