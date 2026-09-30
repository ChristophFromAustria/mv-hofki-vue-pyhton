"""Event log: records every change to the audited models while it is saved.

A listener on SQLAlchemy's ``after_flush`` looks at what the flush wrote (new,
changed and deleted rows, with the old and new value of every changed column)
and inserts one ``events`` row per record and action — so no service can
forget to log. Changes that bypass the ORM (link tables written with core
statements, bulk deletes) are recorded explicitly with ``record()``.

Who did it comes from ``actor_var`` (the Cloudflare Access e-mail, set per
request by ``AuditActorMiddleware``); where from from ``source_var`` (web,
ki-import, import, system). ``audit_context(enabled=False)`` switches logging
off, e.g. for seed data.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import event as sa_event
from sqlalchemy import insert, inspect
from sqlalchemy.orm import Session

from mv_hofki.models.clothing_detail import ClothingDetail
from mv_hofki.models.clothing_type import ClothingType
from mv_hofki.models.currency import Currency
from mv_hofki.models.event import Event
from mv_hofki.models.general_item_category import GeneralItemCategory
from mv_hofki.models.instrument_detail import InstrumentDetail
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.item_image import ItemImage
from mv_hofki.models.item_invoice import ItemInvoice
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.models.register import Register
from mv_hofki.models.sheet_music_detail import SheetMusicDetail
from mv_hofki.models.sheet_music_genre import SheetMusicGenre
from mv_hofki.schemas.inventory_item import format_display_nr

actor_var: ContextVar[str | None] = ContextVar("audit_actor", default=None)
source_var: ContextVar[str] = ContextVar("audit_source", default="web")
enabled_var: ContextVar[bool] = ContextVar("audit_enabled", default=True)


@contextmanager
def audit_context(
    *,
    actor: str | None = None,
    source: str | None = None,
    enabled: bool | None = None,
) -> Iterator[None]:
    """Set who/where for the events recorded inside the block."""
    tokens: list[tuple[ContextVar[Any], Token[Any]]] = []
    if actor is not None:
        tokens.append((actor_var, actor_var.set(actor)))
    if source is not None:
        tokens.append((source_var, source_var.set(source)))
    if enabled is not None:
        tokens.append((enabled_var, enabled_var.set(enabled)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


class AuditActorMiddleware:
    """Pure ASGI middleware: the request's Cloudflare Access e-mail becomes the
    actor of every event recorded while handling it."""

    HEADER = b"cf-access-authenticated-user-email"

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        email = next(
            (v.decode() for k, v in scope.get("headers", []) if k == self.HEADER),
            None,
        )
        token = actor_var.set(email or None)
        try:
            await self.app(scope, receive, send)
        finally:
            actor_var.reset(token)


# ---------------------------------------------------------------------------
# What is audited
# ---------------------------------------------------------------------------


# Labels are looked up also for rows in the trash (events about them).
_WITH_DELETED = {"include_deleted": True}


def item_label(session: Session, item_id: int | None) -> str:
    item = (
        session.get(InventoryItem, item_id, execution_options=_WITH_DELETED)
        if item_id is not None
        else None
    )
    if item is None:
        return f"Gegenstand {item_id}"
    return f"{format_display_nr(item.number_prefix, item.inventory_nr)} {item.label}"


def musician_label(session: Session, musician_id: int | None) -> str:
    m = (
        session.get(Musician, musician_id, execution_options=_WITH_DELETED)
        if musician_id is not None
        else None
    )
    return f"{m.first_name} {m.last_name}" if m else f"Musiker {musician_id}"


def _label_of(model: Any, attr: str = "label") -> Callable[[Session, Any], Any]:
    def resolve(session: Session, value: Any) -> Any:
        if value is None:
            return None
        row = session.get(model, value, execution_options=_WITH_DELETED)
        return getattr(row, attr) if row is not None else value

    return resolve


ITEM_FIELDS = {
    "label": "Bezeichnung",
    "quantity": "Menge",
    "manufacturer": "Hersteller",
    "acquisition_date": "Anschaffungsdatum",
    "acquisition_cost": "Anschaffungskosten",
    "currency_id": "Währung",
    "owner": "Eigentümer",
    "notes": "Notizen",
    "storage_location": "Lagerort",
    "number_prefix": "Nummernkreis",
    "inventory_nr": "Inventarnummer",
    # details
    "instrument_type_id": "Typ",
    "serial_nr": "Seriennummer",
    "construction_year": "Baujahr",
    "distributor": "Händler",
    "container": "Behältnis",
    "particularities": "Besonderheiten",
    "clothing_type_id": "Typ",
    "size": "Größe",
    "gender": "Geschlecht",
    "composer": "Komponist",
    "arranger": "Arrangeur",
    "difficulty": "Schwierigkeitsgrad",
    "genre_id": "Gattung",
}

MUSICIAN_FIELDS = {
    "first_name": "Vorname",
    "last_name": "Nachname",
    "phone": "Telefon",
    "email": "E-Mail",
    "street_address": "Adresse",
    "postal_code": "PLZ",
    "city": "Ort",
    "is_extern": "Extern",
    "is_active": "Aktiv",
    "notes": "Notizen",
    "registers": "Register",
}

LOAN_FIELDS = {
    "start_date": "Ausgeliehen am",
    "end_date": "Zurückgegeben am",
    "due_date": "Rückgabe geplant",
    "notes": "Notiz",
}

INVOICE_FIELDS = {
    "title": "Bezeichnung",
    "amount": "Betrag",
    "currency_id": "Währung",
    "date_issued": "Datum",
    "description": "Beschreibung",
    "invoice_issuer": "Aussteller",
    "issuer_address": "Adresse des Ausstellers",
    "filename": "Datei",
}

LOOKUP_FIELDS = {
    "label": "Bezeichnung",
    "label_short": "Kürzel",
    "abbreviation": "Abkürzung",
    "sort_order": "Reihenfolge",
    "expects_instrument": "Mit Instrument",
}

FK_LABELS: dict[str, Callable[[Session, Any], Any]] = {
    "currency_id": _label_of(Currency, "abbreviation"),
    "instrument_type_id": _label_of(InstrumentType),
    "clothing_type_id": _label_of(ClothingType),
    "genre_id": _label_of(SheetMusicGenre),
}


@dataclass(frozen=True)
class Spec:
    entity_type: str
    fields: dict[str, str]
    label: Callable[[Session, Any], str]
    entity_id: Callable[[Any], int | None] = lambda obj: obj.id
    item_id: Callable[[Any], int | None] = lambda obj: None
    musician_id: Callable[[Any], int | None] = lambda obj: None
    # Detail rows are logged as changes of their item; their own insert and
    # delete happen together with the item's and are not logged separately.
    detail: bool = False
    actions: dict[str, str] = field(default_factory=dict)


def _detail_spec() -> Spec:
    return Spec(
        entity_type="item",
        fields=ITEM_FIELDS,
        label=lambda s, o: item_label(s, o.item_id),
        entity_id=lambda o: o.item_id,
        item_id=lambda o: o.item_id,
        detail=True,
    )


def _lookup_spec(entity_type: str, label_attr: str = "label") -> Spec:
    return Spec(
        entity_type=entity_type,
        fields=LOOKUP_FIELDS,
        label=lambda s, o: getattr(o, label_attr),
    )


SPECS: dict[type, Spec] = {
    InventoryItem: Spec(
        entity_type="item",
        fields=ITEM_FIELDS,
        label=lambda s, o: (
            f"{format_display_nr(o.number_prefix, o.inventory_nr)} {o.label}"
        ),
        item_id=lambda o: o.id,
    ),
    InstrumentDetail: _detail_spec(),
    ClothingDetail: _detail_spec(),
    SheetMusicDetail: _detail_spec(),
    Musician: Spec(
        entity_type="musician",
        fields=MUSICIAN_FIELDS,
        label=lambda s, o: f"{o.first_name} {o.last_name}",
        musician_id=lambda o: o.id,
    ),
    Loan: Spec(
        entity_type="loan",
        fields=LOAN_FIELDS,
        label=lambda s, o: (
            f"{item_label(s, o.item_id)} an {musician_label(s, o.musician_id)}"
        ),
        item_id=lambda o: o.item_id,
        musician_id=lambda o: o.musician_id,
        actions={"created": "loaned"},
    ),
    ItemInvoice: Spec(
        entity_type="invoice",
        fields=INVOICE_FIELDS,
        label=lambda s, o: f"Rechnung „{o.title}“ zu {item_label(s, o.item_id)}",
        item_id=lambda o: o.item_id,
    ),
    ItemImage: Spec(
        entity_type="image",
        fields={"caption": "Beschriftung", "is_profile": "Profilbild"},
        label=lambda s, o: f"Bild zu {item_label(s, o.item_id)}",
        item_id=lambda o: o.item_id,
        actions={"created": "image_added", "deleted": "image_deleted"},
    ),
    InstrumentType: _lookup_spec("instrument_type"),
    ClothingType: _lookup_spec("clothing_type"),
    Register: _lookup_spec("register"),
    GeneralItemCategory: _lookup_spec("general_item_category"),
    SheetMusicGenre: _lookup_spec("sheet_music_genre"),
    Currency: _lookup_spec("currency"),
}


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


def display_value(value: Any) -> Any:
    """A value as it is stored in an event: dates as dd.mm.yyyy, bools as
    Ja/Nein, lists joined; None stays None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "Ja" if value else "Nein"
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, list | tuple):
        return ", ".join(str(v) for v in value) or None
    return value


