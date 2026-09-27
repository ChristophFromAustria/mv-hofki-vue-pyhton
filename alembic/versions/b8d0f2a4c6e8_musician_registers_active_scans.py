"""Musician registers and active flag, image kind/caption, long item notes

- ``registers`` + ``musician_registers`` (many-to-many)
- ``musicians.is_active`` (existing musicians stay active)
- ``item_images.kind`` ("foto" | "scan") and ``item_images.caption``
- ``inventory_items.notes`` becomes TEXT (provenance notes exceed 500 chars)

Revision ID: b8d0f2a4c6e8
Revises: a7c9e1b3d5f7
Create Date: 2026-09-27 20:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d0f2a4c6e8"
down_revision: str | Sequence[str] | None = "a7c9e1b3d5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "registers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(100), nullable=False, unique=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "expects_instrument", sa.Boolean(), nullable=False, server_default="1"
        ),
    )
    op.create_table(
        "musician_registers",
        sa.Column(
            "musician_id",
            sa.Integer(),
            sa.ForeignKey("musicians.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "register_id",
            sa.Integer(),
            sa.ForeignKey("registers.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )
    with op.batch_alter_table("musicians") as batch_op:
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1")
        )
    with op.batch_alter_table("item_images") as batch_op:
        batch_op.add_column(
            sa.Column("kind", sa.String(20), nullable=False, server_default="foto")
        )
        batch_op.add_column(sa.Column("caption", sa.String(300), nullable=True))
    with op.batch_alter_table("inventory_items") as batch_op:
        batch_op.alter_column(
            "notes",
            type_=sa.Text(),
            existing_type=sa.String(500),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("inventory_items") as batch_op:
        batch_op.alter_column(
            "notes",
            type_=sa.String(500),
            existing_type=sa.Text(),
            existing_nullable=True,
        )
    with op.batch_alter_table("item_images") as batch_op:
        batch_op.drop_column("caption")
        batch_op.drop_column("kind")
    with op.batch_alter_table("musicians") as batch_op:
        batch_op.drop_column("is_active")
    op.drop_table("musician_registers")
    op.drop_table("registers")
