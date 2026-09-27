"""ListFilter base: column mapping, custom handlers, search, sorting, paging."""

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from mv_hofki.filters.base import ListFilter, PageParams, paginate
from mv_hofki.models.musician import Musician


class _Filter(ListFilter):
    last_name: str | None = None
    city__ilike: str | None = None
    town: str | None = None
    is_extern: bool | None = None
    id__in: list[int] | None = None
    initial: str | None = None

    class Constants(ListFilter.Constants):
        model = Musician
        search_model_fields = ["first_name", "last_name"]
        columns = {"town": Musician.city}
        sort_fields = {
            "last_name": [Musician.last_name],
            "city": [Musician.city],
            "name": [Musician.last_name, Musician.first_name],
        }
        default_sort = ["last_name"]

    def filter_initial(self, query, value):
        return query.where(Musician.last_name.like(f"{value}%"))


@pytest.fixture
async def people(db_session):
    rows = [
        Musician(first_name="Anna", last_name="Maier", city="Linz", is_extern=False),
        Musician(first_name="Berta", last_name="Maier", city=None, is_extern=True),
        Musician(first_name="Carl", last_name="Huber", city="Wels", is_extern=False),
        Musician(first_name="Dora", last_name="Aigner", city="Linz", is_extern=False),
    ]
    db_session.add_all(rows)
    await db_session.commit()
    return rows


async def _run(db_session, flt):
    result = await db_session.execute(flt.sort(flt.filter(select(Musician))))
    return [m.first_name for m in result.scalars()]


async def test_plain_field_and_default_sort(db_session, people):
    assert await _run(db_session, _Filter(last_name="Maier")) == ["Anna", "Berta"]
    assert await _run(db_session, _Filter()) == ["Dora", "Carl", "Anna", "Berta"]


async def test_mapped_column_and_ilike_adds_wildcards(db_session, people):
    assert await _run(db_session, _Filter(town="Wels")) == ["Carl"]
    assert await _run(db_session, _Filter(city__ilike="IN")) == ["Dora", "Anna"]


async def test_in_operator_and_bool(db_session, people):
    ids = [people[0].id, people[2].id]
    assert await _run(db_session, _Filter(id__in=ids)) == ["Carl", "Anna"]
    assert await _run(db_session, _Filter(is_extern=True)) == ["Berta"]


async def test_custom_handler(db_session, people):
    assert await _run(db_session, _Filter(initial="Hu")) == ["Carl"]


async def test_search_over_model_fields_ignores_blank(db_session, people):
    assert await _run(db_session, _Filter(search="dor")) == ["Dora"]
    assert len(await _run(db_session, _Filter(search="   "))) == 4


async def test_sort_desc_nulls_last_and_id_tiebreak(db_session, people):
    # city desc: Wels, Linz(Anna id1), Linz(Dora id4), NULL last
    assert await _run(db_session, _Filter(order_by=["-city"])) == [
        "Carl",
        "Anna",
        "Dora",
        "Berta",
    ]
    assert await _run(db_session, _Filter(order_by=["city"])) == [
        "Anna",
        "Dora",
        "Carl",
        "Berta",
    ]


async def test_multi_column_sort_key(db_session, people):
    assert await _run(db_session, _Filter(order_by=["-name"])) == [
        "Berta",
        "Anna",
        "Carl",
        "Dora",
    ]


def test_order_by_accepts_comma_string():
    assert _Filter(order_by="-city,last_name").order_by == ["-city", "last_name"]


def test_unknown_sort_key_rejected():
    with pytest.raises(ValidationError) as exc:
        _Filter(order_by=["first_name"])
    assert "kein gültiger Sortierschlüssel" in str(exc.value)


def test_duplicate_sort_key_rejected():
    with pytest.raises(ValidationError):
        _Filter(order_by=["city", "-city"])


async def test_paginate_counts_filtered_and_slices(db_session, people):
    flt = _Filter(city__ilike="linz")
    query = flt.sort(flt.filter(select(Musician)))
    rows, total = await paginate(db_session, query, PageParams(limit=1, offset=1))
    assert total == 2
    assert [m.first_name for m in rows] == ["Anna"]
