"""add detected_measures table

Revision ID: 86a117ea2a72
Revises: 3a7ad6f8d14a
Create Date: 2026-04-02 15:44:39.679156

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "86a117ea2a72"
down_revision: str | Sequence[str] | None = "3a7ad6f8d14a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "detected_measures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "scan_id",
            sa.Integer(),
            sa.ForeignKey("sheet_music_scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "staff_id",
            sa.Integer(),
            sa.ForeignKey("detected_staves.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("staff_index", sa.Integer(), nullable=False),
        sa.Column("measure_number_in_staff", sa.Integer(), nullable=False),
        sa.Column("global_measure_number", sa.Integer(), nullable=False),
        sa.Column("x_start", sa.Integer(), nullable=False),
        sa.Column("x_end", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("detected_measures")
