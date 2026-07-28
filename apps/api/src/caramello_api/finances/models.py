from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from caramello_api.shared.base import Base


class Account(Base):
    """Bank account, card, savings or investment account of a family member."""

    __tablename__ = "account"

    __table_args__ = (Index("ix_account_family_id", "family_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)
    uuid: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False, default=uuid4)
    family_id: Mapped[int] = mapped_column(Integer, ForeignKey("family.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class Movement(Base):
    """Raw financial movement imported from a bank statement."""

    __tablename__ = "movement"

    __table_args__ = (Index("ix_movement_account_id", "account_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)
    uuid: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False, default=uuid4)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("account.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    import_hash: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class FinancialEntry(Base):
    """
    Classified financial entry. Inherits amount and type from Movement (1:1 relation).
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)
    uuid: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False, default=uuid4)
    movement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("movement.id"), unique=True, nullable=False
    )
    subcategory_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subcategory.id"), nullable=False
    )
    competencia_year: Mapped[int] = mapped_column(Integer, nullable=False)
    competencia_month: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_recorrente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    responsible_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class Category(Base):
    """
    Financial classification category — level 1 of the hierarchy. Child: Subcategory.
    """

    __tablename__ = "category"

    __table_args__ = (Index("ix_category_family_id", "family_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)
    uuid: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False, default=uuid4)
    family_id: Mapped[int] = mapped_column(Integer, ForeignKey("family.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class Subcategory(Base):
    """
    Financial classification subcategory — level 2 of the hierarchy. Parent: Category.
    """

    __tablename__ = "subcategory"

    __table_args__ = (Index("ix_subcategory_category_id", "category_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)
    uuid: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False, default=uuid4)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("category.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
