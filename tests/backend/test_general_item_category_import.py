"""Applying a reviewed category proposal CSV to general items."""

from sqlalchemy import select

from mv_hofki.models.general_item_category import GeneralItemCategory
from mv_hofki.services.general_item_category_import import (
    ProposalRow,
    apply_assignments,
    read_proposal,
)


async def _general(client, label):
    resp = await client.post(
        "/api/v1/items", json={"category": "general_item", "label": label}
    )
    assert resp.status_code == 201
    return resp.json()


def test_read_proposal_handles_bom_and_blank_categories(tmp_path):
    csv = tmp_path / "p.csv"
    csv.write_text(
        "﻿display_nr;label;storage_location;categories\n"
        "A-001;Schaukasten;Foyer;Möbel | Deko |\n"
        "A-002;Holzspieße;Archiv;\n",
        encoding="utf-8",
    )
    assert read_proposal(csv) == [
        ProposalRow("A-001", ["Möbel", "Deko"]),
        ProposalRow("A-002", []),
    ]


async def test_apply_creates_categories_and_assigns(client, db_session):
    a1 = await _general(client, "Schaukasten")
    a2 = await _general(client, "Gläser")
    rows = [
        ProposalRow("A-001", ["Möbel", "Deko"]),
        ProposalRow("a-2", ["gastro"]),
        ProposalRow("A-099", ["Deko"]),
    ]
    report = await apply_assignments(db_session, rows)
    assert sorted(report.created_categories) == ["Deko", "Möbel", "gastro"]
    assert report.updated_items == 2
    assert report.unknown_numbers == ["A-099"]

    d1 = (await client.get(f"/api/v1/items/{a1['id']}")).json()
    d2 = (await client.get(f"/api/v1/items/{a2['id']}")).json()
    assert [c["label"] for c in d1["categories"]] == ["Deko", "Möbel"]
    assert [c["label"] for c in d2["categories"]] == ["gastro"]


async def test_apply_reuses_existing_category_ignoring_case(client, db_session):
    await client.post("/api/v1/general-item-categories", json={"label": "Küche"})
    await _general(client, "Topf")
    report = await apply_assignments(db_session, [ProposalRow("A-001", ["KÜCHE"])])
    assert report.created_categories == []
    labels = (await db_session.execute(select(GeneralItemCategory.label))).scalars()
    assert list(labels) == ["Küche"]


async def test_apply_is_idempotent_and_empty_list_clears(client, db_session):
    item = await _general(client, "Stehtisch")
    rows = [ProposalRow("A-001", ["Möbel"])]
    await apply_assignments(db_session, rows)
    again = await apply_assignments(db_session, rows)
    assert again.created_categories == []
    detail = (await client.get(f"/api/v1/items/{item['id']}")).json()
    assert [c["label"] for c in detail["categories"]] == ["Möbel"]

    await apply_assignments(db_session, [ProposalRow("A-001", [])])
    detail = (await client.get(f"/api/v1/items/{item['id']}")).json()
    assert detail["categories"] == []
