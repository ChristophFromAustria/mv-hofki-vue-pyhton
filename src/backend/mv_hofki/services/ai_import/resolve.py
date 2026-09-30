"""Resolve and validate the draft against the database, without the model.

Everything the model returned is text. This module maps it onto what the
import needs (instrument type ids, musician ids, dates, amounts) and reports
per field what it did and how sure it is:

- ``ok``        value accepted as is
- ``info``      value derived/normalised automatically (no action needed)
- ``warning``   value guessed, the user should check it
- ``error``     value missing or conflicting, blocks the import

The heavy lifting is pure Python over a :class:`Context` snapshot so it can
be unit-tested without a database; :func:`load_context` fills the snapshot.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.db.soft_delete import with_deleted
from mv_hofki.models.currency import Currency
from mv_hofki.models.instrument_detail import InstrumentDetail
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.musician import Musician
from mv_hofki.models.retired_inventory_number import RetiredInventoryNumber
from mv_hofki.schemas.inventory_item import format_display_nr

DEFAULT_OWNER = "MV Hofkirchen"

# ---------------------------------------------------------------------------
# Context (database snapshot)
# ---------------------------------------------------------------------------


@dataclass
class TypeRef:
    id: int
    label: str
    label_short: str = ""

    @property
    def number_prefix(self) -> str:
        return self.label_short.strip().upper()


@dataclass
class MusicianRef:
    id: int
    first_name: str
    last_name: str


@dataclass
class CurrencyRef:
    id: int
    label: str
    abbreviation: str


@dataclass
class ExistingItem:
    id: int
    inventory_nr: int
    label: str
    serial_nr: str | None = None
    number_prefix: str = ""


@dataclass
class Context:
    instrument_types: list[TypeRef] = field(default_factory=list)
    musicians: list[MusicianRef] = field(default_factory=list)
    currencies: list[CurrencyRef] = field(default_factory=list)
    instruments: list[ExistingItem] = field(default_factory=list)
    # Numbers of deleted/renumbered instruments per short code: never reused.
    retired: dict[str, set[int]] = field(default_factory=dict)
    today: date = field(default_factory=date.today)

    def used_numbers(self, prefix: str) -> set[int]:
        """Numbers already taken in the sequence of one short code."""
        return {i.inventory_nr for i in self.instruments if i.number_prefix == prefix}

    def retired_numbers(self, prefix: str) -> set[int]:
        return self.retired.get(prefix, set())

    def next_free_number(self, prefix: str) -> int:
        given_out = self.used_numbers(prefix) | self.retired_numbers(prefix)
        return (max(given_out) if given_out else 0) + 1


async def load_context(db: AsyncSession) -> Context:
    types = (await db.execute(select(InstrumentType))).scalars().all()
    musicians = (await db.execute(select(Musician))).scalars().all()
    currencies = (await db.execute(select(Currency))).scalars().all()
    # Items in the trash keep their numbers, so they count as taken.
    rows = (
        await db.execute(
            with_deleted(
                select(InventoryItem, InstrumentDetail.serial_nr)
                .outerjoin(
                    InstrumentDetail, InstrumentDetail.item_id == InventoryItem.id
                )
                .where(InventoryItem.category == "instrument")
            )
        )
    ).all()
    retired: dict[str, set[int]] = {}
    for prefix, nr in (
        await db.execute(
            select(
                RetiredInventoryNumber.number_prefix,
                RetiredInventoryNumber.inventory_nr,
            ).where(RetiredInventoryNumber.category == "instrument")
        )
    ).all():
        retired.setdefault(prefix, set()).add(nr)
    return Context(
        instrument_types=[TypeRef(t.id, t.label, t.label_short) for t in types],
        musicians=[MusicianRef(m.id, m.first_name, m.last_name) for m in musicians],
        currencies=[CurrencyRef(c.id, c.label, c.abbreviation) for c in currencies],
        instruments=[
            ExistingItem(
                item.id, item.inventory_nr, item.label, serial, item.number_prefix
            )
            for item, serial in rows
        ],
        retired=retired,
    )


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def _fold(text: str) -> str:
    """lowercase, umlauts kept as base letters, punctuation -> space."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("ß", "ss")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# Written form on documents -> seeded instrument type label. Keys are folded.
