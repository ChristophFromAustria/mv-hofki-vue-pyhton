"""update instrument_invoices add title and required fields

Revision ID: 85d27ee9935e
Revises: 73b7a5de5b97
Create Date: 2026-03-19 08:49:35.595209

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision: str = "85d27ee9935e"
down_revision: str | Sequence[str] | None = "73b7a5de5b97"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table("instrument_invoices")
    op.create_table(
        "instrument_invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_nr", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency_id", sa.Integer(), nullable=False),
        sa.Column("date_issued", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("invoice_issuer", sa.String(length=100), nullable=True),
        sa.Column("issuer_address", sa.String(length=255), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["currency_id"], ["currencies.id"]),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("instrument_invoices")
    op.create_table(
        "instrument_invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("currency_id", sa.Integer(), nullable=False),
        sa.Column("date_issued", sa.Date(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("invoice_nr", sa.String(length=100), nullable=True),
        sa.Column("invoice_issuer", sa.String(length=100), nullable=True),
        sa.Column("issuer_address", sa.String(length=255), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["currency_id"], ["currencies.id"]),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
