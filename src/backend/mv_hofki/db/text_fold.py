"""Tolerant text comparison: the SQL function ``fold()``.

``fold`` lower-cases (Unicode-aware, ß → ss), drops accents (ü → u, é → e) and
reads German umlaut spellings the same way (ue → u, oe → o, ae → a). Searching
folds both the column and the search words, so "mueller", "müller" and "MÜLLER"
all find "Müller" — plain SQLite LIKE ignores case for ASCII letters only.

The frontend mirrors this in ``lib/highlight.js`` to mark hits; keep both in step.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine

_DIGRAPHS = (("ae", "a"), ("oe", "o"), ("ue", "u"))


def fold(text: str | None) -> str | None:
    if text is None:
        return None
    decomposed = unicodedata.normalize("NFKD", str(text).casefold())
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    for digraph, letter in _DIGRAPHS:
        plain = plain.replace(digraph, letter)
    return plain


@event.listens_for(Engine, "connect")
def _register_fold(dbapi_connection: Any, _record: Any) -> None:
    """Make fold() available on every SQLite connection (app, tests, Alembic)."""
    create_function = getattr(dbapi_connection, "create_function", None)
    if create_function is not None:
        create_function("fold", 1, fold, deterministic=True)
