from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    family_id: int
    name: str
    type: str
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AccountCreate(BaseModel):
    family_id: int
    name: str
    type: str
    currency: str | None = None
    is_active: bool | None = None


class AccountUpdate(BaseModel):
    family_id: int | None = None
    name: str | None = None
    type: str | None = None
    currency: str | None = None
    is_active: bool | None = None


class MovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    account_id: int
    date: datetime
    amount: Decimal
    description: str
    import_hash: str | None
    created_at: datetime
    updated_at: datetime


class MovementCreate(BaseModel):
    account_id: int
    date: datetime
    amount: Decimal
    description: str
    import_hash: str | None = None


class MovementUpdate(BaseModel):
    account_id: int | None = None
    date: datetime | None = None
    amount: Decimal | None = None
    description: str | None = None
    import_hash: str | None = None


class FinancialEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class FinancialEntryCreate(BaseModel):
    movement_id: int
    subcategory_id: int
    competencia_year: int
    competencia_month: int
    notes: str | None = None
    is_recorrente: bool | None = None
    responsible_user_uuid: UUID | None = None


class FinancialEntryUpdate(BaseModel):
    movement_id: int | None = None
    subcategory_id: int | None = None
    competencia_year: int | None = None
    competencia_month: int | None = None
    notes: str | None = None
    is_recorrente: bool | None = None
    responsible_user_uuid: UUID | None = None


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    family_id: int
    name: str
    created_at: datetime
    updated_at: datetime


class CategoryCreate(BaseModel):
    family_id: int
    name: str


class CategoryUpdate(BaseModel):
    family_id: int | None = None
    name: str | None = None


class SubcategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    category_id: int
    name: str
    created_at: datetime
    updated_at: datetime


class SubcategoryCreate(BaseModel):
    category_id: int
    name: str


class SubcategoryUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = None
