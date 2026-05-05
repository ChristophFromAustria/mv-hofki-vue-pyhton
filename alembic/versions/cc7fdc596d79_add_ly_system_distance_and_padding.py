"""add_ly_system_distance_and_padding

Revision ID: cc7fdc596d79
Revises: 1ce4b1698212
Create Date: 2026-04-02 21:58:33.882145

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cc7fdc596d79"
down_revision: str | Sequence[str] | None = "1ce4b1698212"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("scanner_config") as batch_op:
        batch_op.add_column(
            sa.Column(
                "ly_system_distance", sa.Integer(), nullable=False, server_default="6"
            )
        )
        batch_op.add_column(
            sa.Column(
                "ly_system_padding", sa.Float(), nullable=False, server_default="0.6"
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("scanner_config") as batch_op:
        batch_op.drop_column("ly_system_padding")
        batch_op.drop_column("ly_system_distance")
