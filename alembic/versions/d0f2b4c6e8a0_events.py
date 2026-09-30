"""Event log (who changed what, when)

Revision ID: d0f2b4c6e8a0
Revises: c8e0a2b4d6f8
Create Date: 2026-09-30 16:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0f2b4c6e8a0"
down_revision: str | Sequence[str] | None = "c8e0a2b4d6f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("actor", sa.String(200), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("entity_label", sa.String(300), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("summary", sa.String(300), nullable=True),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("musician_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_events_item_id", "events", ["item_id"])
    op.create_index("ix_events_musician_id", "events", ["musician_id"])
    op.create_index("ix_events_at", "events", ["at"])


def downgrade() -> None:
    op.drop_table("events")