TYPE_ALIASES: dict[str, str] = {
    "trompete": "Trompete",
    "trompete b": "Trompete",
    "trompete bb": "Trompete",
    "b trompete": "Trompete",
    "kornett": "Trompete",
    "flugelhorn": "Flügelhorn",
    "flugelhorn b": "Flügelhorn",
    "fluegelhorn": "Flügelhorn",
    "tenorhorn": "Tenorhorn",
    "tenorhorn b": "Tenorhorn",
    "bariton": "Bariton",
    "baritonhorn": "Bariton",
    "euphonium": "Euphonium",
    "horn": "Horn",
    "waldhorn": "Horn",
    "horn f": "Horn",
    "posaune": "Posaune",
    "zugposaune": "Posaune",
    "ventilposaune": "Posaune",
    "tuba": "Tuba",
    "basstuba": "Tuba",
    "bass": "Tuba",
    "b tuba": "Tuba",
    "es tuba": "Tuba",
    "f tuba": "Tuba",
    "helikon": "Tuba",
    "sousaphon": "Tuba",
    "klarinette": "Klarinette in B",
    "klarinette b": "Klarinette in B",
    "klarinette bb": "Klarinette in B",
    "klarinette in b": "Klarinette in B",
    "b klarinette": "Klarinette in B",
    "klarinette es": "Klarinette in Es",
    "klarinette in es": "Klarinette in Es",
    "es klarinette": "Klarinette in Es",
    "bassklarinette": "Bassklarinette",
    "querflote": "Querflöte",
    "flote": "Querflöte",
    "piccolo": "Querflöte",
    "piccoloflote": "Querflöte",
    "oboe": "Oboe",
    "englischhorn": "Englischhorn (Alt-Oboe)",
    "fagott": "Fagott",
    "saxophon": "Saxophon",
    "saxofon": "Saxophon",
    "altsaxophon": "Altsaxophon",
    "altsaxofon": "Altsaxophon",
    "altsax": "Altsaxophon",
    "tenorsaxophon": "Tenorsaxophon",
    "tenorsaxofon": "Tenorsaxophon",
    "tenorsax": "Tenorsaxophon",
    "baritonsaxophon": "Baritonsaxophon",
    "baritonsax": "Baritonsaxophon",
    "schlagwerk": "Schlagwerk",
    "schlagzeug": "Schlagwerk",
    "trommel": "Schlagwerk",
    "grosse trommel": "Schlagwerk",
    "kleine trommel": "Schlagwerk",
    "pauke": "Schlagwerk",
    "pauken": "Schlagwerk",
    "becken": "Schlagwerk",
    "glockenspiel": "Schlagwerk",
    "lyra": "Schlagwerk",
}


def match_instrument_type(
    text: str | None, types: list[TypeRef]
) -> tuple[TypeRef | None, float]:
    """Return (best type, confidence 0..1). Confidence 1.0 = exact/alias hit."""
    if not text or not types:
        return None, 0.0
    by_label = {t.label: t for t in types}
    folded = _fold(text)
    if not folded:
        return None, 0.0

    # exact label
    for t in types:
        if _fold(t.label) == folded:
            return t, 1.0
    # alias, exact
    alias = TYPE_ALIASES.get(folded)
    if alias and alias in by_label:
        return by_label[alias], 1.0
    # alias contained in the text ("Trompete Yamaha Bb" -> "trompete")
    best_alias: tuple[int, str] | None = None
    for key, label in TYPE_ALIASES.items():
        if label in by_label and re.search(rf"\b{re.escape(key)}\b", folded):
            if best_alias is None or len(key) > best_alias[0]:
                best_alias = (len(key), label)
    if best_alias:
        return by_label[best_alias[1]], 0.9

    # fuzzy against labels and alias keys
    best: tuple[float, TypeRef] | None = None
    for t in types:
        score = _ratio(folded, _fold(t.label))
        if best is None or score > best[0]:
            best = (score, t)
    for key, label in TYPE_ALIASES.items():
        if label in by_label:
            score = _ratio(folded, key)
            if best is None or score > best[0]:
                best = (score, by_label[label])
    if best is None:
        return None, 0.0
    return best[1], round(best[0], 2)


