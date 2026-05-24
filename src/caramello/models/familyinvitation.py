from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship
from pydantic import EmailStr

class FamilyInvitation(SQLModel, table=True):
    """Manages the invitation flow for families."""
    __tablename__ = "family_invitation"

    id: Optional['int'] = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    family_id: 'int' = Field(foreign_key='family.id', nullable=False)
    inviter_id: 'int' = Field(foreign_key='user.id', nullable=False)
    invitee_email: EmailStr = Field(nullable=False)
    status: 'str' = Field(max_length=20, default='pending', nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at: datetime = Field(nullable=False)

    family: 'Family' = Relationship(back_populates='invitations')
    inviter: 'User' = Relationship(back_populates='sent_invitations')

class FamilyInvitationRead(SQLModel):
    uuid: UUID
    family_id: 'int'
    inviter_id: 'int'
    invitee_email: EmailStr
    status: 'str'
    created_at: datetime
    expires_at: datetime

class FamilyInvitationCreate(SQLModel):
    family_id: 'int'
    inviter_id: 'int'
    invitee_email: EmailStr
    status: Optional['str'] = None
    expires_at: datetime

class FamilyInvitationUpdate(SQLModel):
    family_id: Optional['int'] = None
    inviter_id: Optional['int'] = None
    invitee_email: Optional[EmailStr] = None
    status: Optional['str'] = None
    expires_at: Optional[datetime] = None
