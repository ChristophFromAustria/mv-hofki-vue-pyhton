"""Per-page extraction of raw inventory data from a document image.

The schema is deliberately "raw": everything is captured as it is written on
the document (instrument type as text, musician as a name, dates and prices
as strings). Mapping onto instrument types, musicians and inventory numbers
in the database is a separate, deterministic step that runs without the model.
"""

from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .llm_client import LlmClient
from .pages import PageImage

# ---------------------------------------------------------------------------
# Pydantic models (what the rest of the app consumes)
# ---------------------------------------------------------------------------

Confidence = Literal["high", "medium", "low"]
PageKind = Literal["inventory_table", "photo_sheet", "mixed", "other"]
# [x1, y1, x2, y2]. The model is asked for Qwen's native normalised coordinates
# (0..1000 relative to image width/height); :func:`to_pixel_boxes` converts them
# to pixel coordinates of the rendered page before anything else sees them.
BBox = list[int]
NORMALISED_RANGE = 1000


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ExtractedLoan(_Lenient):
    musician_name: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    remarks: str | None = None


class ExtractedInstrument(_Lenient):
    inventory_nr: str | None = None
    instrument_type: str | None = None
    label: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    serial_nr: str | None = None
    construction_year: int | None = None
    acquisition_date: str | None = None
    acquisition_cost: str | None = None
    distributor: str | None = None
    container: str | None = None
    particularities: str | None = None
    owner: str | None = None
    loan: ExtractedLoan | None = None
    source_text: str = ""
    confidence: Confidence = "medium"
    bbox_2d: BBox | None = None


class ExtractedPhoto(_Lenient):
    caption: str | None = None
    inventory_nr: str | None = None
    bbox_2d: BBox = Field(min_length=4, max_length=4)


class PageExtraction(_Lenient):
    page_kind: PageKind = "other"
    instruments: list[ExtractedInstrument] = Field(default_factory=list)
    photos: list[ExtractedPhoto] = Field(default_factory=list)
    remarks: str | None = None


def _scale_box(box: BBox, width: int, height: int) -> BBox:
    x1, y1, x2, y2 = box
    fx = width / NORMALISED_RANGE
    fy = height / NORMALISED_RANGE
    xa, xb = sorted((round(x1 * fx), round(x2 * fx)))
    ya, yb = sorted((round(y1 * fy), round(y2 * fy)))
    clamp_x = lambda v: min(width, max(0, v))  # noqa: E731
    clamp_y = lambda v: min(height, max(0, v))  # noqa: E731
    return [clamp_x(xa), clamp_y(ya), clamp_x(xb), clamp_y(yb)]


def to_pixel_boxes(
    extraction: PageExtraction, width: int, height: int
) -> PageExtraction:
    """Return a copy with every bbox_2d converted from 0..1000 to pixels."""
    out = extraction.model_copy(deep=True)
    for inst in out.instruments:
        if inst.bbox_2d is not None:
            inst.bbox_2d = _scale_box(inst.bbox_2d, width, height)
    for photo in out.photos:
        photo.bbox_2d = _scale_box(photo.bbox_2d, width, height)
    return out


class PageResult(BaseModel):
    """One page's extraction together with its provenance."""

    source_name: str
    page_index: int
    width: int
    height: int
    extraction: PageExtraction  # bbox_2d already in pixel coordinates
    raw: dict[str, Any] = Field(default_factory=dict)  # bbox_2d as the model gave it
    usage: dict[str, Any] = Field(default_factory=dict)
    duration_seconds: float | None = None


# ---------------------------------------------------------------------------
# JSON schema handed to the model (kept in sync with the models above)
# ---------------------------------------------------------------------------


def _nullable(t: str) -> dict[str, Any]:
    return {"type": [t, "null"]}


_BBOX_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {"type": "integer"},
    "minItems": 4,
    "maxItems": 4,
}

_LOAN_PROPERTIES: dict[str, Any] = {
    "musician_name": _nullable("string"),
    "start_date": _nullable("string"),
    "end_date": _nullable("string"),
    "remarks": _nullable("string"),
}

_INSTRUMENT_PROPERTIES: dict[str, Any] = {
    "inventory_nr": _nullable("string"),
    "instrument_type": _nullable("string"),
    "label": _nullable("string"),
    "manufacturer": _nullable("string"),
    "model": _nullable("string"),
    "serial_nr": _nullable("string"),
    "construction_year": _nullable("integer"),
    "acquisition_date": _nullable("string"),
    "acquisition_cost": _nullable("string"),
    "distributor": _nullable("string"),
    "container": _nullable("string"),
    "particularities": _nullable("string"),
    "owner": _nullable("string"),
    "loan": {
        "anyOf": [
            {
                "type": "object",
                "properties": _LOAN_PROPERTIES,
                "required": list(_LOAN_PROPERTIES),
                "additionalProperties": False,
            },
            {"type": "null"},
        ]
    },
    "source_text": {"type": "string"},
    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    "bbox_2d": {"anyOf": [_BBOX_SCHEMA, {"type": "null"}]},
}

