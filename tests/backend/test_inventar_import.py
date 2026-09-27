"""Import of the digitised paper inventory: parsing and planning rules."""

import json
from datetime import date

from mv_hofki.services.inventar_import import (
    CLUB_OWNER,
    STORAGE_MS,
    build_plan,
    map_type,
    parse_amount,
    parse_date,
    parse_inventory_nr,
)

CODES = {"Tuba": "TU", "Klarinette in B": "KL", "Querflöte": "FL", "Horn": "WH"}


def test_parse_date_fills_missing_parts_with_first():
    assert parse_date("2003") == (date(2003, 1, 1), False)
    assert parse_date("2023-09") == (date(2023, 9, 1), False)
    assert parse_date("1996-06-10") == (date(1996, 6, 10), True)
    assert parse_date("~2017") == (date(2017, 1, 1), False)
    assert parse_date("2012/13") == (date(2012, 1, 1), False)
    assert parse_date(None) == (None, False)
    assert parse_date("?") == (None, False)


def test_parse_inventory_nr_and_amount():
    assert parse_inventory_nr("TU 1") == ("TU", 1)
    assert parse_inventory_nr("Po 1") == ("PO", 1)
    assert parse_inventory_nr("KL-012") == ("KL", 12)
    assert parse_inventory_nr(None) is None
    assert parse_amount(2000) == 2000.0
    assert parse_amount("25.500") == 25500.0
    assert parse_amount("2.940,00 €") == 2940.0
    assert parse_amount("?") is None


def test_map_type_prefers_specific_names():
    assert map_type("Bassklarinette") == "Bassklarinette"
    assert map_type("Es-Klarinette") == "Klarinette in Es"
    assert map_type("Klarinette in B") == "Klarinette in B"
    assert map_type("Piccolo") == "Querflöte"
    assert map_type("Waldhorn in F (Doppelhorn)") == "Horn"
    assert map_type("Tenorhorn/Bariton in B") == "Tenorhorn"
    assert map_type("Notenständer") is None


def _write(root, folder, data):
    (root / folder).mkdir(parents=True, exist_ok=True)
    (root / folder / "zusammenfuehrung.json").write_text(json.dumps(data))


def _people(root, people, excluded=()):
    (root / "_gesamt").mkdir(parents=True, exist_ok=True)
    (root / "_gesamt" / "musiker.json").write_text(
        json.dumps({"musiker": people, "ausgeschlossen": list(excluded)})
    )


def _person(gid, first, last, *refs):
    return {
        "id": gid,
        "vorname": first,
        "nachname": last,
        "vorkommen": list(refs),
        "status": "sicher",
        "telefone_alle": [],
    }


def test_paper_numbers_kept_and_gaps_filled_per_code(tmp_path):
    _people(tmp_path, [])
    _write(
        tmp_path,
        "Tuba",
        {
            "musiker": [],
            "leihen": [],
            "instrumente": [
                {
                    "id": "TU 2",
                    "inventar_nr": "TU 2",
                    "typ": "Tuba in B",
                    "eigentum": "musikverein",
                },
                {"id": "TU-X01", "typ": "Tuba in F", "eigentum": "musikverein"},
            ],
        },
    )
    _write(
        tmp_path,
        "Klarinette",
        {
            "musiker": [],
            "leihen": [],
            "instrumente": [
                {"id": "KL-01", "typ": "Klarinette in B", "eigentum": "musikverein"},
            ],
        },
    )

    plan = build_plan(tmp_path, CODES, date(2026, 9, 27))

    nrs = {i.key: i.display_nr for i in plan.items}
    assert nrs == {
        "Tuba/TU 2": "TU-002",
        "Tuba/TU-X01": "TU-003",
        "Klarinette/KL-01": "KL-001",
    }
    tu2 = next(i for i in plan.items if i.key == "Tuba/TU 2")
    assert "Inventarnummer auf Papier: TU 2" in tu2.notes


