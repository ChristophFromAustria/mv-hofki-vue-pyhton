"""Inventory items get a quantity (identical pieces under one number)

Revision ID: c9e1a3b5d7f9
Revises: b8d0f2a4c6e8
Create Date: 2026-09-27 21:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9e1a3b5d7f9"
down_revision: str | Sequence[str] | None = "b8d0f2a4c6e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("inventory_items") as batch_op:
        batch_op.add_column(
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1")
        )


def downgrade() -> None:
    with op.batch_alter_table("inventory_items") as batch_op:
        batch_op.drop_column("quantity")
