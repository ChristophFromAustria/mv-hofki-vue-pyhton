"""Tolerant, word-wise search: fold(), search_words() and the list endpoints."""

import pytest

from mv_hofki.db.text_fold import fold
from mv_hofki.filters.text_search import search_words


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Müller", "muller"),
        ("MÜLLER", "muller"),
        ("Mueller", "muller"),
        ("Flügelhorn", "flugelhorn"),
        ("Straße", "strasse"),
        ("STRASSE", "strasse"),
        ("Böhm", "bohm"),
        ("Koenig", "konig"),
        ("Crème", "creme"),
        (None, None),
    ],
)
def test_fold(text, expected):
    assert fold(text) == expected


def test_search_words_are_folded_distinct_and_ordered():
    assert search_words("  Trompete  YAMAHA trompete ") == ["trompete", "yamaha"]
    assert search_words("") == []
    assert search_words(None) == []


async def _itype(client, label, short):
    return (
        await client.post(
            "/api/v1/instrument-types", json={"label": label, "label_short": short}
        )
    ).json()["id"]


async def _instrument(client, type_id, label, **extra):
    resp = await client.post(
        "/api/v1/items",
        json={"category": "instrument", "label": label, "instrument_type_id": type_id}
        | extra,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _labels(client, url):
    resp = await client.get(url)
    assert resp.status_code == 200, resp.text
    return sorted(i["label"] for i in resp.json()["items"])


async def test_item_search_is_word_wise_and_tolerant(client):
    tr = await _itype(client, "Trompete", "TR")
    fh = await _itype(client, "Flügelhorn", "FH")
    await _instrument(client, tr, "Trompete B", manufacturer="Yamaha")
    await _instrument(client, tr, "Trompete C", manufacturer="Bach")
    await _instrument(client, fh, "FLÜGELHORN", manufacturer="Yamaha")
    base = "/api/v1/items?category=instrument"

    assert await _labels(client, f"{base}&search=trompete yamaha") == ["Trompete B"]
    assert await _labels(client, f"{base}&search=yamaha trompete") == ["Trompete B"]
    assert await _labels(client, f"{base}&search=flügelhorn") == ["FLÜGELHORN"]
    assert await _labels(client, f"{base}&search=fluegelhorn") == ["FLÜGELHORN"]
    assert await _labels(client, f"{base}&search=trompete geige") == []
    # LIKE wildcards in the search text are taken literally.
    assert await _labels(client, f"{base}&search=%25") == []
    assert await _labels(client, f"{base}&search=_") == []


async def test_item_search_words_may_hit_different_fields_and_the_borrower(client):
    tr = await _itype(client, "Trompete", "TR")
    item = await _instrument(client, tr, "Trompete B", notes="mit Koffer")
    await _instrument(client, tr, "Trompete C")
    musician = (
        await client.post(
            "/api/v1/musicians", json={"first_name": "Jürgen", "last_name": "Müller"}
        )
    ).json()
    await client.post(
        "/api/v1/loans",
        json={
            "item_id": item["id"],
            "musician_id": musician["id"],
            "start_date": "2026-01-01",
        },
    )
    base = "/api/v1/items?category=instrument"
    assert await _labels(client, f"{base}&search=koffer mueller") == ["Trompete B"]
    assert await _labels(client, f"{base}&search=JUERGEN trompete") == ["Trompete B"]


async def test_musician_search_matches_first_and_last_name_words(client):
    for first, last, city in (
        ("Anna", "Maier", "Hofkirchen"),
        ("Anna", "Huber", "Linz"),
        ("Jörg", "Öller", "Linz"),
    ):
        await client.post(
            "/api/v1/musicians",
            json={"first_name": first, "last_name": last, "city": city},
        )

    async def names(q):
        resp = await client.get(f"/api/v1/musicians?search={q}&is_active=true")
        return sorted(m["last_name"] for m in resp.json()["items"])

    assert await names("anna maier") == ["Maier"]
    assert await names("maier anna") == ["Maier"]
    assert await names("anna") == ["Huber", "Maier"]
    assert await names("OELLER") == ["Öller"]
    assert await names("linz jörg") == ["Öller"]


async def test_an_existing_inventory_number_finds_only_that_item(client):
    tr = await _itype(client, "Trompete", "TR")
    tu = await _itype(client, "Tuba", "TU")
    for i in range(1, 7):
        await _instrument(client, tr, f"Trompete {i}", notes="Satz 6")
    await _instrument(client, tu, "Tuba 2")
    base = "/api/v1/items?category=instrument"

    # "tr 6" is TR-0006: not every trompete with a 6 in its notes.
    assert await _labels(client, f"{base}&search=tr 6") == ["Trompete 6"]
    # There is no TUBA-0002, so "Tuba 2" is searched as two words.
    assert await _labels(client, f"{base}&search=Tuba 2") == ["Tuba 2"]
    # TR-0009 doesn't exist: word search ("tr" and "9") finds nothing.
    assert await _labels(client, f"{base}&search=tr 9") == []
