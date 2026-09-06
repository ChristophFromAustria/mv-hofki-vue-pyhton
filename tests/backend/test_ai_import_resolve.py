"""Draft resolution against a database snapshot (pure Python)."""

from datetime import date

import pytest

from mv_hofki.services.ai_import.resolve import (
    Context,
    CurrencyRef,
    ExistingItem,
    MusicianRef,
    TypeRef,
    match_instrument_type,
    match_musician,
    parse_amount,
    parse_date,
    split_name,
    validate_draft,
)

TYPES = [
    TypeRef(1, "Trompete"),
    TypeRef(2, "Flügelhorn"),
    TypeRef(3, "Klarinette in B"),
    TypeRef(4, "Klarinette in Es"),
    TypeRef(5, "Tuba"),
    TypeRef(6, "Schlagwerk"),
    TypeRef(7, "Tenorhorn"),
]


def ctx(**kw) -> Context:
    base = dict(
        instrument_types=TYPES,
        musicians=[
            MusicianRef(10, "Anna", "Hofer"),
            MusicianRef(11, "Josef", "Berger"),
        ],
        currencies=[CurrencyRef(1, "Euro", "€"), CurrencyRef(2, "Schilling", "ATS")],
        instruments=[
            ExistingItem(100, 12, "Trompete", "YTR-4335 A"),
            ExistingItem(101, 3, "Tuba"),
        ],
        today=date(2026, 9, 6),
    )
    base.update(kw)
    return Context(**base)


def row(**kw):
    base = {
        "key": "p0-i0",
        "inventory_nr": "20",
        "instrument_type": "Trompete Bb",
        "manufacturer": "Yamaha",
        "serial_nr": "S-1",
        "construction_year": 2009,
        "loan": None,
    }
    base.update(kw)
    return base


def issues(v, field=None, level=None):
    out = v["rows"][0]["issues"]
    if field:
        out = [i for i in out if i["field"] == field]
    if level:
        out = [i for i in out if i["level"] == level]
    return out


# --- matching helpers ------------------------------------------------------------


@pytest.mark.parametrize(
    "text,label,min_score",
    [
        ("Trompete", "Trompete", 1.0),
        ("Trompete Bb", "Trompete", 1.0),
        ("B-Trompete", "Trompete", 1.0),
        ("Flügelhorn", "Flügelhorn", 1.0),
        ("Fluegelhorn", "Flügelhorn", 1.0),
        ("Klarinette Bb", "Klarinette in B", 1.0),
        ("Es-Klarinette", "Klarinette in Es", 1.0),
        ("Klarinette", "Klarinette in B", 1.0),
        ("Basstuba", "Tuba", 1.0),
        ("Schlagzeug", "Schlagwerk", 1.0),
        ("große Trommel", "Schlagwerk", 1.0),
        ("Trompete Yamaha", "Trompete", 0.9),
        ("Trompette", "Trompete", 0.85),
    ],
)
def test_match_instrument_type(text, label, min_score):
    ref, score = match_instrument_type(text, TYPES)
    assert ref is not None and ref.label == label, (text, ref, score)
    assert score >= min_score


def test_match_instrument_type_unknown_scores_low():
    ref, score = match_instrument_type("Notenständer", TYPES)
    assert score < 0.6


def test_match_musician():
    musicians = [MusicianRef(1, "Anna", "Hofer"), MusicianRef(2, "Josef", "Berger")]
    assert match_musician("Hofer Anna", musicians)[0].id == 1
    assert match_musician("Anna Hofer", musicians)[0].id == 1
    assert match_musician("Hofer, Anna", musicians)[0].id == 1
    ref, score = match_musician("Hofner Anna", musicians)
    assert ref.id == 1 and 0.8 <= score < 1.0
    ref, score = match_musician("Maier Karl", musicians)
    assert score < 0.8


def test_split_name():
    assert split_name("Hofer Anna") == ("Anna", "Hofer", True)
    assert split_name("Hofer, Anna") == ("Anna", "Hofer", False)
    assert split_name("Hofer Anna Maria") == ("Anna Maria", "Hofer", True)
    assert split_name("Hofer") == (None, "Hofer", False)


