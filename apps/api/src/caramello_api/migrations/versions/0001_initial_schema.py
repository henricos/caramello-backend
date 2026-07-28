"""initial_schema

Schema inicial do domínio família — 4 tabelas base consolidadas:
- user: usuários provisionados via Keycloak (idp_sub, email, name)
- family: grupos familiares
- family_member: associação M:M entre user e family (role, joined_at)
- family_invitation: pré-registro de membro por email (D-01)

Revision ID: 0001
Revises:
Create Date: 2026-05-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("idp_sub", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column(
            "name", sa.String(length=100), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("idp_sub"),
        sa.UniqueConstraint("uuid"),
    )
    op.create_table(
        "family",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column(
            "name", sa.String(length=100), nullable=False
        ),
        sa.Column(
            "description",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "status", sa.String(length=20), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
    )
    op.create_table(
        "family_member",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column(
            "role", sa.String(length=20), nullable=False
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["family.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("user_id", "family_id"),
    )
    op.create_table(
        "family_invitation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("inviter_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column(
            "status", sa.String(length=20), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["family.id"]),
        sa.ForeignKeyConstraint(["inviter_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
    )


def downgrade() -> None:
    op.drop_table("family_invitation")
    op.drop_table("family_member")
    op.drop_table("family")
    op.drop_table("user")