def test_private_owner_and_musikschule_storage(tmp_path):
    (tmp_path / "_gesamt" / "roh").mkdir(parents=True)
    (tmp_path / "_gesamt" / "roh" / "inventar_liste_p01.json").write_text(
        json.dumps(
            {
                "tables": [
                    {
                        "zeilen": [
                            {"zellen": {"Inventarnr.": "WH 5", "Name": "MS Archiv"}}
                        ]
                    }
                ]
            }
        )
    )
    _people(tmp_path, [_person("G1", "Lea", "König", "Querfloete/M1")])
    _write(
        tmp_path,
        "Querfloete",
        {
            "musiker": [{"id": "M1", "vorname": "Lea", "nachname": "König"}],
            "leihen": [],
            "instrumente": [
                {
                    "id": "QF-X01",
                    "typ": "Querflöte",
                    "eigentum": "privat",
                    "privat_eigentuemer": "M1",
                },
            ],
        },
    )
    _write(
        tmp_path,
        "Waldhorn",
        {
            "musiker": [],
            "leihen": [],
            "instrumente": [
                {
                    "id": "WH 5",
                    "inventar_nr": "WH 5",
                    "typ": "Waldhorn in F",
                    "eigentum": "musikverein",
                },
            ],
        },
    )

    plan = build_plan(tmp_path, CODES, date(2026, 9, 27))

    by_key = {i.key: i for i in plan.items}
    assert by_key["Querfloete/QF-X01"].owner == "Lea König"
    assert by_key["Waldhorn/WH 5"].owner == CLUB_OWNER
    assert by_key["Waldhorn/WH 5"].storage_location == STORAGE_MS


def _loan_folder(tmp_path, loans, inst_extra=None):
    people = [
        _person("G1", "Anna", "A", "Tuba/M1"),
        _person("G2", "Bert", "B", "Tuba/M2"),
    ]
    _people(tmp_path, people, [{"vorkommen": "Tuba/M9", "grund": "Musikschule"}])
    _write(
        tmp_path,
        "Tuba",
        {
            "musiker": [{"id": "M1"}, {"id": "M2"}, {"id": "M9"}],
            "leihen": [{"instrument": "TU 1", "quellen": [], **x} for x in loans],
            "instrumente": [
                {
                    "id": "TU 1",
                    "inventar_nr": "TU 1",
                    "typ": "Tuba",
                    "eigentum": "musikverein",
                    **(inst_extra or {}),
                }
            ],
        },
    )
    return build_plan(tmp_path, CODES, date(2026, 9, 27))


def test_open_loan_is_closed_by_the_next_one(tmp_path):
    plan = _loan_folder(
        tmp_path,
        [
            {"musiker": "M1", "von": "2001", "bis": None, "status": "sicher"},
            {"musiker": "M2", "von": "2019", "bis": None, "status": "sicher"},
        ],
    )
    first, second = plan.loans
    assert (first.start, first.end) == (date(2001, 1, 1), date(2019, 1, 1))
    assert (second.start, second.end) == (date(2019, 1, 1), None)


def test_uncertain_loan_does_not_replace_confirmed_active_loan(tmp_path):
    plan = _loan_folder(
        tmp_path,
        [
            {"musiker": "M1", "von": "2023-09", "bis": None, "status": "sicher"},
            {"musiker": "M2", "von": "~2023-09", "bis": None, "status": "offen"},
        ],
    )
    assert [(x.musician_key, x.end) for x in plan.loans] == [("G1", None)]
    assert any("unsichere Leihe" in s["text"] for s in plan.skipped)


def test_non_person_and_archived_items_get_no_active_loan(tmp_path):
    plan = _loan_folder(
        tmp_path,
        [
            {"musiker": "M1", "von": "1990", "bis": "1998", "status": "sicher"},
            {"musiker": "M9", "von": None, "bis": None, "status": "offen"},
            {"musiker": "M2", "von": "2010", "bis": None, "status": "sicher"},
        ],
        {"archiv": True},
    )
    assert [(x.musician_key, x.end) for x in plan.loans] == [("G1", date(1998, 1, 1))]


def test_unknown_start_of_current_loan_uses_import_date(tmp_path):
    plan = _loan_folder(
        tmp_path, [{"musiker": "M1", "von": None, "bis": None, "status": "sicher"}]
    )
    assert plan.loans[0].start == date(2026, 9, 27)
    assert "Leihbeginn unbekannt" in plan.items[0].notes


