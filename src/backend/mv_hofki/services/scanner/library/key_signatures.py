"""Canonical key-signature templates (category ``key_sig``).

Key signatures are matched as a whole group of accidentals, which is far
more reliable than matching single flats/sharps. This list defines one
template per key so the library always offers every entry, even before
variants exist. ``flats`` is positive for flats and negative for sharps.
"""

from __future__ import annotations

# (name, display_name, flats, lilypond key name)
_KEYS: list[tuple[str, str, int, str]] = [
    ("key_c_major", "C-Dur", 0, "c"),
    ("key_f_major", "F-Dur", 1, "f"),
    ("key_bes_major", "B-Dur", 2, "bes"),
    ("key_es_major", "Es-Dur", 3, "es"),
    ("key_as_major", "As-Dur", 4, "as"),
    ("key_des_major", "Des-Dur", 5, "des"),
    ("key_ges_major", "Ges-Dur", 6, "ges"),
    ("key_ces_major", "Ces-Dur", 7, "ces"),
    ("key_g_major", "G-Dur", -1, "g"),
    ("key_d_major", "D-Dur", -2, "d"),
    ("key_a_major", "A-Dur", -3, "a"),
    ("key_e_major", "E-Dur", -4, "e"),
    ("key_h_major", "H-Dur", -5, "b"),
    ("key_fis_major", "Fis-Dur", -6, "fis"),
    ("key_cis_major", "Cis-Dur", -7, "cis"),
]

# German key names → flats count (negative = sharps), major and minor.
GERMAN_MAJOR_FLATS: dict[str, int] = {
    "c": 0,
    "f": 1,
    "b": 2,
    "es": 3,
    "as": 4,
    "des": 5,
    "ges": 6,
    "ces": 7,
    "g": -1,
    "d": -2,
    "a": -3,
    "e": -4,
    "h": -5,
    "fis": -6,
    "cis": -7,
}
GERMAN_MINOR_FLATS: dict[str, int] = {
    "a": 0,
    "d": 1,
    "g": 2,
    "c": 3,
    "f": 4,
    "b": 5,
    "es": 6,
    "as": 7,
    "e": -1,
    "h": -2,
    "fis": -3,
    "cis": -4,
    "gis": -5,
    "dis": -6,
    "ais": -7,
}
LILYPOND_MAJOR_FLATS: dict[str, int] = {ly: flats for _n, _d, flats, ly in _KEYS}


def key_signature_templates() -> list[dict]:
    """Template dicts in the shape used by ``SYMBOL_TEMPLATES``."""
    out: list[dict] = []
    for name, display, flats, ly in _KEYS:
        out.append(
            {
                "category": "key_sig",
                "name": name,
                "display_name": display,
                "lilypond_token": f"\\clef bass \\key {ly} \\major g",
                "musicxml_element": (
                    f"<attributes><key><fifths>{-flats}</fifths></key></attributes>"
                ),
            }
        )
    return out


def canonical_name_for_flats(flats: int) -> str | None:
    for name, _display, f, _ly in _KEYS:
        if f == flats:
            return name
    return None
