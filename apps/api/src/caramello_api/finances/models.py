from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Column, Index, Numeric
from sqlmodel import Field, SQLModel


class Account(SQLModel, table=True):
    """Conta bancária, cartão, poupança ou investimento de um membro da família."""

    __tablename__ = "account"

    __table_args__ = (Index("ix_account_family_id", "family_id"),)

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    family_id: int = Field(foreign_key="family.id", nullable=False)
    name: str = Field(max_length=100, nullable=False)
    type: str = Field(max_length=20, nullable=False)
    currency: str = Field(max_length=3, default="BRL", nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)


class AccountRead(SQLModel):
    uuid: UUID
    family_id: int
    name: str
    type: str
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AccountCreate(SQLModel):
    family_id: int
    name: str
    type: str
    currency: str | None = None
    is_active: bool | None = None


class AccountUpdate(SQLModel):
    family_id: int | None = None
    name: str | None = None
    type: str | None = None
    currency: str | None = None
    is_active: bool | None = None


class Movement(SQLModel, table=True):
    """Movimentação financeira bruta importada do extrato bancário."""

    __tablename__ = "movement"

    __table_args__ = (Index("ix_movement_account_id", "account_id"),)

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    account_id: int = Field(foreign_key="account.id", nullable=False)
    date: datetime = Field(nullable=False)
    amount: Decimal = Field(sa_column=Column(Numeric(15, 2), nullable=False))
    description: str = Field(max_length=255, nullable=False)
    import_hash: str | None = Field(unique=True, default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)


class MovementRead(SQLModel):
    uuid: UUID
    account_id: int
    date: datetime
    amount: Decimal
    description: str
    import_hash: str | None
    created_at: datetime
    updated_at: datetime


class MovementCreate(SQLModel):
    account_id: int
    date: datetime
    amount: Decimal
    description: str
    import_hash: str | None = None


class MovementUpdate(SQLModel):
    account_id: int | None = None
    date: datetime | None = None
    amount: Decimal | None = None
    description: str | None = None
    import_hash: str | None = None


class FinancialEntry(SQLModel, table=True):
    """
    Lançamento financeiro classificado. Herda valor e tipo de Movement via relação 1:1 (D-05).
    """

    __tablename__ = "financial_entry"

    __table_args__ = (
        Index(
            "ix_financial_entry_competencia_year_competencia_month",
            "competencia_year",
            "competencia_month",
        ),
        Index("ix_financial_entry_subcategory_id", "subcategory_id"),
    )

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    movement_id: int = Field(foreign_key="movement.id", unique=True, nullable=False)
    subcategory_id: int = Field(foreign_key="subcategory.id", nullable=False)
    competencia_year: int = Field(nullable=False)
    competencia_month: int = Field(nullable=False)
    notes: str | None = Field(max_length=500, default=None)
    is_recorrente: bool = Field(default=False, nullable=False)
    responsible_user_id: int | None = Field(foreign_key="user.id", default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)


class FinancialEntryRead(SQLModel):
    uuid: UUID
    movement_id: int
    subcategory_id: int
    competencia_year: int
    competencia_month: int
    notes: str | None
    is_recorrente: bool
    responsible_user_uuid: UUID | None = None
    created_at: datetime
    updated_at: datetime


class FinancialEntryCreate(SQLModel):
    movement_id: int
    subcategory_id: int
    competencia_year: int
    competencia_month: int
    notes: str | None = None
    is_recorrente: bool | None = None
    responsible_user_uuid: UUID | None = None


class FinancialEntryUpdate(SQLModel):
    movement_id: int | None = None
    subcategory_id: int | None = None
    competencia_year: int | None = None
    competencia_month: int | None = None
    notes: str | None = None
    is_recorrente: bool | None = None
    responsible_user_uuid: UUID | None = None


class Category(SQLModel, table=True):
    """
    Categoria de classificação financeira — nível 1 da hierarquia (D-06). Filha: Subcategory.
    """

    __tablename__ = "category"

    __table_args__ = (Index("ix_category_family_id", "family_id"),)

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    family_id: int = Field(foreign_key="family.id", nullable=False)
    name: str = Field(max_length=100, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)


class CategoryRead(SQLModel):
    uuid: UUID
    family_id: int
    name: str
    created_at: datetime
    updated_at: datetime


class CategoryCreate(SQLModel):
    family_id: int
    name: str


class CategoryUpdate(SQLModel):
    family_id: int | None = None
    name: str | None = None


class Subcategory(SQLModel, table=True):
    """
    Subcategoria de classificação financeira — nível 2 da hierarquia (D-06). Pai: Category.
    """

    __tablename__ = "subcategory"

    __table_args__ = (Index("ix_subcategory_category_id", "category_id"),)

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    category_id: int = Field(foreign_key="category.id", nullable=False)
    name: str = Field(max_length=100, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)


class SubcategoryRead(SQLModel):
    uuid: UUID
    category_id: int
    name: str
    created_at: datetime
    updated_at: datetime


class SubcategoryCreate(SQLModel):
    category_id: int
    name: str


class SubcategoryUpdate(SQLModel):
    category_id: int | None = None
    name: str | None = None
