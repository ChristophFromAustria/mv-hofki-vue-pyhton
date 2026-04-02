"""Generate and render LilyPond files from detected measure data."""

from __future__ import annotations

import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

_BARLINE_MAP: dict[str, str] = {
    "Doppelter Taktstrich": '\\bar "||"',
    "Schlusstaktstrich": '\\bar "|."',
    "Wiederholung Anfang": '\\bar ".|:"',
    "Wiederholung Ende": '\\bar ":|."',
    "Wiederholung Beidseitig": '\\bar ":|.|:"',
}


def generate_lilypond(measures: list[dict], title: str) -> str:
    """Generate LilyPond source code from detected measures.

    Args:
        measures: List of measure dicts with keys: staff_index,
                  measure_number_in_staff, global_measure_number,
                  end_barline (optional display name of the barline type).
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

    # Build note content: c1 per measure with barline types, \break between systems
    staff_indices = sorted(systems.keys())
    content_lines: list[str] = []
    for i, staff_idx in enumerate(staff_indices):
        parts: list[str] = []
        for m in systems[staff_idx]:
            bar_cmd = _BARLINE_MAP.get(m.get("end_barline") or "", "")
            if bar_cmd:
                parts.append(f"c1 {bar_cmd}")
            else:
                parts.append("c1")
        notes = " ".join(parts)
        content_lines.append(f"    {notes}")
        if i < len(staff_indices) - 1:
            content_lines.append("    \\break")

    content = "\n".join(content_lines)

    return f"""\\version "2.24.0"

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
"""


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
    left = (page_width_mm - crop_width_mm) / 2.0 * pt
    bottom = (page_height_mm - crop_height_mm) / 2.0 * pt
    right = left + crop_width_mm * pt
    top = bottom + crop_height_mm * pt
    ml = mark_length_mm * pt

    lines = [
        "q",
        "0.3 w",
        "0 0 0 RG",
    ]

    corners = [
        (left, top, left + ml, top, left, top, left, top - ml),
        (right, top, right - ml, top, right, top, right, top - ml),
        (left, bottom, left + ml, bottom, left, bottom, left, bottom + ml),
        (right, bottom, right - ml, bottom, right, bottom, right, bottom + ml),
    ]

    for hx1, hy1, hx2, hy2, vx1, vy1, vx2, vy2 in corners:
        lines.append(f"{hx1:.2f} {hy1:.2f} m {hx2:.2f} {hy2:.2f} l S")
        lines.append(f"{vx1:.2f} {vy1:.2f} m {vx2:.2f} {vy2:.2f} l S")

    lines.append("Q")
    return "\n".join(lines).encode("latin-1")


def _find_lilypond() -> str | None:
    """Find the lilypond binary, checking the PyPI package first."""
    try:
        from lilypond import executable  # type: ignore[import-not-found]

        return str(executable())
    except (ImportError, Exception):
        pass
    return shutil.which("lilypond")


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

    # Render PNG (separate call)
    subprocess.run(
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
    # Collect PNG files
    png_paths: list[Path] = []
    single_png = output_stem.with_suffix(".png")
    if single_png.exists():
        png_paths.append(single_png)
    else:
        for p in sorted(output_dir.glob("generated-page*.png")):
            png_paths.append(p)

    # Rotate PDF 90° and add crop marks
    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore[import-not-found]
        from pypdf.generic import (  # type: ignore[import-not-found]
            DecodedStreamObject,
            NameObject,
        )

        reader = PdfReader(pdf_path)
        writer = PdfWriter()

        for page in reader.pages:
            page.rotate(90)

            box = page.mediabox
            pw_pt = float(box.width)
            ph_pt = float(box.height)
            pw_mm = pw_pt / _MM_TO_PT
            ph_mm = ph_pt / _MM_TO_PT

            marks = add_crop_marks_to_pdf(page_width_mm=pw_mm, page_height_mm=ph_mm)

            overlay_writer = PdfWriter()
            overlay_page = overlay_writer.add_blank_page(width=pw_pt, height=ph_pt)
            stream_obj = DecodedStreamObject()
            stream_obj.set_data(marks)
            overlay_page[NameObject("/Contents")] = stream_obj

            page.merge_page(overlay_page)
            writer.add_page(page)

        with open(pdf_path, "wb") as f:
            writer.write(f)
    except ImportError:
        pass

    return {"pdf_path": pdf_path, "png_paths": png_paths}
