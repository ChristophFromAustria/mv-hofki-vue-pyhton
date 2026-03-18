# Inventarsystem Phase 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an instrument inventory system for Musikverein Hofkirchen with CRUD for instruments, musicians, instrument types, currencies, a loan register, and a dashboard — all backed by SQLite.

**Architecture:** FastAPI backend with SQLAlchemy 2.0 async ORM (aiosqlite) and Alembic migrations. Vue 3 frontend with simple fetch-based API calls. SQLite database at `data/mv_hofki.db`. No authentication (secured externally via Cloudflare Tunnel). UI in German, code in English.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), aiosqlite, Alembic, Pydantic v2, Vue 3, Vue Router 4, Vite 5

**Spec:** `docs/superpowers/specs/2026-03-18-inventarsystem-phase1-design.md`

---

## File Structure

### Backend — New Files

```
src/backend/mv_hofki/
├── db/
│   ├── __init__.py              # Empty
│   ├── engine.py                # Async engine + session factory
│   ├── base.py                  # SQLAlchemy DeclarativeBase
│   └── seed.py                  # Seed data (instrument types, currencies)
├── models/
│   ├── __init__.py              # Re-export all models
│   ├── currency.py              # Currency ORM model
│   ├── instrument_type.py       # InstrumentType ORM model
│   ├── instrument.py            # Instrument ORM model
│   ├── musician.py              # Musician ORM model
│   └── loan.py                  # Loan ORM model
├── schemas/
│   ├── __init__.py              # Empty
│   ├── currency.py              # Currency Pydantic schemas
│   ├── instrument_type.py       # InstrumentType Pydantic schemas
│   ├── instrument.py            # Instrument Pydantic schemas
│   ├── musician.py              # Musician Pydantic schemas
│   ├── loan.py                  # Loan Pydantic schemas
│   ├── dashboard.py             # Dashboard Pydantic schemas
│   └── pagination.py            # Generic paginated response schema
├── services/
│   ├── __init__.py              # Empty
│   ├── currency.py              # Currency CRUD service
│   ├── instrument_type.py       # InstrumentType CRUD service
│   ├── instrument.py            # Instrument CRUD service
│   ├── musician.py              # Musician CRUD service
│   ├── loan.py                  # Loan CRUD service
│   └── dashboard.py             # Dashboard aggregation service
├── api/
│   ├── deps.py                  # get_db dependency (async session)
│   └── routes/
│       ├── __init__.py          # Existing (empty)
│       ├── health.py            # Existing (no changes)
│       ├── currencies.py        # Currency routes
│       ├── instrument_types.py  # InstrumentType routes
│       ├── instruments.py       # Instrument routes
│       ├── musicians.py         # Musician routes
│       ├── loans.py             # Loan routes
│       └── dashboard.py         # Dashboard route
├── core/
│   └── config.py                # Add DATABASE_URL setting
```

### Backend — Modified Files

```
src/backend/mv_hofki/api/app.py       # Add lifespan, register new routers
src/backend/mv_hofki/core/config.py   # Add DATABASE_URL
src/backend/mv_hofki/api/deps.py      # Add get_db dependency
pyproject.toml                         # Add sqlalchemy, aiosqlite, alembic deps
```

### Alembic

```
alembic/
├── alembic.ini           # Alembic config (at project root)
├── env.py                # Async alembic env
├── script.py.mako        # Migration template
└── versions/
    └── 001_initial_schema.py   # Initial migration + seed data
```

### Frontend — New Files

```
src/frontend/src/
├── pages/
│   ├── DashboardPage.vue              # Dashboard with stats
│   ├── InstrumentListPage.vue         # Instrument list + filter/search
│   ├── InstrumentFormPage.vue         # Create/edit instrument
│   ├── InstrumentDetailPage.vue       # Instrument detail + loan history
│   ├── MusicianListPage.vue           # Musician list + search
│   ├── MusicianFormPage.vue           # Create/edit musician
│   ├── MusicianDetailPage.vue         # Musician detail + loans
│   ├── LoanListPage.vue              # Loan register
│   ├── InstrumentTypeListPage.vue     # Instrument type CRUD
│   └── CurrencyListPage.vue          # Currency CRUD
├── components/
│   ├── DataTable.vue                  # Reusable table with pagination
│   ├── SearchBar.vue                  # Search input component
│   ├── StatCard.vue                   # Dashboard stat card
│   └── ConfirmDialog.vue             # Delete confirmation dialog
```

### Frontend — Modified Files

```
src/frontend/src/router.js            # Add all routes
src/frontend/src/components/NavBar.vue # Update navigation
src/frontend/src/style.css             # Add table, form, card styles
src/frontend/src/App.vue               # No changes expected
```

### Tests

```
tests/backend/
├── conftest.py                 # Add async DB fixture
├── test_currencies.py          # Currency API tests
├── test_instrument_types.py    # InstrumentType API tests
├── test_instruments.py         # Instrument API tests
├── test_musicians.py           # Musician API tests
├── test_loans.py               # Loan API tests
└── test_dashboard.py           # Dashboard API tests
```

---

## Task 1: Add Dependencies and Database Engine

**Files:**
- Modify: `pyproject.toml:6-9` (add dependencies)
- Create: `src/backend/mv_hofki/db/__init__.py`
- Create: `src/backend/mv_hofki/db/engine.py`
- Create: `src/backend/mv_hofki/db/base.py`
- Modify: `src/backend/mv_hofki/core/config.py` (add DATABASE_URL)
- Modify: `src/backend/mv_hofki/api/deps.py` (add get_db)

- [ ] **Step 1: Add Python dependencies**

In `pyproject.toml`, add to the `dependencies` list:
```toml
dependencies = [
    "fastapi>=0.115,<1",
    "uvicorn[standard]>=0.34,<1",
    "pydantic-settings>=2.0,<3",
    "sqlalchemy[asyncio]>=2.0,<3",
    "aiosqlite>=0.20,<1",
    "alembic>=1.13,<2",
]
```

Also add `pytest-asyncio>=0.23,<1` to the `dev` optional dependencies.

- [ ] **Step 2: Install dependencies**

Run: `cd /workspaces/mv_hofki && pip install -e ".[dev]"`

- [ ] **Step 3: Add DATABASE_URL to config**

In `src/backend/mv_hofki/core/config.py`, add to the `Settings` class:
```python
DATABASE_URL: str = "sqlite+aiosqlite:///data/mv_hofki.db"
```

- [ ] **Step 4: Create db/base.py — DeclarativeBase**

```python
"""SQLAlchemy declarative base."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 5: Create db/engine.py — async engine + session**

```python
"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mv_hofki.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

- [ ] **Step 6: Create db/__init__.py**

Empty file.

- [ ] **Step 7: Update api/deps.py — add get_db**

