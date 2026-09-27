"""General items get free categories (many per item)

Revision ID: d1f3a5c7e9b2
Revises: c9e1a3b5d7f9
Create Date: 2026-09-27 22:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1f3a5c7e9b2"
down_revision: str | Sequence[str] | None = "c9e1a3b5d7f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "general_item_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(50), nullable=False, unique=True),
    )
    op.create_table(
        "general_item_category_links",
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("inventory_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("general_item_categories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("general_item_category_links")
    op.drop_table("general_item_categories")
