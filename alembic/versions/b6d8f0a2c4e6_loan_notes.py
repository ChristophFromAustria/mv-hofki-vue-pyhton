"""Loans get free-text notes

Revision ID: b6d8f0a2c4e6
Revises: a4c6e8f0b2d4
Create Date: 2026-09-30 13:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6d8f0a2c4e6"
down_revision: str | Sequence[str] | None = "a4c6e8f0b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("loan_register") as batch_op:
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("loan_register") as batch_op:
        batch_op.drop_column("notes")