```python
"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.db.engine import async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

- [ ] **Step 8: Create data/ directory with .gitkeep**

Run: `mkdir -p data && touch data/.gitkeep`
Add `data/*.db` to `.gitignore`.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml src/backend/mv_hofki/db/ src/backend/mv_hofki/core/config.py src/backend/mv_hofki/api/deps.py data/.gitkeep .gitignore
git commit -m "feat: add SQLAlchemy async engine, session factory, and DB config"
```

---

## Task 2: ORM Models

**Files:**
- Create: `src/backend/mv_hofki/models/currency.py`
- Create: `src/backend/mv_hofki/models/instrument_type.py`
- Create: `src/backend/mv_hofki/models/instrument.py`
- Create: `src/backend/mv_hofki/models/musician.py`
- Create: `src/backend/mv_hofki/models/loan.py`
- Modify: `src/backend/mv_hofki/models/__init__.py`

- [ ] **Step 1: Create models/currency.py**

```python
"""Currency ORM model."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class Currency(Base):
    __tablename__ = "currencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    abbreviation: Mapped[str] = mapped_column(String(100))
```

- [ ] **Step 2: Create models/instrument_type.py**

```python
"""InstrumentType ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class InstrumentType(Base):
    __tablename__ = "instrument_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(255))
    label_short: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

- [ ] **Step 3: Create models/instrument.py**

```python
"""Instrument ORM model."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True)
    inventory_nr: Mapped[int] = mapped_column(Integer, nullable=False)
    label_addition: Mapped[Optional[str]] = mapped_column(String(100))
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100))
    serial_nr: Mapped[Optional[str]] = mapped_column(String(100))
    construction_year: Mapped[Optional[date]] = mapped_column(Date)
    acquisition_date: Mapped[Optional[date]] = mapped_column(Date)
    acquisition_cost: Mapped[Optional[float]] = mapped_column(Float)
    currency_id: Mapped[int] = mapped_column(ForeignKey("currencies.id"), nullable=False)
    distributor: Mapped[Optional[str]] = mapped_column(String(100))
    container: Mapped[Optional[str]] = mapped_column(String(100))
    particularities: Mapped[Optional[str]] = mapped_column(String(100))
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(100))
    instrument_type_id: Mapped[int] = mapped_column(ForeignKey("instrument_types.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    instrument_type: Mapped["InstrumentType"] = relationship(lazy="joined")
    currency: Mapped["Currency"] = relationship(lazy="joined")
```

- [ ] **Step 4: Create models/musician.py**

```python
"""Musician ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from mv_hofki.db.base import Base


class Musician(Base):
    __tablename__ = "musicians"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[Optional[str]] = mapped_column(String(100))
    street_address: Mapped[Optional[str]] = mapped_column(String(100))
    postal_code: Mapped[Optional[int]] = mapped_column(Integer)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    is_extern: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

- [ ] **Step 5: Create models/loan.py**

```python
"""Loan ORM model."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mv_hofki.db.base import Base


class Loan(Base):
    __tablename__ = "loan_register"

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), nullable=False)
    musician_id: Mapped[int] = mapped_column(ForeignKey("musicians.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    instrument: Mapped["Instrument"] = relationship(lazy="joined")
    musician: Mapped["Musician"] = relationship(lazy="joined")
```

- [ ] **Step 6: Update models/__init__.py**

```python
"""ORM models."""

from mv_hofki.models.currency import Currency
from mv_hofki.models.instrument import Instrument
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician

__all__ = ["Currency", "Instrument", "InstrumentType", "Loan", "Musician"]
```

- [ ] **Step 7: Commit**

```bash
git add src/backend/mv_hofki/models/
git commit -m "feat: add SQLAlchemy ORM models for all Phase 1 tables"
```

---

## Task 3: Alembic Setup and Initial Migration with Seed Data

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/` (directory)
- Create: `src/backend/mv_hofki/db/seed.py`

- [ ] **Step 1: Initialize alembic**

Run: `cd /workspaces/mv_hofki && alembic init alembic`

- [ ] **Step 2: Configure alembic.ini**

In `alembic.ini`, set:
```ini
sqlalchemy.url = sqlite+aiosqlite:///data/mv_hofki.db
```

- [ ] **Step 3: Replace alembic/env.py with async version**

```python
"""Alembic async env."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from mv_hofki.db.base import Base
from mv_hofki.models import *  # noqa: F401, F403 — register all models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 4: Create seed.py**

```python
"""Seed data for initial database population."""

from __future__ import annotations

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.currency import Currency
from mv_hofki.models.instrument_type import InstrumentType

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


async def seed_data(session: AsyncSession) -> None:
    """Insert seed data if tables are empty."""
    result = await session.execute(select(InstrumentType).limit(1))
    if result.scalar_one_or_none() is None:
        await session.execute(insert(InstrumentType), INSTRUMENT_TYPES)

    result = await session.execute(select(Currency).limit(1))
    if result.scalar_one_or_none() is None:
        await session.execute(insert(Currency), CURRENCIES)

    await session.commit()
```

- [ ] **Step 5: Generate initial migration**

Run: `cd /workspaces/mv_hofki && PYTHONPATH=src/backend alembic revision --autogenerate -m "initial schema"`

- [ ] **Step 6: Run migration**

Run: `cd /workspaces/mv_hofki && PYTHONPATH=src/backend alembic upgrade head`

- [ ] **Step 7: Add app lifespan to run seed + create tables**

Modify `src/backend/mv_hofki/api/app.py`:

```python
"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from mv_hofki.api.routes.health import router as health_router
from mv_hofki.core.config import settings
from mv_hofki.db.engine import async_session_factory
from mv_hofki.db.seed import seed_data

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_session_factory() as session:
        await seed_data(session)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    root_path=settings.BASE_PATH if settings.BASE_PATH != "/" else "",
    lifespan=lifespan,
)

app.include_router(health_router)

_frontend_dist = settings.PROJECT_ROOT / "src" / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(_frontend_dist), html=True),
        name="frontend",
    )
```

- [ ] **Step 8: Verify server starts**

Run: `server-restart` then `server-logs` — check for no errors.

- [ ] **Step 9: Commit**

```bash
git add alembic.ini alembic/ src/backend/mv_hofki/db/seed.py src/backend/mv_hofki/api/app.py
git commit -m "feat: add Alembic migrations, seed data, and app lifespan"
```

---

## Task 4: Pydantic Schemas

**Files:**
- Create: `src/backend/mv_hofki/schemas/__init__.py`
- Create: `src/backend/mv_hofki/schemas/pagination.py`
- Create: `src/backend/mv_hofki/schemas/currency.py`
- Create: `src/backend/mv_hofki/schemas/instrument_type.py`
- Create: `src/backend/mv_hofki/schemas/instrument.py`
- Create: `src/backend/mv_hofki/schemas/musician.py`
- Create: `src/backend/mv_hofki/schemas/loan.py`
- Create: `src/backend/mv_hofki/schemas/dashboard.py`

- [ ] **Step 1: Create schemas/__init__.py**

Empty file.

- [ ] **Step 2: Create schemas/pagination.py**

```python
"""Generic paginated response schema."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
```

- [ ] **Step 3: Create schemas/currency.py**

```python
"""Currency Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class CurrencyCreate(BaseModel):
    label: str
    abbreviation: str


class CurrencyUpdate(BaseModel):
    label: str | None = None
    abbreviation: str | None = None


class CurrencyRead(BaseModel):
    id: int
    label: str
    abbreviation: str

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Create schemas/instrument_type.py**

```python
"""InstrumentType Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class InstrumentTypeCreate(BaseModel):
    label: str
    label_short: str


class InstrumentTypeUpdate(BaseModel):
    label: str | None = None
    label_short: str | None = None


class InstrumentTypeRead(BaseModel):
    id: int
    label: str
    label_short: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Create schemas/instrument.py**

```python
"""Instrument Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from mv_hofki.schemas.currency import CurrencyRead
from mv_hofki.schemas.instrument_type import InstrumentTypeRead


class InstrumentCreate(BaseModel):
    inventory_nr: int
    label_addition: str | None = None
    manufacturer: str | None = None
    serial_nr: str | None = None
    construction_year: date | None = None
    acquisition_date: date | None = None
    acquisition_cost: float | None = None
    currency_id: int
    distributor: str | None = None
    container: str | None = None
    particularities: str | None = None
    owner: str
    notes: str | None = None
    instrument_type_id: int


class InstrumentUpdate(BaseModel):
    inventory_nr: int | None = None
    label_addition: str | None = None
    manufacturer: str | None = None
    serial_nr: str | None = None
    construction_year: date | None = None
    acquisition_date: date | None = None
    acquisition_cost: float | None = None
    currency_id: int | None = None
    distributor: str | None = None
    container: str | None = None
    particularities: str | None = None
    owner: str | None = None
    notes: str | None = None
    instrument_type_id: int | None = None


class InstrumentRead(BaseModel):
    id: int
    inventory_nr: int
    label_addition: str | None
    manufacturer: str | None
    serial_nr: str | None
    construction_year: date | None
    acquisition_date: date | None
    acquisition_cost: float | None
    currency_id: int
    distributor: str | None
    container: str | None
    particularities: str | None
    owner: str
    notes: str | None
    instrument_type_id: int
    created_at: datetime
    instrument_type: InstrumentTypeRead
    currency: CurrencyRead

    model_config = {"from_attributes": True}
```

- [ ] **Step 6: Create schemas/musician.py**

```python
"""Musician Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class MusicianCreate(BaseModel):
    first_name: str
    last_name: str
    phone: str | None = None
    email: str | None = None
    street_address: str | None = None
    postal_code: int | None = None
    city: str | None = None
    is_extern: bool = False
    notes: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Darf nicht leer sein")
        return v.strip()


class MusicianUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    street_address: str | None = None
    postal_code: int | None = None
    city: str | None = None
    is_extern: bool | None = None
    notes: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def not_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Darf nicht leer sein")
        return v.strip() if v else v


class MusicianRead(BaseModel):
    id: int
    first_name: str
    last_name: str
    phone: str | None
    email: str | None
    street_address: str | None
    postal_code: int | None
    city: str | None
    is_extern: bool
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 7: Create schemas/loan.py**

```python
"""Loan Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from mv_hofki.schemas.instrument import InstrumentRead
from mv_hofki.schemas.musician import MusicianRead


class LoanCreate(BaseModel):
    instrument_id: int
    musician_id: int
    start_date: date


class LoanUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None


class LoanRead(BaseModel):
    id: int
    instrument_id: int
    musician_id: int
    start_date: date
    end_date: date | None
    created_at: datetime
    instrument: InstrumentRead
    musician: MusicianRead

    model_config = {"from_attributes": True}
```

- [ ] **Step 8: Create schemas/dashboard.py**

```python
"""Dashboard Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class InstrumentsByType(BaseModel):
    label: str
    label_short: str
    count: int


class DashboardStats(BaseModel):
    total_instruments: int
    total_musicians: int
    active_loans: int
    instruments_by_type: list[InstrumentsByType]
```

- [ ] **Step 9: Commit**

```bash
git add src/backend/mv_hofki/schemas/
git commit -m "feat: add Pydantic schemas for all Phase 1 entities"
```

---

## Task 5: Services — Currency and InstrumentType CRUD

**Files:**
- Create: `src/backend/mv_hofki/services/currency.py`
- Create: `src/backend/mv_hofki/services/instrument_type.py`
- Test: `tests/backend/test_currencies.py`
- Test: `tests/backend/test_instrument_types.py`

- [ ] **Step 1: Update test conftest.py with async DB fixture**

Replace `tests/backend/conftest.py`:

```python
"""Test fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mv_hofki.api.deps import get_db
from mv_hofki.db.base import Base
from mv_hofki.models import *  # noqa: F401, F403

# Use in-memory SQLite for tests
TEST_DB_URL = "sqlite+aiosqlite://"

engine = create_async_engine(TEST_DB_URL)
TestSessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session():
    async with TestSessionFactory() as session:
        yield session


@pytest.fixture
async def client(db_session):
    from mv_hofki.api.app import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
```

Add to `pyproject.toml` under `[tool.pytest.ini_options]`:
```toml
asyncio_mode = "auto"
```

- [ ] **Step 2: Create services/currency.py**

```python
"""Currency CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.currency import Currency
from mv_hofki.models.instrument import Instrument
from mv_hofki.schemas.currency import CurrencyCreate, CurrencyUpdate


async def get_all(session: AsyncSession) -> list[Currency]:
    result = await session.execute(select(Currency).order_by(Currency.label))
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, currency_id: int) -> Currency:
    currency = await session.get(Currency, currency_id)
    if not currency:
        raise HTTPException(status_code=404, detail="Währung nicht gefunden")
    return currency


async def create(session: AsyncSession, data: CurrencyCreate) -> Currency:
    currency = Currency(**data.model_dump())
    session.add(currency)
    await session.commit()
    await session.refresh(currency)
    return currency


async def update(session: AsyncSession, currency_id: int, data: CurrencyUpdate) -> Currency:
    currency = await get_by_id(session, currency_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(currency, key, value)
    await session.commit()
    await session.refresh(currency)
    return currency


async def delete(session: AsyncSession, currency_id: int) -> None:
    currency = await get_by_id(session, currency_id)
    # Check if any instruments use this currency
    result = await session.execute(
        select(func.count()).where(Instrument.currency_id == currency_id)
    )
    if result.scalar_one() > 0:
        raise HTTPException(
            status_code=409,
            detail="Währung wird von Instrumenten verwendet und kann nicht gelöscht werden",
        )
    await session.delete(currency)
    await session.commit()
```

- [ ] **Step 3: Create services/instrument_type.py**

```python
"""InstrumentType CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.instrument import Instrument
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.schemas.instrument_type import InstrumentTypeCreate, InstrumentTypeUpdate


async def get_all(session: AsyncSession) -> list[InstrumentType]:
    result = await session.execute(select(InstrumentType).order_by(InstrumentType.label))
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, type_id: int) -> InstrumentType:
    instrument_type = await session.get(InstrumentType, type_id)
    if not instrument_type:
        raise HTTPException(status_code=404, detail="Instrumententyp nicht gefunden")
    return instrument_type


async def create(session: AsyncSession, data: InstrumentTypeCreate) -> InstrumentType:
    instrument_type = InstrumentType(**data.model_dump())
    session.add(instrument_type)
    await session.commit()
    await session.refresh(instrument_type)
    return instrument_type


async def update(
    session: AsyncSession, type_id: int, data: InstrumentTypeUpdate
) -> InstrumentType:
    instrument_type = await get_by_id(session, type_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(instrument_type, key, value)
    await session.commit()
    await session.refresh(instrument_type)
    return instrument_type


async def delete(session: AsyncSession, type_id: int) -> None:
    instrument_type = await get_by_id(session, type_id)
    result = await session.execute(
        select(func.count()).where(Instrument.instrument_type_id == type_id)
    )
    if result.scalar_one() > 0:
        raise HTTPException(
            status_code=409,
            detail="Instrumententyp wird von Instrumenten verwendet und kann nicht gelöscht werden",
        )
    await session.delete(instrument_type)
    await session.commit()
```

- [ ] **Step 4: Write test_currencies.py**

```python
"""Currency API tests."""

import pytest


@pytest.fixture
async def currency(client):
    resp = await client.post("/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"})
    assert resp.status_code == 201
    return resp.json()


async def test_create_currency(client):
    resp = await client.post("/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["label"] == "Euro"
    assert data["abbreviation"] == "€"
    assert "id" in data


async def test_list_currencies(client, currency):
    resp = await client.get("/api/v1/currencies")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_get_currency(client, currency):
    resp = await client.get(f"/api/v1/currencies/{currency['id']}")
    assert resp.status_code == 200
    assert resp.json()["label"] == "Euro"


async def test_update_currency(client, currency):
    resp = await client.put(
        f"/api/v1/currencies/{currency['id']}", json={"label": "US Dollar"}
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "US Dollar"


async def test_delete_currency(client, currency):
    resp = await client.delete(f"/api/v1/currencies/{currency['id']}")
    assert resp.status_code == 204


async def test_get_currency_not_found(client):
    resp = await client.get("/api/v1/currencies/999")
    assert resp.status_code == 404


async def test_delete_currency_in_use_rejected(client, currency):
    """Cannot delete a currency that is referenced by an instrument."""
    itype = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Trompete", "label_short": "TR"}
        )
    ).json()
    await client.post(
        "/api/v1/instruments",
        json={
            "inventory_nr": 1,
            "owner": "Verein",
            "currency_id": currency["id"],
            "instrument_type_id": itype["id"],
        },
    )
    resp = await client.delete(f"/api/v1/currencies/{currency['id']}")
    assert resp.status_code == 409
```

- [ ] **Step 5: Write test_instrument_types.py**

```python
"""InstrumentType API tests."""

import pytest


@pytest.fixture
async def instrument_type(client):
    resp = await client.post(
        "/api/v1/instrument-types", json={"label": "Querflöte", "label_short": "FL"}
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_instrument_type(client):
    resp = await client.post(
        "/api/v1/instrument-types", json={"label": "Klarinette", "label_short": "KL"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["label"] == "Klarinette"
    assert data["label_short"] == "KL"


async def test_list_instrument_types(client, instrument_type):
    resp = await client.get("/api/v1/instrument-types")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_update_instrument_type(client, instrument_type):
    resp = await client.put(
        f"/api/v1/instrument-types/{instrument_type['id']}",
        json={"label": "Piccolo"},
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "Piccolo"


async def test_delete_instrument_type(client, instrument_type):
    resp = await client.delete(f"/api/v1/instrument-types/{instrument_type['id']}")
    assert resp.status_code == 204


async def test_delete_instrument_type_in_use_rejected(client, instrument_type):
    """Cannot delete an instrument type that is referenced by an instrument."""
    currency = (
        await client.post("/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"})
    ).json()
    await client.post(
        "/api/v1/instruments",
        json={
            "inventory_nr": 1,
            "owner": "Verein",
            "currency_id": currency["id"],
            "instrument_type_id": instrument_type["id"],
        },
    )
    resp = await client.delete(f"/api/v1/instrument-types/{instrument_type['id']}")
    assert resp.status_code == 409
```

- [ ] **Step 6: Run tests to verify they fail (routes don't exist yet)**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_currencies.py tests/backend/test_instrument_types.py -v`
Expected: FAIL (404 on all routes)

- [ ] **Step 7: Commit services and tests**

```bash
git add src/backend/mv_hofki/services/currency.py src/backend/mv_hofki/services/instrument_type.py tests/backend/
git commit -m "feat: add currency and instrument type services with tests (routes pending)"
```

---

## Task 6: API Routes — Currencies and InstrumentTypes

**Files:**
- Create: `src/backend/mv_hofki/api/routes/currencies.py`
- Create: `src/backend/mv_hofki/api/routes/instrument_types.py`
- Modify: `src/backend/mv_hofki/api/app.py` (register routers)

- [ ] **Step 1: Create routes/currencies.py**

```python
"""Currency API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.currency import CurrencyCreate, CurrencyRead, CurrencyUpdate
from mv_hofki.services import currency as currency_service

router = APIRouter(prefix="/api/v1/currencies", tags=["currencies"])


@router.get("", response_model=list[CurrencyRead])
async def list_currencies(db: AsyncSession = Depends(get_db)):
    return await currency_service.get_all(db)


@router.post("", response_model=CurrencyRead, status_code=201)
async def create_currency(data: CurrencyCreate, db: AsyncSession = Depends(get_db)):
    return await currency_service.create(db, data)


@router.get("/{currency_id}", response_model=CurrencyRead)
async def get_currency(currency_id: int, db: AsyncSession = Depends(get_db)):
    return await currency_service.get_by_id(db, currency_id)


@router.put("/{currency_id}", response_model=CurrencyRead)
async def update_currency(
    currency_id: int, data: CurrencyUpdate, db: AsyncSession = Depends(get_db)
):
    return await currency_service.update(db, currency_id, data)


@router.delete("/{currency_id}", status_code=204)
async def delete_currency(currency_id: int, db: AsyncSession = Depends(get_db)):
    await currency_service.delete(db, currency_id)
    return Response(status_code=204)
```

- [ ] **Step 2: Create routes/instrument_types.py**

```python
"""InstrumentType API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.instrument_type import (
    InstrumentTypeCreate,
    InstrumentTypeRead,
    InstrumentTypeUpdate,
)
from mv_hofki.services import instrument_type as instrument_type_service

router = APIRouter(prefix="/api/v1/instrument-types", tags=["instrument-types"])


@router.get("", response_model=list[InstrumentTypeRead])
async def list_instrument_types(db: AsyncSession = Depends(get_db)):
    return await instrument_type_service.get_all(db)


@router.post("", response_model=InstrumentTypeRead, status_code=201)
async def create_instrument_type(
    data: InstrumentTypeCreate, db: AsyncSession = Depends(get_db)
):
    return await instrument_type_service.create(db, data)


@router.get("/{type_id}", response_model=InstrumentTypeRead)
async def get_instrument_type(type_id: int, db: AsyncSession = Depends(get_db)):
    return await instrument_type_service.get_by_id(db, type_id)


@router.put("/{type_id}", response_model=InstrumentTypeRead)
async def update_instrument_type(
    type_id: int, data: InstrumentTypeUpdate, db: AsyncSession = Depends(get_db)
):
    return await instrument_type_service.update(db, type_id, data)


@router.delete("/{type_id}", status_code=204)
async def delete_instrument_type(type_id: int, db: AsyncSession = Depends(get_db)):
    await instrument_type_service.delete(db, type_id)
    return Response(status_code=204)
```

- [ ] **Step 3: Register routers in app.py**

Add to `src/backend/mv_hofki/api/app.py` after the health router import:

```python
from mv_hofki.api.routes.currencies import router as currencies_router
from mv_hofki.api.routes.instrument_types import router as instrument_types_router
```

And after `app.include_router(health_router)`:

```python
app.include_router(currencies_router)
app.include_router(instrument_types_router)
```

- [ ] **Step 4: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_currencies.py tests/backend/test_instrument_types.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/api/routes/currencies.py src/backend/mv_hofki/api/routes/instrument_types.py src/backend/mv_hofki/api/app.py
git commit -m "feat: add currency and instrument type API routes"
```

---

## Task 7: Services and Routes — Instruments

**Files:**
- Create: `src/backend/mv_hofki/services/instrument.py`
- Create: `src/backend/mv_hofki/api/routes/instruments.py`
- Test: `tests/backend/test_instruments.py`
- Modify: `src/backend/mv_hofki/api/app.py` (register router)

- [ ] **Step 1: Create services/instrument.py**

```python
"""Instrument CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from mv_hofki.models.instrument import Instrument
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.schemas.instrument import InstrumentCreate, InstrumentUpdate


async def get_list(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    type_id: int | None = None,
) -> tuple[list[Instrument], int]:
    query = select(Instrument).options(
        joinedload(Instrument.instrument_type),
        joinedload(Instrument.currency),
    )
    count_query = select(func.count()).select_from(Instrument)

    if type_id is not None:
        query = query.where(Instrument.instrument_type_id == type_id)
        count_query = count_query.where(Instrument.instrument_type_id == type_id)

    if search:
        pattern = f"%{search}%"
        search_filter = or_(
            Instrument.label_addition.ilike(pattern),
            Instrument.manufacturer.ilike(pattern),
            Instrument.serial_nr.ilike(pattern),
            Instrument.notes.ilike(pattern),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = (await session.execute(count_query)).scalar_one()
    query = query.order_by(Instrument.inventory_nr).limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.unique().scalars().all()), total


async def get_by_id(session: AsyncSession, instrument_id: int) -> Instrument:
    result = await session.execute(
        select(Instrument)
        .options(
            joinedload(Instrument.instrument_type),
            joinedload(Instrument.currency),
        )
        .where(Instrument.id == instrument_id)
    )
    instrument = result.unique().scalar_one_or_none()
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument nicht gefunden")
    return instrument


async def create(session: AsyncSession, data: InstrumentCreate) -> Instrument:
    instrument = Instrument(**data.model_dump())
    session.add(instrument)
    await session.commit()
    await session.refresh(instrument, attribute_names=["instrument_type", "currency"])
    return instrument


async def update(
    session: AsyncSession, instrument_id: int, data: InstrumentUpdate
) -> Instrument:
    instrument = await get_by_id(session, instrument_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(instrument, key, value)
    await session.commit()
    await session.refresh(instrument, attribute_names=["instrument_type", "currency"])
    return instrument


async def delete(session: AsyncSession, instrument_id: int) -> None:
    instrument = await get_by_id(session, instrument_id)
    await session.delete(instrument)
    await session.commit()
```

- [ ] **Step 2: Create routes/instruments.py**

```python
"""Instrument API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.instrument import InstrumentCreate, InstrumentRead, InstrumentUpdate
from mv_hofki.schemas.pagination import PaginatedResponse
from mv_hofki.services import instrument as instrument_service

router = APIRouter(prefix="/api/v1/instruments", tags=["instruments"])


@router.get("", response_model=PaginatedResponse[InstrumentRead])
async def list_instruments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    type_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    items, total = await instrument_service.get_list(
        db, limit=limit, offset=offset, search=search, type_id=type_id
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=InstrumentRead, status_code=201)
async def create_instrument(data: InstrumentCreate, db: AsyncSession = Depends(get_db)):
    return await instrument_service.create(db, data)


@router.get("/{instrument_id}", response_model=InstrumentRead)
async def get_instrument(instrument_id: int, db: AsyncSession = Depends(get_db)):
    return await instrument_service.get_by_id(db, instrument_id)


@router.put("/{instrument_id}", response_model=InstrumentRead)
async def update_instrument(
    instrument_id: int, data: InstrumentUpdate, db: AsyncSession = Depends(get_db)
):
    return await instrument_service.update(db, instrument_id, data)


@router.delete("/{instrument_id}", status_code=204)
async def delete_instrument(instrument_id: int, db: AsyncSession = Depends(get_db)):
    await instrument_service.delete(db, instrument_id)
    return Response(status_code=204)
```

- [ ] **Step 3: Register router in app.py**

Add import and `app.include_router(instruments_router)`.

- [ ] **Step 4: Write test_instruments.py**

```python
"""Instrument API tests."""

import pytest


@pytest.fixture
async def setup_refs(client):
    """Create a currency and instrument type for FK references."""
    currency = (
        await client.post("/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"})
    ).json()
    itype = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Querflöte", "label_short": "FL"}
        )
    ).json()
    return {"currency_id": currency["id"], "instrument_type_id": itype["id"]}


@pytest.fixture
async def instrument(client, setup_refs):
    resp = await client.post(
        "/api/v1/instruments",
        json={
            "inventory_nr": 1,
            "owner": "Musikverein",
            "manufacturer": "Yamaha",
            **setup_refs,
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_instrument(client, setup_refs):
    resp = await client.post(
        "/api/v1/instruments",
        json={
            "inventory_nr": 42,
            "owner": "Musikverein",
            "serial_nr": "YM-12345",
            **setup_refs,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["inventory_nr"] == 42
    assert data["serial_nr"] == "YM-12345"
    assert data["instrument_type"]["label"] == "Querflöte"


async def test_list_instruments_paginated(client, instrument):
    resp = await client.get("/api/v1/instruments?limit=10&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


async def test_list_instruments_search(client, instrument):
    resp = await client.get("/api/v1/instruments?search=Yamaha")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_list_instruments_filter_by_type(client, setup_refs, instrument):
    resp = await client.get(f"/api/v1/instruments?type_id={setup_refs['instrument_type_id']}")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    # Filter with a non-existent type should return 0
    resp2 = await client.get("/api/v1/instruments?type_id=999")
    assert resp2.json()["total"] == 0


async def test_get_instrument(client, instrument):
    resp = await client.get(f"/api/v1/instruments/{instrument['id']}")
    assert resp.status_code == 200
    assert resp.json()["owner"] == "Musikverein"


async def test_update_instrument(client, instrument):
    resp = await client.put(
        f"/api/v1/instruments/{instrument['id']}", json={"notes": "Frisch gewartet"}
    )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Frisch gewartet"


async def test_delete_instrument(client, instrument):
    resp = await client.delete(f"/api/v1/instruments/{instrument['id']}")
    assert resp.status_code == 204
```

- [ ] **Step 5: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_instruments.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/instrument.py src/backend/mv_hofki/api/routes/instruments.py src/backend/mv_hofki/api/app.py tests/backend/test_instruments.py
git commit -m "feat: add instrument CRUD with search, pagination, and tests"
```

---

## Task 8: Services and Routes — Musicians

**Files:**
- Create: `src/backend/mv_hofki/services/musician.py`
- Create: `src/backend/mv_hofki/api/routes/musicians.py`
- Test: `tests/backend/test_musicians.py`
- Modify: `src/backend/mv_hofki/api/app.py`

- [ ] **Step 1: Create services/musician.py**

```python
"""Musician CRUD service."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.schemas.musician import MusicianCreate, MusicianUpdate


async def get_list(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
) -> tuple[list[Musician], int]:
    query = select(Musician)
    count_query = select(func.count()).select_from(Musician)

    if search:
        pattern = f"%{search}%"
        search_filter = or_(
            Musician.first_name.ilike(pattern),
            Musician.last_name.ilike(pattern),
            Musician.email.ilike(pattern),
            Musician.city.ilike(pattern),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = (await session.execute(count_query)).scalar_one()
    query = query.order_by(Musician.last_name, Musician.first_name).limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars().all()), total


async def get_by_id(session: AsyncSession, musician_id: int) -> Musician:
    musician = await session.get(Musician, musician_id)
    if not musician:
        raise HTTPException(status_code=404, detail="Musiker nicht gefunden")
    return musician


async def create(session: AsyncSession, data: MusicianCreate) -> Musician:
    musician = Musician(**data.model_dump())
    session.add(musician)
    await session.commit()
    await session.refresh(musician)
    return musician


async def update(session: AsyncSession, musician_id: int, data: MusicianUpdate) -> Musician:
    musician = await get_by_id(session, musician_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(musician, key, value)
    await session.commit()
    await session.refresh(musician)
    return musician


async def delete(session: AsyncSession, musician_id: int) -> None:
    musician = await get_by_id(session, musician_id)
    # Check for active loans
    result = await session.execute(
        select(func.count()).where(Loan.musician_id == musician_id, Loan.end_date.is_(None))
    )
    if result.scalar_one() > 0:
        raise HTTPException(
            status_code=409,
            detail="Musiker hat aktive Leihen und kann nicht gelöscht werden",
        )
    await session.delete(musician)
    await session.commit()
```

- [ ] **Step 2: Create routes/musicians.py**

```python
"""Musician API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.musician import MusicianCreate, MusicianRead, MusicianUpdate
from mv_hofki.schemas.pagination import PaginatedResponse
from mv_hofki.services import musician as musician_service

router = APIRouter(prefix="/api/v1/musicians", tags=["musicians"])


@router.get("", response_model=PaginatedResponse[MusicianRead])
async def list_musicians(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    items, total = await musician_service.get_list(db, limit=limit, offset=offset, search=search)
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=MusicianRead, status_code=201)
async def create_musician(data: MusicianCreate, db: AsyncSession = Depends(get_db)):
    return await musician_service.create(db, data)


@router.get("/{musician_id}", response_model=MusicianRead)
async def get_musician(musician_id: int, db: AsyncSession = Depends(get_db)):
    return await musician_service.get_by_id(db, musician_id)


@router.put("/{musician_id}", response_model=MusicianRead)
async def update_musician(
    musician_id: int, data: MusicianUpdate, db: AsyncSession = Depends(get_db)
):
    return await musician_service.update(db, musician_id, data)


@router.delete("/{musician_id}", status_code=204)
async def delete_musician(musician_id: int, db: AsyncSession = Depends(get_db)):
    await musician_service.delete(db, musician_id)
    return Response(status_code=204)
```

- [ ] **Step 3: Register router in app.py**

- [ ] **Step 4: Write test_musicians.py**

```python
"""Musician API tests."""

import pytest


@pytest.fixture
async def musician(client):
    resp = await client.post(
        "/api/v1/musicians",
        json={"first_name": "Max", "last_name": "Mustermann", "is_extern": False},
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_musician(client):
    resp = await client.post(
        "/api/v1/musicians",
        json={
            "first_name": "Anna",
            "last_name": "Huber",
            "email": "anna@example.com",
            "city": "Hofkirchen",
            "is_extern": False,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["first_name"] == "Anna"
    assert data["city"] == "Hofkirchen"


async def test_create_musician_empty_name_rejected(client):
    resp = await client.post(
        "/api/v1/musicians",
        json={"first_name": "", "last_name": "Test", "is_extern": False},
    )
    assert resp.status_code == 422


async def test_list_musicians_search(client, musician):
    resp = await client.get("/api/v1/musicians?search=Mustermann")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_update_musician(client, musician):
    resp = await client.put(
        f"/api/v1/musicians/{musician['id']}", json={"phone": "+43 123 456"}
    )
    assert resp.status_code == 200
    assert resp.json()["phone"] == "+43 123 456"


async def test_delete_musician(client, musician):
    resp = await client.delete(f"/api/v1/musicians/{musician['id']}")
    assert resp.status_code == 204


async def test_delete_musician_with_active_loan_rejected(client, musician):
    """Cannot delete a musician who has an active loan."""
    currency = (
        await client.post("/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"})
    ).json()
    itype = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Trompete", "label_short": "TR"}
        )
    ).json()
    instrument = (
        await client.post(
            "/api/v1/instruments",
            json={
                "inventory_nr": 1,
                "owner": "Verein",
                "currency_id": currency["id"],
                "instrument_type_id": itype["id"],
            },
        )
    ).json()
    await client.post(
        "/api/v1/loans",
        json={
            "instrument_id": instrument["id"],
            "musician_id": musician["id"],
            "start_date": "2026-01-01",
        },
    )
    resp = await client.delete(f"/api/v1/musicians/{musician['id']}")
    assert resp.status_code == 409
```

- [ ] **Step 5: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_musicians.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/musician.py src/backend/mv_hofki/api/routes/musicians.py src/backend/mv_hofki/api/app.py tests/backend/test_musicians.py
git commit -m "feat: add musician CRUD with search, pagination, and tests"
```

---

## Task 9: Services and Routes — Loans

**Files:**
- Create: `src/backend/mv_hofki/services/loan.py`
- Create: `src/backend/mv_hofki/api/routes/loans.py`
- Test: `tests/backend/test_loans.py`
- Modify: `src/backend/mv_hofki/api/app.py`

- [ ] **Step 1: Create services/loan.py**

```python
"""Loan CRUD service."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from mv_hofki.models.loan import Loan
from mv_hofki.schemas.loan import LoanCreate, LoanUpdate


async def get_list(
    session: AsyncSession,
    *,
    active: bool | None = None,
    instrument_id: int | None = None,
    musician_id: int | None = None,
) -> list[Loan]:
    query = select(Loan).options(
        joinedload(Loan.instrument),
        joinedload(Loan.musician),
    )
    if active is True:
        query = query.where(Loan.end_date.is_(None))
    elif active is False:
        query = query.where(Loan.end_date.is_not(None))

    if instrument_id is not None:
        query = query.where(Loan.instrument_id == instrument_id)
    if musician_id is not None:
        query = query.where(Loan.musician_id == musician_id)

    query = query.order_by(Loan.start_date.desc())
    result = await session.execute(query)
    return list(result.unique().scalars().all())


async def get_by_id(session: AsyncSession, loan_id: int) -> Loan:
    result = await session.execute(
        select(Loan)
        .options(joinedload(Loan.instrument), joinedload(Loan.musician))
        .where(Loan.id == loan_id)
    )
    loan = result.unique().scalar_one_or_none()
    if not loan:
        raise HTTPException(status_code=404, detail="Leihe nicht gefunden")
    return loan


async def create(session: AsyncSession, data: LoanCreate) -> Loan:
    # Check instrument is not already on active loan
    result = await session.execute(
        select(func.count()).where(
            Loan.instrument_id == data.instrument_id,
            Loan.end_date.is_(None),
        )
    )
    if result.scalar_one() > 0:
        raise HTTPException(
            status_code=409,
            detail="Instrument ist bereits ausgeliehen",
        )
    loan = Loan(**data.model_dump())
    session.add(loan)
    await session.commit()
    return await get_by_id(session, loan.id)


async def update(session: AsyncSession, loan_id: int, data: LoanUpdate) -> Loan:
    loan = await get_by_id(session, loan_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(loan, key, value)
    await session.commit()
    return await get_by_id(session, loan_id)


async def return_instrument(session: AsyncSession, loan_id: int) -> Loan:
    loan = await get_by_id(session, loan_id)
    if loan.end_date is not None:
        raise HTTPException(status_code=409, detail="Instrument wurde bereits zurückgegeben")
    loan.end_date = date.today()
    await session.commit()
    return await get_by_id(session, loan_id)
```

- [ ] **Step 2: Create routes/loans.py**

```python
"""Loan API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.loan import LoanCreate, LoanRead, LoanUpdate
from mv_hofki.services import loan as loan_service

router = APIRouter(prefix="/api/v1/loans", tags=["loans"])


@router.get("", response_model=list[LoanRead])
async def list_loans(
    active: bool | None = None,
    instrument_id: int | None = None,
    musician_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await loan_service.get_list(
        db, active=active, instrument_id=instrument_id, musician_id=musician_id
    )


@router.post("", response_model=LoanRead, status_code=201)
async def create_loan(data: LoanCreate, db: AsyncSession = Depends(get_db)):
    return await loan_service.create(db, data)


@router.get("/{loan_id}", response_model=LoanRead)
async def get_loan(loan_id: int, db: AsyncSession = Depends(get_db)):
    return await loan_service.get_by_id(db, loan_id)


@router.put("/{loan_id}", response_model=LoanRead)
async def update_loan(loan_id: int, data: LoanUpdate, db: AsyncSession = Depends(get_db)):
    return await loan_service.update(db, loan_id, data)


@router.put("/{loan_id}/return", response_model=LoanRead)
async def return_loan(loan_id: int, db: AsyncSession = Depends(get_db)):
    return await loan_service.return_instrument(db, loan_id)
```

- [ ] **Step 3: Register router in app.py**

- [ ] **Step 4: Write test_loans.py**

```python
"""Loan API tests."""

import pytest
from datetime import date


@pytest.fixture
async def setup_data(client):
    """Create currency, type, instrument, and musician for loan tests."""
    currency = (
        await client.post("/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"})
    ).json()
    itype = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Trompete", "label_short": "TR"}
        )
    ).json()
    instrument = (
        await client.post(
            "/api/v1/instruments",
            json={
                "inventory_nr": 1,
                "owner": "Verein",
                "currency_id": currency["id"],
                "instrument_type_id": itype["id"],
            },
        )
    ).json()
    musician = (
        await client.post(
            "/api/v1/musicians",
            json={"first_name": "Max", "last_name": "Muster", "is_extern": False},
        )
    ).json()
    return {"instrument_id": instrument["id"], "musician_id": musician["id"]}


@pytest.fixture
async def loan(client, setup_data):
    resp = await client.post(
        "/api/v1/loans",
        json={**setup_data, "start_date": "2026-01-15"},
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_loan(client, setup_data):
    resp = await client.post(
        "/api/v1/loans",
        json={**setup_data, "start_date": "2026-03-01"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["end_date"] is None
    assert data["instrument"]["inventory_nr"] == 1


async def test_duplicate_active_loan_rejected(client, setup_data, loan):
    resp = await client.post(
        "/api/v1/loans",
        json={**setup_data, "start_date": "2026-03-01"},
    )
    assert resp.status_code == 409


async def test_return_instrument(client, loan):
    resp = await client.put(f"/api/v1/loans/{loan['id']}/return")
    assert resp.status_code == 200
    assert resp.json()["end_date"] is not None


async def test_list_active_loans(client, loan):
    resp = await client.get("/api/v1/loans?active=true")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_return_already_returned(client, loan):
    await client.put(f"/api/v1/loans/{loan['id']}/return")
    resp = await client.put(f"/api/v1/loans/{loan['id']}/return")
    assert resp.status_code == 409
```

- [ ] **Step 5: Run tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/test_loans.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/loan.py src/backend/mv_hofki/api/routes/loans.py src/backend/mv_hofki/api/app.py tests/backend/test_loans.py
git commit -m "feat: add loan register with active loan check and return functionality"
```

---

## Task 10: Dashboard Service and Route

**Files:**
- Create: `src/backend/mv_hofki/services/dashboard.py`
- Create: `src/backend/mv_hofki/api/routes/dashboard.py`
- Test: `tests/backend/test_dashboard.py`
- Modify: `src/backend/mv_hofki/api/app.py`

- [ ] **Step 1: Create services/dashboard.py**

```python
"""Dashboard aggregation service."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.instrument import Instrument
from mv_hofki.models.instrument_type import InstrumentType
from mv_hofki.models.loan import Loan
from mv_hofki.models.musician import Musician
from mv_hofki.schemas.dashboard import DashboardStats, InstrumentsByType


async def get_stats(session: AsyncSession) -> DashboardStats:
    total_instruments = (
        await session.execute(select(func.count()).select_from(Instrument))
    ).scalar_one()

    total_musicians = (
        await session.execute(select(func.count()).select_from(Musician))
    ).scalar_one()

    active_loans = (
        await session.execute(
            select(func.count()).where(Loan.end_date.is_(None))
        )
    ).scalar_one()

    by_type_result = await session.execute(
        select(
            InstrumentType.label,
            InstrumentType.label_short,
            func.count(Instrument.id).label("count"),
        )
        .join(Instrument, Instrument.instrument_type_id == InstrumentType.id)
        .group_by(InstrumentType.id, InstrumentType.label, InstrumentType.label_short)
        .order_by(func.count(Instrument.id).desc())
    )

    instruments_by_type = [
        InstrumentsByType(label=row.label, label_short=row.label_short, count=row.count)
        for row in by_type_result
    ]

    return DashboardStats(
        total_instruments=total_instruments,
        total_musicians=total_musicians,
        active_loans=active_loans,
        instruments_by_type=instruments_by_type,
    )
```

- [ ] **Step 2: Create routes/dashboard.py**

```python
"""Dashboard API route."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.dashboard import DashboardStats
from mv_hofki.services import dashboard as dashboard_service

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardStats)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    return await dashboard_service.get_stats(db)
```

- [ ] **Step 3: Register router in app.py**

- [ ] **Step 4: Write test_dashboard.py**

```python
"""Dashboard API tests."""


async def test_dashboard_empty(client):
    resp = await client.get("/api/v1/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_instruments"] == 0
    assert data["total_musicians"] == 0
    assert data["active_loans"] == 0
    assert data["instruments_by_type"] == []


async def test_dashboard_with_data(client):
    # Create reference data
    currency = (
        await client.post("/api/v1/currencies", json={"label": "Euro", "abbreviation": "€"})
    ).json()
    itype = (
        await client.post(
            "/api/v1/instrument-types", json={"label": "Trompete", "label_short": "TR"}
        )
    ).json()
    await client.post(
        "/api/v1/instruments",
        json={
            "inventory_nr": 1,
            "owner": "Verein",
            "currency_id": currency["id"],
            "instrument_type_id": itype["id"],
        },
    )
    await client.post(
        "/api/v1/musicians",
        json={"first_name": "Max", "last_name": "Muster", "is_extern": False},
    )

    resp = await client.get("/api/v1/dashboard")
    data = resp.json()
    assert data["total_instruments"] == 1
    assert data["total_musicians"] == 1
    assert data["instruments_by_type"][0]["label"] == "Trompete"
    assert data["instruments_by_type"][0]["count"] == 1
```

- [ ] **Step 5: Run all backend tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/mv_hofki/services/dashboard.py src/backend/mv_hofki/api/routes/dashboard.py src/backend/mv_hofki/api/app.py tests/backend/test_dashboard.py
git commit -m "feat: add dashboard endpoint with aggregated stats"
```

---

## Task 11: Frontend — Global Styles, Components, and Navigation

**Files:**
- Modify: `src/frontend/src/style.css`
- Modify: `src/frontend/src/components/NavBar.vue`
- Modify: `src/frontend/src/router.js`
- Create: `src/frontend/src/components/DataTable.vue`
- Create: `src/frontend/src/components/SearchBar.vue`
- Create: `src/frontend/src/components/StatCard.vue`
- Create: `src/frontend/src/components/ConfirmDialog.vue`

- [ ] **Step 1: Extend style.css with form, table, button, card styles**

Append to `src/frontend/src/style.css`:

```css
/* Buttons */
button, .btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 0.875rem;
  cursor: pointer;
  transition: background 0.15s;
}

