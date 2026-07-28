from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    idp_sub: str
    email: EmailStr
    name: str
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    idp_sub: str
    email: EmailStr
    name: str


class UserUpdate(BaseModel):
    idp_sub: str | None = None
    email: EmailStr | None = None
    name: str | None = None
