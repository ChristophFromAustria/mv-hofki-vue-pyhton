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
    assert "c1 | c1 | c1 |" in code
    assert "\\break" in code
    assert "c1 | c1 |" in code


def test_single_system():
    measures = _measures([(0, 4)])
    code = generate_lilypond(measures, "Test")
    assert "\\break" not in code
    assert "c1 | c1 | c1 | c1 |" in code


def test_empty_measures():
    code = generate_lilypond([], "Empty")
    assert '\\version "2.24.0"' in code
    assert "\\clef bass" in code
