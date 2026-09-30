"""Items and musicians never reuse ids (AUTOINCREMENT)

Their event history (and an item's upload folders) are keyed by id; plain
SQLite rowids hand the id of a row deleted for good to the next new row.

Revision ID: f4b6d8a0c2e4
Revises: e2a4c6e8f0b2
Create Date: 2026-09-30 19:00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4b6d8a0c2e4"
down_revision: str | Sequence[str] | None = "e2a4c6e8f0b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("inventory_items", "musicians")


def upgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(
            table, recreate="always", table_kwargs={"sqlite_autoincrement": True}
        ):
            pass
        # Continue after the highest id ever used (ids of rows deleted for
        # good too, as far as the event log knows them). SQLite created the
        # sqlite_sequence row while copying the table.
        entity = "item" if table == "inventory_items" else "musician"
        highest = f"""
            SELECT MAX(m) FROM (
                SELECT COALESCE(MAX(id), 0) AS m FROM {table}
                UNION ALL
                SELECT COALESCE(MAX(entity_id), 0) FROM events
                WHERE entity_type = '{entity}'
            )
        """
        op.execute(
            f"INSERT INTO sqlite_sequence (name, seq) SELECT '{table}', 0 "
            f"WHERE NOT EXISTS (SELECT 1 FROM sqlite_sequence WHERE name = '{table}')"
        )
        op.execute(
            f"UPDATE sqlite_sequence SET seq = MAX(seq, ({highest})) "
            f"WHERE name = '{table}'"
        )


def downgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(
            table, recreate="always", table_kwargs={"sqlite_autoincrement": False}
        ):
            pass
