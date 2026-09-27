"""fetch_page: grouping, counts, NULL group, multi-valued rows, paging."""

import pytest
from pydantic import ValidationError
from sqlalchemy import case, select

from mv_hofki.filters.base import GroupSpec, ListFilter, PageParams, fetch_page
from mv_hofki.models.musician import Musician
from mv_hofki.models.register import Register, musician_registers


def _join_registers(query):
    return query.outerjoin(
        musician_registers, musician_registers.c.musician_id == Musician.id
    ).outerjoin(Register, Register.id == musician_registers.c.register_id)


class _Filter(ListFilter):
    class Constants(ListFilter.Constants):
        model = Musician
        sort_fields = {"first_name": [Musician.first_name]}
        default_sort = ["first_name"]
        group_fields = {
            "city": GroupSpec(
                key=Musician.city, label=Musician.city, empty_label="Ohne Ort"
            ),
            "register": GroupSpec(
                key=Register.id,
                label=Register.label,
                order=Register.sort_order,
                empty_label="Ohne Register",
                join=_join_registers,
                multi=True,
            ),
            "status": GroupSpec(
                key=case((Musician.is_active, "aktiv"), else_="inaktiv"),
                label=case((Musician.is_active, "Aktiv"), else_="Inaktiv"),
                order=case((Musician.is_active, 0), else_=1),
                empty_label="—",
            ),
        }


@pytest.fixture
async def people(db_session):
    brass = Register(label="Blech", sort_order=2)
    wood = Register(label="Holz", sort_order=1)
    db_session.add_all([brass, wood])
    await db_session.flush()
    anna = Musician(first_name="Anna", last_name="A", city="Wels", is_active=True)
    berta = Musician(first_name="Berta", last_name="B", city="Linz", is_active=False)
    carl = Musician(first_name="Carl", last_name="C", city=None, is_active=True)
    dora = Musician(first_name="Dora", last_name="D", city="Linz", is_active=True)
    anna.registers = [brass, wood]
    berta.registers = [brass]
    db_session.add_all([anna, berta, carl, dora])
    await db_session.commit()
    return {"brass": brass.id, "wood": wood.id}


def _names(page):
    return [m.first_name for m in page.rows]


async def test_ungrouped_is_plain_paging(db_session, people):
    page = await fetch_page(
        db_session, _Filter(), select(Musician), PageParams(limit=50, offset=0)
    )
    assert _names(page) == ["Anna", "Berta", "Carl", "Dora"]
    assert page.total == page.item_total == 4
    assert page.groups is None and page.row_groups is None


async def test_single_valued_groups_with_null_last(db_session, people):
    page = await fetch_page(
        db_session,
        _Filter(group_by="city"),
        select(Musician),
        PageParams(limit=50, offset=0),
    )
    assert _names(page) == ["Berta", "Dora", "Anna", "Carl"]
    assert page.row_groups == [
        ("Linz", "Linz"),
        ("Linz", "Linz"),
        ("Wels", "Wels"),
        ("", "Ohne Ort"),
    ]
    assert page.groups == [
        {"key": "Linz", "label": "Linz", "count": 2},
        {"key": "Wels", "label": "Wels", "count": 1},
        {"key": "", "label": "Ohne Ort", "count": 1},
    ]
    assert page.total == page.item_total == 4


async def test_multi_valued_rows_repeat_and_order_by_group_order(db_session, people):
    page = await fetch_page(
        db_session,
        _Filter(group_by="register"),
        select(Musician),
        PageParams(limit=50, offset=0),
    )
    # Holz (sort_order 1) before Blech (2), then no register
    assert [(m.first_name, g[1]) for m, g in zip(page.rows, page.row_groups)] == [
        ("Anna", "Holz"),
        ("Anna", "Blech"),
        ("Berta", "Blech"),
        ("Carl", "Ohne Register"),
        ("Dora", "Ohne Register"),
    ]
    assert page.total == 5
    assert page.item_total == 4
    assert page.groups == [
        {"key": str(people["wood"]), "label": "Holz", "count": 1},
        {"key": str(people["brass"]), "label": "Blech", "count": 2},
        {"key": "", "label": "Ohne Register", "count": 2},
    ]


async def test_multi_valued_paging_has_no_gaps(db_session, people):
    seen = []
    for offset in range(5):
        page = await fetch_page(
            db_session,
            _Filter(group_by="register"),
            select(Musician),
            PageParams(limit=1, offset=offset),
        )
        assert page.total == 5
        seen += [(m.id, g[0]) for m, g in zip(page.rows, page.row_groups)]
    assert len(seen) == 5 and len(set(seen)) == 5


async def test_case_expression_group(db_session, people):
    page = await fetch_page(
        db_session,
        _Filter(group_by="status"),
        select(Musician),
        PageParams(limit=50, offset=0),
    )
    assert [(m.first_name, g[1]) for m, g in zip(page.rows, page.row_groups)] == [
        ("Anna", "Aktiv"),
        ("Carl", "Aktiv"),
        ("Dora", "Aktiv"),
        ("Berta", "Inaktiv"),
    ]
    assert page.groups == [
        {"key": "aktiv", "label": "Aktiv", "count": 3},
        {"key": "inaktiv", "label": "Inaktiv", "count": 1},
    ]


def test_unknown_group_rejected():
    with pytest.raises(ValidationError) as exc:
        _Filter(group_by="nope")
    assert "keine gültige Gruppierung" in str(exc.value)


def test_empty_group_by_means_none():
    assert _Filter(group_by="").group_by is None
