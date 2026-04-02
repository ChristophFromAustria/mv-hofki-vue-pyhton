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


def _measure_to_ly(m: dict) -> str:
    """Convert a single measure dict to a LilyPond note with optional barline."""
    bar_cmd = _BARLINE_MAP.get(m.get("end_barline") or "", "")
    return f"c1 {bar_cmd}" if bar_cmd else "c1"


def _build_staff_content(measures: list[dict]) -> list[str]:
    """Build LilyPond lines for one staff, handling volta/repeat structures."""
    lines: list[str] = []

    # Index volta groups
    volta_groups: dict[int, list[dict]] = {}
    for m in measures:
        gid = m.get("volta_group_id")
        if gid is not None:
            volta_groups.setdefault(gid, []).append(m)

    # Track which measures are in volta groups
    volta_measure_nums: set[int] = set()
    for group in volta_groups.values():
        for m in group:
            volta_measure_nums.add(m["global_measure_number"])

    # Find repeat body start positions for each volta group
    repeat_body_starts: dict[int, int] = {}
    for gid, group in volta_groups.items():
        first_volta_idx = min(
            i for i, m in enumerate(measures) if m.get("volta_group_id") == gid
        )
        start_idx = 0
        for j in range(first_volta_idx - 1, -1, -1):
            bl = measures[j].get("end_barline") or ""
            if "Wiederholung Anfang" in bl or "Wiederholung Beidseitig" in bl:
                start_idx = j + 1
                break
        repeat_body_starts[gid] = start_idx

    # Track repeat body measures per group
    repeat_body_nums: dict[int, set[int]] = {}
    for gid, start_idx in repeat_body_starts.items():
        first_volta_idx = min(
            i for i, m in enumerate(measures) if m.get("volta_group_id") == gid
        )
        repeat_body_nums[gid] = {
            measures[j]["global_measure_number"]
            for j in range(start_idx, first_volta_idx)
        }

    # All repeat body measure nums (across all groups) — used to know where
    # a plain run should stop before a repeat block begins.
    all_repeat_body_nums: set[int] = set()
    for body_set in repeat_body_nums.values():
        all_repeat_body_nums.update(body_set)

    emitted: set[int] = set()
    i = 0
    while i < len(measures):
        m = measures[i]
        gnum = m["global_measure_number"]

        if gnum in emitted:
            i += 1
            continue

        # Check if this measure starts a repeat body for a volta group
        started_group = None
        for gid, start_idx in repeat_body_starts.items():
            if i == start_idx:
                started_group = gid
                break

        if started_group is not None:
            gid = started_group
            body_nums = repeat_body_nums[gid]
            group = volta_groups[gid]
            volta1 = sorted(
                [g for g in group if g.get("volta_number") == 1],
                key=lambda x: x["measure_number_in_staff"],
            )
            volta2 = sorted(
                [g for g in group if g.get("volta_number") == 2],
                key=lambda x: x["measure_number_in_staff"],
            )

            # Emit repeat body
            body_notes = []
            for j in range(i, len(measures)):
                if measures[j]["global_measure_number"] in body_nums:
                    body_notes.append(_measure_to_ly(measures[j]))
                    emitted.add(measures[j]["global_measure_number"])
                else:
                    break

            lines.append("\\repeat volta 2 { " + " ".join(body_notes) + " }")

            # Emit alternatives
            lines.append("\\alternative {")
            if volta1:
                v1 = " ".join(_measure_to_ly(vm) for vm in volta1)
                lines.append(f"  \\volta 1 {{ {v1} }}")
                for vm in volta1:
                    emitted.add(vm["global_measure_number"])
            if volta2:
                v2 = " ".join(_measure_to_ly(vm) for vm in volta2)
                lines.append(f"  \\volta 2 {{ {v2} }}")
                for vm in volta2:
                    emitted.add(vm["global_measure_number"])
            lines.append("}")

            # Advance past all emitted measures
            while i < len(measures) and measures[i]["global_measure_number"] in emitted:
                i += 1
        else:
            # Collect a run of plain (non-repeat-body, non-volta) measures
            # and emit them on a single line.
            plain_notes: list[str] = []
            while i < len(measures):
                cur = measures[i]
                cnum = cur["global_measure_number"]
                if cnum in emitted:
                    i += 1
                    continue
                # Stop if this position starts a repeat body
                is_repeat_start = any(
                    i == start_idx for start_idx in repeat_body_starts.values()
                )
                if is_repeat_start:
                    break
                # Stop if this measure is in a volta group (shouldn't emit plain)
                if cnum in volta_measure_nums or cnum in all_repeat_body_nums:
                    i += 1
                    continue
                plain_notes.append(_measure_to_ly(cur))
                emitted.add(cnum)
                i += 1
            if plain_notes:
                lines.append(" ".join(plain_notes))

    return lines


def generate_lilypond(
    measures: list[dict],
    title: str,
    *,
    top_margin: int = 1,
    bottom_margin: int = 4,
    left_margin: int = 16,
    right_margin: int = 16,
    staff_size: int = 17,
    system_distance: int = 6,
    system_padding: float = 0.6,
) -> str:
    """Generate LilyPond source code from detected measures.

    Args:
        measures: List of measure dicts with keys: staff_index,
                  measure_number_in_staff, global_measure_number,
                  end_barline (optional display name of the barline type).
        title: Title for the score header.
        top_margin: Top margin in mm.
        bottom_margin: Bottom margin in mm.
        left_margin: Left margin in mm.
        right_margin: Right margin in mm.
        staff_size: LilyPond staff size (default 17).

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

    # Build note content with volta/repeat structures
    staff_indices = sorted(systems.keys())
    content_lines: list[str] = []

    for i, staff_idx in enumerate(staff_indices):
        staff_measures = systems[staff_idx]
        lines = _build_staff_content(staff_measures)
        content_lines.extend(f"    {line}" for line in lines)
        if i < len(staff_indices) - 1:
            content_lines.append("    \\break")

    content = "\n".join(content_lines)

    return f"""\\version "2.24.0"

#(set-default-paper-size "a5" 'landscape)

\\paper {{
  top-margin = {top_margin}
  bottom-margin = {bottom_margin}
  left-margin = {left_margin}
  right-margin = {right_margin}
  system-system-spacing.basic-distance = #{system_distance}
  system-system-spacing.minimum-distance = #{max(system_distance - 1, 1)}
  system-system-spacing.padding = #{system_padding}
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
    #(layout-set-staff-size {staff_size})
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
    # Collect and rotate PNG files 90°
    png_paths: list[Path] = []
    single_png = output_stem.with_suffix(".png")
    raw_pngs = (
        [single_png]
        if single_png.exists()
        else sorted(output_dir.glob("generated-page*.png"))
    )
    for png_file in raw_pngs:
        if png_file.exists():
            import cv2

            img = cv2.imread(str(png_file), cv2.IMREAD_UNCHANGED)
            if img is not None:
                rotated = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                cv2.imwrite(str(png_file), rotated)
            png_paths.append(png_file)

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
