"""restructure adjustments_json to grouped format

Revision ID: 642a8244b50e
Revises: 74b05fa3a239
Create Date: 2026-04-01 11:20:00.209895

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "642a8244b50e"
down_revision: str | Sequence[str] | None = "74b05fa3a239"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Ad-hoc table reference for data migration
t_scans = sa.table(
    "sheet_music_scans",
    sa.column("id", sa.Integer),
    sa.column("adjustments_json", sa.Text),
)

PREPROCESSING_KEYS = {
    "brightness",
    "contrast",
    "threshold",
    "rotation",
    "morphology_kernel_size",
}


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.select(t_scans.c.id, t_scans.c.adjustments_json).where(
            t_scans.c.adjustments_json.isnot(None)
        )
    ).fetchall()

    for row_id, raw in rows:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        # Already migrated
        if "preprocessing" in data:
            continue

        preprocessing = {}
        leftover = {}
        for k, v in data.items():
            if k in PREPROCESSING_KEYS:
                preprocessing[k] = v
            else:
                leftover[k] = v

        new_data = {"preprocessing": preprocessing, **leftover}
        conn.execute(
            t_scans.update()
            .where(t_scans.c.id == row_id)
            .values(adjustments_json=json.dumps(new_data))
        )


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.select(t_scans.c.id, t_scans.c.adjustments_json).where(
            t_scans.c.adjustments_json.isnot(None)
        )
    ).fetchall()

    for row_id, raw in rows:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        if "preprocessing" not in data:
            continue

        preprocessing = data.pop("preprocessing", {})
        flat = {**preprocessing, **data}
        conn.execute(
            t_scans.update()
            .where(t_scans.c.id == row_id)
            .values(adjustments_json=json.dumps(flat))
        )
