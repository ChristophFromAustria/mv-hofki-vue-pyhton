"""Pre-seed symbol template definitions for the symbol library."""

SYMBOL_TEMPLATES = [
    # Notes
    {
        "category": "note",
        "name": "whole_note",
        "display_name": "Ganze Note",
        "lilypond_token": "1",
    },
    {
        "category": "note",
        "name": "half_note",
        "display_name": "Halbe Note",
        "lilypond_token": "2",
    },
    {
        "category": "note",
        "name": "quarter_note",
        "display_name": "Viertelnote",
        "lilypond_token": "4",
    },
    {
        "category": "note",
        "name": "eighth_note",
        "display_name": "Achtelnote",
        "lilypond_token": "8",
    },
    {
        "category": "note",
        "name": "sixteenth_note",
        "display_name": "Sechzehntelnote",
        "lilypond_token": "16",
    },
    {
        "category": "note",
        "name": "dotted_half_note",
        "display_name": "Punktierte Halbe",
        "lilypond_token": "2.",
    },
    {
        "category": "note",
        "name": "dotted_quarter_note",
        "display_name": "Punktierte Viertel",
        "lilypond_token": "4.",
    },
    {
        "category": "note",
        "name": "dotted_eighth_note",
        "display_name": "Punktierte Achtel",
        "lilypond_token": "8.",
    },
    # Rests
    {
        "category": "rest",
        "name": "whole_rest",
        "display_name": "Ganze Pause",
        "lilypond_token": "r1",
    },
    {
        "category": "rest",
        "name": "half_rest",
        "display_name": "Halbe Pause",
        "lilypond_token": "r2",
    },
    {
        "category": "rest",
        "name": "quarter_rest",
        "display_name": "Viertelpause",
        "lilypond_token": "r4",
    },
    {
        "category": "rest",
        "name": "eighth_rest",
        "display_name": "Achtelpause",
        "lilypond_token": "r8",
    },
    {
        "category": "rest",
        "name": "sixteenth_rest",
        "display_name": "Sechzehntelpause",
        "lilypond_token": "r16",
    },
    # Accidentals
    {
        "category": "accidental",
        "name": "sharp",
        "display_name": "Kreuz",
        "lilypond_token": "is",
    },
    {
        "category": "accidental",
        "name": "flat",
        "display_name": "Be",
        "lilypond_token": "es",
    },
    {
        "category": "accidental",
        "name": "natural",
        "display_name": "Auflösungszeichen",
        "lilypond_token": "!",
    },
    {
        "category": "accidental",
        "name": "double_sharp",
        "display_name": "Doppelkreuz",
        "lilypond_token": "isis",
    },
    {
        "category": "accidental",
        "name": "double_flat",
        "display_name": "Doppel-Be",
        "lilypond_token": "eses",
    },
    # Clefs
    {
        "category": "clef",
        "name": "treble_clef",
        "display_name": "Violinschlüssel",
        "lilypond_token": "\\clef treble",
    },
    {
        "category": "clef",
        "name": "bass_clef",
        "display_name": "Bassschlüssel",
        "lilypond_token": "\\clef bass",
    },
    # Time signatures
    {
        "category": "time_sig",
        "name": "time_4_4",
        "display_name": "4/4-Takt",
        "lilypond_token": "\\time 4/4",
    },
    {
        "category": "time_sig",
        "name": "time_3_4",
        "display_name": "3/4-Takt",
        "lilypond_token": "\\time 3/4",
    },
    {
        "category": "time_sig",
        "name": "time_2_4",
        "display_name": "2/4-Takt",
        "lilypond_token": "\\time 2/4",
    },
    {
        "category": "time_sig",
        "name": "time_6_8",
        "display_name": "6/8-Takt",
        "lilypond_token": "\\time 6/8",
    },
    {
        "category": "time_sig",
        "name": "time_common",
        "display_name": "Alla breve (C)",
        "lilypond_token": "\\time 4/4",
    },
    {
        "category": "time_sig",
        "name": "time_cut",
        "display_name": "Alla breve (₵)",
        "lilypond_token": "\\time 2/2",
    },
    # Barlines
    {
        "category": "barline",
        "name": "single_barline",
        "display_name": "Einfacher Taktstrich",
    },
    {
        "category": "barline",
        "name": "double_barline",
        "display_name": "Doppelter Taktstrich",
    },
    {
        "category": "barline",
        "name": "final_barline",
        "display_name": "Schlusstaktstrich",
    },
    {
        "category": "barline",
        "name": "repeat_start",
        "display_name": "Wiederholung Anfang",
    },
    {"category": "barline", "name": "repeat_end", "display_name": "Wiederholung Ende"},
    # Dynamics
    {"category": "dynamic", "name": "pp", "display_name": "Pianissimo"},
    {"category": "dynamic", "name": "p", "display_name": "Piano"},
    {"category": "dynamic", "name": "mp", "display_name": "Mezzopiano"},
    {"category": "dynamic", "name": "mf", "display_name": "Mezzoforte"},
    {"category": "dynamic", "name": "f", "display_name": "Forte"},
    {"category": "dynamic", "name": "ff", "display_name": "Fortissimo"},
    {"category": "dynamic", "name": "crescendo", "display_name": "Crescendo"},
    {"category": "dynamic", "name": "decrescendo", "display_name": "Decrescendo"},
    # Articulations
    {"category": "ornament", "name": "staccato", "display_name": "Staccato"},
    {"category": "ornament", "name": "accent", "display_name": "Akzent"},
    {"category": "ornament", "name": "tenuto", "display_name": "Tenuto"},
    {"category": "ornament", "name": "fermata", "display_name": "Fermate"},
    # Other
    {"category": "other", "name": "tie", "display_name": "Haltebogen"},
    {"category": "other", "name": "slur", "display_name": "Bindebogen"},
    {"category": "other", "name": "dot", "display_name": "Punkt (Verlängerung)"},
    {"category": "other", "name": "segno", "display_name": "Segno"},
    {"category": "other", "name": "coda", "display_name": "Coda"},
    {"category": "other", "name": "trill", "display_name": "Triller"},
]