def change(field_name: str, label: str, old: Any, new: Any) -> dict[str, Any]:
    return {
        "field": field_name,
        "label": label,
        "old": display_value(old),
        "new": display_value(new),
    }


def _column_changes(session: Session, obj: Any, spec: Spec) -> list[dict[str, Any]]:
    state = inspect(obj)
    out = []
    for name, label in spec.fields.items():
        if name not in state.attrs:
            continue
        hist = state.attrs[name].history
        if not hist.has_changes():
            continue
        if name == "registers":
            before = [r.label for r in (*hist.unchanged, *hist.deleted)]
            after = [r.label for r in (*hist.unchanged, *hist.added)]
            if sorted(before) != sorted(after):
                out.append(change(name, label, before, after))
            continue
        old = hist.deleted[0] if hist.deleted else None
        new = hist.added[0] if hist.added else None
        if old == new:
            continue
        resolve = FK_LABELS.get(name)
        if resolve is not None:
            old, new = resolve(session, old), resolve(session, new)
        out.append(change(name, label, old, new))
    return out


def _row(
    *,
    entity_type: str,
    entity_id: int | None,
    entity_label: str,
    action: str,
    changes: list[dict[str, Any]] | None = None,
    summary: str | None = None,
    item_id: int | None = None,
    musician_id: int | None = None,
) -> dict[str, Any]:
    return {
        "actor": actor_var.get(),
        "source": source_var.get(),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_label": entity_label[:300],
        "action": action,
        "changes": changes or None,
        "summary": summary,
        "item_id": item_id,
        "musician_id": musician_id,
    }


