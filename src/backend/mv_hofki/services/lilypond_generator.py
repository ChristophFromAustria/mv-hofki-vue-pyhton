"""Generate and render LilyPond files from detected scanner data."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from mv_hofki.services.lilypond_score import (
    MeasureModel,
    ScoreModel,
    build_score,
    duration_tokens,
    key_signature_name,
    time_length,
)

_BARLINE_MAP: dict[str, str] = {
    "Doppelter Taktstrich": '\\bar "||"',
    "Schlusstaktstrich": '\\bar "|."',
    "Wiederholung Anfang": '\\bar ".|:"',
    "Wiederholung Ende": '\\bar ":|."',
    "Wiederholung Beidseitig": '\\bar ":|.|:"',
}
_REPEAT_START = ("Wiederholung Anfang", "Wiederholung Beidseitig")
_REPEAT_END = ("Wiederholung Ende", "Wiederholung Beidseitig")

_COLOR_GROBS = ("NoteHead", "Stem", "Rest", "Flag", "Beam", "Dots", "Accidental")
# Sentinel: forces the next measure to emit an explicit measureLength.
_FORCE_LENGTH = Fraction(-1)

# Indent a single system and print a label ("Trio") in front of it.
# Inlined from samplefiles/reference_transcriptions/frisch_auf_tuba1.ly
_PSEUDO_INDENT_SCM = (
    Path(__file__).with_name("lilypond_pseudo_indent.ily").read_text(encoding="utf-8")
)


# ── Emission helpers ─────────────────────────────────────────────────────


def _moment(length: Fraction) -> str:
    return f"#(ly:make-moment {length.numerator}/{length.denominator})"


def _event_to_ly(e) -> str:  # noqa: ANN001 — Event from lilypond_score
    if e.kind == "rest":
        body = f"r{e.duration_token}"
    elif len(e.pitches) == 1:
        body = f"{e.pitches[0]}{e.duration_token}"
    else:
        body = f"<{' '.join(e.pitches)}>{e.duration_token}"
    parts = [body]
    parts.extend(e.articulations)
    parts.extend(e.dynamics)
    if e.hairpin_start:
        parts.append(e.hairpin_start)
    if e.hairpin_end and not e.dynamics:
        parts.append("\\!")
    for text in e.texts:
        safe = text.replace("\\", "\\\\").replace('"', '\\"')
        parts.append(f'_\\markup {{ \\italic "{safe}" }}')
    return "".join(parts)


@dataclass
class _EmitState:
    effective_len: Fraction
    time_len: Fraction
    last_staff: int | None = None
    mark_errors: bool = True
    last_music: str | None = None  # music of the last normal measure (for copies)
    trio_indent: float = 8.0
    used_indent: bool = False  # a \pseudoIndent was emitted → include preamble
    instrument_unset: bool = False  # instrumentName currently ##f
    unset_instrument_pending: bool = False


@dataclass
class _Item:
    """One emitted measure, kept separately so percent repeats can wrap it."""

    prefix: list[str]
    music: str
    suffix: str
    wrappable: bool
    percent: int = 0
    break_before: bool = False
    suppress_break: bool = False  # \pseudoIndent already breaks the line

    def render(self) -> str:
        out: list[str] = []
        if self.break_before:
            out.append("\\break")
        out.extend(self.prefix)
        if self.percent:
            out.append(f"\\repeat percent {self.percent + 1} {{ {self.music} }}")
        else:
            out.append(self.music)
        if self.suffix:
            out.append(self.suffix)
        return " ".join(part for part in out if part)


def _section_prefix(
    m: MeasureModel, state: _EmitState, line_start: bool
) -> tuple[list[str], bool]:
    """Prefix for a section label ("Trio") plus instrument-name bookkeeping."""
    prefix: list[str] = []
    suppress_break = False
    if m.section_label and line_start:
        label = _escape(m.section_label)
        if state.instrument_unset:
            prefix.append('\\set Staff.instrumentName = ""')
            state.instrument_unset = False
        prefix.append(
            f'\\pseudoIndent \\markuplist {{ \\fontsize #5 \\bold "{label}" }} '
            f"{state.trio_indent:g}"
        )
        state.used_indent = True
        state.unset_instrument_pending = True
        suppress_break = True
    elif m.section_label:
        prefix.append(
            f'\\mark \\markup {{ \\bold \\large "{_escape(m.section_label)}" }}'
        )
    elif line_start and state.unset_instrument_pending:
        # Reference layout: drop the instrument name again on the next system
        prefix.append("\\set Staff.instrumentName = ##f")
        state.instrument_unset = True
        state.unset_instrument_pending = False
    return prefix, suppress_break


def _measure_item(
    m: MeasureModel,
    state: _EmitState,
    *,
    end_barline: str | None,
    line_start: bool = False,
) -> _Item:
    prefix, suppress_break = _section_prefix(m, state, line_start)
    prefix.extend(m.marks)
    if m.clef:
        prefix.append(f"\\clef {m.clef}")
    if m.key_flats is not None:
        prefix.append(f"\\key {key_signature_name(m.key_flats)} \\major")
    if m.time:
        prefix.append(f"\\time {m.time}")
        state.time_len = time_length(m.time)
        state.effective_len = state.time_len

    wrappable = True
    if m.mmrest_measures:
        needed = state.time_len
        total = state.time_len * m.mmrest_measures
        mult = (
            str(total.numerator)
            if total.denominator == 1
            else f"{total.numerator}/{total.denominator}"
        )
        music = f"R1*{mult}"
        if m.orphan_dynamics:
            music = "<>" + "".join(m.orphan_dynamics) + " " + music
        if m.events and state.mark_errors:
            music = (
                "\\markErr "
                + music
                + " "
                + " ".join(_event_to_ly(e) for e in m.events)
                + " \\unmarkErr"
            )
        wrappable = False
    elif m.percent_repeat:
        # Resolved by the container (wrap previous item or copy it).
        needed = state.effective_len
        music = ""
    elif not m.events:
        needed = m.expected_length
        rests = " ".join(f"r{t}" for t in duration_tokens(needed))
        music = f"\\markErr {rests} \\unmarkErr" if state.mark_errors else rests
        if m.orphan_dynamics:
            music = "<>" + "".join(m.orphan_dynamics) + " " + music
        if m.orphan_hairpin_end:
            music = music + " <>\\!"
        wrappable = False
    else:
        needed = m.actual_length
        body = " ".join(_event_to_ly(e) for e in m.events)
        if m.orphan_dynamics:
            body = "<>" + "".join(m.orphan_dynamics) + " " + body
        if m.orphan_hairpin_end:
            body = body + " <>\\!"
        music = (
            f"\\markErr {body} \\unmarkErr"
            if (m.mismatch and state.mark_errors)
            else body
        )

    if needed != state.effective_len:
        prefix.append(f"\\set Timing.measureLength = {_moment(needed)}")
        state.effective_len = needed

    suffix = _BARLINE_MAP.get(end_barline or "", "")
    if not suffix:
        suffix = "|"
    return _Item(
        prefix=prefix,
        music=music,
        suffix=suffix,
        wrappable=wrappable,
        suppress_break=suppress_break,
    )


def _emit_container(
    measures: list[MeasureModel],
    state: _EmitState,
    *,
    drop_last_barline: bool = False,
    drop_repeat_start_last: bool = False,
) -> list[str]:
    """Emit a run of consecutive measures, handling breaks and percent repeats."""
    items: list[_Item] = []
    for idx, m in enumerate(measures):
        is_last = idx == len(measures) - 1
        end_barline = m.end_barline
        if is_last and drop_last_barline and end_barline in _REPEAT_END:
            end_barline = None if end_barline == "Wiederholung Ende" else end_barline
        if is_last and drop_repeat_start_last and end_barline == "Wiederholung Anfang":
            end_barline = None

        break_before = (
            state.last_staff is not None and m.staff_index != state.last_staff
        )
        state.last_staff = m.staff_index

        item = _measure_item(m, state, end_barline=end_barline, line_start=break_before)
        item.break_before = break_before and not item.suppress_break

        if m.percent_repeat:
            prev = items[-1] if items else None
            plain_prev = prev is not None and prev.wrappable and prev.suffix == "|"
            if plain_prev and not break_before and not item.prefix:
                prev.percent += 1  # type: ignore[union-attr]
                prev.suffix = item.suffix  # type: ignore[union-attr]
                continue
            # Fall back to a greyed copy of the last known measure
            if state.last_music:
                item.music = f"\\markCopy {state.last_music} \\unmarkCopy"
            else:
                rests = " ".join(f"r{t}" for t in duration_tokens(m.expected_length))
                item.music = (
                    f"\\markErr {rests} \\unmarkErr" if state.mark_errors else rests
                )
            item.wrappable = False
        elif item.wrappable:
            state.last_music = item.music
        items.append(item)
    return [it.render() for it in items]


def _find_repeat_bodies(measures: list[MeasureModel]) -> dict[int, tuple[int, int]]:
    """Map volta_group_id → (body_start_idx, first_volta_idx) over all measures."""
    groups: dict[int, list[int]] = {}
    for i, m in enumerate(measures):
        if m.volta_group_id is not None and m.volta_number is not None:
            groups.setdefault(m.volta_group_id, []).append(i)

    result: dict[int, tuple[int, int]] = {}
    prev_group_end = -1
    for gid in sorted(groups, key=lambda g: min(groups[g])):
        first_volta = min(groups[gid])
        start = prev_group_end + 1
        for j in range(first_volta - 1, prev_group_end, -1):
            bl = measures[j].end_barline or ""
            if bl in _REPEAT_START:
                start = j + 1
                break
            if bl in ("Wiederholung Ende", "Schlusstaktstrich"):
                start = j + 1
                break
        result[gid] = (start, first_volta)
        prev_group_end = max(groups[gid])
    return result


def _emit_score(
    model: ScoreModel,
    *,
    mark_errors: bool,
    default_time: str,
    trio_indent: float = 8.0,
) -> tuple[list[str], bool]:
    """Return (content lines, whether the pseudo-indent preamble is needed)."""
    measures = sorted(model.measures, key=lambda m: m.global_measure_number)
    if not measures:
        return [], False

    state = _EmitState(
        effective_len=time_length(default_time),
        time_len=time_length(default_time),
        mark_errors=mark_errors,
        trio_indent=trio_indent,
    )
    bodies = _find_repeat_bodies(measures)
    body_starts = {start: gid for gid, (start, _first) in bodies.items()}
    volta_groups: dict[int, list[MeasureModel]] = {}
    for m in measures:
        if m.volta_group_id is not None and m.volta_number is not None:
            volta_groups.setdefault(m.volta_group_id, []).append(m)

    lines: list[str] = []
    i = 0
    n = len(measures)
    while i < n:
        gid = body_starts.get(i)
        if gid is not None:
            start, first_volta = bodies[gid]
            group = volta_groups[gid]
            last_idx = max(measures.index(g) for g in group)
            body = measures[start:first_volta]
            volta1 = [g for g in group if g.volta_number == 1]
            volta2 = [g for g in group if g.volta_number == 2]

            if body:
                body_lines = _emit_container(body, state)
                lines.append("\\repeat volta 2 {")
                lines.extend(f"  {ln}" for ln in body_lines)
                lines.append("}")
                lines.append("\\alternative {")
                # LilyPond does not carry a measureLength set inside one
                # alternative over to the next, so force re-emission.
                if volta1:
                    state.effective_len = _FORCE_LENGTH
                    v1 = _emit_container(volta1, state, drop_last_barline=True)
                    lines.append("  \\volta 1 { " + " ".join(v1) + " }")
                if volta2:
                    state.effective_len = _FORCE_LENGTH
                    v2 = _emit_container(volta2, state)
                    lines.append("  \\volta 2 { " + " ".join(v2) + " }")
                lines.append("}")
                state.effective_len = _FORCE_LENGTH
            else:
                # Degenerate group without a body — emit alternatives plainly.
                lines.extend(_emit_container(group, state))
            i = last_idx + 1
            continue

        # Plain run up to the next repeat body start (or volta measure)
        j = i
        while j < n and j not in body_starts and measures[j].volta_group_id is None:
            j += 1
        if j == i:
            # A stray volta measure not covered by a body — emit plainly.
            j = i + 1
        next_is_body = j in body_starts
        lines.extend(
            _emit_container(measures[i:j], state, drop_repeat_start_last=next_is_body)
        )
        i = j
    return lines, state.used_indent


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


# ── Public API ───────────────────────────────────────────────────────────


def generate_lilypond_with_warnings(
    measures: list[dict],
    title: str,
    *,
    symbols: list[dict] | None = None,
    staves: list[dict] | None = None,
    text_regions: list[dict] | None = None,
    composer: str | None = None,
    arranger: str | None = None,
    instrument: str | None = None,
    default_clef: str = "bass",
    default_time: str = "2/2",
    default_flats: int = 0,
    mark_errors: bool = True,
    trio_indent: float = 8.0,
    top_margin: float = 1,
    bottom_margin: float = 4,
    left_margin: float = 16,
    right_margin: float = 16,
    staff_size: float = 17,
    system_distance: float = 6,
    system_padding: float = 0.6,
) -> tuple[str, list[str]]:
    """Generate LilyPond source from detected data; also return warnings."""
    model = build_score(
        measures,
        symbols,
        staves=staves,
        text_regions=text_regions,
        default_clef=default_clef,
        default_time=default_time,
        default_flats=default_flats,
    )
    content_lines, used_indent = _emit_score(
        model,
        mark_errors=mark_errors,
        default_time=default_time,
        trio_indent=trio_indent,
    )
    if not content_lines:
        content_lines = [f"\\clef {default_clef}", f"\\time {default_time}"]
    content = "\n".join(f"    {line}" for line in content_lines)
    preamble = _PSEUDO_INDENT_SCM if used_indent else ""

    header_fields = [f'  title = "{_escape(title)}"']
    if instrument:
        header_fields.append(f'  subtitle = "{_escape(instrument)}"')
    if composer:
        header_fields.append(f'  composer = "{_escape(composer)}"')
    if arranger:
        header_fields.append(f'  arranger = "{_escape(arranger)}"')
    header_fields.append("  tagline = ##f")
    header = "\n".join(header_fields)

    overrides = " ".join(f"\\override {g}.color = #red" for g in _COLOR_GROBS)
    reverts = " ".join(f"\\revert {g}.color" for g in _COLOR_GROBS)
    copy_overrides = " ".join(f"\\override {g}.color = #grey" for g in _COLOR_GROBS)

    code = f"""\\version "2.24.0"
{preamble}
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
  bookTitleMarkup = \\markup {{
    \\fill-line {{
      ""
      \\center-column {{
        \\fontsize #5 \\bold \\fromproperty #'header:title
        \\fromproperty #'header:subtitle
      }}
      \\right-column {{
        \\fromproperty #'header:composer
        \\fromproperty #'header:arranger
      }}
    }}
  }}
}}

\\header {{
{header}
}}

markErr = {{ {overrides} }}
unmarkErr = {{ {reverts} }}
markCopy = {{ {copy_overrides} }}
unmarkCopy = {{ {reverts} }}

\\score {{
  \\new Staff {{
    \\set Staff.instrumentName = ""
    \\set Staff.shortInstrumentName = ""
    \\compressEmptyMeasures
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
    return code, model.warnings


def generate_lilypond(measures: list[dict], title: str, **kwargs) -> str:
    """Generate LilyPond source code (see :func:`generate_lilypond_with_warnings`)."""
    code, _warnings = generate_lilypond_with_warnings(measures, title, **kwargs)
    return code


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
