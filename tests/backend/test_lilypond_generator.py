"""Tests for Lilypond code generation from measure data."""

from mv_hofki.services.lilypond_generator import generate_lilypond


def _measures(layout):
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
                    "x_start": 0,
                    "x_end": 100,
                }
            )
            global_num += 1
    return result


def test_basic_structure():
    measures = _measures([(0, 2)])
    code = generate_lilypond(measures, "Test Stück")
    assert '\\version "2.24.0"' in code
    assert "a5" in code
    assert 'title = "Test Stück"' in code
    assert "\\clef bass" in code
    assert "\\time 2/2" in code


def test_measures_per_system():
    measures = _measures([(0, 3), (1, 2)])
    code = generate_lilypond(measures, "Test")
    assert "c1 c1 c1" in code
    assert "\\break" in code


def test_single_system():
    measures = _measures([(0, 4)])
    code = generate_lilypond(measures, "Test")
    assert "\\break" not in code
    assert "c1 c1 c1 c1" in code


def test_barline_types():
    """Special barline types should produce \\bar commands."""
    measures = [
        {
            "staff_index": 0,
            "measure_number_in_staff": 1,
            "global_measure_number": 1,
            "x_start": 0,
            "x_end": 100,
            "end_barline": "Wiederholung Anfang",
        },
        {
            "staff_index": 0,
            "measure_number_in_staff": 2,
            "global_measure_number": 2,
            "x_start": 100,
            "x_end": 200,
            "end_barline": "Wiederholung Ende",
        },
        {
            "staff_index": 0,
            "measure_number_in_staff": 3,
            "global_measure_number": 3,
            "x_start": 200,
            "x_end": 300,
            "end_barline": "Schlusstaktstrich",
        },
    ]
    code = generate_lilypond(measures, "Test")
    assert '\\bar ".|:"' in code
    assert '\\bar ":|."' in code
    assert '\\bar "|."' in code


def test_simple_barline_no_bar_command():
    """Simple barlines (Einfacher Taktstrich) should not produce \\bar commands."""
    measures = [
        {
            "staff_index": 0,
            "measure_number_in_staff": 1,
            "global_measure_number": 1,
            "x_start": 0,
            "x_end": 100,
            "end_barline": "Einfacher Taktstrich",
        },
        {
            "staff_index": 0,
            "measure_number_in_staff": 2,
            "global_measure_number": 2,
            "x_start": 100,
            "x_end": 200,
            "end_barline": None,
        },
    ]
    code = generate_lilypond(measures, "Test")
    assert "\\bar" not in code


def test_empty_measures():
    code = generate_lilypond([], "Empty")
    assert '\\version "2.24.0"' in code
    assert "\\clef bass" in code


def test_volta_brackets_generate_repeat_alternative():
    """Measures with volta numbers should produce \\repeat volta / \\alternative."""
    measures = [
        {
            "staff_index": 0,
            "measure_number_in_staff": 1,
            "global_measure_number": 1,
            "x_start": 0,
            "x_end": 100,
            "end_barline": "Einfacher Taktstrich",
        },
        {
            "staff_index": 0,
            "measure_number_in_staff": 2,
            "global_measure_number": 2,
            "x_start": 100,
            "x_end": 200,
            "end_barline": "Einfacher Taktstrich",
        },
        {
            "staff_index": 0,
            "measure_number_in_staff": 3,
            "global_measure_number": 3,
            "x_start": 200,
            "x_end": 300,
            "end_barline": "Wiederholung Ende",
            "volta_number": 1,
            "volta_group_id": 1,
        },
        {
            "staff_index": 0,
            "measure_number_in_staff": 4,
            "global_measure_number": 4,
            "x_start": 300,
            "x_end": 400,
            "end_barline": None,
            "volta_number": 2,
            "volta_group_id": 1,
        },
    ]
    code = generate_lilypond(measures, "Test")
    assert "\\repeat volta 2 {" in code
    assert "\\alternative {" in code
    assert "\\volta 1 {" in code
    assert "\\volta 2 {" in code


def test_no_volta_no_repeat_structure():
    """Measures without volta numbers should not produce repeat structures."""
    measures = [
        {
            "staff_index": 0,
            "measure_number_in_staff": 1,
            "global_measure_number": 1,
            "x_start": 0,
            "x_end": 100,
            "end_barline": "Wiederholung Ende",
        },
    ]
    code = generate_lilypond(measures, "Test")
    assert "\\repeat volta" not in code
