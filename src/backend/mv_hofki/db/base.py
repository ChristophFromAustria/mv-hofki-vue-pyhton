"""SQLAlchemy declarative base."""

from sqlalchemy.orm import DeclarativeBase

# Registers the SQL function fold() on every connection (see text_fold) and
# the soft-delete filter on every ORM query (see soft_delete).
from mv_hofki.db import soft_delete, text_fold  # noqa: F401


class Base(DeclarativeBase):
    pass