button:hover, .btn:hover {
  background: var(--color-border);
}

.btn-primary {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}

.btn-primary:hover {
  background: var(--color-primary-hover);
}

.btn-danger {
  color: #dc2626;
  border-color: #dc2626;
}

.btn-danger:hover {
  background: #fef2f2;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.8rem;
}

/* Forms */
.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.25rem;
  font-weight: 500;
  font-size: 0.875rem;
}

input, select, textarea {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 0.875rem;
  font-family: var(--font-sans);
}

input:focus, select:focus, textarea:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

/* Tables */
table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  padding: 0.625rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  font-size: 0.875rem;
}

th {
  font-weight: 600;
  color: var(--color-muted);
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.025em;
}

tr:hover {
  background: #f9fafb;
}

/* Cards */
.card {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 1.25rem;
  background: var(--color-bg);
}

/* Page header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.page-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
}

/* Grid */
.grid {
  display: grid;
  gap: 1rem;
}

.grid-2 { grid-template-columns: repeat(2, 1fr); }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
.grid-4 { grid-template-columns: repeat(4, 1fr); }

/* Toolbar */
.toolbar {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 1rem;
}

.toolbar > * { flex-shrink: 0; }
.toolbar .grow { flex-grow: 1; }

/* Pagination */
.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 1rem;
  font-size: 0.875rem;
  color: var(--color-muted);
}

