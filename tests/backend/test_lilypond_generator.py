"""Tests for LilyPond code generation from measure + symbol data."""

from mv_hofki.services.lilypond_generator import (
    generate_lilypond,
    generate_lilypond_with_warnings,
)


def _measures(layout, width=100):
    """Helper: build measure dicts from a layout like [(staff, count), ...]."""
    result = []
    global_num = 1
    for staff_index, count in layout:
        for local in range(1, count + 1):
            result.append(
                {
                    "staff_index": staff_index,
                    "measure_number_in_staff": local,
                    "global_measure_number": global_num,
                    "x_start": (local - 1) * width,
                    "x_end": local * width,
                }
            )
            global_num += 1
    return result


def _note(staff, x, display, sy_top, sy_bot, *, name=None, conf=0.8, cat="note"):
    """Helper: a symbol dict as passed by the endpoint."""
    height = (sy_top - sy_bot) * 10  # line spacing 10 px
    return {
        "staff_index": staff,
        "x": x,
        "y": 0,
        "width": 10,
        "height": height,
        "staff_y_top": sy_top,
        "staff_y_bottom": sy_bot,
        "line_spacing": 10,
        "confidence": conf,
        "template_name": name or display.lower().replace(" ", "_"),
        "template_display_name": display,
        "template_category": cat,
    }


def _mark(staff, x, name, display, cat, *, width=10, conf=0.8):
    return {
        "staff_index": staff,
        "x": x,
        "y": 0,
        "width": width,
        "height": 10,
        "staff_y_top": -0.5,
        "staff_y_bottom": -1.5,
        "line_spacing": 10,
        "confidence": conf,
        "template_name": name,
        "template_display_name": display,
        "template_category": cat,
    }


# ── Structure ────────────────────────────────────────────────────────────


def test_basic_structure():
    code = generate_lilypond(_measures([(0, 2)]), "Test Stück")
    assert '\\version "2.24.0"' in code
    assert "a5" in code
    assert 'title = "Test Stück"' in code
    assert "\\clef bass" in code
    assert "\\time 2/2" in code


def test_header_fields():
    code = generate_lilypond(
        _measures([(0, 1)]),
        "T",
        composer="J. F. Wagner",
        arranger="bearb. H. Kliment",
        instrument="Tuba 1",
    )
    assert 'composer = "J. F. Wagner"' in code
    assert 'arranger = "bearb. H. Kliment"' in code
    assert 'subtitle = "Tuba 1"' in code


def test_empty_measures_render_as_marked_whole_rests():
    code = generate_lilypond(_measures([(0, 3), (1, 2)]), "Test")
    assert code.count("\\markErr r1 \\unmarkErr") == 5
    assert code.count("\\break") == 1


def test_single_system_has_no_break():
    code = generate_lilypond(_measures([(0, 4)]), "Test")
    assert "\\break" not in code


def test_mark_errors_can_be_disabled():
    code = generate_lilypond(_measures([(0, 1)]), "Test", mark_errors=False)
    assert "\\markErr" not in code.split("\\score")[1]


def test_barline_types():
    names = [
        "Wiederholung Anfang",
        "Wiederholung Ende",
        "Doppelter Taktstrich",
        "Schlusstaktstrich",
        "Wiederholung Beidseitig",
    ]
    measures = _measures([(0, len(names))])
    for m, bl in zip(measures, names):
        m["end_barline"] = bl
    code = generate_lilypond(measures, "Test")
    for cmd in (
        '\\bar ".|:"',
        '\\bar ":|."',
        '\\bar "||"',
        '\\bar "|."',
        '\\bar ":|.|:"',
    ):
        assert cmd in code


def test_simple_barline_uses_bar_check_only():
    measures = _measures([(0, 2)])
    measures[0]["end_barline"] = "Einfacher Taktstrich"
    code = generate_lilypond(measures, "Test")
    assert "\\bar" not in code


def test_no_measures():
    code = generate_lilypond([], "Empty")
    assert '\\version "2.24.0"' in code
    assert "\\clef bass" in code


