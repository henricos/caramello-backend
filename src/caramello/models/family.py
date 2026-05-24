from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship
from pydantic import EmailStr
from caramello.models.familymember import FamilyMember

class Family(SQLModel, table=True):
    """Represents a family group in the system."""
    __tablename__ = "family"

    id: Optional['int'] = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    name: 'str' = Field(max_length=100, nullable=False)
    description: Optional['str'] = Field(max_length=255, default=None)
    status: 'str' = Field(max_length=20, default='active', nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    members: list['User'] = Relationship(back_populates='families', link_model=FamilyMember)
    invitations: list['FamilyInvitation'] = Relationship(back_populates='family')

class FamilyRead(SQLModel):
    uuid: UUID
    name: 'str'
    description: Optional['str']
    status: 'str'
    created_at: datetime
    updated_at: datetime

class FamilyCreate(SQLModel):
    name: 'str'
    description: Optional['str'] = None
    status: Optional['str'] = None

class FamilyUpdate(SQLModel):
    name: Optional['str'] = None
    description: Optional['str'] = None
    status: Optional['str'] = None