/* Dialog overlay */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.dialog {
  background: var(--color-bg);
  border-radius: 8px;
  padding: 1.5rem;
  max-width: 400px;
  width: 90%;
  box-shadow: 0 10px 25px rgba(0,0,0,0.15);
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
}

/* Badges */
.badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.badge-green { background: #dcfce7; color: #166534; }
.badge-gray { background: #f3f4f6; color: #374151; }

/* Detail page */
.detail-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.5rem 1.5rem;
  font-size: 0.9rem;
}

.detail-grid dt {
  color: var(--color-muted);
  font-weight: 500;
}
```

- [ ] **Step 2: Create components/StatCard.vue**

```vue
<script setup>
defineProps({
  title: String,
  value: [Number, String],
});
</script>

<template>
  <div class="card stat-card">
    <div class="stat-value">{{ value }}</div>
    <div class="stat-title">{{ title }}</div>
  </div>
</template>

<style scoped>
.stat-card { text-align: center; }
.stat-value { font-size: 2rem; font-weight: 700; color: var(--color-primary); }
.stat-title { font-size: 0.875rem; color: var(--color-muted); margin-top: 0.25rem; }
</style>
```

- [ ] **Step 3: Create components/SearchBar.vue**

```vue
<script setup>
const model = defineModel();
defineProps({ placeholder: { type: String, default: "Suchen..." } });
</script>

<template>
  <input
    type="search"
    :placeholder="placeholder"
    :value="model"
    @input="model = $event.target.value"
    class="search-input"
  />
</template>

<style scoped>
.search-input { max-width: 300px; }
</style>
```

- [ ] **Step 4: Create components/DataTable.vue**

```vue
<script setup>
defineProps({
  columns: Array,   // [{ key, label, class? }]
  rows: Array,
  loading: Boolean,
});
defineEmits(["row-click"]);
</script>

<template>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th v-for="col in columns" :key="col.key" :class="col.class">{{ col.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td :colspan="columns.length" style="text-align:center;padding:2rem">Laden...</td>
        </tr>
        <tr v-else-if="!rows?.length">
          <td :colspan="columns.length" style="text-align:center;padding:2rem;color:var(--color-muted)">Keine Einträge</td>
        </tr>
        <tr
          v-for="row in rows"
          :key="row.id"
          @click="$emit('row-click', row)"
          style="cursor:pointer"
        >
          <td v-for="col in columns" :key="col.key" :class="col.class">
            <slot :name="col.key" :row="row" :value="row[col.key]">
              {{ row[col.key] }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
```

- [ ] **Step 5: Create components/ConfirmDialog.vue**

```vue
<script setup>
defineProps({
  open: Boolean,
  title: { type: String, default: "Bestätigung" },
  message: String,
});
defineEmits(["confirm", "cancel"]);
</script>

<template>
  <div v-if="open" class="overlay" @click.self="$emit('cancel')">
    <div class="dialog">
      <h3>{{ title }}</h3>
      <p style="margin-top:0.5rem">{{ message }}</p>
      <div class="dialog-actions">
        <button @click="$emit('cancel')">Abbrechen</button>
        <button class="btn-danger" @click="$emit('confirm')">Löschen</button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 6: Update NavBar.vue**

```vue
<script setup>
import { ref } from "vue";
import { RouterLink } from "vue-router";

const settingsOpen = ref(false);
</script>

<template>
  <nav class="navbar">
    <div class="navbar-inner">
      <RouterLink to="/" class="brand">MV Hofkirchen</RouterLink>
      <div class="links">
        <RouterLink to="/">Dashboard</RouterLink>
        <RouterLink to="/instrumente">Instrumente</RouterLink>
        <RouterLink to="/musiker">Musiker</RouterLink>
        <RouterLink to="/leihen">Leihregister</RouterLink>
        <div class="dropdown" @mouseenter="settingsOpen = true" @mouseleave="settingsOpen = false">
          <span class="dropdown-trigger">Einstellungen</span>
          <div v-show="settingsOpen" class="dropdown-menu">
            <RouterLink to="/einstellungen/instrumententypen">Instrumententypen</RouterLink>
            <RouterLink to="/einstellungen/waehrungen">Währungen</RouterLink>
          </div>
        </div>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.navbar {
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
}

.navbar-inner {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 0.75rem 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.brand {
  font-weight: 700;
  font-size: 1.1rem;
  color: var(--color-text);
}

.links {
  display: flex;
  gap: 1.5rem;
  align-items: center;
}

.links a.router-link-active {
  color: var(--color-primary);
  font-weight: 600;
}

.dropdown {
  position: relative;
}

.dropdown-trigger {
  cursor: pointer;
  color: var(--color-primary);
}

.dropdown-menu {
  position: absolute;
  right: 0;
  top: 100%;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 0.5rem 0;
  min-width: 180px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  z-index: 50;
}

.dropdown-menu a {
  display: block;
  padding: 0.5rem 1rem;
  color: var(--color-text);
}

.dropdown-menu a:hover {
  background: #f9fafb;
}
</style>
```

- [ ] **Step 7: Commit**

```bash
git add src/frontend/src/style.css src/frontend/src/components/
git commit -m "feat: add global styles, reusable components, and updated navigation"
```

---

## Task 12: Frontend — Dashboard Page

**Files:**
- Create: `src/frontend/src/pages/DashboardPage.vue`
- Modify: `src/frontend/src/router.js` (add route)
- Remove: `src/frontend/src/pages/HomePage.vue` (replaced by dashboard)

- [ ] **Step 1: Create DashboardPage.vue**

```vue
<script setup>
import { ref, onMounted } from "vue";
import { get } from "../lib/api.js";
import StatCard from "../components/StatCard.vue";

const stats = ref(null);
const loading = ref(true);

onMounted(async () => {
  try {
    stats.value = await get("/dashboard");
  } catch (e) {
    console.error("Dashboard laden fehlgeschlagen:", e);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div>
    <h1 style="margin-bottom: 1.5rem">Dashboard</h1>

    <div v-if="loading" style="text-align:center;padding:2rem">Laden...</div>

    <template v-else-if="stats">
      <div class="grid grid-3" style="margin-bottom: 2rem">
        <StatCard title="Instrumente" :value="stats.total_instruments" />
        <StatCard title="Musiker" :value="stats.total_musicians" />
        <StatCard title="Aktive Leihen" :value="stats.active_loans" />
      </div>

      <div class="card" v-if="stats.instruments_by_type.length">
        <h2 style="font-size:1.1rem;margin-bottom:1rem">Instrumente nach Typ</h2>
        <table>
          <thead>
            <tr>
              <th>Typ</th>
              <th>Kürzel</th>
              <th style="text-align:right">Anzahl</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in stats.instruments_by_type" :key="t.label">
              <td>{{ t.label }}</td>
              <td>{{ t.label_short }}</td>
              <td style="text-align:right">{{ t.count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
```

- [ ] **Step 2: Update router.js — replace HomePage with DashboardPage, add all routes**

```js
import { createRouter, createWebHistory } from "vue-router";

const routes = [
  {
    path: "/",
    name: "dashboard",
    component: () => import("./pages/DashboardPage.vue"),
  },
  {
    path: "/instrumente",
    name: "instruments",
    component: () => import("./pages/InstrumentListPage.vue"),
  },
  {
    path: "/instrumente/neu",
    name: "instrument-create",
    component: () => import("./pages/InstrumentFormPage.vue"),
  },
  {
    path: "/instrumente/:id",
    name: "instrument-detail",
    component: () => import("./pages/InstrumentDetailPage.vue"),
  },
  {
    path: "/instrumente/:id/bearbeiten",
    name: "instrument-edit",
    component: () => import("./pages/InstrumentFormPage.vue"),
  },
  {
    path: "/musiker",
    name: "musicians",
    component: () => import("./pages/MusicianListPage.vue"),
  },
  {
    path: "/musiker/neu",
    name: "musician-create",
    component: () => import("./pages/MusicianFormPage.vue"),
  },
  {
    path: "/musiker/:id",
    name: "musician-detail",
    component: () => import("./pages/MusicianDetailPage.vue"),
  },
  {
    path: "/musiker/:id/bearbeiten",
    name: "musician-edit",
    component: () => import("./pages/MusicianFormPage.vue"),
  },
  {
    path: "/leihen",
    name: "loans",
    component: () => import("./pages/LoanListPage.vue"),
  },
  {
    path: "/einstellungen/instrumententypen",
    name: "instrument-types",
    component: () => import("./pages/InstrumentTypeListPage.vue"),
  },
  {
    path: "/einstellungen/waehrungen",
    name: "currencies",
    component: () => import("./pages/CurrencyListPage.vue"),
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.VITE_BASE_PATH || "/"),
  routes,
});

export default router;
```

- [ ] **Step 3: Delete HomePage.vue**

Run: `rm src/frontend/src/pages/HomePage.vue`

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/pages/DashboardPage.vue src/frontend/src/router.js
git rm src/frontend/src/pages/HomePage.vue
git commit -m "feat: add dashboard page with stats, replace HomePage"
```

---

## Task 13: Frontend — Instrument Pages

**Files:**
- Create: `src/frontend/src/pages/InstrumentListPage.vue`
- Create: `src/frontend/src/pages/InstrumentFormPage.vue`
- Create: `src/frontend/src/pages/InstrumentDetailPage.vue`

- [ ] **Step 1: Create InstrumentListPage.vue**

```vue
<script setup>
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { get } from "../lib/api.js";
import DataTable from "../components/DataTable.vue";
import SearchBar from "../components/SearchBar.vue";

const router = useRouter();
const items = ref([]);
const total = ref(0);
const loading = ref(true);
const search = ref("");
const typeFilter = ref("");
const types = ref([]);
const limit = 50;
const offset = ref(0);

const columns = [
  { key: "inventory_nr", label: "Inv.-Nr." },
  { key: "type_label", label: "Typ" },
  { key: "manufacturer", label: "Hersteller" },
  { key: "serial_nr", label: "Seriennr." },
  { key: "owner", label: "Eigentümer" },
];

async function load() {
  loading.value = true;
  try {
    const params = new URLSearchParams();
    params.set("limit", limit);
    params.set("offset", offset.value);
    if (search.value) params.set("search", search.value);
    if (typeFilter.value) params.set("type_id", typeFilter.value);
    const data = await get(`/instruments?${params}`);
    items.value = data.items.map((i) => ({
      ...i,
      type_label: i.instrument_type?.label || "",
    }));
    total.value = data.total;
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  types.value = await get("/instrument-types");
  await load();
});

let searchTimeout;
watch(search, () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => { offset.value = 0; load(); }, 300);
});

watch(typeFilter, () => { offset.value = 0; load(); });

function goTo(row) { router.push(`/instrumente/${row.id}`); }
function prevPage() { if (offset.value > 0) { offset.value -= limit; load(); } }
function nextPage() { if (offset.value + limit < total.value) { offset.value += limit; load(); } }
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Instrumente</h1>
      <router-link to="/instrumente/neu" class="btn btn-primary">Neues Instrument</router-link>
    </div>

    <div class="toolbar">
      <SearchBar v-model="search" placeholder="Suche (Hersteller, Seriennr...)" class="grow" />
      <select v-model="typeFilter" style="max-width:200px">
        <option value="">Alle Typen</option>
        <option v-for="t in types" :key="t.id" :value="t.id">{{ t.label }}</option>
      </select>
    </div>

    <DataTable :columns="columns" :rows="items" :loading="loading" @row-click="goTo" />

    <div class="pagination" v-if="total > limit">
      <span>{{ offset + 1 }}–{{ Math.min(offset + limit, total) }} von {{ total }}</span>
      <div style="display:flex;gap:0.5rem">
        <button class="btn-sm" @click="prevPage" :disabled="offset === 0">Zurück</button>
        <button class="btn-sm" @click="nextPage" :disabled="offset + limit >= total">Weiter</button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Create InstrumentFormPage.vue**

```vue
<script setup>
import { ref, onMounted, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get, post, put } from "../lib/api.js";

const route = useRoute();
const router = useRouter();
const isEdit = computed(() => !!route.params.id);
const saving = ref(false);
const types = ref([]);
const currencies = ref([]);

const form = ref({
  inventory_nr: null,
  label_addition: "",
  manufacturer: "",
  serial_nr: "",
  construction_year: "",
  acquisition_date: "",
  acquisition_cost: null,
  currency_id: null,
  distributor: "",
  container: "",
  particularities: "",
  owner: "",
  notes: "",
  instrument_type_id: null,
});

onMounted(async () => {
  const [t, c] = await Promise.all([get("/instrument-types"), get("/currencies")]);
  types.value = t;
  currencies.value = c;

  if (isEdit.value) {
    const data = await get(`/instruments/${route.params.id}`);
    Object.keys(form.value).forEach((key) => {
      if (data[key] !== undefined && data[key] !== null) form.value[key] = data[key];
    });
  } else {
    if (c.length) form.value.currency_id = c[0].id;
  }
});

async function save() {
  saving.value = true;
  try {
    if (isEdit.value) {
      await put(`/instruments/${route.params.id}`, form.value);
      router.push(`/instrumente/${route.params.id}`);
    } else {
      const created = await post("/instruments", form.value);
      router.push(`/instrumente/${created.id}`);
    }
  } catch (e) {
    alert("Fehler: " + e.message);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div>
    <h1 style="margin-bottom:1.5rem">{{ isEdit ? "Instrument bearbeiten" : "Neues Instrument" }}</h1>

    <form @submit.prevent="save" class="card" style="max-width:700px">
      <div class="grid grid-2">
        <div class="form-group">
          <label>Inventarnummer *</label>
          <input type="number" v-model.number="form.inventory_nr" required />
        </div>
        <div class="form-group">
          <label>Instrumententyp *</label>
          <select v-model.number="form.instrument_type_id" required>
            <option v-for="t in types" :key="t.id" :value="t.id">{{ t.label }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>Bezeichnungszusatz</label>
          <input v-model="form.label_addition" />
        </div>
        <div class="form-group">
          <label>Hersteller</label>
          <input v-model="form.manufacturer" />
        </div>
        <div class="form-group">
          <label>Seriennummer</label>
          <input v-model="form.serial_nr" />
        </div>
        <div class="form-group">
          <label>Baujahr</label>
          <input type="date" v-model="form.construction_year" />
        </div>
        <div class="form-group">
          <label>Eigentümer *</label>
          <input v-model="form.owner" required />
        </div>
        <div class="form-group">
          <label>Händler</label>
          <input v-model="form.distributor" />
        </div>
        <div class="form-group">
          <label>Anschaffungsdatum</label>
          <input type="date" v-model="form.acquisition_date" />
        </div>
        <div class="form-group">
          <label>Anschaffungskosten</label>
          <div style="display:flex;gap:0.5rem">
            <input type="number" step="0.01" v-model.number="form.acquisition_cost" style="flex:1" />
            <select v-model.number="form.currency_id" style="width:100px">
              <option v-for="c in currencies" :key="c.id" :value="c.id">{{ c.abbreviation }}</option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label>Behältnis</label>
          <input v-model="form.container" />
        </div>
        <div class="form-group">
          <label>Besonderheiten</label>
          <input v-model="form.particularities" />
        </div>
      </div>
      <div class="form-group">
        <label>Notizen</label>
        <textarea v-model="form.notes" rows="2"></textarea>
      </div>

      <div style="display:flex;gap:0.5rem;margin-top:1rem">
        <button type="submit" class="btn-primary" :disabled="saving">
          {{ saving ? "Speichern..." : "Speichern" }}
        </button>
        <button type="button" @click="router.back()">Abbrechen</button>
      </div>
    </form>
  </div>
</template>
```

- [ ] **Step 3: Create InstrumentDetailPage.vue**

```vue
<script setup>
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get, del } from "../lib/api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const route = useRoute();
const router = useRouter();
const instrument = ref(null);
const loans = ref([]);
const showDelete = ref(false);

onMounted(async () => {
  instrument.value = await get(`/instruments/${route.params.id}`);
  loans.value = await get(`/loans?instrument_id=${route.params.id}`);
});

async function remove() {
  await del(`/instruments/${route.params.id}`);
  router.push("/instrumente");
}
</script>

<template>
  <div v-if="instrument">
    <div class="page-header">
      <h1>{{ instrument.instrument_type.label }} #{{ instrument.inventory_nr }}</h1>
      <div style="display:flex;gap:0.5rem">
        <router-link :to="`/instrumente/${instrument.id}/bearbeiten`" class="btn">Bearbeiten</router-link>
        <button class="btn-danger" @click="showDelete = true">Löschen</button>
      </div>
    </div>

    <div class="card" style="margin-bottom:1.5rem">
      <dl class="detail-grid">
        <dt>Inventarnummer</dt><dd>{{ instrument.inventory_nr }}</dd>
        <dt>Typ</dt><dd>{{ instrument.instrument_type.label }} ({{ instrument.instrument_type.label_short }})</dd>
        <dt>Bezeichnungszusatz</dt><dd>{{ instrument.label_addition || "—" }}</dd>
        <dt>Hersteller</dt><dd>{{ instrument.manufacturer || "—" }}</dd>
        <dt>Seriennummer</dt><dd>{{ instrument.serial_nr || "—" }}</dd>
        <dt>Baujahr</dt><dd>{{ instrument.construction_year || "—" }}</dd>
        <dt>Eigentümer</dt><dd>{{ instrument.owner }}</dd>
        <dt>Händler</dt><dd>{{ instrument.distributor || "—" }}</dd>
        <dt>Anschaffungsdatum</dt><dd>{{ instrument.acquisition_date || "—" }}</dd>
        <dt>Anschaffungskosten</dt>
        <dd>{{ instrument.acquisition_cost != null ? `${instrument.acquisition_cost} ${instrument.currency.abbreviation}` : "—" }}</dd>
        <dt>Behältnis</dt><dd>{{ instrument.container || "—" }}</dd>
        <dt>Besonderheiten</dt><dd>{{ instrument.particularities || "—" }}</dd>
        <dt>Notizen</dt><dd>{{ instrument.notes || "—" }}</dd>
      </dl>
    </div>

    <div class="card" v-if="loans.length">
      <h2 style="font-size:1.1rem;margin-bottom:1rem">Leihhistorie</h2>
      <table>
        <thead>
          <tr><th>Musiker</th><th>Von</th><th>Bis</th><th>Status</th></tr>
        </thead>
        <tbody>
          <tr v-for="l in loans" :key="l.id">
            <td>
              <router-link :to="`/musiker/${l.musician.id}`">
                {{ l.musician.first_name }} {{ l.musician.last_name }}
              </router-link>
            </td>
            <td>{{ l.start_date }}</td>
            <td>{{ l.end_date || "—" }}</td>
            <td>
              <span :class="l.end_date ? 'badge badge-gray' : 'badge badge-green'">
                {{ l.end_date ? "Zurückgegeben" : "Ausgeliehen" }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <ConfirmDialog
      :open="showDelete"
      title="Instrument löschen"
      message="Soll dieses Instrument wirklich gelöscht werden?"
      @confirm="remove"
      @cancel="showDelete = false"
    />
  </div>
</template>
```

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/pages/InstrumentListPage.vue src/frontend/src/pages/InstrumentFormPage.vue src/frontend/src/pages/InstrumentDetailPage.vue
git commit -m "feat: add instrument list, detail, and form pages"
```

---

## Task 14: Frontend — Musician Pages

**Files:**
- Create: `src/frontend/src/pages/MusicianListPage.vue`
- Create: `src/frontend/src/pages/MusicianFormPage.vue`
- Create: `src/frontend/src/pages/MusicianDetailPage.vue`

- [ ] **Step 1: Create MusicianListPage.vue**

```vue
<script setup>
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { get } from "../lib/api.js";
import DataTable from "../components/DataTable.vue";
import SearchBar from "../components/SearchBar.vue";

const router = useRouter();
const items = ref([]);
const total = ref(0);
const loading = ref(true);
const search = ref("");
const limit = 50;
const offset = ref(0);

const columns = [
  { key: "last_name", label: "Nachname" },
  { key: "first_name", label: "Vorname" },
  { key: "city", label: "Ort" },
  { key: "phone", label: "Telefon" },
  { key: "is_extern_label", label: "Extern" },
];

async function load() {
  loading.value = true;
  try {
    const params = new URLSearchParams();
    params.set("limit", limit);
    params.set("offset", offset.value);
    if (search.value) params.set("search", search.value);
    const data = await get(`/musicians?${params}`);
    items.value = data.items.map((m) => ({
      ...m,
      is_extern_label: m.is_extern ? "Ja" : "Nein",
    }));
    total.value = data.total;
  } finally {
    loading.value = false;
  }
}

onMounted(load);

let searchTimeout;
watch(search, () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => { offset.value = 0; load(); }, 300);
});

