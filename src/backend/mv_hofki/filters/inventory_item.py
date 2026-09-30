"""Filter for GET /items. One class for all four item kinds; ``bind`` rejects
fields and sort keys that do not belong to the requested kind."""

from __future__ import annotations

import re
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import PrivateAttr
from sqlalchemy import (
    ColumnElement,
    Select,
    and_,
    case,
    exists,
    func,
    literal,
    or_,
    select,
)
from sqlalchemy.orm import aliased

from mv_hofki.filters.base import GroupSpec, ListFilter
from mv_hofki.filters.text_search import folded_contains, words_clause
from mv_hofki.models.clothing_detail import ClothingDetail
from mv_hofki.models.clothing_type import ClothingType
from mv_hofki.models.general_item_category import GeneralItemCategory
from mv_hofki.models.general_item_category import general_item_category_links as links
from mv_hofki.models.instrument_detail import InstrumentDetail
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.inventory_item import InventoryItem
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.models.sheet_music_detail import SheetMusicDetail
from mv_hofki.models.sheet_music_genre import SheetMusicGenre

# "TU-0002", "TU-002", "tu 2", "TU2" -> ("TU", 2)
_DISPLAY_NR_RE = re.compile(r"^\s*([^\W\d_]+)\s*-?\s*0*(\d+)\s*$")

CATEGORY_LABELS = {
    "instrument": "Instrumente",
    "clothing": "Kleidung",
    "sheet_music": "Noten",
    "general_item": "Allgemein",
}

_COMMON_FIELDS = {"search", "order_by", "group_by", "bestand"}
_CATEGORY_FIELDS = {
    "instrument": {
        "instrument_type_id__in",
        "status",
        "owner",
        "construction_year__gte",
        "construction_year__lte",
    },
    "clothing": {"clothing_type_id__in", "size", "gender", "status"},
    "sheet_music": {"genre_id__in", "difficulty", "storage_location__ilike"},
    "general_item": {
        "category_id__in",
        "without_category",
        "storage_location__ilike",
        "status",
    },
}
_CATEGORY_SORTS = {
    "instrument": {"number", "type", "manufacturer", "construction_year", "borrower"},
    "clothing": {"number", "type", "size", "borrower"},
    "sheet_music": {"number", "label", "composer"},
    "general_item": {"number", "label", "storage_location", "borrower"},
}


_ROOM = func.nullif(
    func.trim(
        func.substr(
            InventoryItem.storage_location,
            1,
            func.instr(InventoryItem.storage_location + literal(" /"), " /") - 1,
        )
    ),
    "",
)
_OPEN_LOAN = exists().where(Loan.item_id == InventoryItem.id, Loan.end_date.is_(None))


def _borrower_column(column: Any) -> Any:
    """``column`` of the musician holding the item's open loan (NULL if none)."""
    return (
        select(column)
        .join(Loan, Loan.musician_id == Musician.id)
        .where(Loan.item_id == InventoryItem.id, Loan.end_date.is_(None))
        .limit(1)
        .scalar_subquery()
    )


def borrower_matches(word: str) -> ColumnElement[bool]:
    """The musician holding the item's open loan has ``word`` (folded) in
    their name."""
    return (
        exists()
        .where(
            Loan.item_id == InventoryItem.id,
            Loan.end_date.is_(None),
            Loan.musician_id == Musician.id,
        )
        .where(folded_contains(Musician.first_name + " " + Musician.last_name, word))
    )


ITEM_SEARCH_COLUMNS = (
    InventoryItem.label,
    InventoryItem.manufacturer,
    InventoryItem.notes,
)


def number_or_words(
    value: str, words: ColumnElement[bool] | None
) -> ColumnElement[bool] | None:
    """A search text that is an existing inventory number ("TR 6") finds just
    that item; otherwise the word condition applies ("Tuba 2" has no item
    TUBA-0002, so it searches for "tuba" and "2")."""
    nr = display_nr_condition(value)
    if nr is None:
        return words
    if words is None:
        return nr
    other_nr = display_nr_condition(value, aliased(InventoryItem))
    assert other_nr is not None  # same text as nr
    return or_(nr, and_(~exists().where(other_nr), words))


