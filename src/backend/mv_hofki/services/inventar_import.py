"""Import of the digitised paper inventory (samplefiles/inventar_scans/_extraktion).

The extraction produced, per folder, a ``zusammenfuehrung.json`` (instruments,
musicians, loans, invoices with page references), a cross-folder musician list
``_gesamt/musiker.json`` and cropped photos with their inventory numbers. This
module turns that into database rows in two steps:

* :func:`build_plan` is pure: it maps types, numbers, dates, owners and loans
  and records every decision or doubt as a warning, so a dry run can show
  exactly what would be written.
* :func:`apply_plan` writes the plan in one transaction and copies photo and
  invoice files into the upload folders.

Rules agreed with the inventory officer (2026-09-27):

* Numbers run per instrument-type short code; paper "TU 1" becomes TU-001, the
  number as written is kept in the notes. Instruments without a paper number
  get the next free number of their code.
* Private instruments are imported with the musician's name as owner.
* "MS" / "MS Archiv" in the register list = Musikschule, eingelagert: storage
  location "Musikschule (Archiv)", no active loan. "Archiv" likewise with
  storage location "Archiv".
* Approximate dates ("~2010", "2016?") become the 1st of January of that year.
* Other clubs are external musicians.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.clothing_detail import ClothingDetail
from mv_hofki.models.clothing_type import ClothingType
from mv_hofki.models.currency import Currency
from mv_hofki.models.instrument_detail import InstrumentDetail
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.item_image import ItemImage
from mv_hofki.models.item_invoice import ItemInvoice
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.models.register import Register, musician_registers
from mv_hofki.schemas.inventory_item import CATEGORY_PREFIXES, format_display_nr

CLUB_OWNER = "MV Hofkirchen"
UNCLEAR_OWNER = "Eigentum unklar"
STORAGE_MS = "Musikschule (Archiv)"
STORAGE_ARCHIV = "Archiv"
NOTES_MAX = 500

# Instrument type text as written -> instrument type label in the database.
# First match wins, so specific names come before general ones.
TYPE_RULES: list[tuple[str, str]] = [
    (r"bassklarinette", "Bassklarinette"),
    (r"es-klarinette|klarinette in es", "Klarinette in Es"),
    (r"klarinette", "Klarinette in B"),
    (r"piccolo|querfl", "Querflöte"),
    (r"baritonsax", "Baritonsaxophon"),
    (r"tenorsax|tenor-sax", "Tenorsaxophon"),
    (r"altsax|alt-sax|saxophon", "Altsaxophon"),
    (r"englischhorn", "Englischhorn (Alt-Oboe)"),
    (r"oboe", "Oboe"),
    (r"fagott", "Fagott"),
    (r"flügelhorn|fluegelhorn", "Flügelhorn"),
    (r"trompete", "Trompete"),
    (r"euphonium", "Euphonium"),
    (r"tenorhorn|bariton", "Tenorhorn"),
    (r"waldhorn|kinderhorn|^horn", "Horn"),
    (r"posaune", "Posaune"),
    (r"tuba", "Tuba"),
]

# Photos that must not be attached (decided while reviewing the scans).
PHOTO_EXCLUDE = {
    # te_05 shows the very same prints as te_06 (serial TCO 4389); the real
    # serial of TE 5 is not documented anywhere, so the photos belong to TE 6.
    ("Tenorhorn", "te_05.jpg"),
}

_YEAR_RE = re.compile(r"(1[89]\d\d|20\d\d)(?:[-./](\d{1,2}))?(?:[-./](\d{1,2}))?")
_NR_RE = re.compile(r"^\s*([^\W\d_]+)\s*-?\s*0*(\d+)\s*$")


# ---------------------------------------------------------------------------
# Small parsers
# ---------------------------------------------------------------------------


def parse_date(value: Any) -> tuple[date | None, bool]:
    """Parse "2003", "2023-09", "1996-06-10", "~2017", "2012/13".

    Returns (date, exact). Missing month/day become 1 (the agreed rule for
    approximate dates); ``exact`` is False whenever something was filled in or
    the text carried a "~" / "?" / "ca.".
    """
    if value is None:
        return None, False
    text = str(value).strip()
    m = _YEAR_RE.search(text)
    if not m:
        return None, False
    year = int(m[1])
    month = int(m[2]) if m[2] else 1
    day = int(m[3]) if m[3] else 1
    if not 1 <= month <= 12:
        month, day = 1, 1
    try:
        parsed = date(year, month, day)
    except ValueError:
        parsed = date(year, month, 1)
    exact = bool(m[3]) and not re.search(r"[~?]|ca\.", text)
    return parsed, exact


def parse_year(value: Any) -> int | None:
    if value is None:
        return None
    m = _YEAR_RE.search(str(value))
    return int(m[1]) if m else None


def parse_amount(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).replace("€", "").replace("ATS", "").replace("S", "")
    text = text.replace(".-", "").replace(",-", "").strip()
    # "25.500" / "2.940,00" -> German thousands separator
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_inventory_nr(value: Any) -> tuple[str, int] | None:
    """ "TU 1" / "Po 1" / "KL 1" -> ("TU", 1)."""
    if not value:
        return None
    m = _NR_RE.match(str(value))
    return (m[1].upper(), int(m[2])) if m else None


def map_type(text: str | None) -> str | None:
    probe = (text or "").lower()
    for pattern, label in TYPE_RULES:
        if re.search(pattern, probe):
            return label
    return None


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _join(parts: list[str | None], sep: str = "; ") -> str:
    return sep.join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


@dataclass
class PlannedMusician:
    key: str  # G-ID from _gesamt/musiker.json
    first_name: str
    last_name: str
    phone: str | None
    is_extern: bool
    notes: str | None
    refs: list[str]  # "<Ordner>/<lokale ID>"
    is_active: bool = False
    registers: list[str] = field(default_factory=list)  # register labels


@dataclass
class PlannedItem:
    key: str  # "<Ordner>/<Instrument-ID>"
    type_label: str
    prefix: str
    inventory_nr: int | None
    paper_nr: str | None
    label: str
    manufacturer: str | None
    serial_nr: str | None
    construction_year: int | None
    acquisition_date: date | None
    acquisition_cost: float | None
    currency: str | None  # "EUR" | "ATS"
    distributor: str | None
    container: str | None
    particularities: str | None
    owner: str
    storage_location: str | None
    notes: str
    sources: list[str]
    photos: list[dict[str, Any]] = field(default_factory=list)
    scans: list[dict[str, Any]] = field(default_factory=list)  # path, caption
    category: str = "instrument"  # | "general_item" | "clothing"
    quantity: int = 1
    clothing_type: str | None = None  # label, created when missing

    @property
    def display_nr(self) -> str:
        return format_display_nr(self.prefix, self.inventory_nr or 0)


@dataclass
class PlannedLoan:
    item_key: str
    musician_key: str
    start: date
    end: date | None
    note: str | None
    sources: list[str]


@dataclass
class PlannedInvoice:
    item_key: str
    title: str
    amount: float
    currency: str
    date_issued: date
    issuer: str | None
    issuer_address: str | None
    description: str | None
    page_images: list[Path]


@dataclass
class Plan:
    musicians: list[PlannedMusician] = field(default_factory=list)
    items: list[PlannedItem] = field(default_factory=list)
    loans: list[PlannedLoan] = field(default_factory=list)
    invoices: list[PlannedInvoice] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    # name matches between the scheduling-app list and the paper records
    name_matches: list[dict[str, str]] = field(default_factory=list)

    def warn(self, where: str, text: str) -> None:
        self.warnings.append({"wo": where, "text": text})

    def skip(self, where: str, text: str) -> None:
        self.skipped.append({"wo": where, "text": text})


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _register_names(root: Path) -> dict[str, str]:
    """Inventory number (normalised "TU 1") -> name column of the register list."""
    names: dict[str, str] = {}
    for page in sorted((root / "_gesamt" / "roh").glob("inventar_liste_p*.json")):
        for table in _load_json(page).get("tables", []):
            for row in table.get("zeilen", []):
                cells = row.get("zellen", {})
                nr = parse_inventory_nr(
                    cells.get("Inventarnr.") or cells.get("Inventarnr")
                )
                name = next(
                    (
                        v
                        for k, v in cells.items()
                        if k.startswith("(ohne") or k == "Name"
                    ),
                    None,
                )
                if nr and name:
                    names[f"{nr[0]} {nr[1]}"] = str(name).strip()
    return names


def _storage_for(item: dict[str, Any], register_name: str | None) -> str | None:
    name = (register_name or "").strip().lower()
    if name.startswith("ms"):
        return STORAGE_MS
    if item.get("archiv") or name == "archiv":
        return STORAGE_ARCHIV
    return None


# Short names of the page formats (formate.json) for provenance notes.
FORMAT_NAMES = {
    "F01": "Instrumentenarchivierung (Tabellenvordruck)",
    "F02": "Sammelliste (maschinengeschrieben)",
    "F03": "Instrumentenarchivierung (alter Vordruck)",
    "F04": "Instrumenten-Datenblatt",
    "F05": "Detailblatt (maschinengeschrieben)",
    "R01": "Rechnung / Angebot / Lieferschein",
    "L01": "Handschriftliche Liste",
    "L02": "Register-Inventarliste",
    "B01": "Zahlungsliste (Online-Banking)",
    "B02": "Kontobericht Instrumentenkauf",
    "L03": "Equipment-/Raumliste (Word)",
    "X01": "Sonstiges",
}

# Scheduling-app spelling -> spelling in the paper records, where the two differ
# by more than a typo. Applied as "wahrscheinlich" and listed for confirmation.
NAME_ALIASES = {
    ("Johannes", "Kreidl"): ("Hansi", "Kreidl"),
    ("Fred", "Hofer"): ("Manfred", "Hofer"),
}


def parse_active_list(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    """The scheduling-app export: a list of names, then blocks "<Register>" +
    names. Returns (all names, register label -> names)."""
    lines = path.read_text(encoding="utf-8").split("\n")
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.strip():
            current.append(line.strip())
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    names = blocks[0]
    registers: dict[str, list[str]] = {}
    for block in blocks[1:]:
        if block[0].lower().startswith("nach register"):
            continue
        registers[block[0]] = block[1:]
    return names, registers


def _split_name(full: str) -> tuple[str, str]:
    first, _, last = full.partition(" ")
    return first, last


def _similar(a: str, b: str) -> float:
    from difflib import SequenceMatcher

    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _merge_active_list(plan: Plan, path: Path, register_labels: set[str]) -> None:
    """Mark musicians from the scheduling app active, set their registers and
    add the ones the paper records do not know."""
    names, registers = parse_active_list(path)
    member_of: dict[str, list[str]] = {}
    for label, members in registers.items():
        if label not in register_labels:
            plan.warn(f"aktive_musiker/{label}", "Register nicht in der Datenbank")
            continue
        for n in members:
            member_of.setdefault(n, []).append(label)
    for n in list(member_of):
        if n not in names:
            match = max(names, key=lambda x: _similar(x, n))
            if _similar(match, n) >= 0.8 or match.startswith(n):
                member_of.setdefault(match, []).extend(member_of[n])
                plan.warn(
                    f"aktive_musiker/{n}", f"im Register als „{n}“, Liste „{match}“"
                )

    by_name = {(m.first_name.lower(), m.last_name.lower()): m for m in plan.musicians}
    used: set[str] = set()
    counter = 0
    for full in names:
        first, last = _split_name(full)
        m = by_name.get((first.lower(), last.lower()))
        how = "gleich"
        if m is None and (first, last) in NAME_ALIASES:
            a_first, a_last = NAME_ALIASES[(first, last)]
            m = by_name.get((a_first.lower(), a_last.lower()))
            how = "Annahme (Kurzform/Spitzname)"
        if m is None:
            candidates = [
                x
                for x in plan.musicians
                if x.key not in used
                and x.first_name.lower() == first.lower()
                and (
                    _similar(x.last_name, last) >= 0.8
                    or last.lower().startswith(x.last_name.lower() + "-")
                    or _similar(x.first_name + x.last_name, first + last) >= 0.9
                )
            ]
            if not candidates:
                candidates = [
                    x
                    for x in plan.musicians
                    if x.key not in used
                    and x.last_name.lower() == last.lower()
                    and _similar(x.first_name, first) >= 0.9
                ]
            if len(candidates) == 1:
                m = candidates[0]
                how = "ähnliche Schreibweise"
        if m is not None and m.key not in used:
            used.add(m.key)
            if (m.first_name, m.last_name) != (first, last):
                plan.name_matches.append(
                    {
                        "termin_app": full,
                        "unterlagen": f"{m.first_name} {m.last_name}",
                        "art": how,
                    }
                )
                old = f"{m.first_name} {m.last_name}"
                m.notes = _join(
                    [m.notes, f"In den Papierunterlagen als „{old}“ ({how})."], "\n"
                )
                m.first_name, m.last_name = first, last
            m.is_active = True
            m.registers = member_of.get(full, [])
            continue
        counter += 1
        plan.musicians.append(
            PlannedMusician(
                key=f"A{counter:03d}",
                first_name=first,
                last_name=last,
                phone=None,
                is_extern=False,
                notes="Aus der Musikerliste der Termin-App; in den "
                "Inventar-Unterlagen nicht gefunden.",
                refs=[],
                is_active=True,
                registers=member_of.get(full, []),
            )
        )
    for full, regs in member_of.items():
        if full not in names:
            continue
        if not regs:
            plan.warn(f"aktive_musiker/{full}", "ohne Register")


# Registers whose members normally have no club instrument.
NO_INSTRUMENT_REGISTERS = {
    "Schlagwerk",
    "Marketenderinnen",
    "Kapellmeister / Stabführer",
}


def active_without_instrument(plan: Plan) -> list[PlannedMusician]:
    """Active musicians in an instrument register with neither an active loan
    nor a private instrument in the records."""
    loaned = {x.musician_key for x in plan.loans if x.end is None}
    owners = {i.owner for i in plan.items}
    out = []
    for m in plan.musicians:
        if not m.is_active or m.key in loaned:
            continue
        if f"{m.first_name} {m.last_name}" in owners:
            continue
        if not set(m.registers) - NO_INSTRUMENT_REGISTERS:
            continue
        out.append(m)
    return out


def _page_index(root: Path) -> dict[str, str]:
    """page_id -> "Format (gedruckter Titel)" for every transcribed page."""
    index: dict[str, str] = {}
    for page in root.glob("*/roh/*.json"):
        data = _load_json(page)
        if "page_id" not in data:
            continue
        fmt = data.get("format", {}).get("id")
        name = FORMAT_NAMES.get(fmt, fmt or "?")
        title = " ".join((data.get("gedruckter_titel") or "").split())
        if title and title.lower() not in name.lower():
            name = f"{name}: {title[:60]}"
        index[data["page_id"]] = name
    return index


def _describe_source(source: str, index: dict[str, str]) -> str:
    page, _, anchor = source.partition("#")
    where = ""
    if anchor:
        m = re.match(r"^([zb])(\d+)$", anchor)
        room = re.match(r"^standort(\d+)/z(\d+)$", anchor)
        if room:
            where = f", Standort {room[1]}, Zeile {room[2]}"
        elif m:
            where = f", {'Zeile' if m[1] == 'z' else 'Block'} {m[2]}"
        elif anchor.isdigit():
            where = f", Zeile {anchor}"
        else:
            where = f", Eintrag {anchor}"
    return f"{page}{where} – {index.get(page, 'Seite')}"


def _booking_notes(root: Path) -> dict[str, list[str]]:
    """Instrument key -> notes about purchase bookings (applied or suggested)."""
    path = root / "_gesamt" / "beleg_zuordnung.json"
    if not path.exists():
        return {}
    out: dict[str, list[str]] = {}
    for z in _load_json(path).get("zuordnungen", []):
        if not z.get("instrument"):
            continue
        amount = z.get("ausgabe") or z.get("einnahme")
        head = (
            f"Buchung {z['quelle']} ({z.get('datum')}, „{z.get('text')}“, "
            f"{z.get('firma') or '–'}, {amount} {z.get('waehrung') or 'ATS'}; "
            f"Zuordnung {z.get('sicherheit')}, Art {z.get('art')})"
        )
        v = z.get("vorschlag") or {}
        proposal = ", ".join(f"{k} = {val}" for k, val in v.items() if val)
        if z.get("sicherheit") == "unsicher":
            text = f"{head}. Korrekturvorschlag (nicht übernommen): {proposal or '–'}"
        elif z.get("art") == "kauf":
            text = f"{head}. Übernommen: {proposal or 'bestätigt die Daten'}"
        else:
            text = f"{head}. Nur als Quelle vermerkt"
        if z.get("begruendung"):
            text += f". Begründung: {z['begruendung']}"
        if z.get("widerspruch"):
            text += f". Widerspruch: {z['widerspruch']}"
        out.setdefault(z["instrument"], []).append(text)
    return out


def build_plan(
    root: Path,
    short_codes: dict[str, str],
    today: date | None = None,
    active_list: Path | None = None,
    register_labels: set[str] | None = None,
) -> Plan:
    """Build the import plan from the extraction folder ``root``.

    ``short_codes`` maps instrument-type labels to their short codes (see
    :func:`load_short_codes`). ``active_list`` is the scheduling-app export of
    the active musicians grouped by register (``register_labels`` = registers
    known to the database)."""
    today = today or date.today()
    plan = Plan()
    register = _register_names(root)
    pages = _page_index(root)
    bookings = _booking_notes(root)

    # --- musicians (cross-folder list) -----------------------------------------
    people = _load_json(root / "_gesamt" / "musiker.json")
    local_to_global: dict[str, str] = {}
    for p in people["musiker"]:
        first = (p.get("vorname") or "").strip()
        last = (p.get("nachname") or "").strip()
        if p.get("namenszusatz"):
            first = f"{first} {p['namenszusatz']}".strip()
        notes = []
        variants = [v for v in p.get("varianten", []) if v not in (f"{first} {last}",)]
        if variants:
            notes.append("Schreibweisen in den Unterlagen: " + ", ".join(variants))
        if len(p.get("telefone_alle", [])) > 1:
            notes.append("Weitere Telefonnummern: " + ", ".join(p["telefone_alle"][1:]))
        if p.get("status") != "sicher":
            notes.append(f"Zuordnung {p.get('status')} (Import aus Papierunterlagen)")
        plan.musicians.append(
            PlannedMusician(
                key=p["id"],
                first_name=first[:100],
                last_name=last[:100],
                phone=(p.get("telefone_alle") or [None])[0],
                is_extern=bool(p.get("extern")),
                notes="\n".join(notes) or None,
                refs=p["vorkommen"],
            )
        )
        for ref in p["vorkommen"]:
            local_to_global[ref] = p["id"]
        if not first and not last:
            plan.warn(p["id"], "Musiker ohne Namen")
    excluded = {e["vorkommen"]: e["grund"] for e in people.get("ausgeschlossen", [])}
    if active_list is not None:
        _merge_active_list(plan, active_list, register_labels or set())

    # --- instruments ------------------------------------------------------------
    raw_loans: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    # Room lists come last so that their instruments get numbers after the
    # instruments of the register folders (existing numbers stay stable).
    folders = sorted(
        root.glob("*/zusammenfuehrung.json"),
        key=lambda zf: (zf.parent.name == "Allgemeines_Inventar", zf.parent.name),
    )
    for zf in folders:
        folder = zf.parent.name
        data = _load_json(zf)
        local_musicians = {m["id"]: m for m in data.get("musiker", [])}
        for inst in data.get("instrumente", []):
            key = f"{folder}/{inst['id']}"
            if inst.get("dublette_von"):
                plan.skip(key, f"Dublette von {inst['dublette_von']}")
                continue
            if inst.get("import") is False:
                plan.skip(
                    key, inst.get("import_grund") or "als nicht importieren markiert"
                )
                continue
            planned = _plan_item(
                plan,
                folder,
                key,
                inst,
                local_musicians,
                local_to_global,
                register,
                root=root,
                pages=pages,
                bookings=bookings.get(key, []),
            )
            if planned is None:
                continue
            plan.items.append(planned)
            for loan in data.get("leihen", []):
                if loan["instrument"] == inst["id"]:
                    raw_loans.append((key, loan, inst))
        for inv in data.get("rechnungen", []):
            _plan_invoices(plan, root, folder, inv)
        for obj in data.get("objekte", []):
            planned = _plan_object(plan, folder, obj, pages, short_codes)
            if planned is not None:
                plan.items.append(planned)
        for left in data.get("nicht_uebernommen", []):
            plan.skip(
                left.get("quelle", folder),
                f"{left.get('wie_geschrieben')}: {left.get('grund')}",
            )

    _assign_numbers(plan, short_codes)
    _attach_photos(plan, root)
    _plan_loans(plan, raw_loans, local_to_global, excluded, today)
    return plan


def _plan_item(
    plan: Plan,
    folder: str,
    key: str,
    inst: dict[str, Any],
    local_musicians: dict[str, dict[str, Any]],
    local_to_global: dict[str, str],
    register: dict[str, str],
    *,
    root: Path | None = None,
    pages: dict[str, str] | None = None,
    bookings: list[str] | None = None,
) -> PlannedItem | None:
    pages = pages or {}
    type_label = "Schlagwerk" if folder == "Schlagwerk" else map_type(inst.get("typ"))
    if type_label is None:
        plan.skip(key, f"Instrumententyp „{inst.get('typ')}“ nicht zuordenbar")
        return None
    if re.search(r"klarinette in c\b", (inst.get("typ") or "").lower()):
        plan.warn(
            key, "Kein Typ „Klarinette in C“ vorhanden, als „Klarinette in B“ erfasst"
        )

    paper = inst.get("inventar_nr") or inst.get("inventar_nr_alt")
    parsed = parse_inventory_nr(paper)
    notes: list[str | None] = []
    if paper:
        notes.append(f"Inventarnummer auf Papier: {paper}")

    # owner
    eigentum = inst.get("eigentum")
    if eigentum == "privat":
        ref = inst.get("privat_eigentuemer")
        person = local_musicians.get(ref or "") or {}
        name = f"{person.get('vorname') or ''} {person.get('nachname') or ''}"
        owner = name.strip() or "Privat"
        if ref and f"{folder}/{ref}" not in local_to_global:
            plan.warn(key, f"Privateigentümer {ref} nicht in der Musikerliste")
    elif eigentum == "musikverein":
        owner = CLUB_OWNER
    elif eigentum == "fremd" and inst.get("eigentuemer"):
        owner = inst["eigentuemer"]  # e.g. the parish, documented on the photo page
    else:
        owner = UNCLEAR_OWNER
        plan.warn(key, "Eigentum unklar (Verein oder privat?)")

    storage = _storage_for(
        inst, register.get(f"{parsed[0]} {parsed[1]}") if parsed else None
    )
    if inst.get("lagerort_ms"):
        storage = STORAGE_MS

    # purchase
    acq_date, _ = parse_date(inst.get("erworben_am"))
    cost = parse_amount(inst.get("kaufpreis"))
    currency = inst.get("waehrung") if cost is not None else None
    if cost is not None and currency not in ("EUR", "ATS"):
        currency = "ATS" if acq_date and acq_date.year < 2002 else "EUR"
        plan.warn(key, f"Währung angenommen: {currency}")
    if inst.get("kaufpreis") is not None and cost is None:
        notes.append(f"Kaufpreis lt. Unterlagen: {inst['kaufpreis']}")

    year = parse_year(inst.get("baujahr"))
    if year is not None and year < 1900:
        notes.append(f"Baujahr lt. Unterlagen {inst['baujahr']} (unplausibel)")
        year = None

    label = _join([inst.get("typ"), inst.get("modell")], " ")
    particularities = _join(
        [
            inst.get("besonderheiten"),
            ("Zubehör: " + ", ".join(inst["zubehoer"]))
            if inst.get("zubehoer")
            else None,
        ]
    )
    if inst.get("status") and inst["status"] != "sicher":
        plan.warn(key, f"Instrument-Status {inst['status']}")
        notes.append(f"Datenlage: {inst['status']} (Import aus Papierunterlagen)")
    if inst.get("notiz"):
        notes.append(inst["notiz"])
    repairs = inst.get("reparaturen") or []
    if repairs:
        notes.append("\nReparaturen:")
        notes += [f"- {r.get('datum') or '?'}: {r.get('text')}" for r in repairs]
    conflicts = inst.get("konflikte") or []
    if conflicts:
        notes.append("\nWidersprüche zwischen den Unterlagen:")
        notes += [f"- {c}" for c in conflicts]
    if bookings:
        notes.append("\nKaufbuchungen (Belegliste):")
        notes += [f"- {b}" for b in bookings]

    sources = list(
        dict.fromkeys(
            s if "/" in s.split("#")[0] else f"{folder}/{s}"
            for s in inst.get("quellen", [])
        )
    )
    notes.append("\nHerkunft der Daten (alle Fundstellen in den Altdaten):")
    notes += [f"- {_describe_source(src, pages)}" for src in sources]

    scans: list[dict[str, Any]] = []
    if root is not None:
        for page in dict.fromkeys(src.split("#")[0] for src in sources):
            folder_part, _, stem = page.rpartition("/")
            image = root / folder_part / "seiten" / f"{stem}.png"
            if image.exists():
                scans.append(
                    {"path": image, "caption": f"Scan {page} – {pages.get(page, '')}"}
                )
    return PlannedItem(
        key=key,
        type_label=type_label,
        prefix="",  # set in _assign_numbers from the type's short code
        inventory_nr=parsed[1] if parsed else None,
        paper_nr=f"{parsed[0]} {parsed[1]}" if parsed else None,
        label=_clip(label or type_label, 200),
        manufacturer=_clip(inst["hersteller"], 100) if inst.get("hersteller") else None,
        serial_nr=_clip(str(inst["seriennummer"]), 100)
        if inst.get("seriennummer")
        else None,
        construction_year=year,
        acquisition_date=acq_date,
        acquisition_cost=cost,
        currency=currency,
        distributor=_clip(inst["erworben_ueber"], 100)
        if inst.get("erworben_ueber")
        else None,
        container=_clip(inst["behaelter"], 100) if inst.get("behaelter") else None,
        particularities=_clip(particularities, 500) if particularities else None,
        owner=_clip(owner, 100),
        storage_location=storage,
        notes=_join(notes, "\n"),
        sources=sources,
        scans=scans,
    )


def _plan_object(
    plan: Plan,
    folder: str,
    obj: dict[str, Any],
    pages: dict[str, str],
    short_codes: dict[str, str],
) -> PlannedItem | None:
    """An entry of a room/equipment list (general item, clothing, instrument)."""
    key = f"{folder}/{obj['id']}"
    category = obj.get("kategorie") or "general_item"
    type_label = ""
    if category == "instrument":
        type_label = obj.get("instrumententyp") or ""
        if type_label not in short_codes:
            mapped = map_type(type_label)
            if mapped is None:
                plan.warn(
                    key, f"Instrumententyp „{type_label}“ unbekannt, als Allgemeines"
                )
                category = "general_item"
            else:
                type_label = mapped
    clothing_type = obj.get("kleidungstyp") if category == "clothing" else None
    if category == "clothing" and not clothing_type:
        plan.warn(key, "Kleidung ohne Kleidungstyp, als Allgemeines")
        category = "general_item"
    notes: list[str | None] = [obj.get("notiz")]
    if obj.get("zustand"):
        notes.append(f"Vermerk in der Liste: {obj['zustand']}")
    if obj.get("wie_geschrieben"):
        notes.append(f"In der Liste: „{obj['wie_geschrieben']}“")
    source = obj.get("quelle")
    sources = [source] if source else []
    notes.append("\nHerkunft der Daten:")
    notes += [f"- {_describe_source(src, pages)}" for src in sources]
    quantity = obj.get("menge") or 1
    if not isinstance(quantity, int) or quantity < 1:
        plan.warn(key, f"Menge „{quantity}“ ungültig, 1 angenommen")
        quantity = 1
    return PlannedItem(
        key=key,
        type_label=type_label,
        prefix="",
        inventory_nr=None,
        paper_nr=None,
        label=_clip(obj.get("bezeichnung") or obj.get("wie_geschrieben") or "?", 200),
        manufacturer=None,
        serial_nr=None,
        construction_year=None,
        acquisition_date=None,
        acquisition_cost=None,
        currency=None,
        distributor=None,
        container=None,
        particularities=None,
        owner=_clip(obj.get("eigentuemer") or CLUB_OWNER, 100),
        storage_location=_clip(obj["lagerort"], 200) if obj.get("lagerort") else None,
        notes=_join(notes, "\n"),
        sources=sources,
        category=category,
        quantity=quantity,
        clothing_type=clothing_type,
    )


def _assign_numbers(plan: Plan, short_codes: dict[str, str]) -> None:
    """Give every item a (prefix, number). Paper numbers are kept when their
    prefix matches the type's short code; the rest get the next free number."""
    taken: dict[str, set[int]] = {}
    for item in plan.items:
        if item.category != "instrument":
            item.prefix = CATEGORY_PREFIXES[item.category]
        else:
            item.prefix = short_codes[item.type_label]
        if item.inventory_nr is not None:
            paper_prefix = (item.paper_nr or "").split(" ")[0]
            if paper_prefix != item.prefix:
                plan.warn(
                    item.key,
                    f"Papier-Nr. {item.paper_nr} passt nicht zum Kürzel {item.prefix}, "
                    "neue Nummer vergeben",
                )
                item.inventory_nr = None
            elif item.inventory_nr in taken.setdefault(item.prefix, set()):
                plan.warn(item.key, f"{item.display_nr} doppelt, neue Nummer vergeben")
                item.inventory_nr = None
            else:
                taken[item.prefix].add(item.inventory_nr)
    for item in plan.items:
        if item.inventory_nr is None:
            used = taken.setdefault(item.prefix, set())
            item.inventory_nr = (max(used) if used else 0) + 1
            used.add(item.inventory_nr)