@pytest.mark.parametrize(
    "text,expected,exact",
    [
        ("14.03.2021", date(2021, 3, 14), True),
        ("14.3.21", date(2021, 3, 14), True),
        ("1.9.98", date(1998, 9, 1), True),
        ("2021-03-14", date(2021, 3, 14), True),
        ("03/2021", date(2021, 3, 1), False),
        ("1998", date(1998, 1, 1), False),
        ("31.02.2021", None, False),
        ("irgendwann", None, False),
        (None, None, False),
    ],
)
def test_parse_date(text, expected, exact):
    assert parse_date(text) == (expected, exact)


@pytest.mark.parametrize(
    "text,amount,currency",
    [
        ("1.200 €", 1200.0, "€"),
        ("€ 850,50", 850.5, "€"),
        ("12.000,- ATS", 12000.0, "ATS"),
        ("ATS 12.000", 12000.0, "ATS"),
        ("öS 4.500", 4500.0, "ATS"),
        ("850.50", 850.5, None),
        ("1200", 1200.0, None),
        ("EUR 2.300,00", 2300.0, "€"),
        ("keine Angabe", None, None),
    ],
)
def test_parse_amount(text, amount, currency):
    assert parse_amount(text) == (amount, currency)


# --- validate_draft -----------------------------------------------------------------


def test_clean_row_has_no_blocking_issues():
    v = validate_draft({"instruments": [row()], "photos": []}, ctx())
    r = v["rows"][0]
    assert r["action"] == "create_instrument"
    assert r["fields"]["instrument_type_id"] == 1
    assert r["fields"]["label"] == "Trompete Bb"
    assert r["fields"]["inventory_nr"] == 20
    assert r["fields"]["owner"] == "MV Hofkirchen"
    assert r["fields"]["construction_year"] == 2009
    assert not issues(v, level="error")
    assert issues(v, "instrument_type_id", "info")  # "Trompete Bb" -> "Trompete"
    assert v["summary"]["blocking"] is False
    assert v["summary"]["instruments_new"] == 1


def test_inventory_number_conflicts():
    v = validate_draft(
        {
            "instruments": [
                row(inventory_nr="I-012"),
                row(key="b", inventory_nr="21"),
                row(key="c", inventory_nr="21"),
            ]
        },
        ctx(),
    )
    a, b, c = v["rows"]
    assert [i["level"] for i in a["issues"] if i["field"] == "inventory_nr"] == [
        "error"
    ]
    assert "bereits vergeben" in a["issues"][-1]["message"] or any(
        "bereits vergeben" in i["message"] for i in a["issues"]
    )
    assert not [i for i in b["issues"] if i["field"] == "inventory_nr"]
    assert any("doppelt" in i["message"] for i in c["issues"])
    assert v["summary"]["errors"] == 2
    assert v["summary"]["blocking"] is True


def test_missing_number_is_info_and_auto_assigned():
    v = validate_draft({"instruments": [row(inventory_nr=None)]}, ctx())
    assert v["rows"][0]["fields"]["inventory_nr"] is None
    assert issues(v, "inventory_nr", "info")
    assert v["summary"]["blocking"] is False


def test_unknown_type_is_error_and_explicit_id_wins():
    v = validate_draft({"instruments": [row(instrument_type="Notenständer")]}, ctx())
    assert issues(v, "instrument_type_id", "error")
    assert "instrument_type_id" not in v["rows"][0]["fields"]

    v = validate_draft(
        {"instruments": [row(instrument_type="Notenständer", instrument_type_id=5)]},
        ctx(),
    )
    assert not issues(v, "instrument_type_id")
    assert v["rows"][0]["fields"]["instrument_type_id"] == 5


def test_uncertain_type_is_warning():
    v = validate_draft({"instruments": [row(instrument_type="Tenor")]}, ctx())
    w = issues(v, "instrument_type_id", "warning")
    assert w and w[0]["suggestion"]["label"] == "Tenorhorn"
    assert v["rows"][0]["fields"]["instrument_type_id"] == 7


