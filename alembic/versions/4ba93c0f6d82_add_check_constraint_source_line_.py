"""add check constraint source_line_spacing gt 5

Revision ID: 4ba93c0f6d82
Revises: af1199d3ac7f
Create Date: 2026-03-26 09:28:25.666867

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4ba93c0f6d82"
down_revision: str | Sequence[str] | None = "af1199d3ac7f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add NOT NULL + CHECK(source_line_spacing > 5) to symbol_variants.

    SQLite doesn't support ALTER COLUMN or ADD CONSTRAINT, so we rebuild
    the table via Alembic's batch mode.
    """
    with op.batch_alter_table("symbol_variants", schema=None) as batch_op:
        batch_op.alter_column(
            "source_line_spacing",
            existing_type=sa.FLOAT(),
            nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_symbol_variants_source_line_spacing_min",
            condition="source_line_spacing > 5",
        )


def downgrade() -> None:
    """Remove the check constraint and allow NULL again."""
    with op.batch_alter_table("symbol_variants", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_symbol_variants_source_line_spacing_min", type_="check"
        )
        batch_op.alter_column(
            "source_line_spacing",
            existing_type=sa.FLOAT(),
            nullable=True,
        )