def _attach_photos(plan: Plan, root: Path) -> None:
    by_paper = {(i.key.split("/")[0], i.paper_nr): i for i in plan.items if i.paper_nr}
    for index in sorted(root.glob("*/fotos/fotos.json")):
        folder = index.parent.parent.name
        for page, photos in _load_json(index).items():
            if (folder, page) in PHOTO_EXCLUDE:
                plan.skip(
                    f"{folder}/{page}", "Fotos nicht übernommen (siehe PHOTO_EXCLUDE)"
                )
                continue
            for photo in photos:
                nr = parse_inventory_nr(photo.get("inventar_nr"))
                item = by_paper.get((folder, f"{nr[0]} {nr[1]}")) if nr else None
                if item is None:
                    plan.skip(
                        f"{folder}/fotos/{photo['datei']}",
                        f"kein Instrument mit Nummer {photo.get('inventar_nr')}",
                    )
                    continue
                item.photos.append(
                    {
                        "path": index.parent / photo["datei"],
                        "motiv": photo.get("motiv") or "",
                    }
                )


def _plan_loans(
    plan: Plan,
    raw_loans: list[tuple[str, dict[str, Any], dict[str, Any]]],
    local_to_global: dict[str, str],
    excluded: dict[str, str],
    today: date,
) -> None:
    items = {i.key: i for i in plan.items}
    per_item: dict[str, list[dict[str, Any]]] = {}
    for item_key, loan, inst in raw_loans:
        folder = item_key.split("/")[0]
        where = f"{item_key} ← {loan['musiker']}"
        ref = f"{folder}/{loan['musiker']}"
        if ref in excluded:
            plan.skip(where, f"Leihnehmer ist keine Person: {excluded[ref]}")
            continue
        if ref not in local_to_global:
            plan.skip(where, "Musiker nicht in der Gesamtliste")
            continue
        item = items.get(item_key)
        if item is None:
            continue
        note = loan.get("notiz") or ""
        if (
            loan.get("status") == "offen"
            and "Vereinseigentum" in note
            and item.owner == UNCLEAR_OWNER
        ):
            plan.skip(where, "Leihe hängt vom ungeklärten Eigentum ab")
            continue
        start, _ = parse_date(loan.get("von"))
        end, _ = parse_date(loan.get("bis"))
        per_item.setdefault(item_key, []).append(
            {
                "musician": local_to_global[ref],
                "start": start,
                "end": end,
                "status": loan.get("status"),
                "where": where,
                "sources": loan.get("quellen", []),
                "note": note or None,
            }
        )

    for item_key, loans in per_item.items():
        item = items[item_key]
        # an uncertain loan never pushes out a confirmed open one
        confirmed_open = [
            x for x in loans if x["end"] is None and x["status"] != "offen"
        ]
        kept = []
        for x in loans:
            if (
                x["status"] == "offen"
                and x["end"] is None
                and confirmed_open
                and x not in confirmed_open
            ):
                plan.skip(x["where"], "unsichere Leihe neben bestätigter aktiver Leihe")
                continue
            if (
                x["status"] == "offen"
                and x["start"] is None
                and x["end"] is None
                and x is not loans[-1]
            ):
                plan.skip(x["where"], "unsichere Leihe ohne Datum (nicht die letzte)")
                continue
            kept.append(x)
        # close superseded open-ended loans with the start of the next one
        for i, x in enumerate(kept[:-1]):
            if x["end"] is None:
                nxt = kept[i + 1]["start"]
                if nxt is not None:
                    x["end"] = nxt
                    plan.warn(
                        x["where"],
                        f"Ende aus Beginn der nächsten Leihe abgeleitet ({nxt})",
                    )
                elif x["start"] is not None:
                    # keep the loan as history; the end is simply not documented
                    x["end"] = x["start"]
                    x["end_unknown"] = True
                    plan.warn(x["where"], "Ende unbekannt (Nachfolger ohne Datum)")
                else:
                    plan.skip(
                        x["where"],
                        "weder Beginn noch Ende bekannt, Nachfolger vorhanden",
                    )
                    x["drop"] = True
        for x in kept:
            if x.get("drop"):
                continue
            active = x["end"] is None
            if active and item.storage_location in (STORAGE_MS, STORAGE_ARCHIV):
                plan.skip(
                    x["where"],
                    f"keine aktive Leihe bei Lagerort „{item.storage_location}“",
                )
                continue
            if active and item.owner not in (CLUB_OWNER,):
                plan.skip(x["where"], f"keine Leihe: Eigentümer „{item.owner}“")
                continue
            start = x["start"]
            if start is None:
                start = x["end"] or today
                plan.warn(x["where"], f"Leihbeginn unbekannt, {start} eingetragen")
                item.notes += f"\nLeihbeginn unbekannt (Import: {start})"
            if x["end"] is not None and x["end"] < start:
                plan.warn(
                    x["where"],
                    f"Rückgabe {x['end']} vor Beginn {start}, Rückgabe = Beginn",
                )
                x["end"] = start
            if x.get("end_unknown"):
                name = next(m for m in plan.musicians if m.key == x["musician"])
                item.notes += (
                    f"\nLeihe an {name.first_name} {name.last_name} ab {start:%Y}: "
                    "Ende unbekannt"
                )
            if x["status"] == "offen":
                plan.warn(x["where"], "unsichere Leihe übernommen")
            plan.loans.append(
                PlannedLoan(
                    item_key, x["musician"], start, x["end"], x["note"], x["sources"]
                )
            )


