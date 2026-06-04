"""0003_movement_schema_update

Remove colunas obsoletas da tabela movement:
- DROP COLUMN type (D-01: substituído por amount com sinal)
- DROP COLUMN is_duplicate (D-02: substituído por potential_duplicates[] na resposta)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"  # D-03: aponta para 0002
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("movement", "type")
    op.drop_column("movement", "is_duplicate")
    # Nota: NUMERIC(15,2) já aceita valores negativos — nenhum ALTER necessário


def downgrade() -> None:
    op.add_column(
        "movement",
        sa.Column("type", sa.String(length=10), nullable=False, server_default=sa.text("'credito'")),
    )
    op.add_column(
        "movement",
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
