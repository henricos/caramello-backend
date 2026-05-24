from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship
from pydantic import EmailStr
from caramello.models.familymember import FamilyMember

class User(SQLModel, table=True):
    """Represents a system user, provisioned on first authentication via Keycloak."""
    __tablename__ = "user"

    id: Optional['int'] = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    idp_sub: 'str' = Field(unique=True, nullable=False)
    email: EmailStr = Field(unique=True, nullable=False)
    name: 'str' = Field(max_length=100, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    families: list['Family'] = Relationship(back_populates='members', link_model=FamilyMember)
    sent_invitations: list['FamilyInvitation'] = Relationship(back_populates='inviter')

class UserRead(SQLModel):
    uuid: UUID
    idp_sub: 'str'
    email: EmailStr
    name: 'str'
    created_at: datetime
    updated_at: datetime

class UserCreate(SQLModel):
    idp_sub: 'str'
    email: EmailStr
    name: 'str'

class UserUpdate(SQLModel):
    idp_sub: Optional['str'] = None
    email: Optional[EmailStr] = None
    name: Optional['str'] = None
