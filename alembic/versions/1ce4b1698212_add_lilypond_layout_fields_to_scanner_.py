"""add_lilypond_layout_fields_to_scanner_config

Revision ID: 1ce4b1698212
Revises: 15139d895f40
Create Date: 2026-04-02 21:45:42.152652

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1ce4b1698212"
down_revision: str | Sequence[str] | None = "15139d895f40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("scanner_config") as batch_op:
        batch_op.add_column(
            sa.Column("ly_top_margin", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.add_column(
            sa.Column(
                "ly_bottom_margin", sa.Integer(), nullable=False, server_default="4"
            )
        )
        batch_op.add_column(
            sa.Column(
                "ly_left_margin", sa.Integer(), nullable=False, server_default="16"
            )
        )
        batch_op.add_column(
            sa.Column(
                "ly_right_margin", sa.Integer(), nullable=False, server_default="16"
            )
        )
        batch_op.add_column(
            sa.Column(
                "ly_staff_size", sa.Integer(), nullable=False, server_default="17"
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("scanner_config") as batch_op:
        batch_op.drop_column("ly_staff_size")
        batch_op.drop_column("ly_right_margin")
        batch_op.drop_column("ly_left_margin")
        batch_op.drop_column("ly_bottom_margin")
        batch_op.drop_column("ly_top_margin")
