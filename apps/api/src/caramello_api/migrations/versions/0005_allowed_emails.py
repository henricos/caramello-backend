"""allowed_emails

Cria a tabela do allowlist de e-mails — a primeira camada de autorização
(quem pode usar o sistema), complementar a family_member (quais dados a
pessoa alcança). Sem coluna uuid: a tabela nunca é exposta pela API.

Nome no plural por alinhamento com o template do portfólio; as tabelas
anteriores usam singular (user, family, account, ...) pela convenção mais
antiga deste projeto e não são renomeadas — renomear custaria uma migração
destrutiva sem nenhum ganho funcional.

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
