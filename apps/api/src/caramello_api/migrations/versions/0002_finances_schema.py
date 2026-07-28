"""0002_finances_schema

Schema of the finances domain — 5 tables:
- category: financial classification categories (level 1)
- subcategory: subcategories (level 2, FK -> category)
- account: the family's bank accounts/cards
- movement: raw statement movements (amount: NUMERIC(15,2))
- financial_entry: classified entries (1:1 with movement, through movement_id UNIQUE)

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The tables with no dependency inside the finances domain come first
    op.create_table(
        "category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column(
            "name", sa.String(length=100), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["family.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
    )
    op.create_index("ix_category_family_id", "category", ["family_id"], unique=False)

    op.create_table(
        "account",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column(
            "name", sa.String(length=100), nullable=False
        ),
        sa.Column(
            "type", sa.String(length=20), nullable=False
        ),
        sa.Column(
            "currency", sa.String(length=3), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["family.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
    )
    op.create_index("ix_account_family_id", "account", ["family_id"], unique=False)

    # Subcategory depends on category
    op.create_table(
        "subcategory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column(
            "name", sa.String(length=100), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
    )
    op.create_index(
        "ix_subcategory_category_id", "subcategory", ["category_id"], unique=False
    )

    # Movement depends on account; amount is NUMERIC(15,2) — never a float (D-02)
    op.create_table(
        "movement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column(
            "type", sa.String(length=10), nullable=False
        ),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column(
            "description", sa.String(length=255), nullable=False
        ),
        sa.Column("import_hash", sa.String(), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_hash"),  # statement deduplication (D-10)
        sa.UniqueConstraint("uuid"),
    )
    op.create_index(
        "ix_movement_account_id", "movement", ["account_id"], unique=False
    )

    # FinancialEntry depends on movement and subcategory; movement_id UNIQUE -> 1:1
    # (D-05). It carries no amount or type column of its own (D-05).
    op.create_table(
        "financial_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("movement_id", sa.Integer(), nullable=False),
        sa.Column("subcategory_id", sa.Integer(), nullable=False),
        sa.Column("competencia_year", sa.Integer(), nullable=False),
        sa.Column("competencia_month", sa.Integer(), nullable=False),
        sa.Column(
            "notes", sa.String(length=500), nullable=True
        ),
        sa.Column("is_recorrente", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["movement_id"], ["movement.id"]),
        sa.ForeignKeyConstraint(["subcategory_id"], ["subcategory.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("movement_id"),  # guarantees the 1:1 with movement (D-05)
        sa.UniqueConstraint("uuid"),
    )
    op.create_index(
        "ix_financial_entry_competencia_year_competencia_month",
        "financial_entry",
        ["competencia_year", "competencia_month"],
        unique=False,
    )
    op.create_index(
        "ix_financial_entry_subcategory_id",
        "financial_entry",
        ["subcategory_id"],
        unique=False,
    )


def downgrade() -> None:
    # Drop in reverse FK order
    # (financial_entry -> movement -> subcategory -> account -> category)
    op.drop_index(
        "ix_financial_entry_subcategory_id", table_name="financial_entry"
    )
    op.drop_index(
        "ix_financial_entry_competencia_year_competencia_month",
        table_name="financial_entry",
    )
    op.drop_table("financial_entry")

    op.drop_index("ix_movement_account_id", table_name="movement")
    op.drop_table("movement")

    op.drop_index("ix_subcategory_category_id", table_name="subcategory")
    op.drop_table("subcategory")

    op.drop_index("ix_account_family_id", table_name="account")
    op.drop_table("account")

    op.drop_index("ix_category_family_id", table_name="category")
    op.drop_table("category")
