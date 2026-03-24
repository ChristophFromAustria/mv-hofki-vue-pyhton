"""Tests for MusicXML export."""

import xml.etree.ElementTree as ET

from mv_hofki.services.scanner.export.musicxml import generate_musicxml


def test_generate_empty_part():
    xml_str = generate_musicxml(
        part_name="1. Flügelhorn",
        clef="treble",
        time_signature="4/4",
        key_signature="0",
        measures=[],
    )
    root = ET.fromstring(xml_str)
    assert root.tag == "score-partwise"
    part_name_el = root.find(".//part-name")
    assert part_name_el is not None
    assert part_name_el.text == "1. Flügelhorn"


def test_generate_single_measure():
    measures = [
        [
            {"type": "note", "pitch": "C", "octave": 4, "duration": "quarter"},
            {"type": "note", "pitch": "D", "octave": 4, "duration": "quarter"},
            {"type": "note", "pitch": "E", "octave": 4, "duration": "quarter"},
            {"type": "note", "pitch": "F", "octave": 4, "duration": "quarter"},
        ]
    ]
    xml_str = generate_musicxml(
        part_name="Test",
        clef="treble",
        time_signature="4/4",
        key_signature="0",
        measures=measures,
    )
    root = ET.fromstring(xml_str)
    notes = root.findall(".//note")
    assert len(notes) == 4

    # Check first note is C4
    pitch = notes[0].find("pitch")
    assert pitch.find("step").text == "C"
    assert pitch.find("octave").text == "4"


def test_generate_with_rests():
    measures = [
        [
            {"type": "note", "pitch": "C", "octave": 4, "duration": "quarter"},
            {"type": "rest", "duration": "quarter"},
            {"type": "note", "pitch": "E", "octave": 4, "duration": "half"},
        ]
    ]
    xml_str = generate_musicxml(
        part_name="Test",
        clef="treble",
        time_signature="4/4",
        key_signature="0",
        measures=measures,
    )
    root = ET.fromstring(xml_str)
    rests = root.findall(".//rest")
    assert len(rests) == 1


def test_generate_bass_clef():
    xml_str = generate_musicxml(
        part_name="Posaune",
        clef="bass",
        time_signature="4/4",
        key_signature="0",
        measures=[],
    )
    root = ET.fromstring(xml_str)
    sign = root.find(".//sign")
    assert sign.text == "F"
    line = root.find(".//clef/line")
    assert line.text == "4"
