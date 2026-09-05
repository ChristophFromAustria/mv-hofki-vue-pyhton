"""add matched_variant_id to detected_symbols

Revision ID: b2d4f6a8c0e2
Revises: a1c3e5f7b9d1
Create Date: 2026-09-04 13:10:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2d4f6a8c0e2"
down_revision: str | Sequence[str] | None = "a1c3e5f7b9d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("detected_symbols") as batch_op:
        batch_op.add_column(
            sa.Column("matched_variant_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_detected_symbols_matched_variant_id",
            "symbol_variants",
            ["matched_variant_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("detected_symbols") as batch_op:
        batch_op.drop_constraint(
            "fk_detected_symbols_matched_variant_id", type_="foreignkey"
        )
        batch_op.drop_column("matched_variant_id")
