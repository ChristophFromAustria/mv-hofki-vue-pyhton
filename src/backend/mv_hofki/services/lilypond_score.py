"""Build a structured score model from detected scanner data.

Pure logic, no DB access. Takes plain dicts (measures, symbols, staves,
text regions) as produced by the scanner pipeline and resolves them into
per-measure event lists that the LilyPond emitter can render:

* symbols are assigned to measures by their x-centre
* notes/rests get durations from their template name/display name
* note pitches are derived from the note-head position relative to the
  bottom staff line, the clef and the key signature
* dynamics, hairpins, articulations and text marks are attached to the
  nearest rhythmic event
* every measure is checked against the time signature; mismatches are
  flagged so the emitter can colour them
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass, field
from fractions import Fraction

from mv_hofki.services.scanner.library.key_signatures import (
    GERMAN_MAJOR_FLATS,
    GERMAN_MINOR_FLATS,
    LILYPOND_MAJOR_FLATS,
)
from mv_hofki.services.scanner.stages.post_matching.staff_start import (
    StaffStartItem,
    resolve_staff_start,
)

# ── Constants ────────────────────────────────────────────────────────────

_LETTERS = "cdefgab"
# Diatonic index (octave * 7 + letter index) of the bottom staff line.
_CLEF_BOTTOM_LINE = {
    "bass": 2 * 7 + 4,  # G2
    "treble": 4 * 7 + 2,  # E4
    "alto": 3 * 7 + 3,  # F3
    "tenor": 3 * 7 + 2,  # D3
}
_FLAT_ORDER = "beadgcf"
_SHARP_ORDER = "fcgdaeb"
_KEY_BY_FLATS = {
    0: "c",
    1: "f",
    2: "bes",
    3: "es",
    4: "as",
    5: "des",
    6: "ges",
    7: "ces",
}
_KEY_BY_SHARPS = {1: "g", 2: "d", 3: "a", 4: "e", 5: "b", 6: "fis", 7: "cis"}

# Offset (in line spacings) from the box edge to the note-head centre.
_HEAD_OFFSET = 0.5

_DYNAMIC_ALIASES = {
    "fortepiano": "fp",
    "forzando": "fz",
    "sforzando": "sfz",
    "pianissimo": "pp",
    "piano": "p",
    "mezzopiano": "mp",
    "mezzoforte": "mf",
    "forte": "f",
    "fortissimo": "ff",
}
_KNOWN_DYNAMICS = {
    "ppp",
    "pp",
    "p",
    "mp",
    "mf",
    "f",
    "ff",
    "fff",
    "fp",
    "sf",
    "sff",
    "sp",
    "spp",
    "sfz",
    "rfz",
    "fz",
}
_ARTICULATIONS = {
    "accent": "->",
    "staccato": "-.",
    "tenuto": "--",
    "marcato": "-^",
    "fermata": "\\fermata",
    "trill": "\\trill",
}
_SECTION_MARK_RE = re.compile(
    r"^(trio|intro|coda|fine|d\.?\s*c\.?|d\.?\s*s\.?|da\s+capo|dal\s+segno)\b",
    re.IGNORECASE,
)
_TEXT_DIRECTION_RE = re.compile(
    r"^(cresc\.?|decresc\.?|dim\.?|rit\.?|rall\.?|accel\.?|a\s+tempo|solo|tutti|"
    r"poco\b.*|molto\b.*|espr\.?|dolce|marcato|legato|stacc\.?)$",
    re.IGNORECASE,
)
_NUMBER_WORDS = {"zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "acht": 8}


# ── Data model ───────────────────────────────────────────────────────────


@dataclass
class Event:
    """A rhythmic event inside a measure (note, chord or rest)."""

    kind: str  # "note" | "rest"
    duration: Fraction
    duration_token: str
    x_center: float
    pitches: list[str] = field(default_factory=list)
    head_positions: list[float] = field(default_factory=list)  # staff steps
    articulations: list[str] = field(default_factory=list)
    dynamics: list[str] = field(default_factory=list)
    hairpin_start: str | None = None  # "\\<" or "\\>"
    hairpin_end: bool = False
    texts: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class MeasureModel:
    """One detected measure with resolved content."""

    staff_index: int
    measure_number_in_staff: int
    global_measure_number: int
    x_start: int
    x_end: int
    end_barline: str | None = None
    volta_number: int | None = None
    volta_group_id: int | None = None

    events: list[Event] = field(default_factory=list)
    clef: str | None = None  # clef change at measure start
    time: str | None = None  # time signature change at measure start
    key_flats: int | None = None  # key change (negative = sharps)
    marks: list[str] = field(default_factory=list)  # LilyPond \mark markups
    section_label: str | None = None  # e.g. "Trio" → indented system with label
    percent_repeat: bool = False
    mmrest_measures: int | None = None
    orphan_dynamics: list[str] = field(default_factory=list)
    orphan_hairpin_end: bool = False

    expected_length: Fraction = Fraction(1)
    mismatch: bool = False

    @property
    def actual_length(self) -> Fraction:
        return sum((e.duration for e in self.events), Fraction(0))


@dataclass
class ScoreModel:
    measures: list[MeasureModel]
    warnings: list[str] = field(default_factory=list)


@dataclass
class _Sym:
    """Normalised view of a symbol dict."""

    staff_index: int
    x: float
    y: float
    width: float
    height: float
    x_center: float
    sy_top: float | None
    sy_bot: float | None
    name: str
    display: str
    category: str
    confidence: float
    line_spacing: float

    @property
    def text(self) -> str:
        return f"{self.name} {self.display}".lower()


# ── Template interpretation ──────────────────────────────────────────────


def duration_from_names(name: str, display: str) -> tuple[str, Fraction] | None:
    """Derive a LilyPond duration token from template name/display name."""
    text = f"{name} {display}".lower()
    base: int | None = None
    if re.search(r"sechzehntel|sixteenth|16th", text):
        base = 16
    elif re.search(r"achtel|eighth", text):
        base = 8
    elif re.search(r"viertel|quarter", text):
        base = 4
    elif re.search(r"halbe|half", text):
        base = 2
    elif re.search(r"ganze|whole", text):
        base = 1
    if base is None:
        return None
    dotted = bool(re.search(r"punktiert|dotted", text))
    token = f"{base}." if dotted else str(base)
    length = Fraction(1, base)
    if dotted:
        length = length * Fraction(3, 2)
    return token, length


def stem_direction(name: str, display: str) -> str | None:
    """Return "up", "down" or None (no stem, e.g. whole note).

    The display name is authoritative — internal template names have been
    observed to contradict it (e.g. ``halbe_note_steil_unten`` labelled
    "Halbe Note Stiel oben").
    """
    for text in (display.lower(), name.lower()):
        if re.search(r"unten|down", text):
            return "down"
        if re.search(r"oben|\bup\b", text):
            return "up"
    if re.search(r"ganze|whole", f"{name} {display}".lower()):
        return None
    return "up"


def multi_measure_rest_count(name: str, display: str) -> int | None:
    """Parse "2 Takte Pause Kompakt" / "zwei_takte_kompakt_pause" → 2."""
    text = f"{name} {display}".lower()
    if not re.search(r"takte|kompakt|measures", text):
        return None
    m = re.search(r"(\d+)", text)
    if m:
        return int(m.group(1))
    for word, value in _NUMBER_WORDS.items():
        if word in text:
            return value
    return None


def dynamic_token(name: str) -> str | None:
    key = name.lower()
    key = _DYNAMIC_ALIASES.get(key, key)
    return f"\\{key}" if key in _KNOWN_DYNAMICS else None


def clef_from_names(name: str, display: str) -> str | None:
    text = f"{name} {display}".lower()
    for clef in ("bass", "treble", "alto", "tenor"):
        if clef in text:
            return clef
    if "violin" in text:
        return "treble"
    return None


def time_from_names(name: str, display: str) -> str | None:
    text = f"{name} {display}".lower()
    if re.search(r"cut|₵|alla breve \(₵\)", text):
        return "2/2"
    if "common" in text:
        return "4/4"
    m = re.search(r"(\d+)[_/](\d+)", text)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None


def accidental_from_names(name: str, display: str) -> tuple[str, int] | None:
    """Return (kind, count): kind in {"flat","sharp","natural"}."""
    text = f"{name} {display}".lower()
    m = re.match(r"^(\d)\s*(b|♭)\b", name.lower()) or re.match(
        r"^(\d)\s*(b|♭)$", display.lower()
    )
    if m:
        return "flat", int(m.group(1))
    m = re.match(r"^(\d)\s*(#|♯)", name.lower()) or re.match(
        r"^(\d)\s*(#|♯)$", display.lower()
    )
    if m:
        return "sharp", int(m.group(1))
    if re.search(r"double_flat|doppel-be|doppelbe", text):
        return "flat", 2
    if re.search(r"double_sharp|doppelkreuz", text):
        return "sharp", 2
    if re.search(r"natural|auflösung", text):
        return "natural", 0
    if re.search(r"flat|\bbe\b|\bb\b", text):
        return "flat", 1
    if re.search(r"sharp|kreuz", text):
        return "sharp", 1
    return None


def key_flats_from_names(name: str, display: str) -> int | None:
    """Flat count (negative = sharps) of a key-signature template.

    Understands canonical names (``key_bes_major``), German key names
    ("B-Dur", "Es-Dur", "a-Moll") and accidental-group names ("3b", "2#").
    """
    m = re.match(r"^key_([a-h]+(?:is|es|s)?)_(major|minor)$", name.lower())
    if m and m.group(2) == "major" and m.group(1) in LILYPOND_MAJOR_FLATS:
        return LILYPOND_MAJOR_FLATS[m.group(1)]
    for text in (display, name):
        t = text.strip().lower().replace("_", "-")
        m = re.match(r"^([a-h](?:is|es|s)?)-?(dur|moll|major|minor)$", t)
        if m:
            table = (
                GERMAN_MAJOR_FLATS
                if m.group(2) in ("dur", "major")
                else GERMAN_MINOR_FLATS
            )
            if m.group(1) in table:
                return table[m.group(1)]
        m = re.match(r"^(\d)\s*(b|♭)$", t)
        if m:
            return int(m.group(1))
        m = re.match(r"^(\d)\s*(#|♯|kreuz)$", t)
        if m:
            return -int(m.group(1))
    return None


def time_length(time_sig: str) -> Fraction:
    num, den = time_sig.split("/")
    return Fraction(int(num), int(den))


def duration_tokens(length: Fraction) -> list[str]:
    """Decompose a length into LilyPond duration tokens (e.g. 3/4 → ["2."])."""
    tokens: list[str] = []
    remaining = length
    for base in (1, 2, 4, 8, 16, 32):
        unit = Fraction(1, base)
        while remaining >= unit:
            if (
                remaining >= unit * Fraction(3, 2)
                and remaining - unit * Fraction(3, 2) >= 0
            ):
                tokens.append(f"{base}.")
                remaining -= unit * Fraction(3, 2)
            else:
                tokens.append(str(base))
                remaining -= unit
    return tokens or ["4"]


# ── Pitch helpers ────────────────────────────────────────────────────────


def key_signature_name(flats: int) -> str:
    """Return the LilyPond key name for a flat count (negative = sharps)."""
    if flats >= 0:
        return _KEY_BY_FLATS.get(min(flats, 7), "c")
    return _KEY_BY_SHARPS.get(min(-flats, 7), "c")


def _key_alterations(flats: int) -> dict[str, int]:
    if flats >= 0:
        return {letter: -1 for letter in _FLAT_ORDER[: min(flats, 7)]}
    return {letter: 1 for letter in _SHARP_ORDER[: min(-flats, 7)]}


def pitch_name(step: int, clef: str, flats: int, alter: int | None = None) -> str:
    """LilyPond absolute pitch for a staff step above the bottom line.

    ``step`` counts half line-spacings (0 = bottom line, 1 = first space…).
    ``alter`` overrides the key signature (-1 flat, 0 natural, 1 sharp).
    """
    base = _CLEF_BOTTOM_LINE.get(clef, _CLEF_BOTTOM_LINE["bass"])
    diatonic = base + step
    octave, letter_idx = divmod(diatonic, 7)
    letter = _LETTERS[letter_idx]
    alteration = alter if alter is not None else _key_alterations(flats).get(letter, 0)
    if alteration == -1:
        name = {"a": "as", "e": "es"}.get(letter, letter + "es")
    elif alteration == -2:
        name = {"a": "ases", "e": "eses"}.get(letter, letter + "eses")
    elif alteration == 1:
        name = letter + "is"
    elif alteration == 2:
        name = letter + "isis"
    else:
        name = letter
    rel = octave - 3
    marks = "'" * rel if rel > 0 else "," * (-rel)
    return name + marks


def head_step(sym_top: float, sym_bot: float, stem: str | None) -> float:
    """Note-head centre in staff steps (half line-spacings above bottom line).

    Variants are cropped tightly to their ink (see
    ``symbol_library.tighten_all_variants``), so the head sits half a line
    spacing inside the stem-free end of the detection box.
    """
    if stem == "up":
        center = sym_bot + _HEAD_OFFSET
    elif stem == "down":
        center = sym_top - _HEAD_OFFSET
    else:
        center = (sym_top + sym_bot) / 2.0
    return center * 2.0


# ── Model construction ───────────────────────────────────────────────────


def _norm_symbol(raw: dict) -> _Sym | None:
    cat = (raw.get("template_category") or "").lower()
    name = raw.get("template_name") or ""
    display = raw.get("template_display_name") or ""
    if not name and not display:
        return None
    w = float(raw.get("width") or 0)
    h = float(raw.get("height") or 0)
    x = float(raw.get("x") or 0)
    y = float(raw.get("y") or 0)
    sy_top = raw.get("staff_y_top")
    sy_bot = raw.get("staff_y_bottom")
    ls = float(raw.get("line_spacing") or 0)
    if ls <= 0 and sy_top is not None and sy_bot is not None and sy_top != sy_bot and h:
        ls = h / abs(float(sy_top) - float(sy_bot))
    if ls <= 0:
        ls = max(h / 4.0, 1.0)
    return _Sym(
        staff_index=int(raw.get("staff_index") or 0),
        x=x,
        y=y,
        width=w,
        height=h,
        x_center=x + w / 2.0,
        sy_top=float(sy_top) if sy_top is not None else None,
        sy_bot=float(sy_bot) if sy_bot is not None else None,
        name=name,
        display=display,
        category=cat,
        confidence=float(raw.get("confidence") or 0.0),
        line_spacing=ls,
    )


def _nearest_event(
    events: list[Event], x: float, *, notes_only: bool = False
) -> Event | None:
    candidates = [e for e in events if (e.kind == "note" or not notes_only)]
    if not candidates:
        return None
    return min(candidates, key=lambda e: abs(e.x_center - x))


def build_score(
    measures: list[dict],
    symbols: list[dict] | None = None,
    *,
    staves: list[dict] | None = None,
    text_regions: list[dict] | None = None,
    default_clef: str = "bass",
    default_time: str = "2/2",
    default_flats: int = 0,
) -> ScoreModel:
    """Resolve measures + symbols into a :class:`ScoreModel`."""
    warnings: list[str] = []

    models = [
        MeasureModel(
            staff_index=m["staff_index"],
            measure_number_in_staff=m["measure_number_in_staff"],
            global_measure_number=m["global_measure_number"],
            x_start=int(m.get("x_start") or 0),
            x_end=int(m.get("x_end") or 0),
            end_barline=m.get("end_barline"),
            volta_number=m.get("volta_number"),
            volta_group_id=m.get("volta_group_id"),
        )
        for m in measures
    ]
    models.sort(key=lambda m: (m.staff_index, m.measure_number_in_staff))

    by_staff: dict[int, list[MeasureModel]] = {}
    for m in models:
        by_staff.setdefault(m.staff_index, []).append(m)

    syms = [s for s in (_norm_symbol(r) for r in (symbols or [])) if s is not None]
    syms_by_staff: dict[int, list[_Sym]] = {}
    for s in syms:
        syms_by_staff.setdefault(s.staff_index, []).append(s)
    for lst in syms_by_staff.values():
        lst.sort(key=lambda s: s.x_center)

    # Running state across the whole scan
    clef = default_clef
    time_sig = default_time
    flats = default_flats
    first_measure = True
    pending_flats: int | None = None  # courtesy key signature at a line end

    # An indented system marks a new section (the Trio of a march).
    first_starts = {idx: ms[0].x_start for idx, ms in by_staff.items()}
    typical_start = _median([float(v) for v in first_starts.values()]) or 0.0

    for staff_index in sorted(by_staff.keys()):
        staff_measures = by_staff[staff_index]
        staff_syms = syms_by_staff.get(staff_index, [])
        starts = [m.x_start for m in staff_measures]

        def measure_for_x(x: float) -> MeasureModel:
            idx = bisect_right(starts, x) - 1
            idx = max(0, min(idx, len(staff_measures) - 1))
            return staff_measures[idx]

        # ── Pass 1: staff start (clef → key → time) and structural symbols ──
        staff_ls = _median([s.line_spacing for s in staff_syms]) or 1.0
        start_items = [
            StaffStartItem(
                key=i,
                x_start=s.x,
                x_end=s.x + s.width,
                category=s.category,
                confidence=s.confidence,
            )
            for i, s in enumerate(staff_syms)
        ]
        header = resolve_staff_start(
            start_items, float(staff_measures[0].x_start), staff_ls
        )
        if header.zone_end is not None:
            # Header zone resolved: drop everything that cannot sit there.
            staff_syms = [s for i, s in enumerate(staff_syms) if i not in header.drop]
        chosen_key_sym = (
            start_items[header.chosen["key_sig"]]
            if "key_sig" in header.chosen
            else None
        )
        rhythmic = [s for s in staff_syms if s.category in ("note", "rest")]
        first_rhythmic_x = rhythmic[0].x_center if rhythmic else float("inf")
        time_syms = [s for s in staff_syms if s.category == "time_sig"]
        first_time_x = time_syms[0].x_center if time_syms else float("inf")
        # Zone in which single accidentals count as key signature: right after
        # the clef (or the staff start when no clef was found).
        zone_anchor = (
            header.zone_end
            if header.zone_end is not None
            else float(staff_measures[0].x_start)
        )
        key_zone_end = min(first_rhythmic_x, first_time_x, zone_anchor + 4.0 * staff_ls)

        per_measure_attrs: dict[int, dict] = {}
        if pending_flats is not None:
            per_measure_attrs.setdefault(id(staff_measures[0]), {})["flats"] = (
                pending_flats
            )
            pending_flats = None
        indent_ls = staff_ls if staff_ls > 1.0 else 30.0
        if staff_index != min(by_staff) and (
            float(staff_measures[0].x_start) > typical_start + 3.0 * indent_ls
        ):
            staff_measures[0].section_label = "Trio"
        last_rhythmic_x = rhythmic[-1].x_center if rhythmic else float("-inf")
        for s in staff_syms:
            if s.category == "clef":
                c = clef_from_names(s.name, s.display)
                if c:
                    per_measure_attrs.setdefault(id(measure_for_x(s.x_center)), {})[
                        "clef"
                    ] = c
            elif s.category == "time_sig":
                t = time_from_names(s.name, s.display)
                if t:
                    per_measure_attrs.setdefault(id(measure_for_x(s.x_center)), {})[
                        "time"
                    ] = t
            elif s.category == "key_sig":
                k = key_flats_from_names(s.name, s.display)
                if k is None:
                    continue
                if s.x_center > last_rhythmic_x and s.x_center > key_zone_end:
                    # Courtesy key signature after the last note → next system
                    pending_flats = k
                    continue
                per_measure_attrs.setdefault(id(measure_for_x(s.x_center)), {})[
                    "flats"
                ] = k

        if chosen_key_sym is None and "flats" not in per_measure_attrs.get(
            id(staff_measures[0]), {}
        ):
            # No whole-group key template — count single accidentals in the zone.
            key_acc = [
                s
                for s in staff_syms
                if s.category == "accidental" and s.x_center < key_zone_end
            ]
            total = 0
            for s in key_acc:
                acc = accidental_from_names(s.name, s.display)
                if acc is None:
                    continue
                kind, count = acc
                if kind == "flat":
                    total += count
                elif kind == "sharp":
                    total -= count
            if total != 0:
                per_measure_attrs.setdefault(id(staff_measures[0]), {})["flats"] = total

        # ── Pass 2: rhythmic events ──
        staff_events: list[Event] = []  # in x order across the staff
        for m in staff_measures:
            attrs = per_measure_attrs.get(id(m), {})
            if "clef" in attrs and (attrs["clef"] != clef or first_measure):
                m.clef = attrs["clef"]
                clef = attrs["clef"]
            if "time" in attrs and (attrs["time"] != time_sig or first_measure):
                m.time = attrs["time"]
                time_sig = attrs["time"]
            if "flats" in attrs and (attrs["flats"] != flats or first_measure):
                m.key_flats = attrs["flats"]
                flats = attrs["flats"]
            if first_measure:
                m.clef = m.clef or clef
                m.time = m.time or time_sig
                m.key_flats = m.key_flats if m.key_flats is not None else flats
                first_measure = False
            m.expected_length = time_length(time_sig)

            in_measure = [
                s
                for s in staff_syms
                if m.x_start <= s.x_center < m.x_end
                or (m is staff_measures[0] and s.x_center < m.x_start)
                or (m is staff_measures[-1] and s.x_center >= m.x_end)
            ]

            notes = [s for s in in_measure if s.category == "note"]
            rests = [s for s in in_measure if s.category == "rest"]

            # Multi-measure rests
            for r in rests:
                mm_count = multi_measure_rest_count(r.name, r.display)
                if mm_count:
                    m.mmrest_measures = mm_count
            if m.mmrest_measures:
                rests = [
                    r for r in rests if not multi_measure_rest_count(r.name, r.display)
                ]

            # Measure repeat sign
            if (
                any(
                    s.category == "other"
                    and re.search(r"takt.*wiederhol|percent|simile", s.text)
                    for s in in_measure
                )
                and not notes
            ):
                m.percent_repeat = True

            # Build note events with chord merging
            events: list[Event] = []
            notes.sort(key=lambda s: s.x_center)
            i = 0
            while i < len(notes):
                group = [notes[i]]
                j = i + 1
                tol = notes[i].line_spacing * 0.75
                while (
                    j < len(notes) and abs(notes[j].x_center - notes[i].x_center) <= tol
                ):
                    group.append(notes[j])
                    j += 1
                lead = max(group, key=lambda s: s.confidence)
                dur = duration_from_names(lead.name, lead.display) or (
                    "4",
                    Fraction(1, 4),
                )
                ev = Event(
                    kind="note",
                    duration=dur[1],
                    duration_token=dur[0],
                    x_center=sum(s.x_center for s in group) / len(group),
                    confidence=lead.confidence,
                )
                for s in group:
                    if s.sy_top is None or s.sy_bot is None:
                        continue
                    step = head_step(
                        s.sy_top, s.sy_bot, stem_direction(s.name, s.display)
                    )
                    ev.head_positions.append(step)
                if not ev.head_positions:
                    ev.head_positions.append(4.0)  # middle line placeholder
                ev.head_positions = _cluster_steps(ev.head_positions)
                events.append(ev)
                i = j

            for r in rests:
                dur = duration_from_names(r.name, r.display) or ("4", Fraction(1, 4))
                events.append(
                    Event(
                        kind="rest",
                        duration=dur[1],
                        duration_token=dur[0],
                        x_center=r.x_center,
                        confidence=r.confidence,
                    )
                )
            events.sort(key=lambda e: e.x_center)

            # Augmentation dots ("Punkt") → lengthen previous event
            for s in in_measure:
                if s.category == "other" and re.search(r"\bdot\b|punkt", s.text):
                    prev = [e for e in events if e.x_center < s.x_center]
                    if prev and not prev[-1].duration_token.endswith("."):
                        e = prev[-1]
                        e.duration_token += "."
                        e.duration = e.duration * Fraction(3, 2)

            # In-measure accidentals → alter next note
            alters: dict[int, dict[int, int]] = {}
            for s in in_measure:
                if s.category != "accidental" or s.x_center < key_zone_end:
                    continue
                acc = accidental_from_names(s.name, s.display)
                if acc is None or acc[1] > 2 and acc[0] != "natural":
                    continue
                kind, count = acc
                if count > 2:
                    continue  # a key-signature template inside the measure — ignore
                alter = {"flat": -count, "sharp": count, "natural": 0}[kind]
                following = [
                    e
                    for e in events
                    if e.kind == "note"
                    and e.x_center > s.x_center
                    and e.x_center - s.x_center <= s.line_spacing * 3
                ]
                if not following:
                    continue
                acc_target = following[0]
                # pick the head closest to the accidental's vertical centre
                if (
                    s.sy_top is not None
                    and s.sy_bot is not None
                    and acc_target.head_positions
                ):
                    acc_step = s.sy_top + s.sy_bot  # centre * 2
                    hi = min(
                        range(len(acc_target.head_positions)),
                        key=lambda k: abs(acc_target.head_positions[k] - acc_step),
                    )
                else:
                    hi = 0
                alters.setdefault(id(acc_target), {})[hi] = alter

            # Resolve pitches
            for e in events:
                if e.kind != "note":
                    continue
                pitches: list[str] = []
                for k, step in enumerate(e.head_positions):
                    override = alters.get(id(e), {}).get(k)
                    pitches.append(pitch_name(round(step), clef, flats, override))
                # dedupe identical pitches, keep order
                e.pitches = list(dict.fromkeys(pitches))

            # Articulations, dynamics, section marks
            dynamic_conf: dict[int, float] = {}
            for s in in_measure:
                if s.category == "ornament":
                    key = s.name.lower()
                    tok = _ARTICULATIONS.get(key)
                    if tok is None:
                        for art_name, art_tok in _ARTICULATIONS.items():
                            if art_name in s.text:
                                tok = art_tok
                                break
                    if tok:
                        target = _nearest_event(
                            events, s.x_center, notes_only=True
                        ) or _nearest_event(events, s.x_center)
                        if target:
                            target.articulations.append(tok)
                elif s.category == "dynamic":
                    if re.search(r"crescendo|decrescendo|hairpin|keil", s.text):
                        continue  # handled staff-wide below
                    tok = dynamic_token(s.name) or dynamic_token(s.display)
                    if tok is None:
                        continue
                    target = _nearest_event(events, s.x_center)
                    if target is None:
                        m.orphan_dynamics.append(tok)
                        continue
                    # Only one absolute dynamic per event — keep the most confident.
                    prev_conf = dynamic_conf.get(id(target), -1.0)
                    if target.dynamics and s.confidence <= prev_conf:
                        continue
                    target.dynamics = [tok]
                    dynamic_conf[id(target)] = s.confidence
                elif s.category == "other":
                    if "segno" in s.text:
                        m.marks.append(
                            '\\mark \\markup { \\musicglyph "scripts.segno" }'
                        )
                    elif "coda" in s.text:
                        m.marks.append(
                            '\\mark \\markup { \\musicglyph "scripts.coda" }'
                        )
                    elif "trill" in s.text or "triller" in s.text:
                        target = _nearest_event(events, s.x_center, notes_only=True)
                        if target:
                            target.articulations.append("\\trill")
                    elif "trio" in s.text:
                        m.section_label = "Trio"

            m.events = events
            staff_events.extend(events)

            if m.mmrest_measures:
                m.expected_length = time_length(time_sig) * m.mmrest_measures
                m.mismatch = bool(events)
            elif m.percent_repeat:
                m.mismatch = False
            elif not events:
                m.mismatch = True
            else:
                m.mismatch = m.actual_length != m.expected_length
            if m.mismatch and (events or not (m.mmrest_measures or m.percent_repeat)):
                warnings.append(
                    f"Takt {m.global_measure_number} (System {staff_index + 1}, "
                    f"Takt {m.measure_number_in_staff}): "
                    f"{_fmt_len(m.actual_length)} statt {_fmt_len(m.expected_length)}"
                )

        # ── Pass 3: hairpins (staff-wide, may span measures) ──
        staff_events.sort(key=lambda e: e.x_center)
        for s in staff_syms:
            if s.category != "dynamic" or not re.search(
                r"crescendo|decrescendo", s.text
            ):
                continue
            tok = "\\<" if "decrescendo" not in s.text else "\\>"
            x_min, x_max = s.x, s.x + s.width
            tol = s.line_spacing
            start = next((e for e in staff_events if e.x_center >= x_min - tol), None)
            if start is None:
                m = measure_for_x(x_min)
                m.orphan_dynamics.append(tok)
                m.orphan_hairpin_end = True
                continue
            ends = [
                e
                for e in staff_events
                if x_min < e.x_center <= x_max + tol and e is not start
            ]
            end = ends[-1] if ends else None
            if end is None:
                idx = staff_events.index(start)
                end = staff_events[idx + 1] if idx + 1 < len(staff_events) else None
            start.hairpin_start = tok
            if end is not None:
                if not end.dynamics:
                    end.hairpin_end = True
            else:
                measure_for_x(x_max).orphan_hairpin_end = True

        # ── Pass 4: text regions → section marks / directions ──
        for tr in text_regions or []:
            if int(tr.get("staff_index", -1)) != staff_index:
                continue
            text = (tr.get("text") or "").strip()
            if not text:
                continue
            tx = float(tr.get("x") or 0) + float(tr.get("width") or 0) / 2.0
            if _SECTION_MARK_RE.match(text):
                label = _SECTION_MARK_RE.match(text).group(1).strip()  # type: ignore[union-attr]
                label = label[0].upper() + label[1:]
                m = measure_for_x(tx)
                if label.lower() == "trio":
                    m.section_label = "Trio"
                else:
                    m.marks.append(
                        f'\\mark \\markup {{ \\bold \\large "{_escape(label)}" }}'
                    )
            elif _TEXT_DIRECTION_RE.match(text):
                m = measure_for_x(tx)
                target = _nearest_event(m.events, tx)
                if target:
                    target.texts.append(text.rstrip("."))

    return ScoreModel(measures=models, warnings=warnings)


def _cluster_steps(steps: list[float], tolerance: float = 1.0) -> list[float]:
    """Merge head positions that belong to the same physical note head.

    A stem-up and a stem-down template often both fire on one note; their
    measured heads differ by measurement noise only. Real chords are at
    least a third (two steps) apart.
    """
    if len(steps) < 2:
        return steps
    ordered = sorted(steps)
    clusters: list[list[float]] = [[ordered[0]]]
    for v in ordered[1:]:
        if v - clusters[-1][-1] <= tolerance:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [sum(c) / len(c) for c in clusters]


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _fmt_len(length: Fraction) -> str:
    if length.denominator == 1:
        return f"{length.numerator}/1"
    return f"{length.numerator}/{length.denominator}"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')
