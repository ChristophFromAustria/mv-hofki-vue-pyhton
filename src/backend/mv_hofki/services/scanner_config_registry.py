"""Scanner config registry — single source of truth for all config keys.

The ``SCANNER_CONFIG_REGISTRY`` list defines every recognised config entry with
its default value, UI metadata, and validation constraints.

``sync_config_registry`` reconciles the database with the registry on every app
startup: new keys are inserted, removed keys are deleted, and metadata for
existing keys is refreshed while preserving user-modified *values*.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scanner_config_entry import ScannerConfigEntry

# ── Registry ─────────────────────────────────────────────────────────

SCANNER_CONFIG_REGISTRY: list[dict] = [
    # ═══════════════════════════════════════════════════════════════════
    #  Bildvorverarbeitung
    # ═══════════════════════════════════════════════════════════════════
    #  ── Bildvorverarbeitung \ Binarisierung ─────────────────────────
    {
        "key": "adaptive_threshold_block_size",
        "default_value": "15",
        "type": "number",
        "label": "Adaptiver Schwellwert Blockgröße",
        "group_path": "Bildvorverarbeitung\\Binarisierung",
        "min": 3.0,
        "max": 99.0,
        "step": 2.0,
        "sort_order": 10,
    },
    {
        "key": "adaptive_threshold_c",
        "default_value": "10",
        "type": "number",
        "label": "Adaptiver Schwellwert Konstante",
        "group_path": "Bildvorverarbeitung\\Binarisierung",
        "min": 0.0,
        "max": 50.0,
        "step": 1.0,
        "sort_order": 20,
    },
    {
        "key": "morphology_kernel_size",
        "default_value": "2",
        "type": "number",
        "label": "Morphologie Kernel-Größe",
        "group_path": "Bildvorverarbeitung\\Binarisierung",
        "min": 1.0,
        "max": 10.0,
        "step": 1.0,
        "sort_order": 30,
    },
    #  ── Bildvorverarbeitung \ Entzerrung ────────────────────────────
    {
        "key": "deskew_method",
        "default_value": "projection",
        "type": "select",
        "label": "Entzerrungsmethode",
        "group_path": "Bildvorverarbeitung\\Entzerrung",
        "options": [
            {"value": "none", "label": "Keine"},
            {"value": "hough", "label": "Hough-Transformation"},
            {"value": "projection", "label": "Projektionsprofil"},
        ],
        "sort_order": 10,
    },
    #  ── Bildvorverarbeitung \ Krümmungskorrektur ────────────────────
    {
        "key": "dewarp_enabled",
        "default_value": "false",
        "type": "toggle",
        "label": "Krümmungskorrektur",
        "group_path": "Bildvorverarbeitung\\Krümmungskorrektur",
        "sort_order": 10,
    },
    {
        "key": "dewarp_smoothing",
        "default_value": "50",
        "type": "number",
        "label": "Glättung (px)",
        "group_path": "Bildvorverarbeitung\\Krümmungskorrektur",
        "min": 5.0,
        "max": 200.0,
        "step": 5.0,
        "sort_order": 20,
    },
    #  ── Bildvorverarbeitung \ Scanbereich ───────────────────────────
    {
        "key": "staff_margin_top",
        "default_value": "4.0",
        "type": "number",
        "label": "Scanbereich oben (\u00d7 Linienabstand)",
        "group_path": "Bildvorverarbeitung\\Scanbereich",
        "min": 1.0,
        "max": 20.0,
        "step": 0.5,
        "sort_order": 10,
    },
    {
        "key": "staff_margin_bottom",
        "default_value": "4.0",
        "type": "number",
        "label": "Scanbereich unten (\u00d7 Linienabstand)",
        "group_path": "Bildvorverarbeitung\\Scanbereich",
        "min": 1.0,
        "max": 20.0,
        "step": 0.5,
        "sort_order": 20,
    },
    # ═══════════════════════════════════════════════════════════════════
    #  Symbolerkennung
    # ═══════════════════════════════════════════════════════════════════
    {
        "key": "confidence_threshold",
        "default_value": "0.6",
        "type": "number",
        "label": "Konfidenz-Schwellwert",
        "group_path": "Symbolerkennung",
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
        "sort_order": 10,
    },
    {
        "key": "matching_method",
        "default_value": "TM_CCOEFF_NORMED",
        "type": "select",
        "label": "Matching-Methode",
        "group_path": "Symbolerkennung",
        "options": [
            {
                "value": "TM_CCOEFF_NORMED",
                "label": "Kreuzkorrelationskoeffizient (Standard)",
            },
            {"value": "TM_CCORR_NORMED", "label": "Kreuzkorrelation"},
            {"value": "TM_SQDIFF_NORMED", "label": "Quadratische Differenz"},
        ],
        "sort_order": 20,
    },
    {
        "key": "auto_verify_confidence",
        "default_value": "0.85",
        "type": "number",
        "label": "Auto-Verifizierung ab",
        "group_path": "Symbolerkennung",
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
        "sort_order": 30,
    },
    #  ── Symbolerkennung \ Multi-Scale ───────────────────────────────
    {
        "key": "multi_scale_enabled",
        "default_value": "false",
        "type": "toggle",
        "label": "Multi-Scale-Suche",
        "group_path": "Symbolerkennung\\Multi-Scale",
        "sort_order": 10,
    },
    {
        "key": "multi_scale_range",
        "default_value": "0.05",
        "type": "number",
        "label": "Suchbereich (+/-)",
        "group_path": "Symbolerkennung\\Multi-Scale",
        "min": 0.01,
        "max": 0.5,
        "step": 0.01,
        "sort_order": 20,
    },
    {
        "key": "multi_scale_steps",
        "default_value": "3",
        "type": "number",
        "label": "Stufen",
        "group_path": "Symbolerkennung\\Multi-Scale",
        "min": 1.0,
        "max": 20.0,
        "step": 1.0,
        "sort_order": 30,
    },
    #  ── Symbolerkennung \ Kanten-Matching ───────────────────────────
    {
        "key": "edge_matching_enabled",
        "default_value": "false",
        "type": "toggle",
        "label": "Kanten-Matching",
        "group_path": "Symbolerkennung\\Kanten-Matching",
        "sort_order": 10,
    },
    {
        "key": "canny_low",
        "default_value": "50",
        "type": "number",
        "label": "Canny unterer Schwellwert",
        "group_path": "Symbolerkennung\\Kanten-Matching",
        "min": 0.0,
        "max": 500.0,
        "step": 10.0,
        "sort_order": 20,
    },
    {
        "key": "canny_high",
        "default_value": "150",
        "type": "number",
        "label": "Canny oberer Schwellwert",
        "group_path": "Symbolerkennung\\Kanten-Matching",
        "min": 0.0,
        "max": 500.0,
        "step": 10.0,
        "sort_order": 30,
    },
    #  ── Symbolerkennung \ Maskiertes Matching ───────────────────────
    {
        "key": "masked_matching_enabled",
        "default_value": "false",
        "type": "toggle",
        "label": "Maskiertes Matching",
        "group_path": "Symbolerkennung\\Maskiertes Matching",
        "sort_order": 10,
    },
    {
        "key": "mask_threshold",
        "default_value": "200",
        "type": "number",
        "label": "Masken-Schwellwert",
        "group_path": "Symbolerkennung\\Maskiertes Matching",
        "min": 0.0,
        "max": 255.0,
        "step": 5.0,
        "sort_order": 20,
    },
    #  ── Symbolerkennung \ Notenlinien-Entfernung ────────────────────
    {
        "key": "staff_removal_before_matching",
        "default_value": "false",
        "type": "toggle",
        "label": "Notenlinien vor Matching entfernen",
        "group_path": "Symbolerkennung\\Notenlinien-Entfernung",
        "sort_order": 10,
    },
    {
        "key": "staff_removal_thickness_pct",
        "default_value": "100",
        "type": "number",
        "label": "Liniendicke-Korrektur (%)",
        "group_path": "Symbolerkennung\\Notenlinien-Entfernung",
        "min": 50.0,
        "max": 300.0,
        "step": 10.0,
        "sort_order": 20,
    },
    {
        "key": "staff_removal_symbol_padding",
        "default_value": "0",
        "type": "number",
        "label": "Symbol-Abstand (px)",
        "group_path": "Symbolerkennung\\Notenlinien-Entfernung",
        "min": 0.0,
        "max": 50.0,
        "step": 1.0,
        "sort_order": 30,
    },
    # ═══════════════════════════════════════════════════════════════════
    #  Nachbearbeitung
    # ═══════════════════════════════════════════════════════════════════
    #  ── Nachbearbeitung \ NMS ───────────────────────────────────────
    {
        "key": "nms_iou_threshold",
        "default_value": "0.3",
        "type": "number",
        "label": "NMS IoU-Schwellwert",
        "group_path": "Nachbearbeitung\\NMS",
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
        "sort_order": 10,
    },
    {
        "key": "nms_method",
        "default_value": "standard",
        "type": "select",
        "label": "NMS-Methode",
        "group_path": "Nachbearbeitung\\NMS",
        "options": [
            {"value": "standard", "label": "Standard (IoU)"},
            {"value": "dilate", "label": "Dilate (Proximity)"},
        ],
        "sort_order": 20,
    },
    #  ── Nachbearbeitung \ Text-Maskierung ───────────────────────────
    {
        "key": "text_masking_min_confidence",
        "default_value": "30",
        "type": "number",
        "label": "Minimale Konfidenz",
        "group_path": "Nachbearbeitung\\Text-Maskierung",
        "min": 0.0,
        "max": 100.0,
        "step": 5.0,
        "sort_order": 10,
    },
    #  ── Nachbearbeitung \ Keil-Erkennung ────────────────────────────
    {
        "key": "hairpin_min_width_factor",
        "default_value": "3.0",
        "type": "number",
        "label": "Min. Linien-Breite (\u00d7 Linienabstand)",
        "group_path": "Nachbearbeitung\\Keil-Erkennung",
        "min": 0.5,
        "max": 10.0,
        "step": 0.5,
        "sort_order": 10,
    },
    {
        "key": "hairpin_min_hitbox_width_factor",
        "default_value": "3.0",
        "type": "number",
        "label": "Min. Hitbox-Breite (\u00d7 Linienabstand)",
        "group_path": "Nachbearbeitung\\Keil-Erkennung",
        "min": 0.5,
        "max": 10.0,
        "step": 0.5,
        "sort_order": 20,
    },
    {
        "key": "hairpin_min_confidence",
        "default_value": "0.3",
        "type": "number",
        "label": "Min. Konfidenz",
        "group_path": "Nachbearbeitung\\Keil-Erkennung",
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
        "sort_order": 30,
    },
    #  ── Nachbearbeitung \ Volta-Erkennung ───────────────────────────
    {
        "key": "volta_min_overlap_pct",
        "default_value": "0.3",
        "type": "number",
        "label": "Min. Überlappung Takt/Klammer (%)",
        "group_path": "Nachbearbeitung\\Volta-Erkennung",
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
        "sort_order": 10,
    },
    # ═══════════════════════════════════════════════════════════════════
    #  LilyPond Layout
    # ═══════════════════════════════════════════════════════════════════
    {
        "key": "ly_top_margin",
        "default_value": "1",
        "type": "number",
        "label": "Oberer Rand (mm)",
        "group_path": "LilyPond Layout",
        "min": 0.0,
        "max": 50.0,
        "step": 1.0,
        "sort_order": 10,
    },
    {
        "key": "ly_bottom_margin",
        "default_value": "4",
        "type": "number",
        "label": "Unterer Rand (mm)",
        "group_path": "LilyPond Layout",
        "min": 0.0,
        "max": 50.0,
        "step": 1.0,
        "sort_order": 20,
    },
    {
        "key": "ly_left_margin",
        "default_value": "16",
        "type": "number",
        "label": "Linker Rand (mm)",
        "group_path": "LilyPond Layout",
        "min": 0.0,
        "max": 50.0,
        "step": 1.0,
        "sort_order": 30,
    },
    {
        "key": "ly_right_margin",
        "default_value": "16",
        "type": "number",
        "label": "Rechter Rand (mm)",
        "group_path": "LilyPond Layout",
        "min": 0.0,
        "max": 50.0,
        "step": 1.0,
        "sort_order": 40,
    },
    {
        "key": "ly_staff_size",
        "default_value": "17",
        "type": "number",
        "label": "Notensystem-Größe",
        "group_path": "LilyPond Layout",
        "min": 8.0,
        "max": 30.0,
        "step": 1.0,
        "sort_order": 50,
    },
    {
        "key": "ly_system_distance",
        "default_value": "6",
        "type": "number",
        "label": "System-Abstand",
        "group_path": "LilyPond Layout",
        "min": 1.0,
        "max": 20.0,
        "step": 1.0,
        "sort_order": 60,
    },
    {
        "key": "ly_system_padding",
        "default_value": "0.6",
        "type": "number",
        "label": "System-Padding",
        "group_path": "LilyPond Layout",
        "min": 0.0,
        "max": 5.0,
        "step": 0.1,
        "sort_order": 70,
    },
    # ═══════════════════════════════════════════════════════════════════
    #  LilyPond Inhalt
    # ═══════════════════════════════════════════════════════════════════
    {
        "key": "ly_default_clef",
        "default_value": "bass",
        "type": "select",
        "label": "Standard-Schlüssel (wenn nicht erkannt)",
        "group_path": "LilyPond Inhalt",
        "options": [
            {"value": "bass", "label": "Bassschlüssel"},
            {"value": "treble", "label": "Violinschlüssel"},
        ],
        "sort_order": 10,
    },
    {
        "key": "ly_default_time",
        "default_value": "2/2",
        "type": "select",
        "label": "Standard-Taktart (wenn nicht erkannt)",
        "group_path": "LilyPond Inhalt",
        "options": [
            {"value": "2/2", "label": "2/2 (Alla breve)"},
            {"value": "4/4", "label": "4/4"},
            {"value": "2/4", "label": "2/4"},
            {"value": "3/4", "label": "3/4"},
            {"value": "6/8", "label": "6/8"},
        ],
        "sort_order": 20,
    },
    {
        "key": "ly_default_flats",
        "default_value": "0",
        "type": "number",
        "label": "Standard-Tonart: Anzahl Bs (negativ = Kreuze)",
        "group_path": "LilyPond Inhalt",
        "min": -7.0,
        "max": 7.0,
        "step": 1.0,
        "sort_order": 30,
    },
    {
        "key": "ly_trio_indent",
        "default_value": "8",
        "type": "number",
        "label": "Einrückung der Trio-Zeile (Staff-Einheiten)",
        "group_path": "LilyPond Inhalt",
        "min": 0.0,
        "max": 30.0,
        "step": 1.0,
        "sort_order": 35,
    },
    {
        "key": "ly_mark_errors",
        "default_value": "true",
        "type": "toggle",
        "label": "Takte mit falscher Taktfüllung rot markieren",
        "group_path": "LilyPond Inhalt",
        "sort_order": 40,
    },
]


# ── Value casting helpers ────────────────────────────────────────────


def _cast_value(
    raw: str,
    entry_type: str,
    *,
    step: float | None = None,
    min_val: float | None = None,
    max_val: float | None = None,
) -> Any:
    """Cast a string value from the DB to a native Python type.

    * ``"toggle"`` -> ``bool``
    * ``"number"`` -> ``int`` when *step* >= 1 **and** *min*/*max* are
      both integers (or ``None``), otherwise ``float``
    * ``"select"`` -> ``str``
    """
    if entry_type == "toggle":
        return raw.lower() == "true"

    if entry_type == "number":
        # Determine whether the number should be int or float.
        use_int = (
            step is not None
            and step >= 1
            and (min_val is None or float(min_val) == int(min_val))
            and (max_val is None or float(max_val) == int(max_val))
        )
        return int(float(raw)) if use_int else float(raw)

    # "select" and anything else → str
    return str(raw)


def _serialize_value(value: Any, entry_type: str) -> str:
    """Convert a native Python value back to its string representation.

    * ``"toggle"`` -> ``"true"`` / ``"false"``
    * else -> ``str(value)``
    """
    if entry_type == "toggle":
        return "true" if value else "false"
    return str(value)


# ── Sync function ────────────────────────────────────────────────────


async def sync_config_registry(session: AsyncSession) -> None:
    """Reconcile the ``scanner_config_entry`` table with the registry.

    1. Load all existing DB entries.
    2. For each registry entry:
       - **exists** -> update metadata columns (NOT ``value``).
       - **new** -> insert with ``value = default_value``.
    3. Delete orphan rows whose key is no longer in the registry.
    4. Flush (caller decides when to commit).
    """
    # 1. Load existing entries keyed by their primary key.
    result = await session.execute(select(ScannerConfigEntry))
    existing: dict[str, ScannerConfigEntry] = {
        row.key: row for row in result.scalars().all()
    }

    registry_keys: set[str] = set()

    for entry_def in SCANNER_CONFIG_REGISTRY:
        key = entry_def["key"]
        registry_keys.add(key)

        # Serialise options list to JSON string if present.
        options_json: str | None = None
        if "options" in entry_def and entry_def["options"] is not None:
            options_json = json.dumps(entry_def["options"])

        if key in existing:
            # 2a. Update metadata, preserve user value.
            row = existing[key]
            row.default_value = entry_def["default_value"]
            row.type = entry_def["type"]
            row.label = entry_def["label"]
            row.group_path = entry_def.get("group_path")
            row.min = entry_def.get("min")
            row.max = entry_def.get("max")
            row.step = entry_def.get("step")
            row.options = options_json
            row.sort_order = entry_def["sort_order"]
        else:
            # 2b. New entry — insert with default value.
            new_row = ScannerConfigEntry(
                key=key,
                value=entry_def["default_value"],
                default_value=entry_def["default_value"],
                type=entry_def["type"],
                label=entry_def["label"],
                group_path=entry_def.get("group_path"),
                min=entry_def.get("min"),
                max=entry_def.get("max"),
                step=entry_def.get("step"),
                options=options_json,
                sort_order=entry_def["sort_order"],
            )
            session.add(new_row)

    # 3. Delete orphans.
    orphan_keys = set(existing.keys()) - registry_keys
    if orphan_keys:
        await session.execute(
            delete(ScannerConfigEntry).where(ScannerConfigEntry.key.in_(orphan_keys))
        )

    # 4. Flush (not commit).
    await session.flush()