PENDING = "audit_pending"


def _merge(
    pending: dict[tuple, dict[str, Any]], key: tuple, row: dict[str, Any]
) -> None:
    """Fold one flush's event into the transaction's pending events: the same
    record and action again adds its changes (a field changed twice keeps the
    first old and the last new value)."""
    current = pending.get(key)
    if current is None:
        pending[key] = row
        return
    by_field = {c["field"]: c for c in current["changes"] or []}
    for c in row["changes"] or []:
        if c["field"] in by_field:
            by_field[c["field"]]["new"] = c["new"]
        else:
            by_field[c["field"]] = c
    kept = [c for c in by_field.values() if c["old"] != c["new"]]
    current["changes"] = kept or None
    current["entity_label"] = row["entity_label"]


def _collect(session: Session) -> None:
    pending: dict[tuple, dict[str, Any]] = session.info.setdefault(PENDING, {})

    def add(obj: Any, spec: Spec, action: str, changes: list | None) -> None:
        action = spec.actions.get(action, action)
        key = (spec.entity_type, spec.entity_id(obj), action)
        _merge(
            pending,
            key,
            _row(
                entity_type=spec.entity_type,
                entity_id=spec.entity_id(obj),
                entity_label=spec.label(session, obj),
                action=action,
                changes=changes,
                item_id=spec.item_id(obj),
                musician_id=spec.musician_id(obj),
            ),
        )

    for obj in session.new:
        spec = SPECS.get(type(obj))
        if spec is not None and not spec.detail:
            add(obj, spec, "created", None)
    for obj in session.deleted:
        spec = SPECS.get(type(obj))
        if spec is not None and not spec.detail:
            # Deleting a row that can go to the trash is deleting it for good.
            add(obj, spec, "purged" if hasattr(obj, "deleted_at") else "deleted", None)
    for obj in session.dirty:
        spec = SPECS.get(type(obj))
        if spec is None or obj in session.new or obj in session.deleted:
            continue
        if not session.is_modified(obj, include_collections=True):
            continue
        trash = _trash_action(obj)
        if trash is not None:
            add(obj, spec, trash, None)
            continue
        changes = _column_changes(session, obj, spec)
        if not changes:
            continue
        action = "updated"
        if isinstance(obj, Loan) and any(
            c["field"] == "end_date" and c["old"] is None for c in changes
        ):
            action = "returned"
        elif isinstance(obj, ItemImage):
            if any(c["field"] == "is_profile" and c["new"] == "Ja" for c in changes):
                action = "image_profile"
            elif not any(c["field"] == "caption" for c in changes):
                continue  # the old profile picture losing its flag
        add(obj, spec, action, changes)


