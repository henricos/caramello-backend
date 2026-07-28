from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FamilyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class FamilyCreate(BaseModel):
    name: str
    description: str | None = None
    status: str | None = None


class FamilyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class FamilyInvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    family_uuid: UUID
    inviter_uuid: UUID
    email: str
    status: str
    created_at: datetime


class FamilyInvitationCreate(BaseModel):
    family_uuid: UUID
    inviter_uuid: UUID
    email: str
    status: str | None = None


class FamilyInvitationUpdate(BaseModel):
    family_uuid: UUID | None = None
    inviter_uuid: UUID | None = None
    email: str | None = None
    status: str | None = None
