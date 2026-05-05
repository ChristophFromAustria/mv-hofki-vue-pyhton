"""MusicXML generation from detected and verified symbols."""

from __future__ import annotations

import xml.etree.ElementTree as ET

DURATION_MAP = {
    "whole": ("whole", 16),
    "half": ("half", 8),
    "quarter": ("quarter", 4),
    "eighth": ("eighth", 2),
    "sixteenth": ("16th", 1),
}

CLEF_MAP = {
    "treble": ("G", "2"),
    "bass": ("F", "4"),
}


def generate_musicxml(
    *,
    part_name: str,
    clef: str,
    time_signature: str,
    key_signature: str,
    measures: list[list[dict]],
) -> str:
    """Generate a MusicXML string from structured measure data.

    Each measure is a list of dicts with keys:
    - type: "note" | "rest"
    - pitch: str (e.g. "C", "D") — only for notes
    - octave: int — only for notes
    - duration: str (e.g. "quarter", "half")
    - alter: int (optional, -1=flat, 1=sharp)
    """
    root = ET.Element("score-partwise", version="4.0")

    # Part list
    part_list = ET.SubElement(root, "part-list")
    score_part = ET.SubElement(part_list, "score-part", id="P1")
    pn = ET.SubElement(score_part, "part-name")
    pn.text = part_name

    # Part
    part = ET.SubElement(root, "part", id="P1")

    # Parse time signature
    beats, beat_type = (
        time_signature.split("/") if "/" in time_signature else ("4", "4")
    )

    for measure_num, measure_data in enumerate(measures, start=1):
        measure = ET.SubElement(part, "measure", number=str(measure_num))

        # Attributes on first measure
        if measure_num == 1:
            attributes = ET.SubElement(measure, "attributes")
            div = ET.SubElement(attributes, "divisions")
            div.text = "4"

            key = ET.SubElement(attributes, "key")
            fifths = ET.SubElement(key, "fifths")
            fifths.text = str(key_signature)

            time_el = ET.SubElement(attributes, "time")
            beats_el = ET.SubElement(time_el, "beats")
            beats_el.text = beats
            beat_type_el = ET.SubElement(time_el, "beat-type")
            beat_type_el.text = beat_type

            clef_sign, clef_line = CLEF_MAP.get(clef, ("G", "2"))
            clef_el = ET.SubElement(attributes, "clef")
            sign_el = ET.SubElement(clef_el, "sign")
            sign_el.text = clef_sign
            line_el = ET.SubElement(clef_el, "line")
            line_el.text = clef_line

        # Notes and rests
        for item in measure_data:
            note_el = ET.SubElement(measure, "note")

            if item["type"] == "rest":
                ET.SubElement(note_el, "rest")
            else:
                pitch_el = ET.SubElement(note_el, "pitch")
                step = ET.SubElement(pitch_el, "step")
                step.text = item["pitch"]
                if "alter" in item and item["alter"] != 0:
                    alter = ET.SubElement(pitch_el, "alter")
                    alter.text = str(item["alter"])
                octave = ET.SubElement(pitch_el, "octave")
                octave.text = str(item["octave"])

            dur_name, dur_val = DURATION_MAP.get(item["duration"], ("quarter", 4))
            duration = ET.SubElement(note_el, "duration")
            duration.text = str(dur_val)
            type_el = ET.SubElement(note_el, "type")
            type_el.text = dur_name

    # If no measures, add an empty first measure with attributes
    if not measures:
        measure = ET.SubElement(part, "measure", number="1")
        attributes = ET.SubElement(measure, "attributes")
        div = ET.SubElement(attributes, "divisions")
        div.text = "4"

        key = ET.SubElement(attributes, "key")
        fifths = ET.SubElement(key, "fifths")
        fifths.text = str(key_signature)

        time_el = ET.SubElement(attributes, "time")
        beats_el = ET.SubElement(time_el, "beats")
        beats_el.text = beats
        beat_type_el = ET.SubElement(time_el, "beat-type")
        beat_type_el.text = beat_type

        clef_sign, clef_line = CLEF_MAP.get(clef, ("G", "2"))
        clef_el = ET.SubElement(attributes, "clef")
        sign_el = ET.SubElement(clef_el, "sign")
        sign_el.text = clef_sign
        line_el = ET.SubElement(clef_el, "line")
        line_el.text = clef_line

    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
