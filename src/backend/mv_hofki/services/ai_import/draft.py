"""Build the editable draft from the per-page extractions.

The draft is what the user corrects in the review editor. It is a plain JSON
document (stored on the session) so the frontend can edit it freely and the
backend can re-validate it on every save.

Structure (version 1)::

    {
      "version": 1,
      "instruments": [ {"key": "p0-i0", "page_id": 7, "page_index": 0,
                        ...ExtractedInstrument fields...} ],
      "photos":      [ {"key": "p0-f0", "page_id": 7, "page_index": 0,
                        "row_key": "p0-i0" | null,
                        ...ExtractedPhoto fields...} ]
    }
"""

from __future__ import annotations

import json
import re
from typing import Any

DRAFT_VERSION = 1


def _norm_nr(value: Any) -> str | None:
    """'I-012' / '12.' / ' 12 ' -> '12' so photo captions match table rows."""
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits.lstrip("0") or ("0" if digits else None)


def build_draft(pages: list[Any]) -> dict[str, Any]:
    """``pages`` are ImportPage rows (only those with ``extraction_json``)."""
    instruments: list[dict[str, Any]] = []
    photos: list[dict[str, Any]] = []

    for page in pages:
        if not page.extraction_json:
            continue
        extraction = json.loads(page.extraction_json)
        for i, inst in enumerate(extraction.get("instruments", [])):
            instruments.append(
                {
                    "key": f"p{page.page_index}-i{i}",
                    "page_id": page.id,
                    "page_index": page.page_index,
                    **inst,
                }
            )
        for i, photo in enumerate(extraction.get("photos", [])):
            photos.append(
                {
                    "key": f"p{page.page_index}-f{i}",
                    "page_id": page.id,
                    "page_index": page.page_index,
                    "row_key": None,
                    **photo,
                }
            )

    # Suggest a row for each photo via the inventory number in its caption:
    # same page first, then anywhere in the session.
    by_nr: dict[str, list[dict[str, Any]]] = {}
    for row in instruments:
        nr = _norm_nr(row.get("inventory_nr"))
        if nr:
            by_nr.setdefault(nr, []).append(row)
    for photo in photos:
        nr = _norm_nr(photo.get("inventory_nr"))
        candidates = by_nr.get(nr or "", [])
        if not candidates:
            continue
        same_page = [r for r in candidates if r["page_index"] == photo["page_index"]]
        photo["row_key"] = (same_page or candidates)[0]["key"]

    return {"version": DRAFT_VERSION, "instruments": instruments, "photos": photos}
