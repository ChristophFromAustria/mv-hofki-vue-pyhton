"""InventoryItem Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, model_validator

from mv_hofki.schemas.clothing_type import ClothingTypeRead
from mv_hofki.schemas.currency import CurrencyRead
from mv_hofki.schemas.general_item_type import GeneralItemTypeRead
from mv_hofki.schemas.instrument_type import InstrumentTypeRead
from mv_hofki.schemas.sheet_music_genre import SheetMusicGenreRead

CATEGORY_PREFIXES = {
    "instrument": "I",
    "clothing": "K",
    "sheet_music": "N",
    "general_item": "A",
}


def format_display_nr(category: str, inventory_nr: int) -> str:
    prefix = CATEGORY_PREFIXES[category]
    return f"{prefix}-{inventory_nr:03d}"


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
    manufacturer: str | None = None
    acquisition_date: date | None = None
    acquisition_cost: float | None = None
    currency_id: int | None = None
    owner: str = "MV Hofkirchen"
    notes: str | None = None

    @model_validator(mode="after")
    def cost_requires_currency(self):
        if self.acquisition_cost is not None and self.currency_id is None:
            raise ValueError("currency_id is required when acquisition_cost is set")
        return self


class InstrumentItemCreate(ItemCreateBase):
    category: str = "instrument"
    instrument_type_id: int
    label_addition: str | None = None
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
    general_item_type_id: int


# ---------------------------------------------------------------------------
# Update schemas
# ---------------------------------------------------------------------------


class ItemUpdateBase(BaseModel):
    label: str | None = None
    manufacturer: str | None = None
    acquisition_date: date | None = None
    acquisition_cost: float | None = None
    currency_id: int | None = None
    owner: str | None = None
    notes: str | None = None


class InstrumentItemUpdate(ItemUpdateBase):
    instrument_type_id: int | None = None
    label_addition: str | None = None
    serial_nr: str | None = None
    construction_year: int | None = None
    distributor: str | None = None
    container: str | None = None
    particularities: str | None = None


class ClothingItemUpdate(ItemUpdateBase):
    clothing_type_id: int | None = None
    size: str | None = None
    gender: str | None = None


class SheetMusicItemUpdate(ItemUpdateBase):
    composer: str | None = None
    arranger: str | None = None
    difficulty: str | None = None
    genre_id: int | None = None


class GeneralItemUpdate(ItemUpdateBase):
    general_item_type_id: int | None = None


# ---------------------------------------------------------------------------
# Read schemas
# ---------------------------------------------------------------------------


class ItemRead(BaseModel):
    id: int
    category: str
    inventory_nr: int
    display_nr: str
    label: str
    manufacturer: str | None
    acquisition_date: date | None
    acquisition_cost: float | None
    currency_id: int | None
    owner: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    currency: CurrencyRead | None = None
    active_loan: ActiveLoanInfo | None = None
    profile_image_url: str | None = None

    model_config = {"from_attributes": True}


class InstrumentItemRead(ItemRead):
    instrument_type_id: int
    label_addition: str | None = None
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
    general_item_type_id: int
    general_item_type: GeneralItemTypeRead | None = None