function goTo(row) { router.push(`/musiker/${row.id}`); }
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Musiker</h1>
      <router-link to="/musiker/neu" class="btn btn-primary">Neuer Musiker</router-link>
    </div>

    <div class="toolbar">
      <SearchBar v-model="search" placeholder="Suche (Name, Ort, E-Mail...)" class="grow" />
    </div>

    <DataTable :columns="columns" :rows="items" :loading="loading" @row-click="goTo" />

    <div class="pagination" v-if="total > limit">
      <span>{{ offset + 1 }}–{{ Math.min(offset + limit, total) }} von {{ total }}</span>
      <div style="display:flex;gap:0.5rem">
        <button class="btn-sm" @click="offset -= limit; load()" :disabled="offset === 0">Zurück</button>
        <button class="btn-sm" @click="offset += limit; load()" :disabled="offset + limit >= total">Weiter</button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Create MusicianFormPage.vue**

```vue
<script setup>
import { ref, onMounted, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get, post, put } from "../lib/api.js";

const route = useRoute();
const router = useRouter();
const isEdit = computed(() => !!route.params.id);
const saving = ref(false);

const form = ref({
  first_name: "",
  last_name: "",
  phone: "",
  email: "",
  street_address: "",
  postal_code: null,
  city: "",
  is_extern: false,
  notes: "",
});

onMounted(async () => {
  if (isEdit.value) {
    const data = await get(`/musicians/${route.params.id}`);
    Object.keys(form.value).forEach((key) => {
      if (data[key] !== undefined && data[key] !== null) form.value[key] = data[key];
    });
  }
});

async function save() {
  saving.value = true;
  try {
    if (isEdit.value) {
      await put(`/musicians/${route.params.id}`, form.value);
      router.push(`/musiker/${route.params.id}`);
    } else {
      const created = await post("/musicians", form.value);
      router.push(`/musiker/${created.id}`);
    }
  } catch (e) {
    alert("Fehler: " + e.message);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div>
    <h1 style="margin-bottom:1.5rem">{{ isEdit ? "Musiker bearbeiten" : "Neuer Musiker" }}</h1>

    <form @submit.prevent="save" class="card" style="max-width:600px">
      <div class="grid grid-2">
        <div class="form-group">
          <label>Vorname *</label>
          <input v-model="form.first_name" required />
        </div>
        <div class="form-group">
          <label>Nachname *</label>
          <input v-model="form.last_name" required />
        </div>
        <div class="form-group">
          <label>Telefon</label>
          <input v-model="form.phone" />
        </div>
        <div class="form-group">
          <label>E-Mail</label>
          <input type="email" v-model="form.email" />
        </div>
        <div class="form-group">
          <label>Straße</label>
          <input v-model="form.street_address" />
        </div>
        <div class="form-group">
          <label>PLZ</label>
          <input type="number" v-model.number="form.postal_code" />
        </div>
        <div class="form-group">
          <label>Ort</label>
          <input v-model="form.city" />
        </div>
        <div class="form-group" style="display:flex;align-items:end;gap:0.5rem;padding-bottom:0.25rem">
          <input type="checkbox" v-model="form.is_extern" id="is_extern" style="width:auto" />
          <label for="is_extern" style="margin:0">Extern</label>
        </div>
      </div>
      <div class="form-group">
        <label>Notizen</label>
        <textarea v-model="form.notes" rows="3"></textarea>
      </div>

      <div style="display:flex;gap:0.5rem;margin-top:1rem">
        <button type="submit" class="btn-primary" :disabled="saving">
          {{ saving ? "Speichern..." : "Speichern" }}
        </button>
        <button type="button" @click="router.back()">Abbrechen</button>
      </div>
    </form>
  </div>
</template>
```

