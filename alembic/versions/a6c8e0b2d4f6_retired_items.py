"""Items can be retired (sold, lost, scrapped, …) and stay with their history

Revision ID: a6c8e0b2d4f6
Revises: f4b6d8a0c2e4
Create Date: 2026-09-30 20:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a6c8e0b2d4f6"
down_revision: str | Sequence[str] | None = "f4b6d8a0c2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("inventory_items") as batch_op:
        batch_op.add_column(sa.Column("retired_at", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("retired_reason", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("retired_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("inventory_items") as batch_op:
        batch_op.drop_column("retired_notes")
        batch_op.drop_column("retired_reason")
        batch_op.drop_column("retired_at")
