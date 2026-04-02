"""add_end_barline_to_detected_measures

Revision ID: 15139d895f40
Revises: 86a117ea2a72
Create Date: 2026-04-02 20:36:59.806548

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "15139d895f40"
down_revision: str | Sequence[str] | None = "86a117ea2a72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("detected_measures") as batch_op:
        batch_op.add_column(sa.Column("end_barline", sa.String(50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("detected_measures") as batch_op:
        batch_op.drop_column("end_barline")
