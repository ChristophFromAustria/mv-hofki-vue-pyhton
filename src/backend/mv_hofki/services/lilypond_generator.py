"""Generate and render LilyPond files from detected measure data."""

from __future__ import annotations

import shutil
import subprocess
from collections import defaultdict
from pathlib import Path


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