def item_search_clause(value: str) -> ColumnElement[bool] | None:
    """Every word in label, manufacturer, notes or the borrower's name; or the
    whole text as an inventory number ("TU-0002", "tu 2")."""
    return number_or_words(
        value, words_clause(value, ITEM_SEARCH_COLUMNS, extra=(borrower_matches,))
    )


def _join_genre(query: Select) -> Select:
    return query.outerjoin(
        SheetMusicGenre, SheetMusicGenre.id == SheetMusicDetail.genre_id
    )


def _join_categories(query: Select) -> Select:
    return query.outerjoin(links, links.c.item_id == InventoryItem.id).outerjoin(
        GeneralItemCategory, GeneralItemCategory.id == links.c.category_id
    )


_CATEGORY_GROUPS = {
    "instrument": {"type", "status", "owner"},
    "clothing": {"type", "size", "status"},
    "sheet_music": {"genre"},
    "general_item": {"category", "room", "status"},
}


def display_nr_condition(
    text: str, item: Any = InventoryItem
) -> ColumnElement[bool] | None:
    """Match an inventory number typed as "TU-0002", "tu 2" or "TU2" (on
    ``item``, InventoryItem or an alias of it)."""
    match = _DISPLAY_NR_RE.match(text)
    if not match:
        return None
    return and_(
        func.upper(item.number_prefix) == match[1].upper(),
        item.inventory_nr == int(match[2]),
    )