def split_name(text: str) -> tuple[str | None, str | None, bool]:
    """Return (first_name, last_name, guessed_order).

    Austrian club lists usually write "Nachname Vorname"; that is the default
    assumption and ``guessed_order`` is True in that case. "Nachname, Vorname"
    is unambiguous.
    """
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return None, None, False
    if "," in text:
        last, first = (p.strip() for p in text.split(",", 1))
        return first or None, last or None, False
    parts = text.split(" ")
    if len(parts) == 1:
        return None, parts[0], False
    return " ".join(parts[1:]), parts[0], True


def match_musician(
    text: str | None, musicians: list[MusicianRef]
) -> tuple[MusicianRef | None, float]:
    if not text:
        return None, 0.0
    tokens = sorted(_fold(text.replace(",", " ")).split())
    if not tokens:
        return None, 0.0
    joined = " ".join(tokens)
    best: tuple[float, MusicianRef] | None = None
    for m in musicians:
        m_tokens = sorted(_fold(f"{m.first_name} {m.last_name}").split())
        if m_tokens == tokens:
            return m, 1.0
        score = _ratio(joined, " ".join(m_tokens))
        if best is None or score > best[0]:
            best = (score, m)
    if best is None:
        return None, 0.0
    return best[1], round(best[0], 2)