def test_duplicate_serial_is_warning():
    v = validate_draft({"instruments": [row(serial_nr="ytr-4335 a")]}, ctx())
    w = issues(v, "serial_nr", "warning")
    assert w and "Nr. 12" in w[0]["message"]


def test_acquisition_parsing_and_currency_guess():
    v = validate_draft(
        {"instruments": [row(acquisition_date="1998", acquisition_cost="12.000,-")]},
        ctx(),
    )
    f = v["rows"][0]["fields"]
    assert f["acquisition_date"] == "1998-01-01"
    assert f["acquisition_cost"] == 12000.0
    assert f["currency_id"] == 2  # ATS guessed for 1998
    assert issues(v, "currency_id", "warning")
    assert issues(v, "acquisition_date", "info")

    v = validate_draft({"instruments": [row(acquisition_cost="1.200 €")]}, ctx())
    assert v["rows"][0]["fields"]["currency_id"] == 1
    assert not issues(v, "currency_id")


def test_loan_with_existing_musician():
    v = validate_draft(
        {
            "instruments": [
                row(loan={"musician_name": "Anna Hofer", "start_date": "14.03.2021"})
            ]
        },
        ctx(),
    )
    r = v["rows"][0]
    assert r["musician"] == {
        "action": "existing",
        "musician_id": 10,
        "first_name": "Anna",
        "last_name": "Hofer",
    }
    assert r["loan"] == {
        "action": "create",
        "start_date": "2021-03-14",
        "end_date": None,
        "active": True,
    }
    assert not issues(v, level="error")
    assert v["summary"]["loans_new"] == 1
    assert v["summary"]["musicians_existing"] == 1


def test_loan_with_new_musician_guesses_order_and_needs_date():
    v = validate_draft(
        {
            "instruments": [
                row(loan={"musician_name": "Maier Karl", "start_date": None})
            ]
        },
        ctx(),
    )
    r = v["rows"][0]
    assert r["musician"]["action"] == "create"
    assert (r["musician"]["first_name"], r["musician"]["last_name"]) == (
        "Karl",
        "Maier",
    )
    assert issues(v, "loan.musician_name", "warning")
    assert issues(v, "loan.start_date", "error")
    assert v["summary"]["musicians_new"] == 1
    assert v["summary"]["blocking"] is True


def test_loan_similar_musician_warns_but_creates():
    v = validate_draft(
        {
            "instruments": [
                row(loan={"musician_name": "Hofner Anna", "start_date": "1.1.2020"})
            ]
        },
        ctx(),
    )
    r = v["rows"][0]
    assert r["musician"]["action"] == "create"
    w = issues(v, "loan.musician_id", "warning")
    assert w and w[0]["suggestion"]["id"] == 10


def test_loan_explicit_musician_id_and_names():
    v = validate_draft(
        {
            "instruments": [
                row(
                    loan={
                        "musician_name": "x",
                        "musician_id": 11,
                        "start_date": "1.1.2020",
                    }
                ),
                row(
                    key="b",
                    loan={
                        "musician_name": "Maier Karl",
                        "first_name": "Karl",
                        "last_name": "Maier",
                        "start_date": "1.1.2020",
                    },
                ),
            ]
        },
        ctx(),
    )
    assert v["rows"][0]["musician"]["musician_id"] == 11
    b = v["rows"][1]
    assert b["musician"]["action"] == "create"
    assert not [i for i in b["issues"] if i["field"] == "loan.musician_name"]


def test_skipped_rows_and_photos():
    v = validate_draft(
        {
            "instruments": [row(skip=True), row(key="b", inventory_nr="21")],
            "photos": [
                {"key": "f1", "row_key": "p0-i0"},
                {"key": "f2", "row_key": "b"},
                {"key": "f3", "row_key": None},
            ],
        },
        ctx(),
    )
    assert v["rows"][0]["action"] == "skip"
    assert [p["action"] for p in v["photos"]] == ["ignore", "attach", "ignore"]
    assert v["summary"]["skipped"] == 1
    assert v["summary"]["photos_attached"] == 1


def test_empty_draft_is_blocking():
    v = validate_draft({"instruments": [], "photos": []}, ctx())
    assert v["summary"]["blocking"] is True
