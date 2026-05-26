from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

from caramello.users.models import User


class FamilyMember(SQLModel, table=True):
    """
    Association table connecting Users and Families, defining the role of each member.
    """

    __tablename__ = "family_member"

    user_id: int | None = Field(primary_key=True, foreign_key="user.id", default=None)
    family_id: int | None = Field(
        primary_key=True, foreign_key="family.id", default=None
    )
    role: str = Field(max_length=20, default="member", nullable=False)
    joined_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )

    user: "User" = Relationship()
    family: "Family" = Relationship()


class Family(SQLModel, table=True):
    """Represents a family group in the system."""

    __tablename__ = "family"

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    name: str = Field(max_length=100, nullable=False)
    description: str | None = Field(max_length=255, default=None)
    status: str = Field(max_length=20, default="active", nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )

    members: list["User"] = Relationship(
        back_populates="families", link_model=FamilyMember
    )
    invitations: list["FamilyInvitation"] = Relationship(back_populates="family")


class FamilyRead(SQLModel):
    uuid: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class FamilyCreate(SQLModel):
    name: str
    description: str | None = None
    status: str | None = None


class FamilyUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class FamilyInvitation(SQLModel, table=True):
    """Pré-registro de membro de família por email (D-01)."""

    __tablename__ = "family_invitation"

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    family_id: int = Field(foreign_key="family.id", nullable=False)
    inviter_id: int = Field(foreign_key="user.id", nullable=False)
    email: str = Field(nullable=False)
    status: str = Field(max_length=20, default="pending_login", nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )

    family: "Family" = Relationship(back_populates="invitations")
    inviter: "User" = Relationship(back_populates="sent_invitations")


class FamilyInvitationRead(SQLModel):
    uuid: UUID
    family_id: int
    inviter_id: int
    email: str
    status: str
    created_at: datetime


class FamilyInvitationCreate(SQLModel):
    family_id: int
    inviter_id: int
    email: str
    status: str | None = None


class FamilyInvitationUpdate(SQLModel):
    family_id: int | None = None
    inviter_id: int | None = None
    email: str | None = None
    status: str | None = None
