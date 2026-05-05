"""remove corrected_image_path and pipeline_config_json from sheet_music_scans

Revision ID: 869c1ea9279f
Revises: 642a8244b50e
Create Date: 2026-04-01 16:04:43.062726

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "869c1ea9279f"
down_revision: str | Sequence[str] | None = "642a8244b50e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sheet_music_scans") as batch_op:
        batch_op.drop_column("corrected_image_path")
        batch_op.drop_column("pipeline_config_json")


def downgrade() -> None:
    with op.batch_alter_table("sheet_music_scans") as batch_op:
        batch_op.add_column(sa.Column("pipeline_config_json", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("corrected_image_path", sa.String(500), nullable=True)
        )
