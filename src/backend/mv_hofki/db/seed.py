"""Seed data for initial database population."""

from __future__ import annotations

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.clothing_type import ClothingType
from mv_hofki.models.currency import Currency
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.scanner_config import ScannerConfig
from mv_hofki.models.sheet_music_genre import SheetMusicGenre
from mv_hofki.models.symbol_template import SymbolTemplate
from mv_hofki.services.scanner.library.seed import SYMBOL_TEMPLATES

INSTRUMENT_TYPES = [
    {"label": "Querflöte", "label_short": "FL"},
    {"label": "Klarinette in Es", "label_short": "KL"},
    {"label": "Klarinette in B", "label_short": "KL"},
    {"label": "Bassklarinette", "label_short": "KL"},
    {"label": "Fagott", "label_short": "FA"},
    {"label": "Oboe", "label_short": "OB"},
    {"label": "Englischhorn (Alt-Oboe)", "label_short": "OB"},
    {"label": "Flügelhorn", "label_short": "FH"},
    {"label": "Saxophon", "label_short": "SA"},
    {"label": "Altsaxophon", "label_short": "SA"},
    {"label": "Tenorsaxophon", "label_short": "SA"},
    {"label": "Baritonsaxophon", "label_short": "SA"},
    {"label": "Trompete", "label_short": "TR"},
    {"label": "Tenorhorn", "label_short": "TE"},
    {"label": "Bariton", "label_short": "TE"},
    {"label": "Euphonium", "label_short": "TE"},
    {"label": "Horn", "label_short": "WH"},
    {"label": "Posaune", "label_short": "PO"},
    {"label": "Tuba", "label_short": "TU"},
    {"label": "Schlagwerk", "label_short": "SW"},
]

CURRENCIES = [
    {"label": "Euro", "abbreviation": "€"},
    {"label": "Schilling", "abbreviation": "ATS"},
    {"label": "Dollar", "abbreviation": "$"},
    {"label": "Pfund", "abbreviation": "£"},
]

CLOTHING_TYPES = [
    {"label": "Hut"},
    {"label": "Jacke"},
    {"label": "Hose"},
    {"label": "Weste"},
    {"label": "Schuhe"},
    {"label": "Bluse"},
    {"label": "Rock"},
    {"label": "Strümpfe"},
]

SHEET_MUSIC_GENRES = [
    {"label": "Marsch"},
    {"label": "Polka"},
    {"label": "Walzer"},
    {"label": "Konzertwerk"},
    {"label": "Kirchenmusik"},
]


async def seed_data(session: AsyncSession) -> None:
    """Insert seed data if tables are empty."""
    result = await session.execute(select(InstrumentType).limit(1))
    if result.scalar_one_or_none() is None:
        await session.execute(insert(InstrumentType), INSTRUMENT_TYPES)

    result = await session.execute(select(Currency).limit(1))
    if result.scalar_one_or_none() is None:
        await session.execute(insert(Currency), CURRENCIES)

    result = await session.execute(select(ClothingType).limit(1))
    if result.scalar_one_or_none() is None:
        await session.execute(insert(ClothingType), CLOTHING_TYPES)

    result = await session.execute(select(SheetMusicGenre).limit(1))
    if result.scalar_one_or_none() is None:
        await session.execute(insert(SheetMusicGenre), SHEET_MUSIC_GENRES)

    result = await session.execute(select(SymbolTemplate).limit(1))
    if result.scalar_one_or_none() is None:
        await session.execute(
            insert(SymbolTemplate),
            [{"is_seed": True, **t} for t in SYMBOL_TEMPLATES],
        )
    else:
        # Update existing seed templates with new fields (musicxml, lilypond)
        for t in SYMBOL_TEMPLATES:
            row = await session.execute(
                select(SymbolTemplate).where(SymbolTemplate.name == t["name"])
            )
            existing = row.scalar_one_or_none()
            if existing and existing.is_seed:
                if t.get("musicxml_element") and not existing.musicxml_element:
                    existing.musicxml_element = t["musicxml_element"]
                if t.get("lilypond_token") and not existing.lilypond_token:
                    existing.lilypond_token = t["lilypond_token"]

    # Seed default scanner config if not present
    result = await session.execute(select(ScannerConfig).limit(1))
    if result.scalar_one_or_none() is None:
        session.add(ScannerConfig())

    await session.commit()