def _plan_invoices(plan: Plan, root: Path, folder: str, inv: dict[str, Any]) -> None:
    where = f"{folder}/{inv.get('id')}"
    amount = parse_amount(inv.get("betrag"))
    issued, _ = parse_date(inv.get("datum"))
    if amount is None or issued is None or not inv.get("instrument"):
        plan.skip(where, "Beleg ohne Betrag, Datum oder Instrument")
        return
    currency = inv.get("waehrung") or ("ATS" if issued.year < 2002 else "EUR")
    art = (inv.get("art") or "rechnung").capitalize()
    title = _join(
        [art, inv.get("aussteller"), inv.get("nummer") and f"Nr. {inv['nummer']}"], " "
    )
    positions = inv.get("positionen") or []
    description = _join(
        [
            f"Betrag {inv.get('betrag_art')}" if inv.get("betrag_art") else None,
            "; ".join(str(p) for p in positions) if positions else None,
            inv.get("notiz"),
        ],
        "\n",
    )
    images = []
    for src in inv.get("quellen", []):
        page = src.split("#")[0]
        path = root / (page if "/" in page else f"{folder}/{page}")
        img = path.parent / "seiten" / f"{path.name}.png"
        if img.exists():
            images.append(img)
    for instrument in [inv["instrument"], *inv.get("weitere_instrumente", [])]:
        plan.invoices.append(
            PlannedInvoice(
                item_key=f"{folder}/{instrument}",
                title=_clip(title, 200),
                amount=amount,
                currency=currency,
                date_issued=issued,
                issuer=_clip(inv["aussteller"], 100) if inv.get("aussteller") else None,
                issuer_address=_clip(inv["aussteller_adresse"], 200)
                if inv.get("aussteller_adresse")
                else None,
                description=_clip(description, 500) if description else None,
                page_images=images,
            )
        )


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def _save_scan(src: Path, dest: Path) -> None:
    """Store a scanned page as JPEG (the 150-dpi PNGs are ~1 MB each)."""
    from PIL import Image

    with Image.open(src) as img:
        img.convert("RGB").save(dest, "JPEG", quality=82, optimize=True)


