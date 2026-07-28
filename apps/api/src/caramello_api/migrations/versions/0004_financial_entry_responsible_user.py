"""0004_financial_entry_responsible_user

Adiciona campo responsible_user_id em financial_entry.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "financial_entry",
        sa.Column(
            "responsible_user_id",
            sa.Integer(),
            sa.ForeignKey("user.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("financial_entry", "responsible_user_id")
