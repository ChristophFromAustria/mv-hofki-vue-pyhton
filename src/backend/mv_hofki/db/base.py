"""SQLAlchemy declarative base."""

from sqlalchemy.orm import DeclarativeBase

# Registers the SQL function fold() on every connection (see text_fold).
from mv_hofki.db import text_fold  # noqa: F401


class Base(DeclarativeBase):
    pass