_DATE_PATTERNS = [
    (re.compile(r"^(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})$"), "dmy"),
    (re.compile(r"^(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{2})$"), "dmy2"),
    (re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$"), "ymd"),
    (re.compile(r"^(\d{1,2})/(\d{4})$"), "my"),
    (re.compile(r"^(\d{1,2})\.(\d{4})$"), "my"),
    (re.compile(r"^(\d{4})$"), "y"),
]


def parse_date(text: str | None) -> tuple[date | None, bool]:
    """Return (date, exact). Month/year-only inputs give the 1st (exact=False)."""
    if not text:
        return None, False
    s = text.strip()
    for pattern, kind in _DATE_PATTERNS:
        m = pattern.match(s)
        if not m:
            continue
        try:
            if kind == "dmy":
                return date(int(m[3]), int(m[2]), int(m[1])), True
            if kind == "dmy2":
                yy = int(m[3])
                return date(
                    2000 + yy if yy < 40 else 1900 + yy, int(m[2]), int(m[1])
                ), True
            if kind == "ymd":
                return date(int(m[1]), int(m[2]), int(m[3])), True
            if kind == "my":
                return date(int(m[2]), int(m[1]), 1), False
            if kind == "y":
                return date(int(m[1]), 1, 1), False
        except ValueError:
            return None, False
    return None, False


_CURRENCY_WORDS = {
    "€": "€",
    "eur": "€",
    "euro": "€",
    "ats": "ATS",
    "s": "ATS",
    "os": "ATS",
    "ös": "ATS",
    "schilling": "ATS",
    "sch": "ATS",
    "$": "$",
    "usd": "$",
    "dollar": "$",
    "£": "£",
    "gbp": "£",
    "pfund": "£",
    "dm": "DM",
}


def parse_amount(text: str | None) -> tuple[float | None, str | None]:
    """'1.200 €' -> (1200.0, '€'); '12.000,- ATS' -> (12000.0, 'ATS');
    '850,50' -> (850.5, None)."""
    if not text:
        return None, None
    s = text.strip()
    currency = None
    for word, abbr in sorted(_CURRENCY_WORDS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"(?<![a-z€$£]){re.escape(word)}(?![a-z])", s.lower()):
            currency = abbr
            break
    num = re.search(r"\d[\d.\s]*(?:,\d{1,2})?|\d+(?:\.\d{1,2})?", s)
    if not num:
        return None, currency
    raw = num.group(0).replace(" ", "")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") == 1 and len(raw.split(".")[1]) != 3:
        pass  # "850.50" -> decimal point
    else:
        raw = raw.replace(".", "")
    try:
        return float(raw), currency
    except ValueError:
        return None, currency


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    digits = re.sub(r"\D", "", str(value))
    return int(digits) if digits else None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _issue(field_name: str, level: str, message: str, suggestion: Any = None) -> dict:
    out: dict[str, Any] = {"field": field_name, "level": level, "message": message}
    if suggestion is not None:
        out["suggestion"] = suggestion
    return out


def validate_row(
    row: dict[str, Any], ctx: Context, reserved: set[tuple[str, int]]
) -> dict[str, Any]:
    """Validate one draft row. ``reserved`` collects (prefix, number) pairs claimed
    by earlier rows of the same draft so duplicates inside the draft are caught.
    Numbers run per instrument-type short code, so they are only checked once the
    type is known."""
    issues: list[dict[str, Any]] = []
    fields: dict[str, Any] = {"category": "instrument", "owner": DEFAULT_OWNER}
    result: dict[str, Any] = {
        "key": row.get("key"),
        "skip": bool(row.get("skip")),
        "action": "skip" if row.get("skip") else "create_instrument",
        "fields": fields,
        "musician": {"action": "none"},
        "loan": {"action": "none"},
        "issues": issues,
    }
    if result["skip"]:
        return result

    # --- instrument type -------------------------------------------------------
    type_ref: TypeRef | None = None
    if row.get("instrument_type_id") is not None:
        type_ref = next(
            (t for t in ctx.instrument_types if t.id == row["instrument_type_id"]), None
        )
        if type_ref is None:
            issues.append(
                _issue("instrument_type_id", "error", "Unbekannter Instrumententyp")
            )
    else:
        type_ref, score = match_instrument_type(
            row.get("instrument_type"), ctx.instrument_types
        )
        text = row.get("instrument_type")
        if type_ref is None or score < 0.6:
            type_ref = None
            issues.append(
                _issue(
                    "instrument_type_id",
                    "error",
                    (
                        f"Instrumententyp „{text}“ nicht erkannt, bitte wählen"
                        if text
                        else "Instrumententyp fehlt"
                    ),
                )
            )
        elif score < 0.85:
            issues.append(
                _issue(
                    "instrument_type_id",
                    "warning",
                    f"„{text}“ unsicher als „{type_ref.label}“ erkannt, bitte prüfen",
                    {"id": type_ref.id, "label": type_ref.label},
                )
            )
        elif _fold(text or "") != _fold(type_ref.label):
            issues.append(
                _issue(
                    "instrument_type_id",
                    "info",
                    f"„{text}“ als „{type_ref.label}“ zugeordnet",
                    {"id": type_ref.id, "label": type_ref.label},
                )
            )
    if type_ref:
        fields["instrument_type_id"] = type_ref.id
        fields["instrument_type_label"] = type_ref.label
        fields["number_prefix"] = type_ref.number_prefix

    # --- label ------------------------------------------------------------------
    label = (row.get("label") or "").strip() or (
        row.get("instrument_type") or ""
    ).strip()
    if not label and type_ref:
        label = type_ref.label
    if label:
        fields["label"] = label[:200]
    else:
        issues.append(_issue("label", "error", "Bezeichnung fehlt"))

    # --- inventory number -------------------------------------------------------
    nr = parse_int(row.get("inventory_nr"))
    prefix = type_ref.number_prefix if type_ref else None
    display = format_display_nr(prefix, nr) if prefix and nr is not None else nr
    fields["inventory_nr"] = nr
    if nr is None:
        issues.append(
            _issue("inventory_nr", "info", "Keine Nummer, wird automatisch vergeben")
        )
    elif prefix is None:
        pass  # checked once the instrument type is chosen
    elif nr in ctx.used_numbers(prefix):
        existing = next(
            i
            for i in ctx.instruments
            if i.number_prefix == prefix and i.inventory_nr == nr
        )
        reserved_here = {n for p, n in reserved if p == prefix}
        issues.append(
            _issue(
                "inventory_nr",
                "error",
                f"Inventarnummer {display} ist bereits vergeben ({existing.label})",
                {
                    "next_free": max(
                        ctx.next_free_number(prefix),
                        max(reserved_here, default=0) + 1,
                    )
                },
            )
        )
    elif nr in ctx.retired_numbers(prefix):
        reserved_here = {n for p, n in reserved if p == prefix}
        issues.append(
            _issue(
                "inventory_nr",
                "error",
                f"Inventarnummer {display} war schon vergeben (gelöschter oder "
                "umnummerierter Gegenstand) und wird nicht wieder verwendet",
                {
                    "next_free": max(
                        ctx.next_free_number(prefix),
                        max(reserved_here, default=0) + 1,
                    )
                },
            )
        )
    elif (prefix, nr) in reserved:
        issues.append(
            _issue(
                "inventory_nr",
                "error",
                f"Inventarnummer {display} kommt im Entwurf doppelt vor",
            )
        )
    else:
        reserved.add((prefix, nr))

    # --- plain text fields -------------------------------------------------------
    for src, dst, limit in (
        ("manufacturer", "manufacturer", 100),
        ("serial_nr", "serial_nr", 100),
        ("distributor", "distributor", 100),
        ("container", "container", 100),
        ("particularities", "particularities", 500),
    ):
        value = row.get(src)
        if value is not None and str(value).strip():
            value = str(value).strip()
            if len(value) > limit:
                issues.append(
                    _issue(dst, "warning", f"Wird auf {limit} Zeichen gekürzt")
                )
            fields[dst] = value[:limit]
        else:
            fields[dst] = None
    if row.get("owner"):
        fields["owner"] = str(row["owner"]).strip()[:100]
    notes_parts = []
    if row.get("model"):
        notes_parts.append(f"Modell: {str(row['model']).strip()}")
    if row.get("notes"):
        notes_parts.append(str(row["notes"]).strip())
    fields["notes"] = " · ".join(notes_parts)[:500] or None

    if fields.get("serial_nr"):
        dup = next(
            (
                i
                for i in ctx.instruments
                if i.serial_nr and _fold(i.serial_nr) == _fold(fields["serial_nr"])
            ),
            None,
        )
        if dup:
            issues.append(
                _issue(
                    "serial_nr",
                    "warning",
                    "Seriennummer existiert bereits bei Nr. "
                    f"{format_display_nr(dup.number_prefix, dup.inventory_nr)} "
                    f"({dup.label})",
                )
            )

    # --- year ---------------------------------------------------------------------
    year = parse_int(row.get("construction_year"))
    if year is not None and not (1800 <= year <= ctx.today.year + 1):
        issues.append(
            _issue("construction_year", "warning", f"Baujahr {year} unplausibel")
        )
        year = None
    fields["construction_year"] = year

    # --- acquisition -------------------------------------------------------------
    acq_text = row.get("acquisition_date")
    acq_date, exact = parse_date(acq_text if isinstance(acq_text, str) else None)
    if acq_text and acq_date is None:
        issues.append(
            _issue(
                "acquisition_date",
                "warning",
                f"Datum „{acq_text}“ nicht lesbar, bitte eingeben",
            )
        )
    elif acq_date and not exact:
        issues.append(
            _issue(
                "acquisition_date",
                "info",
                f"„{acq_text}“ als {acq_date.isoformat()} übernommen",
                acq_date.isoformat(),
            )
        )
    fields["acquisition_date"] = acq_date.isoformat() if acq_date else None

    amount, abbr = parse_amount(row.get("acquisition_cost"))
    fields["acquisition_cost"] = amount
    currency_id = row.get("currency_id")
    if currency_id is None and amount is not None:
        if abbr is None:
            ref_year = acq_date.year if acq_date else year
            abbr = "ATS" if ref_year and ref_year < 2002 else "€"
            issues.append(
                _issue(
                    "currency_id",
                    "warning",
                    f"Keine Währung angegeben, {abbr} angenommen",
                )
            )
        cur = next((c for c in ctx.currencies if c.abbreviation == abbr), None)
        if cur:
            currency_id = cur.id
        else:
            issues.append(
                _issue("currency_id", "warning", f"Währung „{abbr}“ ist nicht angelegt")
            )
    if row.get("acquisition_cost") and amount is None:
        issues.append(
            _issue(
                "acquisition_cost",
                "warning",
                f"Preis „{row['acquisition_cost']}“ nicht lesbar",
            )
        )
    fields["currency_id"] = currency_id

    # --- loan / musician -----------------------------------------------------------
    loan = row.get("loan") or {}
    name = (loan.get("musician_name") or "").strip() if isinstance(loan, dict) else ""
    if isinstance(loan, dict) and (
        name or loan.get("musician_id") or loan.get("last_name")
    ):
        musician: dict[str, Any] = {"action": "create"}
        if loan.get("musician_id") is not None:
            ref = next((m for m in ctx.musicians if m.id == loan["musician_id"]), None)
            if ref:
                musician = {
                    "action": "existing",
                    "musician_id": ref.id,
                    "first_name": ref.first_name,
                    "last_name": ref.last_name,
                }
            else:
                issues.append(
                    _issue("loan.musician_id", "error", "Unbekannter Musiker")
                )
        else:
            ref, score = match_musician(name, ctx.musicians)
            if ref and score >= 0.99:
                musician = {
                    "action": "existing",
                    "musician_id": ref.id,
                    "first_name": ref.first_name,
                    "last_name": ref.last_name,
                }
            else:
                if ref and score >= 0.8:
                    issues.append(
                        _issue(
                            "loan.musician_id",
                            "warning",
                            "Ähnlicher Musiker vorhanden: "
                            f"{ref.first_name} {ref.last_name}",
                            {"id": ref.id, "name": f"{ref.first_name} {ref.last_name}"},
                        )
                    )
                first = loan.get("first_name")
                last = loan.get("last_name")
                if not (first or last):
                    first, last, guessed = split_name(name)
                    if guessed:
                        issues.append(
                            _issue(
                                "loan.musician_name",
                                "warning",
                                f"Reihenfolge angenommen: Nachname „{last}“, "
                                f"Vorname „{first}“",
                            )
                        )
                if not last:
                    issues.append(_issue("loan.last_name", "error", "Nachname fehlt"))
                if not first:
                    issues.append(_issue("loan.first_name", "error", "Vorname fehlt"))
                musician.update(
                    {
                        "first_name": first,
                        "last_name": last,
                        "is_extern": bool(loan.get("is_extern")),
                    }
                )
        result["musician"] = musician

        start_text = loan.get("start_date")
        start, exact = parse_date(start_text if isinstance(start_text, str) else None)
        end_text = loan.get("end_date")
        end, _ = parse_date(end_text if isinstance(end_text, str) else None)
        if start is None:
            suggestion = fields.get("acquisition_date")
            issues.append(
                _issue(
                    "loan.start_date",
                    "error",
                    (
                        f"Leihbeginn „{start_text}“ nicht lesbar"
                        if start_text
                        else "Leihbeginn fehlt"
                    ),
                    suggestion,
                )
            )
        elif not exact:
            issues.append(
                _issue(
                    "loan.start_date",
                    "info",
                    f"„{start_text}“ als {start.isoformat()} übernommen",
                    start.isoformat(),
                )
            )
        if end_text and end is None:
            issues.append(
                _issue(
                    "loan.end_date", "warning", f"Rückgabe „{end_text}“ nicht lesbar"
                )
            )
        result["loan"] = {
            "action": "create",
            "start_date": start.isoformat() if start else None,
            "end_date": end.isoformat() if end else None,
            "active": end is None,
        }

    return result


def validate_draft(draft: dict[str, Any], ctx: Context) -> dict[str, Any]:
    rows_out: list[dict[str, Any]] = []
    reserved: set[tuple[str, int]] = set()
    for row in draft.get("instruments", []):
        rows_out.append(validate_row(row, ctx, reserved))

    row_keys = {r["key"] for r in rows_out if not r["skip"]}
    photos_out = []
    for photo in draft.get("photos", []):
        row_key = photo.get("row_key")
        photos_out.append(
            {
                "key": photo.get("key"),
                "row_key": row_key,
                "action": "attach" if row_key in row_keys else "ignore",
            }
        )

    active = [r for r in rows_out if not r["skip"]]
    errors = sum(1 for r in active for i in r["issues"] if i["level"] == "error")
    warnings = sum(1 for r in active for i in r["issues"] if i["level"] == "warning")
    new_musicians = {
        (r["musician"].get("last_name"), r["musician"].get("first_name"))
        for r in active
        if r["musician"]["action"] == "create"
    }
    summary = {
        "rows": len(rows_out),
        "skipped": len(rows_out) - len(active),
        "instruments_new": len(active),
        "musicians_existing": len(
            {
                r["musician"]["musician_id"]
                for r in active
                if r["musician"]["action"] == "existing"
            }
        ),
        "musicians_new": len(new_musicians),
        "loans_new": sum(1 for r in active if r["loan"]["action"] == "create"),
        "photos_attached": sum(1 for p in photos_out if p["action"] == "attach"),
        "errors": errors,
        "warnings": warnings,
        "blocking": errors > 0 or not active,
    }
    return {"rows": rows_out, "photos": photos_out, "summary": summary}
