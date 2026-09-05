"""store the edited LilyPond version of a scan

Revision ID: e5a7c9d1f3b5
Revises: d4f6b8c0e2a4
Create Date: 2026-09-06 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a7c9d1f3b5"
down_revision: str | Sequence[str] | None = "d4f6b8c0e2a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sheet_music_scans") as batch_op:
        batch_op.add_column(sa.Column("lilypond_edited", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("lilypond_edited_at", sa.DateTime(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("sheet_music_scans") as batch_op:
        batch_op.drop_column("lilypond_edited_at")
        batch_op.drop_column("lilypond_edited")
