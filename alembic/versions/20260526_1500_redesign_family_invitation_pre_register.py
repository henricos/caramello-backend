"""redesign_family_invitation_pre_register

Redesenha a tabela family_invitation conforme D-01 (Phase 4 CONTEXT.md):
- Remove invitee_email e expires_at (modelo antigo: convite por email com expiração)
- Adiciona email (str) e status (default 'pending_login') — modelo novo: pré-registro

Revision ID: 0b1c2d3e4f5a
Revises: a1b2c3d4e5f6
Create Date: 2026-05-26 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401 — mantido para consistência com initial_schema
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0b1c2d3e4f5a"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """D-01: troca invitee_email/expires_at por email/status pending_login."""
    # Drop colunas obsoletas
    op.drop_column("family_invitation", "invitee_email")
    op.drop_column("family_invitation", "expires_at")

    # Add novas colunas com server_default temporário para satisfazer NOT NULL
    # em linhas pré-existentes (Pitfall 5 do RESEARCH.md Phase 4).
    op.add_column(
        "family_invitation",
        sa.Column("email", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "family_invitation",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending_login",
        ),
    )

    # Remover server_default após popular linhas existentes — evita constraint
    # permanente no schema.
    op.alter_column("family_invitation", "email", server_default=None)
    op.alter_column("family_invitation", "status", server_default=None)


def downgrade() -> None:
    """Reverte para o schema do initial_schema (com invitee_email/expires_at)."""
    op.drop_column("family_invitation", "email")
    op.drop_column("family_invitation", "status")
    op.add_column(
        "family_invitation",
        sa.Column("invitee_email", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "family_invitation",
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.alter_column("family_invitation", "invitee_email", server_default=None)
    op.alter_column("family_invitation", "expires_at", server_default=None)