# ── Repeats / voltas ─────────────────────────────────────────────────────


def _volta_layout():
    measures = _measures([(0, 4)])
    measures[0]["end_barline"] = "Einfacher Taktstrich"
    measures[1]["end_barline"] = "Einfacher Taktstrich"
    measures[2].update(
        end_barline="Wiederholung Ende", volta_number=1, volta_group_id=1
    )
    measures[3].update(end_barline=None, volta_number=2, volta_group_id=1)
    return measures


def test_volta_brackets_generate_repeat_alternative():
    code = generate_lilypond(_volta_layout(), "Test")
    assert "\\repeat volta 2 {" in code
    assert "\\alternative {" in code
    assert "\\volta 1 {" in code
    assert "\\volta 2 {" in code
    # the repeat-end bar inside volta 1 is implied by \alternative
    assert (
        "\\volta 1 { " in code
        and ':|."' not in code.split("\\volta 1")[1].split("}")[0]
    )


def test_volta_across_system_break_keeps_one_repeat_block():
    """Volta 1 at the end of one system, volta 2 at the start of the next."""
    measures = _measures([(0, 3), (1, 3)])
    measures[0]["end_barline"] = "Wiederholung Anfang"
    measures[2].update(
        end_barline="Wiederholung Ende", volta_number=1, volta_group_id=1
    )
    measures[3].update(
        end_barline="Einfacher Taktstrich", volta_number=2, volta_group_id=1
    )
    code = generate_lilypond(measures, "Test")
    assert code.count("\\repeat volta 2 {") == 1
    assert "\\repeat volta 2 {\n    }" not in code  # no empty body
    body = code.split("\\repeat volta 2 {")[1].split("}")[0]
    assert "r1" in body  # measure 2 is the body
    assert "\\volta 2 { \\break" in code


def test_no_volta_no_repeat_structure():
    measures = _measures([(0, 1)])
    measures[0]["end_barline"] = "Wiederholung Ende"
    code = generate_lilypond(measures, "Test")
    assert "\\repeat volta" not in code
    assert '\\bar ":|."' in code


# ── Content: notes, rests, pitches ───────────────────────────────────────


def test_notes_and_rests_with_pitches_in_bass_clef():
    measures = _measures([(0, 1)])
    symbols = [
        # stem up: head at the bottom of the box → bottom line + 0.5 → G2
        _note(0, 10, "Viertel Stiel oben", 4.0, -0.5),
        # stem down: head at the top of the box → 2nd line → B2
        _note(0, 30, "Viertel Stiel unten", 1.5, -2.0),
        _note(0, 50, "Halbe Pause", 4.5, -0.5, cat="rest", name="half_rest"),
    ]
    code, warnings = generate_lilypond_with_warnings(measures, "T", symbols=symbols)
    assert "g,4 b,4 r2" in code
    assert warnings == []
    assert "\\markErr" not in code.split("\\score")[1]


def test_key_signature_alters_pitches():
    measures = _measures([(0, 1)])
    symbols = [
        _note(0, 10, "Halbe Note Stiel oben", 4.5, 0.5),
        _note(0, 50, "Halbe Note Stiel oben", 4.5, 0.5),
    ]
    code = generate_lilypond(measures, "T", symbols=symbols, default_flats=2)
    assert "\\key bes \\major" in code
    assert "bes,2 bes,2" in code


def test_display_name_wins_over_contradicting_template_name():
    measures = _measures([(0, 1)])
    sym = _note(0, 10, "Halbe Note Stiel oben", 4.5, 0.5, name="halbe_note_steil_unten")
    code = generate_lilypond(
        measures, "T", symbols=[sym, _note(0, 50, "Halbe Pause", 4.5, -0.5, cat="rest")]
    )
    assert "b,2 r2" in code


def test_chord_merging_of_stacked_notes():
    measures = _measures([(0, 1)])
    symbols = [
        _note(0, 10, "Viertel Stiel oben", 4.0, -0.5),  # G2
        _note(0, 12, "Viertel Stiel unten", 3.5, 0.0),  # head at 3.0 → step 6 → F3
        _note(0, 60, "Halbe Pause", 4.5, -0.5, cat="rest"),
        _note(0, 80, "Viertelpause", 4.5, -0.5, cat="rest"),
    ]
    code = generate_lilypond(measures, "T", symbols=symbols)
    assert "<g, f>4 r2 r4" in code


