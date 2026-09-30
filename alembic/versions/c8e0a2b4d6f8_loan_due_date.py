"""Loans get a planned return date (overdue when open after it)

Revision ID: c8e0a2b4d6f8
Revises: b6d8f0a2c4e6
Create Date: 2026-09-30 14:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8e0a2b4d6f8"
down_revision: str | Sequence[str] | None = "b6d8f0a2c4e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("loan_register") as batch_op:
        batch_op.add_column(sa.Column("due_date", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("loan_register") as batch_op:
        batch_op.drop_column("due_date")
