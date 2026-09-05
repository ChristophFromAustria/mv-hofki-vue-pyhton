"""add per-template matching parameters to symbol_templates

Revision ID: c3e5a7b9d1f3
Revises: b2d4f6a8c0e2
Create Date: 2026-09-04 23:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e5a7b9d1f3"
down_revision: str | Sequence[str] | None = "b2d4f6a8c0e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("symbol_templates") as batch_op:
        batch_op.add_column(sa.Column("min_confidence", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("confidence_weight", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "merge_overlapping",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("symbol_templates") as batch_op:
        batch_op.drop_column("merge_overlapping")
        batch_op.drop_column("confidence_weight")
        batch_op.drop_column("min_confidence")
