"""KI-Import: import_sessions and import_pages

Revision ID: f2b7c9d4e6a1
Revises: e5a7c9d1f3b5
Create Date: 2026-09-06 16:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b7c9d4e6a1"
down_revision: str | Sequence[str] | None = "e5a7c9d1f3b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("archive_dir", sa.String(length=500), nullable=True),
        sa.Column("draft_json", sa.Text(), nullable=True),
        sa.Column("import_result_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "import_pages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("import_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.String(length=500), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("extraction_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_import_pages_session_id", "import_pages", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_import_pages_session_id", table_name="import_pages")
    op.drop_table("import_pages")
    op.drop_table("import_sessions")