class ItemFilter(ListFilter):
    instrument_type_id__in: list[int] | None = None
    clothing_type_id__in: list[int] | None = None
    genre_id__in: list[int] | None = None
    category_id__in: list[int] | None = None
    without_category: bool | None = None
    status: Literal["verfuegbar", "verliehen"] | None = None
    # In stock (default), retired, or both.
    bestand: Literal["aktiv", "ausgeschieden", "alle"] = "aktiv"
    owner: str | None = None
    size: str | None = None
    gender: str | None = None
    difficulty: str | None = None
    storage_location__ilike: str | None = None
    construction_year__gte: int | None = None
    construction_year__lte: int | None = None

    _category: str = PrivateAttr(default="")

    class Constants(ListFilter.Constants):
        model = InventoryItem
        columns = {
            "instrument_type_id": InstrumentDetail.instrument_type_id,
            "construction_year": InstrumentDetail.construction_year,
            "clothing_type_id": ClothingDetail.clothing_type_id,
            "size": ClothingDetail.size,
            "gender": ClothingDetail.gender,
            "genre_id": SheetMusicDetail.genre_id,
            "difficulty": SheetMusicDetail.difficulty,
        }
        sort_fields = {
            "number": [InventoryItem.number_prefix, InventoryItem.inventory_nr],
            "type": [],  # instrument or clothing type label, see sort_columns
            "manufacturer": [InventoryItem.manufacturer],
            "construction_year": [InstrumentDetail.construction_year],
            "size": [ClothingDetail.size],
            "label": [InventoryItem.label],
            "composer": [SheetMusicDetail.composer],
            "storage_location": [InventoryItem.storage_location],
            # Last name first, like the musician list; available items last.
            "borrower": [
                _borrower_column(Musician.last_name),
                _borrower_column(Musician.first_name),
            ],
        }
        default_sort = ["number"]
        group_fields = {
            "type": None,  # instrument or clothing type, see group_spec
            "status": GroupSpec(
                key=case((_OPEN_LOAN, "verliehen"), else_="verfuegbar"),
                label=case((_OPEN_LOAN, "Ausgeliehen"), else_="Verfügbar"),
                empty_label="—",
            ),
            "owner": GroupSpec(
                key=InventoryItem.owner,
                label=InventoryItem.owner,
                empty_label="Ohne Eigentümer",
            ),
            "size": GroupSpec(
                key=ClothingDetail.size,
                label=ClothingDetail.size,
                empty_label="Ohne Größe",
            ),
            "genre": GroupSpec(
                key=SheetMusicGenre.id,
                label=SheetMusicGenre.label,
                empty_label="Ohne Gattung",
                join=_join_genre,
            ),
            "category": GroupSpec(
                key=GeneralItemCategory.id,
                label=GeneralItemCategory.label,
                empty_label="Ohne Kategorie",
                join=_join_categories,
                multi=True,
            ),
            "room": GroupSpec(key=_ROOM, label=_ROOM, empty_label="Ohne Lagerort"),
        }

    def bind(self, category: str) -> ItemFilter:
        label = CATEGORY_LABELS[category]
        allowed = _CATEGORY_FIELDS[category] | _COMMON_FIELDS
        for name in self.model_dump(exclude_none=True, exclude_unset=True):
            if name not in allowed:
                raise HTTPException(
                    status_code=422, detail=f"Filter „{name}“ gibt es für {label} nicht"
                )
        for key in self.order_by or []:
            name = key.lstrip("+-")
            if name not in _CATEGORY_SORTS[category]:
                raise HTTPException(
                    status_code=422,
                    detail=f"Sortierung „{name}“ gibt es für {label} nicht",
                )
        if self.group_by and self.group_by not in _CATEGORY_GROUPS[category]:
            raise HTTPException(
                status_code=422,
                detail=f"Gruppierung „{self.group_by}“ gibt es für {label} nicht",
            )
        self._category = category
        return self

    def sort_columns(self, key: str) -> list[Any]:
        if key == "type":
            return [
                InstrumentType.label
                if self._category == "instrument"
                else ClothingType.label
            ]
        return super().sort_columns(key)

    def group_spec(self) -> GroupSpec | None:
        if self.group_by == "type":
            if self._category == "instrument":
                return GroupSpec(
                    key=InstrumentType.id,
                    label=InstrumentType.label,
                    empty_label="Ohne Typ",
                )
            return GroupSpec(
                key=ClothingType.id, label=ClothingType.label, empty_label="Ohne Typ"
            )
        return super().group_spec()

    def search_clause(self, value: str) -> ColumnElement[bool] | None:
        return item_search_clause(value)

    def filter(self, query: Select) -> Select:  # type: ignore[override]
        query = super().filter(query)
        # fastapi-filter applies only fields that were given; "in stock" is
        # the default and must hold without ?bestand= too.
        if "bestand" not in self.model_fields_set:
            query = self.filter_bestand(query, "aktiv")
        return query

    def filter_bestand(self, query: Select, value: str) -> Select:
        if value == "aktiv":
            return query.where(InventoryItem.retired_at.is_(None))
        if value == "ausgeschieden":
            return query.where(InventoryItem.retired_at.is_not(None))
        return query

    def filter_status(self, query: Select, value: str) -> Select:
        open_loan = exists().where(
            Loan.item_id == InventoryItem.id, Loan.end_date.is_(None)
        )
        return query.where(open_loan if value == "verliehen" else ~open_loan)

    def filter_category_id__in(self, query: Select, value: list[int]) -> Select:
        has_any = InventoryItem.id.in_(
            select(links.c.item_id).where(links.c.category_id.in_(value))
        )
        if self.without_category:
            has_none = ~InventoryItem.id.in_(select(links.c.item_id))
            return query.where(or_(has_any, has_none))
        return query.where(has_any)

    def filter_without_category(self, query: Select, value: bool) -> Select:
        # Combined with category_id__in as OR in filter_category_id__in.
        if not value or self.category_id__in:
            return query
        return query.where(~InventoryItem.id.in_(select(links.c.item_id)))