async def load_register_labels(db: AsyncSession) -> set[str]:
    return set((await db.execute(select(Register.label))).scalars())


async def load_short_codes(db: AsyncSession) -> dict[str, str]:
    rows = (
        await db.execute(select(InstrumentType.label, InstrumentType.label_short))
    ).all()
    return {label: short.strip().upper() for label, short in rows}


async def wipe_inventory(db: AsyncSession) -> dict[str, int]:
    """Delete all items (every category), musicians, loans, invoices and image
    rows. Upload files are the caller's business (move them aside first)."""
    counts = {}
    await db.execute(delete(musician_registers))
    for model in (
        Loan,
        ItemImage,
        ItemInvoice,
        InstrumentDetail,
        InventoryItem,
        Musician,
    ):
        result = await db.execute(delete(model))
        counts[model.__tablename__] = result.rowcount or 0  # type: ignore[attr-defined]
    return counts


async def restrict_to_folder(db: AsyncSession, plan: Plan, folder: str) -> Plan:
    """Plan for adding one folder to an existing inventory: only that folder's
    items (no musicians, loans or invoices), numbered after the numbers already
    in the database. Items whose source is already cited in an existing item's
    notes count as imported and are skipped, so the step can be repeated."""
    out = Plan(warnings=plan.warnings, skipped=plan.skipped)
    existing_notes = [
        n for n in (await db.execute(select(InventoryItem.notes))).scalars() if n
    ]
    next_nr: dict[tuple[str, str], int] = {}
    for item in plan.items:
        if not item.key.startswith(f"{folder}/"):
            continue
        marker = (
            "- " + _describe_source(item.sources[0], {}).split(" – ")[0] + " – "
            if item.sources
            else None
        )
        if marker and any(marker in n for n in existing_notes):
            out.skip(item.key, "bereits importiert (Quelle in vorhandener Notiz)")
            continue
        slot = (item.category, item.prefix)
        if slot not in next_nr:
            current = await db.scalar(
                select(func.max(InventoryItem.inventory_nr)).where(
                    InventoryItem.category == item.category,
                    InventoryItem.number_prefix == item.prefix,
                )
            )
            next_nr[slot] = (current or 0) + 1
        item.inventory_nr = next_nr[slot]
        next_nr[slot] += 1
        out.items.append(item)
    return out


