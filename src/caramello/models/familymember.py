from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship
from pydantic import EmailStr

class FamilyMember(SQLModel, table=True):
    """Association table connecting Users and Families, defining the role of each member."""
    __tablename__ = "family_member"

    user_id: Optional['int'] = Field(primary_key=True, foreign_key='user.id', default=None)
    family_id: Optional['int'] = Field(primary_key=True, foreign_key='family.id', default=None)
    role: 'str' = Field(max_length=20, default='member', nullable=False)
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    user: 'User' = Relationship()
    family: 'Family' = Relationship()

class FamilyMemberRead(SQLModel):
    user_id: 'int'
    family_id: 'int'
    role: 'str'
    joined_at: datetime

class FamilyMemberCreate(SQLModel):
    user_id: 'int'
    family_id: 'int'
    role: Optional['str'] = None
    joined_at: datetime

class FamilyMemberUpdate(SQLModel):
    user_id: Optional['int'] = None
    family_id: Optional['int'] = None
    role: Optional['str'] = None
    joined_at: Optional[datetime] = None

