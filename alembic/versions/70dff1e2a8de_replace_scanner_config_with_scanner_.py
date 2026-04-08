"""replace scanner_config with scanner_config_entry

Revision ID: 70dff1e2a8de
Revises: e8e7aacfc5e9
Create Date: 2026-04-08 13:02:41.263030

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "70dff1e2a8de"
down_revision: str | Sequence[str] | None = "e8e7aacfc5e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create new table
    op.create_table(
        "scanner_config_entry",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("default_value", sa.Text(), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("group_path", sa.String(200), nullable=True),
        sa.Column("min", sa.Float(), nullable=True),
        sa.Column("max", sa.Float(), nullable=True),
        sa.Column("step", sa.Float(), nullable=True),
        sa.Column("options", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )

    # 2. Migrate values from old table
    import json

    from mv_hofki.services.scanner_config_registry import SCANNER_CONFIG_REGISTRY

    conn = op.get_bind()
    old_row = None
    try:
        old_row = (
            conn.execute(sa.text("SELECT * FROM scanner_config LIMIT 1"))
            .mappings()
            .first()
        )
    except Exception:
        pass

    for entry in SCANNER_CONFIG_REGISTRY:
        key = entry["key"]
        default_val = entry["default_value"]
        value = default_val

        if old_row and key in old_row:
            old_val = old_row[key]
            if entry["type"] == "toggle":
                value = "true" if old_val else "false"
            else:
                value = str(old_val)

        options_str = json.dumps(entry["options"]) if entry.get("options") else None
        conn.execute(
            sa.text(
                "INSERT INTO scanner_config_entry "
                "(key, value, default_value, type, label, group_path, min, max, step, options, sort_order) "
                "VALUES (:key, :value, :default_value, :type, :label, :group_path, :min, :max, :step, :options, :sort_order)"
            ),
            {
                "key": key,
                "value": value,
                "default_value": default_val,
                "type": entry["type"],
                "label": entry["label"],
                "group_path": entry.get("group_path"),
                "min": entry.get("min"),
                "max": entry.get("max"),
                "step": entry.get("step"),
                "options": options_str,
                "sort_order": entry.get("sort_order", 0),
            },
        )

    # 3. Drop old table
    op.drop_table("scanner_config")

    # 4. Clear scan-specific overrides
    conn.execute(sa.text("UPDATE sheet_music_scans SET adjustments_json = NULL"))


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported")
