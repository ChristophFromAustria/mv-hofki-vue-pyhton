"""Remember inventory numbers of deleted/renumbered items so they are never reused

Revision ID: a4c6e8f0b2d4
Revises: d1f3a5c7e9b2
Create Date: 2026-09-30 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4c6e8f0b2d4"
down_revision: str | Sequence[str] | None = "d1f3a5c7e9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "retired_inventory_numbers",
        sa.Column("category", sa.String(20), primary_key=True),
        sa.Column("number_prefix", sa.String(10), primary_key=True),
        sa.Column("inventory_nr", sa.Integer(), primary_key=True),
        sa.Column(
            "retired_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("retired_inventory_numbers")
