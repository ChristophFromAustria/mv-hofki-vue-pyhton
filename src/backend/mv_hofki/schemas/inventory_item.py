"""InventoryItem Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import ClassVar

from pydantic import BaseModel, Field, model_validator

from mv_hofki.schemas.clothing_type import ClothingTypeRead
from mv_hofki.schemas.currency import CurrencyRead
from mv_hofki.schemas.general_item_category import GeneralItemCategoryRef
from mv_hofki.schemas.instrument_type import InstrumentTypeRead
from mv_hofki.schemas.sheet_music_genre import SheetMusicGenreRead

# Number prefixes for categories without their own short codes. Instruments use
# the short code of their instrument type instead ("TU", "KL", ...).
CATEGORY_PREFIXES = {
    "instrument": "I",
    "clothing": "K",
    "sheet_music": "N",
    "general_item": "A",
}


def format_display_nr(number_prefix: str, inventory_nr: int) -> str:
    return f"{number_prefix}-{inventory_nr:03d}"


class ActiveLoanInfo(BaseModel):
    loan_id: int
    musician_id: int
    musician_name: str
    is_extern: bool
    start_date: date


# ---------------------------------------------------------------------------
# Create schemas
# ---------------------------------------------------------------------------


class ItemCreateBase(BaseModel):
    label: str
    quantity: int = Field(1, ge=1)
    manufacturer: str | None = None
    acquisition_date: date | None = None
    acquisition_cost: float | None = None
    currency_id: int | None = None
    owner: str = "MV Hofkirchen"
    notes: str | None = None
    storage_location: str | None = None

    @model_validator(mode="after")
    def cost_requires_currency(self):
        if self.acquisition_cost is not None and self.currency_id is None:
            raise ValueError("currency_id is required when acquisition_cost is set")
        return self


class InstrumentItemCreate(ItemCreateBase):
    category: str = "instrument"
    instrument_type_id: int
    serial_nr: str | None = None
    construction_year: int | None = None
    distributor: str | None = None
    container: str | None = None
    particularities: str | None = None


class ClothingItemCreate(ItemCreateBase):
    category: str = "clothing"
    clothing_type_id: int
    size: str | None = None
    gender: str | None = None


class SheetMusicItemCreate(ItemCreateBase):
    category: str = "sheet_music"
    composer: str | None = None
    arranger: str | None = None
    difficulty: str | None = None
    genre_id: int | None = None


class GeneralItemCreate(ItemCreateBase):
    category: str = "general_item"
    category_ids: list[int] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Update schemas
# ---------------------------------------------------------------------------


class ItemUpdateBase(BaseModel):
    label: str | None = None
    quantity: int | None = Field(None, ge=1)
    manufacturer: str | None = None
    acquisition_date: date | None = None
    acquisition_cost: float | None = None
    currency_id: int | None = None
    owner: str | None = None
    notes: str | None = None
    storage_location: str | None = None

    # Subclasses with a required FK to a type (instrument, clothing) list its
    # field name here so clearing it is rejected the same way as label/owner.
    _required_fk_fields: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def required_fields_not_cleared(self):
        for name in ("label", "owner", "quantity", *self._required_fk_fields):
            if name in self.model_fields_set:
                value = getattr(self, name)
                if value is None or (isinstance(value, str) and not value.strip()):
                    raise ValueError(f"Pflichtfeld: {name}")
        return self


class InstrumentItemUpdate(ItemUpdateBase):
    instrument_type_id: int | None = None
    serial_nr: str | None = None
    construction_year: int | None = None
    distributor: str | None = None
    container: str | None = None
    particularities: str | None = None

    _required_fk_fields: ClassVar[tuple[str, ...]] = ("instrument_type_id",)


class ClothingItemUpdate(ItemUpdateBase):
    clothing_type_id: int | None = None
    size: str | None = None
    gender: str | None = None

    _required_fk_fields: ClassVar[tuple[str, ...]] = ("clothing_type_id",)


class SheetMusicItemUpdate(ItemUpdateBase):
    composer: str | None = None
    arranger: str | None = None
    difficulty: str | None = None
    genre_id: int | None = None


class GeneralItemUpdate(ItemUpdateBase):
    category_ids: list[int] | None = None


# ---------------------------------------------------------------------------
# Read schemas
# ---------------------------------------------------------------------------


class ItemRead(BaseModel):
    id: int
    category: str
    inventory_nr: int
    display_nr: str
    label: str
    quantity: int = 1
    manufacturer: str | None
    acquisition_date: date | None
    acquisition_cost: float | None
    currency_id: int | None
    owner: str
    notes: str | None
    storage_location: str | None = None
    created_at: datetime
    updated_at: datetime
    currency: CurrencyRead | None = None
    active_loan: ActiveLoanInfo | None = None
    profile_image_url: str | None = None

    model_config = {"from_attributes": True}


class InstrumentItemRead(ItemRead):
    instrument_type_id: int
    serial_nr: str | None = None
    construction_year: int | None = None
    distributor: str | None = None
    container: str | None = None
    particularities: str | None = None
    instrument_type: InstrumentTypeRead | None = None


class ClothingItemRead(ItemRead):
    clothing_type_id: int
    size: str | None = None
    gender: str | None = None
    clothing_type: ClothingTypeRead | None = None


class SheetMusicItemRead(ItemRead):
    composer: str | None = None
    arranger: str | None = None
    difficulty: str | None = None
    genre_id: int | None = None
    genre: SheetMusicGenreRead | None = None


class GeneralItemRead(ItemRead):
    categories: list[GeneralItemCategoryRef] = []
