"""Inventory numbers per prefix: instruments numbered per type short code

Adds ``inventory_items.number_prefix``: the category letter (K, N, A) or, for
instruments, the upper-cased short code of the instrument type ("TU", "KL").
Uniqueness moves from (category, inventory_nr) to
(category, number_prefix, inventory_nr). Existing numbers stay as they are; they
were unique per category, so they are unique per prefix too.

Revision ID: a7c9e1b3d5f7
Revises: f2b7c9d4e6a1
Create Date: 2026-09-27 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c9e1b3d5f7"
down_revision: str | Sequence[str] | None = "f2b7c9d4e6a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The original unique constraint is unnamed; a naming convention lets batch mode
# address it on SQLite.
NAMING = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade() -> None:
    with op.batch_alter_table("inventory_items") as batch_op:
        batch_op.add_column(sa.Column("number_prefix", sa.String(10), nullable=True))

    op.execute(
        """
        UPDATE inventory_items SET number_prefix = CASE category
            WHEN 'clothing' THEN 'K'
            WHEN 'sheet_music' THEN 'N'
            WHEN 'general_item' THEN 'A'
        END
        WHERE category != 'instrument'
        """
    )
    op.execute(
        """
        UPDATE inventory_items SET number_prefix = (
            SELECT upper(trim(t.label_short))
            FROM instrument_details d
            JOIN instrument_types t ON t.id = d.instrument_type_id
            WHERE d.item_id = inventory_items.id
        )
        WHERE category = 'instrument'
        """
    )
    op.execute(
        "UPDATE inventory_items SET number_prefix = 'I' WHERE number_prefix IS NULL"
    )

    with op.batch_alter_table(
        "inventory_items", naming_convention=NAMING, recreate="always"
    ) as batch_op:
        batch_op.alter_column("number_prefix", nullable=False)
        batch_op.drop_constraint("uq_inventory_items_category", type_="unique")
        batch_op.create_unique_constraint(
            "uq_inventory_number", ["category", "number_prefix", "inventory_nr"]
        )


def downgrade() -> None:
    # Per-prefix numbers can repeat within a category; renumber instruments into
    # one sequence (ordered by prefix and number) before restoring the old key.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id FROM inventory_items WHERE category = 'instrument' "
            "ORDER BY number_prefix, inventory_nr"
        )
    ).fetchall()
    for nr, (item_id,) in enumerate(rows, 1):
        bind.execute(
            sa.text("UPDATE inventory_items SET inventory_nr = -:nr WHERE id = :id"),
            {"nr": nr, "id": item_id},
        )
    bind.execute(
        sa.text(
            "UPDATE inventory_items SET inventory_nr = -inventory_nr "
            "WHERE category = 'instrument'"
        )
    )

    with op.batch_alter_table("inventory_items", recreate="always") as batch_op:
        batch_op.drop_constraint("uq_inventory_number", type_="unique")
        batch_op.create_unique_constraint(
            "uq_inventory_items_category", ["category", "inventory_nr"]
        )
        batch_op.drop_column("number_prefix")