def test_mismatched_measure_is_marked_and_reported():
    measures = _measures([(0, 1)])
    symbols = [_note(0, 10, "Viertel Stiel oben", 4.0, -0.5)]
    code, warnings = generate_lilypond_with_warnings(measures, "T", symbols=symbols)
    assert "\\set Timing.measureLength = #(ly:make-moment 1/4)" in code
    assert "\\markErr g,4 \\unmarkErr" in code
    assert len(warnings) == 1 and "1/4 statt 1/1" in warnings[0]


def test_clef_and_time_signature_from_symbols():
    measures = _measures([(0, 2)])
    symbols = [
        _mark(0, 2, "treble_clef", "Violinschlüssel", "clef"),
        _mark(0, 20, "time_3_4", "3/4-Takt", "time_sig"),
        _note(0, 40, "Halbe Note Stiel oben", 4.5, 0.5),
        _note(0, 70, "Viertel Stiel oben", 4.5, 0.5),
    ]
    code, warnings = generate_lilypond_with_warnings(measures, "T", symbols=symbols)
    assert "\\clef treble" in code and "\\clef bass" not in code
    assert "\\time 3/4" in code
    # bottom line in treble clef is E4 → head centre one line up → G4
    assert "g'2 g'4" in code
    assert warnings == ["Takt 2 (System 1, Takt 2): 0/1 statt 3/4"]


def test_key_signature_from_accidental_templates():
    measures = _measures([(0, 1)])
    symbols = [
        _mark(0, 2, "bass_clef", "Bassschlüssel", "clef"),
        _mark(0, 15, "3b", "3b", "accidental"),
        _note(0, 40, "Ganze Note", 2.5, 1.5),  # head centre 2.0 → step 4 → D3
    ]
    code = generate_lilypond(measures, "T", symbols=symbols)
    assert "\\key es \\major" in code
    assert "d1" in code


def test_in_measure_accidental_alters_next_note():
    measures = _measures([(0, 1)], width=400)
    symbols = [
        _mark(0, 0, "bass_clef", "Bassschlüssel", "clef", width=30),
        _mark(0, 200, "flat", "Be", "accidental"),
        _note(0, 210, "Halbe Note Stiel oben", 4.5, 0.5),  # B2 → Bes
        _note(0, 300, "Halbe Note Stiel oben", 4.5, 0.5),
    ]
    code = generate_lilypond(measures, "T", symbols=symbols)
    assert "bes,2 b,2" in code


# ── Marks: dynamics, hairpins, articulations, repeats ────────────────────


def test_dynamics_and_accents_attach_to_nearest_event():
    measures = _measures([(0, 1)])
    symbols = [
        _note(0, 10, "Halbe Note Stiel oben", 4.5, 0.5),
        _note(0, 60, "Halbe Note Stiel oben", 4.5, 0.5),
        _mark(0, 8, "f", "Forte", "dynamic"),
        _mark(0, 58, "accent", "Akzent", "ornament"),
    ]
    code = generate_lilypond(measures, "T", symbols=symbols)
    assert "b,2\\f b,2->" in code


def test_only_most_confident_dynamic_per_event():
    measures = _measures([(0, 1)])
    symbols = [
        _note(0, 10, "Ganze Note", 2.5, 1.5),
        _mark(0, 8, "p", "Piano", "dynamic", conf=0.6),
        _mark(0, 9, "mf", "Mezzoforte", "dynamic", conf=0.95),
    ]
    code = generate_lilypond(measures, "T", symbols=symbols)
    assert "d1\\mf" in code and "\\p" not in code.split("\\score")[1]


