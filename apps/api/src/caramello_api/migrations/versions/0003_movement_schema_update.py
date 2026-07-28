"""0003_movement_schema_update

Drops the obsolete columns of the movement table:
- DROP COLUMN type (D-01: replaced by a signed amount)
- DROP COLUMN is_duplicate (D-02: replaced by potential_duplicates[] in the response)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"  # D-03: points at 0002
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("movement", "type")
    op.drop_column("movement", "is_duplicate")
    # Note: NUMERIC(15,2) already accepts negative values — no ALTER needed


def downgrade() -> None:
    op.add_column(
        "movement",
        sa.Column("type", sa.String(length=10), nullable=False, server_default=sa.text("'credito'")),
    )
    op.add_column(
        "movement",
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
