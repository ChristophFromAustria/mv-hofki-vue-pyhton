"""Papierkorb: deleted_at on items, musicians, invoices, images and master data

Revision ID: e2a4c6e8f0b2
Revises: d0f2b4c6e8a0
Create Date: 2026-09-30 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2a4c6e8f0b2"
down_revision: str | Sequence[str] | None = "d0f2b4c6e8a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "inventory_items",
    "musicians",
    "item_invoices",
    "item_images",
    "instrument_types",
    "clothing_types",
    "registers",
    "general_item_categories",
    "sheet_music_genres",
    "currencies",
)


def upgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("deleted_at")
