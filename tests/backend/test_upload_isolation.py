"""Tests must never touch the real upload folders under data/."""

import io
from pathlib import Path

from mv_hofki.core.config import settings
from mv_hofki.services import inventory_item, item_image, item_invoice

REAL_UPLOADS = Path(settings.PROJECT_ROOT) / "data" / "uploads"


def test_upload_roots_point_outside_data():
    for root in (
        item_image.UPLOAD_DIR,
        item_invoice.UPLOAD_DIR,
        inventory_item.UPLOADS_ROOT,
    ):
        assert REAL_UPLOADS not in Path(root).parents and Path(root) != REAL_UPLOADS


async def test_deleting_an_item_leaves_real_uploads_alone(client, tmp_path):
    itype = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Tuba", "label_short": "TU"}
        )
    ).json()
    item = (
        await client.post(
            "/api/v1/items",
            json={
                "category": "instrument",
                "label": "T",
                "instrument_type_id": itype["id"],
            },
        )
    ).json()
    await client.post(
        f"/api/v1/items/{item['id']}/images",
        files={"file": ("x.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
    )
    before = sorted(p.name for p in (REAL_UPLOADS / "images").glob("*"))

    await client.delete(f"/api/v1/items/{item['id']}")

    assert sorted(p.name for p in (REAL_UPLOADS / "images").glob("*")) == before