_PHOTO_PROPERTIES: dict[str, Any] = {
    "caption": _nullable("string"),
    "inventory_nr": _nullable("string"),
    "bbox_2d": _BBOX_SCHEMA,
}

EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "page_kind": {
            "type": "string",
            "enum": ["inventory_table", "photo_sheet", "mixed", "other"],
        },
        "instruments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": _INSTRUMENT_PROPERTIES,
                "required": list(_INSTRUMENT_PROPERTIES),
                "additionalProperties": False,
            },
        },
        "photos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": _PHOTO_PROPERTIES,
                "required": list(_PHOTO_PROPERTIES),
                "additionalProperties": False,
            },
        },
        "remarks": _nullable("string"),
    },
    "required": ["page_kind", "instruments", "photos", "remarks"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "Du bist ein sorgfältiger Archivar eines österreichischen Blasmusikvereins. "
    "Du liest gescannte Inventardokumente (gedruckt und handschriftlich) und "
    "überträgst deren Inhalt exakt in JSON. Du erfindest nichts: Was nicht "
    "lesbar oder nicht vorhanden ist, wird null. Du antwortest ausschließlich "
    "mit JSON gemäß dem vorgegebenen Schema."
)


def build_prompt(width: int, height: int) -> str:
    return f"""Das Bild ist eine Seite aus dem Instrumenten-Inventar des Musikvereins
(Breite {width} px, Höhe {height} px). Alle Koordinaten (bbox_2d) gibst du als
[x1, y1, x2, y2] auf einer Skala von 0 bis 1000 an, relativ zur Bildbreite bzw.
Bildhöhe (0 = linker/oberer Rand, 1000 = rechter/unterer Rand).

Aufgabe:
1. Bestimme page_kind: "inventory_table" (Liste/Tabelle/Karteikarte mit
   Instrumentdaten), "photo_sheet" (Seite mit abgedruckten Fotos von
   Instrumenten), "mixed" (beides) oder "other".
2. Extrahiere jedes Instrument, das auf der Seite beschrieben ist, als eigenen
   Eintrag in "instruments". Pro Instrument:
   - inventory_nr: Inventarnummer genau wie geschrieben (z.B. "12", "I-012",
     "12a"), sonst null.
   - instrument_type: Instrumentenart wie geschrieben (z.B. "Trompete Bb",
     "Flügelhorn", "Tenorhorn", "Klarinette", "Schlagzeug"), sonst null.
   - label: freie Bezeichnung/Überschrift des Eintrags, falls vorhanden.
   - manufacturer, model, serial_nr, distributor (Händler), container
     (Koffer/Etui), particularities (Besonderheiten, Zustand, Zubehör),
     owner (Eigentümer, falls angegeben).
   - construction_year: Baujahr als ganze Zahl, sonst null.
   - acquisition_date und acquisition_cost: Anschaffungsdatum und -preis genau
     wie geschrieben (Zeichenkette, inkl. Währung wie "ATS" oder "€"), keine
     Umrechnung.
   - loan: Wenn das Instrument an eine Person ausgegeben/verliehen ist:
     musician_name (Name wie geschrieben), start_date und end_date wie
     geschrieben, remarks. Sonst null.
   - source_text: der Originaltext der Zeile bzw. des Eintrags, so wie er
     dasteht.
   - confidence: "high" bei klar gedrucktem Text, "medium" bei gut lesbarer
     Handschrift, "low" wenn du raten musstest.
   - bbox_2d: Position des Eintrags auf der Seite als [x1, y1, x2, y2]
     (Skala 0-1000), sonst null.
3. Erfasse jedes abgedruckte Foto eines Instruments in "photos" mit bbox_2d
   [x1, y1, x2, y2] (Skala 0-1000, eng um das Foto, ohne Beschriftung), caption
   (Beschriftung wie geschrieben) und inventory_nr, falls aus der Beschriftung
   erkennbar. Logos, Stempel und Dekorationen sind keine Fotos.
4. remarks: Hinweise zu Unlesbarem, Durchgestrichenem oder Mehrdeutigem,
   sonst null.

Regeln: Nichts ergänzen, nichts korrigieren, nichts übersetzen. Zahlen und
Namen exakt übernehmen, auch wenn sie ungewöhnlich wirken. Leere Tabellenzeilen
ignorieren."""


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


async def extract_page(client: LlmClient, page: PageImage) -> PageResult:
    t0 = time.monotonic()
    raw, usage = await client.chat_json(
        prompt=build_prompt(page.width, page.height),
        images=[page.png],
        schema=EXTRACTION_SCHEMA,
        schema_name="inventory_page",
        system=SYSTEM_PROMPT,
    )
    return PageResult(
        source_name=page.source_name,
        page_index=page.index,
        width=page.width,
        height=page.height,
        extraction=to_pixel_boxes(
            PageExtraction.model_validate(raw), page.width, page.height
        ),
        raw=raw,
        usage=usage,
        duration_seconds=round(time.monotonic() - t0, 2),
    )


async def extract_pages(client: LlmClient, pages: list[PageImage]) -> list[PageResult]:
    """Extract pages one after another (vLLM allows 2 concurrent sequences;
    keep one free for other users)."""
    return [await extract_page(client, page) for page in pages]
