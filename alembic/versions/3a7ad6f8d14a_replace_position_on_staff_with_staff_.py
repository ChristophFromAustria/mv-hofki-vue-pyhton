"""replace_position_on_staff_with_staff_coords

Revision ID: 3a7ad6f8d14a
Revises: 869c1ea9279f
Create Date: 2026-04-02 12:06:43.974360

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3a7ad6f8d14a"
down_revision: str | Sequence[str] | None = "869c1ea9279f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("detected_symbols") as batch_op:
        batch_op.drop_column("position_on_staff")
        batch_op.add_column(sa.Column("staff_y_top", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("staff_y_bottom", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("staff_x_start", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("staff_x_end", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("detected_symbols") as batch_op:
        batch_op.drop_column("staff_x_end")
        batch_op.drop_column("staff_x_start")
        batch_op.drop_column("staff_y_bottom")
        batch_op.drop_column("staff_y_top")
        batch_op.add_column(sa.Column("position_on_staff", sa.Integer(), nullable=True))
