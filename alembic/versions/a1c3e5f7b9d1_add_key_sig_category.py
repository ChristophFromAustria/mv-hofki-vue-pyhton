"""move key-signature templates to category key_sig and complete the list

Revision ID: a1c3e5f7b9d1
Revises: 70dff1e2a8de
Create Date: 2026-09-04 12:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c3e5f7b9d1"
down_revision: str | Sequence[str] | None = "70dff1e2a8de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _flats_from_template(name: str, display: str) -> int | None:
    """Best-effort: derive the flat count (negative = sharps) of a template."""
    import re

    from mv_hofki.services.scanner.library.key_signatures import (
        GERMAN_MAJOR_FLATS,
        GERMAN_MINOR_FLATS,
    )

    for text in (display or "", name or ""):
        t = text.strip().lower().replace("_", "-")
        m = re.match(r"^([a-h](?:is|es|s)?)-?(dur|moll|major|minor)$", t)
        if m:
            table = (
                GERMAN_MAJOR_FLATS
                if m.group(2) in ("dur", "major")
                else GERMAN_MINOR_FLATS
            )
            if m.group(1) in table:
                return table[m.group(1)]
        m = re.match(r"^(\d)\s*(b|♭)$", t)
        if m:
            return int(m.group(1))
        m = re.match(r"^(\d)\s*(#|♯|kreuz)$", t)
        if m:
            return -int(m.group(1))
    return None


def upgrade() -> None:
    from mv_hofki.services.scanner.library.key_signatures import (
        canonical_name_for_flats,
        key_signature_templates,
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, name, display_name, category FROM symbol_templates")
    ).fetchall()

    existing_names = {r[1] for r in rows}
    taken_canonical: set[str] = set()

    # 1. Move user-made key-signature templates into key_sig, canonical names
    for tid, name, display, category in rows:
        if category not in ("accidental", "other", "key_sig"):
            continue
        flats = _flats_from_template(name, display)
        if flats is None:
            continue
        is_group = bool(
            __import__("re").match(r"^\d\s*(b|♭|#|♯)$", (name or "").strip().lower())
            or __import__("re").search(
                r"dur|moll|major|minor", f"{name} {display}".lower()
            )
        )
        if not is_group:
            continue  # single accidental (Be, Kreuz) stays an accidental
        canonical = canonical_name_for_flats(flats)
        new_name = name
        if (
            canonical
            and canonical not in existing_names
            and canonical not in taken_canonical
        ):
            new_name = canonical
        if canonical:
            taken_canonical.add(canonical)
        conn.execute(
            sa.text(
                "UPDATE symbol_templates SET category = 'key_sig', name = :new_name "
                "WHERE id = :tid"
            ),
            {"new_name": new_name, "tid": tid},
        )
        existing_names.discard(name)
        existing_names.add(new_name)

    # 2. Insert the missing canonical key signatures as seed templates
    for tpl in key_signature_templates():
        if tpl["name"] in existing_names or tpl["name"] in taken_canonical:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO symbol_templates "
                "(category, name, display_name, musicxml_element, lilypond_token, is_seed, created_at) "
                "VALUES ('key_sig', :name, :display_name, :musicxml_element, :lilypond_token, 1, CURRENT_TIMESTAMP)"
            ),
            {
                "name": tpl["name"],
                "display_name": tpl["display_name"],
                "musicxml_element": tpl["musicxml_element"],
                "lilypond_token": tpl["lilypond_token"],
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM symbol_templates WHERE category = 'key_sig' AND is_seed = 1 "
            "AND id NOT IN (SELECT DISTINCT template_id FROM symbol_variants)"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE symbol_templates SET category = 'accidental' WHERE category = 'key_sig'"
        )
    )