async def apply_plan(db: AsyncSession, plan: Plan, uploads: Path) -> dict[str, Any]:
    """Write the plan. The caller commits (or rolls back)."""
    types = {t.label: t for t in (await db.execute(select(InstrumentType))).scalars()}
    currencies = {
        c.abbreviation: c for c in (await db.execute(select(Currency))).scalars()
    }
    cur_ids = {
        code: currencies[abbr].id
        for code, abbr in (("EUR", "€"), ("ATS", "ATS"))
        if abbr in currencies
    }
    registers = {r.label: r for r in (await db.execute(select(Register))).scalars()}

    musicians: dict[str, Musician] = {}
    for pm in plan.musicians:
        m = Musician(
            first_name=pm.first_name,
            last_name=pm.last_name,
            phone=pm.phone,
            is_extern=pm.is_extern,
            is_active=pm.is_active,
            notes=pm.notes,
        )
        m.registers = [registers[label] for label in pm.registers]
        db.add(m)
        musicians[pm.key] = m
    await db.flush()

    items: dict[str, InventoryItem] = {}
    written: list[Path] = []
    report_items = []
    clothing_types = {
        t.label: t for t in (await db.execute(select(ClothingType))).scalars()
    }
    for pi in plan.items:
        item = InventoryItem(
            category=pi.category,
            number_prefix=pi.prefix,
            inventory_nr=pi.inventory_nr,
            label=pi.label,
            quantity=pi.quantity,
            manufacturer=pi.manufacturer,
            acquisition_date=pi.acquisition_date,
            acquisition_cost=pi.acquisition_cost,
            currency_id=cur_ids[pi.currency] if pi.currency else None,
            owner=pi.owner,
            notes=pi.notes,
            storage_location=pi.storage_location,
        )
        db.add(item)
        await db.flush()
        if pi.category == "instrument":
            db.add(
                InstrumentDetail(
                    item_id=item.id,
                    instrument_type_id=types[pi.type_label].id,
                    serial_nr=pi.serial_nr,
                    construction_year=pi.construction_year,
                    distributor=pi.distributor,
                    container=pi.container,
                    particularities=pi.particularities,
                )
            )
        elif pi.category == "clothing":
            ctype = clothing_types.get(pi.clothing_type or "")
            if ctype is None:
                ctype = ClothingType(label=pi.clothing_type)
                db.add(ctype)
                await db.flush()
                clothing_types[ctype.label] = ctype
            db.add(ClothingDetail(item_id=item.id, clothing_type_id=ctype.id))
        items[pi.key] = item
        profile = next(
            (p for p in pi.photos if "gesamt" in p["motiv"].lower()),
            pi.photos[0] if pi.photos else None,
        )
        for photo in pi.photos:
            name = f"{uuid.uuid4().hex}{photo['path'].suffix.lower()}"
            dest = uploads / "images" / str(item.id) / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(photo["path"], dest)
            written.append(dest)
            db.add(
                ItemImage(
                    item_id=item.id,
                    filename=name,
                    is_profile=photo is profile,
                    kind="foto",
                    caption=photo["motiv"] or None,
                )
            )
        for scan in pi.scans:
            name = f"{uuid.uuid4().hex}.jpg"
            dest = uploads / "images" / str(item.id) / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            _save_scan(scan["path"], dest)
            written.append(dest)
            db.add(
                ItemImage(
                    item_id=item.id,
                    filename=name,
                    is_profile=False,
                    kind="scan",
                    caption=_clip(scan["caption"], 300),
                )
            )
        report_items.append(
            {
                "key": pi.key,
                "id": item.id,
                "display_nr": pi.display_nr,
                "label": pi.label,
            }
        )

    for pl in plan.loans:
        db.add(
            Loan(
                item_id=items[pl.item_key].id,
                musician_id=musicians[pl.musician_key].id,
                start_date=pl.start,
                end_date=pl.end,
            )
        )

    invoice_nrs: dict[str, int] = {}
    for inv in plan.invoices:
        target = items.get(inv.item_key)
        if target is None:
            plan.skip(inv.item_key, f"Beleg „{inv.title}“: Instrument nicht importiert")
            continue
        invoice_nrs[inv.item_key] = invoice_nrs.get(inv.item_key, 0) + 1
        filename = None
        if inv.page_images:
            src = inv.page_images[0]
            filename = f"{uuid.uuid4().hex}{src.suffix}"
            dest = uploads / "invoices" / str(target.id) / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            written.append(dest)
        db.add(
            ItemInvoice(
                invoice_nr=invoice_nrs[inv.item_key],
                item_id=target.id,
                title=inv.title,
                amount=inv.amount,
                currency_id=cur_ids[inv.currency],
                date_issued=inv.date_issued,
                description=inv.description,
                invoice_issuer=inv.issuer,
                issuer_address=inv.issuer_address,
                filename=filename,
            )
        )
    await db.flush()
    return {"items": report_items, "files": [str(p) for p in written]}
