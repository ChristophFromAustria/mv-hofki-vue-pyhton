"""Edited images keep their original file (restore anytime)

Revision ID: 74ccdd1dd0b9
Revises: a6c8e0b2d4f6
Create Date: 2026-10-02 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "74ccdd1dd0b9"
down_revision: str | Sequence[str] | None = "a6c8e0b2d4f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("item_images") as batch_op:
        batch_op.add_column(
            sa.Column("original_filename", sa.String(255), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("item_images") as batch_op:
        batch_op.drop_column("original_filename")
