"""Word-wise, tolerant search conditions.

A search text is split into words; every word must occur (as a substring) in at
least one of the searched fields. Fields and words are compared through
``fold()`` (see ``db/text_fold.py``), so case, accents and ue/ü spellings don't
matter.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy import ColumnElement, and_, func, or_

from mv_hofki.db.text_fold import fold


def search_words(text: str | None) -> list[str]:
    """The folded, distinct words of a search text, in order."""
    words: list[str] = []
    for raw in (text or "").split():
        word = fold(raw) or ""
        if word and word not in words:
            words.append(word)
    return words


def _like_pattern(word: str) -> str:
    escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def folded_contains(column: Any, word: str) -> ColumnElement[bool]:
    """``column`` contains the (already folded) ``word``, tolerantly."""
    return func.fold(column).like(_like_pattern(word), escape="\\")


def words_clause(
    text: str | None,
    columns: Sequence[Any],
    extra: Sequence[Callable[[str], ColumnElement[bool]]] = (),
) -> ColumnElement[bool] | None:
    """Every word of ``text`` in one of ``columns`` (or matched by one of the
    ``extra`` per-word conditions, e.g. an EXISTS over a related table).
    None when the text has no words."""
    words = search_words(text)
    if not words:
        return None
    per_word = [
        or_(
            *(folded_contains(col, word) for col in columns),
            *(make(word) for make in extra),
        )
        for word in words
    ]
    return and_(*per_word)