- [ ] **Step 3: Create MusicianDetailPage.vue**

```vue
<script setup>
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get, del } from "../lib/api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const route = useRoute();
const router = useRouter();
const musician = ref(null);
const loans = ref([]);
const showDelete = ref(false);

onMounted(async () => {
  musician.value = await get(`/musicians/${route.params.id}`);
  loans.value = await get(`/loans?musician_id=${route.params.id}`);
});

async function remove() {
  try {
    await del(`/musicians/${route.params.id}`);
    router.push("/musiker");
  } catch (e) {
    alert("Fehler: " + e.message);
    showDelete.value = false;
  }
}
</script>

<template>
  <div v-if="musician">
    <div class="page-header">
      <h1>{{ musician.first_name }} {{ musician.last_name }}</h1>
      <div style="display:flex;gap:0.5rem">
        <router-link :to="`/musiker/${musician.id}/bearbeiten`" class="btn">Bearbeiten</router-link>
        <button class="btn-danger" @click="showDelete = true">Löschen</button>
      </div>
    </div>

    <div class="card" style="margin-bottom:1.5rem">
      <dl class="detail-grid">
        <dt>Vorname</dt><dd>{{ musician.first_name }}</dd>
        <dt>Nachname</dt><dd>{{ musician.last_name }}</dd>
        <dt>Telefon</dt><dd>{{ musician.phone || "—" }}</dd>
        <dt>E-Mail</dt><dd>{{ musician.email || "—" }}</dd>
        <dt>Adresse</dt><dd>{{ musician.street_address || "—" }}</dd>
        <dt>PLZ / Ort</dt><dd>{{ [musician.postal_code, musician.city].filter(Boolean).join(" ") || "—" }}</dd>
        <dt>Extern</dt><dd>{{ musician.is_extern ? "Ja" : "Nein" }}</dd>
        <dt>Notizen</dt><dd>{{ musician.notes || "—" }}</dd>
      </dl>
    </div>

    <div class="card" v-if="loans.length">
      <h2 style="font-size:1.1rem;margin-bottom:1rem">Ausgeliehene Instrumente</h2>
      <table>
        <thead>
          <tr><th>Instrument</th><th>Inv.-Nr.</th><th>Von</th><th>Bis</th><th>Status</th></tr>
        </thead>
        <tbody>
          <tr v-for="l in loans" :key="l.id">
            <td>
              <router-link :to="`/instrumente/${l.instrument.id}`">
                {{ l.instrument.instrument_type.label }}
              </router-link>
            </td>
            <td>{{ l.instrument.inventory_nr }}</td>
            <td>{{ l.start_date }}</td>
            <td>{{ l.end_date || "—" }}</td>
            <td>
              <span :class="l.end_date ? 'badge badge-gray' : 'badge badge-green'">
                {{ l.end_date ? "Zurückgegeben" : "Ausgeliehen" }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <ConfirmDialog
      :open="showDelete"
      title="Musiker löschen"
      message="Soll dieser Musiker wirklich gelöscht werden?"
      @confirm="remove"
      @cancel="showDelete = false"
    />
  </div>
</template>
```

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/pages/MusicianListPage.vue src/frontend/src/pages/MusicianFormPage.vue src/frontend/src/pages/MusicianDetailPage.vue
git commit -m "feat: add musician list, detail, and form pages"
```

---

## Task 15: Frontend — Loan Register Page

**Files:**
- Create: `src/frontend/src/pages/LoanListPage.vue`

- [ ] **Step 1: Create LoanListPage.vue**

```vue
<script setup>
import { ref, onMounted, watch } from "vue";
import { get, post, put } from "../lib/api.js";

