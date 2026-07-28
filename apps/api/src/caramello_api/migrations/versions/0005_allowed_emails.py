"""allowed_emails

Creates the e-mail allowlist table — the first authorization layer (who may use
the system at all), complementing family_member (which data that person
reaches). No uuid column: the table is never exposed by the api.

The name is plural to align with the portfolio template; the earlier tables use
the singular (user, family, account, ...) following this project's older
convention and are NOT renamed — renaming would cost a destructive migration
for no functional gain.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "allowed_emails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_allowed_emails_email"),
    )


def downgrade() -> None:
    op.drop_table("allowed_emails")