def test_hairpin_spans_events():
    measures = _measures([(0, 1)])
    symbols = [
        _note(0, 10, "Viertel Stiel oben", 4.0, -0.5),
        _note(0, 30, "Viertel Stiel oben", 4.0, -0.5),
        _note(0, 50, "Viertel Stiel oben", 4.0, -0.5),
        _note(0, 70, "Viertel Stiel oben", 4.0, -0.5),
        _mark(0, 12, "crescendo", "Crescendo", "dynamic", width=45),
    ]
    code = generate_lilypond(measures, "T", symbols=symbols)
    assert "g,4\\< g,4 g,4\\! g,4" in code


def test_hairpin_end_is_dropped_when_dynamic_present():
    measures = _measures([(0, 1)])
    symbols = [
        _note(0, 10, "Halbe Note Stiel oben", 4.5, 0.5),
        _note(0, 60, "Halbe Note Stiel oben", 4.5, 0.5),
        _mark(0, 12, "decrescendo", "Decrescendo", "dynamic", width=50),
        _mark(0, 62, "p", "Piano", "dynamic"),
    ]
    code = generate_lilypond(measures, "T", symbols=symbols)
    assert "b,2\\> b,2\\p" in code
    assert "\\!" not in code


def test_orphan_dynamic_uses_empty_chord():
    measures = _measures([(0, 1)])
    symbols = [_mark(0, 10, "ff", "Fortissimo", "dynamic")]
    code = generate_lilypond(measures, "T", symbols=symbols)
    # measure has no events → marked rest; dynamic still emitted on <>
    assert "\\ff" in code


def test_measure_repeat_sign_wraps_previous_measure():
    measures = _measures([(0, 3)])
    symbols = [
        _note(0, 10, "Viertel Stiel oben", 4.0, -0.5),
        _note(0, 40, "Viertel Stiel oben", 4.0, -0.5),
        _note(0, 70, "Halbe Pause", 4.5, -0.5, cat="rest"),
        _mark(0, 140, "takt_wiederholen", "Takt wiederholen", "other"),
        _mark(0, 240, "takt_wiederholen", "Takt wiederholen", "other"),
    ]
    code, warnings = generate_lilypond_with_warnings(measures, "T", symbols=symbols)
    assert "\\repeat percent 3 { g,4 g,4 r2 }" in code
    assert warnings == []


def test_measure_repeat_at_system_start_becomes_grey_copy():
    measures = _measures([(0, 1), (1, 1)])
    symbols = [
        _note(0, 10, "Ganze Note", 2.5, 1.5),
        _mark(1, 40, "takt_wiederholen", "Takt wiederholen", "other"),
    ]
    code = generate_lilypond(measures, "T", symbols=symbols)
    assert "\\break \\markCopy d1 \\unmarkCopy" in code


def test_multi_measure_rest():
    measures = _measures([(0, 2)])
    symbols = [
        _mark(0, 40, "zwei_takte_kompakt_pause", "2 Takte Pause Kompakt", "rest"),
        _note(0, 140, "Ganze Note", 2.5, 1.5),
    ]
    code, warnings = generate_lilypond_with_warnings(measures, "T", symbols=symbols)
    assert "R1*2" in code
    assert "\\compressEmptyMeasures" in code
    assert warnings == []


def test_section_mark_from_text_region():
    measures = _measures([(0, 2)])
    texts = [
        {"staff_index": 0, "x": 0, "y": 0, "width": 20, "height": 10, "text": "Trio"}
    ]
    code = generate_lilypond(measures, "T", text_regions=texts)
    assert '\\mark \\markup { \\bold \\large "Trio" }' in code


# ── Staff start, key-signature templates, head fractions, Trio ───────────


def test_key_signature_template_sets_key():
    measures = _measures([(0, 1)], width=400)
    symbols = [
        _mark(0, 0, "bass_clef", "Bassschlüssel", "clef", width=40),
        _mark(0, 50, "key_bes_major", "B-Dur", "key_sig", width=30),
        _note(0, 200, "Halbe Note Stiel oben", 4.5, 0.5),
        _note(0, 300, "Halbe Note Stiel oben", 4.5, 0.5),
    ]
    code = generate_lilypond(measures, "T", symbols=symbols)
    assert "\\key bes \\major" in code
    assert "bes,2 bes,2" in code


