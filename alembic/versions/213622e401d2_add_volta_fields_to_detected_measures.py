"""add_volta_fields_to_detected_measures

Revision ID: 213622e401d2
Revises: cc7fdc596d79
Create Date: 2026-04-02 23:03:52.454232

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "213622e401d2"
down_revision: str | Sequence[str] | None = "cc7fdc596d79"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("detected_measures") as batch_op:
        batch_op.add_column(sa.Column("volta_number", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("volta_group_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("detected_measures") as batch_op:
        batch_op.drop_column("volta_group_id")
        batch_op.drop_column("volta_number")