def test_items_marked_not_to_import_are_skipped_with_their_loans(tmp_path):
    plan = _loan_folder(
        tmp_path,
        [{"musiker": "M1", "von": "2001", "bis": None, "status": "sicher"}],
        {"import": False, "import_grund": "verkauft"},
    )
    assert plan.items == [] and plan.loans == []
    assert {"wo": "Tuba/TU 1", "text": "verkauft"} in plan.skipped


def test_room_list_objects_get_category_prefix_quantity_and_owner(tmp_path):
    _people(tmp_path, [])
    _write(
        tmp_path,
        "Allgemeines_Inventar",
        {
            "musiker": [],
            "leihen": [],
            "objekte": [
                {
                    "id": "AI-001",
                    "kategorie": "general_item",
                    "bezeichnung": "Kühlschrank",
                    "menge": 3,
                    "eigentuemer": "MV Hofkirchen",
                    "lagerort": "Stüberl/Küche",
                    "quelle": "Allgemeines_Inventar/equipment#standort12/z2",
                },
                {
                    "id": "AI-002",
                    "kategorie": "clothing",
                    "bezeichnung": "Mantel (braun)",
                    "menge": 1,
                    "kleidungstyp": "Mantel",
                    "eigentuemer": "MV Hofkirchen",
                },
                {
                    "id": "AI-003",
                    "kategorie": "general_item",
                    "bezeichnung": "Stehleiter",
                    "eigentuemer": "Landesmusikschule",
                },
                {
                    "id": "AI-004",
                    "kategorie": "instrument",
                    "bezeichnung": "Helikon",
                    "instrumententyp": "Tuba",
                },
            ],
            "nicht_uebernommen": [
                {
                    "quelle": "x#standort2/z4",
                    "wie_geschrieben": "Volle Getränkekisten",
                    "grund": "Verbrauchsmaterial",
                },
            ],
        },
    )

    plan = build_plan(tmp_path, CODES, date(2026, 9, 27))

    by_key = {i.key: i for i in plan.items}
    fridge = by_key["Allgemeines_Inventar/AI-001"]
    assert (fridge.display_nr, fridge.quantity, fridge.storage_location) == (
        "A-001",
        3,
        "Stüberl/Küche",
    )
    coat = by_key["Allgemeines_Inventar/AI-002"]
    assert (coat.category, coat.display_nr, coat.clothing_type) == (
        "clothing",
        "K-001",
        "Mantel",
    )
    assert by_key["Allgemeines_Inventar/AI-003"].owner == "Landesmusikschule"
    assert by_key["Allgemeines_Inventar/AI-004"].display_nr == "TU-001"
    assert any("Getränkekisten" in s["text"] for s in plan.skipped)


async def test_adding_a_folder_numbers_after_existing_and_is_repeatable(
    tmp_path, db_session
):
    from mv_hofki.models.inventory_item import InventoryItem
    from mv_hofki.services.inventar_import import apply_plan, restrict_to_folder

    db_session.add(
        InventoryItem(
            category="general_item",
            number_prefix="A",
            inventory_nr=5,
            label="Alt",
            owner="MV Hofkirchen",
        )
    )
    await db_session.commit()
    _people(tmp_path, [])
    _write(
        tmp_path,
        "Allgemeines_Inventar",
        {
            "musiker": [],
            "leihen": [],
            "objekte": [
                {
                    "id": "AI-001",
                    "kategorie": "general_item",
                    "bezeichnung": "Stehleiter",
                    "quelle": "Allgemeines_Inventar/equipment#standort4/z4",
                },
            ],
        },
    )

    plan = await restrict_to_folder(
        db_session, build_plan(tmp_path, CODES), "Allgemeines_Inventar"
    )
    assert [i.display_nr for i in plan.items] == ["A-006"]
    await apply_plan(db_session, plan, tmp_path / "uploads")
    await db_session.commit()

    again = await restrict_to_folder(
        db_session, build_plan(tmp_path, CODES), "Allgemeines_Inventar"
    )
    assert again.items == []
    assert any("bereits importiert" in s["text"] for s in again.skipped)