def test_user_named_key_template_is_understood():
    measures = _measures([(0, 1)], width=400)
    symbols = [
        _mark(0, 0, "bass_clef", "Bassschlüssel", "clef", width=40),
        _mark(0, 50, "3b", "Es-Dur", "key_sig", width=30),
        _note(0, 200, "Ganze Note", 2.5, 1.5),
    ]
    code = generate_lilypond(measures, "T", symbols=symbols)
    assert "\\key es \\major" in code


def test_staff_start_zone_drops_notes_inside_header():
    measures = _measures([(0, 1)], width=400)
    symbols = [
        _mark(0, 0, "bass_clef", "Bassschlüssel", "clef", width=40),
        _mark(0, 50, "key_bes_major", "B-Dur", "key_sig", width=30),
        _note(0, 55, "Viertel Stiel oben", 4.0, -0.5),  # a flat matched as a note
        _mark(0, 90, "time_cut", "Alla breve (₵)", "time_sig", width=25),
        _note(0, 200, "Halbe Note Stiel oben", 4.5, 0.5),
        _note(0, 300, "Halbe Note Stiel oben", 4.5, 0.5),
    ]
    code, warnings = generate_lilypond_with_warnings(measures, "T", symbols=symbols)
    assert "bes,2 bes,2" in code
    assert "g,4" not in code
    assert warnings == []


def test_trio_symbol_indents_system_with_label():
    measures = _measures([(0, 2), (1, 2)])
    symbols = [_mark(1, 0, "Trio", "Trio", "other", width=30)]
    code = generate_lilypond(measures, "T", symbols=symbols, trio_indent=8)
    assert 'pseudoIndent \\markuplist { \\fontsize #5 \\bold "Trio" } 8' in code
    assert "pseudoIndents =" in code  # preamble included
    assert '\\set Staff.instrumentName = ""' in code
    # pseudoIndent breaks the line itself
    assert (
        "\\break \\pseudoIndent" not in code
        and "\\break" not in code.split("\\score")[1]
    )


def test_trio_text_region_mid_line_falls_back_to_mark():
    measures = _measures([(0, 3)])
    texts = [
        {"staff_index": 0, "x": 150, "y": 0, "width": 20, "height": 10, "text": "TRIO"}
    ]
    code = generate_lilypond(measures, "T", text_regions=texts)
    assert '\\mark \\markup { \\bold \\large "Trio" }' in code
    assert "pseudoIndents =" not in code


def test_indented_system_becomes_trio_section():
    measures = _measures([(0, 3), (1, 3), (2, 3)], width=400)
    for m in measures:
        if m["staff_index"] == 2:
            m["x_start"] += 250
            m["x_end"] += 250
    code = generate_lilypond(measures, "T", trio_indent=8)
    body = code.split("\\score")[1]
    assert body.count("\\pseudoIndent") == 1
    assert '\\bold "Trio" } 8' in body


def test_courtesy_key_signature_applies_to_next_system():
    measures = _measures([(0, 2), (1, 2)], width=400)
    symbols = [
        _mark(0, 0, "bass_clef", "Bassschlüssel", "clef", width=40),
        _note(0, 100, "Ganze Note", 2.5, 1.5),
        _note(0, 500, "Ganze Note", 2.5, 1.5),
        _mark(0, 760, "key_es_major", "Es-Dur", "key_sig", width=30),  # line end
        _mark(1, 0, "bass_clef", "Bassschlüssel", "clef", width=40),
        _note(1, 100, "Ganze Note", 2.5, 1.5),
        _note(1, 500, "Ganze Note", 2.5, 1.5),
    ]
    code = generate_lilypond(measures, "T", symbols=symbols)
    body = code.split("\\score")[1]
    # key change is printed at the start of system 2, not inside system 1
    assert body.count("\\key es \\major") == 1
    first_line, second_line = body.split("\\break")
    assert "\\key es" not in first_line and "\\key es" in second_line
    assert first_line.count("d1") == 2  # system 1 still in C major