const loans = ref([]);
const instruments = ref([]);
const musicians = ref([]);
const loading = ref(true);
const activeOnly = ref(true);
const showForm = ref(false);

const form = ref({ instrument_id: null, musician_id: null, start_date: "" });

async function load() {
  loading.value = true;
  try {
    loans.value = await get(`/loans?active=${activeOnly.value}`);
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  const [i, m] = await Promise.all([get("/instruments?limit=200"), get("/musicians?limit=200")]);
  instruments.value = i.items;
  musicians.value = m.items;
  await load();
});

watch(activeOnly, load);

async function createLoan() {
  try {
    await post("/loans", form.value);
    showForm.value = false;
    form.value = { instrument_id: null, musician_id: null, start_date: "" };
    await load();
  } catch (e) {
    alert("Fehler: " + e.message);
  }
}

async function returnLoan(id) {
  await put(`/loans/${id}/return`);
  await load();
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Leihregister</h1>
      <button class="btn btn-primary" @click="showForm = !showForm">Neue Ausleihe</button>
    </div>

    <div v-if="showForm" class="card" style="margin-bottom:1.5rem;max-width:600px">
      <h3 style="margin-bottom:1rem">Neue Ausleihe</h3>
      <form @submit.prevent="createLoan">
        <div class="grid grid-3">
          <div class="form-group">
            <label>Instrument *</label>
            <select v-model.number="form.instrument_id" required>
              <option :value="null" disabled>Auswählen...</option>
              <option v-for="i in instruments" :key="i.id" :value="i.id">
                #{{ i.inventory_nr }} {{ i.instrument_type?.label }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label>Musiker *</label>
            <select v-model.number="form.musician_id" required>
              <option :value="null" disabled>Auswählen...</option>
              <option v-for="m in musicians" :key="m.id" :value="m.id">
                {{ m.last_name }} {{ m.first_name }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label>Datum *</label>
            <input type="date" v-model="form.start_date" required />
          </div>
        </div>
        <div style="display:flex;gap:0.5rem;margin-top:0.5rem">
          <button type="submit" class="btn-primary">Ausleihen</button>
          <button type="button" @click="showForm = false">Abbrechen</button>
        </div>
      </form>
    </div>

    <div class="toolbar">
      <label style="display:flex;align-items:center;gap:0.5rem;font-size:0.875rem">
        <input type="checkbox" v-model="activeOnly" style="width:auto" />
        Nur aktive Leihen
      </label>
    </div>

    <div v-if="loading" style="text-align:center;padding:2rem">Laden...</div>
    <table v-else-if="loans.length">
      <thead>
        <tr>
          <th>Instrument</th>
          <th>Inv.-Nr.</th>
          <th>Musiker</th>
          <th>Von</th>
          <th>Bis</th>
          <th>Status</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="l in loans" :key="l.id">
          <td>
            <router-link :to="`/instrumente/${l.instrument.id}`">
              {{ l.instrument.instrument_type.label }}
            </router-link>
          </td>
          <td>{{ l.instrument.inventory_nr }}</td>
          <td>
            <router-link :to="`/musiker/${l.musician.id}`">
              {{ l.musician.first_name }} {{ l.musician.last_name }}
            </router-link>
          </td>
          <td>{{ l.start_date }}</td>
          <td>{{ l.end_date || "—" }}</td>
          <td>
            <span :class="l.end_date ? 'badge badge-gray' : 'badge badge-green'">
              {{ l.end_date ? "Zurückgegeben" : "Ausgeliehen" }}
            </span>
          </td>
          <td>
            <button v-if="!l.end_date" class="btn-sm" @click="returnLoan(l.id)">Rückgabe</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else style="text-align:center;padding:2rem;color:var(--color-muted)">Keine Leihen vorhanden</p>
  </div>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add src/frontend/src/pages/LoanListPage.vue
git commit -m "feat: add loan register page with create and return actions"
```

---

## Task 16: Frontend — Settings Pages (Instrument Types & Currencies)

**Files:**
- Create: `src/frontend/src/pages/InstrumentTypeListPage.vue`
- Create: `src/frontend/src/pages/CurrencyListPage.vue`

- [ ] **Step 1: Create InstrumentTypeListPage.vue**

```vue
<script setup>
import { ref, onMounted } from "vue";
import { get, post, put, del } from "../lib/api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const items = ref([]);
const editing = ref(null);
const form = ref({ label: "", label_short: "" });
const deleteTarget = ref(null);

async function load() {
  items.value = await get("/instrument-types");
}

onMounted(load);

function startEdit(item) {
  editing.value = item.id;
  form.value = { label: item.label, label_short: item.label_short };
}

function startCreate() {
  editing.value = "new";
  form.value = { label: "", label_short: "" };
}

async function save() {
  try {
    if (editing.value === "new") {
      await post("/instrument-types", form.value);
    } else {
      await put(`/instrument-types/${editing.value}`, form.value);
    }
    editing.value = null;
    await load();
  } catch (e) {
    alert("Fehler: " + e.message);
  }
}

async function remove() {
  try {
    await del(`/instrument-types/${deleteTarget.value}`);
    deleteTarget.value = null;
    await load();
  } catch (e) {
    alert("Fehler: " + e.message);
    deleteTarget.value = null;
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Instrumententypen</h1>
      <button class="btn btn-primary" @click="startCreate">Neuer Typ</button>
    </div>

    <table>
      <thead>
        <tr><th>Bezeichnung</th><th>Kürzel</th><th style="width:120px"></th></tr>
      </thead>
      <tbody>
        <tr v-if="editing === 'new'">
          <td><input v-model="form.label" placeholder="Bezeichnung" /></td>
          <td><input v-model="form.label_short" placeholder="Kürzel" style="width:80px" /></td>
          <td>
            <div style="display:flex;gap:0.25rem">
              <button class="btn-sm btn-primary" @click="save">OK</button>
              <button class="btn-sm" @click="editing = null">X</button>
            </div>
          </td>
        </tr>
        <tr v-for="item in items" :key="item.id">
          <template v-if="editing === item.id">
            <td><input v-model="form.label" /></td>
            <td><input v-model="form.label_short" style="width:80px" /></td>
            <td>
              <div style="display:flex;gap:0.25rem">
                <button class="btn-sm btn-primary" @click="save">OK</button>
                <button class="btn-sm" @click="editing = null">X</button>
              </div>
            </td>
          </template>
          <template v-else>
            <td>{{ item.label }}</td>
            <td>{{ item.label_short }}</td>
            <td>
              <div style="display:flex;gap:0.25rem">
                <button class="btn-sm" @click="startEdit(item)">Bearbeiten</button>
                <button class="btn-sm btn-danger" @click="deleteTarget = item.id">X</button>
              </div>
            </td>
          </template>
        </tr>
      </tbody>
    </table>

    <ConfirmDialog
      :open="!!deleteTarget"
      title="Typ löschen"
      message="Soll dieser Instrumententyp wirklich gelöscht werden?"
      @confirm="remove"
      @cancel="deleteTarget = null"
    />
  </div>
</template>
```

- [ ] **Step 2: Create CurrencyListPage.vue**

```vue
<script setup>
import { ref, onMounted } from "vue";
import { get, post, put, del } from "../lib/api.js";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const items = ref([]);
const editing = ref(null);
const form = ref({ label: "", abbreviation: "" });
const deleteTarget = ref(null);

async function load() {
  items.value = await get("/currencies");
}

onMounted(load);

function startEdit(item) {
  editing.value = item.id;
  form.value = { label: item.label, abbreviation: item.abbreviation };
}

function startCreate() {
  editing.value = "new";
  form.value = { label: "", abbreviation: "" };
}

async function save() {
  try {
    if (editing.value === "new") {
      await post("/currencies", form.value);
    } else {
      await put(`/currencies/${editing.value}`, form.value);
    }
    editing.value = null;
    await load();
  } catch (e) {
    alert("Fehler: " + e.message);
  }
}

async function remove() {
  try {
    await del(`/currencies/${deleteTarget.value}`);
    deleteTarget.value = null;
    await load();
  } catch (e) {
    alert("Fehler: " + e.message);
    deleteTarget.value = null;
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Währungen</h1>
      <button class="btn btn-primary" @click="startCreate">Neue Währung</button>
    </div>

    <table>
      <thead>
        <tr><th>Bezeichnung</th><th>Kürzel</th><th style="width:120px"></th></tr>
      </thead>
      <tbody>
        <tr v-if="editing === 'new'">
          <td><input v-model="form.label" placeholder="Bezeichnung" /></td>
          <td><input v-model="form.abbreviation" placeholder="Kürzel" style="width:80px" /></td>
          <td>
            <div style="display:flex;gap:0.25rem">
              <button class="btn-sm btn-primary" @click="save">OK</button>
              <button class="btn-sm" @click="editing = null">X</button>
            </div>
          </td>
        </tr>
        <tr v-for="item in items" :key="item.id">
          <template v-if="editing === item.id">
            <td><input v-model="form.label" /></td>
            <td><input v-model="form.abbreviation" style="width:80px" /></td>
            <td>
              <div style="display:flex;gap:0.25rem">
                <button class="btn-sm btn-primary" @click="save">OK</button>
                <button class="btn-sm" @click="editing = null">X</button>
              </div>
            </td>
          </template>
          <template v-else>
            <td>{{ item.label }}</td>
            <td>{{ item.abbreviation }}</td>
            <td>
              <div style="display:flex;gap:0.25rem">
                <button class="btn-sm" @click="startEdit(item)">Bearbeiten</button>
                <button class="btn-sm btn-danger" @click="deleteTarget = item.id">X</button>
              </div>
            </td>
          </template>
        </tr>
      </tbody>
    </table>

    <ConfirmDialog
      :open="!!deleteTarget"
      title="Währung löschen"
      message="Soll diese Währung wirklich gelöscht werden?"
      @confirm="remove"
      @cancel="deleteTarget = null"
    />
  </div>
</template>
```

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/pages/InstrumentTypeListPage.vue src/frontend/src/pages/CurrencyListPage.vue
git commit -m "feat: add instrument type and currency settings pages"
```

---

## Task 17: Integration Test and Final Verification

- [ ] **Step 1: Run all backend tests**

Run: `cd /workspaces/mv_hofki && python -m pytest tests/backend/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run linter**

Run: `cd /workspaces/mv_hofki && pre-commit run --all-files`
Fix any issues.

- [ ] **Step 3: Run frontend build**

Run: `frontend-restart` then `frontend-logs`
Verify no build errors.

- [ ] **Step 4: Restart server and verify**

Run: `server-restart` then `server-logs`
Verify no startup errors, seed data loaded.

- [ ] **Step 5: Manual smoke test via API**

```bash
curl -s http://localhost:8000/api/v1/dashboard | python -m json.tool
curl -s http://localhost:8000/api/v1/instrument-types | python -m json.tool
curl -s http://localhost:8000/api/v1/currencies | python -m json.tool
```

- [ ] **Step 6: Update CLAUDE.md with infrastructure info**

Add to the `## Infrastructure` section:

```markdown
- **Database:** SQLite at `data/mv_hofki.db`, managed via SQLAlchemy async + Alembic
- **Migrations:** `PYTHONPATH=src/backend alembic upgrade head`
- **Seed data:** Instrument types and currencies are seeded on app startup if tables are empty
```

- [ ] **Step 7: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with database infrastructure info"
```
