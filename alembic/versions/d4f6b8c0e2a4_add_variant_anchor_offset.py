"""add anchor offset to symbol_variants

Revision ID: d4f6b8c0e2a4
Revises: c3e5a7b9d1f3
Create Date: 2026-09-05 09:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f6b8c0e2a4"
down_revision: str | Sequence[str] | None = "c3e5a7b9d1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("symbol_variants") as batch_op:
        batch_op.add_column(sa.Column("anchor_dx", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("anchor_dy", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("symbol_variants") as batch_op:
        batch_op.drop_column("anchor_dy")
        batch_op.drop_column("anchor_dx")