def _trash_action(obj: Any) -> str | None:
    """ "trashed" / "restored" when this flush moved obj into / out of the trash."""
    if not hasattr(obj, "deleted_at"):
        return None
    hist = inspect(obj).attrs["deleted_at"].history
    if not hist.has_changes():
        return None
    old = hist.deleted[0] if hist.deleted else None
    new = hist.added[0] if hist.added else None
    if old is None and new is not None:
        return "trashed"
    if old is not None and new is None:
        return "restored"
    return None


def _final_rows(pending: dict[tuple, dict[str, Any]]) -> list[dict[str, Any]]:
    # An item created in this transaction: its later changes (detail row,
    # number) are part of "created".
    created = {(k[0], k[1]) for k in pending if k[2] == "created"}
    return [
        row
        for key, row in pending.items()
        if not (key[2] == "updated" and (key[0], key[1]) in created)
        and not (key[2] == "updated" and not row["changes"])
    ]


@sa_event.listens_for(Session, "after_flush")
def _after_flush(session: Session, _flush_context: Any) -> None:
    if enabled_var.get():
        _collect(session)


@sa_event.listens_for(Session, "before_commit")
def _before_commit(session: Session) -> None:
    """Write the transaction's events together, so one save is one event
    even when the service flushed several times."""
    session.flush()  # the last changes may still be pending
    pending = session.info.pop(PENDING, None)
    if pending:
        rows = _final_rows(pending)
        if rows:
            session.connection().execute(insert(Event), rows)


@sa_event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session) -> None:
    session.info.pop(PENDING, None)


def record(
    session: Any,
    *,
    entity_type: str,
    entity_id: int | None,
    entity_label: str,
    action: str,
    changes: list[dict[str, Any]] | None = None,
    summary: str | None = None,
    item_id: int | None = None,
    musician_id: int | None = None,
) -> None:
    """Log an event for a change the flush listener cannot see (link tables,
    bulk statements, summaries). ``session`` may be sync or async; the row is
    written with the session's next flush/commit."""
    if not enabled_var.get():
        return
    session.add(
        Event(
            **_row(
                entity_type=entity_type,
                entity_id=entity_id,
                entity_label=entity_label,
                action=action,
                changes=changes,
                summary=summary,
                item_id=item_id,
                musician_id=musician_id,
            )
        )
    )
